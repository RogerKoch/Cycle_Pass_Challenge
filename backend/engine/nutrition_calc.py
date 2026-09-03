"""Kalorien- und Makronaehrstoff-Berechnung.

Quellen: docs/research/ernaehrungsplan.md, Formeln/Tabellen aus docs/data-model.yaml.

Das taegliche kcal-Ziel wird aus den tatsaechlichen Trainingsparametern des Tages berechnet
(BMR -> Erhaltungsbedarf -> Phasen-Defizit), nicht aus einer statischen Tagestyp-Tabelle.
DayType wird ausschliesslich fuer die Makro-Periodisierung (Kohlenhydrate g/kg) verwendet,
das ist eine explizite Tabelle in data-model.yaml.
"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DayType(str, Enum):
    """Tagestyp fuer die Kohlenhydrat-Periodisierung."""

    RUHETAG = "ruhetag"
    MODERATER_TAG = "moderater_tag"
    LANGER_HARTER_TAG = "langer_harter_tag"


class CyclingIntensity(str, Enum):
    """MET-basierte Rad-Intensitaetsstufen (kcal/h bei 74kg Referenzgewicht)."""

    LEICHT_REKOM = "leicht_rekom"
    MODERAT_BASE = "moderat_base"
    ZUEGIG_TEMPO = "zuegig_tempo"
    RENNEN_INTERVALLE = "rennen_intervalle"
    SEHR_HART = "sehr_hart"


_CYCLING_KCAL_PER_HOUR_AT_74KG: dict[CyclingIntensity, float] = {
    CyclingIntensity.LEICHT_REKOM: 503.0,
    CyclingIntensity.MODERAT_BASE: 592.0,
    CyclingIntensity.ZUEGIG_TEMPO: 740.0,
    CyclingIntensity.RENNEN_INTERVALLE: 888.0,
    CyclingIntensity.SEHR_HART: 1169.0,
}
_REFERENCE_WEIGHT_KG = 74.0

_CARBS_G_PER_KG_BY_DAYTYPE: dict[DayType, float] = {
    DayType.RUHETAG: 3.0,
    DayType.MODERATER_TAG: 5.0,
    DayType.LANGER_HARTER_TAG: 7.0,  # Mittelwert aus data-model.yaml [6, 8]
}

ACTIVE_DEFICIT_PHASES = {"base", "build1"}
DEFAULT_DEFICIT_KCAL = 350.0  # Mittelwert aus data-model.yaml [300, 400]
STRENGTH_KCAL_PER_SESSION = 300.0
NON_EXERCISE_FACTOR = 1.45
PROTEIN_G_PER_KG_FFM = 2.6  # Mittelwert aus data-model.yaml [2.3, 2.9]
FAT_G_PER_KG_BODYWEIGHT = 0.95  # Mittelwert aus data-model.yaml [0.9, 1.0]


@dataclass
class NutritionTarget:
    """Taegliches kcal-Ziel inklusive seiner Komponenten (fuer Transparenz/Debugging)."""

    bmr_kcal: float
    non_exercise_kcal: float
    cycling_kcal: float
    strength_kcal: float
    maintenance_kcal: float
    deficit_kcal: float
    target_kcal: float


@dataclass
class MacroTargets:
    """Taegliche Makronaehrstoff-Ziele in Gramm."""

    protein_g: float
    fat_g: float
    carbs_g: float


def calculate_bmr(weight_kg: float, height_cm: float, age: int) -> float:
    """Grundumsatz nach Mifflin-St Jeor (Formel fuer Maenner).

    Args:
        weight_kg: Koerpergewicht in kg.
        height_cm: Koerpergroesse in cm.
        age: Alter in Jahren.

    Returns:
        BMR in kcal/Tag.
    """
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5


def calculate_non_exercise_kcal(bmr_kcal: float, factor: float = NON_EXERCISE_FACTOR) -> float:
    """Nicht-Trainings-Energieumsatz (Alltagsaktivitaet + Thermogenese).

    Args:
        bmr_kcal: Grundumsatz in kcal/Tag.
        factor: Multiplikator auf den BMR.

    Returns:
        Nicht-Trainings-kcal/Tag.
    """
    return bmr_kcal * factor


def calculate_cycling_kcal(hours: float, intensity: CyclingIntensity, weight_kg: float) -> float:
    """Rad-Energieverbrauch, skaliert vom 74kg-Referenzwert auf das aktuelle Gewicht.

    Args:
        hours: Fahrzeit in Stunden.
        intensity: Intensitaetsstufe der Ausfahrt.
        weight_kg: aktuelles Koerpergewicht in kg.

    Returns:
        Verbrauchte kcal fuer diese Ausfahrt.

    Raises:
        ValueError: wenn hours negativ ist.
    """
    if hours < 0:
        raise ValueError(f"hours darf nicht negativ sein, war {hours}")
    kcal_per_hour_at_current_weight = _CYCLING_KCAL_PER_HOUR_AT_74KG[intensity] / _REFERENCE_WEIGHT_KG * weight_kg
    return kcal_per_hour_at_current_weight * hours


def calculate_strength_kcal(sessions: int, kcal_per_session: float = STRENGTH_KCAL_PER_SESSION) -> float:
    """Kraft-Energieverbrauch fuer eine Anzahl Einheiten.

    Args:
        sessions: Anzahl Krafteinheiten am Tag.
        kcal_per_session: kcal pro Einheit.

    Returns:
        Verbrauchte kcal.

    Raises:
        ValueError: wenn sessions negativ ist.
    """
    if sessions < 0:
        raise ValueError(f"sessions darf nicht negativ sein, war {sessions}")
    return sessions * kcal_per_session


def calculate_deficit_kcal(phase_id: str, deficit_kcal: float = DEFAULT_DEFICIT_KCAL) -> float:
    """Kalorisches Defizit fuer den Tag, abhaengig von der Trainingsphase.

    Args:
        phase_id: aktuelle Trainingsphasen-ID (siehe engine.training_phase).
        deficit_kcal: Defizithoehe, falls die Phase aktiv ist.

    Returns:
        deficit_kcal wenn phase_id in ACTIVE_DEFICIT_PHASES, sonst 0.
    """
    return deficit_kcal if phase_id in ACTIVE_DEFICIT_PHASES else 0.0


def calculate_daily_kcal_target(
    weight_kg: float,
    height_cm: float,
    age: int,
    phase_id: str,
    cycling_hours: float,
    cycling_intensity: CyclingIntensity,
    strength_sessions: int,
) -> NutritionTarget:
    """Berechnet das vollstaendige taegliche kcal-Ziel aus den Tagesparametern.

    Args:
        weight_kg: aktuelles Koerpergewicht (aus dem letzten Check-in).
        height_cm: Koerpergroesse.
        age: Alter in Jahren.
        phase_id: aktuelle Trainingsphase.
        cycling_hours: geplante/geloggte Radzeit fuer den Tag.
        cycling_intensity: Intensitaet der Radeinheit.
        strength_sessions: Anzahl Krafteinheiten am Tag.

    Returns:
        NutritionTarget mit voller Komponenten-Aufschluesselung.
    """
    bmr = calculate_bmr(weight_kg, height_cm, age)
    non_exercise = calculate_non_exercise_kcal(bmr)
    cycling = calculate_cycling_kcal(cycling_hours, cycling_intensity, weight_kg)
    strength = calculate_strength_kcal(strength_sessions)
    maintenance = non_exercise + cycling + strength
    deficit = calculate_deficit_kcal(phase_id)
    return NutritionTarget(
        bmr_kcal=bmr,
        non_exercise_kcal=non_exercise,
        cycling_kcal=cycling,
        strength_kcal=strength,
        maintenance_kcal=maintenance,
        deficit_kcal=deficit,
        target_kcal=maintenance - deficit,
    )


def calculate_macro_targets(weight_kg: float, ffm_kg: float, day_type: DayType, target_kcal: float) -> MacroTargets:
    """Berechnet Protein-, Fett- und Kohlenhydrat-Ziele in Gramm.

    Args:
        weight_kg: aktuelles Koerpergewicht.
        ffm_kg: fettfreie Masse (aus dem letzten Check-in).
        day_type: Tagestyp fuer die Kohlenhydrat-Periodisierung.
        target_kcal: taegliches kcal-Ziel (nur informativ, aktuell ungenutzt in der Berechnung).

    Returns:
        MacroTargets mit Protein (FFM-basiert), Fett (gewichtsbasiert) und
        Kohlenhydraten (tagestyp-periodisiert) in Gramm.
    """
    protein_g = ffm_kg * PROTEIN_G_PER_KG_FFM
    fat_g = weight_kg * FAT_G_PER_KG_BODYWEIGHT
    carbs_g = weight_kg * _CARBS_G_PER_KG_BY_DAYTYPE[day_type]
    return MacroTargets(protein_g=protein_g, fat_g=fat_g, carbs_g=carbs_g)
