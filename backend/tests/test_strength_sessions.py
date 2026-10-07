import pytest

from backend.engine.strength_sessions import (
    MOBILITY_ROUTINE,
    STRENGTH_PHASES,
    build_strength_session,
    mobility_routine,
    shift_numbers,
    strength_phase_for,
)


def _names(session):
    return [e.name for e in session.exercises]


def test_cycling_phases_map_to_strength_phases_per_sync_rules():
    assert strength_phase_for("phase0_wiedereinstieg").number == 1
    assert strength_phase_for("base").number == 1
    assert strength_phase_for("build1").number == 2
    assert strength_phase_for("build2").number == 3
    assert strength_phase_for("peak_taper").number == 3
    assert strength_phase_for("passsaison").number == 3


def test_phase1_omits_exercises_introduced_in_phase2():
    session_b = build_strength_session("B", STRENGTH_PHASES[1])
    assert "Bulgarian Split Squat" not in _names(session_b)
    assert "Bulgarian Split Squat" in _names(build_strength_session("B", STRENGTH_PHASES[2]))


def test_phase3_adds_copenhagen_plank():
    assert "Copenhagen Plank" in _names(build_strength_session("B", STRENGTH_PHASES[3]))
    assert "Copenhagen Plank" not in _names(build_strength_session("B", STRENGTH_PHASES[2]))


def test_scaled_exercises_take_reps_and_rest_from_phase():
    phase1 = build_strength_session("A", STRENGTH_PHASES[1])
    glute = next(e for e in phase1.exercises if e.name.startswith("Glute Bridge"))
    assert (glute.sets, glute.reps, glute.rest) == ("2–3", "15–25", "60–90 s")
    phase2 = build_strength_session("A", STRENGTH_PHASES[2])
    assert next(e for e in phase2.exercises if e.name.startswith("Glute Bridge")).reps == "8–12"


def test_holds_keep_their_library_values():
    session = build_strength_session("A", STRENGTH_PHASES[1])
    side_plank = next(e for e in session.exercises if e.name == "Side Plank")
    assert side_plank.reps == "15–30 s je Seite"


def test_sessions_end_without_stretch_block_mobility_closes_instead():
    for session_id in ("A", "B"):
        assert "Auslaufen/Stretch" not in _names(build_strength_session(session_id, STRENGTH_PHASES[1]))


def test_rejects_unknown_session_and_phase():
    with pytest.raises(ValueError):
        build_strength_session("C", STRENGTH_PHASES[1])
    with pytest.raises(ValueError):
        strength_phase_for("nonsense")


# --- Kraft-Fokus -----------------------------------------------------------


def _sets(session):
    return {e.name: e.sets for e in session.exercises}


def test_without_focus_session_is_unchanged():
    plain = build_strength_session("A", STRENGTH_PHASES[2])
    assert build_strength_session("A", STRENGTH_PHASES[2], focus="none") == plain
    assert plain.duration_minutes == "50–55" and plain.note is None


def test_core_focus_adds_a_set_to_core_exercises_and_a_plank():
    plain = _sets(build_strength_session("A", STRENGTH_PHASES[2]))
    session = build_strength_session("A", STRENGTH_PHASES[2], focus="core")
    sets = _sets(session)
    assert (sets["Dead Bug"], sets["Hollow Body Hold"]) == ("4", "4")
    assert sets["Liegestütz-Progression"] == plain["Liegestütz-Progression"]  # andere Gruppe unveraendert
    assert sets["Plank (Unterarmstütz)"] == "4–5"
    assert session.duration_minutes == "60–65"
    assert "Fokus Bauch/Core" in session.note


def test_core_focus_in_session_b_switches_from_plank_to_reverse_crunch_in_phase_2():
    assert "Plank (Unterarmstütz)" in _sets(build_strength_session("B", STRENGTH_PHASES[1], focus="core"))
    phase2 = _sets(build_strength_session("B", STRENGTH_PHASES[2], focus="core"))
    assert "Reverse Crunch / Leg Raises" in phase2 and "Plank (Unterarmstütz)" not in phase2


def test_upper_focus_scales_phase_sets_and_adds_scapular_pushups():
    sets = _sets(build_strength_session("A", STRENGTH_PHASES[1], focus="upper"))
    assert sets["Liegestütz-Progression"] == "3–4"  # Phase 1 "2–3" + 1
    assert sets["Scapular Push-ups"] == "3"


def test_upper_focus_adds_pull_aparts_to_b_only_before_they_are_regular():
    phase1 = [e.name for e in build_strength_session("B", STRENGTH_PHASES[1], focus="upper").exercises]
    phase2 = [e.name for e in build_strength_session("B", STRENGTH_PHASES[2], focus="upper").exercises]
    assert phase1.count("Band Pull-Aparts + Face Pulls") == 1
    assert phase2.count("Band Pull-Aparts + Face Pulls") == 1


def test_leg_focus_extras_are_dropped_when_reduced():
    session = build_strength_session("B", STRENGTH_PHASES[2], focus="legs", reduced=True)
    assert not any(e.leg for e in session.exercises)


def test_mobility_focus_leaves_strength_session_unchanged():
    session = build_strength_session("A", STRENGTH_PHASES[2], focus="mobility")
    assert _sets(session) == _sets(build_strength_session("A", STRENGTH_PHASES[2]))
    assert session.duration_minutes == "50–55"


def test_mobility_routine_by_focus():
    assert mobility_routine() == MOBILITY_ROUTINE
    longer = mobility_routine("mobility")
    assert longer[0].sets == "3" and longer[-1].note is None  # Pigeon fest statt bei Bedarf
    assert [e.name for e in mobility_routine("core")][-3:] == ["McGill Curl-Up", "Side Plank", "Bird Dog"]
    assert len(mobility_routine("core", core_daily=True)) == len(MOBILITY_ROUTINE) + 3


def test_shift_numbers():
    assert (shift_numbers("2–3", 1), shift_numbers("50–55", 10), shift_numbers("3", 1)) == ("3–4", "60–65", "4")


def test_rejects_unknown_focus():
    with pytest.raises(ValueError):
        build_strength_session("A", STRENGTH_PHASES[1], focus="arme")
