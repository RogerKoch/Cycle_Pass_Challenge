"""Trainings-Ist aus importierten Aktivitaeten (intervals.icu / Garmin).

Rad-kcal kommen aus der mechanischen Arbeit: 1 kJ ~ 1 kcal Verbrauch (Wirkungsgrad ~24 %),
konsistent mit dem Caveat in docs/research/ernaehrungsplan.md („~3,6 kcal/Watt-Stunde“).
Ohne Leistungsmesser gilt Garmins Kalorienwert. Die Intensitaetsstufe (fuer Tagestyp und Fueling)
wird aus dem Intensity Factor nach den Coggan-Zonen abgeleitet (engine.cycling_zones).
"""

import logging
from dataclasses import dataclass, field
from datetime import date

from backend.engine.nutrition_calc import CyclingIntensity

logger = logging.getLogger(__name__)

STRENGTH_TYPES: frozenset[str] = frozenset({"WeightTraining"})
KCAL_PER_KJ = 1.0


@dataclass
class ActivityRecord:
    """Eine importierte Aktivitaet (Felder wie in der intervals.icu-API, Einheiten metrisch)."""

    icu_id: str
    day: date
    type: str
    name: str | None = None
    moving_seconds: int | None = None
    joules: float | None = None
    calories: float | None = None
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
    def is_strength(self) -> bool:
        """Krafteinheit."""
        return self.type in STRENGTH_TYPES

    @property
    def kcal(self) -> float | None:
        """Verbrauch: aus kJ, sonst Garmin-Kalorien."""
        if self.joules:
            return self.joules / 1000 * KCAL_PER_KJ
        return self.calories


@dataclass
class ImportedDay:
    """Zusammenfassung der importierten Aktivitaeten eines Tages."""

    ride_minutes: float = 0.0
    ride_kcal: float | None = None  # None, wenn eine Fahrt weder kJ noch kcal hat -> MET-Schaetzung
    ride_intensity: CyclingIntensity | None = None
    strength_done: bool = False
    activities: list[ActivityRecord] = field(default_factory=list)

    @property
    def has_training(self) -> bool:
        """True, wenn eine Fahrt oder Krafteinheit importiert ist."""
        return self.ride_minutes > 0 or self.strength_done


def intensity_from_if(intensity_pct: float | None) -> CyclingIntensity:
    """Intensitaetsstufe aus dem Intensity Factor (%), Grenzen wie die Coggan-Zonen; ohne Leistung moderat."""
    if intensity_pct is None:
        return CyclingIntensity.MODERAT_BASE
    if intensity_pct < 56:  # Z1
        return CyclingIntensity.LEICHT_REKOM
    if intensity_pct < 76:  # Z2
        return CyclingIntensity.MODERAT_BASE
    if intensity_pct < 88:  # Z3
        return CyclingIntensity.ZUEGIG_TEMPO
    if intensity_pct <= 105:  # Sweet Spot / Schwelle
        return CyclingIntensity.RENNEN_INTERVALLE
    return CyclingIntensity.SEHR_HART


def summarize_day(activities: list[ActivityRecord]) -> ImportedDay:
    """Fasst die Aktivitaeten eines Tages zusammen.

    Args:
        activities: importierte Aktivitaeten desselben Tages.

    Returns:
        ImportedDay mit Rad-Minuten, Rad-kcal (None, wenn einer Fahrt kJ und kcal fehlen),
        zeitgewichteter Intensitaet und Kraft ja/nein.
    """
    rides = [a for a in activities if a.is_ride and (a.moving_seconds or 0) > 0]
    minutes = sum(a.moving_seconds for a in rides) / 60
    intensity = None
    if rides:
        powered = [a for a in rides if a.intensity is not None]
        if powered:
            weighted = sum(a.intensity * a.moving_seconds for a in powered) / sum(a.moving_seconds for a in powered)
            intensity = intensity_from_if(weighted)
        else:
            intensity = CyclingIntensity.MODERAT_BASE
    return ImportedDay(
        ride_minutes=minutes,
        ride_kcal=sum(a.kcal for a in rides) if rides and all(a.kcal is not None for a in rides) else None,
        ride_intensity=intensity,
        strength_done=any(a.is_strength for a in activities),
        activities=list(activities),
    )
