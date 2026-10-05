from datetime import date, timedelta

import pytest

TODAY = date.today()
THIS_MONDAY = TODAY - timedelta(days=TODAY.weekday())
SIGNALS_OK = {"sleep": 0, "legs": 0, "hunger": 0, "back": 0, "effort": 0}


def _next_weekday(weekday: int) -> date:
    """Naechster Wochentag ab heute (0 = Montag), heute eingeschlossen."""
    return TODAY + timedelta(days=(weekday - TODAY.weekday()) % 7)


@pytest.fixture()
def profile(client):
    # diese Woche = Base Woche 1 -> Defizit 350 aktiv
    start = THIS_MONDAY - timedelta(weeks=2)
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": start.isoformat()})
    return client


def _checkin(client, days_ago: int, weight: float):
    day = (TODAY - timedelta(days=days_ago)).isoformat()
    client.post("/api/checkins", json={"weight_kg": weight, "bodyfat_pct": 23, "muscle_kg": 30, "checkin_date": day})


def _findings(client):
    return {f["trigger_id"]: f for f in client.get("/api/review").get_json()["findings"]}


def _signals(client, days_ago=0, **scores):
    body = {**SIGNALS_OK, **scores, "date": (TODAY - timedelta(days=days_ago)).isoformat()}
    return client.post("/api/signals", json=body)


def _accept(client, trigger_id):
    key = _findings(client)[trigger_id]["key"]
    return client.post("/api/review/decisions", json={"key": key, "decision": "accepted"})


# --- Fragebogen ----------------------------------------------------------


def test_signals_are_upserted_per_day(profile):
    assert _signals(profile, sleep=1).status_code == 201
    response = _signals(profile, sleep=2, resting_hr=52)
    assert response.status_code == 200
    listed = profile.get("/api/signals").get_json()
    assert len(listed) == 1
    assert (listed[0]["sleep"], listed[0]["resting_hr"]) == (2, 52)


@pytest.mark.parametrize("body", [
    {**SIGNALS_OK, "sleep": 4},
    {**SIGNALS_OK, "legs": "2"},
    {"sleep": 0},
    {**SIGNALS_OK, "resting_hr": 200},
    {**SIGNALS_OK, "date": (TODAY + timedelta(days=1)).isoformat()},
])
def test_invalid_signals_are_rejected(profile, body):
    assert profile.post("/api/signals", json=body).status_code == 400


# --- Review --------------------------------------------------------------


def test_review_requires_profile(client):
    assert client.get("/api/review").status_code == 404


def test_review_reminds_about_missing_checkin_and_questionnaire(profile):
    findings = _findings(profile)
    assert {"checkin_due", "signals_due"} <= set(findings)


def test_fast_weight_loss_shows_finding_and_summary(profile):
    _checkin(profile, 14, 74.0)
    _checkin(profile, 7, 73.3)
    _checkin(profile, 0, 72.6)
    review = profile.get("/api/review").get_json()
    assert review["summary"]["trend_kg_per_week"] == pytest.approx(-0.7)
    assert review["summary"]["deficit_kcal"] == 350
    assert "weight_loss_too_fast" in {f["trigger_id"] for f in review["findings"]}


def test_accepting_smaller_deficit_lowers_kcal_target_and_can_be_undone(profile):
    _checkin(profile, 14, 74.0)
    _checkin(profile, 7, 73.3)
    _checkin(profile, 0, 72.6)
    before = profile.get("/api/plan/today").get_json()["nutrition"]["deficit_kcal"]
    response = _accept(profile, "weight_loss_too_fast")
    assert response.status_code == 201
    adjustment = response.get_json()["adjustment"]
    assert (adjustment["kind"], adjustment["value"], adjustment["end_date"]) == ("deficit_delta", -100, None)
    assert profile.get("/api/plan/today").get_json()["nutrition"]["deficit_kcal"] == before - 100
    assert "weight_loss_too_fast" not in _findings(profile)

    assert profile.delete(f"/api/adjustments/{adjustment['id']}").status_code == 204
    assert profile.get("/api/plan/today").get_json()["nutrition"]["deficit_kcal"] == before
    assert "weight_loss_too_fast" in _findings(profile)


def test_dismissed_finding_disappears_without_adjustment(profile):
    key = _findings(profile)["checkin_due"]["key"]
    response = profile.post("/api/review/decisions", json={"key": key, "decision": "dismissed"})
    assert response.status_code == 201
    assert response.get_json()["adjustment"] is None
    assert "checkin_due" not in _findings(profile)
    assert profile.get("/api/adjustments").get_json() == []


def test_decision_validation(profile):
    assert profile.post("/api/review/decisions", json={"key": "nope:1", "decision": "accepted"}).status_code == 404
    key = _findings(profile)["checkin_due"]["key"]
    assert profile.post("/api/review/decisions", json={"key": key, "decision": "maybe"}).status_code == 400


def test_recovery_warning_puts_recovery_week_into_calendar(profile):
    _checkin(profile, 0, 74.0)
    tuesday = _next_weekday(1).isoformat()
    before = profile.get(f"/api/calendar/day/{tuesday}").get_json()
    _signals(profile, sleep=3)
    adjustment = _accept(profile, "recovery_warning").get_json()["adjustment"]
    assert adjustment["kind"] == "deload"
    after = profile.get(f"/api/calendar/day/{tuesday}").get_json()
    assert after["phase"]["deload"] is True
    assert after["cycling"]["minutes"] < before["cycling"]["minutes"]
    assert "Erholungswoche" in after["cycling"]["title"]


def test_back_pain_adds_mcgill_big_3_to_mobility(profile):
    _checkin(profile, 0, 74.0)
    _signals(profile, back=2)
    _accept(profile, "back_pain")
    day = profile.get(f"/api/calendar/day/{TODAY.isoformat()}").get_json()
    assert "core_daily" in day["adjustments"]
    assert any(e["name"] == "McGill Curl-Up" for e in day["mobility"])


def test_flat_legs_reduce_strength_sessions(profile):
    _checkin(profile, 0, 74.0)
    _signals(profile, 7, legs=2)
    _signals(profile, 0, legs=3)
    _accept(profile, "legs_flat")
    thursday = _next_weekday(3).isoformat()
    strength = profile.get(f"/api/calendar/day/{thursday}").get_json()["strength"]
    assert "Volumen" in strength["note"]
    assert all(e["name"] != "Lateral Band Walks" for e in strength["exercises"])


def test_low_energy_availability_from_intake_and_calendar(profile):
    _checkin(profile, 0, 74.0)
    for days_ago in (1, 2, 3):
        day = (TODAY - timedelta(days=days_ago)).isoformat()
        profile.put(f"/api/intake/{day}", json={"kcal": 1000, "protein_g": 80, "carbs_g": 100, "fat_g": 30})
    finding = _findings(profile)["low_energy_availability"]
    assert finding["severity"] == "alert"
    assert profile.get("/api/review").get_json()["summary"]["energy_availability_avg"] < 30


def test_missing_ramp_test_result_is_reported(client):
    # Programmstart letzte Woche -> Phase-0-Samstag (Ramp-Test) liegt in der Vergangenheit
    start = THIS_MONDAY - timedelta(weeks=1)
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": start.isoformat()})
    week = client.get(f"/api/calendar/week/{start.isoformat()}").get_json()
    assert week["days"][5]["cycling"]["slot"] == "ftp_test"
    assert "ftp_test_missing" in _findings(client)
    client.post("/api/checkins/ftp-tests", json={"best_1min_power_watts": 300, "test_date": (start + timedelta(days=5)).isoformat()})
    assert "ftp_test_missing" not in _findings(client)
