"""Trainings-Ist aus importierten Aktivitaeten (intervals.icu / Garmin).

Rad-kcal kommen aus der mechanischen Arbeit: 1 kJ ~ 1 kcal Verbrauch (Wirkungsgrad ~24 %),
konsistent mit dem Caveat in docs/research/ernaehrungsplan.md („~3,6 kcal/Watt-Stunde“).
Ohne Leistungsmesser gilt die MET-Tabelle der Recherche (moderate Intensitaet, aufs Gewicht skaliert);
Garmins Kalorienwert wird nicht verwendet, weil er ohne Leistung unplausibel tief sein kann.
Die Intensitaetsstufe (fuer Tagestyp und Fueling) wird aus dem Intensity Factor nach den
Coggan-Zonen abgeleitet (engine.cycling_zones).
"""

import logging
from dataclasses import dataclass, field
from datetime import date

from backend.engine.nutrition_calc import CyclingIntensity, calculate_cycling_kcal

logger = logging.getLogger(__name__)

STRENGTH_TYPES: frozenset[str] = frozenset({"WeightTraining"})
RUN_TYPES: frozenset[str] = frozenset({"Run", "TrailRun", "VirtualRun"})
RUN_MET = 9.8  # Laufen ~9,7 km/h (Compendium of Physical Activities); kcal = MET x kg x h
KCAL_PER_KJ = 1.0
UNPOWERED_INTENSITY = CyclingIntensity.MODERAT_BASE


@dataclass
class ActivityRecord:
    """Eine importierte Aktivitaet (Felder wie in der intervals.icu-API, Einheiten metrisch)."""

    icu_id: str
    day: date
    type: str
    name: str | None = None
    moving_seconds: int | None = None
    joules: float | None = None
    calories: float | None = None  # Garmin-Wert, nur zur Anzeige
    training_load: float | None = None
    avg_watts: float | None = None
    weighted_watts: float | None = None
    avg_hr: float | None = None
    intensity: float | None = None  # Intensity Factor in %

    @property
    def is_ride(self) -> bool:
        """Radfahrt (Ride, VirtualRide, GravelRide, MountainBikeRide, ...)."""
        return self.type.endswith("Ride")

    @property
    def is_run(self) -> bool:
        """Lauf (Run, TrailRun, VirtualRun)."""
        return self.type in RUN_TYPES

    @property
    def is_strength(self) -> bool:
        """Krafteinheit."""
        return self.type in STRENGTH_TYPES

    @property
    def kcal(self) -> float | None:
        """Gemessener Verbrauch aus kJ; None ohne Leistungsmesser."""
        if self.joules:
            return self.joules / 1000 * KCAL_PER_KJ
        return None


@dataclass
class ImportedDay:
    """Zusammenfassung der importierten Aktivitaeten eines Tages."""

    endurance_minutes: float = 0.0
    endurance_kcal: float | None = None  # None nur, wenn ohne Gewicht Fahrten ohne Leistung oder Laeufe dabei sind
    endurance_intensity: CyclingIntensity | None = None
    strength_done: bool = False
    activities: list[ActivityRecord] = field(default_factory=list)

    @property
    def has_training(self) -> bool:
        """True, wenn eine Fahrt, ein Lauf oder eine Krafteinheit importiert ist."""
        return self.endurance_minutes > 0 or self.strength_done


def intensity_from_if(intensity_pct: float | None) -> CyclingIntensity:
    """Intensitaetsstufe aus dem Intensity Factor (%), Grenzen wie die Coggan-Zonen; ohne Leistung moderat."""
    if intensity_pct is None:
        return UNPOWERED_INTENSITY
    if intensity_pct < 56:  # Z1
        return CyclingIntensity.LEICHT_REKOM
    if intensity_pct < 76:  # Z2
        return CyclingIntensity.MODERAT_BASE
    if intensity_pct < 88:  # Z3
        return CyclingIntensity.ZUEGIG_TEMPO
    if intensity_pct <= 105:  # Sweet Spot / Schwelle
        return CyclingIntensity.RENNEN_INTERVALLE
    return CyclingIntensity.SEHR_HART


def activity_kcal(activity: ActivityRecord, weight_kg: float | None) -> float | None:
    """Verbrauch einer Fahrt (kJ, sonst MET-Schaetzung) oder eines Laufs (MET); braucht ohne kJ das Gewicht."""
    if activity.is_run:
        if weight_kg is None or not activity.moving_seconds:
            return None
        return RUN_MET * weight_kg * activity.moving_seconds / 3600
    if activity.kcal is not None:
        return activity.kcal
    if weight_kg is None or not activity.moving_seconds:
        return None
    return calculate_cycling_kcal(activity.moving_seconds / 3600, UNPOWERED_INTENSITY, weight_kg)


def summarize_day(activities: list[ActivityRecord], weight_kg: float | None = None) -> ImportedDay:
    """Fasst die Aktivitaeten eines Tages zusammen.

    Args:
        activities: importierte Aktivitaeten desselben Tages.
        weight_kg: aktuelles Gewicht fuer die MET-Schaetzung von Fahrten ohne Leistungsmesser und von Laeufen.

    Returns:
        ImportedDay mit Ausdauer-Minuten (Rad und Lauf), Ausdauer-kcal (pro Fahrt kJ oder MET, pro Lauf MET;
        None nur ohne Gewicht bei Fahrten ohne Leistung oder Laeufen), zeitgewichteter Intensitaet und Kraft ja/nein.
    """
    rides = [a for a in activities if (a.is_ride or a.is_run) and (a.moving_seconds or 0) > 0]
    minutes = sum(a.moving_seconds for a in rides) / 60
    intensity = None
    if rides:
        powered = [a for a in rides if a.intensity is not None]
        if powered:
            weighted = sum(a.intensity * a.moving_seconds for a in powered) / sum(a.moving_seconds for a in powered)
            intensity = intensity_from_if(weighted)
        else:
            intensity = UNPOWERED_INTENSITY
    per_ride = [activity_kcal(a, weight_kg) for a in rides]
    return ImportedDay(
        endurance_minutes=minutes,
        endurance_kcal=sum(per_ride) if rides and None not in per_ride else None,
        endurance_intensity=intensity,
        strength_done=any(a.is_strength for a in activities),
        activities=list(activities),
    )
