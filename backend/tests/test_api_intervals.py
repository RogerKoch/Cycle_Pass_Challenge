from datetime import date, timedelta

import pytest

from backend.engine.imported_training import ActivityRecord
from backend.integrations.intervals_icu import IcuError, WellnessRecord
from backend.tests.test_intervals_icu import FakeClient

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
THIS_MONDAY = TODAY - timedelta(days=TODAY.weekday())


@pytest.fixture()
def profile(client):
    start = THIS_MONDAY - timedelta(weeks=2)  # diese Woche = Base Woche 1
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": start.isoformat()})
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30,
                                       "checkin_date": (TODAY - timedelta(days=20)).isoformat()})
    return client


def _use_fake(app, **kwargs):
    fake = FakeClient(**kwargs)
    app.config["INTERVALS_ICU_CLIENT"] = fake
    return fake


def _ride(day, icu_id="i1", joules=900_000, seconds=5400, intensity=72.0):
    return ActivityRecord(icu_id=icu_id, day=day, type="VirtualRide", name="Zwift", moving_seconds=seconds,
                          joules=joules, intensity=intensity, training_load=70)


def test_status_without_api_key(client):
    body = client.get("/api/intervals/status").get_json()
    assert body["configured"] is False
    assert client.post("/api/intervals/sync").status_code == 409


def test_status_never_exposes_the_api_key(app, client):
    app.config["INTERVALS_ICU_API_KEY"] = "super-secret"
    body = client.get("/api/intervals/status")
    assert body.get_json()["configured"] is True
    assert b"super-secret" not in body.data


def test_sync_imports_and_reports_counts(app, profile):
    _use_fake(app, activities=[_ride(YESTERDAY)], wellness=[WellnessRecord(TODAY, weight_kg=73.1, resting_hr=49)])
    body = profile.post("/api/intervals/sync").get_json()
    assert (body["synced"], body["activities"], body["wellness_days"], body["checkins_created"]) == (True, 1, 1, 1)
    status = profile.get("/api/intervals/status").get_json()
    assert status["last_sync"] is not None and status["activities"] == 1
    checkins = profile.get("/api/checkins").get_json()
    assert checkins[0]["source"] == "intervals" and checkins[-1]["source"] == "manual"


def test_if_stale_skips_recent_sync(app, profile):
    _use_fake(app)
    assert profile.post("/api/intervals/sync").get_json()["synced"] is True
    assert profile.post("/api/intervals/sync?if_stale=1").get_json()["synced"] is False


def test_sync_error_is_reported(app, profile):
    _use_fake(app, error=IcuError("API-Key ungültig"))
    response = profile.post("/api/intervals/sync")
    assert response.status_code == 502
    assert profile.get("/api/intervals/status").get_json()["last_error"] == "API-Key ungültig"


def test_imported_ride_today_sets_cycling_kcal_from_kilojoules(app, profile):
    _use_fake(app, activities=[_ride(TODAY, joules=812_000, seconds=4500)])
    profile.post("/api/intervals/sync")
    body = profile.get("/api/plan/today").get_json()
    assert body["nutrition"]["cycling_kcal"] == pytest.approx(812)
    assert body["training"]["imported"][0]["kilojoules"] == pytest.approx(812)


def test_import_overrides_manual_feedback(app, profile):
    profile.get("/api/plan/today")
    profile.patch(f"/api/calendar/day/{TODAY.isoformat()}", json={"status": "skipped"})
    assert profile.get("/api/plan/today").get_json()["nutrition"]["cycling_kcal"] == 0
    _use_fake(app, activities=[_ride(TODAY, joules=600_000)])
    profile.post("/api/intervals/sync")
    assert profile.get("/api/plan/today").get_json()["nutrition"]["cycling_kcal"] == pytest.approx(600)


def test_day_view_lists_imported_activities(app, profile):
    _use_fake(app, activities=[_ride(YESTERDAY), ActivityRecord("i2", YESTERDAY, "WeightTraining", "Kraft", 3000)])
    profile.post("/api/intervals/sync")
    day = profile.get(f"/api/calendar/day/{YESTERDAY.isoformat()}").get_json()
    assert [a["type"] for a in day["imported"]] == ["VirtualRide", "WeightTraining"]
    assert day["imported"][0]["minutes"] == 90


def test_low_energy_availability_uses_imported_kilojoules(app, profile):
    days = [TODAY - timedelta(days=i) for i in (1, 2, 3)]
    _use_fake(app, activities=[_ride(d, icu_id=f"i{d.day}", joules=1_500_000) for d in days])
    profile.post("/api/intervals/sync")
    for d in days:
        profile.put(f"/api/intake/{d.isoformat()}", json={"kcal": 2400, "protein_g": 150, "carbs_g": 300, "fat_g": 70})
    findings = {f["trigger_id"] for f in profile.get("/api/review").get_json()["findings"]}
    # (2400 - 1500 kcal Rad) / 57 kg FFM ~ 15.8 < 30
    assert "low_energy_availability" in findings
