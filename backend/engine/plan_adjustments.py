"""Wirkung bestaetigter Plan-Anpassungen aus dem Check-in-Review.

Anpassungen sind Zeitfenster (start..end, end=None = offen). Quellen der Regeln:
docs/research/ernaehrungsplan.md §6 (Defizit, Diaet-Pause, Erhaltung) und
docs/research/Trainingsplan Ausdauer.md §3/„Schwellen“ (Erholungswoche: Volumen -40 %,
Intensitaet kuerzer beibehalten).
"""

import logging
from dataclasses import dataclass, replace
from datetime import date

from backend.engine.cycling_sessions import DELOAD_VOLUME_FACTOR, SLOT_FTP_TEST, CyclingSession
from backend.engine.nutrition_calc import calculate_deficit_kcal

logger = logging.getLogger(__name__)

KIND_DEFICIT_DELTA = "deficit_delta"
KIND_DIET_BREAK = "diet_break"
KIND_MAINTENANCE = "maintenance"
KIND_DELOAD = "deload"
KIND_STRENGTH_REDUCED = "strength_reduced"
KIND_CORE_DAILY = "core_daily"
KINDS: tuple[str, ...] = (
    KIND_DEFICIT_DELTA,
    KIND_DIET_BREAK,
    KIND_MAINTENANCE,
    KIND_DELOAD,
    KIND_STRENGTH_REDUCED,
    KIND_CORE_DAILY,
)


@dataclass
class AdjustmentSpan:
    """Eine bestaetigte Anpassung als Zeitfenster."""

    kind: str
    start: date
    end: date | None = None
    value: float | None = None

    def covers(self, day: date) -> bool:
        """True, wenn `day` im Zeitfenster liegt."""
        return self.start <= day and (self.end is None or day <= self.end)


def active_kinds(day: date, adjustments: list[AdjustmentSpan]) -> set[str]:
    """Arten der am Tag aktiven Anpassungen."""
    return {a.kind for a in adjustments if a.covers(day)}


def effective_deficit(day: date, phase_id: str, adjustments: list[AdjustmentSpan]) -> float:
    """Kalorisches Defizit eines Tages nach allen Anpassungen.

    Args:
        day: Datum.
        phase_id: Trainingsphase des Tages (Defizit nur in base/build1).
        adjustments: alle bestaetigten Anpassungen.

    Returns:
        Phasen-Defizit plus Summe der aktiven deficit_delta-Werte, mindestens 0;
        0 waehrend Diaet-Pause oder Erhaltung.
    """
    kinds = active_kinds(day, adjustments)
    if KIND_DIET_BREAK in kinds or KIND_MAINTENANCE in kinds:
        return 0.0
    base = calculate_deficit_kcal(phase_id)
    if base == 0:
        return 0.0
    delta = sum(a.value or 0.0 for a in adjustments if a.kind == KIND_DEFICIT_DELTA and a.covers(day))
    return max(base + delta, 0.0)


def is_forced_deload(day: date, adjustments: list[AdjustmentSpan]) -> bool:
    """True, wenn fuer den Tag eine Erholungswoche bestaetigt wurde."""
    return KIND_DELOAD in active_kinds(day, adjustments)


def apply_deload(session: CyclingSession) -> CyclingSession:
    """Erholungswoche: alle Abschnitte x0,6 bei gleicher Intensitaet; der Ramp-Test bleibt.

    Args:
        session: geplante Rad-Einheit.

    Returns:
        Gekuerzte Einheit (Abschnitte gerundet, mindestens 1 min) bzw. unveraendert beim Ramp-Test.
    """
    if session.slot == SLOT_FTP_TEST:
        return session
    segments = [replace(s, minutes=max(round(s.minutes * DELOAD_VOLUME_FACTOR), 1)) for s in session.segments]
    return replace(session, segments=segments, title=f"{session.title} (Erholungswoche)")
