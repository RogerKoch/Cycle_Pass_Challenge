import pytest

from backend.extensions import db
from backend.models.food import Food

DAY = "2026-10-04"


@pytest.fixture()
def foods(app) -> tuple[Food, Food]:
    muesli = Food(name="Müesli", source="blv", source_id="1", search_name="muesli",
                  kcal_100g=380, protein_100g=10, carbs_100g=60, fat_100g=8)
    yogurt = Food(name="Joghurt", source="blv", source_id="2", search_name="joghurt",
                  kcal_100g=60, protein_100g=4, carbs_100g=5, fat_100g=3)
    db.session.add_all([muesli, yogurt])
    db.session.commit()
    return muesli, yogurt


def test_creates_template_from_items(client, foods):
    muesli, yogurt = foods
    body = {"name": "Frühstück", "meal": "fruehstueck",
            "items": [{"food_id": muesli.id, "grams": 60}, {"food_id": yogurt.id, "grams": 180}]}
    response = client.post("/api/meal-templates", json=body)
    assert response.status_code == 201
    assert response.get_json()["kcal"] == 336.0


def test_saves_logged_meal_as_template_skipping_quick_entries(client, foods):
    muesli, _ = foods
    client.post("/api/food-log", json={"date": DAY, "meal": "fruehstueck", "food_id": muesli.id, "grams": 60})
    client.post("/api/food-log", json={"date": DAY, "meal": "fruehstueck", "kcal": 50,
                                       "protein_g": 0, "carbs_g": 0, "fat_g": 0})
    response = client.post("/api/meal-templates", json={"name": "Std", "meal": "fruehstueck", "from_date": DAY})
    assert [i["name"] for i in response.get_json()["items"]] == ["Müesli"]


def test_applying_template_creates_entries_and_intake(client, foods):
    muesli, yogurt = foods
    template_id = client.post("/api/meal-templates", json={
        "name": "Frühstück", "meal": "fruehstueck",
        "items": [{"food_id": muesli.id, "grams": 60}, {"food_id": yogurt.id, "grams": 180}],
    }).get_json()["id"]
    response = client.post(f"/api/meal-templates/{template_id}/apply", json={"date": DAY})
    assert response.get_json()["created"] == 2
    day = client.get(f"/api/food-log/{DAY}").get_json()
    assert len(day["meals"]["fruehstueck"]) == 2
    assert client.get(f"/api/intake/{DAY}").get_json()["kcal"] == 336.0


def test_apply_can_target_other_meal(client, foods):
    muesli, _ = foods
    template_id = client.post("/api/meal-templates", json={
        "name": "M", "meal": "fruehstueck", "items": [{"food_id": muesli.id, "grams": 60}],
    }).get_json()["id"]
    client.post(f"/api/meal-templates/{template_id}/apply", json={"date": DAY, "meal": "snack"})
    assert len(client.get(f"/api/food-log/{DAY}").get_json()["meals"]["snack"]) == 1


def test_deletes_template(client, foods):
    muesli, _ = foods
    template_id = client.post("/api/meal-templates", json={
        "name": "M", "meal": "snack", "items": [{"food_id": muesli.id, "grams": 60}],
    }).get_json()["id"]
    assert client.delete(f"/api/meal-templates/{template_id}").status_code == 204
    assert client.get("/api/meal-templates").get_json() == []


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "meal": "snack", "items": [{"food_id": 1, "grams": 10}]},
        {"name": "X", "meal": "snack", "items": []},
        {"name": "X", "meal": "snack", "items": [{"food_id": 999, "grams": 10}]},
        {"name": "X", "meal": "snack", "from_date": DAY},
    ],
)
def test_rejects_invalid_templates(client, foods, body):
    assert client.post("/api/meal-templates", json=body).status_code == 400
