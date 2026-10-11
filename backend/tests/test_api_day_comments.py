def test_get_returns_empty_text_without_comment(client):
    assert client.get("/api/day-comments/2026-10-12").get_json() == {"date": "2026-10-12", "text": ""}


def test_put_saves_and_overwrites_comment(client):
    client.put("/api/day-comments/2026-10-12", json={"text": "Beine schwer"})
    assert client.get("/api/day-comments/2026-10-12").get_json()["text"] == "Beine schwer"
    client.put("/api/day-comments/2026-10-12", json={"text": "Besser nach Mittag"})
    assert client.get("/api/day-comments/2026-10-12").get_json()["text"] == "Besser nach Mittag"


def test_blank_text_deletes_comment(client):
    client.put("/api/day-comments/2026-10-12", json={"text": "Notiz"})
    assert client.put("/api/day-comments/2026-10-12", json={"text": "   "}).get_json()["text"] == ""
    assert client.get("/api/day-comments/2026-10-12").get_json()["text"] == ""


def test_comments_of_different_days_are_independent(client):
    client.put("/api/day-comments/2026-10-12", json={"text": "A"})
    client.put("/api/day-comments/2026-10-13", json={"text": "B"})
    assert client.get("/api/day-comments/2026-10-12").get_json()["text"] == "A"
    assert client.get("/api/day-comments/2026-10-13").get_json()["text"] == "B"


def test_rejects_invalid_date_type_and_length(client):
    assert client.get("/api/day-comments/gestern").status_code == 400
    assert client.put("/api/day-comments/gestern", json={"text": "x"}).status_code == 400
    assert client.put("/api/day-comments/2026-10-12", json={"text": 5}).status_code == 400
    assert client.put("/api/day-comments/2026-10-12", json={"text": "x" * 2001}).status_code == 400
