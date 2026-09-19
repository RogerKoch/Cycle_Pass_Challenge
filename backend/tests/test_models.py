from datetime import date

import pytest

from backend.extensions import db
from backend.models.checkins import Checkin
from backend.models.ftp_tests import FtpTest


def test_checkin_ffm_kg_computed_from_weight_and_bodyfat(app):
    checkin = Checkin(checkin_date=date.today(), weight_kg=74.0, bodyfat_pct=23.0, muscle_kg=30.0)
    assert checkin.ffm_kg == pytest.approx(74.0 * 0.77)


def test_ftp_test_stores_computed_ftp_watts(app):
    ftp_test = FtpTest(test_date=date.today(), best_1min_power_watts=300.0, ftp_watts=225)
    db.session.add(ftp_test)
    db.session.commit()
    assert ftp_test.id is not None
    assert ftp_test.ftp_watts == 225


def test_ftp_test_manual_correction_is_optional(app):
    ftp_test = FtpTest(test_date=date.today(), best_1min_power_watts=300.0, ftp_watts=225)
    db.session.add(ftp_test)
    db.session.commit()
    assert ftp_test.manual_correction_pct is None
