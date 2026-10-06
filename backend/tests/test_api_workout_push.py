from datetime import date, timedelta

import pytest

from backend.integrations.intervals_icu import IcuError
from backend.tests.test_intervals_icu import FakeClient

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
THIS_MONDAY = TODAY - timedelta(days=TODAY.weekday())
NEXT_MONDAY = THIS_MONDAY + timedelta(weeks=1)


@pytest.fixture()
def profile(client):
    start = THIS_MONDAY - timedelta(weeks=2)  # diese Woche = Base Woche 1
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": start.isoformat()})
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30})
    return client


def _use_fake(app, **kwargs):
    fake = FakeClient(**kwargs)
    app.config["INTERVALS_ICU_CLIENT"] = fake
    return fake


def _pushed_days(fake):
    return {e["start_date_local"][:10] for e in fake.upserted}


def test_zwo_download_of_planned_ride(profile):
    tuesday = (NEXT_MONDAY + timedelta(days=1)).isoformat()
    response = profile.get(f"/api/calendar/day/{tuesday}/zwo")
    assert response.status_code == 200
    assert response.headers["Content-Disposition"] == f'attachment; filename="{tuesday}.zwo"'
    assert b"<SteadyState" in response.data


def test_zwo_download_without_ride_is_404(profile):
    friday = (NEXT_MONDAY + timedelta(days=4)).isoformat()  # Ruhetag der Standardwoche
    assert profile.get(f"/api/calendar/day/{friday}/zwo").status_code == 404


def test_sync_pushes_next_seven_days(app, profile):
    fake = _use_fake(app)
    body = profile.post("/api/intervals/sync").get_json()
    assert body["workouts_pushed"] == len(fake.upserted) > 0
    assert body["push_error"] is None
    assert all(TODAY.isoformat() <= d <= (TODAY + timedelta(days=6)).isoformat() for d in _pushed_days(fake))


def test_skipping_a_day_removes_its_workout(app, profile):
    fake = _use_fake(app, events=[{"id": 9, "external_id": f"cpc-{TOMORROW.isoformat()}",
                                   "start_date_local": f"{TOMORROW.isoformat()}T00:00:00"}])
    response = profile.patch(f"/api/calendar/day/{TOMORROW.isoformat()}", json={"status": "skipped"})
    assert response.status_code == 200
    assert fake.deleted == [9]
    assert TOMORROW.isoformat() not in _pushed_days(fake)


def test_done_day_is_left_untouched(app, profile):
    fake = _use_fake(app)
    profile.patch(f"/api/calendar/day/{TODAY.isoformat()}", json={"status": "done"})
    assert fake.upserted and TODAY.isoformat() not in _pushed_days(fake)


def test_push_error_does_not_block_calendar_change(app, profile):
    _use_fake(app, push_error=IcuError("intervals.icu antwortet mit HTTP 500"))
    response = profile.patch(f"/api/calendar/day/{TOMORROW.isoformat()}", json={"status": "skipped"})
    assert response.status_code == 200
    assert profile.post("/api/intervals/sync").get_json()["push_error"] == "intervals.icu antwortet mit HTTP 500"


def test_calendar_change_without_api_key_does_not_push(profile):
    response = profile.patch(f"/api/calendar/day/{TOMORROW.isoformat()}", json={"status": "skipped"})
    assert response.status_code == 200
