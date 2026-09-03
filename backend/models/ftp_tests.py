"""Zwift-Ramp-Test-Ergebnisse."""

from datetime import date, datetime, timezone

from backend.extensions import db


class FtpTest(db.Model):
    """Ein FTP-Test. `ftp_watts` wird beim Anlegen serverseitig berechnet."""

    __tablename__ = "ftp_tests"

    id: int = db.Column(db.Integer, primary_key=True)
    test_date: date = db.Column(db.Date, nullable=False, index=True)
    best_1min_power_watts: float = db.Column(db.Float, nullable=False)
    ftp_watts: int = db.Column(db.Integer, nullable=False)
    manual_correction_pct: float | None = db.Column(db.Float, nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
