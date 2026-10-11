from datetime import date, timedelta

import pytest

THIS_MONDAY = date.today() - timedelta(days=date.today().weekday())
PROGRAM_START = THIS_MONDAY - timedelta(weeks=2)  # Base, Kraftphase 1
THURSDAY = (THIS_MONDAY + timedelta(weeks=1, days=3)).isoformat()  # Einheit B
ROWS = "Inverted Rows (Tischkanten-Rudern)"


@pytest.fixture()
def profile(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": PROGRAM_START.isoformat()})
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30})
    return client


def _names(client) -> list[str]:
    return [e["name"] for e in client.get(f"/api/calendar/day/{THURSDAY}").get_json()["strength"]["exercises"]]


def test_swap_persists_until_cleared(profile):
    assert ROWS in _names(profile)
    assert profile.put("/api/exercises/swap", json={"original": ROWS, "alternative": "Band-Rudern"}).status_code == 200
    assert "Band-Rudern" in _names(profile) and ROWS not in _names(profile)
    exercise = next(
        e for e in profile.get(f"/api/calendar/day/{THURSDAY}").get_json()["strength"]["exercises"]
        if e["name"] == "Band-Rudern"
    )
    assert exercise["original"] == ROWS and "Handtuch-Rudern an Türklinke" in exercise["alternatives"]
    profile.delete("/api/exercises/swap", json={"original": ROWS})
    assert ROWS in _names(profile)


def test_swap_rejects_unknown_alternative(profile):
    response = profile.put("/api/exercises/swap", json={"original": ROWS, "alternative": "Kreuzheben"})
    assert response.status_code == 400


def test_missing_bands_in_profile_swap_band_exercises_automatically(profile):
    assert "Lateral Band Walks" in _names(profile)
    profile.put("/api/profile", json={"equipment_missing": ["bands"]})
    names = _names(profile)
    assert "Lateral Band Walks" not in names and "Seitliches Beinheben (Seitenlage)" in names


def test_manual_swap_overrides_missing_equipment(profile):
    profile.put("/api/profile", json={"equipment_missing": ["table"]})
    assert "Band-Rudern" in _names(profile)
    profile.put("/api/exercises/swap", json={"original": ROWS, "alternative": "Rucksack-Rudern vorgebeugt"})
    assert "Rucksack-Rudern vorgebeugt" in _names(profile)


def test_profile_equipment_defaults_validates_and_lists_options(client):
    base = {"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"}
    body = client.post("/api/profile", json=base).get_json()
    assert body["equipment_missing"] == []
    assert {"id": "bands", "label": "Keine Widerstandsbänder"} in body["equipment_options"]
    assert client.put("/api/profile", json={"equipment_missing": ["table", "bands"]}).get_json()[
        "equipment_missing"
    ] == ["bands", "table"]
    assert client.put("/api/profile", json={"equipment_missing": ["hantel"]}).status_code == 400
