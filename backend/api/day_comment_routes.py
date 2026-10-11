"""API-Endpunkte fuer Tageskommentare (ein Freitext pro Datum)."""

import logging
from datetime import date

from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models.day_comments import MAX_COMMENT_LENGTH, DayComment

logger = logging.getLogger(__name__)

day_comments_bp = Blueprint("day_comments", __name__, url_prefix="/api/day-comments")


def _serialize(day: date, comment: DayComment | None) -> dict:
    return {"date": day.isoformat(), "text": comment.text if comment else ""}


@day_comments_bp.get("/<day>")
def get_comment(day: str):
    """Kommentar eines Tages; `text` ist leer, wenn keiner existiert."""
    try:
        parsed = date.fromisoformat(day)
    except ValueError as exc:
        return jsonify({"error": f"ungueltiges Datum: {exc}"}), 400
    return jsonify(_serialize(parsed, DayComment.query.filter_by(day_date=parsed).first())), 200


@day_comments_bp.put("/<day>")
def put_comment(day: str):
    """Speichert den Kommentar eines Tages; leerer Text loescht ihn."""
    try:
        parsed = date.fromisoformat(day)
    except ValueError as exc:
        return jsonify({"error": f"ungueltiges Datum: {exc}"}), 400
    text = (request.get_json(force=True, silent=True) or {}).get("text")
    if not isinstance(text, str) or len(text) > MAX_COMMENT_LENGTH:
        return jsonify({"error": f"text: Text mit max. {MAX_COMMENT_LENGTH} Zeichen erwartet"}), 400
    text = text.strip()
    comment = DayComment.query.filter_by(day_date=parsed).first()
    if not text:
        if comment is not None:
            db.session.delete(comment)
            db.session.commit()
        return jsonify(_serialize(parsed, None)), 200
    if comment is None:
        comment = DayComment(day_date=parsed, text=text)
        db.session.add(comment)
    else:
        comment.text = text
    db.session.commit()
    return jsonify(_serialize(parsed, comment)), 200
