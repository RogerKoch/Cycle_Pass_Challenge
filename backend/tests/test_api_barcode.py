import pytest

from backend.api import food_routes
from backend.integrations.open_food_facts import OffProduct, OffUnavailableError
from backend.models.food import Food

EAN = "7610200000000"
CUSTOM = {"name": "Riegel", "kcal_100g": 380, "protein_100g": 30, "carbs_100g": 40, "fat_100g": 10}


@pytest.fixture()
def off(monkeypatch):
    """Ersetzt den OFF-Lookup; `off.result` steuert die Antwort, `off.calls` zaehlt Aufrufe."""

    class FakeOff:
        result: OffProduct | None | Exception = None
        calls = 0

        def __call__(self, ean: str) -> OffProduct | None:
            self.calls += 1
            if isinstance(self.result, Exception):
                raise self.result
            return self.result

    fake = FakeOff()
    monkeypatch.setattr(food_routes, "lookup_product", fake)
    return fake


def test_off_hit_is_stored_and_reused_without_second_request(client, off):
    off.result = OffProduct("Ovomaltine (Wander)", 380, 8, 80, 2)
    response = client.get(f"/api/foods/barcode/{EAN}")
    assert response.status_code == 201
    assert response.get_json()["source"] == "off"
    assert client.get(f"/api/foods/barcode/{EAN}").status_code == 200
    assert off.calls == 1
    assert Food.query.count() == 1


def test_custom_food_with_barcode_is_found_locally(client, off):
    client.post("/api/foods", json={**CUSTOM, "barcode": EAN})
    response = client.get(f"/api/foods/barcode/{EAN}")
    assert response.get_json()["name"] == "Riegel"
    assert off.calls == 0


def test_incomplete_off_product_returns_404_with_name(client, off):
    off.result = OffProduct("Unbekannter Riegel", None, 5, None, 3)
    response = client.get(f"/api/foods/barcode/{EAN}")
    assert response.status_code == 404
    assert response.get_json()["name"] == "Unbekannter Riegel"
    assert Food.query.count() == 0


def test_unknown_barcode_returns_404(client, off):
    assert client.get(f"/api/foods/barcode/{EAN}").status_code == 404


def test_off_unavailable_returns_502(client, off):
    off.result = OffUnavailableError("timeout")
    assert client.get(f"/api/foods/barcode/{EAN}").status_code == 502


def test_rejects_non_numeric_barcode(client, off):
    assert client.get("/api/foods/barcode/abc123").status_code == 400


def test_rejects_duplicate_custom_barcode(client):
    client.post("/api/foods", json={**CUSTOM, "barcode": EAN})
    assert client.post("/api/foods", json={**CUSTOM, "barcode": EAN}).status_code == 409
