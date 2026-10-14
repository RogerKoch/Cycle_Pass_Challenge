"""API-Endpunkte fuer Check-ins und FTP-Tests."""

import logging
from datetime import date

from flask import Blueprint, jsonify, request

from backend.engine.cycling_zones import calculate_ftp_from_ramp_test
from backend.extensions import db
from backend.models.checkins import Checkin
from backend.models.ftp_tests import FtpTest
from backend.models.intervals import IcuWellness

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
        "weight_only": checkin.weight_only,
    }


def _serialize_ftp_test(ftp_test: FtpTest) -> dict:
    return {
        "id": ftp_test.id,
        "test_date": ftp_test.test_date.isoformat(),
        # bei FTP aus intervals.icu gibt es keine 1-Minuten-Bestleistung (0 = unbekannt)
        "best_1min_power_watts": ftp_test.best_1min_power_watts or None,
        "ftp_watts": ftp_test.ftp_watts,
        "manual_correction_pct": ftp_test.manual_correction_pct,
        "source": ftp_test.source,
    }


def _carry_forward(weight_kg: float, checkin_date: date) -> tuple[float, float]:
    """Koerperfett und Muskelmasse fuer einen Nur-Gewicht-Check-in: FFM und Muskel des letzten Check-ins bleiben.

    Raises:
        ValueError: ohne vorherigen Check-in (der erste braucht alle Werte) oder wenn die FFM das Gewicht uebersteigt.
    """
    base = Checkin.query.filter(Checkin.checkin_date <= checkin_date).order_by(
        Checkin.checkin_date.desc(), Checkin.created_at.desc()
    ).first() or Checkin.query.order_by(Checkin.checkin_date.asc(), Checkin.created_at.asc()).first()
    if base is None:
        raise ValueError("der erste Check-in braucht Körperfett und Muskelmasse")
    bodyfat_pct = 100 * (1 - base.ffm_kg / weight_kg)
    if not 0 <= bodyfat_pct < 100:
        raise ValueError("Gewicht liegt unter der letzten fettfreien Masse – bitte Körperfett und Muskelmasse erfassen")
    return bodyfat_pct, base.muscle_kg


@checkins_bp.post("")
def create_checkin():
    """Legt einen neuen Check-in an."""
    body = request.get_json(force=True, silent=True) or {}
    weight_only = body.get("bodyfat_pct") is None and body.get("muscle_kg") is None
    try:
        weight_kg = float(body["weight_kg"])
        checkin_date = date.fromisoformat(body["checkin_date"]) if "checkin_date" in body else date.today()
        if weight_kg <= 0:
            raise ValueError(f"weight_kg muss positiv sein, war {weight_kg}")
        if weight_only:
            bodyfat_pct, muscle_kg = _carry_forward(weight_kg, checkin_date)
        else:
            bodyfat_pct = float(body["bodyfat_pct"])
            muscle_kg = float(body["muscle_kg"])
        if not 0 <= bodyfat_pct <= 100:
            raise ValueError(f"bodyfat_pct muss zwischen 0 und 100 liegen, war {bodyfat_pct}")
        if muscle_kg <= 0:
            raise ValueError(f"muscle_kg muss positiv sein, war {muscle_kg}")
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"ungueltige Check-in-Daten: {exc}"}), 400

    checkin = Checkin(
        checkin_date=checkin_date, weight_kg=weight_kg, bodyfat_pct=bodyfat_pct, muscle_kg=muscle_kg,
        weight_only=weight_only,
    )
    db.session.add(checkin)
    db.session.commit()
    return jsonify(_serialize_checkin(checkin)), 201


@checkins_bp.get("")
def list_checkins():
    """Listet alle Check-ins, neueste zuerst."""
    checkins = Checkin.query.order_by(Checkin.checkin_date.desc(), Checkin.created_at.desc()).all()
    imported = {w.checkin_id for w in IcuWellness.query.filter(IcuWellness.checkin_id.isnot(None)).all()}
    return jsonify([
        {**_serialize_checkin(c), "source": "intervals" if c.id in imported else "manual"} for c in checkins
    ]), 200


@checkins_bp.get("/latest")
def get_latest_checkin():
    """Gibt den neuesten Check-in zurueck, oder 404 falls keiner existiert."""
    checkin = Checkin.query.order_by(Checkin.checkin_date.desc(), Checkin.created_at.desc()).first()
    if checkin is None:
        return jsonify({"error": "kein Check-in vorhanden"}), 404
    return jsonify(_serialize_checkin(checkin)), 200


@checkins_bp.post("/ftp-tests")
def create_ftp_test():
    """Legt einen FTP-Eintrag an: entweder Ramp-Test (ftp_watts wird berechnet) oder FTP direkt.

    Body: `best_1min_power_watts` (+ optional `manual_correction_pct`) oder `ftp_watts` (direkt, ohne 1-Min-Wert).
    """
    body = request.get_json(force=True, silent=True) or {}
    try:
        test_date = date.fromisoformat(body["test_date"]) if "test_date" in body else date.today()
        manual_correction_pct = (
            float(body["manual_correction_pct"]) if body.get("manual_correction_pct") is not None else None
        )
        if body.get("ftp_watts") is not None:
            if body.get("best_1min_power_watts") is not None or manual_correction_pct is not None:
                raise ValueError("entweder FTP direkt oder Ramp-Test-Wert (mit Korrektur) angeben")
            ftp_watts = round(float(body["ftp_watts"]))
            if ftp_watts <= 0:
                raise ValueError("ftp_watts muss positiv sein")
            best_1min_power_watts = 0.0  # unbekannt, direkt eingetragen
        else:
            best_1min_power_watts = float(body["best_1min_power_watts"])
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


@checkins_bp.get("/ftp-tests")
def list_ftp_tests():
    """Listet alle FTP-Tests, neueste zuerst."""
    tests = FtpTest.query.order_by(FtpTest.test_date.desc(), FtpTest.created_at.desc()).all()
    return jsonify([_serialize_ftp_test(t) for t in tests]), 200


@checkins_bp.get("/ftp-tests/latest")
def get_latest_ftp_test():
    """Gibt den neuesten FTP-Test zurueck, oder 404 falls keiner existiert."""
    ftp_test = FtpTest.query.order_by(FtpTest.test_date.desc(), FtpTest.created_at.desc()).first()
    if ftp_test is None:
        return jsonify({"error": "kein FTP-Test vorhanden"}), 404
    return jsonify(_serialize_ftp_test(ftp_test)), 200
