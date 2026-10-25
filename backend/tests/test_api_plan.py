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
    assert sum(m["carbs_g"] for m in body["meals"]) == pytest.approx(body["macros"]["carbs_g"])
    assert sum(m["fat_g"] for m in body["meals"]) == pytest.approx(body["macros"]["fat_g"])


def test_today_plan_with_query_params_keeps_manual_mode(client):
    _calendar_profile(client)
    body = client.get(f"/api/plan/today{PLAN_QUERY}").get_json()
    assert body["training"] is None
    assert body["day_type"] == "moderater_tag"


def test_plan_uses_activity_factor_from_profile(client):
    _setup_profile_and_checkin(client)
    client.put("/api/profile", json={"activity_level": "schwer"})
    nutrition = client.get(f"/api/plan/today{PLAN_QUERY}").get_json()["nutrition"]
    assert nutrition["non_exercise_factor"] == 2.1
    assert nutrition["non_exercise_kcal"] == pytest.approx(nutrition["bmr_kcal"] * 2.1)


# ---- Plan fuer beliebige Tage und Uebersicht (Ernaehrungs-Kalender)

def _days_range(days_back: int, days_forward: int = 0) -> str:
    from datetime import date, timedelta

    today = date.today()
    return f"from={(today - timedelta(days=days_back)).isoformat()}&to={(today + timedelta(days=days_forward)).isoformat()}"


def test_plan_for_today_matches_plan_today(client):
    from datetime import date

    _calendar_profile(client)
    today = client.get("/api/plan/today").get_json()
    by_date = client.get(f"/api/plan/{date.today().isoformat()}").get_json()
    assert by_date["nutrition"] == today["nutrition"]
    assert by_date["macros"] == today["macros"]


def test_plan_for_future_day_writes_no_training_days(client, app):
    from datetime import date, timedelta

    from backend.models.training_days import TrainingDay

    _calendar_profile(client)
    client.get("/api/plan/today")
    before = TrainingDay.query.count()
    far = (date.today() + timedelta(days=60)).isoformat()
    assert client.get(f"/api/plan/{far}").status_code == 200
    assert TrainingDay.query.count() == before


def test_plan_for_day_before_program_start_is_422(client):
    _setup_profile_and_checkin(client, program_start_date="2026-10-01")
    response = client.get("/api/plan/2026-09-01")
    assert response.status_code == 422
    assert "Programmstart" in response.get_json()["error"]


def test_plan_for_invalid_date_is_400(client):
    _calendar_profile(client)
    assert client.get("/api/plan/morgen").status_code == 400


def test_plan_uses_newest_checkin_up_to_that_day(client):
    from datetime import date, timedelta

    _calendar_profile(client)
    today = date.today()
    client.post("/api/checkins", json={"weight_kg": 80, "bodyfat_pct": 23, "muscle_kg": 30,
                                       "checkin_date": (today - timedelta(days=3)).isoformat()})
    old_day = (today - timedelta(days=2)).isoformat()
    older = client.get(f"/api/plan/{old_day}").get_json()["nutrition"]["bmr_kcal"]
    client.post("/api/checkins", json={"weight_kg": 60, "bodyfat_pct": 23, "muscle_kg": 30,
                                       "checkin_date": (today - timedelta(days=1)).isoformat()})
    assert client.get(f"/api/plan/{old_day}").get_json()["nutrition"]["bmr_kcal"] == older
    assert client.get(f"/api/plan/{today.isoformat()}").get_json()["nutrition"]["bmr_kcal"] < older


def test_days_overview_has_target_and_eaten(client):
    from datetime import date

    _calendar_profile(client)
    today = date.today().isoformat()
    client.post("/api/food-log", json={"date": today, "meal": "snack", "label": "Gel", "kcal": 300,
                                       "protein_g": 0, "carbs_g": 70, "fat_g": 0})
    body = client.get(f"/api/plan/days?{_days_range(1, 1)}").get_json()
    assert [d["date"] for d in body["days"]][1] == today
    day = body["days"][1]
    assert day["eaten"]["kcal"] == 300
    assert day["target"]["kcal"] == pytest.approx(client.get("/api/plan/today").get_json()["nutrition"]["target_kcal"])
    assert body["days"][0]["eaten"] is None


def test_days_overview_has_no_target_before_program_start(client):
    _setup_profile_and_checkin(client, program_start_date="2026-10-01")
    body = client.get("/api/plan/days?from=2026-09-29&to=2026-10-02").get_json()
    assert [d["target"] is None for d in body["days"]] == [True, True, False, False]


@pytest.mark.parametrize("query", ["", "from=2026-10-01", "from=x&to=y", "from=2026-10-05&to=2026-10-01",
                                   "from=2026-01-01&to=2026-12-31"])
def test_days_overview_rejects_bad_ranges(client, query):
    _calendar_profile(client)
    assert client.get(f"/api/plan/days?{query}").status_code == 400


def test_days_overview_has_planned_separately_from_eaten(client):
    from datetime import date, timedelta

    _calendar_profile(client)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    client.post("/api/food-log", json={"date": tomorrow, "meal": "mittag", "label": "Pasta", "kcal": 700,
                                       "protein_g": 25, "carbs_g": 120, "fat_g": 10, "status": "planned"})
    day = client.get(f"/api/plan/days?from={tomorrow}&to={tomorrow}").get_json()["days"][0]
    assert day["planned"]["kcal"] == 700
    assert day["eaten"] is None


def test_plan_today_ignores_planned_entries(client):
    from datetime import date

    _calendar_profile(client)
    client.post("/api/food-log", json={"date": date.today().isoformat(), "meal": "mittag", "label": "Pasta",
                                       "kcal": 700, "protein_g": 25, "carbs_g": 120, "fat_g": 10, "status": "planned"})
    assert client.get("/api/plan/today").get_json()["intake"] is None


def _meal_slots(client) -> list[str]:
    body = client.get(f"/api/plan/today{PLAN_QUERY}").get_json()
    return [m["slot"] for m in body["meals"]]


def test_training_after_work_merges_snack_2_into_dinner(client):
    from datetime import date

    _setup_profile_and_checkin(client)
    today = date.today().weekday()
    client.put("/api/profile", json={"evening_training_days": [today]})
    assert _meal_slots(client) == ["fruehstueck", "snack_1", "mittag", "abend"]
    body = client.get(f"/api/plan/today{PLAN_QUERY}").get_json()
    assert any("nach der Arbeit" in hint for hint in body["timing_hints"])


def test_flexible_day_keeps_all_five_meals(client):
    from datetime import date

    _setup_profile_and_checkin(client)
    client.put("/api/profile", json={"evening_training_days": [(date.today().weekday() + 1) % 7]})
    assert len(_meal_slots(client)) == 5


def test_evening_training_days_default_update_and_validation(client):
    body = client.post(
        "/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"}
    ).get_json()
    assert body["evening_training_days"] == [1, 2, 3, 4]
    assert {"id": 0, "label": "Mo"} in body["weekday_options"]
    assert client.put("/api/profile", json={"evening_training_days": [5, 1]}).get_json()["evening_training_days"] == [1, 5]
    assert client.put("/api/profile", json={"evening_training_days": [7]}).status_code == 400
    assert client.put("/api/profile", json={"evening_training_days": "1,2"}).status_code == 400
