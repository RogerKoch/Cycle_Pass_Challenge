"""Trigger-Regeln fuer das Check-in-Review.

Quellen (Volltexte massgeblich):
- docs/research/Trainingsplan Ausdauer.md – „Schwellen, die die Empfehlung aendern“, §5, §6
- docs/research/ernaehrungsplan.md – §6 „Anpassung ueber 6 Monate“ (Regeln, Warnsignale)
- docs/research/Trainingsplan Kraft.md – „Woechentliches Signal-Monitoring“, Recommendations 5
- docs/research/Leistungsoptimale Koerperwerte fuer einen Radfahrer.md – RED-S/EA, Stopp Fettabbau

Die Recherche nennt fuer einige Aktionen keine Zahl; Annahmen sind als Konstanten markiert und in
docs/architecture.md dokumentiert. Die Regeln schlagen nur vor – angewendet wird erst nach Bestaetigung.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from backend.engine.plan_adjustments import (
    KIND_CORE_DAILY,
    KIND_DEFICIT_DELTA,
    KIND_DELOAD,
    KIND_DIET_BREAK,
    KIND_MAINTENANCE,
    KIND_STRENGTH_REDUCED,
)

logger = logging.getLogger(__name__)

SEVERITY_INFO = "info"
SEVERITY_WARN = "warn"
SEVERITY_ALERT = "alert"
_SEVERITY_ORDER = {SEVERITY_ALERT: 0, SEVERITY_WARN: 1, SEVERITY_INFO: 2}

MAX_WEIGHT_LOSS_PCT_PER_WEEK = 0.7  # Ausdauer „Schwellen“, Garthe 2011
LOSS_TREND_WINDOW_DAYS = 14  # Ernaehrung §6: „Monitoring ueber 2-Wochen-Gewichtstrend“
LOSS_TREND_MIN_SPAN_DAYS = 7
STAGNATION_WINDOW_DAYS = 28
STAGNATION_MIN_SPAN_DAYS = 14  # „stagnierendes Gewicht >2–3 Wochen“
STAGNATION_MIN_POINTS = 3
DIET_BREAK_HINT_WEEKS = 6  # „Diaet-Pausen: alle 6–10 Wochen 1–2 Wochen auf Erhaltung“
DIET_BREAK_WARN_WEEKS = 10
EA_THRESHOLD = 30.0  # kcal/kg FFM, Koerperwerte (RED-S)
EA_WINDOW_DAYS = 7
EA_MIN_DAYS = 3
SIGNAL_THRESHOLD = 2  # Problem-Score 0–3, ab „deutlich“
SIGNAL_MAX_AGE_DAYS = 10
RESTING_HR_RISE_BPM = 5  # Annahme: Recherche nennt nur „kippt mehrtaegig“
RESTING_HR_BASELINE_ENTRIES = 4
# Taegliche Wellness-Werte (intervals.icu): „kippt mehrtaegig“ = Ø der letzten 3 Tage gegen Ø der 28 Tage davor
WELLNESS_RECENT_DAYS = 3
WELLNESS_BASELINE_DAYS = 28
WELLNESS_MIN_BASELINE_DAYS = 14
HRV_DROP_PCT = 10.0  # Annahme: Recherche nennt keine Zahl
CHECKIN_INTERVAL_DAYS = 7
FTP_TEST_MISSING_WINDOW_DAYS = 14

# Annahmen fuer die Groesse der vorgeschlagenen Aktionen
DEFICIT_STEP_KCAL = -100.0  # Base 300–400 -> Build 200–300 (Ernaehrung §6)
DIET_BREAK_DAYS = 7  # „1–2 Wochen“
DELOAD_DAYS = 7
STRENGTH_ADJUST_DAYS = 28  # Kraft-Benchmarks alle 4 Wochen


@dataclass
class CheckinPoint:
    """Gewicht aus einem Check-in."""

    day: date
    weight_kg: float


@dataclass
class FtpPoint:
    """Ein FTP-Test."""

    test_id: int
    day: date
    ftp_watts: int


@dataclass
class WellnessPoint:
    """Taegliche Erholungswerte aus intervals.icu (Garmin)."""

    day: date
    resting_hr: float | None = None
    hrv: float | None = None


@dataclass
class SignalPoint:
    """Fragebogen: Problem-Scores 0–3 und optional Ruhe-HF."""

    day: date
    sleep: int
    legs: int
    hunger: int
    back: int
    effort: int
    resting_hr: int | None = None


@dataclass
class EaDay:
    """Energy Availability eines Tages (kcal/kg FFM)."""

    day: date
    ea: float


@dataclass
class Action:
    """Vorgeschlagene Anpassung; wird bei Bestaetigung als PlanAdjustment ab heute angelegt."""

    kind: str
    label: str
    value: float | None = None
    days: int | None = None  # None = offen bis zur Ruecknahme


@dataclass
class Finding:
    """Ein Befund des Reviews."""

    key: str
    trigger_id: str
    severity: str
    title: str
    detail: str
    source: str
    action: Action | None = None


@dataclass
class TriggerInputs:
    """Alle Daten, die die Regeln brauchen."""

    today: date
    checkins: list[CheckinPoint] = field(default_factory=list)
    ftp_tests: list[FtpPoint] = field(default_factory=list)
    signals: list[SignalPoint] = field(default_factory=list)
    ea_days: list[EaDay] = field(default_factory=list)
    deficit_active_today: bool = False
    deficit_streak_start: date | None = None
    target_weight_kg: float | None = None
    planned_ftp_tests: list[date] = field(default_factory=list)
    wellness: list[WellnessPoint] = field(default_factory=list)
    last_strength_benchmark: date | None = None
    benchmark_interval_weeks: int = 4


@dataclass
class WeightTrend:
    """Lineare Gewichtstendenz."""

    kg_per_week: float
    pct_per_week: float
    points: int
    span_days: int


def weight_trend(checkins: list[CheckinPoint], today: date, window_days: int) -> WeightTrend | None:
    """Gewichtstrend per linearer Regression ueber die Check-ins im Fenster.

    Args:
        checkins: Check-ins (beliebige Reihenfolge).
        today: Bezugsdatum.
        window_days: Fenster rueckwaerts ab heute.

    Returns:
        WeightTrend (negativ = Abnahme), oder None bei weniger als 2 Werten bzw. gleichem Datum.
    """
    points = sorted((c for c in checkins if today - timedelta(days=window_days) <= c.day <= today), key=lambda c: c.day)
    if len(points) < 2:
        return None
    xs = [(p.day - points[0].day).days for p in points]
    span = xs[-1]
    if span == 0:
        return None
    ys = [p.weight_kg for p in points]
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    slope_per_day = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sum((x - mean_x) ** 2 for x in xs)
    kg_per_week = slope_per_day * 7
    return WeightTrend(kg_per_week, kg_per_week / ys[-1] * 100, len(points), span)


def deficit_streak_start(today: date, deficit_active: Callable[[date], bool], max_days: int = 200) -> date | None:
    """Erster Tag der laufenden Phase mit aktivem Defizit (ohne Unterbruch bis heute).

    Args:
        today: Bezugsdatum.
        deficit_active: liefert fuer ein Datum, ob dort ein Defizit galt.
        max_days: maximale Rueckschau.

    Returns:
        Startdatum der Serie, oder None wenn heute kein Defizit gilt.
    """
    if not deficit_active(today):
        return None
    start = today
    for offset in range(1, max_days):
        day = today - timedelta(days=offset)
        if not deficit_active(day):
            break
        start = day
    return start


def average_energy_availability(ea_days: list[EaDay], today: date) -> tuple[float, int] | None:
    """Mittlere EA der letzten 7 abgeschlossenen Tage (heute ausgenommen).

    Returns:
        (Mittelwert, Anzahl Tage), oder None bei weniger als EA_MIN_DAYS Tagen.
    """
    window = [d.ea for d in ea_days if today - timedelta(days=EA_WINDOW_DAYS) <= d.day < today]
    if len(window) < EA_MIN_DAYS:
        return None
    return sum(window) / len(window), len(window)


def _deficit_action(inputs: TriggerInputs) -> Action | None:
    if not inputs.deficit_active_today:
        return None
    return Action(KIND_DEFICIT_DELTA, f"Defizit {DEFICIT_STEP_KCAL:+.0f} kcal", DEFICIT_STEP_KCAL)


def _weight_findings(inputs: TriggerInputs) -> list[Finding]:
    findings = []
    latest = max(inputs.checkins, key=lambda c: c.day) if inputs.checkins else None
    loss = weight_trend(inputs.checkins, inputs.today, LOSS_TREND_WINDOW_DAYS)
    if loss and loss.span_days >= LOSS_TREND_MIN_SPAN_DAYS and -loss.pct_per_week > MAX_WEIGHT_LOSS_PCT_PER_WEEK:
        findings.append(Finding(
            key=f"weight_loss_too_fast:{latest.day.isoformat()}",
            trigger_id="weight_loss_too_fast",
            severity=SEVERITY_WARN,
            title="Gewicht fällt zu schnell",
            detail=f"Trend {loss.kg_per_week:+.2f} kg/Woche ({loss.pct_per_week:+.2f} %/Woche), "
                   f"Grenze {MAX_WEIGHT_LOSS_PCT_PER_WEEK} %/Woche. Schneller Verlust kostet Magermasse.",
            source="Trainingsplan Ausdauer: Schwellen (Garthe 2011); Körperwerte: max. 0,5 kg/Woche",
            action=_deficit_action(inputs),
        ))
    stagnation = weight_trend(inputs.checkins, inputs.today, STAGNATION_WINDOW_DAYS)
    if (
        inputs.deficit_active_today
        and stagnation
        and stagnation.points >= STAGNATION_MIN_POINTS
        and stagnation.span_days >= STAGNATION_MIN_SPAN_DAYS
        and stagnation.kg_per_week >= 0
    ):
        findings.append(Finding(
            key=f"weight_stagnation:{latest.day.isoformat()}",
            trigger_id="weight_stagnation",
            severity=SEVERITY_WARN,
            title="Gewicht stagniert trotz Defizit",
            detail=f"Trend {stagnation.kg_per_week:+.2f} kg/Woche über {stagnation.span_days} Tage.",
            source="Ernährungsplan §6: Warnsignale (stagnierendes Gewicht >2–3 Wochen → Defizit reduzieren)",
            action=_deficit_action(inputs),
        ))
    if (
        latest is not None
        and inputs.target_weight_kg is not None
        and inputs.deficit_active_today
        and latest.weight_kg <= inputs.target_weight_kg
    ):
        findings.append(Finding(
            key=f"target_weight_reached:{latest.day.isoformat()}",
            trigger_id="target_weight_reached",
            severity=SEVERITY_INFO,
            title="Zielgewicht erreicht",
            detail=f"{latest.weight_kg:.1f} kg ≤ Ziel {inputs.target_weight_kg:.1f} kg. Auf Erhaltung umstellen, "
                   "Protein bei ~2,0 g/kg halten.",
            source="Ernährungsplan §6",
            action=Action(KIND_MAINTENANCE, "Auf Erhaltung umstellen (Defizit 0)"),
        ))
    return findings


def _diet_break_finding(inputs: TriggerInputs) -> list[Finding]:
    if inputs.deficit_streak_start is None:
        return []
    weeks = (inputs.today - inputs.deficit_streak_start).days // 7
    if weeks < DIET_BREAK_HINT_WEEKS:
        return []
    level = DIET_BREAK_WARN_WEEKS if weeks >= DIET_BREAK_WARN_WEEKS else DIET_BREAK_HINT_WEEKS
    return [Finding(
        key=f"diet_break_due:{inputs.deficit_streak_start.isoformat()}:{level}",
        trigger_id="diet_break_due",
        severity=SEVERITY_WARN if level == DIET_BREAK_WARN_WEEKS else SEVERITY_INFO,
        title="Diät-Pause fällig",
        detail=f"Defizit seit {weeks} Wochen ohne Pause. Empfohlen: alle 6–10 Wochen 1–2 Wochen Erhaltung.",
        source="Ernährungsplan §6",
        action=Action(KIND_DIET_BREAK, f"Diät-Pause {DIET_BREAK_DAYS} Tage", days=DIET_BREAK_DAYS),
    )]


def _ea_finding(inputs: TriggerInputs) -> list[Finding]:
    result = average_energy_availability(inputs.ea_days, inputs.today)
    if result is None or result[0] >= EA_THRESHOLD:
        return []
    average, days = result
    last_day = max(d.day for d in inputs.ea_days if d.day < inputs.today)
    return [Finding(
        key=f"low_energy_availability:{last_day.isoformat()}",
        trigger_id="low_energy_availability",
        severity=SEVERITY_ALERT,
        title="Energieverfügbarkeit zu tief",
        detail=f"Ø {average:.1f} kcal/kg FFM über {days} Tage (Grenze {EA_THRESHOLD:.0f}). RED-S-Risiko – mehr essen.",
        source="Körperwerte: RED-S, EA nie unter 30 kcal/kg FFM",
        action=_deficit_action(inputs),
    )]


def _ftp_findings(inputs: TriggerInputs) -> list[Finding]:
    findings = []
    tests = sorted(inputs.ftp_tests, key=lambda t: (t.day, t.test_id))
    if len(tests) >= 3:
        a, b, c = (t.ftp_watts for t in tests[-3:])
        last = tests[-1]
        if c < b < a:
            findings.append(Finding(
                key=f"ftp_declining:{last.test_id}",
                trigger_id="ftp_declining",
                severity=SEVERITY_ALERT,
                title="FTP sinkt über zwei Tests",
                detail=f"FTP {a} → {b} → {c} W. Signal für Muskelabbau bzw. Unterversorgung – Fettabbau stoppen und neu bewerten.",
                source="Körperwerte: Stopp/Neubewertung des Fettabbaus",
                action=Action(KIND_DIET_BREAK, f"Defizit {DIET_BREAK_DAYS} Tage pausieren", days=DIET_BREAK_DAYS)
                if inputs.deficit_active_today else None,
            ))
        elif c <= b <= a:
            findings.append(Finding(
                key=f"ftp_stagnation:{last.test_id}",
                trigger_id="ftp_stagnation",
                severity=SEVERITY_WARN,
                title="FTP stagniert",
                detail=f"FTP {a} → {b} → {c} W: zwei Retests ohne Fortschritt. Volumen/Recovery prüfen "
                       "(meist Unter-Erholung, nicht zu wenig Intensität).",
                source="Trainingsplan Ausdauer: Schwellen",
                action=Action(KIND_DELOAD, f"Erholungswoche ({DELOAD_DAYS} Tage)", days=DELOAD_DAYS),
            ))
    for planned in sorted(inputs.planned_ftp_tests):
        if not inputs.today - timedelta(days=FTP_TEST_MISSING_WINDOW_DAYS) <= planned < inputs.today:
            continue
        if any(t.day >= planned - timedelta(days=1) for t in tests):
            continue
        findings.append(Finding(
            key=f"ftp_test_missing:{planned.isoformat()}",
            trigger_id="ftp_test_missing",
            severity=SEVERITY_INFO,
            title="FTP-Test eintragen",
            detail=f"Ramp-Test war am {planned.strftime('%d.%m.')} geplant – Ergebnis im Dashboard erfassen, "
                   "damit Zonen und Watt stimmen.",
            source="Trainingsplan Ausdauer §6",
        ))
    return findings


def _signal_findings(inputs: TriggerInputs) -> list[Finding]:
    signals = sorted(inputs.signals, key=lambda s: s.day)
    if not signals or (inputs.today - signals[-1].day).days > SIGNAL_MAX_AGE_DAYS:
        return []
    latest = signals[-1]
    ref = latest.day.isoformat()
    findings = []

    reasons = []
    if latest.sleep >= SIGNAL_THRESHOLD:
        reasons.append("Schlaf leidet")
    if latest.effort >= SIGNAL_THRESHOLD:
        reasons.append("Anstrengung bei gleicher Leistung höher")
    previous_hr = [s.resting_hr for s in signals[:-1] if s.resting_hr is not None][-RESTING_HR_BASELINE_ENTRIES:]
    if latest.resting_hr is not None and len(previous_hr) >= 2:
        baseline = sum(previous_hr) / len(previous_hr)
        if latest.resting_hr >= baseline + RESTING_HR_RISE_BPM:
            reasons.append(f"Ruhe-HF {latest.resting_hr} statt Ø {baseline:.0f}")
    if reasons:
        findings.append(Finding(
            key=f"recovery_warning:{ref}",
            trigger_id="recovery_warning",
            severity=SEVERITY_ALERT,
            title="Erholung kippt",
            detail=", ".join(reasons) + ". Empfehlung: sofort Erholungswoche/Deload.",
            source="Trainingsplan Ausdauer: Schwellen",
            action=Action(KIND_DELOAD, f"Erholungswoche ({DELOAD_DAYS} Tage)", days=DELOAD_DAYS),
        ))
    if len(signals) >= 2 and all(s.legs >= SIGNAL_THRESHOLD for s in signals[-2:]):
        findings.append(Finding(
            key=f"legs_flat:{ref}",
            trigger_id="legs_flat",
            severity=SEVERITY_WARN,
            title="Beine chronisch platt",
            detail="Zwei Fragebögen in Folge mit platten Beinen. Kraftvolumen −20 %, Beinanteil reduzieren.",
            source="Trainingsplan Kraft: Signal-Monitoring, Recommendations 5",
            action=Action(KIND_STRENGTH_REDUCED, f"Kraft reduzieren ({STRENGTH_ADJUST_DAYS} Tage)",
                          days=STRENGTH_ADJUST_DAYS),
        ))
    if latest.back >= SIGNAL_THRESHOLD:
        findings.append(Finding(
            key=f"back_pain:{ref}",
            trigger_id="back_pain",
            severity=SEVERITY_WARN,
            title="Rücken nach langen Fahrten",
            detail="Core-Frequenz erhöhen: McGill Big 3 täglich mit der Mobility-Routine.",
            source="Trainingsplan Kraft: Signal-Monitoring",
            action=Action(KIND_CORE_DAILY, f"Core täglich ({STRENGTH_ADJUST_DAYS} Tage)", days=STRENGTH_ADJUST_DAYS),
        ))
    if latest.hunger >= SIGNAL_THRESHOLD:
        findings.append(Finding(
            key=f"constant_hunger:{ref}",
            trigger_id="constant_hunger",
            severity=SEVERITY_WARN,
            title="Dauerhunger",
            detail="Warnsignal im Defizit.",
            source="Ernährungsplan §6: Warnsignale → Defizit reduzieren",
            action=_deficit_action(inputs),
        ))
    return findings


def _recent_vs_baseline(points: list[WellnessPoint], attr: str, today: date) -> tuple[float, float] | None:
    """(Ø letzte 3 Tage, Ø der 28 Tage davor) fuer ein Wellness-Feld; None bei zu wenig Daten."""
    recent_start = today - timedelta(days=WELLNESS_RECENT_DAYS - 1)
    baseline_start = recent_start - timedelta(days=WELLNESS_BASELINE_DAYS)
    recent = [getattr(p, attr) for p in points if recent_start <= p.day <= today and getattr(p, attr) is not None]
    baseline = [
        getattr(p, attr) for p in points if baseline_start <= p.day < recent_start and getattr(p, attr) is not None
    ]
    if len(recent) < WELLNESS_RECENT_DAYS or len(baseline) < WELLNESS_MIN_BASELINE_DAYS:
        return None
    return sum(recent) / len(recent), sum(baseline) / len(baseline)


def _wellness_findings(inputs: TriggerInputs) -> list[Finding]:
    reasons = []
    hr = _recent_vs_baseline(inputs.wellness, "resting_hr", inputs.today)
    if hr and hr[0] >= hr[1] + RESTING_HR_RISE_BPM:
        reasons.append(f"Ruhe-HF Ø 3 Tage {hr[0]:.0f} statt Ø {hr[1]:.0f}")
    hrv = _recent_vs_baseline(inputs.wellness, "hrv", inputs.today)
    if hrv and hrv[0] <= hrv[1] * (1 - HRV_DROP_PCT / 100):
        reasons.append(f"HRV Ø 3 Tage {hrv[0]:.0f} statt Ø {hrv[1]:.0f}")
    if not reasons:
        return []
    return [Finding(
        # pro Kalenderwoche ein Befund, sonst kaeme er nach "Verwerfen" taeglich wieder
        key=f"recovery_warning_wellness:{(inputs.today - timedelta(days=inputs.today.weekday())).isoformat()}",
        trigger_id="recovery_warning_wellness",
        severity=SEVERITY_ALERT,
        title="Erholung kippt (Garmin)",
        detail=", ".join(reasons) + ". Empfehlung: sofort Erholungswoche/Deload.",
        source="Trainingsplan Ausdauer: Schwellen (Ruhe-HF/HRV kippt mehrtägig)",
        action=Action(KIND_DELOAD, f"Erholungswoche ({DELOAD_DAYS} Tage)", days=DELOAD_DAYS),
    )]


def _due_findings(inputs: TriggerInputs) -> list[Finding]:
    findings = []
    last_checkin = max((c.day for c in inputs.checkins), default=None)
    if last_checkin is None or (inputs.today - last_checkin).days > CHECKIN_INTERVAL_DAYS:
        findings.append(Finding(
            key=f"checkin_due:{last_checkin.isoformat() if last_checkin else 'none'}",
            trigger_id="checkin_due",
            severity=SEVERITY_INFO,
            title="Check-in fällig",
            detail="Gewicht, Körperfett und Muskelmasse von der Waage erfassen (wöchentlich).",
            source="Projekt-Brief: wöchentlicher Check-in",
        ))
    last_signal = max((s.day for s in inputs.signals), default=None)
    if last_signal is None or (inputs.today - last_signal).days > CHECKIN_INTERVAL_DAYS:
        findings.append(Finding(
            key=f"signals_due:{last_signal.isoformat() if last_signal else 'none'}",
            trigger_id="signals_due",
            severity=SEVERITY_INFO,
            title="Fragebogen fällig",
            detail="Schlaf, Beine, Hunger, Rücken, Anstrengung kurz bewerten (wöchentlich).",
            source="Check-in-Review",
        ))
    last_benchmark = inputs.last_strength_benchmark
    if last_benchmark is None or inputs.today >= last_benchmark + timedelta(weeks=inputs.benchmark_interval_weeks):
        findings.append(Finding(
            key=f"strength_benchmark_due:{last_benchmark.isoformat() if last_benchmark else 'none'}",
            trigger_id="strength_benchmark_due",
            severity=SEVERITY_INFO,
            title="Kraft-Benchmark fällig",
            detail=(
                "Plank, Side Plank, Single-Leg Glute Bridge, Liegestütze und Inverted Rows testen "
                f"(alle {inputs.benchmark_interval_weeks} Wochen) – passt die Stufen der Übungen an."
            ),
            source="Trainingsplan Kraft: Fortschrittsmessung, Recommendations 5",
        ))
    return findings


def evaluate(inputs: TriggerInputs) -> list[Finding]:
    """Wertet alle Trigger-Regeln aus.

    Args:
        inputs: Check-ins, FTP-Tests, Frageboegen, EA-Tage und Defizit-Status.

    Returns:
        Befunde, sortiert nach Schweregrad (alert, warn, info).
    """
    findings = [
        *_weight_findings(inputs),
        *_diet_break_finding(inputs),
        *_ea_finding(inputs),
        *_ftp_findings(inputs),
        *_signal_findings(inputs),
        *_wellness_findings(inputs),
        *_due_findings(inputs),
    ]
    return sorted(findings, key=lambda f: _SEVERITY_ORDER[f.severity])
