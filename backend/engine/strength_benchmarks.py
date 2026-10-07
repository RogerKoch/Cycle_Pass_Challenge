"""Kraft-Benchmarks: Stufe je Uebung und Meilensteine aus den Testwerten.

Quelle: docs/research/Trainingsplan Kraft.md – „Fortschrittsmessung / Meilensteine“ (Woche-0-Tests,
Meilensteine W8–W24), Uebungsbibliothek (Progressionsreihenfolgen) und Recommendations 5
(„Core-Benchmarks uebertroffen -> auf anti-rotatorische/Hollow-Body-Progression wechseln“).

Annahme: Die naechste Stufe gilt ab dem oberen Ende des Rep-Bereichs (15 saubere Wdh.); die Recherche
sagt nur „zuerst Wiederholungen steigern, dann Hebel verlaengern“.
"""

import logging
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
LEVEL_UP_REPS = 15  # Annahme: oberes Ende des Rep-Bereichs 8–15
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
            if f.name in _PAIRED:
                setattr(combined, _PAIRED[f.name], getattr(result, _PAIRED[f.name]))
    return combined


def _next_pushup_variant(variant: str, reps: int) -> str:
    keys = list(PUSHUP_VARIANTS)
    index = keys.index(variant)
    if reps >= LEVEL_UP_REPS and index < len(keys) - 1:
        index += 1
    return keys[index]


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


def milestones(current: BenchmarkResult | None) -> list[Milestone]:
    """Meilensteine W8–W24 der Kraft-Recherche mit Status aus den Testwerten."""
    c = current or BenchmarkResult(test_date=date.min)
    variants = list(PUSHUP_VARIANTS)
    standard_clean = c.pushup_variant in variants and (
        variants.index(c.pushup_variant) > variants.index("standard")
        or (c.pushup_variant == "standard" and (c.pushup_reps or 0) >= 8)
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
