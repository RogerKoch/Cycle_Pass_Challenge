import pytest


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


def test_measured_rmr_changes_kcal_target_and_marks_source(client):
    _setup_profile_and_checkin(client)
    estimated = client.get(f"/api/plan/today{PLAN_QUERY}").get_json()
    client.put("/api/baseline/rmr_kcal", json={"value": 1800})
    measured = client.get(f"/api/plan/today{PLAN_QUERY}").get_json()
    assert estimated["targets_source"] == "estimated"
    assert measured["targets_source"] == "measured"
    assert measured["nutrition"]["bmr_kcal"] == 1800
    assert measured["nutrition"]["maintenance_kcal"] > estimated["nutrition"]["maintenance_kcal"]


def test_energy_availability_only_present_with_intake_today(client):
    from datetime import date

    _setup_profile_and_checkin(client)
    assert client.get(f"/api/plan/today{PLAN_QUERY}").get_json()["intake"] is None
    client.put(
        f"/api/intake/{date.today().isoformat()}",
        json={"kcal": 2500, "protein_g": 150, "carbs_g": 300, "fat_g": 70},
    )
    body = client.get(f"/api/plan/today{PLAN_QUERY}").get_json()
    training_kcal = body["nutrition"]["cycling_kcal"] + body["nutrition"]["strength_kcal"]
    ffm = 74 * 0.77
    assert body["intake"]["energy_availability"] == pytest.approx((2500 - training_kcal) / ffm)


def _calendar_profile(client):
    from datetime import date, timedelta

    this_monday = date.today() - timedelta(days=date.today().weekday())
    _setup_profile_and_checkin(client, program_start_date=(this_monday - timedelta(weeks=2)).isoformat())


def _set_today(app, **fields):
    from datetime import date

    from backend.extensions import db
    from backend.models.training_days import TrainingDay

    row = TrainingDay.query.filter_by(day_date=date.today()).one()
    for key, value in fields.items():
        setattr(row, key, value)
    db.session.commit()


def test_today_plan_without_params_comes_from_training_calendar(client):
    from datetime import date

    _calendar_profile(client)
    response = client.get("/api/plan/today")
    assert response.status_code == 200
    body = response.get_json()
    assert body["training"]["date"] == date.today().isoformat()
    assert body["day_type"] in ("ruhetag", "moderater_tag", "langer_harter_tag")


def test_today_plan_uses_adjusted_planned_duration(client, app):
    _calendar_profile(client)
    client.get("/api/plan/today")
    _set_today(app, cycling_slot="z2_grundlage", planned_minutes=90, strength_session=None)
    body = client.get("/api/plan/today").get_json()
    assert body["nutrition"]["cycling_kcal"] == pytest.approx(592 * 1.5)
    assert body["nutrition"]["strength_kcal"] == 0
    assert body["training"]["cycling"]["minutes"] == 90
    assert body["fueling"]["carbs_g_per_hour_min"] == 30


def test_skipped_day_has_no_training_kcal_and_is_rest_day(client, app):
    from datetime import date

    _calendar_profile(client)
    client.get("/api/plan/today")
    _set_today(app, cycling_slot="z2_grundlage", strength_session="A")
    client.patch(f"/api/calendar/day/{date.today().isoformat()}", json={"status": "skipped"})
    body = client.get("/api/plan/today").get_json()
    assert body["nutrition"]["cycling_kcal"] == 0
    assert body["nutrition"]["strength_kcal"] == 0
    assert body["day_type"] == "ruhetag"
    assert body["fueling"] is None


def test_modified_day_uses_actual_minutes_and_intensity(client, app):
    from datetime import date

    _calendar_profile(client)
    client.get("/api/plan/today")
    _set_today(app, cycling_slot="z2_grundlage", strength_session=None)
    client.patch(
        f"/api/calendar/day/{date.today().isoformat()}",
        json={"status": "modified", "actual_minutes": 120, "actual_intensity": "moderat_base"},
    )
    body = client.get("/api/plan/today").get_json()
    assert body["nutrition"]["cycling_kcal"] == pytest.approx(592 * 2)
    assert body["day_type"] == "langer_harter_tag"


def test_meals_add_up_to_daily_target(client):
    _calendar_profile(client)
    body = client.get("/api/plan/today").get_json()
    assert sum(m["kcal"] for m in body["meals"]) == pytest.approx(body["nutrition"]["target_kcal"])
    assert sum(m["protein_g"] for m in body["meals"]) == pytest.approx(body["macros"]["protein_g"])


def test_today_plan_with_query_params_keeps_manual_mode(client):
    _calendar_profile(client)
    body = client.get(f"/api/plan/today{PLAN_QUERY}").get_json()
    assert body["training"] is None
    assert body["day_type"] == "moderater_tag"
