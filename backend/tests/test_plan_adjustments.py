from datetime import date, timedelta

from backend.engine.cycling_sessions import build_cycling_session
from backend.engine.plan_adjustments import (
    AdjustmentSpan,
    active_kinds,
    apply_deload,
    effective_deficit,
    is_forced_deload,
)

DAY = date(2026, 11, 10)


def test_deficit_defaults_to_phase_value():
    assert effective_deficit(DAY, "base", []) == 350
    assert effective_deficit(DAY, "build2", []) == 0


def test_deficit_deltas_add_up_and_never_go_below_zero():
    deltas = [AdjustmentSpan("deficit_delta", DAY - timedelta(days=3), value=-100)]
    assert effective_deficit(DAY, "base", deltas) == 250
    many = deltas * 5
    assert effective_deficit(DAY, "base", many) == 0


def test_deficit_delta_only_applies_inside_its_window():
    delta = [AdjustmentSpan("deficit_delta", DAY, DAY + timedelta(days=2), value=-100)]
    assert effective_deficit(DAY - timedelta(days=1), "base", delta) == 350
    assert effective_deficit(DAY + timedelta(days=3), "base", delta) == 350


def test_diet_break_and_maintenance_set_deficit_to_zero():
    assert effective_deficit(DAY, "base", [AdjustmentSpan("diet_break", DAY, DAY + timedelta(days=6))]) == 0
    assert effective_deficit(DAY, "build1", [AdjustmentSpan("maintenance", DAY - timedelta(days=30))]) == 0


def test_deficit_delta_does_not_create_deficit_outside_deficit_phases():
    assert effective_deficit(DAY, "peak_taper", [AdjustmentSpan("deficit_delta", DAY, value=100)]) == 0


def test_active_kinds_and_forced_deload():
    spans = [AdjustmentSpan("deload", DAY, DAY + timedelta(days=6)), AdjustmentSpan("core_daily", DAY)]
    assert active_kinds(DAY, spans) == {"deload", "core_daily"}
    assert is_forced_deload(DAY + timedelta(days=6), spans)
    assert not is_forced_deload(DAY + timedelta(days=7), spans)


def test_apply_deload_shortens_all_segments_by_40_percent_keeping_intensity():
    session = build_cycling_session("schluessel_1", "base", 3)  # Sweet Spot 3x12
    deloaded = apply_deload(session)
    work = [s for s in deloaded.segments if s.label.startswith("Sweet Spot")]
    assert [s.minutes for s in work] == [7, 7, 7]
    assert work[0].pct_ftp_low == 88
    assert deloaded.minutes < session.minutes


def test_apply_deload_keeps_ramp_test():
    ramp = build_cycling_session("ftp_test", "base", 8)
    assert apply_deload(ramp) == ramp
