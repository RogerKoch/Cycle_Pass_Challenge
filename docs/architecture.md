# Architektur: Alpenpässe-Applikation

## Ziel

Eine Web-Applikation, die aus Start-Parametern (Alter, Gewicht, FTP, Körperfett % etc.)
automatisch Trainings-, Kraft- und Ernährungspläne ableitet, per Check-ins fortlaufend
aktualisiert, und eine Pass-Übersicht (199 Schweizer Alpenpässe) als weitere Komponente
integriert.

## Komponentenübersicht

| Komponente | Zweck | Status |
|---|---|---|
| **Trainings-Engine** | Rad-Zonen (Coggan) aus FTP, phasenabhängige Intervall-Vorgaben | Recherche fertig |
| **Kraft-Engine** | Phasenabhängige Sätze/Reps/Übungsauswahl | Recherche fertig |
| **Ernährungs-Engine** | kcal/Makros aus Gewicht, Körperfett %, Trainingslast | Recherche fertig |
| **Check-in-Modul** | Wöchentliche/periodische Erfassung, Trigger-Regeln für Re-Kalibrierung | zu bauen |
| **Pass-Datenbank** | 199 Pässe, Cluster, Logistik-Planung | Excel vorhanden |
| **Frontend/Dashboard** | Anzeige aller abgeleiteten Pläne + Pass-Übersicht | zu bauen |

Alle Komponenten teilen sich **eine SQLite-Datenbank**.

## Grundprinzip: Quelle der Wahrheit bleibt unangetastet

Die drei Recherche-Dokumente (Ernährung, Kraft, Ausdauer) werden **unverändert** unter
`docs/research/` abgelegt. Der Code leitet daraus strukturierte Configs ab
(`data-model.yaml` und weitere), ersetzt die Volltexte aber nicht. Bei Unklarheiten
oder Änderungswünschen wird immer auf die Original-Recherche zurückgegriffen, nie auf
eine bereits komprimierte Zwischenstufe.

## Verzeichnisstruktur

```
alpenpaesse-app/
├── docs/
│   ├── architecture.md              ← dieses Dokument
│   ├── data-model.yaml              ← siehe separate Datei
│   └── research/                    ← Original-Volltexte, 1:1 aus den 3 Chats
│       ├── ernaehrungsplan.md
│       ├── kraftplan.md
│       └── trainingsplan_ausdauer.md
│
├── backend/
│   ├── models/                      # SQLAlchemy/DB-Modelle
│   │   ├── user_profile.py
│   │   ├── checkins.py
│   │   ├── ftp_tests.py
│   │   └── training_calendar.py
│   ├── engine/                      # reine Berechnungslogik, ungekoppelt von Flask
│   │   ├── cycling_zones.py         # Coggan-Zonen aus FTP
│   │   ├── nutrition_calc.py        # BMR, kcal-Ziel, Makros
│   │   ├── strength_phases.py       # Phasenparameter Kraft
│   │   └── sync_rules.py            # Kopplungsregeln (Phasen-Sync, 6h-Abstand, Defizit-Fenster)
│   ├── integrations/
│   │   ├── garmin_csv_import.py     # MVP: manueller CSV-Import
│   │   └── garmin_api.py            # Platzhalter für spätere API/Aggregator-Anbindung
│   └── api/                         # Flask-Endpunkte (REST)
│       ├── profile_routes.py
│       ├── checkin_routes.py
│       └── plan_routes.py
│
├── frontend/
│   ├── dashboard/                   # Trainings-/Ernährungs-/Kraft-Ansicht
│   └── passuebersicht/              # Pass-Datenbank durchsuchbar/filterbar
│
├── data/
│   └── Schweizer_Alpenpaesse_Liste.xlsx   # bereits vorhanden, 199 Pässe
│
└── alpenpaesse.db                   # SQLite, wird bei erstem Start erzeugt
```

## Kopplungsregeln zwischen den Engines

1. **Phasen-Synchronisation:** `training_calendar.phase_rad` und `phase_kraft` laufen
   auf denselben 6–8-Wochen-Blöcken (Base ↔ Phase 1, Build1 ↔ Phase 2, Build2/Peak ↔ Phase 3).
2. **Zeitliche Trennung:** Kraft-Session nur zulässig, wenn ≥6h Abstand zu einem
   Rad-Intervalltag (`sync_rules.py` prüft das beim Anlegen des Trainingskalenders).
3. **Kalorisches Defizit:** nur aktiv in Base/Build1 (`nutrition_calc.py` liest
   `phase_rad` und schaltet Defizit ab Build2 auf 0).
4. **Tagestyp steuert Makros:** Ruhetag/moderat/hart bestimmt KH-Menge und
   Intra-Workout-Fueling gemäss `data-model.yaml`.

## Offene Punkte (aus Recherche)

- FTP-Baseline erst nach Zwift-Ramp-Test (Anfang Oktober) verfügbar → Zonen bis dahin
  nicht berechenbar, UI muss das abfangen (Platzhalter/Hinweis anzeigen)
- Col du Sanetsch und Männlichen: Zufahrt/Befahrbarkeit noch zu verifizieren, bevor
  sie in Routen-Planung der Pass-Komponente einfliessen
- Garmin-Datenweg: Start mit CSV-Import, `garmin_api.py` bleibt Platzhalter bis
  API-Zugang oder Aggregator geklärt ist

## Tech-Stack

- Backend: Python, Flask
- DB: SQLite
- Frontend: HTML (+ ggf. leichtes JS, kein schweres Framework nötig für v1)
- Datenimport: manueller CSV-Export aus Garmin Connect (MVP)
