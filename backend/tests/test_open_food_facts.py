import pytest

from backend.integrations import open_food_facts
from backend.integrations.open_food_facts import OffUnavailableError, lookup_product


class _Response:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def _patch(monkeypatch, body):
    monkeypatch.setattr(open_food_facts.requests, "get", lambda *a, **k: _Response(body))


def test_non_object_response_is_reported_as_unavailable(monkeypatch):
    _patch(monkeypatch, [1, 2])
    with pytest.raises(OffUnavailableError):
        lookup_product("7612345678900")


def test_non_finite_and_boolean_nutrients_are_treated_as_unknown(monkeypatch):
    nutriments = {"energy-kcal_100g": "nan", "proteins_100g": True, "carbohydrates_100g": "inf", "fat_100g": 3.5}
    _patch(monkeypatch, {"status": 1, "product": {"product_name": "Test", "nutriments": nutriments}})
    product = lookup_product("7612345678900")
    assert (product.kcal_100g, product.protein_100g, product.carbs_100g, product.fat_100g) == (None, None, None, 3.5)
    assert not product.complete
