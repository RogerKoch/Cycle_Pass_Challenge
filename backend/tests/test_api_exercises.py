from datetime import date, timedelta

import pytest

THIS_MONDAY = date.today() - timedelta(days=date.today().weekday())
PROGRAM_START = THIS_MONDAY - timedelta(weeks=2)  # Base, Kraftphase 1
B_DAY = (THIS_MONDAY + timedelta(weeks=1, days=4)).isoformat()  # Einheit B (Freitag = Z2-oder-Rekom bei Ruhetag Dienstag)
ROWS = "Band-Rudern"


@pytest.fixture()
def profile(client):
    client.post("/api/profile", json={
        "age": 49, "height_cm": 173, "program_start_date": PROGRAM_START.isoformat(), "equipment_profile": "bands",
    })
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30})
    return client


def _names(client) -> list[str]:
    return [e["name"] for e in client.get(f"/api/calendar/day/{B_DAY}").get_json()["strength"]["exercises"]]


def test_swap_persists_until_cleared(profile):
    assert ROWS in _names(profile)
    towel = "Handtuch-Rudern an Türklinke"
    assert profile.put("/api/exercises/swap", json={"original": ROWS, "alternative": towel}).status_code == 200
    assert towel in _names(profile) and ROWS not in _names(profile)
    exercise = next(
        e for e in profile.get(f"/api/calendar/day/{B_DAY}").get_json()["strength"]["exercises"]
        if e["name"] == towel
    )
    assert exercise["original"] == ROWS and towel in exercise["alternatives"]
    profile.delete("/api/exercises/swap", json={"original": ROWS})
    assert ROWS in _names(profile)


def test_swap_rejects_unknown_alternative(profile):
    response = profile.put("/api/exercises/swap", json={"original": ROWS, "alternative": "Kreuzheben"})
    assert response.status_code == 400


def test_profile_decides_the_exercises(profile):
    assert "Lateral Band Walks" in _names(profile)
    profile.put("/api/profile", json={"equipment_profile": "bodyweight"})
    names = _names(profile)
    assert "Lateral Band Walks" not in names and "Seitliches Beinheben (Seitenlage)" in names
    profile.put("/api/profile", json={"equipment_profile": "neolymp"})
    assert "Rudern zur Brust mit Bänderstange" in _names(profile)


def test_changing_profile_clears_exercise_swaps(profile):
    profile.put("/api/exercises/swap", json={"original": ROWS, "alternative": "Handtuch-Rudern an Türklinke"})
    profile.put("/api/profile", json={"equipment_profile": "bands"})  # unveraendert: Tausch bleibt
    assert "Handtuch-Rudern an Türklinke" in _names(profile)
    profile.put("/api/profile", json={"equipment_profile": "neolymp"})
    profile.put("/api/profile", json={"equipment_profile": "bands"})
    assert ROWS in _names(profile)


def test_profile_equipment_defaults_validates_and_lists_options(client):
    base = {"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"}
    body = client.post("/api/profile", json=base).get_json()
    assert body["equipment_profile"] == "bodyweight"
    assert {o["id"] for o in body["equipment_options"]} == {"bodyweight", "bands", "neolymp"}
    assert all(o["label"] and o["hint"] for o in body["equipment_options"])
    assert client.put("/api/profile", json={"equipment_profile": "neolymp"}).get_json()["equipment_profile"] == "neolymp"
    assert client.put("/api/profile", json={"equipment_profile": "hantel"}).status_code == 400


def test_set_checks_persist_per_day_and_can_be_undone(client):
    put = lambda index, done=True: client.put(  # noqa: E731
        "/api/exercises/sets", json={"date": B_DAY, "exercise": "Bird Dog", "set_index": index, "done": done}
    )
    assert put(1).get_json() == {"Bird Dog": [1]}
    assert put(0).get_json() == {"Bird Dog": [0, 1]}
    assert put(1).get_json() == {"Bird Dog": [0, 1]}  # idempotent
    assert client.get(f"/api/exercises/sets/{B_DAY}").get_json() == {"Bird Dog": [0, 1]}
    assert client.get(f"/api/exercises/sets/{PROGRAM_START.isoformat()}").get_json() == {}
    assert put(0, done=False).get_json() == {"Bird Dog": [1]}


def test_set_checks_reject_invalid_input(client):
    body = {"date": B_DAY, "exercise": "Bird Dog", "set_index": 0}
    assert client.put("/api/exercises/sets", json={**body, "date": "gestern"}).status_code == 400
    assert client.put("/api/exercises/sets", json={**body, "set_index": -1}).status_code == 400
    assert client.put("/api/exercises/sets", json={**body, "exercise": ""}).status_code == 400
    assert client.get("/api/exercises/sets/nope").status_code == 400
