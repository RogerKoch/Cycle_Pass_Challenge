"""Tests fuer die Wochenanalyse der Ernaehrung (engine.nutrition_review und /api/nutrition/review)."""

from dataclasses import asdict
from datetime import date, timedelta

import pytest

from backend.engine.day_timeline import BaseTargets, build_timeline
from backend.engine.nutrition_calc import CyclingIntensity
from backend.engine.nutrition_review import DayInput, review_days

BASE = BaseTargets(kcal=2050, protein_g=107, carbs_g=198, fat_g=83)


def _plan(training: bool = True, evening: bool = True) -> list[dict]:
    minutes = 60 if training else 0
    return [asdict(s) for s in build_timeline(BASE, minutes, CyclingIntensity.MODERAT_BASE, 0, evening, False)]


def _meal(kcal: float, protein: float = 0.0, carbs: float = 0.0, fat: float = 0.0) -> dict:
    return {"kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat}


def _plan_as_eaten(plan: list[dict], scale: float = 1.0) -> dict:
    return {s["slot"]: _meal(s["kcal"] * scale, s["protein_g"] * scale, s["carbs_g"] * scale, s["fat_g"] * scale) for s in plan}


def _ids(result: dict) -> set[str]:
    return {f["id"] for f in result["findings"]}


def test_eating_exactly_the_plan_gives_no_findings():
    plan = _plan()
    result = review_days([DayInput(date(2026, 10, 19), plan, _plan_as_eaten(plan))])
    assert result["findings"] == []
    assert result["daily"]["kcal"]["pct"] == 100


def test_days_without_entries_are_ignored():
    assert review_days([DayInput(date(2026, 10, 19), _plan(), {})])["days_logged"] == 0


def test_flags_oversized_dinner_small_snacks_and_low_fat():
    plan = _plan(training=False)
    eaten = {
        "fruehstueck": _meal(530, 32, 73, 10),
        "snack": _meal(144, 5, 26, 2),
        "mittag": _meal(527, 42, 59, 13),
        "abend": _meal(656, 51, 77, 14),
    }
    result = review_days([DayInput(date(2026, 10, 19), plan, eaten)])
    assert {"dinner_heavy", "snacks_small", "fat_low"} <= _ids(result)
    assert result["findings"][0]["severity"] == "warn"


def test_missing_pre_snack_on_training_day_is_flagged():
    plan = _plan()
    eaten = _plan_as_eaten(plan)
    del eaten["pre"]
    assert "pre_missing" in _ids(review_days([DayInput(date(2026, 10, 19), plan, eaten)]))


def test_legacy_training_entries_count_as_sport_nutrition():
    plan = _plan()
    eaten = _plan_as_eaten(plan)
    del eaten["pre"], eaten["intra"]
    eaten["training"] = _meal(120, 2, 25, 1)
    result = review_days([DayInput(date(2026, 10, 19), plan, eaten)])
    assert "pre_missing" not in _ids(result)
    assert any(s["slot"] == "sport" and s["eaten"]["kcal"] == 120 for s in result["slots"])


def test_energy_within_tolerance_above_target_is_not_flagged():
    plan = _plan(training=False)
    result = review_days([DayInput(date(2026, 10, 19), plan, _plan_as_eaten(plan, 1.08))])
    assert "kcal_high" not in _ids(result)


def test_energy_above_tolerance_is_reported():
    plan = _plan(training=False)
    result = review_days([DayInput(date(2026, 10, 19), plan, _plan_as_eaten(plan, 1.2))])
    assert "kcal_high" in _ids(result)


def test_post_workout_entries_fold_into_merged_dinner_slot():
    plan = _plan()
    eaten = _plan_as_eaten(plan)
    eaten["abend"] = _meal(420, 30, 59, 20)
    eaten["post"] = _meal(217, 28, 15, 5)
    del eaten["intra"]
    result = review_days([DayInput(date(2026, 10, 19), plan, eaten)])
    dinner = next(s for s in result["slots"] if s["slot"] == "abend")
    assert dinner["eaten"]["kcal"] == pytest.approx(637)


def test_review_endpoint_requires_base_values(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30})
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.post("/api/food-log", json={"date": yesterday, "meal": "mittag", "label": "Reis", "kcal": 500,
                                       "protein_g": 10, "carbs_g": 100, "fat_g": 2})
    assert client.get("/api/nutrition/review").status_code == 422


def test_review_endpoint_compares_logged_days_with_timeline(client):
    client.post("/api/profile", json={"age": 49, "height_cm": 173, "program_start_date": "2026-10-01"})
    client.post("/api/checkins", json={"weight_kg": 74, "bodyfat_pct": 23, "muscle_kg": 30})
    client.put("/api/profile", json={"base_kcal": 2050, "base_protein_g": 107, "base_carbs_g": 198, "base_fat_g": 83})
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.post("/api/food-log", json={"date": yesterday, "meal": "abend", "label": "Pasta", "kcal": 900,
                                       "protein_g": 40, "carbs_g": 120, "fat_g": 10})
    body = client.get("/api/nutrition/review").get_json()
    assert body["days_logged"] == 1
    assert next(s for s in body["slots"] if s["slot"] == "abend")["eaten"]["kcal"] == 900
    assert "dinner_heavy" in {f["id"] for f in body["findings"]}


def test_review_endpoint_rejects_bad_dates(client):
    assert client.get("/api/nutrition/review?from=heute").status_code == 400
