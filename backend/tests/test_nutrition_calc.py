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
