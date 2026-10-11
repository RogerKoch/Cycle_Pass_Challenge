import pytest

from backend.engine.strength_alternatives import (
    ALTERNATIVES,
    EQUIPMENT_BANDS,
    EQUIPMENT_TABLE,
    REQUIRES,
    apply_swaps,
)
from backend.engine.strength_sessions import SESSION_IDS, STRENGTH_PHASES, build_strength_session

ROWS = "Inverted Rows (Tischkanten-Rudern)"


def _session_b(phase: int = 1):
    return build_strength_session("B", STRENGTH_PHASES[phase])


def _exercise(name: str):
    return next(e for e in _session_b().exercises if e.name == name)


def test_exercise_without_alternatives_stays_unchanged():
    original = _exercise("Bird Dog")
    assert apply_swaps(original, {}, frozenset({EQUIPMENT_BANDS})) == original


def test_original_lists_its_alternatives_when_nothing_is_swapped():
    result = apply_swaps(_exercise(ROWS), {}, frozenset())
    assert result.name == ROWS and result.original is None
    assert result.alternatives == [a.name for a in ALTERNATIVES[ROWS]]


def test_manual_swap_replaces_name_but_keeps_sets_and_group():
    original = _exercise(ROWS)
    result = apply_swaps(original, {ROWS: "Handtuch-Rudern an Türklinke"}, frozenset())
    assert result.name == "Handtuch-Rudern an Türklinke"
    assert result.original == ROWS
    assert (result.sets, result.reps, result.rest, result.group) == (
        original.sets, original.reps, original.rest, original.group
    )


def test_missing_table_swaps_to_first_alternative_that_needs_no_missing_material():
    result = apply_swaps(_exercise(ROWS), {}, frozenset({EQUIPMENT_TABLE}))
    assert result.name == "Band-Rudern"  # braucht Band, aber das ist vorhanden


def test_missing_table_and_bands_skips_band_alternative():
    result = apply_swaps(_exercise(ROWS), {}, frozenset({EQUIPMENT_TABLE, EQUIPMENT_BANDS}))
    assert result.name == "Handtuch-Rudern an Türklinke"


def test_manual_swap_wins_over_equipment_automation():
    result = apply_swaps(
        _exercise(ROWS), {ROWS: "Rucksack-Rudern vorgebeugt"}, frozenset({EQUIPMENT_TABLE})
    )
    assert result.name == "Rucksack-Rudern vorgebeugt"


def test_unknown_manual_alternative_is_ignored():
    assert apply_swaps(_exercise(ROWS), {ROWS: "Kreuzheben"}, frozenset()).name == ROWS


def test_present_material_does_not_trigger_automatic_swap():
    assert apply_swaps(_exercise("Lateral Band Walks"), {}, frozenset({EQUIPMENT_TABLE})).name == "Lateral Band Walks"


def test_override_reps_only_when_alternative_defines_them():
    session_a = build_strength_session("A", STRENGTH_PHASES[3])
    pallof = next(e for e in session_a.exercises if e.name.startswith("Anti-rotatorischer"))
    result = apply_swaps(pallof, {}, frozenset({EQUIPMENT_BANDS}))
    assert (result.name, result.reps) == ("Plank Shoulder Taps", "10–16 Taps")


def test_every_original_with_required_material_has_an_alternative_without_it():
    for name, needed in REQUIRES.items():
        assert any(not a.requires & needed for a in ALTERNATIVES[name]), name


def test_all_requiring_originals_exist_in_the_library():
    names = set()
    for phase in STRENGTH_PHASES.values():
        for session_id in SESSION_IDS:
            for focus in ("none", "core", "upper", "legs"):
                names.update(e.name for e in build_strength_session(session_id, phase, focus=focus).exercises)
    assert set(REQUIRES) <= names


@pytest.mark.parametrize("name", sorted(ALTERNATIVES))
def test_alternative_names_are_unique_per_original(name):
    names = [a.name for a in ALTERNATIVES[name]]
    assert len(names) == len(set(names)) and name not in names
