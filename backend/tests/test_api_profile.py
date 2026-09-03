def test_creates_profile_returns_201(client):
    response = client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    assert response.status_code == 201
    assert response.get_json()["age"] == 49


def test_get_profile_returns_404_when_none_exists(client):
    response = client.get("/api/profile")
    assert response.status_code == 404


def test_creating_second_profile_returns_409(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    response = client.post("/api/profile", json={"age": 50, "height_cm": 173, "program_start_date": "2026-10-01"})
    assert response.status_code == 409


def test_updates_existing_profile_via_put(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    response = client.put("/api/profile", json={"age": 50})
    assert response.status_code == 200
    assert response.get_json()["age"] == 50


def test_put_returns_404_when_no_profile_exists(client):
    response = client.put("/api/profile", json={"age": 50})
    assert response.status_code == 404


def test_create_profile_rejects_missing_fields(client):
    response = client.post("/api/profile", json={"age": 49})
    assert response.status_code == 400
