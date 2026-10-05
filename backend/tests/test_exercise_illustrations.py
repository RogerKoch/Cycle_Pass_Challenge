import json
from pathlib import Path

from backend.engine.strength_sessions import MOBILITY_ROUTINE, SESSION_IDS, STRENGTH_PHASES, build_strength_session

EXERCISE_DIR = Path(__file__).resolve().parents[2] / "frontend" / "training" / "img" / "exercises"


def _index() -> dict:
    return json.loads((EXERCISE_DIR / "index.json").read_text(encoding="utf-8"))


def _all_exercise_names() -> set[str]:
    names = {e.name for e in MOBILITY_ROUTINE}
    for phase in STRENGTH_PHASES.values():
        for session_id in SESSION_IDS:
            names.update(e.name for e in build_strength_session(session_id, phase).exercises)
    return names


def test_every_exercise_has_an_illustration_entry():
    assert _all_exercise_names() - _index().keys() == set()


def _single_entries() -> dict:
    return {name: entry for name, entry in _index().items() if entry and "parts" not in entry}


def test_every_illustration_file_exists_and_has_a_video_query():
    for name, entry in _single_entries().items():
        assert (EXERCISE_DIR / entry["img"]).is_file(), name
        assert entry["video"].strip(), name


def test_every_svg_is_referenced():
    referenced = {entry["img"] for entry in _single_entries().values()}
    assert {p.name for p in EXERCISE_DIR.glob("*.svg")} == referenced


def test_warmup_parts_exist_for_both_sessions_and_have_illustrations():
    parts = _index()["Aufwärmen/Mobility"]["parts"]
    assert set(parts) == set(SESSION_IDS)
    for session_parts in parts.values():
        assert session_parts
        assert set(session_parts) <= _single_entries().keys()
