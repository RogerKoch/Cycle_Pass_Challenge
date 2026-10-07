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
# Alltagsfaktor auf den BMR ohne Sport (Training wird separat addiert). User-Vorgabe 2026-10-05, Werte nach
# DGE-PAL; 1.45 (Buero) ist der Wert aus ernaehrungsplan.md.
ACTIVITY_LEVELS: dict[str, tuple[str, float]] = {
    "sitzend": ("nur sitzend", 1.2),
    "buero": ("Büro", 1.45),
    "gemischt": ("gemischt sitzend/stehend", 1.65),
    "stehend": ("überwiegend stehend/gehend", 1.85),
    "schwer": ("körperlich schwer", 2.1),
}
DEFAULT_ACTIVITY_LEVEL = "buero"
NON_EXERCISE_FACTOR = ACTIVITY_LEVELS[DEFAULT_ACTIVITY_LEVEL][1]
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
    non_exercise_factor: float = NON_EXERCISE_FACTOR


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
    rmr_kcal: float | None = None,
    deficit_kcal: float | None = None,
    cycling_kcal: float | None = None,
    non_exercise_factor: float = NON_EXERCISE_FACTOR,
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
        rmr_kcal: gemessener/aufgeloester Ruheumsatz; ersetzt den Mifflin-St-Jeor-BMR, falls gesetzt.
        deficit_kcal: Defizit nach Review-Anpassungen (engine.plan_adjustments); None = Phasen-Default.
        cycling_kcal: gemessener Rad-Verbrauch (kJ bzw. Garmin, engine.imported_training); None = MET-Schaetzung.
        non_exercise_factor: Alltagsfaktor auf den BMR (siehe ACTIVITY_LEVELS).

    Returns:
        NutritionTarget mit voller Komponenten-Aufschluesselung.
    """
    bmr = rmr_kcal if rmr_kcal is not None else calculate_bmr(weight_kg, height_cm, age)
    non_exercise = calculate_non_exercise_kcal(bmr, non_exercise_factor)
    if cycling_kcal is not None:
        cycling = cycling_kcal
    else:
        cycling = calculate_cycling_kcal(cycling_hours, cycling_intensity, weight_kg)
    strength = calculate_strength_kcal(strength_sessions)
    maintenance = non_exercise + cycling + strength
    deficit = calculate_deficit_kcal(phase_id) if deficit_kcal is None else deficit_kcal
    return NutritionTarget(
        bmr_kcal=bmr,
        non_exercise_kcal=non_exercise,
        cycling_kcal=cycling,
        strength_kcal=strength,
        maintenance_kcal=maintenance,
        deficit_kcal=deficit,
        target_kcal=maintenance - deficit,
        non_exercise_factor=non_exercise_factor,
    )


def calculate_macro_targets(
    weight_kg: float,
    ffm_kg: float,
    day_type: DayType,
    target_kcal: float,
    carbs_g_per_kg: float | None = None,
    fat_g_per_kg: float | None = None,
) -> MacroTargets:
    """Berechnet Protein-, Fett- und Kohlenhydrat-Ziele in Gramm.

    Args:
        weight_kg: aktuelles Koerpergewicht.
        ffm_kg: fettfreie Masse (aus dem letzten Check-in).
        day_type: Tagestyp fuer die Kohlenhydrat-Periodisierung.
        target_kcal: taegliches kcal-Ziel (nur informativ, aktuell ungenutzt in der Berechnung).
        carbs_g_per_kg: Event-Override (Carb-Loading) statt Tagestyp-Wert.
        fat_g_per_kg: Event-Override fuer Fett (Vorabend-Mahlzeiten fettarm).

    Returns:
        MacroTargets mit Protein (FFM-basiert), Fett (gewichtsbasiert) und
        Kohlenhydraten (tagestyp-periodisiert) in Gramm.
    """
    protein_g = ffm_kg * PROTEIN_G_PER_KG_FFM
    fat_g = weight_kg * (FAT_G_PER_KG_BODYWEIGHT if fat_g_per_kg is None else fat_g_per_kg)
    carbs_g = weight_kg * (_CARBS_G_PER_KG_BY_DAYTYPE[day_type] if carbs_g_per_kg is None else carbs_g_per_kg)
    return MacroTargets(protein_g=protein_g, fat_g=fat_g, carbs_g=carbs_g)


# ---------------------------------------------------------------------------
# Tagestyp, Mahlzeitenverteilung und Fueling aus der geplanten Einheit
# Quelle: docs/research/ernaehrungsplan.md §1 (Tagestypen), §3 (Mahlzeitenstruktur), §4 (Intra-Fueling)
# ---------------------------------------------------------------------------

# Intensitaeten, die als "Intervalle"/hart gelten (Tagestyp lang/hart, Fueling 60–90 g/h)
HARD_INTENSITIES: frozenset[CyclingIntensity] = frozenset(
    {CyclingIntensity.ZUEGIG_TEMPO, CyclingIntensity.RENNEN_INTERVALLE, CyclingIntensity.SEHR_HART}
)
LONG_RIDE_MINUTES = 120  # "Langer/harter Tag: >=2 h Rad o. Intervalle"

SNACK_1_KCAL = 200.0  # Mittelwert 150–250
SNACK_2_KCAL = 250.0  # Mittelwert 200–300
# (slot, Bezeichnung, Anteil an kcal ohne Snacks bzw. None fuer Snack, Protein-Gewicht, Hinweis)
_MEAL_SLOTS: list[tuple[str, str, float | None, float, str]] = [
    ("fruehstueck", "Frühstück", 25.0, 45.0, "Grundversorgung"),
    ("snack_1", "Snack 1", None, 0.0, "Pre-Workout 30–60 min vorher (schnelle KH, wenig Fett/Ballaststoffe) oder Vormittags-Puffer"),
    ("mittag", "Mittagessen", 30.0, 47.5, "kalt oder mikrowellengeeignet"),
    ("snack_2", "Snack 2", None, 22.5, "Post-Workout direkt nach dem Training: KH + 20–25 g Protein"),
    ("abend", "Abendessen", 30.0, 50.0, "Recovery, Casein-Anteil"),
]


@dataclass
class MealSlot:
    """Richtwert fuer eine Mahlzeit."""

    slot: str
    label: str
    kcal: float
    protein_g: float
    hint: str


@dataclass
class Fueling:
    """Intra-Workout-Kohlenhydrate fuer die Radeinheit."""

    carbs_g_per_hour_min: float
    carbs_g_per_hour_max: float
    carbs_g_total_min: float
    carbs_g_total_max: float
    note: str


def derive_day_type(cycling_minutes: float, intensity: CyclingIntensity | None, strength_sessions: int) -> DayType:
    """Tagestyp nach ernaehrungsplan.md §1: Ruhetag / moderat (Kraft o. ~1 h Rad) / lang-hart (>=2 h o. Intervalle).

    Args:
        cycling_minutes: Radzeit des Tages.
        intensity: Intensitaet der Radeinheit (None ohne Rad).
        strength_sessions: Anzahl Krafteinheiten.

    Returns:
        Der DayType fuer die Kohlenhydrat-Periodisierung.
    """
    if cycling_minutes > 0 and (cycling_minutes >= LONG_RIDE_MINUTES or intensity in HARD_INTENSITIES):
        return DayType.LANGER_HARTER_TAG
    if cycling_minutes > 0 or strength_sessions > 0:
        return DayType.MODERATER_TAG
    return DayType.RUHETAG


def distribute_meals(target_kcal: float, protein_g: float) -> list[MealSlot]:
    """Verteilt kcal und Protein auf 3 Hauptmahlzeiten + 2 Snacks (ernaehrungsplan.md §3).

    Snacks erhalten feste Mittelwerte, der Rest geht im Verhaeltnis 25:30:30 an die
    Hauptmahlzeiten. Protein folgt den Richtwerten (40–50 / 45–50 / 20–25 / ~50 g),
    skaliert auf das Tagesziel.

    Args:
        target_kcal: Tagesziel kcal.
        protein_g: Tagesziel Protein.

    Returns:
        Fuenf MealSlots; Summe kcal = target_kcal, Summe Protein = protein_g.
    """
    main_kcal = max(target_kcal - SNACK_1_KCAL - SNACK_2_KCAL, 0.0)
    main_share_total = sum(share for _, _, share, _, _ in _MEAL_SLOTS if share is not None)
    protein_weight_total = sum(weight for _, _, _, weight, _ in _MEAL_SLOTS)
    snack_kcal = {"snack_1": SNACK_1_KCAL, "snack_2": SNACK_2_KCAL}
    return [
        MealSlot(
            slot=slot,
            label=label,
            kcal=main_kcal * share / main_share_total if share is not None else snack_kcal[slot],
            protein_g=protein_g * weight / protein_weight_total,
            hint=hint,
        )
        for slot, label, share, weight, hint in _MEAL_SLOTS
    ]


def intra_fueling(cycling_minutes: float, intensity: CyclingIntensity | None) -> Fueling | None:
    """Kohlenhydrate waehrend der Fahrt nach ernaehrungsplan.md §4.

    Args:
        cycling_minutes: Dauer der Radeinheit.
        intensity: Intensitaet (intensive Intervalle -> obere Stufe).

    Returns:
        Fueling, oder None ohne Radeinheit.
    """
    if cycling_minutes <= 0:
        return None
    hours = cycling_minutes / 60
    if cycling_minutes < 75:
        low, high, note = 0.0, 0.0, "Keine KH nötig, Wasser reicht."
    elif cycling_minutes > 150 or intensity in HARD_INTENSITIES:
        low, high, note = 60.0, 90.0, "2:1 Glukose:Fruktose (Gel/Getränk), ab Beginn ~alle 20 min."
    else:
        low, high, note = 30.0, 60.0, "Ab Beginn regelmässig, nicht erst bei Hunger."
    return Fueling(low, high, low * hours, high * hours, note)


def nutrition_timing_hints(has_ride: bool, has_strength: bool, weight_kg: float) -> list[str]:
    """Timing-Hinweise rund ums Training (ernaehrungsplan.md §3).

    Args:
        has_ride: Radeinheit geplant.
        has_strength: Krafteinheit geplant.
        weight_kg: aktuelles Gewicht (fuer KH nach dem Training).

    Returns:
        Hinweistexte, leer an Ruhetagen.
    """
    hints = []
    if has_ride:
        hints.append("Training vormittags: Snack 1 als Pre-Workout. Nachmittags/abends: Snack 2 direkt danach.")
        hints.append(f"Nach dem Rad: {weight_kg * 1.0:.0f}–{weight_kg * 1.2:.0f} g KH in den ersten Stunden.")
    if has_strength:
        hints.append("Nach der Krafteinheit: 20–25 g Protein innerhalb ~2 h.")
    return hints
