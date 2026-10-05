from datetime import date, timedelta

from backend.engine.week_plan import (
    MSG_CONSECUTIVE_HARD,
    MSG_NO_REST_DAY,
    MSG_STRENGTH_SAME_DAY,
    DayPlan,
    default_day_plan,
    phase_week,
    resolve_strength,
    suggest_reschedule,
    swap_plans,
    validate_week,
    week_start,
)

PROGRAM_START = date(2026, 10, 5)  # Montag
BASE_MONDAY = PROGRAM_START + timedelta(weeks=2)
BUILD2_MONDAY = PROGRAM_START + timedelta(weeks=2 + 8 + 8)


def _week(monday):
    return [DayPlan(monday + timedelta(days=i), *default_day_plan(PROGRAM_START, monday + timedelta(days=i))) for i in range(7)]


def test_week_start_is_monday():
    assert week_start(date(2026, 10, 8)) == date(2026, 10, 5)


def test_phase_week_counts_weeks_within_phase():
    phase, week = phase_week(PROGRAM_START, BASE_MONDAY + timedelta(weeks=2, days=3))
    assert (phase.phase_id, week) == ("base", 3)


def test_base_standard_week_has_strength_monday_and_thursday_and_friday_rest():
    plan = [(d.cycling_slot, d.strength_session) for d in _week(BASE_MONDAY)]
    assert plan == [
        ("rekom", "A"),
        ("schluessel_1", None),
        ("z2_grundlage", None),
        ("z2_oder_rekom", "B"),
        (None, None),
        ("schluessel_2", None),
        ("lang", None),
    ]


def test_build2_has_only_one_strength_session_on_monday_alternating_a_and_b():
    week1 = _week(BUILD2_MONDAY)
    week2 = _week(BUILD2_MONDAY + timedelta(weeks=1))
    assert [d.strength_session for d in week1] == ["A", None, None, None, None, None, None]
    assert week2[0].strength_session == "B"


def test_nothing_planned_before_program_start():
    assert default_day_plan(PROGRAM_START, PROGRAM_START - timedelta(days=1)) == (None, None)


def test_standard_weeks_have_no_blocking_violations_in_any_phase():
    monday = PROGRAM_START
    for _ in range(30):
        assert not [v for v in validate_week(_week(monday)) if v.blocking], monday
        monday += timedelta(weeks=1)


def test_consecutive_key_sessions_are_blocked():
    week = swap_plans(_week(BASE_MONDAY), BASE_MONDAY + timedelta(days=2), BASE_MONDAY + timedelta(days=5))
    messages = [(v.message, v.blocking) for v in validate_week(week)]
    assert (MSG_CONSECUTIVE_HARD, True) in messages


def test_week_without_full_rest_day_is_blocked():
    week = _week(BASE_MONDAY)
    week[4] = DayPlan(week[4].day, "z2_grundlage", None)
    assert (MSG_NO_REST_DAY, True) in [(v.message, v.blocking) for v in validate_week(week)]


def test_skipped_day_counts_as_rest_day():
    week = _week(BASE_MONDAY)
    week[4] = DayPlan(week[4].day, "z2_grundlage", None)
    week[2] = DayPlan(week[2].day, "z2_grundlage", None, status="skipped")
    assert not [v for v in validate_week(week) if v.blocking]


def test_strength_and_key_session_on_same_day_is_only_a_warning():
    week = _week(BASE_MONDAY)
    week[1] = DayPlan(week[1].day, "schluessel_1", "A")
    violations = validate_week(week)
    assert [(v.message, v.blocking) for v in violations] == [(MSG_STRENGTH_SAME_DAY, False)]


def test_swap_moves_plan_but_keeps_status():
    week = _week(BASE_MONDAY)
    week[1] = DayPlan(week[1].day, "schluessel_1", None, status="skipped")
    swapped = swap_plans(week, week[1].day, week[2].day)
    assert (swapped[1].cycling_slot, swapped[1].status) == ("z2_grundlage", "skipped")
    assert (swapped[2].cycling_slot, swapped[2].status) == ("schluessel_1", "planned")


def test_suggest_reschedule_offers_free_days_without_rule_violation():
    week = _week(BASE_MONDAY)
    week[1] = DayPlan(week[1].day, "schluessel_1", None, status="skipped")  # Dienstag abgesagt
    suggestions = suggest_reschedule(week, week[1].day, today=BASE_MONDAY)
    # Mi ok; Fr (Ruhetag) waere direkt vor Sa-Schluessel -> blockiert; Sa/So: Sa ist selbst Schluessel, So nach Sa
    assert week[2].day in suggestions
    assert week[4].day not in suggestions
    assert week[5].day not in suggestions
    assert week[6].day not in suggestions


def test_suggest_reschedule_ignores_past_days_and_non_key_sessions():
    week = _week(BASE_MONDAY)
    week[1] = DayPlan(week[1].day, "schluessel_1", None, status="skipped")
    assert week[0].day not in suggest_reschedule(week, week[1].day, today=week[1].day)
    week[2] = DayPlan(week[2].day, "z2_grundlage", None, status="skipped")
    assert suggest_reschedule(week, week[2].day, today=BASE_MONDAY) == []


def test_taper_strength_session_is_reduced():
    session = resolve_strength("A", "peak_taper", 4)
    assert session.duration_minutes == "40"
    assert session.note is not None
    assert resolve_strength("A", "peak_taper", 1).note is None


def test_ftp_retests_replace_saturday_key_session_in_retest_weeks():
    def saturday(phase_offset_weeks, week):
        return PROGRAM_START + timedelta(weeks=phase_offset_weeks + week - 1, days=5)

    assert default_day_plan(PROGRAM_START, saturday(0, 1))[0] == "ftp_test"  # Phase 0 W1
    assert default_day_plan(PROGRAM_START, saturday(2, 8))[0] == "ftp_test"  # Base W8
    assert default_day_plan(PROGRAM_START, saturday(2 + 8, 6))[0] == "ftp_test"  # Build 1 W6
    assert default_day_plan(PROGRAM_START, saturday(2 + 8 + 8, 5))[0] == "ftp_test"  # Build 2 W5
    assert default_day_plan(PROGRAM_START, saturday(2, 7))[0] == "schluessel_2"


def test_ftp_test_counts_as_key_session_in_rules():
    week = _week(BASE_MONDAY)
    week[4] = DayPlan(week[4].day, "ftp_test", None)
    assert MSG_CONSECUTIVE_HARD in [v.message for v in validate_week(week)]


def test_reduced_strength_session_drops_leg_exercises():
    session = resolve_strength("B", "build1", 1, reduced=True)
    names = [e.name for e in session.exercises]
    assert "Bulgarian Split Squat" not in names
    assert "Lateral Band Walks" not in names
    assert "Volumen" in session.note
