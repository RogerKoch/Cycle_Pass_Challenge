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

```bash
C:\dev\virtualenvs\cycle_pass_challenge\Scripts\python -m pytest backend/tests
```

## Dashboard

| Abschnitt | Zweck |
|---|---|
| Profil | Alter, Grösse, Programmstart (steuert die Trainingsphase) |
| Check-in | Gewicht, Körperfett, Muskelmasse (FFM wird berechnet) |
| FTP-Test | Beste 1-Min-Leistung → FTP = 75 %, optionale manuelle Korrektur |
| Heute | Tagesparameter → Phase, Rad-Zonen, kcal-Ziel, Makros |

Ohne FTP-Test zeigt "Heute" statt der Zonen einen Hinweis.

## API

| Methode | Pfad | Zweck |
|---|---|---|
| GET / POST / PUT | `/api/profile` | Profil lesen / anlegen (409 falls vorhanden) / ändern |
| GET / POST | `/api/checkins` | Check-ins listen (neueste zuerst) / erfassen |
| GET | `/api/checkins/latest` | Neuester Check-in |
| POST | `/api/checkins/ftp-tests` | FTP-Test erfassen (`best_1min_power_watts`, optional `test_date`, `manual_correction_pct`) |
| GET | `/api/checkins/ftp-tests/latest` | Neuester FTP-Test |
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

## Stand

Vorhanden: Rad-Zonen, Ernährung, Phasenlogik, Dashboard. Fehlt: Kraft-Engine, Pass-Übersicht, Garmin-Import.
