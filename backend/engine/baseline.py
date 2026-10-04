"""Fallback-Pattern (estimated -> measured) und abgeleitete Baseline-Werte.

Quelle: docs/data-model.yaml -> baseline_values. Schaetzwerte werden bei jedem Lesen live
berechnet, nur Messwerte werden gespeichert. Abgeleitete Felder werden nie gespeichert.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Felder, fuer die ein Messwert gespeichert werden kann (Diagnostik-Termin).
BASELINE_FIELDS: tuple[str, ...] = (
    "rmr_kcal",
    "ffm_kg",
    "bodyfat_pct",
    "skinfold_sum_mm",
    "phase_angle_deg",
    "vt1_hr",
    "vt1_watts",
    "vt2_hr",
    "vt2_watts",
    "fatmax_watts",
    "fatmax_hr",
    "mfo_g_min",
    "target_bodyfat_pct",
)

DEFAULT_TARGET_BODYFAT_PCT = 16.0  # ergibt 68 kg bei ca. 57 kg FFM (Zielgewicht)


@dataclass
class ResolvedValue:
    """Aufgeloester Wert inklusive Herkunft ('measured' | 'estimated' | None)."""

    value: float | None
    source: str | None


def resolve(measured: float | None, estimated: float | None) -> ResolvedValue:
    """Messwert hat Vorrang vor Schaetzwert.

    Args:
        measured: Messwert aus der Diagnostik, oder None.
        estimated: Schaetzwert aus den Berechnungen, oder None.

    Returns:
        ResolvedValue; value und source sind None, wenn beides fehlt.
    """
    if measured is not None:
        return ResolvedValue(value=measured, source="measured")
    if estimated is not None:
        return ResolvedValue(value=estimated, source="estimated")
    return ResolvedValue(value=None, source=None)


def calculate_rmr_ratio(rmr_kcal: float, ffm_kg: float) -> float:
    """Verhaeltnis gemessener/geschaetzter RMR zum Erwartungswert: rmr / (500 + 22 * ffm).

    Args:
        rmr_kcal: Ruheumsatz in kcal/Tag.
        ffm_kg: fettfreie Masse in kg.

    Returns:
        rmr_ratio (< 0.9 gilt ueblicherweise als unterdrueckter Stoffwechsel).
    """
    return rmr_kcal / (500 + 22 * ffm_kg)


def calculate_target_weight_kg(ffm_kg: float, target_bodyfat_pct: float) -> float:
    """Zielgewicht bei gehaltener FFM: ffm / (1 - Ziel-KFA).

    Args:
        ffm_kg: fettfreie Masse in kg.
        target_bodyfat_pct: Ziel-Koerperfett in Prozent (0-100, exklusive 100).

    Returns:
        Zielgewicht in kg.

    Raises:
        ValueError: wenn target_bodyfat_pct nicht in [0, 100) liegt.
    """
    if not 0 <= target_bodyfat_pct < 100:
        raise ValueError(f"target_bodyfat_pct muss in [0, 100) liegen, war {target_bodyfat_pct}")
    return ffm_kg / (1 - target_bodyfat_pct / 100)


def calculate_energy_availability(intake_kcal: float, training_kcal: float, ffm_kg: float) -> float:
    """Energieverfuegbarkeit in kcal pro kg FFM: (Zufuhr - Trainingsenergie) / ffm.

    Args:
        intake_kcal: Kalorienzufuhr des Tages.
        training_kcal: Energieverbrauch durch Training (Rad + Kraft).
        ffm_kg: fettfreie Masse in kg.

    Returns:
        Energy availability in kcal/kg FFM.

    Raises:
        ValueError: wenn ffm_kg null oder negativ ist.
    """
    if ffm_kg <= 0:
        raise ValueError(f"ffm_kg muss positiv sein, war {ffm_kg}")
    return (intake_kcal - training_kcal) / ffm_kg
