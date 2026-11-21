from datetime import datetime

from backend.integrations.scheduler import seconds_until_next_hour


def test_waits_until_next_full_hour():
    assert seconds_until_next_hour(datetime(2026, 11, 21, 10, 15, 0)) == 45 * 60


def test_exactly_on_the_hour_waits_a_full_hour():
    assert seconds_until_next_hour(datetime(2026, 11, 21, 10, 0, 0)) == 3600
