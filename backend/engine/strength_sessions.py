"""Kraft-, Core- und Mobility-Einheiten je Kraftphase.

Quelle: docs/research/Trainingsplan Kraft.md – Uebungsbibliothek (A–D), 6-Monats-Periodisierung
(Phasen 1–3) und Beispiel-Einheiten A/B. Die Zuordnung der neu hinzukommenden Uebungen aus den
Phasen 2/3 (Hollow Body, Single-Leg Deadlift, Copenhagen Plank, Pallof-Hold) zu Einheit A bzw. B
ist eine Annahme; die Recherche nennt sie nur als Phasen-Fokus.
"""

import logging
from dataclasses import dataclass, replace

logger = logging.getLogger(__name__)

SESSION_IDS: tuple[str, ...] = ("A", "B")


@dataclass
class Exercise:
    """Eine Uebung. `scaled` = Saetze/Reps/Pause kommen aus den Parametern der Kraftphase."""

    name: str
    sets: str
    reps: str
    rest: str | None = None
    note: str | None = None
    min_phase: int = 1
    max_phase: int = 3
    scaled: bool = False
    leg: bool = False  # Beinuebung, entfaellt bei reduzierter Kraft (Beine chronisch platt)


@dataclass
class StrengthPhase:
    """Parameter einer Kraftphase (Saetze/Reps/Pause fuer `scaled`-Uebungen)."""

    number: int
    title: str
    sets: str | None
    reps: str
    rest: str
    tempo: str


@dataclass
class StrengthSession:
    """Eine Krafteinheit (A oder B) in einer Kraftphase."""

    session_id: str
    title: str
    phase: StrengthPhase
    exercises: list[Exercise]
    duration_minutes: str = "50–55"
    note: str | None = None


STRENGTH_PHASES: dict[int, StrengthPhase] = {
    1: StrengthPhase(1, "Anatomische Anpassung", "2–3", "15–25", "60–90 s", "langsam & kontrolliert"),
    2: StrengthPhase(2, "Kraft-/Muskelaufbau", "3", "8–12", "60–90 s", "2–3 s exzentrisch"),
    3: StrengthPhase(3, "Kraftausdauer & Erhalt", None, "10–15", "45–60 s", "kontrolliert, einzelne schwer-langsame Sätze"),
}

# sync_rules.phase_alignment aus docs/data-model.yaml; phase0 (Wiedereinstieg) zaehlt zur Anpassungsphase
_STRENGTH_PHASE_BY_CYCLING_PHASE: dict[str, int] = {
    "phase0_wiedereinstieg": 1,
    "base": 1,
    "build1": 2,
    "build2": 3,
    "peak_taper": 3,
    "passsaison": 3,
}

_SESSION_A: list[Exercise] = [
    Exercise("Aufwärmen/Mobility", "1", "8 min", note="Hüftbeuger, Open Book, Cat-Cow, Wall Angels"),
    Exercise("Glute Bridge (Progression → Single-Leg)", "3", "12–15", scaled=True,
             note="Im Gesäss spüren, nicht im Hamstring/unteren Rücken"),
    Exercise("Liegestütz-Progression", "3", "8–15", scaled=True,
             note="Wand → Inkline → Knie → Standard → Füsse erhöht; 2 s runter / 1 s hoch"),
    Exercise("Pike Push-ups", "3", "6–10", min_phase=2),
    Exercise("Hollow Body Hold", "3", "20–40 s", min_phase=2),
    Exercise("Dead Bug", "3", "8–10 je Seite", note="Lendenwirbel flach am Boden, langsam"),
    Exercise("Side Plank", "3", "15–30 s je Seite", note="Phase 1 Knie gebeugt, ab Phase 2 gestreckt"),
    Exercise("Anti-rotatorischer Band-Hold (Pallof)", "3", "20–30 s je Seite", min_phase=3),
    Exercise("Band External Rotation", "2", "12–15 je Seite", note="Handtuch zwischen Ellbogen und Rippen"),
]

_SESSION_B: list[Exercise] = [
    Exercise("Aufwärmen/Mobility", "1", "8 min", note="90/90, BWS-Extension, Clamshells als Aktivierung"),
    Exercise("Inverted Rows (Tischkanten-Rudern)", "3–4", "8–15", scaled=True,
             note="Körper gerade, Schulterblätter zusammen; Progression Füsse erhöht"),
    Exercise("Band Pull-Aparts + Face Pulls", "2–3", "15–20", min_phase=2),
    Exercise("Bulgarian Split Squat", "3", "6–10 je Bein", min_phase=2, scaled=True, leg=True,
             note="Wdh. je Bein, 2–3 Wdh. in Reserve"),
    Exercise("Single-Leg Deadlift", "2–3", "8 je Bein", min_phase=2, leg=True, note="Hüfthinge, Balance"),
    Exercise("Lateral Band Walks", "2", "10 Schritte je Richtung", leg=True,
             note="Leichte Kniebeuge, Knie nicht einknicken"),
    Exercise("Copenhagen Plank", "2", "10–20 s je Seite", min_phase=3),
    Exercise("McGill Curl-Up", "1", "Pyramide 5-3-1, je 8–10 s halten", note="Kein Nacken-Crunch"),
    Exercise("Bird Dog", "3", "6–8 je Seite, 3–5 s halten", note="Neutrale Wirbelsäule"),
    Exercise("YTW-Raises", "2–3", "8–12 pro Buchstabe"),
]

_SESSIONS: dict[str, tuple[str, list[Exercise]]] = {
    "A": ("Krafteinheit A (Push/Core/Glute)", _SESSION_A),
    "B": ("Krafteinheit B (Pull/Core/Bein-Stabilität)", _SESSION_B),
}

MOBILITY_ROUTINE: list[Exercise] = [
    Exercise("Kniender Hüftbeuger-Stretch", "2", "30–45 s je Seite", note="Becken untertucken, kein Hohlkreuz"),
    Exercise("90/90 Hüftrotationen", "1", "8–10 Wechsel je Seite"),
    Exercise("Open Book", "1", "6–8 je Seite, 2 s halten"),
    Exercise("Cat-Cow / Quadruped Rotation", "1", "8 bzw. 6 je Seite"),
    Exercise("BWS-Extension über Foam Roller", "1", "6–8 langsam"),
    Exercise("Wall Angels / Wall Slides", "1", "8–10"),
    Exercise("Pigeon (Glute-Stretch)", "1", "30–60 s je Seite", note="bei Bedarf"),
]

# Bei Rueckenschmerz nach langen Fahrten: Core-Frequenz erhoehen (McGill: kurze, haeufige Belastungen)
MCGILL_BIG_3: list[Exercise] = [
    Exercise("McGill Curl-Up", "1", "Pyramide 5-3-1, je 8–10 s halten", note="Core täglich"),
    Exercise("Side Plank", "2", "10–20 s je Seite", note="Core täglich"),
    Exercise("Bird Dog", "2", "6 je Seite, 3–5 s halten", note="Core täglich"),
]

REDUCED_NOTE = "Reduziert (Beine platt): Beinübungen entfallen, Volumen ~20 % runter (je Übung 1 Satz weniger)."


def strength_phase_for(cycling_phase_id: str) -> StrengthPhase:
    """Kraftphase, die laut sync_rules zur Rad-Phase gehoert.

    Args:
        cycling_phase_id: Trainingsphase (siehe engine.training_phase).

    Returns:
        Die zugehoerige StrengthPhase.

    Raises:
        ValueError: bei unbekannter Phase.
    """
    if cycling_phase_id not in _STRENGTH_PHASE_BY_CYCLING_PHASE:
        raise ValueError(f"unbekannte Phase: {cycling_phase_id}")
    return STRENGTH_PHASES[_STRENGTH_PHASE_BY_CYCLING_PHASE[cycling_phase_id]]


def build_strength_session(
    session_id: str, phase: StrengthPhase, note: str | None = None, reduced: bool = False
) -> StrengthSession:
    """Stellt Einheit A oder B fuer eine Kraftphase zusammen.

    Uebungen ausserhalb ihres Phasenfensters entfallen; `scaled`-Uebungen uebernehmen
    Saetze (falls die Phase welche vorgibt), Reps und Pause der Phase.

    Args:
        session_id: "A" oder "B".
        phase: Kraftphase (siehe strength_phase_for).
        note: optionaler Hinweis (z. B. reduzierte Einheit im Taper).
        reduced: Beinuebungen weglassen und Reduktionshinweis ergaenzen (Kraft-Recherche:
            "Beine chronisch platt -> Volumen -20 %").

    Returns:
        StrengthSession mit den Uebungen der Phase.

    Raises:
        ValueError: bei unbekannter session_id.
    """
    if session_id not in _SESSIONS:
        raise ValueError(f"unbekannte Krafteinheit: {session_id}")
    title, library = _SESSIONS[session_id]
    exercises = []
    for exercise in library:
        if not exercise.min_phase <= phase.number <= exercise.max_phase or (reduced and exercise.leg):
            continue
        if exercise.scaled:
            exercise = replace(exercise, sets=phase.sets or exercise.sets, reps=phase.reps, rest=phase.rest)
        exercises.append(exercise)
    if reduced:
        note = f"{note} {REDUCED_NOTE}" if note else REDUCED_NOTE
    return StrengthSession(session_id=session_id, title=title, phase=phase, exercises=exercises, note=note)
