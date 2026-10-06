from datetime import date, datetime, timedelta, timezone

import pytest
import requests

from backend.engine.cycling_sessions import build_cycling_session
from backend.engine.imported_training import ActivityRecord
from backend.extensions import db
from backend.integrations import intervals_icu
from backend.integrations.intervals_icu import (
    IcuClient,
    IcuError,
    WellnessRecord,
    get_state,
    is_stale,
    parse_activity,
    parse_wellness,
    push_workouts,
    sync,
)
from backend.models.checkins import Checkin
from backend.models.intervals import IcuActivity, IcuWellness

TODAY = date(2026, 10, 20)


class FakeClient:
    """Liefert vorgegebene Daten wie IcuClient."""

    def __init__(self, activities=None, wellness=None, error=None, events=None, push_error=None):
        self.activities = activities or []
        self.wellness = wellness or []
        self.error = error
        self.events = events or []  # Kalender-Events in intervals.icu
        self.push_error = push_error
        self.upserted = []
        self.deleted = []

    def fetch_activities(self, oldest, newest):
        if self.error:
            raise self.error
        return list(self.activities)

    def fetch_wellness(self, oldest, newest):
        return list(self.wellness)

    def fetch_workout_events(self, oldest, newest):
        return [e for e in self.events if oldest.isoformat() <= e["start_date_local"][:10] <= newest.isoformat()]

    def upsert_workouts(self, events):
        if self.push_error:
            raise self.push_error
        self.upserted.extend(events)

    def delete_event(self, event_id):
        self.deleted.append(event_id)


def _ride(icu_id="i100", day=TODAY, **kwargs):
    return ActivityRecord(icu_id=icu_id, day=day, type="VirtualRide", moving_seconds=3600, joules=700_000, **kwargs)


def _manual_checkin(day, weight=74.0, bodyfat=23.0, muscle=30.0):
    db.session.add(Checkin(checkin_date=day, weight_kg=weight, bodyfat_pct=bodyfat, muscle_kg=muscle))
    db.session.commit()


# --- Parser --------------------------------------------------------------


def test_parse_activity_maps_api_fields():
    record = parse_activity({
        "id": "i12345", "start_date_local": "2026-10-19T07:30:00", "type": "VirtualRide", "name": "Zwift",
        "moving_time": 3725, "icu_joules": 812345, "calories": 790, "icu_training_load": 65,
        "icu_average_watts": 180, "icu_weighted_avg_watts": 195, "average_heartrate": 138.5, "icu_intensity": 86.7,
    })
    assert (record.icu_id, record.day, record.type, record.moving_seconds) == ("i12345", date(2026, 10, 19), "VirtualRide", 3725)
    assert (record.joules, record.training_load, record.weighted_watts, record.intensity) == (812345, 65, 195, 86.7)


def test_parse_activity_skips_entries_without_date():
    assert parse_activity({"id": "i1", "_note": "STRAVA activities are not available via the API"}) is None


def test_parse_wellness_maps_api_fields():
    record = parse_wellness({"id": "2026-10-19", "restingHR": 48, "hrv": 62.5, "weight": 73.4, "bodyFat": 21.8,
                             "sleepSecs": 26100, "sleepScore": 81})
    assert record == WellnessRecord(date(2026, 10, 19), 48, 62.5, 73.4, 21.8, 26100, 81)


# --- Client --------------------------------------------------------------


class _Response:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


def test_client_uses_basic_auth_with_api_key_username(monkeypatch):
    calls = {}

    def fake_request(method, url, params, auth, timeout):
        calls.update(method=method, url=url, params=params, auth=auth)
        return _Response(200, [{"id": "2026-10-19", "weight": 73.4}])

    monkeypatch.setattr(intervals_icu.requests, "request", fake_request)
    result = IcuClient("secret").fetch_wellness(date(2026, 10, 1), date(2026, 10, 19))
    assert (calls["method"], calls["auth"]) == ("GET", ("API_KEY", "secret"))
    assert calls["url"].endswith("/athlete/0/wellness")
    assert calls["params"] == {"oldest": "2026-10-01", "newest": "2026-10-19"}
    assert result[0].weight_kg == 73.4


@pytest.mark.parametrize("status,message", [(401, "API-Key"), (500, "HTTP 500")])
def test_client_raises_readable_errors(monkeypatch, status, message):
    monkeypatch.setattr(intervals_icu.requests, "request", lambda *a, **k: _Response(status, {}))
    with pytest.raises(IcuError, match=message):
        IcuClient("secret").fetch_activities(date(2026, 10, 1), date(2026, 10, 19))


def test_client_wraps_network_errors(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(intervals_icu.requests, "request", boom)
    with pytest.raises(IcuError, match="nicht erreichbar"):
        IcuClient("secret").fetch_activities(date(2026, 10, 1), date(2026, 10, 19))


# --- Sync ----------------------------------------------------------------


def test_sync_upserts_activities_and_removes_deleted_ones(app):
    sync(FakeClient([_ride("i1"), _ride("i2", TODAY - timedelta(days=1))]), TODAY)
    assert IcuActivity.query.count() == 2
    result = sync(FakeClient([_ride("i1", name="Umbenannt")]), TODAY)
    assert (result.activities, result.activities_removed) == (1, 1)
    assert IcuActivity.query.one().name == "Umbenannt"


def test_sync_keeps_activities_outside_the_window(app):
    db.session.add(IcuActivity(icu_id="old", day=TODAY - timedelta(days=60), type="Ride"))
    db.session.commit()
    sync(FakeClient([]), TODAY)
    assert IcuActivity.query.filter_by(icu_id="old").count() == 1


def test_weigh_in_creates_auto_checkin_with_last_muscle_mass(app):
    _manual_checkin(TODAY - timedelta(days=10), weight=74.0, bodyfat=23.0, muscle=30.5)
    result = sync(FakeClient(wellness=[WellnessRecord(TODAY, weight_kg=73.2, body_fat_pct=22.4)]), TODAY)
    assert result.checkins_created == 1
    checkin = Checkin.query.filter_by(checkin_date=TODAY).one()
    assert (checkin.weight_kg, checkin.bodyfat_pct, checkin.muscle_kg) == (73.2, 22.4, 30.5)
    assert IcuWellness.query.one().checkin_id == checkin.id


def test_missing_body_fat_uses_last_known_value(app):
    _manual_checkin(TODAY - timedelta(days=10), bodyfat=23.0)
    sync(FakeClient(wellness=[WellnessRecord(TODAY, weight_kg=73.2)]), TODAY)
    assert Checkin.query.filter_by(checkin_date=TODAY).one().bodyfat_pct == 23.0


def test_manual_checkin_on_same_day_wins(app):
    _manual_checkin(TODAY, weight=73.0)
    result = sync(FakeClient(wellness=[WellnessRecord(TODAY, weight_kg=73.5)]), TODAY)
    assert result.checkins_created == 0
    assert Checkin.query.filter_by(checkin_date=TODAY).one().weight_kg == 73.0


def test_no_auto_checkin_without_any_previous_checkin(app):
    result = sync(FakeClient(wellness=[WellnessRecord(TODAY, weight_kg=73.5)]), TODAY)
    assert result.checkins_created == 0
    assert result.notes


def test_changed_weigh_in_updates_linked_checkin_instead_of_duplicating(app):
    _manual_checkin(TODAY - timedelta(days=10))
    sync(FakeClient(wellness=[WellnessRecord(TODAY, weight_kg=73.2)]), TODAY)
    result = sync(FakeClient(wellness=[WellnessRecord(TODAY, weight_kg=72.9)]), TODAY)
    assert (result.checkins_created, result.checkins_updated) == (0, 1)
    assert Checkin.query.filter_by(checkin_date=TODAY).one().weight_kg == 72.9


def test_failed_sync_stores_error_and_raises(app):
    with pytest.raises(IcuError):
        sync(FakeClient(error=IcuError("API-Key ungültig")), TODAY)
    assert intervals_icu.get_state("last_error") == "API-Key ungültig"


def test_staleness_after_thirty_minutes(app):
    now = datetime.now(timezone.utc)
    assert is_stale(now)
    sync(FakeClient(), TODAY)
    assert not is_stale(now + timedelta(minutes=29))
    assert is_stale(now + timedelta(minutes=31))


# --- Workout-Push --------------------------------------------------------


def test_client_upserts_workouts_via_bulk_endpoint(monkeypatch):
    calls = {}

    def fake_request(method, url, auth, timeout, **kwargs):
        calls.update(method=method, url=url, **kwargs)
        return _Response(200, [])

    monkeypatch.setattr(intervals_icu.requests, "request", fake_request)
    IcuClient("secret").upsert_workouts([{"external_id": "cpc-2026-10-20"}])
    assert (calls["method"], calls["params"]) == ("POST", {"upsert": "true"})
    assert calls["url"].endswith("/athlete/0/events/bulk")
    assert calls["json"] == [{"external_id": "cpc-2026-10-20"}]


def test_push_upserts_planned_days_as_zwo_workouts(app):
    fake = FakeClient()
    session = build_cycling_session("schluessel_1", "base", 1)
    result = push_workouts(fake, {TODAY: session})
    assert (result.upserted, result.deleted) == (1, 0)
    event = fake.upserted[0]
    assert (event["category"], event["type"], event["name"]) == ("WORKOUT", "Ride", "Sweet Spot 3×10 min")
    assert (event["external_id"], event["start_date_local"]) == ("cpc-2026-10-20", "2026-10-20T00:00:00")
    assert event["filename"].endswith(".zwo") and "<SteadyState" in event["file_contents"]


def test_push_deletes_own_workout_on_day_without_session_but_keeps_foreign_events(app):
    tomorrow = TODAY + timedelta(days=1)
    fake = FakeClient(events=[
        {"id": 1, "external_id": "cpc-2026-10-21", "start_date_local": "2026-10-21T00:00:00"},
        {"id": 2, "external_id": None, "start_date_local": "2026-10-21T00:00:00"},  # selbst geplant
        {"id": 3, "external_id": "cpc-2026-10-20", "start_date_local": "2026-10-20T00:00:00"},
    ])
    result = push_workouts(fake, {TODAY: build_cycling_session("lang", "base", 1), tomorrow: None})
    assert fake.deleted == [1]
    assert (result.upserted, result.deleted) == (1, 1)


def test_push_error_is_stored_and_raised(app):
    fake = FakeClient(push_error=IcuError("intervals.icu antwortet mit HTTP 500"))
    with pytest.raises(IcuError):
        push_workouts(fake, {TODAY: build_cycling_session("lang", "base", 1)})
    assert get_state(intervals_icu.STATE_LAST_PUSH_ERROR) == "intervals.icu antwortet mit HTTP 500"
    push_workouts(FakeClient(), {TODAY: build_cycling_session("lang", "base", 1)})
    assert get_state(intervals_icu.STATE_LAST_PUSH_ERROR) is None
