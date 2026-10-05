from datetime import date, timedelta

import pytest

from backend.extensions import db
from backend.models.training_days import TrainingDay

THIS_MONDAY = date.today() - timedelta(days=date.today().weekday())
PROGRAM_START = THIS_MONDAY - timedelta(weeks=2)  # diese Woche = Base Woche 1
NEXT_MONDAY = THIS_MONDAY + timedelta(weeks=1)


def _day(offset: int) -> str:
    """Tag der naechsten Woche (0 = Montag), liegt immer in der Zukunft."""
    return (NEXT_MONDAY + timedelta(days=offset)).isoformat()


@pytest.fixture()
def profile(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": PROGRAM_START.isoformat()})
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30})
    return client


def _slots(week):
    return [(d["cycling"]["slot"] if d["cycling"] else None, d["strength"]["session_id"] if d["strength"] else None) for d in week["days"]]


def test_week_requires_profile(client):
    assert client.get(f"/api/calendar/week/{_day(0)}").status_code == 404


def test_week_is_generated_lazily_and_idempotent(profile, app):
    first = profile.get(f"/api/calendar/week/{_day(3)}").get_json()
    second = profile.get(f"/api/calendar/week/{_day(0)}").get_json()
    assert first == second
    assert first["week_start"] == _day(0)
    assert _slots(first) == [
        ("rekom", "A"), ("schluessel_1", None), ("z2_grundlage", None), ("z2_oder_rekom", "B"),
        (None, None), ("schluessel_2", None), ("lang", None),
    ]
    assert TrainingDay.query.count() == 7


def test_week_rejects_invalid_date(profile):
    assert profile.get("/api/calendar/week/2026-13-01").status_code == 400


def test_day_contains_watts_strength_mobility_and_options(profile):
    profile.post("/api/checkins/ftp-tests", json={"best_1min_power_watts": 300})  # FTP 225
    tuesday = profile.get(f"/api/calendar/day/{_day(1)}").get_json()
    assert tuesday["phase"] == {"phase_id": "base", "week_in_phase": 2, "deload": False}
    interval = next(s for s in tuesday["cycling"]["segments"] if s["label"].startswith("Sweet Spot"))
    assert interval["watts_low"] == 198
    assert tuesday["mobility"]
    assert {o["slot"] for o in tuesday["slot_options"]} >= {"schluessel_1", "lang"}
    monday = profile.get(f"/api/calendar/day/{_day(0)}").get_json()
    assert monday["strength"]["session_id"] == "A"
    assert monday["strength"]["phase"]["number"] == 1


def test_day_without_ftp_has_percent_only(profile):
    tuesday = profile.get(f"/api/calendar/day/{_day(1)}").get_json()
    assert tuesday["cycling"]["message"]
    assert all(s["watts_low"] is None for s in tuesday["cycling"]["segments"])


def test_swap_moves_plan_between_days(profile):
    response = profile.post("/api/calendar/swap", json={"date_a": _day(2), "date_b": _day(3)})
    assert response.status_code == 200
    slots = _slots(response.get_json())
    assert slots[2] == ("z2_oder_rekom", "B")
    assert slots[3] == ("z2_grundlage", None)


def test_swap_creating_consecutive_key_sessions_is_rejected(profile):
    response = profile.post("/api/calendar/swap", json={"date_a": _day(2), "date_b": _day(5)})
    assert response.status_code == 409
    assert response.get_json()["violations"]
    assert _slots(profile.get(f"/api/calendar/week/{_day(0)}").get_json())[2] == ("z2_grundlage", None)


def test_swap_across_weeks_or_in_the_past_is_rejected(profile):
    assert profile.post("/api/calendar/swap", json={"date_a": _day(6), "date_b": _day(7)}).status_code == 400
    last_week = THIS_MONDAY - timedelta(weeks=1)
    past = {"date_a": last_week.isoformat(), "date_b": (last_week + timedelta(days=1)).isoformat()}
    assert profile.post("/api/calendar/swap", json=past).status_code == 400


def test_swap_of_completed_day_is_rejected(profile, app):
    profile.get(f"/api/calendar/week/{_day(0)}")
    row = TrainingDay.query.filter_by(day_date=date.fromisoformat(_day(2))).one()
    row.status = "done"
    db.session.commit()
    assert profile.post("/api/calendar/swap", json={"date_a": _day(2), "date_b": _day(3)}).status_code == 409


def test_future_day_can_be_cancelled_with_reason_and_reverted(profile):
    response = profile.patch(f"/api/calendar/day/{_day(2)}", json={"status": "skipped", "note": "privat"})
    assert response.status_code == 200
    assert (response.get_json()["status"], response.get_json()["note"]) == ("skipped", "privat")
    reverted = profile.patch(f"/api/calendar/day/{_day(2)}", json={"status": "planned"}).get_json()
    assert (reverted["status"], reverted["note"]) == ("planned", None)


def test_future_day_cannot_be_marked_done(profile):
    assert profile.patch(f"/api/calendar/day/{_day(2)}", json={"status": "done"}).status_code == 400


def test_modified_requires_actual_minutes_and_valid_intensity(profile):
    today = date.today().isoformat()
    assert profile.patch(f"/api/calendar/day/{today}", json={"status": "modified"}).status_code == 400
    bad = {"status": "modified", "actual_minutes": 60, "actual_intensity": "nonsense"}
    assert profile.patch(f"/api/calendar/day/{today}", json=bad).status_code == 400
    ok = {"status": "modified", "actual_minutes": 60, "actual_intensity": "moderat_base", "actual_strength_done": False}
    body = profile.patch(f"/api/calendar/day/{today}", json=ok).get_json()
    assert body["actual"] == {"minutes": 60, "intensity": "moderat_base", "strength_done": False}


def test_invalid_status_is_rejected(profile):
    assert profile.patch(f"/api/calendar/day/{_day(2)}", json={"status": "nonsense"}).status_code == 400


def test_cancelled_key_session_offers_reschedule_days(profile):
    body = profile.patch(f"/api/calendar/day/{_day(1)}", json={"status": "skipped"}).get_json()
    assert _day(2) in body["reschedule_options"]
    assert _day(4) not in body["reschedule_options"]  # Fr direkt vor dem Sa-Schluessel
    moved = profile.post("/api/calendar/swap", json={"date_a": _day(1), "date_b": _day(2)})
    assert moved.status_code == 200
    days = moved.get_json()["days"]
    assert (days[1]["status"], days[2]["cycling"]["slot"]) == ("skipped", "schluessel_1")


def test_plan_can_switch_unit_and_adjust_endurance_duration(profile):
    response = profile.put(f"/api/calendar/day/{_day(2)}/plan", json={"cycling_slot": "lang", "planned_minutes": 90})
    assert response.status_code == 200
    cycling = response.get_json()["cycling"]
    assert (cycling["slot"], cycling["minutes"], cycling["adjusted"]) == ("lang", 90, True)


def test_plan_rejects_duration_for_key_session(profile):
    response = profile.put(f"/api/calendar/day/{_day(1)}/plan", json={"planned_minutes": 30})
    assert response.status_code == 400


def test_plan_rejects_unknown_unit(profile):
    assert profile.put(f"/api/calendar/day/{_day(1)}/plan", json={"cycling_slot": "nonsense"}).status_code == 400


def test_plan_rejects_rule_violations(profile):
    consecutive = profile.put(f"/api/calendar/day/{_day(2)}/plan", json={"cycling_slot": "schluessel_1"})
    assert consecutive.status_code == 409
    no_rest_day = profile.put(f"/api/calendar/day/{_day(4)}/plan", json={"strength_session": "A"})
    assert no_rest_day.status_code == 409


def test_plan_can_drop_strength_and_ride(profile):
    body = profile.put(f"/api/calendar/day/{_day(0)}/plan", json={"cycling_slot": None, "strength_session": None}).get_json()
    assert (body["cycling"], body["strength"]) == (None, None)


def test_plan_of_cancelled_day_is_rejected(profile):
    profile.patch(f"/api/calendar/day/{_day(2)}", json={"status": "skipped"})
    assert profile.put(f"/api/calendar/day/{_day(2)}/plan", json={"cycling_slot": "lang"}).status_code == 409


def test_reset_restores_standard_week(profile):
    profile.put(f"/api/calendar/day/{_day(2)}/plan", json={"cycling_slot": "lang", "planned_minutes": 90})
    profile.patch(f"/api/calendar/day/{_day(3)}", json={"status": "skipped", "note": "privat"})
    week = profile.post(f"/api/calendar/week/{_day(0)}/reset").get_json()
    assert _slots(week)[2] == ("z2_grundlage", None)
    assert week["days"][2]["cycling"]["minutes"] == 60
    assert (week["days"][3]["status"], week["days"][3]["note"]) == ("planned", None)


def test_days_before_program_start_are_empty(profile):
    before = (PROGRAM_START - timedelta(days=1)).isoformat()
    body = profile.get(f"/api/calendar/day/{before}").get_json()
    assert (body["started"], body["cycling"], body["strength"], body["slot_options"]) == (False, None, None, [])
