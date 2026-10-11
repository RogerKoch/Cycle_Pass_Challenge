"""Alternativuebungen fuer Kraftuebungen, deren Material fehlt (Tisch, Widerstandsband).

Schluessel sind die Namen der Originaluebungen aus engine.strength_sessions. Die Reihenfolge der
Alternativen ist die Praeferenz: beim automatischen Tausch (Profil „Material fehlt“) gewinnt die
erste Alternative, die selbst kein fehlendes Material braucht.
"""

from dataclasses import dataclass, replace

from backend.engine.strength_sessions import Exercise

EQUIPMENT_TABLE = "table"
EQUIPMENT_BANDS = "bands"
EQUIPMENT_OPTIONS: dict[str, str] = {
    EQUIPMENT_TABLE: "Kein stabiler Tisch",
    EQUIPMENT_BANDS: "Keine Widerstandsbänder",
}


@dataclass(frozen=True)
class Alternative:
    """Eine Alternativuebung; Saetze/Pause/Phasenfenster bleiben die der Originaluebung."""

    name: str
    note: str
    requires: frozenset[str] = frozenset()
    reps: str | None = None  # nur wenn die Dosierung des Originals nicht passt


_SIDE_LEG_RAISE = Alternative(
    "Seitliches Beinheben (Seitenlage)",
    "Oberes Bein gestreckt heben, Becken stabil, langsam senken (Glute medius)",
)

# Material, das die Originaluebung braucht
REQUIRES: dict[str, frozenset[str]] = {
    "Inverted Rows (Tischkanten-Rudern)": frozenset({EQUIPMENT_TABLE}),
    "Band Pull-Aparts + Face Pulls": frozenset({EQUIPMENT_BANDS}),
    "Anti-rotatorischer Band-Hold (Pallof)": frozenset({EQUIPMENT_BANDS}),
    "Band External Rotation": frozenset({EQUIPMENT_BANDS}),
    "Lateral Band Walks": frozenset({EQUIPMENT_BANDS}),
    "Clamshells": frozenset({EQUIPMENT_BANDS}),
}

ALTERNATIVES: dict[str, list[Alternative]] = {
    "Inverted Rows (Tischkanten-Rudern)": [
        Alternative("Band-Rudern", "Band an Türklinke/Pfosten, Schulterblätter zusammen",
                    requires=frozenset({EQUIPMENT_BANDS})),
        Alternative("Handtuch-Rudern an Türklinke", "Handtuch um beide Klinken einer geschlossenen Tür, "
                    "zurücklehnen und rudern; Füsse näher = schwerer"),
        Alternative("Rucksack-Rudern vorgebeugt", "Gefüllter Rucksack, Hüfte gebeugt, Rücken gerade, "
                    "Ellbogen zur Hüfte"),
    ],
    "Band Pull-Aparts + Face Pulls": [
        Alternative("Rucksack Reverse Fly", "Vorgebeugt, Arme seitlich anheben, Schulterblätter zusammen"),
        Alternative("Prone T-Raises (Bauchlage)", "Arme seitlich anheben, Daumen nach oben, 1–2 s halten"),
    ],
    "Anti-rotatorischer Band-Hold (Pallof)": [
        Alternative("Plank Shoulder Taps", "Hüfte ruhig halten, keine Rotation; abwechselnd Schulter antippen",
                    reps="10–16 Taps"),
    ],
    "Band External Rotation": [
        Alternative("Seitlage Aussenrotation (Wasserflasche)", "Ellbogen am Körper, Handtuch zwischen Ellbogen "
                    "und Rippen, Flasche nach oben drehen"),
    ],
    "Lateral Band Walks": [_SIDE_LEG_RAISE],
    "Clamshells": [_SIDE_LEG_RAISE],
}


def alternatives_for(name: str) -> list[Alternative]:
    """Alternativen zu einer Originaluebung (leer, wenn es keine gibt)."""
    return ALTERNATIVES.get(name, [])


def _auto_alternative(name: str, missing: frozenset[str]) -> Alternative | None:
    """Erste Alternative ohne fehlendes Material, falls das Original fehlendes Material braucht."""
    if not REQUIRES.get(name, frozenset()) & missing:
        return None
    return next((a for a in alternatives_for(name) if not a.requires & missing), None)


def apply_swaps(exercise: Exercise, swaps: dict[str, str], missing: frozenset[str]) -> Exercise:
    """Ersetzt eine Uebung durch ihre Alternative (manueller Tausch vor Material-Automatik).

    Die Alternative erbt Saetze, Pause, Gruppe und Beinflag des Originals. Nicht tauschbare
    Uebungen und unbekannte Alternativnamen bleiben unveraendert.

    Args:
        exercise: Uebung der aufgebauten Einheit.
        swaps: Originalname -> Name der gewaehlten Alternative (dauerhaft, aus der DB).
        missing: Fehlendes Material aus dem Profil.

    Returns:
        Die Alternative (mit `original`) oder die unveraenderte Uebung; `alternatives` ist gefuellt,
        wenn es Alternativen gibt.
    """
    options = alternatives_for(exercise.name)
    if not options:
        return exercise
    names = [a.name for a in options]
    chosen = next((a for a in options if a.name == swaps.get(exercise.name)), None)
    chosen = chosen or _auto_alternative(exercise.name, missing)
    if chosen is None:
        return replace(exercise, alternatives=names)
    return replace(
        exercise,
        name=chosen.name,
        reps=chosen.reps or exercise.reps,
        note=chosen.note,
        original=exercise.name,
        alternatives=names,
    )
