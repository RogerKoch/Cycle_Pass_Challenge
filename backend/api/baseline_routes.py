"""API-Endpunkte fuer Baseline-Werte (estimated -> measured)."""

import logging
import math

from flask import Blueprint, jsonify, request

from backend.engine.baseline import (
    BASELINE_FIELDS,
    DEFAULT_TARGET_BODYFAT_PCT,
    ResolvedValue,
    calculate_rmr_ratio,
    calculate_target_weight_kg,
    resolve,
)
from backend.engine.nutrition_calc import calculate_bmr
from backend.extensions import db
from backend.models.baseline_measurements import BaselineMeasurement
from backend.models.checkins import Checkin
from backend.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

baseline_bp = Blueprint("baseline", __name__, url_prefix="/api/baseline")


def resolve_baseline(profile: UserProfile, checkin: Checkin) -> dict[str, tuple[ResolvedValue, str | None]]:
    """Loest alle Baseline-Felder auf (Messwert vor Schaetzwert).

    Args:
        profile: Nutzerprofil (Alter, Groesse).
        checkin: neuester Check-in (Gewicht, KFA fuer die Schaetzwerte).

    Returns:
        Feldname -> (ResolvedValue, updated_at als ISO-String oder None).
    """
    estimates: dict[str, float | None] = {
        "rmr_kcal": calculate_bmr(checkin.weight_kg, profile.height_cm, profile.age),
        "ffm_kg": checkin.ffm_kg,
        "bodyfat_pct": checkin.bodyfat_pct,
        "target_bodyfat_pct": DEFAULT_TARGET_BODYFAT_PCT,
    }
    estimate_updated_at = {
        "rmr_kcal": checkin.created_at.isoformat(),
        "ffm_kg": checkin.created_at.isoformat(),
        "bodyfat_pct": checkin.created_at.isoformat(),
    }
    measured = {m.field_name: m for m in BaselineMeasurement.query.all()}

    result: dict[str, tuple[ResolvedValue, str | None]] = {}
    for field in BASELINE_FIELDS:
        row = measured.get(field)
        resolved = resolve(row.measured_value if row else None, estimates.get(field))
        updated_at = row.updated_at.isoformat() if row else estimate_updated_at.get(field)
        result[field] = (resolved, updated_at)
    return result


@baseline_bp.get("")
def get_baseline():
    """Gibt alle Baseline-Felder (Wert, Quelle, Zeitpunkt) und die abgeleiteten Werte zurueck."""
    profile = UserProfile.query.first()
    if profile is None:
        return jsonify({"error": "kein Profil vorhanden"}), 404
    checkin = Checkin.query.order_by(Checkin.checkin_date.desc(), Checkin.created_at.desc()).first()
    if checkin is None:
        return jsonify({"error": "kein Check-in vorhanden, Schaetzwerte nicht berechenbar"}), 422

    fields = resolve_baseline(profile, checkin)
    rmr, ffm, target_bf = fields["rmr_kcal"][0], fields["ffm_kg"][0], fields["target_bodyfat_pct"][0]
    derived = {
        "rmr_ratio": calculate_rmr_ratio(rmr.value, ffm.value),
        "target_weight_kg": calculate_target_weight_kg(ffm.value, target_bf.value),
    }
    return jsonify(
        {
            "fields": {
                name: {"value": r.value, "source": r.source, "updated_at": updated_at}
                for name, (r, updated_at) in fields.items()
            },
            "derived": derived,
        }
    ), 200


@baseline_bp.put("/<field>")
def set_measured_value(field: str):
    """Setzt (oder ueberschreibt) den Messwert eines Baseline-Feldes."""
    if field not in BASELINE_FIELDS:
        return jsonify({"error": f"unbekanntes Feld '{field}'", "allowed": list(BASELINE_FIELDS)}), 400

    body = request.get_json(force=True, silent=True) or {}
    try:
        value = float(body["value"])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"value muss positiv sein, war {value}")
        if field.endswith("_pct") and value >= 100:
            raise ValueError(f"{field} muss unter 100 liegen, war {value}")
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltiger Messwert: {exc}"}), 400

    row = BaselineMeasurement.query.filter_by(field_name=field).first()
    if row is None:
        row = BaselineMeasurement(field_name=field, measured_value=value)
        db.session.add(row)
    else:
        row.measured_value = value
    db.session.commit()
    return jsonify(
        {"field": field, "value": row.measured_value, "source": "measured", "updated_at": row.updated_at.isoformat()}
    ), 200
