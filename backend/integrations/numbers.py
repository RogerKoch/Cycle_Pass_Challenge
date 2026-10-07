"""Gemeinsame Zahl-Konvertierung fuer externe API-Antworten."""

import math


def finite_number(value: object) -> float | None:
    """Wert als endliche Zahl; None bei None, bool, Text ohne Zahl, NaN und inf."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
