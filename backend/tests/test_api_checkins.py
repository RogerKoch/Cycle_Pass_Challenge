import pytest


def test_submits_checkin_returns_201_with_computed_ffm(client):
    response = client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30})
    assert response.status_code == 201
    body = response.get_json()
    assert body["ffm_kg"] == pytest.approx(74 * 0.77)


def test_rejects_checkin_with_negative_weight(client):
    response = client.post("/api/checkins", json={"weight_kg": -5, "bodyfat_pct": 23, "muscle_kg": 30})
    assert response.status_code == 400


def test_rejects_checkin_with_out_of_range_bodyfat(client):
    response = client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 150, "muscle_kg": 30})
    assert response.status_code == 400


def test_lists_checkins_newest_first(client):
    client.post("/api/checkins", json={"weight_kg": 75, "bodyfat_pct": 24, "muscle_kg": 30, "checkin_date": "2026-10-01"})
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30, "checkin_date": "2026-10-08"})
    response = client.get("/api/checkins")
    body = response.get_json()
    assert body[0]["checkin_date"] == "2026-10-08"


def test_latest_checkin_returns_404_when_none_exist(client):
    response = client.get("/api/checkins/latest")
    assert response.status_code == 404


def test_submits_ftp_test_computes_ftp_watts_server_side(client):
    response = client.post("/api/checkins/ftp-tests", json={"best_1min_power_watts": 300})
    assert response.status_code == 201
    assert response.get_json()["ftp_watts"] == 225


def test_ftp_test_applies_manual_correction(client):
    response = client.post(
        "/api/checkins/ftp-tests", json={"best_1min_power_watts": 300, "manual_correction_pct": -5}
    )
    assert response.status_code == 201
    assert response.get_json()["ftp_watts"] == 214  # round(225 * 0.95)


def test_latest_ftp_test_returns_404_when_none_exist(client):
    response = client.get("/api/checkins/ftp-tests/latest")
    assert response.status_code == 404
