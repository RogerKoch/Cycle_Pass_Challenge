"""Tests fuer den Ernaehrungs-Tagesablauf (engine.day_timeline)."""

import pytest

from backend.engine.day_timeline import (
    BaseTargets,
    SLOT_MEAL,
    build_timeline,
    sport_fueling,
    timeline_totals,
)
from backend.engine.nutrition_calc import CyclingIntensity

BASE = BaseTargets(kcal=2050, protein_g=107, carbs_g=198, fat_g=83, fiber_g=43)


def _by_slot(slots):
    return {s.slot: s for s in slots}


def test_rest_day_has_five_meals_and_no_sport_slots():
    slots = build_timeline(BASE, 0, None, 0, evening=False, weekend=False)
    assert [s.slot for s in slots] == ["fruehstueck", "snack", "mittag", "snack_nachmittag", "abend"]
    assert all(s.kind == SLOT_MEAL for s in slots)


def test_main_meals_sum_to_base_values():
    kcal, protein, carbs, fat = timeline_totals(build_timeline(BASE, 0, None, 0, evening=False, weekend=False))
    assert (kcal, protein, carbs, fat) == pytest.approx((2050, 107, 198, 83))


def test_main_meals_scale_with_base_kcal():
    base = BaseTargets(kcal=2255, protein_g=107, carbs_g=198, fat_g=83)
    breakfast = _by_slot(build_timeline(base, 0, None, 0, evening=False, weekend=False))["fruehstueck"]
    assert breakfast.kcal == pytest.approx(550 * 1.1)


def test_weekday_evening_places_pre_before_and_dinner_after_training():
    slots = _by_slot(build_timeline(BASE, 60, CyclingIntensity.MODERAT_BASE, 0, evening=True, weekend=False))
    assert slots["pre"].time == "17:15"
    assert slots["intra"].time == "18:00"
    assert slots["abend"].time == "19:15"
    assert "post" not in slots  # Post-Workout und Abendessen fallen zusammen
    assert slots["abend"].label == "Abendessen (Post-Workout)"
    assert slots["abend"].kcal == pytest.approx(420 + 217)


def test_weekend_morning_ride_replaces_lunch_with_post_meal():
    slots = _by_slot(build_timeline(BASE, 180, CyclingIntensity.MODERAT_BASE, 0, evening=False, weekend=True))
    assert "snack" not in slots and "post" not in slots
    assert slots["fruehstueck"].time == "08:00"
    assert slots["pre"].time == "09:15"
    assert slots["mittag"].time == "13:00"
    assert slots["mittag"].label == "Mittagessen (Post-Training)"


def test_short_morning_session_keeps_lunch_and_gets_separate_post():
    slots = _by_slot(build_timeline(BASE, 30, CyclingIntensity.LEICHT_REKOM, 0, evening=False, weekend=True))
    assert slots["post"].time == "10:30"
    assert slots["mittag"].time == "12:30"
    assert slots["mittag"].kcal == pytest.approx(555 + 275)  # Vormittags-Snack entfaellt ins Mittagessen


def test_training_day_target_is_base_plus_pre_and_post():
    total = timeline_totals(build_timeline(BASE, 60, CyclingIntensity.LEICHT_REKOM, 0, evening=False, weekend=True))[0]
    assert total == pytest.approx(2050 + 117 + 217)  # Wasser beim Intra, Post-Variante 1


def test_intensive_session_adds_about_600_kcal_of_sport_nutrition():
    slots = build_timeline(BASE, 45, CyclingIntensity.RENNEN_INTERVALLE, 0, evening=False, weekend=True)
    extra = timeline_totals(slots)[0] - 2050
    assert extra == pytest.approx(600, rel=0.15)


def test_strength_block_extends_training_and_adds_protein_post():
    slots = _by_slot(build_timeline(BASE, 30, CyclingIntensity.LEICHT_REKOM, 1, evening=True, weekend=False))
    assert slots["intra"].hint.startswith("18:00–19:20")
    assert slots["abend"].protein_g >= 30


def test_sport_fueling_follows_duration_and_intensity():
    assert sport_fueling(0, None) is None
    water = sport_fueling(45, CyclingIntensity.LEICHT_REKOM)
    assert water.carbs_g_per_hour_max == 0
    ga1 = sport_fueling(90, CyclingIntensity.MODERAT_BASE)
    assert (ga1.carbs_g_per_hour_min, ga1.carbs_g_per_hour_max) == (40, 60)
    hard = sport_fueling(45, CyclingIntensity.RENNEN_INTERVALLE)
    assert (hard.carbs_g_per_hour_min, hard.carbs_g_per_hour_max) == (60, 90)
    assert (sport_fueling(180, CyclingIntensity.MODERAT_BASE).carbs_g_per_hour_max) == 90


def test_base_targets_requires_all_main_values():
    class P:
        base_kcal, base_protein_g, base_carbs_g, base_fat_g, base_fiber_g = 2050, 107, 198, None, 43

    assert BaseTargets.from_profile(P()) is None
    P.base_fat_g = 83
    assert BaseTargets.from_profile(P()) == BASE
