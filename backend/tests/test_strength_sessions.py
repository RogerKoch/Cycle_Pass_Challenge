import pytest

from backend.engine.strength_sessions import STRENGTH_PHASES, build_strength_session, strength_phase_for


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


def test_rejects_unknown_session_and_phase():
    with pytest.raises(ValueError):
        build_strength_session("C", STRENGTH_PHASES[1])
    with pytest.raises(ValueError):
        strength_phase_for("nonsense")
