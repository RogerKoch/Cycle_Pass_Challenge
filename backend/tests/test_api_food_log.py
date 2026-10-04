from datetime import date

import pytest

from backend.extensions import db
from backend.models.food import Food
from backend.models.intake import IntakeDay

DAY = "2026-10-04"
QUICK = {"date": DAY, "meal": "snack", "label": "Gel", "kcal": 100, "protein_g": 0, "carbs_g": 25, "fat_g": 0}


@pytest.fixture()
def egg(app) -> Food:
    food = Food(
        name="Ei", source="blv", source_id="1", search_name="ei",
        kcal_100g=155, protein_100g=12.6, carbs_100g=1.1, fat_100g=10.6,
    )
    db.session.add(food)
    db.session.commit()
    return food


def add_egg(client, egg, grams=60, meal="fruehstueck"):
    return client.post("/api/food-log", json={"date": DAY, "meal": meal, "food_id": egg.id, "grams": grams})


def intake() -> IntakeDay | None:
    return IntakeDay.query.filter_by(intake_date=date.fromisoformat(DAY)).first()


def test_food_entry_stores_scaled_snapshot_and_updates_intake_day(client, egg):
    response = add_egg(client, egg)
    assert response.status_code == 201
    assert response.get_json()["kcal"] == 93.0
    assert intake().kcal == 93.0
    assert egg.use_count == 1


def test_quick_entry_adds_to_intake_day(client, egg):
    add_egg(client, egg)
    response = client.post("/api/food-log", json=QUICK)
    assert response.status_code == 201
    assert response.get_json()["food_id"] is None
    assert intake().kcal == 193.0
    assert intake().carbs_g == 25.7


def test_day_view_groups_by_meal_with_totals(client, egg):
    add_egg(client, egg)
    client.post("/api/food-log", json=QUICK)
    body = client.get(f"/api/food-log/{DAY}").get_json()
    assert [e["label"] for e in body["meals"]["fruehstueck"]] == ["Ei"]
    assert [e["label"] for e in body["meals"]["snack"]] == ["Gel"]
    assert body["meals"]["mittag"] == []
    assert body["totals"]["kcal"] == 193.0


def test_changing_grams_recomputes_entry_and_intake(client, egg):
    entry_id = add_egg(client, egg).get_json()["id"]
    response = client.patch(f"/api/food-log/{entry_id}", json={"grams": 120})
    assert response.get_json()["kcal"] == 186.0
    assert intake().kcal == 186.0


def test_snapshot_stays_stable_when_food_changes(client, egg):
    add_egg(client, egg)
    egg.kcal_100g = 999
    db.session.commit()
    assert client.get(f"/api/food-log/{DAY}").get_json()["totals"]["kcal"] == 93.0


def test_deleting_last_entry_removes_intake_day(client, egg):
    entry_id = add_egg(client, egg).get_json()["id"]
    assert client.delete(f"/api/food-log/{entry_id}").status_code == 204
    assert intake() is None


def test_log_overrides_imported_intake_day(client, egg):
    client.put(f"/api/intake/{DAY}", json={"kcal": 2000, "protein_g": 100, "carbs_g": 200, "fat_g": 50})
    add_egg(client, egg)
    assert intake().kcal == 93.0


def test_quick_entry_grams_cannot_be_changed(client):
    entry_id = client.post("/api/food-log", json=QUICK).get_json()["id"]
    assert client.patch(f"/api/food-log/{entry_id}", json={"grams": 50}).status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {"date": DAY, "meal": "zvieri", "kcal": 1, "protein_g": 0, "carbs_g": 0, "fat_g": 0},
        {"date": "kein-datum", "meal": "snack", "kcal": 1, "protein_g": 0, "carbs_g": 0, "fat_g": 0},
        {"date": DAY, "meal": "snack", "kcal": -1, "protein_g": 0, "carbs_g": 0, "fat_g": 0},
        {"date": DAY, "meal": "snack", "kcal": 1},
    ],
)
def test_rejects_invalid_entries(client, body):
    assert client.post("/api/food-log", json=body).status_code == 400


def test_rejects_zero_grams(client, egg):
    assert add_egg(client, egg, grams=0).status_code == 400


def test_unknown_food_returns_404(client):
    response = client.post("/api/food-log", json={"date": DAY, "meal": "snack", "food_id": 999, "grams": 10})
    assert response.status_code == 404
