from datetime import date, timedelta

import pytest

from backend.engine.checkin_triggers import (
    CheckinPoint,
    EaDay,
    FtpPoint,
    SignalPoint,
    TriggerInputs,
    deficit_streak_start,
    evaluate,
    weight_trend,
)

TODAY = date(2026, 12, 1)


def _ids(findings):
    return [f.trigger_id for f in findings]


def _find(findings, trigger_id):
    return next(f for f in findings if f.trigger_id == trigger_id)


def _checkins(*weights, every_days=7):
    """Check-ins rueckwaerts ab heute: letzter Wert = heute."""
    n = len(weights)
    return [CheckinPoint(TODAY - timedelta(days=every_days * (n - 1 - i)), w) for i, w in enumerate(weights)]


def _signal(days_ago=0, sleep=0, legs=0, hunger=0, back=0, effort=0, resting_hr=None):
    return SignalPoint(TODAY - timedelta(days=days_ago), sleep, legs, hunger, back, effort, resting_hr)


def _inputs(**kwargs):
    base = {"today": TODAY, "checkins": _checkins(74.0), "signals": [_signal()], "deficit_active_today": True}
    base.update(kwargs)
    return TriggerInputs(**base)


# --- Gewicht -------------------------------------------------------------


def test_weight_trend_is_linear_regression_in_kg_and_percent_per_week():
    trend = weight_trend(_checkins(74.0, 73.5, 73.0), TODAY, 21)
    assert trend.kg_per_week == pytest.approx(-0.5)
    assert trend.pct_per_week == pytest.approx(-0.5 / 73.0 * 100)


def test_weight_trend_needs_two_points_on_different_days():
    assert weight_trend(_checkins(74.0), TODAY, 21) is None
    assert weight_trend([CheckinPoint(TODAY, 74), CheckinPoint(TODAY, 73)], TODAY, 21) is None


def test_weight_loss_above_0_7_percent_per_week_suggests_smaller_deficit():
    findings = evaluate(_inputs(checkins=_checkins(74.0, 73.3, 72.6)))  # ~0,96 %/Woche
    finding = _find(findings, "weight_loss_too_fast")
    assert finding.action.kind == "deficit_delta"
    assert finding.action.value == -100


def test_weight_loss_at_0_5_percent_per_week_is_fine():
    assert "weight_loss_too_fast" not in _ids(evaluate(_inputs(checkins=_checkins(74.0, 73.63, 73.26))))


def test_weight_loss_needs_a_week_of_data():
    findings = evaluate(_inputs(checkins=_checkins(74.0, 72.0, every_days=3)))
    assert "weight_loss_too_fast" not in _ids(findings)


def test_weight_stagnation_over_two_weeks_with_deficit():
    findings = evaluate(_inputs(checkins=_checkins(73.0, 73.1, 73.0)))
    assert "weight_stagnation" in _ids(findings)
    assert "weight_stagnation" not in _ids(evaluate(_inputs(checkins=_checkins(73.0, 73.1, 73.0), deficit_active_today=False)))


def test_no_deficit_action_when_deficit_is_not_active():
    finding = _find(evaluate(_inputs(checkins=_checkins(74.0, 73.3, 72.6), deficit_active_today=False)), "weight_loss_too_fast")
    assert finding.action is None


def test_target_weight_reached_suggests_maintenance():
    finding = _find(evaluate(_inputs(checkins=_checkins(67.9), target_weight_kg=68.0)), "target_weight_reached")
    assert finding.action.kind == "maintenance"


def test_finding_key_changes_with_new_checkin():
    first = _find(evaluate(_inputs(checkins=_checkins(74.0, 73.3, 72.6))), "weight_loss_too_fast")
    later = evaluate(_inputs(today=TODAY + timedelta(days=7), checkins=_checkins(74.0, 73.3, 72.6) + [CheckinPoint(TODAY + timedelta(days=7), 71.9)]))
    assert first.key != _find(later, "weight_loss_too_fast").key


# --- Diaet-Pause, EA -----------------------------------------------------


def test_diet_break_hint_after_six_weeks_and_warning_after_ten():
    assert "diet_break_due" not in _ids(evaluate(_inputs(deficit_streak_start=TODAY - timedelta(weeks=5))))
    hint = _find(evaluate(_inputs(deficit_streak_start=TODAY - timedelta(weeks=6))), "diet_break_due")
    warn = _find(evaluate(_inputs(deficit_streak_start=TODAY - timedelta(weeks=10))), "diet_break_due")
    assert (hint.severity, warn.severity) == ("info", "warn")
    assert hint.key != warn.key
    assert hint.action.kind == "diet_break" and hint.action.days == 7


def test_deficit_streak_start_walks_back_until_gap():
    gap = TODAY - timedelta(days=20)
    assert deficit_streak_start(TODAY, lambda d: d != gap) == gap + timedelta(days=1)
    assert deficit_streak_start(TODAY, lambda d: False) is None


def test_low_energy_availability_below_30_over_last_week():
    ea = [EaDay(TODAY - timedelta(days=i), 25.0) for i in range(1, 5)]
    finding = _find(evaluate(_inputs(ea_days=ea)), "low_energy_availability")
    assert finding.severity == "alert"
    ok = [EaDay(TODAY - timedelta(days=i), 30.0) for i in range(1, 5)]
    assert "low_energy_availability" not in _ids(evaluate(_inputs(ea_days=ok)))


def test_energy_availability_ignores_today_and_needs_three_days():
    ea = [EaDay(TODAY, 5.0), EaDay(TODAY - timedelta(days=1), 5.0), EaDay(TODAY - timedelta(days=2), 5.0)]
    assert "low_energy_availability" not in _ids(evaluate(_inputs(ea_days=ea)))


# --- FTP -----------------------------------------------------------------


def _ftp(*values):
    return [FtpPoint(i + 1, TODAY - timedelta(weeks=7 * (len(values) - 1 - i)), v) for i, v in enumerate(values)]


def test_ftp_stagnation_after_two_retests_without_progress():
    finding = _find(evaluate(_inputs(ftp_tests=_ftp(220, 220, 218))), "ftp_stagnation")
    assert finding.action.kind == "deload"
    assert "ftp_stagnation" not in _ids(evaluate(_inputs(ftp_tests=_ftp(220, 220, 225))))


def test_ftp_declining_twice_suggests_pausing_the_deficit():
    findings = evaluate(_inputs(ftp_tests=_ftp(230, 225, 220)))
    assert "ftp_declining" in _ids(findings)
    assert "ftp_stagnation" not in _ids(findings)
    assert _find(findings, "ftp_declining").action.kind == "diet_break"


def test_missing_result_of_planned_ramp_test():
    planned = TODAY - timedelta(days=3)
    assert "ftp_test_missing" in _ids(evaluate(_inputs(planned_ftp_tests=[planned])))
    done = [FtpPoint(1, planned, 230)]
    assert "ftp_test_missing" not in _ids(evaluate(_inputs(planned_ftp_tests=[planned], ftp_tests=done)))


# --- Fragebogen ----------------------------------------------------------


def test_poor_sleep_triggers_recovery_week():
    finding = _find(evaluate(_inputs(signals=[_signal(sleep=2)])), "recovery_warning")
    assert finding.action.kind == "deload"
    assert "recovery_warning" not in _ids(evaluate(_inputs(signals=[_signal(sleep=1)])))


def test_rising_resting_heart_rate_triggers_recovery_week():
    signals = [_signal(21, resting_hr=50), _signal(14, resting_hr=52), _signal(7, resting_hr=51), _signal(0, resting_hr=56)]
    assert "recovery_warning" in _ids(evaluate(_inputs(signals=signals)))
    signals[-1] = _signal(0, resting_hr=55)
    assert "recovery_warning" not in _ids(evaluate(_inputs(signals=signals)))


def test_legs_flat_needs_two_questionnaires_in_a_row():
    assert "legs_flat" not in _ids(evaluate(_inputs(signals=[_signal(7), _signal(0, legs=3)])))
    finding = _find(evaluate(_inputs(signals=[_signal(7, legs=2), _signal(0, legs=2)])), "legs_flat")
    assert finding.action.kind == "strength_reduced"


def test_back_pain_suggests_daily_core_and_hunger_smaller_deficit():
    findings = evaluate(_inputs(signals=[_signal(back=2, hunger=3)]))
    assert _find(findings, "back_pain").action.kind == "core_daily"
    assert _find(findings, "constant_hunger").action.kind == "deficit_delta"


def test_old_questionnaire_is_ignored():
    assert "recovery_warning" not in _ids(evaluate(_inputs(signals=[_signal(11, sleep=3)])))


def test_due_reminders_when_checkin_or_questionnaire_older_than_a_week():
    findings = evaluate(_inputs(checkins=_checkins(74.0, every_days=1), signals=[_signal(8)]))
    assert "signals_due" in _ids(findings)
    assert "checkin_due" not in _ids(findings)
    assert "checkin_due" in _ids(evaluate(_inputs(checkins=[])))


def test_strength_benchmark_due_after_interval():
    assert "strength_benchmark_due" in _ids(evaluate(_inputs()))
    three_weeks_ago = TODAY - timedelta(weeks=3)
    assert "strength_benchmark_due" not in _ids(evaluate(_inputs(last_strength_benchmark=three_weeks_ago)))
    every_two_weeks = _inputs(last_strength_benchmark=three_weeks_ago, benchmark_interval_weeks=2)
    assert "strength_benchmark_due" in _ids(evaluate(every_two_weeks))


def test_findings_are_sorted_by_severity():
    findings = evaluate(_inputs(checkins=[], signals=[_signal(sleep=3, back=2)]))
    assert [f.severity for f in findings] == sorted([f.severity for f in findings], key=["alert", "warn", "info"].index)


# --- Wellness (intervals.icu) --------------------------------------------


def _wellness(baseline_hr=48.0, recent_hr=48.0, baseline_hrv=60.0, recent_hrv=60.0, baseline_days=28):
    from backend.engine.checkin_triggers import WellnessPoint

    points = [WellnessPoint(TODAY - timedelta(days=3 + i), baseline_hr, baseline_hrv) for i in range(baseline_days)]
    points += [WellnessPoint(TODAY - timedelta(days=i), recent_hr, recent_hrv) for i in range(3)]
    return points


def test_resting_hr_up_five_over_three_days_triggers_recovery_week():
    finding = _find(evaluate(_inputs(wellness=_wellness(recent_hr=53))), "recovery_warning_wellness")
    assert finding.action.kind == "deload"
    assert "recovery_warning_wellness" not in _ids(evaluate(_inputs(wellness=_wellness(recent_hr=52.9))))


def test_hrv_down_ten_percent_triggers_recovery_week():
    assert "recovery_warning_wellness" in _ids(evaluate(_inputs(wellness=_wellness(recent_hrv=54))))
    assert "recovery_warning_wellness" not in _ids(evaluate(_inputs(wellness=_wellness(recent_hrv=55))))


def test_wellness_trigger_needs_two_weeks_of_baseline():
    assert "recovery_warning_wellness" not in _ids(evaluate(_inputs(wellness=_wellness(recent_hr=60, baseline_days=13))))


def test_wellness_finding_key_is_stable_within_a_week():
    first = _find(evaluate(_inputs(wellness=_wellness(recent_hr=55))), "recovery_warning_wellness")
    assert first.key.endswith((TODAY - timedelta(days=TODAY.weekday())).isoformat())
