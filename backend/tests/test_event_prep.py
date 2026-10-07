from datetime import date, timedelta

import pytest

from backend.engine.cycling_sessions import SLOT_FTP_TEST, SLOT_KEY_1, SLOT_LONG, build_cycling_session
from backend.engine.event_prep import (
    SLOT_EVENT,
    SLOT_OPENER,
    EventSpan,
    apply_event_to_session,
    carbs_g_per_kg,
    deficit_factor,
    event_context,
    event_hints,
    event_nutrition,
    recovery_days,
    strength_blocked,
    taper_volume_factor,
    weight_trend_excluded,
)
from backend.engine.nutrition_calc import CyclingIntensity

EVENT_DAY = date(2026, 11, 14)


def span(priority="A", minutes=240.0, kind="rennen", day=EVENT_DAY) -> EventSpan:
    return EventSpan(day, "Gran Fondo", priority, minutes, kind)


def ctx_at(offset: int, **kwargs):
    """Kontext `offset` Tage vor dem Event (negativ = danach)."""
    return event_context(EVENT_DAY - timedelta(days=offset), [span(**kwargs)])


def test_no_context_outside_window():
    assert ctx_at(15, priority="A") is None
    assert ctx_at(8, priority="B") is None
    assert ctx_at(3, priority="C") is not None  # Ladefenster gilt immer
    assert ctx_at(4, priority="C") is None
    assert ctx_at(-4, minutes=240) is None


@pytest.mark.parametrize(
    "offset, phase, label",
    [(14, "taper", "T-14"), (4, "taper", "T-4"), (3, "load", "T-3"), (1, "load", "T-1"), (0, "event", "Event"), (-1, "recovery", "R+1")],
)
def test_phase_and_label(offset, phase, label):
    ctx = ctx_at(offset, priority="A")
    assert (ctx.phase, ctx.label) == (phase, label)


@pytest.mark.parametrize("minutes, days", [(60, 1), (119, 1), (120, 2), (240, 2), (241, 3), (420, 3)])
def test_recovery_days_scale_with_event_duration(minutes, days):
    assert recovery_days(minutes) == days


def test_taper_volume_ramps_down_and_keeps_floor():
    assert taper_volume_factor(ctx_at(14, priority="A")) == pytest.approx(0.8)
    assert taper_volume_factor(ctx_at(2, priority="A")) == pytest.approx(0.5)
    assert taper_volume_factor(ctx_at(8, priority="A")) == pytest.approx(0.65)
    assert taper_volume_factor(ctx_at(7, priority="B")) == pytest.approx(0.7)
    assert taper_volume_factor(ctx_at(2, priority="C")) == pytest.approx(0.8)
    assert taper_volume_factor(ctx_at(1, priority="A")) is None  # Opener
    assert taper_volume_factor(ctx_at(0, priority="A")) is None


def test_taper_keeps_intensity_and_shortens_volume():
    base = build_cycling_session(SLOT_KEY_1, "build1", 1)
    tapered = apply_event_to_session(base, ctx_at(2, priority="A"))
    assert tapered.intensity == base.intensity
    assert tapered.minutes < base.minutes * 0.6
    assert [s.pct_ftp_low for s in tapered.segments] == [s.pct_ftp_low for s in base.segments]
    assert "Taper" in tapered.title


def test_ramp_test_is_not_tapered():
    test = build_cycling_session(SLOT_FTP_TEST, "base", 8)
    assert apply_event_to_session(test, ctx_at(5, priority="A")) is test


def test_no_context_leaves_session_unchanged():
    base = build_cycling_session(SLOT_LONG, "base", 1)
    assert apply_event_to_session(base, None) is base


def test_opener_and_event_day_replace_even_rest_days():
    opener = apply_event_to_session(None, ctx_at(1))
    event = apply_event_to_session(None, ctx_at(0, minutes=300, kind="tour"))
    assert opener.slot == SLOT_OPENER and 30 <= opener.minutes <= 50
    assert event.slot == SLOT_EVENT and event.minutes == 300
    assert event.intensity == CyclingIntensity.MODERAT_BASE


def test_race_event_day_is_hard():
    assert apply_event_to_session(None, ctx_at(0, kind="rennen")).intensity == CyclingIntensity.RENNEN_INTERVALLE


def test_recovery_replaces_planned_ride_with_easy_spin_and_keeps_rest_days():
    base = build_cycling_session(SLOT_KEY_1, "build1", 1)
    recovery = apply_event_to_session(base, ctx_at(-1))
    assert recovery.intensity == CyclingIntensity.LEICHT_REKOM and recovery.minutes <= 30
    assert apply_event_to_session(None, ctx_at(-1)) is None


def test_carbs_only_on_load_days_for_long_a_event():
    assert [carbs_g_per_kg(ctx_at(d, priority="A", minutes=240)) for d in (4, 3, 2, 1, 0, -1)] == [
        None, 7.0, 9.0, 10.0, None, None,
    ]


def test_medium_events_load_more_gently():
    assert carbs_g_per_kg(ctx_at(3, priority="B", minutes=120)) is None
    assert carbs_g_per_kg(ctx_at(2, priority="B", minutes=120)) == 7.0
    assert carbs_g_per_kg(ctx_at(1, priority="B", minutes=120)) == 8.5
    assert carbs_g_per_kg(ctx_at(1, priority="A", minutes=120)) == 8.5


def test_short_or_low_priority_events_get_no_loading_beyond_normal_hard_day():
    assert carbs_g_per_kg(ctx_at(1, priority="A", minutes=60)) == 7.0
    assert carbs_g_per_kg(ctx_at(1, priority="C", minutes=240)) == 7.0
    assert carbs_g_per_kg(ctx_at(2, priority="C", minutes=240)) is None


def test_fat_is_lowered_on_last_two_load_days_only():
    assert event_nutrition(ctx_at(3), 70).fat_g_per_kg is None
    assert event_nutrition(ctx_at(2), 70).fat_g_per_kg == 0.8
    assert event_nutrition(ctx_at(1), 70).fat_g_per_kg == 0.8


@pytest.mark.parametrize(
    "priority, offset, factor",
    [("A", 20, 1.0), ("A", 14, 0.5), ("A", 8, 0.5), ("A", 7, 0.0), ("B", 8, 1.0), ("B", 7, 0.0), ("C", 4, 1.0), ("C", 3, 0.0)],
)
def test_deficit_factor_before_event(priority, offset, factor):
    ctx = event_context(EVENT_DAY - timedelta(days=offset), [span(priority=priority)])
    if ctx is None:  # ausserhalb des Fensters gilt das normale Defizit
        assert factor == 1.0
    else:
        assert deficit_factor(ctx) == factor


def test_deficit_is_off_on_event_day_and_recovery():
    assert deficit_factor(ctx_at(0)) == 0.0
    assert deficit_factor(ctx_at(-2, minutes=240)) == 0.0


def test_strength_blocked_around_event():
    blocked = [d for d in range(5, -4, -1) if strength_blocked(ctx_at(d, priority="A"))]
    assert blocked == [2, 1, 0, -1, -2]
    assert not strength_blocked(ctx_at(2, priority="C"))
    assert not strength_blocked(None)


def test_overlapping_events_prefer_nearest_then_higher_priority():
    near = EventSpan(EVENT_DAY + timedelta(days=3), "Nah", "C", 90)
    far = EventSpan(EVENT_DAY + timedelta(days=10), "Fern", "A", 240)
    assert event_context(EVENT_DAY, [far, near]).span.name == "Nah"
    same_a = EventSpan(EVENT_DAY + timedelta(days=2), "A-Event", "A", 240)
    same_b = EventSpan(EVENT_DAY - timedelta(days=2), "B-Event", "B", 240)
    assert event_context(EVENT_DAY, [same_b, same_a]).span.name == "A-Event"


def test_hints_scale_with_weight():
    hints = event_hints(ctx_at(2, priority="A", minutes=240), 70)
    assert any("630 g KH" in h for h in hints)
    event_hints_text = " ".join(event_hints(ctx_at(0, minutes=240), 70))
    assert "210–280 g KH" in event_hints_text and "60–90 g KH/h" in event_hints_text


def test_weight_trend_excluded_in_load_and_recovery_window():
    spans = [span()]
    assert weight_trend_excluded(EVENT_DAY - timedelta(days=3), spans)
    assert weight_trend_excluded(EVENT_DAY + timedelta(days=3), spans)
    assert not weight_trend_excluded(EVENT_DAY - timedelta(days=4), spans)
    assert not weight_trend_excluded(EVENT_DAY + timedelta(days=4), spans)
