# TODO / Backlog

Stand: 2026-10-05

## Offen

| #  | Thema | Notiz |
|----|-------|-------|
| 1  | ✅ Flacher Bauch als Ziel | In #14 aufgegangen (Fokus Bauch/Core). Bauchumfang wird bewusst nicht gemessen (Entscheid 2026-10-06). |
| 2  | ✅ Benutzer-Dokumentation | Alle Werte, Abkürzungen (FTP, FFM, Z2, Sweet Spot …) und Formeln laienverständlich erklären. Vorschlag akzeptiert: Erklär-Seite in der App (Markdown im Repo), ⓘ-Links aus dem UI, Kapitel 1–7, Begriffe nach Schema Was/Wozu/Berechnung/Beispiel. |
| 3  | ✅ Dehnen am Schluss ersetzen | „Auslaufen/Stretch 5 min“ in A/B durch die Mobility-Routine am Schluss ersetzen (`backend/engine/strength_sessions.py`). Entschieden 2026-10-05. |
| 4  | ✅ Trainingszonen erklären | Coggan-7-Zonen in % FTP; FTP = 75 % der besten 1-min-Leistung im Zwift-Ramp-Test. In Doku (#2) aufnehmen. |
| 5  | ✅ Kraft-Level pro User | Umgesetzt 2026-10-07 als Kraft-Benchmarks (Woche-0-Tests der Recherche) → Stufe je Übung, Core-Freischaltung, Meilensteine; Intervall im Profil 2–8 Wochen (Standard 4), Erinnerung im Review. |
| 6  | Mehrere User | Entschieden: eigene Instanz pro User (eigene DB/Passwort/Pfad, gleicher Code). Server-Setup pro neuem User. |
| 7  | ✅ Barcode-Scanner iPhone | Scan soll automatisch erkennen (kein Auslöser). Auf iPhone kein Ergebnis – Symptome klären, dann debuggen (`frontend/ernaehrung/app.js`, ZXing). |
| 8  | Kapitel UI/Navigation | Gesamt-Überarbeitung des UI, Mix aus Sidebar (Desktop)/Tab-Leiste (Handy) und grünem Karten-Look. Bereiche: Heute, Profil, Training (Kalender Tag/Woche/Monat, geplant vs. gemacht), Check-ins (Wöchentlich/FTP/Kraft-Benchmark mit Chart+Tabelle), Ernährung (Kalender, Mahlzeiten vorplanen, Soll/Ist). Etappen: 1 Shell ✔ (PR #24), 2 Heute ✔ (PR #25), 3 Profil ✔ (PR #26) (Profil + Startwerte + Messwerte unter `/profil/`, Check-in/Review/FTP/Benchmark unter `/checkins/`; manuelle Ist-Zufuhr entfernt), 4 Check-ins ✔ (PR #27), **5 Training-Kalender ✔ in Arbeit** (Tag/Woche/Monat, gemacht/abweichend/geplant; Monats-Endpoint schreibgeschützt; `ensure_week` gegen parallele Anlage abgesichert), 6 Ernährung-Kalender + Mahlzeitenplanung. |
| 9  | Kapitel Pässe-Planung | **Nicht vor 1.12.2026**, ausser explizit angefragt. Benötigt die Pass-Excel-Dateien. |
| 10 | FTP eintragen | Ramp-Test Anfang Oktober → FTP erfassen, damit Zonen/Watt freigeschaltet werden. |
| 11 | Waage/Wellness-Sync | intervals.icu-Wellness inaktiv → keine automatischen Check-ins. Aktivieren oder manuell erfassen. |
| 12 | ✅ DB-Backup Server | War keins vorhanden. Eingerichtet und getestet 2026-10-06: `flask backup-db` (30 lokal) + Aufgabe 03:30 + rclone → Google Drive (90 Tage), Runbook `server-infra/docs/3-backup.md`. |
| 13 | ✅ Zwift `.zwo`-Export | Umgesetzt 2026-10-06: Workouts der nächsten 7 Tage automatisch via intervals.icu → Zwift (bei Kalender-Änderung + Sync), `.zwo`-Download als Fallback. **Einmalig:** intervals.icu → Settings → Zwift → Connect. |
| 14 | ✅ Fokus-Thema (z. B. flacher Bauch) | Umgesetzt 2026-10-06: Profilfeld Kraft-Fokus (Bauch/Core, Oberkörper, Beine/Gesäss, Mobility) → +1 Satz + Zusatzübung aus der Recherche-Bibliothek, +10 min. Bein-Fokus pausiert in Peak/Taper/Passsaison. Keine Ernährungs-/Ausdauer-Akzente (Entscheid). |
| 15 | ✅ Wie wird der Grundumsatz berechnet | Mifflin-St Jeor (10 × kg + 6,25 × cm − 5 × Alter + 5); gemessener RMR ersetzt die Schätzung. Erklärt in `/hilfe/#grundumsatz`. |
| 16 | ✅ Man sollte abfragen können was der Beruf ist damit man den BMR Multiplikator einstellen kann, aufgrund des trainingsplan vervollständigt sich das bild | Heute fix 1,45. Vorschlag: Profilfeld „Alltag/Beruf“ mit 5 Stufen (PAL ohne Sport, DGE): nur sitzend 1,2 · Büro 1,45 · gemischt 1,65 · stehend/gehend 1,85 · körperlich schwer 2,1. Training bleibt separat (keine Doppelzählung). |
| 17 | ✅ Event-Vorbereitung (Training + Ernährung) | Umgesetzt 2026-10-07 (Entscheid: Events übers ganze Jahr, nicht nur Pass-Ziel): Event im Training anlegen (Datum, Dauer, Prio A/B/C, Rennen/Tour) → Taper (A 14 / B 7 / C 2 Tage), Opener T-1, Carb-Loading T-3…T-1 (bis 10 g/kg), Eventtag-Fueling, Recovery 1–3 Tage, Defizit pausiert, Gewichtstrend im Fenster ignoriert. Recherche in `docs/research/event-vorbereitung.md` (Quellenwerte aus Zusammenfassungen, Primärquellen noch gegenprüfen). Hilfe `/hilfe/#events`. |
