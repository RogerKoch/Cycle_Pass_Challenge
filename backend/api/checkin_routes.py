"""API-Endpunkte fuer Check-ins und FTP-Tests."""

import logging
from datetime import date

from flask import Blueprint, jsonify, request

from backend.engine.cycling_zones import calculate_ftp_from_ramp_test
from backend.extensions import db
from backend.models.checkins import Checkin
from backend.models.ftp_tests import FtpTest

logger = logging.getLogger(__name__)

checkins_bp = Blueprint("checkins", __name__, url_prefix="/api/checkins")


def _serialize_checkin(checkin: Checkin) -> dict:
    return {
        "id": checkin.id,
        "checkin_date": checkin.checkin_date.isoformat(),
        "weight_kg": checkin.weight_kg,
        "bodyfat_pct": checkin.bodyfat_pct,
        "muscle_kg": checkin.muscle_kg,
        "ffm_kg": checkin.ffm_kg,
    }


def _serialize_ftp_test(ftp_test: FtpTest) -> dict:
    return {
        "id": ftp_test.id,
        "test_date": ftp_test.test_date.isoformat(),
        "best_1min_power_watts": ftp_test.best_1min_power_watts,
        "ftp_watts": ftp_test.ftp_watts,
        "manual_correction_pct": ftp_test.manual_correction_pct,
    }


@checkins_bp.post("")
def create_checkin():
    """Legt einen neuen Check-in an."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        weight_kg = float(body["weight_kg"])
        bodyfat_pct = float(body["bodyfat_pct"])
        muscle_kg = float(body["muscle_kg"])
        checkin_date = date.fromisoformat(body["checkin_date"]) if "checkin_date" in body else date.today()
        if weight_kg <= 0:
            raise ValueError(f"weight_kg muss positiv sein, war {weight_kg}")
        if not 0 <= bodyfat_pct <= 100:
            raise ValueError(f"bodyfat_pct muss zwischen 0 und 100 liegen, war {bodyfat_pct}")
        if muscle_kg <= 0:
            raise ValueError(f"muscle_kg muss positiv sein, war {muscle_kg}")
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Check-in-Daten: {exc}"}), 400

    checkin = Checkin(
        checkin_date=checkin_date, weight_kg=weight_kg, bodyfat_pct=bodyfat_pct, muscle_kg=muscle_kg
    )
    db.session.add(checkin)
    db.session.commit()
    return jsonify(_serialize_checkin(checkin)), 201


@checkins_bp.get("")
def list_checkins():
    """Listet alle Check-ins, neueste zuerst."""
    checkins = Checkin.query.order_by(Checkin.checkin_date.desc(), Checkin.created_at.desc()).all()
    return jsonify([_serialize_checkin(c) for c in checkins]), 200


@checkins_bp.get("/latest")
def get_latest_checkin():
    """Gibt den neuesten Check-in zurueck, oder 404 falls keiner existiert."""
    checkin = Checkin.query.order_by(Checkin.checkin_date.desc(), Checkin.created_at.desc()).first()
    if checkin is None:
        return jsonify({"error": "kein Check-in vorhanden"}), 404
    return jsonify(_serialize_checkin(checkin)), 200


@checkins_bp.post("/ftp-tests")
def create_ftp_test():
    """Legt einen FTP-Test an; ftp_watts wird serverseitig berechnet."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        best_1min_power_watts = float(body["best_1min_power_watts"])
        test_date = date.fromisoformat(body["test_date"]) if "test_date" in body else date.today()
        manual_correction_pct = (
            float(body["manual_correction_pct"]) if body.get("manual_correction_pct") is not None else None
        )
        ftp_watts = calculate_ftp_from_ramp_test(best_1min_power_watts)
        if manual_correction_pct is not None:
            ftp_watts = round(ftp_watts * (1 + manual_correction_pct / 100))
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige FTP-Test-Daten: {exc}"}), 400

    ftp_test = FtpTest(
        test_date=test_date,
        best_1min_power_watts=best_1min_power_watts,
        ftp_watts=ftp_watts,
        manual_correction_pct=manual_correction_pct,
    )
    db.session.add(ftp_test)
    db.session.commit()
    return jsonify(_serialize_ftp_test(ftp_test)), 201


@checkins_bp.get("/ftp-tests/latest")
def get_latest_ftp_test():
    """Gibt den neuesten FTP-Test zurueck, oder 404 falls keiner existiert."""
    ftp_test = FtpTest.query.order_by(FtpTest.test_date.desc(), FtpTest.created_at.desc()).first()
    if ftp_test is None:
        return jsonify({"error": "kein FTP-Test vorhanden"}), 404
    return jsonify(_serialize_ftp_test(ftp_test)), 200
