import pytest

from backend.engine.cycling_zones import calculate_ftp_from_ramp_test, compute_cycling_zones


def test_returns_unavailable_when_ftp_is_none():
    result = compute_cycling_zones(None)
    assert result.available is False
    assert result.zones is None
    assert result.message


def test_unavailable_result_has_no_watts():
    result = compute_cycling_zones(None)
    assert result.ftp_watts is None


def test_computes_zone_watt_boundaries_from_known_ftp():
    result = compute_cycling_zones(250)
    assert result.available is True
    sweet_spot = next(z for z in result.zones if z.zone_id == "sweet_spot")
    assert sweet_spot.watts_min == 220  # ceil(250*0.88)
    assert sweet_spot.watts_max == 235  # floor(250*0.94)


def test_top_zone_has_no_upper_bound():
    result = compute_cycling_zones(250)
    top_zone = result.zones[-1]
    assert top_zone.pct_ftp_max is None
    assert top_zone.watts_max is None


def test_zones_are_contiguous_and_non_overlapping():
    result = compute_cycling_zones(250)
    for previous, current in zip(result.zones, result.zones[1:]):
        assert current.pct_ftp_min >= previous.pct_ftp_max


def test_calculates_ftp_from_ramp_test_best_1min_power():
    assert calculate_ftp_from_ramp_test(300) == 225


def test_rejects_negative_ftp():
    with pytest.raises(ValueError):
        compute_cycling_zones(-100)


def test_rejects_non_positive_best_1min_power():
    with pytest.raises(ValueError):
        calculate_ftp_from_ramp_test(0)
