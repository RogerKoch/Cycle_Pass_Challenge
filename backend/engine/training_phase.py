"""Datumsgetriebene Bestimmung der aktuellen Trainingsphase.

Phasenlaengen sind aus docs/research/Trainingsplan Ausdauer.md abgeleitet (dort nur als
Wochen-Range angegeben, hier auf einen Fixwert je Phase reduziert). data-model.yaml's
`duration_weeks`-Ranges werden bewusst NICHT verwendet, da sie sich ueberlappen und keine
konsistente absolute Wochenzaehlung ergeben.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

logger = logging.getLogger(__name__)

PASSSAISON_PHASE_ID = "passsaison"

# (phase_id, Laenge in Wochen), sequenziell ab program_start_date verkettet.
PHASE_SEQUENCE: list[tuple[str, int]] = [
    ("phase0_wiedereinstieg", 2),
    ("base", 8),
    ("build1", 8),
    ("build2", 5),
    ("peak_taper", 5),
]


@dataclass
class PhaseInfo:
    """Aktuelle Trainingsphase inklusive ihres Datumsfensters."""

    phase_id: str
    phase_start: date
    phase_end: date | None  # None bei der offenen Passsaison
    day_in_phase: int  # 1-indexiert


def get_phase_boundaries(program_start_date: date) -> list[tuple[str, date, date | None]]:
    """Berechnet Start-/Enddatum jeder Phase ab dem Programmstart.

    Args:
        program_start_date: Datum, an dem Phase 0 (Wiedereinstieg) beginnt.

    Returns:
        Liste von (phase_id, start_date, end_date) in Ablaufreihenfolge.
        Der letzte Eintrag (Passsaison) hat end_date=None (offen).
    """
    boundaries: list[tuple[str, date, date | None]] = []
    current_start = program_start_date
    for phase_id, weeks in PHASE_SEQUENCE:
        current_end = current_start + timedelta(weeks=weeks) - timedelta(days=1)
        boundaries.append((phase_id, current_start, current_end))
        current_start = current_end + timedelta(days=1)
    boundaries.append((PASSSAISON_PHASE_ID, current_start, None))
    return boundaries


def get_current_phase(program_start_date: date, today: date) -> PhaseInfo:
    """Ermittelt die aktive Trainingsphase fuer ein gegebenes Datum.

    Args:
        program_start_date: Datum, an dem Phase 0 (Wiedereinstieg) beginnt.
        today: Datum, fuer das die Phase bestimmt werden soll.

    Returns:
        PhaseInfo der Phase, die `today` enthaelt. Liegt `today` vor
        program_start_date, wird Phase 0 mit day_in_phase <= 0 zurueckgegeben.
    """
    boundaries = get_phase_boundaries(program_start_date)
    if today < program_start_date:
        phase_id, start, end = boundaries[0]
        return PhaseInfo(phase_id=phase_id, phase_start=start, phase_end=end, day_in_phase=(today - start).days + 1)
    for phase_id, start, end in boundaries:
        if end is None or today <= end:
            return PhaseInfo(phase_id=phase_id, phase_start=start, phase_end=end, day_in_phase=(today - start).days + 1)
    raise AssertionError("unreachable: passsaison boundary is always open-ended")
