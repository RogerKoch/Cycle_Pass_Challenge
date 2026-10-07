from datetime import date, timedelta

from backend.engine.strength_benchmarks import (
    BenchmarkResult,
    ExerciseStages,
    combine,
    exercise_stages,
    milestones,
    next_due,
)
from backend.engine.strength_sessions import STRENGTH_PHASES, build_strength_session

DAY = date(2026, 10, 7)


def _notes(session):
    return {e.name: e.note for e in session.exercises}


def test_pushups_move_to_next_variant_from_15_clean_reps():
    assert exercise_stages(BenchmarkResult(DAY, pushup_reps=14, pushup_variant="knie")).pushup_variant == "knie"
    assert exercise_stages(BenchmarkResult(DAY, pushup_reps=15, pushup_variant="knie")).pushup_variant == "standard"
    assert exercise_stages(BenchmarkResult(DAY, pushup_reps=30, pushup_variant="deficit")).pushup_variant == "deficit"


def test_rows_side_plank_and_glute_bridge_stages():
    stages = exercise_stages(
        BenchmarkResult(DAY, row_reps=15, side_plank_s=20, side_plank_straight=False, sl_bridge_s=45)
    )
    assert (stages.rows_feet_elevated, stages.side_plank_straight, stages.glute_bridge_single_leg) == (True, True, False)
    assert exercise_stages(BenchmarkResult(DAY, side_plank_s=12, side_plank_straight=False)).side_plank_straight is False


def test_untested_exercises_have_no_stage():
    assert exercise_stages(None) == ExerciseStages()
    assert exercise_stages(BenchmarkResult(DAY, plank_s=60)).pushup_variant is None


def test_core_advanced_needs_plank_2_min_and_straight_side_plank_30_s():
    assert exercise_stages(BenchmarkResult(DAY, plank_s=120, side_plank_s=30, side_plank_straight=True)).core_advanced
    assert not exercise_stages(
        BenchmarkResult(DAY, plank_s=120, side_plank_s=30, side_plank_straight=False)
    ).core_advanced
    assert not exercise_stages(BenchmarkResult(DAY, plank_s=90, side_plank_s=40, side_plank_straight=True)).core_advanced


def test_combine_takes_newest_value_per_test_and_keeps_pairs_together():
    old = BenchmarkResult(DAY - timedelta(weeks=4), pushup_reps=10, pushup_variant="knie", plank_s=60)
    new = BenchmarkResult(DAY, pushup_reps=8, pushup_variant="standard")
    combined = combine([new, old])
    assert (combined.test_date, combined.pushup_reps, combined.pushup_variant, combined.plank_s) == (
        DAY, 8, "standard", 60)
    assert combine([]) is None


def test_milestones_reflect_measured_values():
    status = {(m.week, m.text): m.achieved for m in milestones(BenchmarkResult(DAY, sl_bridge_s=60, plank_s=100))}
    assert status[(12, "Single-Leg Glute Bridge 60 s je Bein")] is True
    assert status[(20, "Plank 2 min")] is False
    assert status[(8, "Standard-Liegestütz sauber")] is None  # nicht getestet
    assert status[(16, "Bulgarian Split Squat 3× 10 sauber")] is None  # nicht messbar


def test_next_due_uses_interval_and_is_immediate_without_test():
    assert next_due(None, 4, DAY) == DAY
    assert next_due(DAY, 2, DAY) == DAY + timedelta(weeks=2)


def test_session_shows_stage_instead_of_progression_list():
    stages = exercise_stages(BenchmarkResult(DAY, pushup_reps=6, pushup_variant="knie", side_plank_s=25,
                                             side_plank_straight=True, sl_bridge_s=20))
    notes = _notes(build_strength_session("A", STRENGTH_PHASES[1], stages=stages))
    assert notes["Liegestütz-Progression"].startswith("Deine Stufe: Knie")
    assert notes["Side Plank"] == "Deine Stufe: Beine gestreckt"
    assert notes["Glute Bridge (Progression → Single-Leg)"] == "Deine Stufe: beidbeinig"
    assert notes["Dead Bug"] == "Lendenwirbel flach am Boden, langsam"  # unveraendert


def test_core_benchmark_unlocks_hollow_body_and_pallof_in_phase_1():
    advanced = ExerciseStages(core_advanced=True)
    names = [e.name for e in build_strength_session("A", STRENGTH_PHASES[1], stages=advanced).exercises]
    assert "Hollow Body Hold" in names and "Anti-rotatorischer Band-Hold (Pallof)" in names
    plain = [e.name for e in build_strength_session("A", STRENGTH_PHASES[1]).exercises]
    assert "Hollow Body Hold" not in plain


def test_combine_keeps_older_partner_value_when_newer_test_has_none():
    old = BenchmarkResult(DAY - timedelta(weeks=4), pushup_reps=10, pushup_variant="knie")
    new = BenchmarkResult(DAY, pushup_reps=16)
    combined = combine([old, new])
    assert (combined.pushup_reps, combined.pushup_variant) == (16, "knie")


def test_standard_milestone_needs_clean_reps_for_harder_variants():
    def achieved(variant, reps):
        status = {m.week: m.achieved for m in milestones(BenchmarkResult(DAY, pushup_reps=reps, pushup_variant=variant))}
        return status[8]

    assert achieved("deficit", 1) is False
    assert achieved("fuesse_erhoeht", 8) is True
