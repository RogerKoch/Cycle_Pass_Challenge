"""Standardwoche, Phasen-Woche und Kopplungsregeln zwischen Rad und Kraft.

Quellen: docs/research/Trainingsplan Ausdauer.md §2 (Wochengeruest) und `sync_rules` in
docs/data-model.yaml. Die Kraft-Recherche empfiehlt alternativ Kraft am harten Radtag abends;
umgesetzt ist das Mo/Do-Muster der Ausdauer-Recherche (siehe docs/architecture.md, Offene Punkte).
"""

import logging
from dataclasses import dataclass, replace
from datetime import date, timedelta

from backend.engine.cycling_sessions import (
    KEY_SLOTS,
    PEAK_SPECIFIC_WEEKS,
    RETEST_WEEKS,
    SLOT_FTP_TEST,
    SLOT_KEY_1,
    SLOT_KEY_2,
    SLOT_LONG,
    SLOT_REKOM,
    SLOT_Z2,
    SLOT_Z2_OR_REKOM,
    build_cycling_session,
)
from backend.engine.strength_sessions import (
    FOCUS_EXTRA_MINUTES,
    FOCUS_NONE,
    GROUP_LEGS,
    STRENGTH_FOCUSES,
    StrengthSession,
    build_strength_session,
    shift_numbers,
    strength_phase_for,
)
from backend.engine.training_phase import PhaseInfo, get_current_phase

logger = logging.getLogger(__name__)

STATUS_PLANNED = "planned"
STATUS_DONE = "done"
STATUS_MODIFIED = "modified"
STATUS_SKIPPED = "skipped"

# Bein-Fokus pausiert, wenn Radleistung Vorrang hat (Kraft-Recherche: "Beine schonen")
LEG_FOCUS_PAUSED_PHASES: frozenset[str] = frozenset({"peak_taper", "passsaison"})
STATUSES: tuple[str, ...] = (STATUS_PLANNED, STATUS_DONE, STATUS_MODIFIED, STATUS_SKIPPED)

# Wochentag (0 = Montag) -> (Rad-Slot, Krafteinheit)
STANDARD_WEEK: dict[int, tuple[str | None, str | None]] = {
    0: (SLOT_REKOM, "A"),
    1: (SLOT_KEY_1, None),
    2: (SLOT_Z2, None),
    3: (SLOT_Z2_OR_REKOM, "B"),
    4: (None, None),  # kompletter Ruhetag
    5: (SLOT_KEY_2, None),
    6: (SLOT_LONG, None),
}
# Ab Build 2 nur noch 1 Krafteinheit pro Woche (Montag), A/B im Wochenwechsel
TWO_STRENGTH_SESSION_PHASES: frozenset[str] = frozenset({"phase0_wiedereinstieg", "base", "build1"})

MSG_CONSECUTIVE_HARD = "Zwei harte Schlüsseleinheiten an aufeinanderfolgenden Tagen (mind. 48 h Abstand)."
MSG_NO_REST_DAY = "Kein kompletter Ruhetag mehr in dieser Woche."
MSG_STRENGTH_SAME_DAY = "Kraft und Schlüsseleinheit am selben Tag: zuerst Rad, Kraft mit ≥6 h Abstand."


@dataclass
class DayPlan:
    """Minimale Sicht auf einen Kalendertag fuer die Regelpruefung."""

    day: date
    cycling_slot: str | None
    strength_session: str | None
    status: str = STATUS_PLANNED


@dataclass
class Violation:
    """Regelverstoss; blocking=False ist nur ein Hinweis."""

    day: date
    message: str
    blocking: bool


def week_start(day: date) -> date:
    """Montag der Kalenderwoche von `day`."""
    return day - timedelta(days=day.weekday())


def phase_week(program_start_date: date, day: date) -> tuple[PhaseInfo, int]:
    """Phase und 1-indexierte Woche innerhalb der Phase fuer ein Datum.

    Args:
        program_start_date: Programmstart (Beginn Phase 0).
        day: Datum.

    Returns:
        (PhaseInfo, week_in_phase); vor dem Programmstart ist week_in_phase 1.
    """
    phase = get_current_phase(program_start_date, day)
    return phase, max((day - phase.phase_start).days // 7 + 1, 1)


def default_day_plan(program_start_date: date, day: date) -> tuple[str | None, str | None]:
    """Rad-Slot und Krafteinheit der Standardwoche fuer ein Datum.

    Args:
        program_start_date: Programmstart.
        day: Datum.

    Returns:
        (cycling_slot, strength_session). Vor dem Programmstart (None, None). Der Slot ist None,
        wenn die Phase dafuer keine Radeinheit vorsieht.
    """
    if day < program_start_date:
        return None, None
    phase, week = phase_week(program_start_date, day)
    slot, strength = STANDARD_WEEK[day.weekday()]
    if slot == SLOT_KEY_2 and (phase.phase_id, week) in RETEST_WEEKS:
        slot = SLOT_FTP_TEST
    if slot is not None and build_cycling_session(slot, phase.phase_id, week) is None:
        slot = None
    if phase.phase_id not in TWO_STRENGTH_SESSION_PHASES:
        strength = ("A" if week % 2 == 1 else "B") if day.weekday() == 0 else None
    return slot, strength


def resolve_strength(
    session_id: str, phase_id: str, week_in_phase: int, reduced: bool = False, focus: str = FOCUS_NONE
) -> StrengthSession:
    """Krafteinheit fuer Phase und Woche, im Taper mit Reduktionshinweis.

    Der Bein-Fokus pausiert in Peak/Taper/Passsaison und bei reduzierter Kraft (Kraft-Recherche:
    "Beine schonen" – Beinarbeit darf das Radtraining nicht beeintraechtigen).

    Args:
        session_id: "A" oder "B".
        phase_id: Trainingsphase.
        week_in_phase: Woche in der Phase.
        reduced: reduzierte Einheit aus dem Check-in-Review (Beine platt).
        focus: Kraft-Fokus aus dem Profil.

    Returns:
        StrengthSession der zugehoerigen Kraftphase.
    """
    notes = []
    if phase_id == "peak_taper" and week_in_phase > PEAK_SPECIFIC_WEEKS:
        notes.append("Taper: Erhalt, reduziert auf ~40 min.")
    taper = bool(notes)
    if focus == GROUP_LEGS and (reduced or phase_id in LEG_FOCUS_PAUSED_PHASES):
        notes.append("Bein-Fokus pausiert (Beine schonen fürs Radtraining).")
        focus = FOCUS_NONE
    session = build_strength_session(session_id, strength_phase_for(phase_id), " ".join(notes) or None, reduced, focus)
    if not taper:
        return session
    extra = FOCUS_EXTRA_MINUTES if session.focus in STRENGTH_FOCUSES else 0
    return replace(session, duration_minutes=shift_numbers("40", extra))


def _is_hard(day: DayPlan) -> bool:
    return day.status != STATUS_SKIPPED and day.cycling_slot in KEY_SLOTS


def _is_rest(day: DayPlan) -> bool:
    return day.status == STATUS_SKIPPED or (day.cycling_slot is None and day.strength_session is None)


def validate_week(days: list[DayPlan]) -> list[Violation]:
    """Prueft die Kopplungsregeln einer Woche.

    Blockierend: zwei harte Schluesseleinheiten an aufeinanderfolgenden Tagen; kein kompletter
    Ruhetag. Hinweis: Kraft und Schluesseleinheit am selben Tag (>=6 h Abstand).

    Args:
        days: Tage einer Kalenderwoche (beliebige Reihenfolge).

    Returns:
        Liste der Verstoesse, leer wenn alles passt.
    """
    ordered = sorted(days, key=lambda d: d.day)
    violations: list[Violation] = []
    for previous, current in zip(ordered, ordered[1:]):
        if (current.day - previous.day).days == 1 and _is_hard(previous) and _is_hard(current):
            violations.append(Violation(current.day, MSG_CONSECUTIVE_HARD, blocking=True))
    if ordered and not any(_is_rest(d) for d in ordered):
        violations.append(Violation(ordered[0].day, MSG_NO_REST_DAY, blocking=True))
    for d in ordered:
        if _is_hard(d) and d.strength_session is not None:
            violations.append(Violation(d.day, MSG_STRENGTH_SAME_DAY, blocking=False))
    return violations


def swap_plans(days: list[DayPlan], day_a: date, day_b: date) -> list[DayPlan]:
    """Tauscht die geplanten Inhalte (Slot und Kraft) zweier Tage; der Status bleibt beim Datum."""
    by_day = {d.day: d for d in days}
    a, b = by_day[day_a], by_day[day_b]
    swapped = {
        day_a: replace(a, cycling_slot=b.cycling_slot, strength_session=b.strength_session),
        day_b: replace(b, cycling_slot=a.cycling_slot, strength_session=a.strength_session),
    }
    return [swapped.get(d.day, d) for d in days]


def has_blocking(violations: list[Violation]) -> bool:
    """True, wenn mindestens ein Verstoss blockierend ist."""
    return any(v.blocking for v in violations)


def suggest_reschedule(days: list[DayPlan], cancelled: date, today: date) -> list[date]:
    """Ersatztage fuer eine abgesagte Schluesseleinheit innerhalb derselben Woche.

    Kandidaten sind geplante Tage ab heute ohne eigene Schluesseleinheit, bei denen der Tausch
    keinen blockierenden Regelverstoss erzeugt.

    Args:
        days: Tage der Woche (der abgesagte Tag mit Status skipped).
        cancelled: Datum der abgesagten Einheit.
        today: heutiges Datum.

    Returns:
        Moegliche Ersatzdaten, aufsteigend. Leer, wenn der Tag keine Schluesseleinheit hat.
    """
    by_day = {d.day: d for d in days}
    if by_day[cancelled].cycling_slot not in KEY_SLOTS:
        return []
    candidates = []
    for d in sorted(days, key=lambda x: x.day):
        if d.day == cancelled or d.day < today or d.status != STATUS_PLANNED or d.cycling_slot in KEY_SLOTS:
            continue
        if not has_blocking(validate_week(swap_plans(days, cancelled, d.day))):
            candidates.append(d.day)
    return candidates
