# CLAUDE.md — Projekt-Brief

Diese Datei ist der Einstiegskontext für Claude Code in diesem Projekt. Lies sie zuerst,
bevor du Code schreibst.

## Was hier gebaut wird

Eine Web-Applikation für einen ambitionierten Wiedereinsteiger-Radfahrer (49, 74→68kg),
der über eine ~3-monatige Passsaison (Mai–Aug) 50–60 Schweizer Alpenpässe fahren will
(3.000–4.500 Hm pro Tag, Mehrfachpass-Tage). Die App leitet aus persönlichen
Start-/Verlaufsparametern automatisch drei aufeinander abgestimmte Pläne ab:

1. **Rad-Trainingsplan** (Zonen, Phasen, Intervalle)
2. **Kraft-/Mobility-Plan** (phasenabhängige Übungen, Sätze/Reps)
3. **Ernährungsplan** (kcal, Makros, Timing)

Dazu kommt eine vierte Komponente:

4. **Pass-Übersicht**: durchsuchbare Ansicht der 199-Pässe-Datenbank
   (`data/Schweizer_Alpenpaesse_Liste.xlsx`), inkl. Cluster-/Logistikplanung für die
   Top-50-Pässe (bereits als separates Excel vorhanden).

## Kern-Workflow (das eigentliche Ziel der App)

```
Effektive Start-Parameter eingeben
        ↓
Alle Pläne (Rad/Kraft/Ernährung) daraus berechnen
        ↓
Pläne werden synchron gehalten (gleiche Phasenblöcke, Konfliktregeln)
        ↓
Alle 2-4 Wochen: Check-in-Review (Trigger-Regeln prüfen, ggf. Pläne anpassen)
        ↓
Wöchentlich: Gewicht/Muskel/Fett% erfassen (Garmin-Waage)
```

Das ist die zentrale Interaktionsschleife der App — nicht nur "Pläne einmal anzeigen",
sondern ein **lebendes System**, das sich mit den Check-ins fortlaufend rekalibriert.

## Nicht verhandelbare Prinzipien

- **Nichts aus der Recherche weglassen.** `docs/research/*.md` sind die vollständigen,
  unveränderten Original-Recherchedokumente (inkl. wissenschaftlicher Quellen). Sie
  werden NIE durch komprimierte Configs ersetzt, nur ergänzt. Bei Unklarheiten in
  `data-model.yaml` gilt der Volltext in `docs/research/` als massgeblich.
- **Aktuellste Artefakt-Version zählt**, aber prüfe auch nachträgliche Korrekturen im
  Chat-Fliesstext nach dem letzten Artefakt (siehe Hinweis unten zu kcal-Korrektur).
- **API vor manuellem Import, wo möglich.** Aktuell (Stand 2026) hat Garmin keine
  Self-Serve-API für Privatpersonen; `backend/integrations/garmin_csv_import.py` ist
  der MVP-Weg, `garmin_api.py` bleibt Platzhalter für später (Aggregator/eigene
  Business-Zulassung).
- **Einzelperson, kein Multi-User-System.** Kein Auth/Login-System nötig für v1.

## Bekannte Datenkorrektur (wichtig!)

Im Ernährungs-Chat gab es zwei Artefakt-Versionen mit unterschiedlichen kcal-Zielen
(2.550 vs. 2.480 kcal/Tag). Die **2.480-Version ist final** — sie korrigiert eine
Diskrepanz zwischen Ziel-Gewichtsverlustrate (0,25 kg/Woche) und ursprünglichem
Defizit. Falls `docs/research/ernaehrungsplan.md` beide Zahlen enthält: 2.480 gilt.

## Architektur & Datenmodell

Siehe `docs/architecture.md` (Komponentenübersicht, Verzeichnisstruktur, Tech-Stack)
und `docs/data-model.yaml` (maschinenlesbare Formeln/Parameter, abgeleitet aus den
drei Recherche-Dokumenten).

## Person / Kontext für Berechnungen

- 49 Jahre, 173 cm, Start 74 kg → Ziel 68 kg
- Kein Fisch/Meeresfrüchte, Präferenz roh/kalt, minimaler Kochaufwand, Mittagessen
  kalt oder mikrowellengeeignet, kein Intervallfasten
- Verfügbare Zeit: 6–8 h/Woche Rad, ~2 h/Woche Kraft
- Winter: nur Indoor (Zwift)
- FTP wird erst Anfang Oktober per Zwift-Ramp-Test bestimmt — bis dahin sind
  Zonen-Berechnungen nicht möglich, UI muss das sauber abfangen

## Kommunikationsstil (für generierte Texte/UI-Copy)

Deutsch, kurz und direkt, tabellarisch/strukturiert statt Fliesstext.
