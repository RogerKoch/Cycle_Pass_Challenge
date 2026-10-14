"""Kraft-Benchmarks: Stufe je Uebung und Meilensteine aus den Testwerten.

Quelle: docs/research/Trainingsplan Kraft.md – „Fortschrittsmessung / Meilensteine“ (Woche-0-Tests,
Meilensteine W8–W24), Uebungsbibliothek (Progressionsreihenfolgen) und Recommendations 5
(„Core-Benchmarks uebertroffen -> auf anti-rotatorische/Hollow-Body-Progression wechseln“).

Progression (docs/research/Kraftprogression-Ergaenzung.md): naechste Stufe bei 12 sauberen Wdh. (Coach-Regel
3 x 12), ab 20 Wdh. zwei Stufen; am Ende der Leiter Tempo 3 s exzentrisch statt Zusatzlast; Ziel des naechsten
Tests = Testwert + 10 % (ACSM: 2-10 %).
"""

import logging
import math
from dataclasses import dataclass, fields
from datetime import date, timedelta

logger = logging.getLogger(__name__)

PUSHUP_VARIANTS: dict[str, str] = {
    "wand": "Wand",
    "inkline": "Inkline",
    "knie": "Knie",
    "standard": "Standard",
    "fuesse_erhoeht": "Füsse erhöht",
    "deficit": "Deficit",
}
LEVEL_UP_REPS = 12  # 3 x 12 saubere Wdh. -> naechste Stufe (Coach-Regel, siehe Kraftprogression-Ergaenzung.md)
TWO_STAGE_REPS = 20  # ab hier ueberspringt der Liegestuetz eine Stufe (Plateau bei 20–25 Wdh.)
TARGET_GROWTH = 1.10  # Ziel des naechsten Tests: +10 % (mind. +1)
NEW_STAGE_REPS = "8–12"  # Wdh., die in einer neuen Stufe zuerst aufgebaut werden
SIDE_PLANK_STRAIGHT_FROM_S = 20  # Seitstuetz: Anfang 10–20 s mit gebeugten Knien, dann gestreckt
SIDE_PLANK_TARGET_S = 30  # Meilenstein W12: Side Plank gestreckt 30 s
SL_BRIDGE_TARGET_S = 60  # Benchmark: Single-Leg Glute Bridge 60 s je Bein
PLANK_TARGET_S = 120  # Meilenstein W20: Plank 2 min (Ziel langfristig 2–3 min)

DEFAULT_INTERVAL_WEEKS = 4  # „Miss Fortschritt an den Woche-0-Benchmarks alle 4 Wochen“
MIN_INTERVAL_WEEKS = 2
MAX_INTERVAL_WEEKS = 8


@dataclass
class BenchmarkResult:
    """Testwerte eines Benchmark-Termins; None = nicht getestet."""

    test_date: date
    pushup_reps: int | None = None
    pushup_variant: str | None = None
    row_reps: int | None = None
    side_plank_s: int | None = None
    side_plank_straight: bool | None = None
    sl_bridge_s: int | None = None  # schwaechere Seite
    plank_s: int | None = None


@dataclass
class ExerciseStages:
    """Abgeleitete Stufen; None = noch nicht getestet (Uebung bleibt wie geplant)."""

    pushup_variant: str | None = None
    rows_feet_elevated: bool | None = None
    side_plank_straight: bool | None = None
    glute_bridge_single_leg: bool | None = None
    core_advanced: bool = False  # Hollow Body/Pallof vor ihrer Phase freischalten
    pushup_slow_tempo: bool = False  # Liegestuetz-Leiter ausgereizt: Tempo 3 s exzentrisch statt Zusatzlast


@dataclass
class Milestone:
    """Meilenstein der Recherche; achieved = None, wenn nicht aus den Tests messbar."""

    week: int
    text: str
    achieved: bool | None


# Testpaare, die zusammengehoeren und deshalb nur gemeinsam uebernommen werden
_PAIRED = {"pushup_reps": "pushup_variant", "side_plank_s": "side_plank_straight"}


def combine(results: list[BenchmarkResult]) -> BenchmarkResult | None:
    """Neuester Wert je Test ueber alle Termine (Teiltests erlaubt).

    Args:
        results: Benchmark-Termine in beliebiger Reihenfolge.

    Returns:
        Kombiniertes Ergebnis (test_date = neuester Termin) oder None ohne Tests.
    """
    if not results:
        return None
    ordered = sorted(results, key=lambda r: r.test_date)
    combined = BenchmarkResult(test_date=ordered[-1].test_date)
    paired_values = set(_PAIRED.values())
    for result in ordered:
        for f in fields(BenchmarkResult):
            if f.name == "test_date" or f.name in paired_values:
                continue
            value = getattr(result, f.name)
            if value is None:
                continue
            setattr(combined, f.name, value)
            partner = _PAIRED.get(f.name)
            if partner and getattr(result, partner) is not None:
                setattr(combined, partner, getattr(result, partner))
    return combined


def _next_pushup_variant(variant: str, reps: int) -> str:
    keys = list(PUSHUP_VARIANTS)
    index = keys.index(variant)
    steps = 2 if reps >= TWO_STAGE_REPS else 1 if reps >= LEVEL_UP_REPS else 0
    return keys[min(index + steps, len(keys) - 1)]


def exercise_stages(current: BenchmarkResult | None) -> ExerciseStages:
    """Leitet die Stufe je Uebung aus den neuesten Testwerten ab.

    Args:
        current: kombinierte Testwerte (siehe combine) oder None.

    Returns:
        ExerciseStages; ungetestete Uebungen bleiben None.
    """
    if current is None:
        return ExerciseStages()
    stages = ExerciseStages()
    if current.pushup_reps is not None and current.pushup_variant in PUSHUP_VARIANTS:
        stages.pushup_variant = _next_pushup_variant(current.pushup_variant, current.pushup_reps)
        stages.pushup_slow_tempo = (
            current.pushup_variant == list(PUSHUP_VARIANTS)[-1] and current.pushup_reps >= TWO_STAGE_REPS
        )
    if current.row_reps is not None:
        stages.rows_feet_elevated = current.row_reps >= LEVEL_UP_REPS
    if current.side_plank_s is not None:
        stages.side_plank_straight = bool(current.side_plank_straight) or (
            current.side_plank_s >= SIDE_PLANK_STRAIGHT_FROM_S
        )
    if current.sl_bridge_s is not None:
        stages.glute_bridge_single_leg = current.sl_bridge_s >= SL_BRIDGE_TARGET_S
    stages.core_advanced = (
        (current.plank_s or 0) >= PLANK_TARGET_S
        and bool(current.side_plank_straight)
        and (current.side_plank_s or 0) >= SIDE_PLANK_TARGET_S
    )
    return stages


def _grow(value: int, cap: int | None = None) -> int:
    """Ziel des naechsten Tests: Wert + 10 % (mind. +1), hoechstens `cap`."""
    target = max(value + 1, math.ceil(value * TARGET_GROWTH))
    return min(target, cap) if cap is not None else target


def next_targets(current: BenchmarkResult | None) -> list[str]:
    """Ziel je getesteter Uebung fuer den naechsten Benchmark-Termin (Anzeige).

    Args:
        current: kombinierte Testwerte (siehe combine) oder None.

    Returns:
        Zeilen wie "Liegestütz (Knie): 10 Wdh., ab 12 nächste Stufe"; leer ohne Tests.
    """
    if current is None:
        return []
    targets: list[str] = []
    if current.pushup_reps is not None and current.pushup_variant in PUSHUP_VARIANTS:
        label = PUSHUP_VARIANTS[current.pushup_variant]
        stage = exercise_stages(current)
        if stage.pushup_variant != current.pushup_variant:
            targets.append(
                f"Liegestütz: Stufe {PUSHUP_VARIANTS[stage.pushup_variant]}, dort zuerst {NEW_STAGE_REPS} Wdh. aufbauen"
            )
        elif stage.pushup_slow_tempo:
            targets.append(f"Liegestütz ({label}): Tempo 3 s runter, {_grow(current.pushup_reps)} Wdh.")
        else:
            targets.append(
                f"Liegestütz ({label}): {_grow(current.pushup_reps)} Wdh., ab {LEVEL_UP_REPS} nächste Stufe"
            )
    if current.row_reps is not None:
        if current.row_reps >= LEVEL_UP_REPS:
            targets.append(f"Inverted Rows: Füsse erhöht, dort zuerst {NEW_STAGE_REPS} Wdh. aufbauen")
        else:
            targets.append(f"Inverted Rows: {_grow(current.row_reps)} Wdh., ab {LEVEL_UP_REPS} Füsse erhöht")
    if current.side_plank_s is not None:
        if bool(current.side_plank_straight) and current.side_plank_s >= SIDE_PLANK_TARGET_S:
            targets.append(f"Side Plank: Ziel {SIDE_PLANK_TARGET_S} s gestreckt erreicht")
        elif not current.side_plank_straight and current.side_plank_s >= SIDE_PLANK_STRAIGHT_FROM_S:
            targets.append("Side Plank: Beine gestreckt, dort zuerst 15–20 s aufbauen")
        else:
            cap = SIDE_PLANK_TARGET_S if current.side_plank_straight else SIDE_PLANK_STRAIGHT_FROM_S
            targets.append(f"Side Plank: {_grow(current.side_plank_s, cap)} s")
    if current.sl_bridge_s is not None:
        targets.append(
            f"Single-Leg Glute Bridge: Ziel {SL_BRIDGE_TARGET_S} s erreicht" if current.sl_bridge_s >= SL_BRIDGE_TARGET_S
            else f"Single-Leg Glute Bridge: {_grow(current.sl_bridge_s, SL_BRIDGE_TARGET_S)} s je Bein"
        )
    if current.plank_s is not None:
        targets.append(
            f"Plank: Ziel {PLANK_TARGET_S} s erreicht" if current.plank_s >= PLANK_TARGET_S
            else f"Plank: {_grow(current.plank_s, PLANK_TARGET_S)} s"
        )
    return targets


def milestones(current: BenchmarkResult | None) -> list[Milestone]:
    """Meilensteine W8–W24 der Kraft-Recherche mit Status aus den Testwerten."""
    c = current or BenchmarkResult(test_date=date.min)
    variants = list(PUSHUP_VARIANTS)
    standard_clean = c.pushup_variant in variants and (
        variants.index(c.pushup_variant) >= variants.index("standard") and (c.pushup_reps or 0) >= 8
    )

    def measured(*values: object) -> bool:
        return all(v is not None for v in values)

    return [
        Milestone(8, "Standard-Liegestütz sauber", standard_clean if measured(c.pushup_reps) else None),
        Milestone(12, f"Single-Leg Glute Bridge {SL_BRIDGE_TARGET_S} s je Bein",
                  c.sl_bridge_s >= SL_BRIDGE_TARGET_S if measured(c.sl_bridge_s) else None),
        Milestone(12, f"Side Plank gestreckt {SIDE_PLANK_TARGET_S} s",
                  bool(c.side_plank_straight) and c.side_plank_s >= SIDE_PLANK_TARGET_S
                  if measured(c.side_plank_s) else None),
        Milestone(16, "Bulgarian Split Squat 3× 10 sauber", None),
        Milestone(20, f"Plank {PLANK_TARGET_S // 60} min", c.plank_s >= PLANK_TARGET_S if measured(c.plank_s) else None),
        Milestone(24, "Re-Test aller Baseline-Werte", None),
    ]


def next_due(last_test: date | None, interval_weeks: int, today: date) -> date:
    """Naechster Benchmark-Termin; ohne Test sofort (Woche-0-Baseline)."""
    if last_test is None:
        return today
    return last_test + timedelta(weeks=interval_weeks)
