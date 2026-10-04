import pytest


def _setup(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30})


def test_baseline_without_measurements_is_all_estimated(client):
    _setup(client)
    body = client.get("/api/baseline").get_json()
    assert body["fields"]["rmr_kcal"]["source"] == "estimated"
    assert body["fields"]["rmr_kcal"]["value"] == pytest.approx(1581.25)
    assert body["fields"]["ffm_kg"]["value"] == pytest.approx(74 * 0.77)
    assert body["fields"]["target_bodyfat_pct"]["value"] == 16.0


def test_baseline_fields_without_estimate_have_no_value(client):
    _setup(client)
    field = client.get("/api/baseline").get_json()["fields"]["vt1_hr"]
    assert field["value"] is None
    assert field["source"] is None


def test_measured_value_replaces_estimate_and_updates_derived_values(client):
    _setup(client)
    before = client.get("/api/baseline").get_json()["derived"]["rmr_ratio"]
    response = client.put("/api/baseline/rmr_kcal", json={"value": 1800})
    assert response.status_code == 200
    after = client.get("/api/baseline").get_json()
    assert after["fields"]["rmr_kcal"]["source"] == "measured"
    assert after["fields"]["rmr_kcal"]["value"] == 1800
    assert after["derived"]["rmr_ratio"] > before


def test_rejects_unknown_field(client):
    response = client.put("/api/baseline/nonsense", json={"value": 1})
    assert response.status_code == 400


def test_rejects_non_positive_measured_value(client):
    response = client.put("/api/baseline/rmr_kcal", json={"value": -5})
    assert response.status_code == 400


def test_rejects_percentage_of_100_or_more(client):
    response = client.put("/api/baseline/bodyfat_pct", json={"value": 100})
    assert response.status_code == 400


def test_baseline_returns_404_without_profile(client):
    assert client.get("/api/baseline").status_code == 404


def test_baseline_returns_422_without_checkin(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    assert client.get("/api/baseline").status_code == 422
