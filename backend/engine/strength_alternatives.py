"""Alternativuebungen, gegen die man eine Uebung dauerhaft tauschen kann.

Schluessel sind die Namen der Originaluebungen aus engine.strength_sessions. Das Material steckt schon
in der Uebungsliste des Material-Profils (kein automatischer Tausch): ein Original kommt nur in den
Profilen vor, in denen es moeglich ist, und seine Alternativen sind dort ebenfalls machbar.
"""

from dataclasses import dataclass, replace

from backend.engine.strength_sessions import Exercise


@dataclass(frozen=True)
class Alternative:
    """Eine Alternativuebung; Saetze/Pause/Phasenfenster bleiben die der Originaluebung."""

    name: str
    note: str
    reps: str | None = None  # nur wenn die Dosierung des Originals nicht passt


_SIDE_LEG_RAISE = Alternative(
    "Seitliches Beinheben (Seitenlage)",
    "Oberes Bein gestreckt heben, Becken stabil, langsam senken (Glute medius)",
)

ALTERNATIVES: dict[str, list[Alternative]] = {
    # einfache Baender
    "Band-Rudern": [
        Alternative("Handtuch-Rudern an Türklinke", "Handtuch um beide Klinken einer geschlossenen Tür, "
                    "zurücklehnen und rudern; Füsse näher = schwerer"),
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
    # NEOLYMP-Set
    "Brustpresse mit Bänderstange": [
        Alternative("Brustpresse mit Griffen", "Rückenlage, Band hinter den Schulterblättern fixiert, "
                    "Ellbogen am Boden, Arme fast vollständig strecken"),
    ],
    "Schulterdrücken mit Bänderstange (Kniestand)": [
        Alternative("Einarmiges Schulterdrücken mit Griff", "Kniestand, Griff auf Kopfhöhe, Arm nach oben "
                    "strecken; je Seite", reps="12–15 je Seite"),
    ],
    "Rudern zur Brust mit Bänderstange": [
        Alternative("Rudern vorgebeugt mit Bänderstange", "Leicht vorgebeugt, Rücken gerade, Stange auf "
                    "Bauchnabelhöhe ziehen, Ellbogen nach aussen"),
        Alternative("Rudern zur Brust einarmig mit Griff", "Sitzend, Rücken gerade, Griff zur Brust ziehen; "
                    "je Seite", reps="10–12 je Seite"),
    ],
    "Butterfly reverse einarmig mit Griff": [
        Alternative("Seitenheben vorgebeugt mit Griff", "Fuss auf dem Band, vorgebeugt, Arm seitlich anheben; "
                    "je Seite", reps="12–15 je Seite"),
    ],
    "Single-Leg Deadlift": [
        Alternative("Kreuzheben mit gestreckten Beinen mit Bänderstange", "Füsse auf dem Band, Knie leicht "
                    "gebeugt, Rücken gerade, aufrichten; Last über die Bandstärke", reps="10–15"),
    ],
    "Seitliches Beinstrecken mit Fußschlaufe": [
        Alternative("Seitlicher Ausfallschritt mit kurzem Fitnessband", "Band oberhalb der Knöchel, grosser "
                    "Schritt zur Seite in die Kniebeuge, Fuss nachziehen", reps="12 je Seite"),
    ],
}


def alternatives_for(name: str) -> list[Alternative]:
    """Alternativen zu einer Originaluebung (leer, wenn es keine gibt)."""
    return ALTERNATIVES.get(name, [])


def apply_swaps(exercise: Exercise, swaps: dict[str, str]) -> Exercise:
    """Ersetzt eine Uebung durch die gewaehlte Alternative.

    Die Alternative erbt Saetze, Pause, Gruppe und Beinflag des Originals. Nicht tauschbare
    Uebungen und unbekannte Alternativnamen bleiben unveraendert.

    Args:
        exercise: Uebung der aufgebauten Einheit.
        swaps: Originalname -> Name der gewaehlten Alternative (dauerhaft, aus der DB).

    Returns:
        Die Alternative (mit `original`) oder die unveraenderte Uebung; `alternatives` ist gefuellt,
        wenn es Alternativen gibt.
    """
    options = alternatives_for(exercise.name)
    if not options:
        return exercise
    names = [a.name for a in options]
    chosen = next((a for a in options if a.name == swaps.get(exercise.name)), None)
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
