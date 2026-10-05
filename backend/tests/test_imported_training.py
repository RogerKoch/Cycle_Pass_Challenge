from datetime import date

import pytest

from backend.engine.imported_training import ActivityRecord, intensity_from_if, summarize_day
from backend.engine.nutrition_calc import CyclingIntensity

DAY = date(2026, 10, 6)


def _activity(type_="VirtualRide", seconds=3600, **kwargs):
    return ActivityRecord(icu_id=kwargs.pop("icu_id", "i1"), day=DAY, type=type_, moving_seconds=seconds, **kwargs)


def test_ride_types_and_strength_are_recognised():
    assert _activity("Ride").is_ride and _activity("VirtualRide").is_ride and _activity("GravelRide").is_ride
    assert not _activity("Run").is_ride
    assert _activity("WeightTraining").is_strength


def test_kcal_from_kilojoules_and_garmin_calories_are_ignored():
    assert _activity(joules=812_000, calories=700).kcal == pytest.approx(812)
    assert _activity(calories=351).kcal is None


def test_ride_without_power_uses_met_estimate_instead_of_garmin_calories():
    # 3 h ohne Leistung, Garmin meldet 351 kcal -> MET moderat (592 kcal/h bei 74 kg)
    day = summarize_day([_activity("Ride", seconds=10800, calories=351)], weight_kg=74.0)
    assert day.ride_kcal == pytest.approx(592 * 3)


def test_mixed_day_combines_kilojoules_and_met_per_ride():
    day = summarize_day([
        _activity(icu_id="a", seconds=3600, joules=700_000, intensity=70),
        _activity("Ride", icu_id="b", seconds=3600),
    ], weight_kg=74.0)
    assert day.ride_kcal == pytest.approx(700 + 592)


@pytest.mark.parametrize("intensity_pct,expected", [
    (None, CyclingIntensity.MODERAT_BASE),
    (50, CyclingIntensity.LEICHT_REKOM),
    (70, CyclingIntensity.MODERAT_BASE),
    (80, CyclingIntensity.ZUEGIG_TEMPO),
    (95, CyclingIntensity.RENNEN_INTERVALLE),
    (105, CyclingIntensity.RENNEN_INTERVALLE),
    (110, CyclingIntensity.SEHR_HART),
])
def test_intensity_bands_follow_coggan_zones(intensity_pct, expected):
    assert intensity_from_if(intensity_pct) == expected


def test_summary_adds_rides_weights_intensity_by_time_and_detects_strength():
    day = summarize_day([
        _activity(icu_id="a", seconds=3600, joules=700_000, intensity=70),
        _activity(icu_id="b", seconds=1800, joules=400_000, intensity=100),
        _activity("WeightTraining", icu_id="c", seconds=3000),
        _activity("Walk", icu_id="d", seconds=1200, calories=100),
    ])
    assert day.ride_minutes == 90
    assert day.ride_kcal == pytest.approx(1100)
    assert day.ride_intensity == CyclingIntensity.ZUEGIG_TEMPO  # (70*60 + 100*30) / 90 = 80 %
    assert day.strength_done is True
    assert day.has_training


def test_without_weight_unpowered_rides_leave_kcal_to_the_caller():
    day = summarize_day([_activity(icu_id="a", joules=500_000), _activity(icu_id="b")])
    assert day.ride_kcal is None


def test_non_training_activities_do_not_count():
    day = summarize_day([_activity("Walk", calories=150)])
    assert not day.has_training
    assert day.ride_intensity is None
