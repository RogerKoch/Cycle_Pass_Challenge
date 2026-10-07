"""Event-Vorbereitung: Taper, Carb-Loading, Event-Tag und Recovery.

Quelle: docs/research/event-vorbereitung.md (Burke 2011, ACSM 2016, Bosquet 2007, Mujika & Padilla 2003).
Alles wird zur Lesezeit aus dem Event abgeleitet, im Kalender wird nichts persistiert. Mit [A] markierte
Werte in der Recherche sind App-Ableitungen, keine Literaturvorgaben.
"""

import logging
from dataclasses import dataclass, replace
from datetime import date

from backend.engine.cycling_sessions import SLOT_FTP_TEST, SLOT_REKOM, CyclingSession, Segment
from backend.engine.nutrition_calc import CyclingIntensity

logger = logging.getLogger(__name__)

PRIORITIES: tuple[str, ...] = ("A", "B", "C")
KIND_RACE = "rennen"
KIND_TOUR = "tour"
KINDS: tuple[str, ...] = (KIND_RACE, KIND_TOUR)

SLOT_EVENT = "event"
SLOT_OPENER = "opener"

PHASE_TAPER = "taper"
PHASE_LOAD = "load"
PHASE_EVENT = "event"
PHASE_RECOVERY = "recovery"

TAPER_DAYS = {"A": 14, "B": 7, "C": 2}
# Volumen-Faktor am ersten und am letzten Taper-Tag (T-2); dazwischen linear
TAPER_VOLUME = {"A": (0.8, 0.5), "B": (0.7, 0.55), "C": (0.8, 0.8)}
LOAD_DAYS = 3  # T-3 .. T-1
LOADING_MIN_MINUTES = 90  # darunter kein Carb-Loading
LONG_EVENT_MINUTES = 150
# KH g/kg je Tag vor dem Event (Tage bis zum Event -> g/kg)
CARBS_LONG_A = {3: 7.0, 2: 9.0, 1: 10.0}
CARBS_MEDIUM = {2: 7.0, 1: 8.5}
CARBS_SHORT = {1: 7.0}
LOAD_FAT_G_PER_KG = 0.8  # T-2/T-1: Fett runter, aber nicht unter 0,8 g/kg
FULL_DEFICIT_PAUSE_DAYS = 7  # Defizit ab T-7 aus (Prio A/B)
HALF_DEFICIT_FROM_DAYS = 14  # Prio A: T-14..T-8 halbes Defizit
RECOVERY_RIDE_MINUTES = 30
RECOVERY_MIN_DAYS = 2  # Kontextfenster nach dem Event mind. 48 h (Kraftsperre, auch bei kurzen Events)
WEIGHT_EXCLUDED_AFTER_DAYS = 3  # Check-in-Gewichte bis R+3 verfaelschen den Trend (Wasser)
RECOVERY_DAYS_SHORT_MIN, RECOVERY_DAYS_LONG_MIN = 120, 240  # <2 h: 1 Tag, <=4 h: 2 Tage, sonst 3
EVENT_INTENSITY = {KIND_RACE: CyclingIntensity.RENNEN_INTERVALLE, KIND_TOUR: CyclingIntensity.MODERAT_BASE}


@dataclass
class EventSpan:
    """Ein Event als Engine-Sicht."""

    event_date: date
    name: str
    priority: str = "B"
    expected_minutes: float = 180.0
    kind: str = KIND_RACE


@dataclass
class EventContext:
    """Lage eines Tages relativ zu einem Event (days_to > 0 vor, 0 am Tag, < 0 danach)."""

    span: EventSpan
    days_to: int
    phase: str  # taper | load | event | recovery

    @property
    def label(self) -> str:
        """T-3, Event oder R+1."""
        if self.days_to > 0:
            return f"T-{self.days_to}"
        return "Event" if self.days_to == 0 else f"R+{-self.days_to}"


def recovery_days(expected_minutes: float) -> int:
    """Lockere Tage nach dem Event: <2 h 1, <=4 h 2, laenger 3."""
    if expected_minutes < RECOVERY_DAYS_SHORT_MIN:
        return 1
    return 2 if expected_minutes <= RECOVERY_DAYS_LONG_MIN else 3


def _context_for(day: date, span: EventSpan) -> EventContext | None:
    days_to = (span.event_date - day).days
    if days_to > max(TAPER_DAYS[span.priority], LOAD_DAYS):
        return None
    if days_to < -max(recovery_days(span.expected_minutes), RECOVERY_MIN_DAYS):
        return None
    if days_to < 0:
        phase = PHASE_RECOVERY
    elif days_to == 0:
        phase = PHASE_EVENT
    elif days_to <= LOAD_DAYS:
        phase = PHASE_LOAD
    else:
        phase = PHASE_TAPER
    return EventContext(span, days_to, phase)


def event_context(day: date, spans: list[EventSpan]) -> EventContext | None:
    """Relevanter Event-Kontext eines Tages; bei Ueberlappung gewinnt das naechste (bei Gleichstand das kommende
    vor dem vergangenen), dann das wichtigere Event."""
    contexts = [c for s in spans if (c := _context_for(day, s)) is not None]
    if not contexts:
        return None
    return min(contexts, key=lambda c: (abs(c.days_to), c.days_to < 0, c.span.priority))


def taper_volume_factor(ctx: EventContext) -> float | None:
    """Volumen-Faktor des Tages (T-N..T-2); None ausserhalb des Tapers oder am Opener-/Eventtag."""
    if ctx.days_to < 2 or ctx.days_to > TAPER_DAYS[ctx.span.priority]:
        return None
    start, end = TAPER_VOLUME[ctx.span.priority]
    length = TAPER_DAYS[ctx.span.priority] - 2
    if length == 0:
        return start
    return start + (end - start) * (TAPER_DAYS[ctx.span.priority] - ctx.days_to) / length


def apply_taper(session: CyclingSession, factor: float) -> CyclingSession:
    """Taper: alle Abschnitte x Faktor bei gleicher Intensitaet; der Ramp-Test bleibt unveraendert."""
    if session.slot == SLOT_FTP_TEST:
        return session
    segments = [replace(s, minutes=max(round(s.minutes * factor), 1)) for s in session.segments]
    return replace(session, segments=segments, title=f"{session.title} (Taper)")


def opener_session() -> CyclingSession:
    """T-1: kurze Einheit mit drei Antritten zum Aufwecken (Recherche §1)."""
    segments = [Segment(15, 50, 65, "Einfahren")]
    for i in range(3):
        segments.append(Segment(1, 110, 130, f"Antritt {i + 1}/3"))
        segments.append(Segment(4, 40, 55, "Locker Z1"))
    segments.append(Segment(8, 40, 55, "Ausfahren"))
    return CyclingSession(
        SLOT_OPENER,
        "Opener: 3 kurze Antritte",
        segments,
        CyclingIntensity.MODERAT_BASE,
        zwift_hint="Kurze Antritte, nicht ausreizen",
        note="Beine wecken, nicht trainieren. Danach Beine hochlegen.",
    )


def event_day_session(span: EventSpan) -> CyclingSession:
    """Platzhalter-Einheit fuer den Eventtag (Dauer und Intensitaet fuer kcal und Fueling, kein Zwift-Workout)."""
    return CyclingSession(
        SLOT_EVENT,
        f"Event: {span.name}",
        [Segment(span.expected_minutes, None, None, "Event")],
        EVENT_INTENSITY[span.kind],
        note="Pacing konservativ beginnen, Fueling ab Minute 1 nach Plan.",
    )


def recovery_session() -> CyclingSession:
    """Lockere Erholungsfahrt nach dem Event."""
    return CyclingSession(
        SLOT_REKOM,
        "Rekom-Spin (Erholung nach Event)",
        [Segment(RECOVERY_RIDE_MINUTES, 40, 55, "Locker Z1", filler=True)],
        CyclingIntensity.LEICHT_REKOM,
    )


def apply_event_to_session(session: CyclingSession | None, ctx: EventContext | None) -> CyclingSession | None:
    """Ueberlagert die geplante Rad-Einheit mit dem Event (Taper, Opener, Eventtag, Recovery).

    Args:
        session: regulaer geplante Einheit oder None (Ruhetag).
        ctx: Event-Kontext des Tages.

    Returns:
        Die angepasste Einheit; Opener und Eventtag auch an Ruhetagen, Taper und Recovery nur wo geplant.
    """
    if ctx is None:
        return session
    if ctx.days_to == 0:
        return event_day_session(ctx.span)
    if ctx.days_to == 1:
        return opener_session()
    if ctx.days_to < 0:
        return recovery_session() if session is not None else None
    factor = taper_volume_factor(ctx)
    if session is None or factor is None:
        return session
    return apply_taper(session, factor)


def strength_blocked(ctx: EventContext | None) -> bool:
    """Keine Kraft am Eventtag, T-1, bei A/B auch T-2, und 48 h nach dem Event (Recherche §1/§5)."""
    if ctx is None:
        return False
    if ctx.days_to in (0, 1) or (ctx.days_to == 2 and ctx.span.priority in ("A", "B")):
        return True
    return -2 <= ctx.days_to < 0


@dataclass
class EventNutrition:
    """Ernaehrungs-Override eines Tages."""

    carbs_g_per_kg: float | None
    fat_g_per_kg: float | None
    deficit_factor: float  # 1 = normal, 0,5 halbes Defizit, 0 = kein Defizit
    hints: list[str]


def carbs_g_per_kg(ctx: EventContext) -> float | None:
    """KH-Ziel des Tages in g/kg (nur Ladetage); None = normale Tagesperiodisierung."""
    if ctx.phase != PHASE_LOAD:
        return None
    span = ctx.span
    if span.priority == "C" or span.expected_minutes < LOADING_MIN_MINUTES:
        table = CARBS_SHORT
    elif span.priority == "A" and span.expected_minutes >= LONG_EVENT_MINUTES:
        table = CARBS_LONG_A
    else:
        table = CARBS_MEDIUM
    return table.get(ctx.days_to)


def deficit_factor(ctx: EventContext) -> float:
    """Anteil des normalen Defizits: 0 im Lade-/Event-/Recovery-Fenster und bei A/B ab T-7, A halb ab T-14."""
    if ctx.phase in (PHASE_LOAD, PHASE_EVENT, PHASE_RECOVERY):
        return 0.0
    if ctx.span.priority in ("A", "B") and ctx.days_to <= FULL_DEFICIT_PAUSE_DAYS:
        return 0.0
    if ctx.span.priority == "A" and ctx.days_to <= HALF_DEFICIT_FROM_DAYS:
        return 0.5
    return 1.0


def event_hints(ctx: EventContext, weight_kg: float) -> list[str]:
    """Hinweistexte des Tages (Training und Ernaehrung)."""
    span = ctx.span
    hints: list[str] = []
    if ctx.phase == PHASE_TAPER:
        factor = deficit_factor(ctx)
        deficit = "Defizit aus" if factor == 0 else "Defizit halbiert" if factor < 1 else "normales Defizit"
        hints.append(f"Taper: Intensität halten, {deficit}.")
    elif ctx.phase == PHASE_LOAD:
        gpk = carbs_g_per_kg(ctx)
        if gpk is not None:
            hints.append(f"Carb-Loading {ctx.label}: {gpk:g} g/kg ≈ {gpk * weight_kg:.0f} g KH.")
        if ctx.days_to <= 2 and gpk is not None:
            hints.append("Ballaststoffe und Fett runter: Reis, Pasta, Weissbrot, Banane, Konfitüre, Saft.")
        if ctx.days_to == 1:
            hints.append("Vorabend: gewohnte, gut verträgliche KH-Mahlzeit, nichts Neues, früh essen.")
            hints.append("Opener 30–45 min locker, danach Beine hochlegen.")
        hints.append("Defizit aus. 1–2 kg mehr auf der Waage sind Wasser, kein Fett.")
    elif ctx.phase == PHASE_EVENT:
        hints.append(f"3–4 h vor Start: {weight_kg * 3:.0f}–{weight_kg * 4:.0f} g KH (Frühstück, wenig Fett/Ballaststoffe).")
        hints.append(f"1–2 h vor Start: {weight_kg:.0f}–{weight_kg * 1.5:.0f} g KH (Reiswaffeln, Riegel, Isogetränk).")
        if span.expected_minutes > 150:
            hints.append("Unterwegs 60–90 g KH/h (2:1 Glukose:Fruktose), ab Beginn alle ~20 min.")
        elif span.expected_minutes >= 75:
            hints.append("Unterwegs 30–60 g KH/h, ab Beginn regelmässig, nicht erst bei Hunger.")
        hints.append(
            f"Danach in den ersten 4 h: {weight_kg:.0f}–{weight_kg * 1.2:.0f} g KH pro Stunde und 20–30 g Protein."
        )
    elif ctx.phase == PHASE_RECOVERY:
        hints.append(
            f"Recovery {ctx.label}: locker/frei, keine Key-Einheit, keine Beinkraft in den ersten 48 h."
        )
        hints.append("Protein 2,0–2,2 g/kg, KH normal, Defizit noch aus.")
    return hints


def event_nutrition(ctx: EventContext, weight_kg: float) -> EventNutrition:
    """Ernaehrungs-Override des Tages."""
    gpk = carbs_g_per_kg(ctx)
    fat = LOAD_FAT_G_PER_KG if gpk is not None and ctx.days_to <= 2 else None
    return EventNutrition(gpk, fat, deficit_factor(ctx), event_hints(ctx, weight_kg))


def weight_trend_excluded(day: date, spans: list[EventSpan]) -> bool:
    """True, wenn ein Check-in-Gewicht im Lade-/Eventfenster (T-3 .. R+3) liegt und den Trend verfaelscht."""
    for span in spans:
        days_to = (span.event_date - day).days
        if -WEIGHT_EXCLUDED_AFTER_DAYS <= days_to <= LOAD_DAYS:
            return True
    return False
