def test_creates_profile_returns_201(client):
    response = client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    assert response.status_code == 201
    assert response.get_json()["age"] == 49


def test_get_profile_returns_404_when_none_exists(client):
    response = client.get("/api/profile")
    assert response.status_code == 404


def test_profile_404_lists_form_options_so_new_profile_is_fillable(client):
    body = client.get("/api/profile").get_json()
    assert {o["id"] for o in body["activity_levels"]}
    assert {o["id"] for o in body["focus_options"]}
    assert {o["id"] for o in body["equipment_options"]}
    assert len(body["weekday_options"]) == 7


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


def test_profile_defaults_to_male_cyclist_and_validates_both(client):
    response = client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    assert (response.get_json()["sex"], response.get_json()["sport"]) == ("m", "cycling")
    assert client.put("/api/profile", json={"sex": "x"}).status_code == 400
    assert client.put("/api/profile", json={"sport": "swimming"}).status_code == 400
    updated = client.put("/api/profile", json={"sex": "f", "sport": "running"}).get_json()
    assert (updated["sex"], updated["sport"]) == ("f", "running")


def test_switching_to_running_removes_cycling_slots_from_future_plan_days(client):
    from datetime import date, timedelta

    client.post("/api/profile", json={"age": 45, "height_cm": 168, "program_start_date": "2026-10-01"})
    url = f"/api/calendar/week/{date.today() + timedelta(days=14)}"
    assert any(day["cycling"] for day in client.get(url).get_json()["days"])
    client.put("/api/profile", json={"sport": "running"})
    assert all(day["cycling"] is None for day in client.get(url).get_json()["days"])


def test_new_profile_defaults_to_tuesday_rest_day(client):
    response = client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    assert response.get_json()["rest_weekday"] == 1


def test_rejects_invalid_rest_weekday(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    assert client.put("/api/profile", json={"rest_weekday": 7}).status_code == 400
    assert client.put("/api/profile", json={"rest_weekday": "x"}).status_code == 400


def test_changing_rest_day_replans_untouched_future_days_only(client):
    from datetime import date, timedelta

    this_monday = date.today() - timedelta(days=date.today().weekday())
    start = this_monday - timedelta(weeks=3)  # naechste Woche liegt in der Base-Phase
    client.post("/api/profile", json={
        "age": 49, "height_cm": 173, "program_start_date": start.isoformat(), "rest_weekday": 4})
    monday = this_monday + timedelta(weeks=1)
    days = {d["date"]: d for d in client.get(f"/api/calendar/week/{monday}").get_json()["days"]}
    tuesday, thursday, friday = ((monday + timedelta(days=i)).isoformat() for i in (1, 3, 4))
    assert days[friday]["cycling"] is None and days[tuesday]["cycling"] is not None
    assert client.put(f"/api/calendar/day/{thursday}/plan", json={"planned_minutes": 50}).status_code == 200

    assert client.put("/api/profile", json={"rest_weekday": 1}).status_code == 200

    days = {d["date"]: d for d in client.get(f"/api/calendar/week/{monday}").get_json()["days"]}
    assert days[tuesday]["cycling"] is None  # neuer Ruhetag
    assert days[friday]["cycling"] is not None
    assert days[thursday]["cycling"]["minutes"] == 50  # vom Nutzer angepasster Tag bleibt
