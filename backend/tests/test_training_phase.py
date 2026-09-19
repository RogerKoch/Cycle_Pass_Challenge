from datetime import date, timedelta

from backend.engine.training_phase import get_current_phase, get_phase_boundaries

PROGRAM_START = date(2026, 10, 1)


def test_returns_phase0_on_program_start_date():
    phase = get_current_phase(PROGRAM_START, PROGRAM_START)
    assert phase.phase_id == "phase0_wiedereinstieg"
    assert phase.day_in_phase == 1


def test_stays_in_phase0_until_day_before_boundary():
    last_phase0_day = PROGRAM_START + timedelta(weeks=2) - timedelta(days=1)
    phase = get_current_phase(PROGRAM_START, last_phase0_day)
    assert phase.phase_id == "phase0_wiedereinstieg"


def test_transitions_to_base_at_phase0_end_plus_one_day():
    first_base_day = PROGRAM_START + timedelta(weeks=2)
    phase = get_current_phase(PROGRAM_START, first_base_day)
    assert phase.phase_id == "base"
    assert phase.day_in_phase == 1


def test_transitions_to_build1_after_base_ends():
    first_build1_day = PROGRAM_START + timedelta(weeks=2 + 8)
    phase = get_current_phase(PROGRAM_START, first_build1_day)
    assert phase.phase_id == "build1"


def test_transitions_to_build2_after_build1_ends():
    first_build2_day = PROGRAM_START + timedelta(weeks=2 + 8 + 8)
    phase = get_current_phase(PROGRAM_START, first_build2_day)
    assert phase.phase_id == "build2"


def test_transitions_to_peak_taper_after_build2_ends():
    first_peak_taper_day = PROGRAM_START + timedelta(weeks=2 + 8 + 8 + 5)
    phase = get_current_phase(PROGRAM_START, first_peak_taper_day)
    assert phase.phase_id == "peak_taper"


def test_transitions_to_passsaison_after_peak_taper_ends():
    first_passsaison_day = PROGRAM_START + timedelta(weeks=2 + 8 + 8 + 5 + 5)
    phase = get_current_phase(PROGRAM_START, first_passsaison_day)
    assert phase.phase_id == "passsaison"
    assert phase.phase_end is None


def test_passsaison_remains_active_far_in_the_future():
    far_future = PROGRAM_START + timedelta(weeks=200)
    phase = get_current_phase(PROGRAM_START, far_future)
    assert phase.phase_id == "passsaison"


def test_phase_boundaries_are_contiguous_with_no_gaps_or_overlaps():
    boundaries = get_phase_boundaries(PROGRAM_START)
    assert boundaries[0][1] == PROGRAM_START
    for (_, _, end), (_, next_start, _) in zip(boundaries, boundaries[1:]):
        assert end is not None
        assert next_start == end + timedelta(days=1)
    assert boundaries[-1][2] is None
