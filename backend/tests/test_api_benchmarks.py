from datetime import date, timedelta

import pytest

TODAY = date.today()
THIS_MONDAY = TODAY - timedelta(days=TODAY.weekday())
NEXT_MONDAY = THIS_MONDAY + timedelta(weeks=1)


@pytest.fixture()
def profile(client):
    start = THIS_MONDAY - timedelta(weeks=2)  # Base, Kraftphase 1
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": start.isoformat()})
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30})
    return client


def _trigger_ids(client):
    return {f["trigger_id"] for f in client.get("/api/review").get_json()["findings"]}


def test_without_tests_benchmark_is_due_today(profile):
    body = profile.get("/api/strength-benchmarks").get_json()
    assert (body["tests"], body["current"], body["next_due"], body["interval_weeks"]) == ([], None, TODAY.isoformat(), 4)
    assert body["stages"]["pushup_variant"] is None


def test_create_benchmark_derives_stages(profile):
    response = profile.post("/api/strength-benchmarks", json={
        "pushup_reps": 15, "pushup_variant": "knie", "row_reps": 9, "plank_s": 75})
    assert response.status_code == 201
    body = profile.get("/api/strength-benchmarks").get_json()
    assert body["stages"]["pushup_variant"] == "standard"
    assert body["stages"]["rows_feet_elevated"] is False
    assert body["next_due"] == (TODAY + timedelta(weeks=4)).isoformat()


def test_interval_from_profile_controls_next_due(profile):
    profile.put("/api/profile", json={"benchmark_interval_weeks": 2})
    profile.post("/api/strength-benchmarks", json={"plank_s": 60})
    assert profile.get("/api/strength-benchmarks").get_json()["next_due"] == (TODAY + timedelta(weeks=2)).isoformat()


@pytest.mark.parametrize("payload", [
    {},
    {"pushup_reps": 10},  # Variante fehlt
    {"pushup_reps": 10, "pushup_variant": "einarmig"},
    {"side_plank_s": 20},  # gestreckt/Knie fehlt
    {"plank_s": -1},
    {"plank_s": True},
])
def test_rejects_invalid_benchmarks(profile, payload):
    assert profile.post("/api/strength-benchmarks", json=payload).status_code == 400


def test_calendar_shows_stage_from_benchmark(profile):
    profile.post("/api/strength-benchmarks", json={"pushup_reps": 6, "pushup_variant": "inkline"})
    monday = profile.get(f"/api/calendar/day/{NEXT_MONDAY.isoformat()}").get_json()
    pushups = next(e for e in monday["strength"]["exercises"] if e["name"] == "Liegestütz-Progression")
    assert pushups["note"].startswith("Deine Stufe: Inkline")


def test_review_reminds_when_benchmark_is_due(profile):
    assert "strength_benchmark_due" in _trigger_ids(profile)
    profile.post("/api/strength-benchmarks", json={"plank_s": 60})
    assert "strength_benchmark_due" not in _trigger_ids(profile)


def test_profile_validates_benchmark_interval(profile):
    assert profile.put("/api/profile", json={"benchmark_interval_weeks": 1}).status_code == 400
    assert profile.put("/api/profile", json={"benchmark_interval_weeks": 9}).status_code == 400
    assert profile.put("/api/profile", json={"benchmark_interval_weeks": 3}).get_json()["benchmark_interval_weeks"] == 3


@pytest.mark.parametrize("value", [1e999, 12.7])
def test_non_integer_values_are_rejected_with_400(profile, value):
    response = profile.post("/api/strength-benchmarks", json={"plank_s": value})
    assert response.status_code == 400
    assert profile.put("/api/profile", json={"benchmark_interval_weeks": value}).status_code == 400


def test_same_day_retest_replaces_earlier_value(profile):
    profile.post("/api/strength-benchmarks", json={"plank_s": 60})
    profile.post("/api/strength-benchmarks", json={"plank_s": 90})
    body = profile.get("/api/strength-benchmarks").get_json()
    assert body["current"]["plank_s"] == 90
    assert [t["plank_s"] for t in body["tests"]] == [90, 60]
