import re

import pytest

from backend.config import REPO_ROOT
from backend.engine.baseline import DEFAULT_TARGET_BODYFAT_PCT
from backend.engine.checkin_triggers import (
    DEFICIT_STEP_KCAL,
    DIET_BREAK_DAYS,
    EA_THRESHOLD,
    HRV_DROP_PCT,
    MAX_WEIGHT_LOSS_PCT_PER_WEEK,
    RESTING_HR_RISE_BPM,
)
from backend.engine.cycling_zones import FTP_RAMP_TEST_FACTOR
from backend.engine.nutrition_calc import (
    DEFAULT_DEFICIT_KCAL,
    FAT_G_PER_KG_BODYWEIGHT,
    ACTIVITY_LEVELS,
    NON_EXERCISE_FACTOR,
    PROTEIN_G_PER_KG_FFM,
    STRENGTH_KCAL_PER_SESSION,
)
from backend.engine.training_phase import PHASE_SEQUENCE

FRONTEND = REPO_ROOT / "frontend"
CONTENT = (FRONTEND / "hilfe" / "inhalt.md").read_text(encoding="utf-8")


def _de(value: float) -> str:
    """Zahl so, wie sie im deutschen Text steht (Dezimalkomma, ohne ,0)."""
    return f"{value:g}".replace(".", ",")


def test_help_page_and_content_are_served(client):
    assert client.get("/hilfe/").status_code == 200
    assert client.get("/hilfe/inhalt.md").status_code == 200


@pytest.mark.parametrize("text", [
    f"{_de(FTP_RAMP_TEST_FACTOR * 100)} % deiner besten 1-Minuten-Leistung",
    f"(Büro {_de(NON_EXERCISE_FACTOR)})",
    f"{_de(DEFAULT_DEFICIT_KCAL)} kcal in Base/Build 1",
    f"{_de(PROTEIN_G_PER_KG_FFM)} g pro kg FFM",
    f"{_de(FAT_G_PER_KG_BODYWEIGHT)} g pro kg Gewicht",
    f"{_de(STRENGTH_KCAL_PER_SESSION)} kcal pro Einheit",
    f"{_de(DEFAULT_TARGET_BODYFAT_PCT)} % Körperfett",
    f"schneller als {_de(MAX_WEIGHT_LOSS_PCT_PER_WEEK)} % pro Woche",
    f"Defizit {_de(DEFICIT_STEP_KCAL)} kcal".replace("-", "−"),
    f"Diät-Pause {DIET_BREAK_DAYS} Tage",
    f"unter {_de(EA_THRESHOLD)} kcal/kg FFM",
    f"Ruhepuls +{RESTING_HR_RISE_BPM} oder HRV −{_de(HRV_DROP_PCT)} %",
])
def test_help_numbers_match_engine_constants(text):
    assert text in CONTENT


def test_help_lists_every_activity_level_with_its_factor():
    for label, factor in ACTIVITY_LEVELS.values():
        assert f"| {label} | " in CONTENT and f" | {_de(factor)} |" in CONTENT


def test_help_phase_lengths_match_phase_sequence():
    names = {"phase0_wiedereinstieg": "Wiedereinstieg", "base": "Base", "build1": "Build 1",
             "build2": "Build 2", "peak_taper": "Peak/Taper"}
    for phase_id, weeks in PHASE_SEQUENCE:
        assert f"| {names[phase_id]} | {weeks} Wochen |" in CONTENT


def test_every_info_link_points_to_existing_anchor():
    anchors = set(re.findall(r'<a id="([^"]+)"></a>', CONTENT))
    sources = [p.read_text(encoding="utf-8") for p in FRONTEND.glob("*/*.*") if p.suffix in {".html", ".js"}]
    links = {a for s in sources for a in re.findall(r'hilfe/#([\w-]+)', s)}
    links |= {a for s in sources for a in re.findall(r'infoLink\("([\w-]+)"\)', s)}
    links |= set(re.findall(r"\]\(#([\w-]+)\)", CONTENT))
    assert links, "keine Links gefunden"
    assert links - anchors == set()


def test_help_event_numbers_match_engine_constants():
    from backend.engine import event_prep as ep

    taper = ", ".join(f"{k}: {v}" for k, v in ep.TAPER_DAYS.items())
    assert f"Taper (A: {ep.TAPER_DAYS['A']} Tage, B: {ep.TAPER_DAYS['B']}, C: {ep.TAPER_DAYS['C']})" in CONTENT, taper
    for key, (start, end) in ep.TAPER_VOLUME.items():
        text = f"{key}: {start * 100:.0f} % → {end * 100:.0f} %" if start != end else f"{key}: {start * 100:.0f} %"
        assert text in CONTENT
    assert f"| A, ab {ep.LONG_EVENT_MINUTES} min | {_de(ep.CARBS_LONG_A[3])} g/kg | {_de(ep.CARBS_LONG_A[2])} g/kg | {_de(ep.CARBS_LONG_A[1])} g/kg |" in CONTENT
    assert f"| normal | {_de(ep.CARBS_MEDIUM[2])} g/kg | {_de(ep.CARBS_MEDIUM[1])} g/kg |" in CONTENT
    assert f"| normal | normal | {_de(ep.CARBS_SHORT[1])} g/kg |" in CONTENT
    assert f"auf {_de(ep.LOAD_FAT_G_PER_KG)} g pro kg Gewicht" in CONTENT
    assert f"mindestens {ep.LOADING_MIN_MINUTES} min" in CONTENT
