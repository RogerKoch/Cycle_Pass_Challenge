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
from dataclasses import dataclass, field, replace

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

# Material-Profil (Profilfeld equipment_profile): jedes Profil hat seine eigenen Uebungen
PROFILE_BODYWEIGHT = "bodyweight"
PROFILE_BANDS = "bands"
PROFILE_NEOLYMP = "neolymp"
DEFAULT_PROFILE = PROFILE_BODYWEIGHT
EQUIPMENT_PROFILES: dict[str, dict[str, str]] = {
    PROFILE_BODYWEIGHT: {"label": "Nur Körpergewicht", "hint": "Kein Tisch, Rucksack oder Band"},
    PROFILE_BANDS: {"label": "Einfache Bänder", "hint": "Bänder an Türklinke/Pfosten, Core mit Körpergewicht"},
    PROFILE_NEOLYMP: {"label": "NEOLYMP-Set", "hint": "Bänderstange, Griffe, Fussschlaufen, kurzes Band"},
}


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
    original: str | None = None  # Name der ersetzten Uebung, wenn getauscht (engine.strength_alternatives)
    alternatives: list[str] = field(default_factory=list)  # tauschbar gegen diese Uebungen
    hold: dict | None = None  # Halte-Zyklen fuer den Timer, siehe hold_cycle()


def hold_cycle(hold_s: int, move_s: int, reps: int | list[int], per_side: bool = False) -> dict:
    """Halte-Zyklus fuer den Timer: je Wiederholung `move_s` Bewegung, dann `hold_s` halten.

    Args:
        hold_s: Haltedauer pro Wiederholung in Sekunden.
        move_s: Dauer der Bewegung (z. B. Curl hoch) in Sekunden.
        reps: Wiederholungen pro Satz; Liste = ein Satz je Eintrag (Pyramide 5-3-1).
        per_side: je Seite ausfuehren (Seitenwechsel zwischen den Seiten).

    Returns:
        Dict fuer Exercise.hold.
    """
    return {"hold_s": hold_s, "move_s": move_s, "reps": reps, "per_side": per_side}


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

# --- Uebungslisten je Material-Profil ---------------------------------------------------------------
# Jedes Profil ist eigenstaendig (keine Hierarchie). Gemeinsame Uebungen sind geteilte Objekte.

_WARMUP_A = Exercise("Aufwärmen/Mobility", "1", "8 min", note="Hüftbeuger, Open Book, Cat-Cow, Wall Angels")
_WARMUP_B = Exercise("Aufwärmen/Mobility", "1", "8 min", note="90/90, BWS-Extension, Clamshells als Aktivierung")
_GLUTE_BRIDGE = Exercise("Glute Bridge (Progression → Single-Leg)", "3", "12–15", scaled=True, group=GROUP_LEGS,
                         note="Im Gesäss spüren, nicht im Hamstring/unteren Rücken")
_HOLLOW = Exercise("Hollow Body Hold", "3", "20–40 s", min_phase=2, group=GROUP_CORE)
_DEAD_BUG = Exercise("Dead Bug", "3", "8–10 je Seite", note="Lendenwirbel flach am Boden, langsam", group=GROUP_CORE)
_SIDE_PLANK = Exercise("Side Plank", "3", "15–30 s je Seite", note="Phase 1 Knie gebeugt, ab Phase 2 gestreckt",
                       group=GROUP_CORE)
_PALLOF = Exercise("Anti-rotatorischer Band-Hold (Pallof)", "3", "20–30 s je Seite", min_phase=3, group=GROUP_CORE)
_BULGARIAN = Exercise("Bulgarian Split Squat", "3", "6–10 je Bein", min_phase=2, scaled=True, leg=True,
                      group=GROUP_LEGS, note="Wdh. je Bein, 2–3 Wdh. in Reserve")
_SINGLE_LEG_DL = Exercise("Single-Leg Deadlift", "2–3", "8 je Bein", min_phase=2, leg=True,
                          note="Hüfthinge, Balance", group=GROUP_LEGS)
_COPENHAGEN = Exercise("Copenhagen Plank", "2", "10–20 s je Seite", min_phase=3, group=GROUP_LEGS)
_MCGILL = Exercise("McGill Curl-Up", "1", "Pyramide 5-3-1, je 8–10 s halten", note="Kein Nacken-Crunch",
                   group=GROUP_CORE, hold=hold_cycle(8, 3, [5, 3, 1]))
_BIRD_DOG = Exercise("Bird Dog", "3", "6–8 je Seite, 3–5 s halten", note="Neutrale Wirbelsäule", group=GROUP_CORE,
                     hold=hold_cycle(5, 3, 6, per_side=True))
_YTW = Exercise("YTW-Raises", "2–3", "8–12 pro Buchstabe", group=GROUP_UPPER)
_STEP_UPS = Exercise("Step-ups", "3", "10 je Bein", leg=True, group=GROUP_LEGS,
                     note="Niedrige Stufe, aus dem Gesäss drücken, 2–3 Wdh. in Reserve")
_PLANK = Exercise("Plank (Unterarmstütz)", "3–4", "30–60 s", group=GROUP_CORE)
_REVERSE_CRUNCH = Exercise("Reverse Crunch / Leg Raises", "3", "10–15", min_phase=2, group=GROUP_CORE,
                           note="Langsam, Lendenwirbel am Boden")

# Koerpergewicht und einfache Baender: Push/Pull-Uebungen aus der Kraft-Recherche
_PUSHUP = Exercise("Liegestütz-Progression", "3", "8–15", scaled=True, group=GROUP_UPPER,
                   note="Wand → Inkline → Knie → Standard → Füsse erhöht; 2 s runter / 1 s hoch")
_PIKE = Exercise("Pike Push-ups", "3", "6–10", min_phase=2, group=GROUP_UPPER)
_SCAPULAR_PUSHUPS = Exercise("Scapular Push-ups", "2", "10–12", group=GROUP_UPPER,
                             note="Arme gestreckt, nur die Schulterblätter bewegen (Serratus)")

# Koerpergewicht: nur der eigene Koerper (kein Tisch, Rucksack, Band)
_BW_SHOULDER_TAPS = Exercise("Plank Shoulder Taps", "3", "10–16 Taps", min_phase=3, group=GROUP_CORE,
                             note="Hüfte ruhig halten, keine Rotation; abwechselnd Schulter antippen")
_BW_EXTERNAL_ROTATION = Exercise("Seitlage Aussenrotation (Wasserflasche)", "2", "12–15 je Seite", group=GROUP_UPPER,
                                 note="Ellbogen am Körper, Handtuch zwischen Ellbogen und Rippen, Flasche nach oben")
_BW_ROW = Exercise("Superman-Pull (Bauchlage-Rudern)", "3–4", "8–15", scaled=True, group=GROUP_UPPER,
                   note="Bauchlage, Arme vorne gestreckt, Ellbogen zur Hüfte ziehen, Schulterblätter zusammen")
_BW_T_RAISE = Exercise("Prone T-Raises (Bauchlage)", "2–3", "12–15", group=GROUP_UPPER,
                       note="Arme seitlich anheben, Daumen nach oben, 1–2 s halten")
_BW_SIDE_LEG_RAISE = Exercise("Seitliches Beinheben (Seitenlage)", "2", "12–15 je Seite", leg=True,
                              group=GROUP_LEGS,
                              note="Oberes Bein gestreckt heben, Becken stabil, langsam senken (Glute medius)")
_BW_CLAMSHELLS = Exercise("Clamshells", "2", "15 je Seite", leg=True, group=GROUP_LEGS,
                          note="Langsam, Becken stabil (Glute medius)")

# Einfache Baender: Band an Tuerklinke/Pfosten
_BAND_ER = Exercise("Band External Rotation", "2", "12–15 je Seite", note="Handtuch zwischen Ellbogen und Rippen",
                    group=GROUP_UPPER)
_BAND_ROW = Exercise("Band-Rudern", "3–4", "8–15", scaled=True, group=GROUP_UPPER,
                     note="Band an Türklinke/Pfosten, Schulterblätter zusammen")
_PULL_APART = Exercise("Band Pull-Aparts + Face Pulls", "2–3", "15–20", min_phase=2, group=GROUP_UPPER)
_BAND_WALKS = Exercise("Lateral Band Walks", "2", "10 Schritte je Richtung", leg=True, group=GROUP_LEGS,
                       note="Leichte Kniebeuge, Knie nicht einknicken")
_BAND_CLAMSHELLS = replace(_BW_CLAMSHELLS, note="Mit Mini-Band, langsam (Glute medius)")

# NEOLYMP-Set (Baenderstange, Griffe, Fussschlaufen); Namen = Titel aus dem NEOLYMP-Trainingsplan
_NL_CHEST_PRESS = Exercise("Brustpresse mit Bänderstange", "3", "8–15", scaled=True, group=GROUP_UPPER,
                           note="Rückenlage, Band hinter den Schulterblättern, Ellbogen am Boden; Handgelenke "
                                "neutral. Steigern über Bandstärke statt Liegestütz")
_NL_SHOULDER_PRESS = Exercise("Schulterdrücken mit Bänderstange (Kniestand)", "3", "8–15", scaled=True,
                              group=GROUP_UPPER, note="Kniestand, Rücken gerade, Stange hinter dem Kopf nach oben")
_NL_BUTTERFLY = Exercise("Butterfly einarmig mit Griff", "2", "12–15 je Seite", min_phase=2, group=GROUP_UPPER,
                         note="Arm leicht angewinkelt, Griff zur Brustmitte, kurz halten")
_NL_EXTERNAL_ROTATION = Exercise("Schulterrotation außen mit Griff", "2", "12–15 je Seite", group=GROUP_UPPER,
                                 note="Ellbogen im 90°-Winkel eng am Körper, Unterarm nach aussen drehen")
_NL_ROW = Exercise("Rudern zur Brust mit Bänderstange", "3–4", "8–15", scaled=True, group=GROUP_UPPER,
                   note="Sitzend, Rücken gerade, Ellbogen nach aussen, Stange zur oberen Brust")
_NL_LAT_PULL = Exercise("Latzug zur Brust mit Bänderstange", "3", "8–15", scaled=True, group=GROUP_UPPER,
                        note="Stange zur Brust (nicht hinter den Nacken), Rücken gerade")
_NL_REAR_FLY = Exercise("Butterfly reverse einarmig mit Griff", "2", "12–15 je Seite", min_phase=2, group=GROUP_UPPER,
                        note="Arm leicht angewinkelt, Griff seitlich vom Körper wegziehen")
_NL_LEG_EXTENSION = Exercise("Seitliches Beinstrecken mit Fußschlaufe", "2", "12 je Seite", leg=True,
                             group=GROUP_LEGS, note="Mit einer Hand an Tür/Stuhl abstützen, Rücken gerade")
_NL_KICKBACKS = Exercise("Kickbacks mit Fußschlaufe", "2", "12 je Seite", leg=True, group=GROUP_LEGS,
                         note="Vierfüsserstand auf den Unterarmen (Handgelenke schonen), Rücken gerade")
_NL_LEG_RAISE = Exercise("Beinheben liegend mit Fußschlaufe", "3", "10–15", min_phase=2, group=GROUP_CORE,
                         note="Langsam, Lendenwirbel am Boden")
_NL_LATERAL_RAISE = Exercise("Seitenheben mit Griff", "2", "12–15 je Seite", group=GROUP_UPPER,
                             note="Fuss auf dem Band, Arm seitlich bis Schulterhöhe")
_NL_TRICEPS = Exercise("Einarmiges Trizepstrecken über Kopf mit Griff", "2", "12–15 je Seite", group=GROUP_UPPER,
                       note="Schrittstellung, Arm über dem Kopf nach vorne strecken")
_NL_REAR_FLY_PHASE1 = replace(_NL_REAR_FLY, min_phase=1, max_phase=1)
_NL_CURLS = Exercise("Einarmige Curls mit Griff", "2", "12–15 je Seite", group=GROUP_UPPER,
                     note="Ellbogen eng am Körper, Fuss im Band")

_LIBRARY: dict[str, dict[str, list[Exercise]]] = {
    PROFILE_BODYWEIGHT: {
        "A": [_WARMUP_A, _GLUTE_BRIDGE, _PUSHUP, _PIKE, _HOLLOW, _DEAD_BUG, _SIDE_PLANK, _BW_SHOULDER_TAPS,
              _BW_EXTERNAL_ROTATION],
        "B": [_WARMUP_B, _BW_ROW, _BULGARIAN, _SINGLE_LEG_DL, _BW_SIDE_LEG_RAISE, _COPENHAGEN, _MCGILL, _BIRD_DOG,
              _YTW],
    },
    PROFILE_BANDS: {
        "A": [_WARMUP_A, _GLUTE_BRIDGE, _PUSHUP, _PIKE, _HOLLOW, _DEAD_BUG, _SIDE_PLANK, _PALLOF, _BAND_ER],
        "B": [_WARMUP_B, _BAND_ROW, _PULL_APART, _BULGARIAN, _SINGLE_LEG_DL, _BAND_WALKS, _COPENHAGEN, _MCGILL,
              _BIRD_DOG, _YTW],
    },
    PROFILE_NEOLYMP: {
        "A": [_WARMUP_A, _GLUTE_BRIDGE, _NL_CHEST_PRESS, _NL_SHOULDER_PRESS, _NL_BUTTERFLY, _HOLLOW, _DEAD_BUG,
              _SIDE_PLANK, _PALLOF, _NL_EXTERNAL_ROTATION],
        "B": [_WARMUP_B, _NL_ROW, _NL_LAT_PULL, _NL_REAR_FLY, _BULGARIAN, _SINGLE_LEG_DL, _NL_LEG_EXTENSION,
              _COPENHAGEN, _MCGILL, _BIRD_DOG, _YTW],
    },
}

# Zusatzuebungen je Fokus aus der Bibliothek (Kraft-Recherche B/C/D), die in A/B sonst fehlen
_PLANK_A = replace(_PLANK, note="Progression: Plank mit lateralem Step oder Plank-to-Pushup")
_PLANK_B = replace(_PLANK, max_phase=1)

_FOCUS_EXTRAS: dict[str, dict[str, dict[str, list[Exercise]]]] = {
    PROFILE_BODYWEIGHT: {
        GROUP_CORE: {"A": [_PLANK_A], "B": [_PLANK_B, _REVERSE_CRUNCH]},
        GROUP_UPPER: {"A": [_SCAPULAR_PUSHUPS], "B": [_BW_T_RAISE]},
        GROUP_LEGS: {"A": [_BW_CLAMSHELLS], "B": [_STEP_UPS]},
    },
    PROFILE_BANDS: {
        GROUP_CORE: {"A": [_PLANK_A], "B": [_PLANK_B, _REVERSE_CRUNCH]},
        # ab Phase 2 sind die Pull-Aparts regulaer in B (dann reicht +1 Satz)
        GROUP_UPPER: {"A": [_SCAPULAR_PUSHUPS], "B": [replace(_PULL_APART, min_phase=1, max_phase=1)]},
        GROUP_LEGS: {"A": [_BAND_CLAMSHELLS], "B": [_STEP_UPS]},
    },
    PROFILE_NEOLYMP: {
        GROUP_CORE: {"A": [_PLANK_A], "B": [_PLANK_B, _NL_LEG_RAISE]},
        GROUP_UPPER: {"A": [_NL_LATERAL_RAISE, _NL_TRICEPS], "B": [_NL_REAR_FLY_PHASE1, _NL_CURLS]},
        GROUP_LEGS: {"A": [_NL_KICKBACKS], "B": [_STEP_UPS]},
    },
}

# Fokus-Themen, die die Krafteinheit veraendern (Mobility wirkt nur auf die Routine)
STRENGTH_FOCUSES: frozenset[str] = frozenset(_FOCUS_EXTRAS[DEFAULT_PROFILE])

_SESSION_TITLES: dict[str, str] = {
    "A": "Krafteinheit A (Push/Core/Glute)",
    "B": "Krafteinheit B (Pull/Core/Bein-Stabilität)",
}

MOBILITY_ROUTINE: list[Exercise] = [
    Exercise("Kniender Hüftbeuger-Stretch", "2", "30–45 s je Seite", note="Becken untertucken, kein Hohlkreuz",
             group=GROUP_MOBILITY),
    Exercise("90/90 Hüftrotationen", "1", "8–10 Wechsel je Seite", group=GROUP_MOBILITY),
    Exercise("Open Book", "1", "6–8 je Seite, 2 s halten", group=GROUP_MOBILITY,
             hold=hold_cycle(2, 3, 6, per_side=True)),
    Exercise("Cat-Cow / Quadruped Rotation", "1", "8 bzw. 6 je Seite", group=GROUP_MOBILITY),
    Exercise("BWS-Extension über Foam Roller", "1", "6–8 langsam", group=GROUP_MOBILITY),
    Exercise("Wall Angels / Wall Slides", "1", "8–10", group=GROUP_MOBILITY),
    Exercise("Pigeon (Glute-Stretch)", "1", "30–60 s je Seite", note="bei Bedarf", group=GROUP_MOBILITY),
]

# Bei Rueckenschmerz nach langen Fahrten: Core-Frequenz erhoehen (McGill: kurze, haeufige Belastungen)
MCGILL_BIG_3: list[Exercise] = [
    Exercise("McGill Curl-Up", "1", "Pyramide 5-3-1, je 8–10 s halten", note="Core täglich",
             hold=hold_cycle(8, 3, [5, 3, 1])),
    Exercise("Side Plank", "2", "10–20 s je Seite", note="Core täglich"),
    Exercise("Bird Dog", "2", "6 je Seite, 3–5 s halten", note="Core täglich",
             hold=hold_cycle(5, 3, 6, per_side=True)),
]

# Core-Benchmarks uebertroffen -> diese Uebungen vor ihrer Phase (Kraft-Recherche, Recommendations 5)
CORE_ADVANCED_UNLOCKS: frozenset[str] = frozenset({
    "Hollow Body Hold", "Anti-rotatorischer Band-Hold (Pallof)", "Plank Shoulder Taps",  # Taps = Pallof ohne Band
})

# Uebungen mit Benchmark-Stufe: Wdh.-Bereich der Bibliothek (8–15), die Phase bestimmt nur Saetze und Pause
STAGED_EXERCISES: frozenset[str] = frozenset({"Liegestütz-Progression", "Glute Bridge (Progression → Single-Leg)"})
RIR_NOTE = "2–3 Wdh. in Reserve"

REDUCED_NOTE = "Reduziert (Beine platt): Beinübungen entfallen, Volumen ~20 % runter (je Übung 1 Satz weniger)."


def shift_numbers(text: str, delta: int) -> str:
    """Erhoeht alle Zahlen einer Angabe: ("2–3", 1) -> "3–4", ("50–55", 10) -> "60–65"."""
    return re.sub(r"\d+", lambda m: str(int(m.group()) + delta), text)


def focus_note(focus: str) -> str:
    """Hinweistext zum angewendeten Kraft-Fokus."""
    label = FOCUS_OPTIONS[focus]
    return f"Fokus {label}: +1 Satz auf {label}-Übungen, Zusatzübung, ca. +{FOCUS_EXTRA_MINUTES} min."


def mobility_routine(focus: str = FOCUS_NONE, core_daily: bool = False, double_day: bool = False) -> list[Exercise]:
    """Taegliche Mobility-Routine.

    Args:
        focus: Kraft-Fokus; "mobility" = +1 Satz je Drill, Pigeon fest statt bei Bedarf;
            "core" = McGill Big 3 taeglich (Kraft-Recherche: Core profitiert von hoher Frequenz).
        core_daily: McGill Big 3 aus dem Check-in-Review (Ruecken nach langen Fahrten).
        double_day: Rad und Kraft am selben Tag; das Aufwaermen der Krafteinheit enthaelt schon Mobility, daher
            entfaellt die Routine (nur McGill Big 3 bleiben, falls Core taeglich vorgesehen ist).

    Returns:
        Liste der Uebungen.
    """
    if double_day:
        return list(MCGILL_BIG_3) if core_daily or focus == GROUP_CORE else []
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
        tempo = "3 s runter / 1 s Pause unten / 1 s hoch" if stages.pushup_slow_tempo else "2 s runter / 1 s hoch"
        return f"Deine Stufe: {PUSHUP_VARIANTS[stages.pushup_variant]} · {tempo}"
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
    profile: str = DEFAULT_PROFILE,
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
        profile: Material-Profil (siehe EQUIPMENT_PROFILES); bestimmt die Uebungen.

    Returns:
        StrengthSession mit den Uebungen der Phase.

    Raises:
        ValueError: bei unbekannter session_id, unbekanntem Fokus oder unbekanntem Profil.
    """
    if profile not in _LIBRARY:
        raise ValueError(f"unbekanntes Material-Profil: {profile}")
    if session_id not in _SESSION_TITLES:
        raise ValueError(f"unbekannte Krafteinheit: {session_id}")
    if focus not in FOCUS_OPTIONS:
        raise ValueError(f"unbekannter Kraft-Fokus: {focus}")
    title, library = _SESSION_TITLES[session_id], _LIBRARY[profile][session_id]
    strength_focus = focus in STRENGTH_FOCUSES
    if strength_focus:
        library = library + _FOCUS_EXTRAS[profile][focus][session_id]
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
            reps = exercise.reps if exercise.name in STAGED_EXERCISES else phase.reps
            exercise = replace(exercise, sets=phase.sets or exercise.sets, reps=reps, rest=phase.rest)
        if exercise.name in STAGED_EXERCISES:
            exercise = replace(exercise, note=" · ".join(n for n in (exercise.note, RIR_NOTE) if n))
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
