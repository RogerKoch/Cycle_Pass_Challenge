"""Rad-Einheiten je Phase, Wochentags-Slot und Woche in der Phase.

Quelle: docs/research/Trainingsplan Ausdauer.md, §2 (Wochengeruest), §3 (Beispielwochen und
Progressionen je Phase) und §4 (Passsaison). Wo die Recherche eine Progression nur als
Start -> Ziel angibt (z. B. Sweet Spot 3x10 -> 3x12 -> 2x20), ist die Verteilung auf die
Wochen hier eine Annahme.

Die Intensitaet (`CyclingIntensity`) ist pro Einheit explizit gesetzt und speist die
MET-basierte kcal-Berechnung in engine.nutrition_calc.
"""

import logging
import math
from dataclasses import dataclass, field, replace

from backend.engine.nutrition_calc import CyclingIntensity

logger = logging.getLogger(__name__)

# Slots der Standardwoche (siehe engine.week_plan.STANDARD_WEEK)
SLOT_REKOM = "rekom"
SLOT_KEY_1 = "schluessel_1"
SLOT_Z2 = "z2_grundlage"
SLOT_Z2_OR_REKOM = "z2_oder_rekom"
SLOT_KEY_2 = "schluessel_2"
SLOT_LONG = "lang"
SLOT_FTP_TEST = "ftp_test"  # Ramp-Test, in Retest-Wochen statt schluessel_2

ALL_SLOTS: tuple[str, ...] = (SLOT_REKOM, SLOT_KEY_1, SLOT_Z2, SLOT_Z2_OR_REKOM, SLOT_KEY_2, SLOT_LONG, SLOT_FTP_TEST)
KEY_SLOTS: frozenset[str] = frozenset({SLOT_KEY_1, SLOT_KEY_2, SLOT_FTP_TEST})
# Nur bei diesen Slots darf die Dauer angepasst werden (Intervallstruktur der Schluesseleinheiten bleibt fix)
ENDURANCE_SLOTS: frozenset[str] = frozenset({SLOT_REKOM, SLOT_Z2, SLOT_Z2_OR_REKOM, SLOT_LONG})

BUILD1_DELOAD_EVERY_WEEKS = 3  # "Erholungswoche alle 3. Woche: Volumen -40 %"
DELOAD_VOLUME_FACTOR = 0.6
PEAK_SPECIFIC_WEEKS = 3  # danach Taper (peak_taper hat 5 Wochen, siehe engine.training_phase)
# FTP-Retest alle 6–8 Wochen (§6): Ende Base, "Mitte Build" (Build 1 W6, 6 Wochen nach Ende Base),
# Ende Build 2 = "vor Peak" (beide Termine liegen direkt hintereinander und sind zusammengelegt).
# Dazu der erste Test am Ende von Phase 0, Woche 1.
RETEST_WEEKS: frozenset[tuple[str, int]] = frozenset(
    {("phase0_wiedereinstieg", 1), ("base", 8), ("build1", 6), ("build2", 5)}
)

FTP_MISSING_MESSAGE = "Noch kein FTP-Test erfasst – Vorgaben in % FTP statt Watt."


@dataclass
class Segment:
    """Ein Abschnitt einer Einheit. pct_ftp_* = None bei Abschnitten ohne Leistungsvorgabe (Ramp-Test)."""

    minutes: float
    pct_ftp_low: float | None
    pct_ftp_high: float | None
    label: str
    cadence_rpm: str | None = None
    filler: bool = False  # Grundlagen-Abschnitt, der bei Dauer-Anpassung skaliert wird


@dataclass
class CyclingSession:
    """Eine Rad-Einheit mit Abschnitten und kcal-relevanter Intensitaet."""

    slot: str
    title: str
    segments: list[Segment]
    intensity: CyclingIntensity
    zwift_hint: str | None = None
    note: str | None = None
    adjusted: bool = False

    @property
    def minutes(self) -> float:
        """Gesamtdauer in Minuten."""
        return sum(s.minutes for s in self.segments)

    @property
    def is_key(self) -> bool:
        """True fuer harte Schluesseleinheiten (Regelpruefung in engine.week_plan)."""
        return self.slot in KEY_SLOTS


@dataclass
class SegmentWatts:
    """Abschnitt mit aufgeloesten Watt-Werten (None ohne FTP oder ohne Leistungsvorgabe)."""

    minutes: float
    label: str
    pct_ftp_low: float | None
    pct_ftp_high: float | None
    watts_low: int | None
    watts_high: int | None
    cadence_rpm: str | None


@dataclass
class SessionWatts:
    """Ergebnis von session_watts: Abschnitte plus Hinweis, falls die FTP fehlt."""

    ftp_watts: int | None
    segments: list[SegmentWatts] = field(default_factory=list)
    message: str | None = None


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------


def _warmup(minutes: float = 15) -> Segment:
    return Segment(minutes, 50, 65, "Einfahren")


def _cooldown(minutes: float = 10) -> Segment:
    return Segment(minutes, 40, 55, "Ausfahren")


def _z1(minutes: float, label: str = "Locker Z1") -> Segment:
    return Segment(minutes, 40, 55, label, filler=True)


def _z2(minutes: float, label: str = "Grundlage Z2", low: float = 56) -> Segment:
    return Segment(minutes, low, 75, label, filler=True)


def _long_z2(minutes: float) -> Segment:
    # lange Ausfahrt laut §3: Z2 (65–75 % FTP)
    return _z2(minutes, "Lange Ausfahrt Z2", low=65)


def _intervals(
    reps: int,
    work_min: float,
    low: float,
    high: float,
    rest_min: float,
    label: str,
    cadence: str | None = None,
) -> list[Segment]:
    """Expandiert reps x (Belastung + Pause Z1); nach dem letzten Intervall keine Pause."""
    segments: list[Segment] = []
    for i in range(reps):
        segments.append(Segment(work_min, low, high, f"{label} {i + 1}/{reps}", cadence))
        if i < reps - 1:
            segments.append(Segment(rest_min, 40, 55, "Pause Z1"))
    return segments


def _structured(warmup: float, blocks: list[Segment], cooldown: float = 10) -> list[Segment]:
    return [_warmup(warmup), *blocks, _cooldown(cooldown)]


def _endurance_with_blocks(total_minutes: float, blocks: list[Segment], low: float = 65) -> list[Segment]:
    """Grundlagenfahrt, in deren Mitte Bloecke liegen; der Rest ist Z2 vorher/nachher."""
    block_minutes = sum(b.minutes for b in blocks)
    remaining = max(total_minutes - block_minutes, 0)
    before = round(remaining * 0.5)
    return [_z2(before, "Grundlage Z2", low=low), *blocks, _z2(remaining - before, "Grundlage Z2", low=low)]


def _late_efforts(total_minutes: float, blocks: list[Segment]) -> list[Segment]:
    """Lange Fahrt mit Efforts spaet in der Ausfahrt ("hard efforts on tired legs")."""
    block_minutes = sum(b.minutes for b in blocks)
    remaining = max(total_minutes - block_minutes, 0)
    after = 20
    return [_z2(remaining - after, "Lange Ausfahrt Z2", low=65), *blocks, _z1(after, "Ausrollen")]


def _ramp_test() -> CyclingSession:
    return CyclingSession(
        SLOT_FTP_TEST,
        "Zwift-Ramp-Test (FTP)",
        [
            _warmup(10),
            Segment(15, None, None, "Ramp-Test: Start 100 W, +20 W/min bis zur Erschöpfung"),
            _cooldown(10),
        ],
        CyclingIntensity.ZUEGIG_TEMPO,
        zwift_hint="Workout „Ramp Test“ (Wiedereinsteiger ggf. „Ramp Test Lite“: 50 W, +10 W/min)",
        note="FTP = 75 % der besten 1-Min-Leistung – danach im Dashboard als FTP-Test erfassen.",
    )


def _rekom(minutes: float, title: str = "Rekom-Spin") -> CyclingSession:
    return CyclingSession(SLOT_REKOM, title, [_z1(minutes)], CyclingIntensity.LEICHT_REKOM)


def _z2_ride(slot: str, minutes: float, title: str = "Grundlage") -> CyclingSession:
    return CyclingSession(
        slot, title, [_z2(minutes)], CyclingIntensity.MODERAT_BASE, zwift_hint="Zone-2-Endurance-Ride"
    )


# ---------------------------------------------------------------------------
# Phasen
# ---------------------------------------------------------------------------


def _phase0(slot: str, week: int) -> CyclingSession | None:
    """Wiedereinstieg: ~5 h/Woche, ueberwiegend Z2, kurze Aktivierungen 3x3 min Z3."""
    activation = _intervals(3, 3, 76, 87, 3, "Aktivierung Z3")
    if slot == SLOT_REKOM:
        return _rekom(30)
    if slot == SLOT_KEY_1:
        return CyclingSession(
            slot, "Grundlage mit Aktivierung 3×3 min Z3", _endurance_with_blocks(60, activation, low=56),
            CyclingIntensity.MODERAT_BASE,
        )
    if slot == SLOT_Z2:
        return _z2_ride(slot, 60)
    if slot == SLOT_Z2_OR_REKOM:
        return _rekom(30)
    if slot == SLOT_KEY_2:
        if week == 1:
            return _ramp_test()  # fuer bereits gespeicherte Tage; neue Tage erhalten den Slot ftp_test
        return CyclingSession(
            slot, "Grundlage mit Aktivierung 3×3 min Z3", _endurance_with_blocks(60, activation, low=56),
            CyclingIntensity.MODERAT_BASE,
        )
    if slot == SLOT_LONG:
        return CyclingSession(slot, "Längere Grundlage", [_long_z2(75)], CyclingIntensity.MODERAT_BASE)
    return None


def _base(slot: str, week: int) -> CyclingSession | None:
    """Base (8 Wochen): Sweet-Spot-Aufbau, Low-Cadence-Kraftintervalle, lange Ausfahrt 2 -> 3 h."""
    if slot in (SLOT_REKOM, SLOT_Z2_OR_REKOM):
        return _rekom(30)
    if slot == SLOT_KEY_1:
        reps, work = (3, 10) if week <= 2 else (3, 12) if week <= 5 else (2, 20)
        return CyclingSession(
            slot,
            f"Sweet Spot {reps}×{work} min",
            _structured(15, _intervals(reps, work, 88, 94, 5, "Sweet Spot")),
            CyclingIntensity.ZUEGIG_TEMPO,
            zwift_hint="Kategorie „Sweet Spot Base“",
        )
    if slot == SLOT_Z2:
        return _z2_ride(slot, 60 if week <= 4 else 75)
    if slot == SLOT_KEY_2:
        reps, work = {1: (4, 5), 2: (4, 5), 3: (5, 5), 4: (5, 5), 5: (6, 5), 6: (6, 5)}.get(week, (5, 8))
        return CyclingSession(
            slot,
            f"Low-Cadence {reps}×{work} min",
            _structured(15, _intervals(reps, work, 88, 92, 4, "Low-Cadence", cadence="50–60")),
            CyclingIntensity.ZUEGIG_TEMPO,
            zwift_hint="Kategorie „Climbing“ (Low-Cadence-Strength-Ramps)",
            note="Sitzend fahren. Bei Knie-/Rückenproblemen vorsichtig aufbauen.",
        )
    if slot == SLOT_LONG:
        minutes = 120 if week <= 2 else 150 if week <= 4 else 180
        return CyclingSession(
            slot, f"Lange Ausfahrt {minutes // 60}:{minutes % 60:02d} h", [_long_z2(minutes)],
            CyclingIntensity.MODERAT_BASE, zwift_hint="Alpe du Zwift / Epic KOM als steady Z2-Anstieg",
        )
    return None


def _build1(slot: str, week: int) -> CyclingSession | None:
    """Build 1 (8 Wochen): Schwelle, Over-Unders, lange Ausfahrt mit Tempo; jede 3. Woche Erholung."""
    deload = week % BUILD1_DELOAD_EVERY_WEEKS == 0
    if slot in (SLOT_REKOM, SLOT_Z2_OR_REKOM):
        return _rekom(30)
    if slot == SLOT_KEY_1:
        if deload:
            reps, work, low, high, rest = 3, 8, 95, 100, 4
        elif week <= 2:
            reps, work, low, high, rest = 4, 8, 95, 100, 4
        elif week <= 5:
            reps, work, low, high, rest = 3, 15, 95, 105, 5
        else:
            reps, work, low, high, rest = 2, 20, 95, 105, 5
        return CyclingSession(
            slot,
            f"Schwelle {reps}×{work} min",
            _structured(15, _intervals(reps, work, low, high, rest, "Schwelle")),
            CyclingIntensity.RENNEN_INTERVALLE,
            zwift_hint="Kategorie „Threshold“",
            note="Zur Bergspezifik teils bei 65–75 rpm fahren.",
        )
    if slot == SLOT_Z2:
        return _z2_ride(slot, 45 if deload else 75)
    if slot == SLOT_KEY_2:
        reps = 2 if deload else 3
        blocks: list[Segment] = []
        for i in range(reps):
            for _ in range(3):
                blocks.append(Segment(2, 95, 95, f"Under {i + 1}/{reps}"))
                blocks.append(Segment(2, 105, 105, f"Over {i + 1}/{reps}"))
            if i < reps - 1:
                blocks.append(Segment(6, 40, 55, "Pause Z1"))
        return CyclingSession(
            slot, f"Over-Unders {reps}×12 min (95/105 %)", _structured(15, blocks),
            CyclingIntensity.RENNEN_INTERVALLE, zwift_hint="Over-Under-Klassiker",
        )
    if slot == SLOT_LONG:
        if deload:
            minutes = round(180 * DELOAD_VOLUME_FACTOR)
            return CyclingSession(slot, "Lange Ausfahrt (Erholungswoche)", [_long_z2(minutes)], CyclingIntensity.MODERAT_BASE)
        minutes, tempo_reps = (180, 2) if week <= 2 else (210, 2) if week <= 5 else (240, 3)
        tempo = _intervals(tempo_reps, 20, 76, 87, 10, "Tempo Z3")
        return CyclingSession(
            slot, f"Lange Ausfahrt {minutes // 60}:{minutes % 60:02d} h + {tempo_reps}×20 min Tempo",
            _endurance_with_blocks(minutes, tempo), CyclingIntensity.MODERAT_BASE,
        )
    return None


def _build2(slot: str, week: int) -> CyclingSession | None:
    """Build 2 (5 Wochen): VO2max, Bergsimulation, Back-to-Back-Wochenende."""
    if slot == SLOT_REKOM:
        return _rekom(30)
    if slot == SLOT_Z2_OR_REKOM:
        return _rekom(45, "Rekom oder locker Z2")
    if slot == SLOT_KEY_1:
        return CyclingSession(
            slot, "VO2max 5×4 min", _structured(15, _intervals(5, 4, 106, 115, 4, "VO2max")),
            CyclingIntensity.RENNEN_INTERVALLE,
            zwift_hint="Kategorie „VO2 Max“ (Alternative: 30/15 oder 40/20)",
        )
    if slot == SLOT_Z2:
        return _z2_ride(slot, 75)
    if slot == SLOT_KEY_2:
        minutes = 180 if week <= 2 else 210
        climb = [Segment(60, 85, 95, "Bergsimulation", "60–70")]
        return CyclingSession(
            slot, f"Bergsimulation 60 min + Grundlage ({minutes // 60}:{minutes % 60:02d} h)",
            _endurance_with_blocks(minutes, climb), CyclingIntensity.MODERAT_BASE,
            zwift_hint="Alpe du Zwift (12,4 km, 1.144 Hm) als Referenz",
        )
    if slot == SLOT_LONG:
        minutes = 150 if week <= 2 else 180
        late = _intervals(2, 15, 88, 92, 10, "Später Effort")
        return CyclingSession(
            slot, f"Lange Ausfahrt + späte Efforts ({minutes // 60}:{minutes % 60:02d} h)",
            _late_efforts(minutes, late), CyclingIntensity.MODERAT_BASE,
            note="Back-to-Back mit Samstag: harte Efforts auf müden Beinen.",
        )
    return None


def _peak_taper(slot: str, week: int) -> CyclingSession | None:
    """Peak (3 Spezifik-Wochen mit Back-to-Back-Wochenenden) und Taper (2 Wochen, Volumen -40–60 %)."""
    if week <= PEAK_SPECIFIC_WEEKS:
        if slot == SLOT_REKOM:
            return _rekom(30)
        if slot == SLOT_Z2_OR_REKOM:
            return _rekom(45, "Rekom oder locker Z2")
        if slot == SLOT_KEY_1:
            return CyclingSession(
                slot, "Schwelle 2×20 min am Berg",
                _structured(15, _intervals(2, 20, 95, 105, 5, "Schwelle", cadence="65–75")),
                CyclingIntensity.RENNEN_INTERVALLE,
            )
        if slot == SLOT_Z2:
            return _z2_ride(slot, 75)
        if slot == SLOT_KEY_2:
            blocks = _intervals(2, 20, 88, 94, 10, "Sweet Spot am Berg", cadence="60–70")
            return CyclingSession(
                slot, "Spezifik: 4 h mit 2×20 min Sweet Spot am Berg", _endurance_with_blocks(240, blocks),
                CyclingIntensity.MODERAT_BASE, note="Mini-Trainingslager Sa+So: viele Höhenmeter.",
            )
        if slot == SLOT_LONG:
            late = _intervals(2, 15, 88, 92, 10, "Später Effort")
            return CyclingSession(
                slot, "Spezifik: 3:30 h, Back-to-Back", _late_efforts(210, late), CyclingIntensity.MODERAT_BASE,
            )
        return None
    # Taper-Beispielwoche aus §3: Volumen runter, Intensitaet und Frequenz halten
    if slot == SLOT_REKOM:
        return None
    if slot == SLOT_KEY_1:
        return CyclingSession(
            slot, "Schwelle 3×6 min (scharf, kurz)", _structured(12, _intervals(3, 6, 100, 100, 4, "Schwelle")),
            CyclingIntensity.ZUEGIG_TEMPO,
        )
    if slot == SLOT_Z2:
        return _rekom(40, "Rekom")
    if slot == SLOT_Z2_OR_REKOM:
        return CyclingSession(
            slot, "Kurze Aktivierung 3×3 min Z4", _endurance_with_blocks(45, _intervals(3, 3, 95, 105, 3, "Aktivierung Z4"), low=56),
            CyclingIntensity.MODERAT_BASE,
        )
    if slot == SLOT_KEY_2:
        return CyclingSession(
            slot, "Moderate Ausfahrt 2 h mit 2×15 min Tempo",
            _endurance_with_blocks(120, _intervals(2, 15, 76, 87, 10, "Tempo Z3")), CyclingIntensity.MODERAT_BASE,
        )
    if slot == SLOT_LONG:
        return _z2_ride(slot, 70, "Locker")
    return None


def _passsaison(slot: str, week: int) -> CyclingSession | None:
    """Nicht-Tour-Woche der Passsaison: 1 Erhaltungs-Schluesseleinheit, 1–2 lockere Z2-Ausfahrten."""
    if slot in (SLOT_REKOM, SLOT_Z2):
        return None
    if slot == SLOT_KEY_1:
        return CyclingSession(
            slot, "Erhalt: 2×20 min @ 90–95 %", _structured(15, _intervals(2, 20, 90, 95, 5, "Erhalt")),
            CyclingIntensity.ZUEGIG_TEMPO,
        )
    if slot == SLOT_Z2_OR_REKOM:
        return _z2_ride(slot, 60)
    if slot == SLOT_KEY_2:
        return CyclingSession(
            slot, "Passtour oder lange Ausfahrt", [_long_z2(240)], CyclingIntensity.MODERAT_BASE,
            note="Pacing: Anstiege 75–85 % FTP, erste Rampen 5–10 % unter Zielwatt. 2–3 Tage vor Mehrfachpass-Tagen locker/Ruhe.",
        )
    if slot == SLOT_LONG:
        return _z2_ride(slot, 90, "Lockere Grundlage")
    return None


_PHASE_BUILDERS = {
    "phase0_wiedereinstieg": _phase0,
    "base": _base,
    "build1": _build1,
    "build2": _build2,
    "peak_taper": _peak_taper,
    "passsaison": _passsaison,
}


def build_cycling_session(slot: str, phase_id: str, week_in_phase: int) -> CyclingSession | None:
    """Liefert die Rad-Einheit fuer einen Slot in einer Phase-Woche.

    Args:
        slot: Slot der Standardwoche (siehe ALL_SLOTS).
        phase_id: Trainingsphase (siehe engine.training_phase).
        week_in_phase: 1-indexierte Woche innerhalb der Phase.

    Returns:
        Die Einheit, oder None, wenn die Phase fuer diesen Slot keine Radeinheit vorsieht.

    Raises:
        ValueError: bei unbekanntem Slot oder unbekannter Phase.
    """
    if slot not in ALL_SLOTS:
        raise ValueError(f"unbekannter Slot: {slot}")
    if phase_id not in _PHASE_BUILDERS:
        raise ValueError(f"unbekannte Phase: {phase_id}")
    if slot == SLOT_FTP_TEST:
        return _ramp_test()
    session = _PHASE_BUILDERS[phase_id](slot, max(week_in_phase, 1))
    # Bausteine wie _rekom() kennen den angefragten Slot nicht
    return replace(session, slot=slot) if session is not None else None


def is_deload_week(phase_id: str, week_in_phase: int) -> bool:
    """True in den Erholungswochen von Build 1 (jede 3. Woche)."""
    return phase_id == "build1" and week_in_phase % BUILD1_DELOAD_EVERY_WEEKS == 0


def adjust_duration(session: CyclingSession, minutes: float) -> CyclingSession:
    """Passt die Dauer einer Ausdauerfahrt an.

    Die Grundlagen-Abschnitte (filler) werden proportional skaliert; Bloecke (Tempo, Efforts)
    bleiben. Reicht die Zeit nicht fuer die Bloecke, wird daraus eine reine Grundlagenfahrt.

    Args:
        session: Einheit eines Ausdauer-Slots (siehe ENDURANCE_SLOTS).
        minutes: gewuenschte Gesamtdauer (> 0).

    Returns:
        Neue CyclingSession mit adjusted=True.

    Raises:
        ValueError: bei Schluesseleinheiten oder minutes <= 0.
    """
    if session.slot not in ENDURANCE_SLOTS:
        raise ValueError("Dauer nur bei Ausdauerfahrten anpassbar")
    if minutes <= 0:
        raise ValueError("minutes muss > 0 sein")
    fillers = [s for s in session.segments if s.filler]
    fixed = sum(s.minutes for s in session.segments if not s.filler)
    filler_total = sum(s.minutes for s in fillers)
    if not fillers or minutes - fixed < 10:
        base = fillers[0] if fillers else _z2(minutes)
        segments = [replace(base, minutes=minutes)]
    else:
        factor = (minutes - fixed) / filler_total
        segments = [replace(s, minutes=round(s.minutes * factor)) if s.filler else s for s in session.segments]
        # Rundungsdifferenz auf den letzten Filler-Abschnitt
        diff = minutes - sum(s.minutes for s in segments)
        last = max(i for i, s in enumerate(segments) if s.filler)
        segments[last] = replace(segments[last], minutes=segments[last].minutes + diff)
    return replace(session, segments=segments, adjusted=True)


def session_watts(session: CyclingSession, ftp_watts: int | None) -> SessionWatts:
    """Rechnet die %-FTP-Vorgaben in Watt um.

    Args:
        session: Rad-Einheit.
        ftp_watts: aktuelle FTP, oder None falls noch nicht getestet.

    Returns:
        SessionWatts; ohne FTP bleiben die Watt-Felder None und `message` ist gesetzt.
    """

    def watts(pct: float | None, rounder) -> int | None:
        if ftp_watts is None or pct is None:
            return None
        return int(rounder(ftp_watts * pct / 100))

    segments = [
        SegmentWatts(
            minutes=s.minutes,
            label=s.label,
            pct_ftp_low=s.pct_ftp_low,
            pct_ftp_high=s.pct_ftp_high,
            watts_low=watts(s.pct_ftp_low, math.ceil),
            watts_high=watts(s.pct_ftp_high, math.floor),
            cadence_rpm=s.cadence_rpm,
        )
        for s in session.segments
    ]
    return SessionWatts(
        ftp_watts=ftp_watts, segments=segments, message=None if ftp_watts is not None else FTP_MISSING_MESSAGE
    )
