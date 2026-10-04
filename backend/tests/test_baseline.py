import pytest

from backend.engine.baseline import (
    calculate_energy_availability,
    calculate_rmr_ratio,
    calculate_target_weight_kg,
    resolve,
)


def test_measured_value_takes_precedence_over_estimate():
    resolved = resolve(measured=1700.0, estimated=1581.0)
    assert resolved.value == 1700.0
    assert resolved.source == "measured"


def test_falls_back_to_estimate_when_no_measurement():
    resolved = resolve(measured=None, estimated=1581.0)
    assert resolved.value == 1581.0
    assert resolved.source == "estimated"


def test_resolves_to_none_when_neither_value_exists():
    resolved = resolve(measured=None, estimated=None)
    assert resolved.value is None
    assert resolved.source is None


def test_rmr_ratio_matches_reference_formula():
    # 1581 / (500 + 22*57) = 1581 / 1754
    assert calculate_rmr_ratio(1581.0, 57.0) == pytest.approx(1581.0 / 1754.0)


def test_target_weight_reaches_68kg_at_16_percent_bodyfat():
    assert calculate_target_weight_kg(57.0, 16.0) == pytest.approx(67.86, abs=0.01)


def test_target_weight_rejects_100_percent_bodyfat():
    with pytest.raises(ValueError):
        calculate_target_weight_kg(57.0, 100.0)


def test_energy_availability_subtracts_training_and_divides_by_ffm():
    assert calculate_energy_availability(2500.0, 700.0, 57.0) == pytest.approx(1800.0 / 57.0)


def test_energy_availability_rejects_non_positive_ffm():
    with pytest.raises(ValueError):
        calculate_energy_availability(2500.0, 700.0, 0.0)
