import pytest

from backend.engine.nutrition_calc import (
    CyclingIntensity,
    DayType,
    calculate_bmr,
    calculate_cycling_kcal,
    calculate_daily_kcal_target,
    calculate_deficit_kcal,
    calculate_macro_targets,
    calculate_non_exercise_kcal,
    calculate_strength_kcal,
    derive_day_type,
    distribute_meals,
    intra_fueling,
    nutrition_timing_hints,
)

REFERENCE_WEIGHT_KG = 74.0
REFERENCE_HEIGHT_CM = 173.0
REFERENCE_AGE = 49


def test_calculates_bmr_matching_reference_person():
    bmr = calculate_bmr(REFERENCE_WEIGHT_KG, REFERENCE_HEIGHT_CM, REFERENCE_AGE)
    assert round(bmr) == 1581


def test_non_exercise_kcal_applies_1_45_factor_to_bmr():
    assert calculate_non_exercise_kcal(1000.0) == pytest.approx(1450.0)


@pytest.mark.parametrize(
    "intensity,expected_kcal_per_hour",
    [
        (CyclingIntensity.LEICHT_REKOM, 503.0),
        (CyclingIntensity.MODERAT_BASE, 592.0),
        (CyclingIntensity.ZUEGIG_TEMPO, 740.0),
        (CyclingIntensity.RENNEN_INTERVALLE, 888.0),
        (CyclingIntensity.SEHR_HART, 1169.0),
    ],
)
def test_cycling_kcal_matches_reference_table_at_74kg(intensity, expected_kcal_per_hour):
    kcal = calculate_cycling_kcal(hours=1.0, intensity=intensity, weight_kg=REFERENCE_WEIGHT_KG)
    assert kcal == pytest.approx(expected_kcal_per_hour)


def test_cycling_kcal_scales_with_current_bodyweight():
    kcal_at_74kg = calculate_cycling_kcal(1.0, CyclingIntensity.MODERAT_BASE, 74.0)
    kcal_at_68kg = calculate_cycling_kcal(1.0, CyclingIntensity.MODERAT_BASE, 68.0)
    assert kcal_at_68kg < kcal_at_74kg
    assert kcal_at_68kg == pytest.approx(592.0 / 74.0 * 68.0)


def test_cycling_kcal_rejects_negative_hours():
    with pytest.raises(ValueError):
        calculate_cycling_kcal(-1.0, CyclingIntensity.MODERAT_BASE, 74.0)


def test_strength_kcal_defaults_to_300_per_session():
    assert calculate_strength_kcal(2) == pytest.approx(600.0)


def test_strength_kcal_rejects_negative_sessions():
    with pytest.raises(ValueError):
        calculate_strength_kcal(-1)


def test_deficit_active_in_base_and_build1():
    assert calculate_deficit_kcal("base") == pytest.approx(350.0)
    assert calculate_deficit_kcal("build1") == pytest.approx(350.0)


@pytest.mark.parametrize("phase_id", ["phase0_wiedereinstieg", "build2", "peak_taper", "passsaison"])
def test_deficit_zero_outside_base_and_build1(phase_id):
    assert calculate_deficit_kcal(phase_id) == 0.0


def test_daily_kcal_target_composes_components_correctly():
    target = calculate_daily_kcal_target(
        weight_kg=REFERENCE_WEIGHT_KG,
        height_cm=REFERENCE_HEIGHT_CM,
        age=REFERENCE_AGE,
        phase_id="base",
        cycling_hours=1.0,
        cycling_intensity=CyclingIntensity.MODERAT_BASE,
        strength_sessions=1,
    )
    assert target.bmr_kcal == pytest.approx(1581.25)
    assert target.non_exercise_kcal == pytest.approx(2292.8125)
    assert target.cycling_kcal == pytest.approx(592.0)
    assert target.strength_kcal == pytest.approx(300.0)
    assert target.maintenance_kcal == pytest.approx(3184.8125)
    assert target.deficit_kcal == pytest.approx(350.0)
    assert target.target_kcal == pytest.approx(2834.8125)
    assert target.non_exercise_factor == 1.45


def test_daily_kcal_target_uses_given_non_exercise_factor():
    target = calculate_daily_kcal_target(
        weight_kg=REFERENCE_WEIGHT_KG,
        height_cm=REFERENCE_HEIGHT_CM,
        age=REFERENCE_AGE,
        phase_id="base",
        cycling_hours=0.0,
        cycling_intensity=CyclingIntensity.MODERAT_BASE,
        strength_sessions=0,
        non_exercise_factor=2.1,
    )
    assert target.non_exercise_kcal == pytest.approx(1581.25 * 2.1)
    assert target.target_kcal == pytest.approx(1581.25 * 2.1 - 350.0)
    # Sanity: liegt in der von der Recherche genannten Groessenordnung (~2830-3030
    # Erhaltung, ~2480 Wochenschnitt-Ziel) - exakter Match ist nicht zu erwarten,
    # da das parametergetriebene Modell bewusst anders periodisiert als die
    # Tagestyp-Tabelle in ernaehrungsplan.md (siehe Plan-Dokumentation).
    assert 2000 < target.target_kcal < 3100


def test_daily_kcal_target_has_no_deficit_outside_active_phases():
    target = calculate_daily_kcal_target(
        weight_kg=REFERENCE_WEIGHT_KG,
        height_cm=REFERENCE_HEIGHT_CM,
        age=REFERENCE_AGE,
        phase_id="peak_taper",
        cycling_hours=1.0,
        cycling_intensity=CyclingIntensity.MODERAT_BASE,
        strength_sessions=1,
    )
    assert target.deficit_kcal == 0.0
    assert target.target_kcal == target.maintenance_kcal


@pytest.mark.parametrize(
    "day_type,expected_g_per_kg",
    [
        (DayType.RUHETAG, 3.0),
        (DayType.MODERATER_TAG, 5.0),
        (DayType.LANGER_HARTER_TAG, 7.0),
    ],
)
def test_macro_carbs_periodized_by_daytype(day_type, expected_g_per_kg):
    macros = calculate_macro_targets(weight_kg=74.0, ffm_kg=57.0, day_type=day_type, target_kcal=2480.0)
    assert macros.carbs_g == pytest.approx(74.0 * expected_g_per_kg)


def test_macro_protein_targets_ffm_based_range():
    macros = calculate_macro_targets(weight_kg=74.0, ffm_kg=57.0, day_type=DayType.MODERATER_TAG, target_kcal=2480.0)
    # Helms/Aragon/Fitschen-Range: 2.3-2.9 g/kg FFM
    assert 57.0 * 2.3 <= macros.protein_g <= 57.0 * 2.9


def test_macro_fat_stays_at_or_above_0_9_g_per_kg():
    macros = calculate_macro_targets(weight_kg=74.0, ffm_kg=57.0, day_type=DayType.MODERATER_TAG, target_kcal=2480.0)
    assert macros.fat_g >= 74.0 * 0.9


def test_rmr_kcal_replaces_mifflin_st_jeor_bmr():
    target = calculate_daily_kcal_target(
        weight_kg=REFERENCE_WEIGHT_KG,
        height_cm=REFERENCE_HEIGHT_CM,
        age=REFERENCE_AGE,
        phase_id="base",
        cycling_hours=0.0,
        cycling_intensity=CyclingIntensity.MODERAT_BASE,
        strength_sessions=0,
        rmr_kcal=1800.0,
    )
    assert target.bmr_kcal == 1800.0
    assert target.non_exercise_kcal == pytest.approx(1800.0 * 1.45)


def test_day_type_rest_without_any_training():
    assert derive_day_type(0, None, 0) == DayType.RUHETAG


def test_day_type_moderate_for_strength_or_short_easy_ride():
    assert derive_day_type(0, None, 1) == DayType.MODERATER_TAG
    assert derive_day_type(60, CyclingIntensity.MODERAT_BASE, 0) == DayType.MODERATER_TAG


def test_day_type_long_hard_for_two_hours_or_intervals():
    assert derive_day_type(120, CyclingIntensity.MODERAT_BASE, 0) == DayType.LANGER_HARTER_TAG
    assert derive_day_type(60, CyclingIntensity.RENNEN_INTERVALLE, 0) == DayType.LANGER_HARTER_TAG


def test_meals_sum_to_daily_targets():
    meals = distribute_meals(2480, 160)
    assert [m.slot for m in meals] == ["fruehstueck", "snack_1", "mittag", "snack_2", "abend"]
    assert sum(m.kcal for m in meals) == pytest.approx(2480)
    assert sum(m.protein_g for m in meals) == pytest.approx(160)
    assert meals[2].kcal == pytest.approx(meals[4].kcal)


def test_no_fueling_below_75_minutes():
    assert intra_fueling(60, CyclingIntensity.RENNEN_INTERVALLE).carbs_g_per_hour_max == 0


def test_moderate_fueling_up_to_two_and_a_half_hours():
    fueling = intra_fueling(120, CyclingIntensity.MODERAT_BASE)
    assert (fueling.carbs_g_per_hour_min, fueling.carbs_g_per_hour_max) == (30, 60)
    assert fueling.carbs_g_total_max == pytest.approx(120)


def test_high_fueling_for_long_rides_or_intense_intervals():
    assert intra_fueling(180, CyclingIntensity.MODERAT_BASE).carbs_g_per_hour_max == 90
    assert intra_fueling(90, CyclingIntensity.RENNEN_INTERVALLE).carbs_g_per_hour_min == 60


def test_no_fueling_without_ride():
    assert intra_fueling(0, None) is None


def test_timing_hints_empty_on_rest_day_and_include_protein_after_strength():
    assert nutrition_timing_hints(False, False, 74) == []
    assert any("Protein" in h for h in nutrition_timing_hints(False, True, 74))


def test_macro_targets_accept_event_overrides_for_carbs_and_fat():
    macros = calculate_macro_targets(70, 55, DayType.RUHETAG, 2500, carbs_g_per_kg=10.0, fat_g_per_kg=0.8)
    assert macros.carbs_g == 700
    assert macros.fat_g == pytest.approx(56)
    assert macros.protein_g == calculate_macro_targets(70, 55, DayType.RUHETAG, 2500).protein_g
