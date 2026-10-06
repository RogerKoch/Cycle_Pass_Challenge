# TODO / Backlog

Stand: 2026-10-05

## Offen

| #  | Thema | Notiz |
|----|-------|-------|
| 1  | Flacher Bauch als Ziel | Heute nur indirekt (kcal-Defizit, Körperfett-%, Core). Vorschlag: Bauchumfang wöchentlich im Check-in erfassen + Trend anzeigen. |
| 2  | ✅ Benutzer-Dokumentation | Alle Werte, Abkürzungen (FTP, FFM, Z2, Sweet Spot …) und Formeln laienverständlich erklären. Vorschlag akzeptiert: Erklär-Seite in der App (Markdown im Repo), ⓘ-Links aus dem UI, Kapitel 1–7, Begriffe nach Schema Was/Wozu/Berechnung/Beispiel. |
| 3  | ✅ Dehnen am Schluss ersetzen | „Auslaufen/Stretch 5 min“ in A/B durch die Mobility-Routine am Schluss ersetzen (`backend/engine/strength_sessions.py`). Entschieden 2026-10-05. |
| 4  | ✅ Trainingszonen erklären | Coggan-7-Zonen in % FTP; FTP = 75 % der besten 1-min-Leistung im Zwift-Ramp-Test. In Doku (#2) aufnehmen. |
| 5  | Kraft-Level pro User | Heute kein Level, nur Kraftphasen 1–3. Einstufung (Einsteiger/Mittel/Fortgeschritten) → Übungsvarianten/Volumen. |
| 6  | Mehrere User | Entschieden: eigene Instanz pro User (eigene DB/Passwort/Pfad, gleicher Code). Server-Setup pro neuem User. |
| 7  | ✅ Barcode-Scanner iPhone | Scan soll automatisch erkennen (kein Auslöser). Auf iPhone kein Ergebnis – Symptome klären, dann debuggen (`frontend/ernaehrung/app.js`, ZXing). |
| 8  | Kapitel UI/Navigation | Gesamt-Navigation, Gruppierung der Seiten. Eigenes Kapitel. |
| 9  | Kapitel Pässe-Planung | **Nicht vor 1.12.2026**, ausser explizit angefragt. Benötigt die Pass-Excel-Dateien. |
| 10 | FTP eintragen | Ramp-Test Anfang Oktober → FTP erfassen, damit Zonen/Watt freigeschaltet werden. |
| 11 | Waage/Wellness-Sync | intervals.icu-Wellness inaktiv → keine automatischen Check-ins. Aktivieren oder manuell erfassen. |
| 12 | DB-Backup Server | Prüfen, ob die SQLite-DB auf 161.97.157.97 gesichert wird. |
| 13 | Zwift `.zwo`-Export | Früher als „später“ vereinbart. |
| 14 | Fokus-Thema (z. B. flacher Bauch) | Wählbarer Fokus steuert Übungsauswahl/Volumen + Ernährungs-/Ausdauer-Akzente. Zusammen mit #1 und #5 umsetzen. |
| 15 | ✅ Wie wird der Grundumsatz berechnet | Mifflin-St Jeor (10 × kg + 6,25 × cm − 5 × Alter + 5); gemessener RMR ersetzt die Schätzung. Erklärt in `/hilfe/#grundumsatz`. |
| 16 | ✅ Man sollte abfragen können was der Beruf ist damit man den BMR Multiplikator einstellen kann, aufgrund des trainingsplan vervollständigt sich das bild | Heute fix 1,45. Vorschlag: Profilfeld „Alltag/Beruf“ mit 5 Stufen (PAL ohne Sport, DGE): nur sitzend 1,2 · Büro 1,45 · gemischt 1,65 · stehend/gehend 1,85 · körperlich schwer 2,1. Training bleibt separat (keine Doppelzählung). |
