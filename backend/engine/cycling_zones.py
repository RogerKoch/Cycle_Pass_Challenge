"""Coggan-7-Zonen-Modell (% der FTP) und FTP-Ableitung aus dem Zwift-Ramp-Test.

Quelle: docs/research/Trainingsplan Ausdauer.md, Zonentabelle aus docs/data-model.yaml.
"""

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# (zone_id, pct_ftp_min, pct_ftp_max) - pct_ftp_max=None bedeutet nach oben offen.
_ZONE_TABLE: list[tuple[str, float, float | None]] = [
    ("Z1_aktive_erholung", 0.0, 55.0),
    ("Z2_grundlagenausdauer", 55.0, 75.0),
    ("Z3_tempo", 76.0, 87.0),
    ("sweet_spot", 88.0, 94.0),
    ("Z4_schwelle", 95.0, 105.0),
    ("Z5_vo2max", 106.0, 120.0),
    ("Z6_Z7_anaerob", 120.0, None),
]

FTP_RAMP_TEST_FACTOR = 0.75


@dataclass
class PowerZone:
    """Eine Coggan-Leistungszone, in % FTP und in Watt."""

    zone_id: str
    pct_ftp_min: float
    pct_ftp_max: float | None
    watts_min: int
    watts_max: int | None


@dataclass
class ZoneResult:
    """Ergebnis der Zonenberechnung, deckt den Fall unbekannter FTP explizit ab."""

    available: bool
    ftp_watts: int | None
    zones: list[PowerZone] | None
    message: str | None


def compute_cycling_zones(ftp_watts: int | None) -> ZoneResult:
    """Leitet die Coggan-Leistungszonen aus der FTP ab.

    Args:
        ftp_watts: aktuelle FTP in Watt, oder None falls noch nicht getestet.

    Returns:
        ZoneResult mit available=False und Hinweistext, falls ftp_watts None ist;
        sonst available=True mit den berechneten Zonen.

    Raises:
        ValueError: wenn ftp_watts negativ oder null ist.
    """
    if ftp_watts is None:
        return ZoneResult(
            available=False,
            ftp_watts=None,
            zones=None,
            message="FTP noch nicht getestet (Zwift-Ramp-Test steht aus).",
        )
    if ftp_watts <= 0:
        raise ValueError(f"ftp_watts muss positiv sein, war {ftp_watts}")

    zones = [
        PowerZone(
            zone_id=zone_id,
            pct_ftp_min=pct_min,
            pct_ftp_max=pct_max,
            watts_min=math.ceil(ftp_watts * pct_min / 100),
            watts_max=math.floor(ftp_watts * pct_max / 100) if pct_max is not None else None,
        )
        for zone_id, pct_min, pct_max in _ZONE_TABLE
    ]
    return ZoneResult(available=True, ftp_watts=ftp_watts, zones=zones, message=None)


def calculate_ftp_from_ramp_test(best_1min_power_watts: float) -> int:
    """Schaetzt die FTP aus der besten 1-Minuten-Leistung eines Ramp-Tests.

    Args:
        best_1min_power_watts: beste durchgehaltene 1-Minuten-Leistung im Test.

    Returns:
        Geschaetzte FTP in Watt (gerundet).

    Raises:
        ValueError: wenn best_1min_power_watts negativ oder null ist.
    """
    if best_1min_power_watts <= 0:
        raise ValueError(f"best_1min_power_watts muss positiv sein, war {best_1min_power_watts}")
    return round(best_1min_power_watts * FTP_RAMP_TEST_FACTOR)
