import xml.etree.ElementTree as ET

from backend.engine.cycling_sessions import build_cycling_session
from backend.engine.zwo_export import session_to_zwo


def _workout(slot, phase, week):
    root = ET.fromstring(session_to_zwo(build_cycling_session(slot, phase, week)))
    return root, list(root.find("workout"))


def test_sweet_spot_maps_to_warmup_steady_states_and_cooldown():
    root, steps = _workout("schluessel_1", "base", 1)
    assert root.find("name").text == "Sweet Spot 3×10 min"
    assert root.find("sportType").text == "bike"
    assert [s.tag for s in steps] == ["Warmup", "SteadyState", "SteadyState", "SteadyState", "SteadyState",
                                      "SteadyState", "Cooldown"]
    warmup, cooldown = steps[0], steps[-1]
    assert (warmup.get("Duration"), warmup.get("PowerLow"), warmup.get("PowerHigh")) == ("900", "0.500", "0.650")
    assert (cooldown.get("PowerLow"), cooldown.get("PowerHigh")) == ("0.550", "0.400")


def test_interval_range_is_exported_as_midpoint_with_label():
    _, steps = _workout("schluessel_1", "base", 1)
    work = steps[1]
    assert (work.get("Duration"), work.get("Power")) == ("600", "0.910")
    assert work.find("textevent").get("message") == "Sweet Spot 1/3"


def test_cadence_range_is_exported_as_midpoint():
    _, steps = _workout("schluessel_2", "base", 1)
    assert steps[1].get("Cadence") == "55"
    assert steps[2].get("Cadence") is None  # Pause ohne Kadenzvorgabe


def test_ramp_test_without_power_target_becomes_free_ride():
    root, steps = _workout("ftp_test", "base", 1)
    assert [s.tag for s in steps] == ["Warmup", "FreeRide", "Cooldown"]
    assert "Ramp Test" in root.find("description").text


def test_total_duration_matches_session():
    session = build_cycling_session("lang", "build1", 1)
    steps = ET.fromstring(session_to_zwo(session)).find("workout")
    assert sum(int(s.get("Duration")) for s in steps) == session.minutes * 60
