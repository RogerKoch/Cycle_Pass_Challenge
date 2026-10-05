import pytest

from backend.engine.cycling_sessions import (
    ALL_SLOTS,
    FTP_MISSING_MESSAGE,
    adjust_duration,
    build_cycling_session,
    is_deload_week,
    session_watts,
)
from backend.engine.nutrition_calc import CyclingIntensity


def _work_segments(session, prefix):
    return [s for s in session.segments if s.label.startswith(prefix)]


def test_base_sweet_spot_progresses_from_3x10_to_2x20():
    week1 = build_cycling_session("schluessel_1", "base", 1)
    week8 = build_cycling_session("schluessel_1", "base", 8)
    assert [s.minutes for s in _work_segments(week1, "Sweet Spot")] == [10, 10, 10]
    assert [s.minutes for s in _work_segments(week8, "Sweet Spot")] == [20, 20]
    assert all(s.pct_ftp_low == 88 and s.pct_ftp_high == 94 for s in _work_segments(week1, "Sweet Spot"))


def test_base_low_cadence_intervals_carry_cadence():
    session = build_cycling_session("schluessel_2", "base", 1)
    work = _work_segments(session, "Low-Cadence")
    assert len(work) == 4
    assert all(s.cadence_rpm == "50–60" for s in work)


def test_base_long_ride_grows_from_two_to_three_hours():
    assert build_cycling_session("lang", "base", 1).minutes == 120
    assert build_cycling_session("lang", "base", 8).minutes == 180


def test_build1_every_third_week_is_a_deload_week():
    assert [is_deload_week("build1", w) for w in range(1, 9)] == [False, False, True, False, False, True, False, False]
    assert not is_deload_week("base", 3)


def test_build1_deload_cuts_long_ride_volume_by_40_percent_and_shortens_intervals():
    normal_long = build_cycling_session("lang", "build1", 2)
    deload_long = build_cycling_session("lang", "build1", 3)
    assert normal_long.minutes == 180
    assert deload_long.minutes == pytest.approx(180 * 0.6)
    normal_key = build_cycling_session("schluessel_1", "build1", 2)
    deload_key = build_cycling_session("schluessel_1", "build1", 3)
    assert len(_work_segments(deload_key, "Schwelle")) < len(_work_segments(normal_key, "Schwelle"))
    assert _work_segments(deload_key, "Schwelle")[0].pct_ftp_low == 95


def test_over_unders_alternate_95_and_105_percent():
    session = build_cycling_session("schluessel_2", "build1", 1)
    work = [s for s in session.segments if s.label.startswith(("Over", "Under"))]
    assert len(work) == 3 * 6
    assert {s.pct_ftp_low for s in work} == {95, 105}


def test_taper_drops_monday_ride_and_keeps_intensity():
    assert build_cycling_session("rekom", "peak_taper", 4) is None
    taper_key = build_cycling_session("schluessel_1", "peak_taper", 4)
    assert _work_segments(taper_key, "Schwelle")[0].pct_ftp_low == 100


def test_passsaison_week_has_one_maintenance_key_session():
    key = build_cycling_session("schluessel_1", "passsaison", 1)
    assert [s.minutes for s in _work_segments(key, "Erhalt")] == [20, 20]
    assert build_cycling_session("z2_grundlage", "passsaison", 1) is None


def test_phase0_first_saturday_is_ramp_test():
    session = build_cycling_session("schluessel_2", "phase0_wiedereinstieg", 1)
    assert "Ramp" in session.title
    assert build_cycling_session("schluessel_2", "phase0_wiedereinstieg", 2).title != session.title


def test_every_phase_and_slot_builds_without_error():
    for phase in ("phase0_wiedereinstieg", "base", "build1", "build2", "peak_taper", "passsaison"):
        for slot in ALL_SLOTS:
            for week in range(1, 9):
                session = build_cycling_session(slot, phase, week)
                if session is not None:
                    assert session.minutes > 0
                    assert all(s.minutes >= 0 for s in session.segments)


def test_rejects_unknown_slot_and_phase():
    with pytest.raises(ValueError):
        build_cycling_session("nonsense", "base", 1)
    with pytest.raises(ValueError):
        build_cycling_session("lang", "nonsense", 1)


def test_watts_are_derived_from_ftp():
    session = build_cycling_session("schluessel_1", "base", 1)
    result = session_watts(session, 250)
    first_interval = next(s for s in result.segments if s.label.startswith("Sweet Spot"))
    assert (first_interval.watts_low, first_interval.watts_high) == (220, 235)
    assert result.message is None


def test_without_ftp_only_percentages_and_hint():
    result = session_watts(build_cycling_session("schluessel_1", "base", 1), None)
    assert all(s.watts_low is None for s in result.segments)
    assert result.message == FTP_MISSING_MESSAGE


def test_adjust_duration_scales_endurance_ride_and_keeps_tempo_blocks():
    session = build_cycling_session("lang", "build1", 1)  # 180 min mit 2x20 Tempo
    adjusted = adjust_duration(session, 120)
    assert adjusted.minutes == 120
    assert adjusted.adjusted is True
    assert len(_work_segments(adjusted, "Tempo")) == 2


def test_adjust_duration_turns_too_short_ride_into_plain_endurance():
    adjusted = adjust_duration(build_cycling_session("lang", "build1", 1), 45)
    assert adjusted.minutes == 45
    assert len(adjusted.segments) == 1


def test_adjust_duration_rejects_key_sessions():
    with pytest.raises(ValueError):
        adjust_duration(build_cycling_session("schluessel_1", "base", 1), 30)


def test_intensity_is_explicit_per_session():
    assert build_cycling_session("rekom", "base", 1).intensity == CyclingIntensity.LEICHT_REKOM
    assert build_cycling_session("schluessel_1", "build2", 1).intensity == CyclingIntensity.RENNEN_INTERVALLE


def test_session_keeps_requested_slot_even_when_built_from_shared_block():
    assert build_cycling_session("z2_oder_rekom", "base", 1).slot == "z2_oder_rekom"
