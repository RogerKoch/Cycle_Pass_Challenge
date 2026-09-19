PLAN_QUERY = "?cycling_hours=1&cycling_intensity=moderat_base&strength_sessions=1&day_type=moderater_tag"


def _setup_profile_and_checkin(client, program_start_date="2026-10-01"):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": program_start_date})
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30})


def test_today_plan_returns_zones_unavailable_when_no_ftp_test_exists(client):
    _setup_profile_and_checkin(client)
    response = client.get(f"/api/plan/today{PLAN_QUERY}")
    assert response.status_code == 200
    assert response.get_json()["zones"]["available"] is False


def test_today_plan_returns_zones_when_ftp_test_exists(client):
    _setup_profile_and_checkin(client)
    client.post("/api/checkins/ftp-tests", json={"best_1min_power_watts": 300})
    response = client.get(f"/api/plan/today{PLAN_QUERY}")
    body = response.get_json()
    assert body["zones"]["available"] is True
    assert body["zones"]["ftp_watts"] == 225


def test_today_plan_requires_day_type_query_param(client):
    _setup_profile_and_checkin(client)
    response = client.get("/api/plan/today?cycling_hours=1&cycling_intensity=moderat_base&strength_sessions=1")
    assert response.status_code == 400


def test_today_plan_rejects_invalid_day_type(client):
    _setup_profile_and_checkin(client)
    response = client.get(
        "/api/plan/today?cycling_hours=1&cycling_intensity=moderat_base&strength_sessions=1&day_type=nonsense"
    )
    assert response.status_code == 400


def test_today_plan_returns_404_when_profile_missing(client):
    response = client.get(f"/api/plan/today{PLAN_QUERY}")
    assert response.status_code == 404


def test_today_plan_returns_422_when_no_checkin_exists(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    response = client.get(f"/api/plan/today{PLAN_QUERY}")
    assert response.status_code == 422


def test_today_plan_disables_deficit_far_in_the_past_start_date(client):
    # program_start_date weit in der Vergangenheit -> Passsaison ist aktiv -> Defizit = 0
    _setup_profile_and_checkin(client, program_start_date="2000-01-01")
    response = client.get(f"/api/plan/today{PLAN_QUERY}")
    body = response.get_json()
    assert body["phase"]["phase_id"] == "passsaison"
    assert body["nutrition"]["deficit_kcal"] == 0.0
