"""Erledigte Saetze je Tag und Uebung (Haken in der Krafteinheit bzw. Mobility)."""

from datetime import date

from backend.extensions import db


class SetLog(db.Model):
    """Ein abgehakter Satz. Nur erledigte Saetze werden gespeichert; Abhaken loescht die Zeile."""

    __tablename__ = "set_logs"
    __table_args__ = (db.UniqueConstraint("day_date", "exercise_name", "set_index"),)

    id: int = db.Column(db.Integer, primary_key=True)
    day_date: date = db.Column(db.Date, nullable=False, index=True)
    exercise_name: str = db.Column(db.String(100), nullable=False)
    set_index: int = db.Column(db.Integer, nullable=False)  # 0-basiert


def sets_done(day: date) -> dict[str, list[int]]:
    """Erledigte Saetze eines Tages als Uebungsname -> sortierte Satz-Indizes."""
    done: dict[str, list[int]] = {}
    for row in SetLog.query.filter_by(day_date=day).order_by(SetLog.set_index):
        done.setdefault(row.exercise_name, []).append(row.set_index)
    return done
