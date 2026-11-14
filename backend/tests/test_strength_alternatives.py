import pytest

from backend.engine.strength_alternatives import ALTERNATIVES, apply_swaps
from backend.engine.strength_sessions import (
    EQUIPMENT_PROFILES,
    PROFILE_BANDS,
    PROFILE_NEOLYMP,
    SESSION_IDS,
    STRENGTH_PHASES,
    build_strength_session,
)

ROWS = "Band-Rudern"


def _session_b(phase: int = 1, profile: str = PROFILE_BANDS):
    return build_strength_session("B", STRENGTH_PHASES[phase], profile=profile)


def _exercise(name: str, profile: str = PROFILE_BANDS):
    return next(e for e in _session_b(profile=profile).exercises if e.name == name)


def test_exercise_without_alternatives_stays_unchanged():
    original = _exercise("Bird Dog")
    assert apply_swaps(original, {}) == original


def test_original_lists_its_alternatives_when_nothing_is_swapped():
    result = apply_swaps(_exercise(ROWS), {})
    assert result.name == ROWS and result.original is None
    assert result.alternatives == [a.name for a in ALTERNATIVES[ROWS]]


def test_manual_swap_replaces_name_but_keeps_sets_and_group():
    original = _exercise(ROWS)
    result = apply_swaps(original, {ROWS: "Handtuch-Rudern an Türklinke"})
    assert result.name == "Handtuch-Rudern an Türklinke"
    assert result.original == ROWS
    assert (result.sets, result.reps, result.rest, result.group) == (
        original.sets, original.reps, original.rest, original.group
    )


def test_unknown_manual_alternative_is_ignored():
    assert apply_swaps(_exercise(ROWS), {ROWS: "Kreuzheben"}).name == ROWS


def test_override_reps_only_when_alternative_defines_them():
    session_a = build_strength_session("A", STRENGTH_PHASES[3], profile=PROFILE_BANDS)
    pallof = next(e for e in session_a.exercises if e.name.startswith("Anti-rotatorischer"))
    result = apply_swaps(pallof, {pallof.name: "Plank Shoulder Taps"})
    assert (result.name, result.reps) == ("Plank Shoulder Taps", "10–16 Taps")


def test_neolymp_exercise_offers_neolymp_alternatives():
    result = apply_swaps(_exercise("Rudern zur Brust mit Bänderstange", PROFILE_NEOLYMP), {})
    assert "Rudern vorgebeugt mit Bänderstange" in result.alternatives


def _all_names(profile: str) -> set[str]:
    names = set()
    for phase in STRENGTH_PHASES.values():
        for session_id in SESSION_IDS:
            for focus in ("none", "core", "upper", "legs"):
                names.update(e.name for e in build_strength_session(session_id, phase, focus=focus, profile=profile).exercises)
    return names


def test_all_swappable_originals_exist_in_some_profile():
    names = set().union(*(_all_names(profile) for profile in EQUIPMENT_PROFILES))
    assert set(ALTERNATIVES) <= names


def test_bodyweight_profile_offers_no_equipment_exercise_or_swap():
    names = _all_names("bodyweight")
    forbidden = ("Band", "Rucksack", "Tisch", "Handtuch-Rudern", "Griff", "Fußschlaufe", "Bänderstange")
    assert not [n for n in names if any(word in n for word in forbidden)]


@pytest.mark.parametrize("name", sorted(ALTERNATIVES))
def test_alternative_names_are_unique_per_original(name):
    names = [a.name for a in ALTERNATIVES[name]]
    assert len(names) == len(set(names)) and name not in names
