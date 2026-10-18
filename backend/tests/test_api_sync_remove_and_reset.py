from datetime import date, timedelta

import pytest

from backend.engine.imported_training import ActivityRecord
from backend.extensions import db
from backend.models.day_comments import DayComment
from backend.models.food import Food, MealTemplate
from backend.models.intervals import IcuActivity
from backend.models.training_days import TrainingDay
from backend.models.user_profile import UserProfile
from backend.tests.test_intervals_icu import FakeClient

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
THIS_MONDAY = TODAY - timedelta(days=TODAY.weekday())


@pytest.fixture()
def profile(client):
    start = THIS_MONDAY - timedelta(weeks=2)
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": start.isoformat()})
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30,
                                       "checkin_date": (TODAY - timedelta(days=20)).isoformat()})
    return client


def _ride(icu_id="i1"):
    return ActivityRecord(icu_id=icu_id, day=YESTERDAY, type="VirtualRide", name="Zwift", moving_seconds=5400,
                          joules=900_000, intensity=72.0, training_load=70)


def _imported(client) -> list[str]:
    day = client.get(f"/api/calendar/day/{YESTERDAY.isoformat()}").get_json()
    return [a["icu_id"] for a in day["imported"]]


def test_removed_activity_disappears_from_day_and_stays_away_after_sync(app, profile):
    app.config["INTERVALS_ICU_CLIENT"] = FakeClient(activities=[_ride()])
    profile.post("/api/intervals/sync")
    assert _imported(profile) == ["i1"]

    assert profile.delete("/api/intervals/activities/i1").status_code == 200
    assert _imported(profile) == []

    profile.post("/api/intervals/sync")  # 14-Tage-Fenster liefert dieselbe Aktivitaet erneut
    assert _imported(profile) == []
    assert IcuActivity.query.filter_by(icu_id="i1").one().ignored is True


def test_remove_unknown_activity_returns_404(profile):
    assert profile.delete("/api/intervals/activities/nope").status_code == 404


def test_reset_requires_exact_confirmation_and_deletes_nothing_otherwise(profile):
    assert profile.post("/api/admin/reset", json={}).status_code == 400
    assert profile.post("/api/admin/reset", json={"confirm": "ja"}).status_code == 400
    assert profile.get("/api/profile").status_code == 200


def test_reset_deletes_user_data_but_keeps_shared_foods_and_meal_templates(app, profile):
    profile.get(f"/api/calendar/week/{THIS_MONDAY.isoformat()}")  # legt training_days an
    db.session.add_all([
        DayComment(day_date=TODAY, text="x"),
        Food(source="custom", source_id="c1", name="Haferflocken", search_name="haferflocken", kcal_100g=370,
             protein_100g=13, carbs_100g=60, fat_100g=7),
        MealTemplate(name="Standard", meal="fruehstueck"),
    ])
    db.session.commit()
    assert TrainingDay.query.count() > 0

    response = profile.post("/api/admin/reset", json={"confirm": "ZURÜCKSETZEN"})

    assert response.status_code == 200 and response.get_json()["backup"] is None  # In-Memory-DB
    assert UserProfile.query.count() == TrainingDay.query.count() == DayComment.query.count() == 0
    assert MealTemplate.query.count() == 1
    assert Food.query.count() == 1
    assert profile.get("/api/profile").status_code == 404


def test_profile_can_be_created_again_after_reset(profile):
    profile.post("/api/admin/reset", json={"confirm": "ZURÜCKSETZEN"})
    created = profile.post("/api/profile", json={"age": 50, "height_cm": 173, "program_start_date": "2026-11-02"})
    assert created.status_code == 201
