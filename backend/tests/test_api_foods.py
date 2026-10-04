import pytest

from backend.engine.food_calc import normalize_search
from backend.extensions import db
from backend.models.food import Food

CUSTOM = {"name": "Proteinriegel", "kcal_100g": 380, "protein_100g": 30, "carbs_100g": 40, "fat_100g": 10}


def add_blv(name: str, use_count: int = 0) -> Food:
    food = Food(
        name=name, source="blv", source_id=name, search_name=normalize_search(name), use_count=use_count,
        kcal_100g=100, protein_100g=1, carbs_100g=1, fat_100g=1,
    )
    db.session.add(food)
    db.session.commit()
    return food


def names(response) -> list[str]:
    return [f["name"] for f in response.get_json()]


def test_search_ranks_prefix_before_word_before_substring(client):
    for name in ("Hühnerbrühe", "Brühwürfel", "Gemüse Brühe"):
        add_blv(name)
    assert names(client.get("/api/foods?q=brüh")) == ["Brühwürfel", "Gemüse Brühe", "Hühnerbrühe"]


def test_search_ignores_umlauts_and_requires_all_words(client):
    add_blv("Äpfel, roh")
    add_blv("Äpfel, gedörrt")
    assert names(client.get("/api/foods?q=apfel roh")) == ["Äpfel, roh"]


def test_search_prefers_frequently_used_within_same_rank(client):
    add_blv("Milch, Vollmilch")
    add_blv("Milch, Magermilch", use_count=5)
    assert names(client.get("/api/foods?q=milch"))[0] == "Milch, Magermilch"


def test_search_without_query_returns_recently_used_foods(client):
    old, new = add_blv("Banane"), add_blv("Brot")
    add_blv("Unbenutzt")
    for food in (old, new):
        client.post("/api/food-log", json={"date": "2026-10-04", "meal": "snack", "food_id": food.id, "grams": 50})
    assert names(client.get("/api/foods")) == ["Brot", "Banane"]


def test_creates_custom_food_with_portion(client):
    response = client.post("/api/foods", json={**CUSTOM, "portion_label": "Riegel", "portion_g": 45})
    assert response.status_code == 201
    assert response.get_json()["source"] == "custom"
    assert names(client.get("/api/foods?q=protein")) == ["Proteinriegel"]


@pytest.mark.parametrize(
    "override",
    [{"name": ""}, {"kcal_100g": -1}, {"portion_label": "Riegel"}, {"portion_label": "Riegel", "portion_g": 0}],
)
def test_rejects_invalid_custom_food(client, override):
    assert client.post("/api/foods", json={**CUSTOM, **override}).status_code == 400


def test_sets_and_clears_portion_on_blv_food(client):
    food = add_blv("Ei, Huhn")
    response = client.patch(f"/api/foods/{food.id}", json={"portion_label": "Ei", "portion_g": 60})
    assert response.get_json()["portion_g"] == 60
    response = client.patch(f"/api/foods/{food.id}", json={"portion_label": None, "portion_g": None})
    assert response.get_json()["portion_label"] is None


def test_blv_nutrients_cannot_be_changed(client):
    food = add_blv("Ei, Huhn")
    assert client.patch(f"/api/foods/{food.id}", json={"kcal_100g": 1}).status_code == 400


def test_custom_food_nutrients_can_be_changed(client):
    food_id = client.post("/api/foods", json=CUSTOM).get_json()["id"]
    response = client.patch(f"/api/foods/{food_id}", json={"kcal_100g": 400, "name": "Riegel neu"})
    assert response.get_json()["kcal_100g"] == 400
    assert names(client.get("/api/foods?q=neu")) == ["Riegel neu"]


def test_patch_unknown_food_returns_404(client):
    assert client.patch("/api/foods/999", json={}).status_code == 404


def test_search_ranks_whole_word_match_before_longer_prefix(client):
    for name in ("Eierschwamm, roh", "Eisbergsalat", "Ei, Huhn, ganz, roh"):
        add_blv(name)
    assert names(client.get("/api/foods?q=ei"))[0] == "Ei, Huhn, ganz, roh"


def test_get_food_by_id(client):
    food = add_blv("Banane")
    assert client.get(f"/api/foods/{food.id}").get_json()["name"] == "Banane"
    assert client.get("/api/foods/999").status_code == 404
