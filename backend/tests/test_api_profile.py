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


def test_profile_defaults_to_office_activity_level(client):
    response = client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    body = response.get_json()
    assert body["activity_level"] == "buero"
    assert {"id": "schwer", "label": "körperlich schwer", "factor": 2.1} in body["activity_levels"]


def test_updates_activity_level_via_put(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    response = client.put("/api/profile", json={"activity_level": "stehend"})
    assert response.status_code == 200
    assert response.get_json()["activity_level"] == "stehend"


def test_rejects_unknown_activity_level(client):
    base = {"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"}
    assert client.post("/api/profile", json={**base, "activity_level": "astronaut"}).status_code == 400
    client.post("/api/profile", json=base)
    assert client.put("/api/profile", json={"activity_level": "astronaut"}).status_code == 400


def test_strength_focus_defaults_to_none_and_lists_options(client):
    body = client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"}).get_json()
    assert body["strength_focus"] == "none"
    assert {"id": "core", "label": "Bauch/Core"} in body["focus_options"]


def test_updates_and_validates_strength_focus(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    assert client.put("/api/profile", json={"strength_focus": "legs"}).get_json()["strength_focus"] == "legs"
    assert client.put("/api/profile", json={"strength_focus": "arme"}).status_code == 400
