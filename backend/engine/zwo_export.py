"""Export einer Rad-Einheit als Zwift-Workout (.zwo).

.zwo-Leistungen sind Anteile der FTP (1.0 = 100 %); Zwift rechnet mit seiner eigenen FTP in Watt um.
Der Export braucht deshalb keinen erfassten FTP-Test.

Annahme: %-Bereiche (z. B. Sweet Spot 88–94 %) werden als Mittelwert vorgegeben (ERG-Ziel).
"""

import logging
import re
import xml.etree.ElementTree as ET

from backend.engine.cycling_sessions import CyclingSession, Segment

logger = logging.getLogger(__name__)

WARMUP_LABEL = "Einfahren"  # siehe cycling_sessions._warmup
COOLDOWN_LABEL = "Ausfahren"  # siehe cycling_sessions._cooldown


def _ratio(pct: float) -> str:
    return f"{pct / 100:.3f}"


def _cadence(cadence_rpm: str | None) -> str | None:
    """'50–60' -> '55', '90' -> '90'; None ohne Vorgabe."""
    if not cadence_rpm:
        return None
    numbers = [int(n) for n in re.findall(r"\d+", cadence_rpm)]
    return str(round(sum(numbers) / len(numbers))) if numbers else None


def _segment_element(segment: Segment) -> ET.Element:
    duration = str(round(segment.minutes * 60))
    low, high = segment.pct_ftp_low, segment.pct_ftp_high
    if low is None or high is None:
        element = ET.Element("FreeRide", Duration=duration)
    elif segment.label == WARMUP_LABEL:
        element = ET.Element("Warmup", Duration=duration, PowerLow=_ratio(low), PowerHigh=_ratio(high))
    elif segment.label == COOLDOWN_LABEL:
        element = ET.Element("Cooldown", Duration=duration, PowerLow=_ratio(high), PowerHigh=_ratio(low))
    else:
        element = ET.Element("SteadyState", Duration=duration, Power=_ratio((low + high) / 2))
    cadence = _cadence(segment.cadence_rpm)
    if cadence:
        element.set("Cadence", cadence)
    ET.SubElement(element, "textevent", timeoffset="0", message=segment.label)
    return element


def session_to_zwo(session: CyclingSession, name: str | None = None) -> str:
    """Erzeugt den .zwo-Inhalt einer Rad-Einheit.

    Args:
        session: Rad-Einheit (inkl. Deload/Dauer-Anpassung).
        name: Workout-Name in Zwift; Default ist der Titel der Einheit.

    Returns:
        XML-Text der .zwo-Datei.
    """
    root = ET.Element("workout_file")
    ET.SubElement(root, "author").text = "Cycle Pass Challenge"
    ET.SubElement(root, "name").text = name or session.title
    ET.SubElement(root, "description").text = " ".join(p for p in (session.note, session.zwift_hint) if p)
    ET.SubElement(root, "sportType").text = "bike"
    ET.SubElement(root, "tags")
    workout = ET.SubElement(root, "workout")
    for segment in session.segments:
        if segment.minutes > 0:
            workout.append(_segment_element(segment))
    ET.indent(root)
    return ET.tostring(root, encoding="unicode")
