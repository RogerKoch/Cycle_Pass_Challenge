"""Kraft-, Core- und Mobility-Einheiten je Kraftphase.

Quelle: docs/research/Trainingsplan Kraft.md – Uebungsbibliothek (A–D), 6-Monats-Periodisierung
(Phasen 1–3) und Beispiel-Einheiten A/B. Die Zuordnung der neu hinzukommenden Uebungen aus den
Phasen 2/3 (Hollow Body, Single-Leg Deadlift, Copenhagen Plank, Pallof-Hold) zu Einheit A bzw. B
ist eine Annahme; die Recherche nennt sie nur als Phasen-Fokus.

Kraft-Fokus (waehlbar im Profil): Gruppen = Uebungsbibliothek A–D der Recherche (Mobility, Core,
Oberkoerper, Bein-/Gesaess-Stabilitaet). Fokus-Gruppe +1 Satz plus eine Zusatzuebung aus derselben
Bibliotheksgruppe, die in A/B sonst fehlt. Die Zuordnung der Zusatzuebungen zu A bzw. B ist eine
Annahme (Schwerpunkt der Einheit).
"""

import logging
import re
from dataclasses import dataclass, replace

from backend.engine.strength_benchmarks import PUSHUP_VARIANTS, ExerciseStages

logger = logging.getLogger(__name__)

SESSION_IDS: tuple[str, ...] = ("A", "B")

# Uebungsgruppen = Bibliothek A–D der Kraft-Recherche
GROUP_MOBILITY = "mobility"
GROUP_CORE = "core"
GROUP_UPPER = "upper"
GROUP_LEGS = "legs"

FOCUS_NONE = "none"
FOCUS_OPTIONS: dict[str, str] = {
    FOCUS_NONE: "Kein Fokus",
    GROUP_CORE: "Bauch/Core",
    GROUP_UPPER: "Oberkörper",
    GROUP_LEGS: "Beine/Gesäss",
    GROUP_MOBILITY: "Mobility",
}
FOCUS_EXTRA_MINUTES = 10  # Fokus kommt obendrauf (User-Entscheid 2026-10-06)


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
    group: str | None = None  # Bibliotheksgruppe fuer den Kraft-Fokus; None = Aufwaermen


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
    focus: str = FOCUS_NONE  # tatsaechlich angewendeter Kraft-Fokus


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
    Exercise("Glute Bridge (Progression → Single-Leg)", "3", "12–15", scaled=True, group=GROUP_LEGS,
             note="Im Gesäss spüren, nicht im Hamstring/unteren Rücken"),
    Exercise("Liegestütz-Progression", "3", "8–15", scaled=True, group=GROUP_UPPER,
             note="Wand → Inkline → Knie → Standard → Füsse erhöht; 2 s runter / 1 s hoch"),
    Exercise("Pike Push-ups", "3", "6–10", min_phase=2, group=GROUP_UPPER),
    Exercise("Hollow Body Hold", "3", "20–40 s", min_phase=2, group=GROUP_CORE),
    Exercise("Dead Bug", "3", "8–10 je Seite", note="Lendenwirbel flach am Boden, langsam", group=GROUP_CORE),
    Exercise("Side Plank", "3", "15–30 s je Seite", note="Phase 1 Knie gebeugt, ab Phase 2 gestreckt",
             group=GROUP_CORE),
    Exercise("Anti-rotatorischer Band-Hold (Pallof)", "3", "20–30 s je Seite", min_phase=3, group=GROUP_CORE),
    Exercise("Band External Rotation", "2", "12–15 je Seite", note="Handtuch zwischen Ellbogen und Rippen",
             group=GROUP_UPPER),
]

_SESSION_B: list[Exercise] = [
    Exercise("Aufwärmen/Mobility", "1", "8 min", note="90/90, BWS-Extension, Clamshells als Aktivierung"),
    Exercise("Inverted Rows (Tischkanten-Rudern)", "3–4", "8–15", scaled=True, group=GROUP_UPPER,
             note="Körper gerade, Schulterblätter zusammen; Progression Füsse erhöht"),
    Exercise("Band Pull-Aparts + Face Pulls", "2–3", "15–20", min_phase=2, group=GROUP_UPPER),
    Exercise("Bulgarian Split Squat", "3", "6–10 je Bein", min_phase=2, scaled=True, leg=True, group=GROUP_LEGS,
             note="Wdh. je Bein, 2–3 Wdh. in Reserve"),
    Exercise("Single-Leg Deadlift", "2–3", "8 je Bein", min_phase=2, leg=True, note="Hüfthinge, Balance",
             group=GROUP_LEGS),
    Exercise("Lateral Band Walks", "2", "10 Schritte je Richtung", leg=True, group=GROUP_LEGS,
             note="Leichte Kniebeuge, Knie nicht einknicken"),
    Exercise("Copenhagen Plank", "2", "10–20 s je Seite", min_phase=3, group=GROUP_LEGS),
    Exercise("McGill Curl-Up", "1", "Pyramide 5-3-1, je 8–10 s halten", note="Kein Nacken-Crunch", group=GROUP_CORE),
    Exercise("Bird Dog", "3", "6–8 je Seite, 3–5 s halten", note="Neutrale Wirbelsäule", group=GROUP_CORE),
    Exercise("YTW-Raises", "2–3", "8–12 pro Buchstabe", group=GROUP_UPPER),
]

# Zusatzuebungen je Fokus aus der Bibliothek (Kraft-Recherche B/C/D), die in A/B sonst fehlen
_FOCUS_EXTRAS: dict[str, dict[str, list[Exercise]]] = {
    GROUP_CORE: {
        "A": [Exercise("Plank (Unterarmstütz)", "3–4", "30–60 s", group=GROUP_CORE,
                       note="Progression: Plank mit lateralem Step oder Plank-to-Pushup")],
        "B": [
            Exercise("Plank (Unterarmstütz)", "3–4", "30–60 s", max_phase=1, group=GROUP_CORE),
            Exercise("Reverse Crunch / Leg Raises", "3", "10–15", min_phase=2, group=GROUP_CORE,
                     note="Langsam, Lendenwirbel am Boden"),
        ],
    },
    GROUP_UPPER: {
        "A": [Exercise("Scapular Push-ups", "2", "10–12", group=GROUP_UPPER,
                       note="Arme gestreckt, nur die Schulterblätter bewegen (Serratus)")],
        # ab Phase 2 ist die Uebung regulaer in B (dann reicht +1 Satz)
        "B": [Exercise("Band Pull-Aparts + Face Pulls", "2–3", "15–20", max_phase=1, group=GROUP_UPPER)],
    },
    GROUP_LEGS: {
        "A": [Exercise("Clamshells", "2", "15 je Seite", leg=True, group=GROUP_LEGS,
                       note="Mit Mini-Band, langsam (Glute medius)")],
        "B": [Exercise("Step-ups", "3", "10 je Bein", leg=True, group=GROUP_LEGS,
                       note="Niedrige Stufe, aus dem Gesäss drücken, 2–3 Wdh. in Reserve")],
    },
}

# Fokus-Themen, die die Krafteinheit veraendern (Mobility wirkt nur auf die Routine)
STRENGTH_FOCUSES: frozenset[str] = frozenset(_FOCUS_EXTRAS)

_SESSIONS: dict[str, tuple[str, list[Exercise]]] = {
    "A": ("Krafteinheit A (Push/Core/Glute)", _SESSION_A),
    "B": ("Krafteinheit B (Pull/Core/Bein-Stabilität)", _SESSION_B),
}

MOBILITY_ROUTINE: list[Exercise] = [
    Exercise("Kniender Hüftbeuger-Stretch", "2", "30–45 s je Seite", note="Becken untertucken, kein Hohlkreuz",
             group=GROUP_MOBILITY),
    Exercise("90/90 Hüftrotationen", "1", "8–10 Wechsel je Seite", group=GROUP_MOBILITY),
    Exercise("Open Book", "1", "6–8 je Seite, 2 s halten", group=GROUP_MOBILITY),
    Exercise("Cat-Cow / Quadruped Rotation", "1", "8 bzw. 6 je Seite", group=GROUP_MOBILITY),
    Exercise("BWS-Extension über Foam Roller", "1", "6–8 langsam", group=GROUP_MOBILITY),
    Exercise("Wall Angels / Wall Slides", "1", "8–10", group=GROUP_MOBILITY),
    Exercise("Pigeon (Glute-Stretch)", "1", "30–60 s je Seite", note="bei Bedarf", group=GROUP_MOBILITY),
]

# Bei Rueckenschmerz nach langen Fahrten: Core-Frequenz erhoehen (McGill: kurze, haeufige Belastungen)
MCGILL_BIG_3: list[Exercise] = [
    Exercise("McGill Curl-Up", "1", "Pyramide 5-3-1, je 8–10 s halten", note="Core täglich"),
    Exercise("Side Plank", "2", "10–20 s je Seite", note="Core täglich"),
    Exercise("Bird Dog", "2", "6 je Seite, 3–5 s halten", note="Core täglich"),
]

# Core-Benchmarks uebertroffen -> diese Uebungen vor ihrer Phase (Kraft-Recherche, Recommendations 5)
CORE_ADVANCED_UNLOCKS: frozenset[str] = frozenset({"Hollow Body Hold", "Anti-rotatorischer Band-Hold (Pallof)"})

REDUCED_NOTE = "Reduziert (Beine platt): Beinübungen entfallen, Volumen ~20 % runter (je Übung 1 Satz weniger)."


def shift_numbers(text: str, delta: int) -> str:
    """Erhoeht alle Zahlen einer Angabe: ("2–3", 1) -> "3–4", ("50–55", 10) -> "60–65"."""
    return re.sub(r"\d+", lambda m: str(int(m.group()) + delta), text)


def focus_note(focus: str) -> str:
    """Hinweistext zum angewendeten Kraft-Fokus."""
    label = FOCUS_OPTIONS[focus]
    return f"Fokus {label}: +1 Satz auf {label}-Übungen, Zusatzübung, ca. +{FOCUS_EXTRA_MINUTES} min."


def mobility_routine(focus: str = FOCUS_NONE, core_daily: bool = False) -> list[Exercise]:
    """Taegliche Mobility-Routine.

    Args:
        focus: Kraft-Fokus; "mobility" = +1 Satz je Drill, Pigeon fest statt bei Bedarf;
            "core" = McGill Big 3 taeglich (Kraft-Recherche: Core profitiert von hoher Frequenz).
        core_daily: McGill Big 3 aus dem Check-in-Review (Ruecken nach langen Fahrten).

    Returns:
        Liste der Uebungen.
    """
    routine = list(MOBILITY_ROUTINE)
    if focus == GROUP_MOBILITY:
        routine = [
            replace(e, sets=shift_numbers(e.sets, 1), note=None if e.note == "bei Bedarf" else e.note)
            for e in routine
        ]
    if core_daily or focus == GROUP_CORE:
        routine += MCGILL_BIG_3
    return routine


def _stage_note(exercise: Exercise, stages: ExerciseStages) -> str | None:
    """Stufe aus dem Kraft-Benchmark fuer eine Uebung; None = keine Aussage."""
    if exercise.name == "Liegestütz-Progression" and stages.pushup_variant:
        return f"Deine Stufe: {PUSHUP_VARIANTS[stages.pushup_variant]} · 2 s runter / 1 s hoch"
    if exercise.name == "Inverted Rows (Tischkanten-Rudern)" and stages.rows_feet_elevated is not None:
        return "Deine Stufe: Füsse erhöht" if stages.rows_feet_elevated else "Deine Stufe: Füsse am Boden"
    if exercise.name == "Side Plank" and stages.side_plank_straight is not None:
        return "Deine Stufe: Beine gestreckt" if stages.side_plank_straight else "Deine Stufe: Knie gebeugt"
    if exercise.name == "Glute Bridge (Progression → Single-Leg)" and stages.glute_bridge_single_leg is not None:
        return "Deine Stufe: einbeinig" if stages.glute_bridge_single_leg else "Deine Stufe: beidbeinig"
    if exercise.name in CORE_ADVANCED_UNLOCKS and stages.core_advanced:
        return "Freigeschaltet durch deinen Core-Benchmark"
    return None


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
    session_id: str,
    phase: StrengthPhase,
    note: str | None = None,
    reduced: bool = False,
    focus: str = FOCUS_NONE,
    stages: ExerciseStages | None = None,
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
        focus: Kraft-Fokus (siehe FOCUS_OPTIONS). Core/Oberkoerper/Beine: +1 Satz auf die Gruppe,
            Zusatzuebung, Dauer +FOCUS_EXTRA_MINUTES. Mobility wirkt nur auf mobility_routine.
        stages: Stufen aus dem Kraft-Benchmark (Hinweis „Deine Stufe“, Core-Freischaltung).

    Returns:
        StrengthSession mit den Uebungen der Phase.

    Raises:
        ValueError: bei unbekannter session_id oder unbekanntem Fokus.
    """
    if session_id not in _SESSIONS:
        raise ValueError(f"unbekannte Krafteinheit: {session_id}")
    if focus not in FOCUS_OPTIONS:
        raise ValueError(f"unbekannter Kraft-Fokus: {focus}")
    title, library = _SESSIONS[session_id]
    strength_focus = focus in STRENGTH_FOCUSES
    if strength_focus:
        library = library + _FOCUS_EXTRAS[focus][session_id]
    exercises = []
    stages = stages or ExerciseStages()
    for exercise in library:
        unlocked = stages.core_advanced and exercise.name in CORE_ADVANCED_UNLOCKS
        in_phase = exercise.min_phase <= phase.number <= exercise.max_phase or unlocked
        if not in_phase or (reduced and exercise.leg):
            continue
        stage_note = _stage_note(exercise, stages)
        if stage_note:
            exercise = replace(exercise, note=stage_note)
        if exercise.scaled:
            exercise = replace(exercise, sets=phase.sets or exercise.sets, reps=phase.reps, rest=phase.rest)
        if strength_focus and exercise.group == focus:
            exercise = replace(exercise, sets=shift_numbers(exercise.sets, 1))
        exercises.append(exercise)
    notes = [n for n in (note, REDUCED_NOTE if reduced else None, focus_note(focus) if strength_focus else None) if n]
    session = StrengthSession(
        session_id=session_id, title=title, phase=phase, exercises=exercises, note=" ".join(notes) or None, focus=focus
    )
    if strength_focus:
        session = replace(session, duration_minutes=shift_numbers(session.duration_minutes, FOCUS_EXTRA_MINUTES))
    return session
