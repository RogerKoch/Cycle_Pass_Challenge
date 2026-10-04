from backend.models.intake import IntakeDay

DAY = {"kcal": 2480, "protein_g": 150, "carbs_g": 300, "fat_g": 70}


def test_first_put_creates_intake_with_201(client):
    response = client.put("/api/intake/2026-10-05", json=DAY)
    assert response.status_code == 201
    assert response.get_json()["kcal"] == 2480


def test_repeated_put_is_idempotent_and_overwrites(client, app):
    client.put("/api/intake/2026-10-05", json=DAY)
    response = client.put("/api/intake/2026-10-05", json={**DAY, "kcal": 2600})
    assert response.status_code == 200
    assert IntakeDay.query.count() == 1
    assert client.get("/api/intake/2026-10-05").get_json()["kcal"] == 2600


def test_get_returns_404_for_missing_day(client):
    assert client.get("/api/intake/2026-10-05").status_code == 404


def test_list_filters_by_date_range_newest_first(client):
    for day in ("2026-10-01", "2026-10-05", "2026-10-09"):
        client.put(f"/api/intake/{day}", json=DAY)
    body = client.get("/api/intake?from=2026-10-02&to=2026-10-09").get_json()
    assert [d["intake_date"] for d in body] == ["2026-10-09", "2026-10-05"]


def test_rejects_negative_values(client):
    response = client.put("/api/intake/2026-10-05", json={**DAY, "kcal": -1})
    assert response.status_code == 400


def test_rejects_missing_fields(client):
    response = client.put("/api/intake/2026-10-05", json={"kcal": 2000})
    assert response.status_code == 400


def test_rejects_invalid_date(client):
    response = client.put("/api/intake/not-a-date", json=DAY)
    assert response.status_code == 400
