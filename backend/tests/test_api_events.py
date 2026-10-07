from datetime import date, timedelta

import pytest

TODAY = date.today()
THIS_MONDAY = TODAY - timedelta(days=TODAY.weekday())
NEXT_MONDAY = THIS_MONDAY + timedelta(weeks=1)
EVENT = {"event_date": (NEXT_MONDAY + timedelta(days=5)).isoformat(), "name": "Gran Fondo", "priority": "A",
         "expected_minutes": 240, "kind": "rennen"}


@pytest.fixture()
def profile(client):
    client.post(
        "/api/profile",
        json={"age": 49, "height_cm": 173, "program_start_date": (THIS_MONDAY - timedelta(weeks=2)).isoformat()},
    )
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30})
    return client


def _day(client, day: date) -> dict:
    return client.get(f"/api/calendar/day/{day.isoformat()}").get_json()


def _event_day(offset: int) -> date:
    return date.fromisoformat(EVENT["event_date"]) + timedelta(days=offset)


# --- CRUD ----------------------------------------------------------------


def test_event_crud_roundtrip(client):
    created = client.post("/api/events", json=EVENT)
    assert created.status_code == 201
    event_id = created.get_json()["id"]
    assert [e["name"] for e in client.get("/api/events").get_json()] == ["Gran Fondo"]
    updated = client.put(f"/api/events/{event_id}", json={"priority": "B"})
    assert updated.get_json()["priority"] == "B" and updated.get_json()["name"] == "Gran Fondo"
    assert client.delete(f"/api/events/{event_id}").status_code == 204
    assert client.get("/api/events").get_json() == []


def test_events_are_listed_by_date_and_past_events_are_hidden_by_default(client):
    client.post("/api/events", json={**EVENT, "name": "Spaeter", "event_date": (TODAY + timedelta(days=60)).isoformat()})
    client.post("/api/events", json={**EVENT, "name": "Frueher", "event_date": (TODAY + timedelta(days=20)).isoformat()})
    client.post("/api/events", json={**EVENT, "name": "Vorbei", "event_date": (TODAY - timedelta(days=5)).isoformat()})
    assert [e["name"] for e in client.get("/api/events").get_json()] == ["Frueher", "Spaeter"]
    assert len(client.get(f"/api/events?from={(TODAY - timedelta(days=30)).isoformat()}").get_json()) == 3


@pytest.mark.parametrize(
    "change",
    [
        {"event_date": "morgen"},
        {"name": " "},
        {"priority": "D"},
        {"kind": "marathon"},
        {"expected_minutes": 0},
        {"expected_minutes": -5},
        {"expected_minutes": 10_000},
        {"expected_minutes": True},
        {"note": "x" * 201},
    ],
)
def test_invalid_events_are_rejected(client, change):
    assert client.post("/api/events", json={**EVENT, **change}).status_code == 400


def test_unknown_event_returns_404(client):
    assert client.put("/api/events/99", json={"name": "x"}).status_code == 404
    assert client.delete("/api/events/99").status_code == 404
    assert client.get("/api/events/99/prep").status_code == 404


def test_prep_lists_countdown_with_carbs_and_deficit(client):
    client.post("/api/checkins", json={"weight_kg": 70, "bodyfat_pct": 23, "muscle_kg": 30})
    event_id = client.post("/api/events", json=EVENT).get_json()["id"]
    prep = client.get(f"/api/events/{event_id}/prep").get_json()
    by_label = {d["label"]: d for d in prep["days"]}
    assert list(by_label)[0] == "T-14" and list(by_label)[-1] == "R+2"
    assert by_label["T-1"]["carbs_g"] == 700 and by_label["T-1"]["carbs_g_per_kg"] == 10.0
    assert by_label["T-14"]["volume_pct"] == 80 and by_label["T-14"]["deficit_factor"] == 0.5
    assert by_label["Event"]["deficit_factor"] == 0.0
    assert by_label["R+1"]["strength_blocked"] is True


# --- Kalender --------------------------------------------------------------


def test_calendar_applies_taper_opener_event_and_recovery(profile):
    profile.post("/api/events", json=EVENT)
    outside = _day(profile, _event_day(-15))  # ausserhalb des Fensters
    assert outside["event"] is None

    in_taper = _day(profile, _event_day(-5))
    assert in_taper["event"]["label"] == "T-5" and in_taper["event"]["phase"] == "taper"

    opener = _day(profile, _event_day(-1))
    assert opener["cycling"]["slot"] == "opener" and opener["strength"] is None

    event = _day(profile, _event_day(0))
    assert event["cycling"]["slot"] == "event" and event["cycling"]["minutes"] == 240
    assert event["event"]["name"] == "Gran Fondo"

    recovery = _day(profile, _event_day(1))
    assert recovery["event"]["phase"] == "recovery"
    assert recovery["strength"] is None
    if recovery["cycling"]:
        assert recovery["cycling"]["intensity"] == "leicht_rekom"


def test_taper_shortens_planned_ride_but_keeps_intensity(profile):
    # Event in 6 Tagen vom Samstag der naechsten Woche -> Dienstag (schluessel_1) ist T-4
    before = _day(profile, NEXT_MONDAY + timedelta(days=1))["cycling"]
    profile.post("/api/events", json=EVENT)
    after = _day(profile, NEXT_MONDAY + timedelta(days=1))["cycling"]
    assert after["minutes"] < before["minutes"]
    assert after["intensity"] == before["intensity"]
    assert "Taper" in after["title"]


def test_deleting_event_restores_plan(profile):
    before = _day(profile, NEXT_MONDAY + timedelta(days=1))["cycling"]
    event_id = profile.post("/api/events", json=EVENT).get_json()["id"]
    profile.delete(f"/api/events/{event_id}")
    assert _day(profile, NEXT_MONDAY + timedelta(days=1))["cycling"] == before


def test_event_day_has_no_zwift_download(profile):
    profile.post("/api/events", json=EVENT)
    assert profile.get(f"/api/calendar/day/{EVENT['event_date']}/zwo").status_code == 404


def test_event_before_program_start_does_not_break_week(profile):
    start = THIS_MONDAY - timedelta(weeks=2)
    profile.post("/api/events", json={**EVENT, "event_date": (start - timedelta(days=5)).isoformat()})
    assert profile.get(f"/api/calendar/week/{start.isoformat()}").status_code == 200


# --- Tagesplan (Ernaehrung) ---------------------------------------------------


def _today_plan(client) -> dict:
    return client.get("/api/plan/today").get_json()


def _event_in(client, days: int, **overrides) -> None:
    client.post("/api/events", json={**EVENT, "event_date": (TODAY + timedelta(days=days)).isoformat(), **overrides})


def test_load_day_raises_carbs_and_kcal_and_removes_deficit(profile):
    baseline = _today_plan(profile)
    _event_in(profile, 1)  # morgen Event -> heute T-1
    plan = _today_plan(profile)
    assert plan["event"]["label"] == "T-1"
    assert plan["macros"]["carbs_g"] == pytest.approx(74 * 10)
    assert plan["macros"]["fat_g"] == pytest.approx(74 * 0.8)
    assert plan["nutrition"]["deficit_kcal"] == 0
    assert plan["nutrition"]["target_kcal"] >= (plan["macros"]["protein_g"] + plan["macros"]["carbs_g"]) * 4
    assert plan["nutrition"]["target_kcal"] > baseline["nutrition"]["target_kcal"]
    assert any("Carb-Loading" in hint for hint in plan["timing_hints"])
    assert sum(m["kcal"] for m in plan["meals"]) == pytest.approx(plan["nutrition"]["target_kcal"])


def test_event_day_plan_uses_hard_day_and_fueling(profile):
    _event_in(profile, 0, expected_minutes=300)
    plan = _today_plan(profile)
    assert plan["event"]["phase"] == "event"
    assert plan["day_type"] == "langer_harter_tag"
    assert plan["fueling"]["carbs_g_per_hour_max"] == 90
    assert plan["nutrition"]["deficit_kcal"] == 0
    assert any("60–90 g KH/h" in hint for hint in plan["timing_hints"])


def test_taper_phase_halves_deficit_for_priority_a(profile):
    baseline = _today_plan(profile)["nutrition"]["deficit_kcal"]
    assert baseline == 350  # Base-Phase
    _event_in(profile, 10)
    assert _today_plan(profile)["nutrition"]["deficit_kcal"] == pytest.approx(175)


def test_plan_without_event_has_no_event_block(profile):
    assert _today_plan(profile)["event"] is None


# --- Review -------------------------------------------------------------------


def _checkin(client, days_ago: int, weight: float) -> None:
    client.post(
        "/api/checkins",
        json={"weight_kg": weight, "bodyfat_pct": 23, "muscle_kg": 30, "checkin_date": (TODAY - timedelta(days=days_ago)).isoformat()},
    )


def test_event_window_weights_do_not_trigger_weight_loss_finding(profile):
    _checkin(profile, 14, 74.0)
    _checkin(profile, 7, 73.9)
    _checkin(profile, 0, 72.0)  # starker Abfall nach dem Event (Wasser)
    triggers = {f["trigger_id"] for f in profile.get("/api/review").get_json()["findings"]}
    assert "weight_loss_too_fast" in triggers
    profile.post("/api/events", json={**EVENT, "event_date": (TODAY - timedelta(days=1)).isoformat()})
    triggers = {f["trigger_id"] for f in profile.get("/api/review").get_json()["findings"]}
    assert "weight_loss_too_fast" not in triggers
