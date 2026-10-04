# Alpenpässe-App

Lokale Web-App (Einzelperson) für Rad-Trainings- und Ernährungsplanung im Hinblick auf die
Passsaison. Projekt-Brief: [CLAUDE.md](CLAUDE.md), Architektur: [docs/architecture.md](docs/architecture.md),
Formeln/Parameter: [docs/data-model.yaml](docs/data-model.yaml).

## Setup

```bash
python -m venv C:\dev\virtualenvs\cycle_pass_challenge
C:\dev\virtualenvs\cycle_pass_challenge\Scripts\pip install -r requirements.txt
```

## Start / Tests

```bash
C:\dev\virtualenvs\cycle_pass_challenge\Scripts\python main.py
```

Dashboard: http://127.0.0.1:5000 (SQLite-DB `alpenpaesse.db` entsteht beim ersten Start).
Ernährungs-Tagebuch (mobil): http://127.0.0.1:5000/ernaehrung/

Lebensmittel-Datenbank einmalig (und nach neuer BLV-Version) importieren:

```bash
C:\dev\virtualenvs\cycle_pass_challenge\Scripts\flask --app main.py import-blv data/Schweizer_Nahrwertdatenbank.xlsx
```

Nährwerte: Schweizer Nährwertdatenbank, Bundesamt für Lebensmittelsicherheit und Veterinärwesen (BLV),
[naehrwertdaten.ch](https://naehrwertdaten.ch) · Barcodes: [Open Food Facts](https://openfoodfacts.org) (ODbL).

```bash
C:\dev\virtualenvs\cycle_pass_challenge\Scripts\python -m pytest backend/tests
```

## Betrieb auf dem Server

Läuft unter `https://161.97.157.97/cpc/` hinter Caddy. Setup und Runbook liegen im Repo `server-infra`.
Produktions-Einstieg ist `serve.py` (waitress, `127.0.0.1:8101`). Ohne Login-Konfiguration startet er nicht.

`instance/config.py` (nicht versioniert):

```python
SECRET_KEY = "..."      # python -c "import secrets; print(secrets.token_hex(32))"
PASSWORD_HASH = "..."   # flask --app main.py hash-password
```

Lokal ohne `instance/config.py` gibt es keinen Login. Um den Login lokal über HTTP zu testen, zusätzlich
`SESSION_COOKIE_SECURE = False` setzen.

## Dashboard

| Abschnitt | Zweck |
|---|---|
| Profil | Alter, Grösse, Programmstart (steuert die Trainingsphase) |
| Check-in | Gewicht, Körperfett, Muskelmasse (FFM wird berechnet) |
| FTP-Test | Beste 1-Min-Leistung → FTP = 75 %, optionale manuelle Korrektur |
| Messwerte | Diagnostik-Werte (RMR, FFM, KFA, VT1/VT2 …); bis dahin gelten Schätzwerte |
| Ist-Zufuhr heute | Tagessumme kcal/Makros manuell setzen (wird vom Ernährungs-Tagebuch überschrieben, sobald es Einträge gibt) |
| Heute | Tagesparameter → Phase, Rad-Zonen, kcal-Ziel, Makros, Soll/Ist, Energy Availability |

Ohne FTP-Test zeigt "Heute" statt der Zonen einen Hinweis.

## API

| Methode | Pfad | Zweck |
|---|---|---|
| GET / POST / PUT | `/api/profile` | Profil lesen / anlegen (409 falls vorhanden) / ändern |
| GET / POST | `/api/checkins` | Check-ins listen (neueste zuerst) / erfassen |
| GET | `/api/checkins/latest` | Neuester Check-in |
| POST | `/api/checkins/ftp-tests` | FTP-Test erfassen (`best_1min_power_watts`, optional `test_date`, `manual_correction_pct`) |
| GET | `/api/checkins/ftp-tests/latest` | Neuester FTP-Test |
| GET | `/api/baseline` | Alle Baseline-Felder (Wert, Quelle `estimated`/`measured`, Zeitpunkt) + abgeleitete Werte |
| PUT | `/api/baseline/<feld>` | Messwert setzen (`{"value": 1800}`), überschreibt die Schätzung |
| PUT | `/api/intake/<YYYY-MM-DD>` | Tagessumme setzen/überschreiben (`kcal`, `protein_g`, `carbs_g`, `fat_g`), idempotent |
| GET | `/api/intake/<YYYY-MM-DD>` | Tagessumme lesen (404 falls keine) |
| GET | `/api/intake?from=&to=` | Tagessummen im Zeitraum |
| GET | `/api/foods?q=&limit=` | Lebensmittel suchen; ohne `q` zuletzt verwendete |
| GET / PATCH | `/api/foods/<id>` | Lebensmittel lesen / Portion setzen (Name+Nährwerte nur bei eigenen) |
| POST | `/api/foods` | Eigenes Lebensmittel (pro 100 g, optional `portion_label`/`portion_g`, `barcode`) |
| GET | `/api/foods/barcode/<ean>` | Lokal, sonst Open Food Facts (Treffer wird gespeichert) |
| GET | `/api/food-log/<YYYY-MM-DD>` | Einträge je Mahlzeit + Tagessumme |
| POST | `/api/food-log` | `{date, meal, food_id, grams}` oder Schnelleintrag `{date, meal, label, kcal, protein_g, carbs_g, fat_g}` |
| PATCH / DELETE | `/api/food-log/<id>` | Menge ändern / Eintrag löschen |
| GET / POST | `/api/meal-templates` | Vorlagen listen / anlegen (`items` oder `from_date` + `meal`) |
| DELETE | `/api/meal-templates/<id>` | Vorlage löschen |
| POST | `/api/meal-templates/<id>/apply` | `{date, meal?}` → Einträge anlegen |
| GET | `/api/plan/today` | Query: `cycling_hours`, `cycling_intensity`, `strength_sessions`, `day_type` |

Werte: `cycling_intensity` = `leicht_rekom` · `moderat_base` · `zuegig_tempo` · `rennen_intervalle` · `sehr_hart`;
`day_type` = `ruhetag` · `moderater_tag` · `langer_harter_tag`.

## Berechnungslogik

| Thema | Regel |
|---|---|
| BMR | Mifflin-St Jeor (Mann) |
| Erhaltung | BMR × 1.45 + Rad-kcal (MET-Tabelle, auf aktuelles Gewicht skaliert) + 300 kcal je Krafteinheit |
| Defizit | 350 kcal nur in Phase `base` und `build1`, sonst 0 |
| Phasen | ab Programmstart: phase0 2 Wo → base 8 → build1 8 → build2 5 → peak_taper 5 → passsaison (Längen sind Annahmen, siehe `backend/engine/training_phase.py`) |
| Makros | Protein 2.6 g/kg FFM, Fett 0.95 g/kg, KH 3 / 5 / 7 g/kg je Tagestyp |
| Messwert-Fallback | Messwert vor Schätzwert (`value`, `source`, `updated_at`). Nur Messwerte werden gespeichert, Schätzwerte und abgeleitete Felder (`rmr_ratio`, `target_weight_kg`) werden bei jedem Lesen berechnet. Gemessener RMR ersetzt den Mifflin-St-Jeor-BMR. |
| Ziel-KFA | Schätzung 16 % (≈ 68 kg bei 57 kg FFM), per `PUT /api/baseline/target_bodyfat_pct` überschreibbar |
| Energy Availability | (Ist-Zufuhr heute − Trainingskcal) ÷ FFM, nur für heute |
| Intake | Ernährungs-Tagebuch in der App; jede Änderung schreibt die Tagessumme nach `intake_days` |

## Stand

Vorhanden: Rad-Zonen, Ernährung, Phasenlogik, Messwert-Fallback, Intake-API, Ernährungs-Tagebuch (mobil), Dashboard. Fehlt: Kraft-Engine, Pass-Übersicht, Garmin-Import.
