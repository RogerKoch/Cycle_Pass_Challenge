# Architektur: Alpenpässe-Applikation

## Ziel

Eine Web-Applikation, die aus Start-Parametern (Alter, Gewicht, FTP, Körperfett % etc.)
automatisch Trainings-, Kraft- und Ernährungspläne ableitet, per Check-ins fortlaufend
aktualisiert, und eine Pass-Übersicht (199 Schweizer Alpenpässe) als weitere Komponente
integriert.

## Komponentenübersicht

| Komponente | Zweck | Status |
|---|---|---|
| **Trainings-Engine** | Rad-Zonen (Coggan) aus FTP, phasenabhängige Intervall-Vorgaben | gebaut (`cycling_sessions.py`) |
| **Kraft-Engine** | Phasenabhängige Sätze/Reps/Übungsauswahl | gebaut (`strength_sessions.py`) |
| **Ernährungs-Engine** | kcal/Makros aus Gewicht, Körperfett %, Trainingslast | gebaut |
| **Trainingskalender** | Standardwoche je Phase, Tauschen/Anpassen/Absagen, Kopplungsregeln | gebaut (`week_plan.py`, `/training/`) |
| **Check-in-Modul** | Wöchentliche/periodische Erfassung, Trigger-Regeln für Re-Kalibrierung | Erfassung gebaut, Trigger zu bauen |
| **Pass-Datenbank** | 199 Pässe, Cluster, Logistik-Planung | Excel vorhanden |
| **Frontend/Dashboard** | Anzeige aller abgeleiteten Pläne + Pass-Übersicht | Dashboard, `/training/`, `/ernaehrung/` gebaut; Pass-Übersicht zu bauen |

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
├── serve.py                        ← Produktions-Einstieg (waitress, ProxyFix)
├── instance/config.py              ← Secrets, nicht versioniert
├── backend/
│   ├── models/                      # SQLAlchemy/DB-Modelle
│   │   ├── user_profile.py
│   │   ├── checkins.py
│   │   ├── ftp_tests.py
│   │   └── training_days.py         # Trainingskalender, 1 Zeile pro Tag
│   ├── engine/                      # reine Berechnungslogik, ungekoppelt von Flask
│   │   ├── cycling_zones.py         # Coggan-Zonen aus FTP
│   │   ├── nutrition_calc.py        # BMR, kcal-Ziel, Makros
│   │   ├── training_phase.py        # Phase aus Programmstart + Datum
│   │   ├── cycling_sessions.py      # Rad-Einheiten je Phase/Slot/Woche, Watt aus FTP
│   │   ├── strength_sessions.py     # Übungsbibliothek, Einheiten A/B je Kraftphase, Mobility
│   │   └── week_plan.py             # Standardwoche, Kopplungsregeln, Ersatztage
│   ├── integrations/
│   │   ├── blv_import.py            # BLV-Nährwertdatenbank → foods (CLI import-blv)
│   │   ├── open_food_facts.py       # Barcode-Lookup
│   │   ├── garmin_csv_import.py     # MVP: manueller CSV-Import
│   │   └── garmin_api.py            # Platzhalter für spätere API/Aggregator-Anbindung
│   └── api/                         # Flask-Endpunkte (REST)
│       ├── profile_routes.py
│       ├── checkin_routes.py
│       ├── calendar_routes.py       # Woche/Tag, Tauschen, Anpassen, Rückmeldung
│       └── plan_routes.py
│
├── frontend/
│   ├── dashboard/                   # Profil, Check-in, FTP, Messwerte
│   ├── training/                    # mobil: Tagesplan (Rad/Kraft/Mobility/Ernährung) + Woche
│   ├── ernaehrung/                  # mobil: Ernährungs-Tagebuch
│   └── passuebersicht/              # Pass-Datenbank durchsuchbar/filterbar
│
├── data/
│   └── Schweizer_Alpenpaesse_Liste.xlsx   # bereits vorhanden, 199 Pässe
│
└── alpenpaesse.db                   # SQLite, wird bei erstem Start erzeugt
```

## Kopplungsregeln zwischen den Engines

1. **Phasen-Synchronisation:** Die Kraftphase folgt der Rad-Phase des Tages
   (Phase 0/Base ↔ Phase 1, Build1 ↔ Phase 2, Build2/Peak/Passsaison ↔ Phase 3,
   `strength_sessions.strength_phase_for`). Ab Build 2 nur 1 Krafteinheit (Mo, A/B im Wochenwechsel).
2. **Wochenregeln** (`week_plan.validate_week`, geprüft bei Tausch und Anpassung):
   blockierend sind zwei Schlüsseleinheiten an aufeinanderfolgenden Tagen (≥48 h) und eine Woche
   ohne kompletten Ruhetag (abgesagter Tag zählt als Ruhetag). Kraft am Tag einer Schlüsseleinheit
   ist nur ein Hinweis (≥6 h Abstand, Rad zuerst).
3. **Kalorisches Defizit:** nur aktiv in Base/Build1 (`nutrition_calc.py` schaltet es ab Build2 auf 0).
4. **Tagestyp steuert Makros:** Ruhetag / moderat (Kraft o. ~1 h Rad) / lang-hart (≥2 h o. Intervalle),
   abgeleitet aus der geplanten bzw. zurückgemeldeten Einheit (`derive_day_type`), bestimmt KH-Menge
   und Intra-Workout-Fueling.

## Trainingskalender

| Baustein | Umsetzung |
|---|---|
| Speicherung | `training_days`: Slot (`rekom`, `schluessel_1`, `z2_grundlage`, `z2_oder_rekom`, `schluessel_2`, `lang` oder leer), Krafteinheit A/B, Dauer-Override, Status, Ist-Werte, Notiz. Intervalle, Watt und Übungen werden beim Lesen aus Phase und Woche aufgelöst |
| Erzeugung | Lazy beim ersten Abruf einer Woche aus der Standardwoche (Mo Kraft A + Rekom · Di Schlüssel 1 · Mi Z2 · Do Kraft B + Rekom · Fr Ruhe · Sa Schlüssel 2 · So lang). Vor dem Programmstart leer |
| Progression | je Phase/Woche nach *Trainingsplan Ausdauer* §3; Build 1 jede 3. Woche Erholungswoche (−40 % Volumen); Peak: 3 Spezifik- + 2 Taper-Wochen |
| Tauschen | ganze Tage (Rad + Kraft) innerhalb einer Woche, ab heute; der Status bleibt beim Datum. So wird eine abgesagte Schlüsseleinheit auf einen Ersatztag verschoben |
| Anpassen | geplanter Tag: andere Einheit der Phase, Dauer nur bei Ausdauerfahrten (Grundlagen-Abschnitte skalieren, Blöcke bleiben), Kraft an/aus/A↔B |
| Rückmeldung | `done` / `modified` (Ist-Minuten, Intensität, Kraft ja/nein) nur heute/vergangen; `skipped` auch im Voraus mit Grund |
| Ernährung | `/api/plan/today` ohne Parameter rechnet mit dem Kalendertag (Ist vor geplant, abgesagt = 0) und liefert Mahlzeitenverteilung (3 + 2 Snacks), Fueling und Timing-Hinweise |

## Messwert-Fallback-Pattern (estimated → measured)

Baseline-Werte (RMR, FFM, Körperfett, VT1/VT2, FatMax, MFO, Ernährungsziele) werden mit
`source: estimated | measured` und `updated_at` gespeichert. Bis zum Diagnostik-Termin
gelten Schätzwerte (Mifflin-St Jeor, Garmin-KFA, Ernährungsplan, %HFmax), danach
überschreiben Messwerte sie. Gespeichert werden nur Messwerte; Schätzwerte und abgeleitete
Felder (`rmr_ratio`, `target_weight_kg`, `energy_availability`) werden bei jedem Lesen neu
berechnet. Details und Formeln: `docs/data-model.yaml` → `baseline_values`.

## Ernährungs-Intake (Ist-Werte)

Die Zufuhr wird **in der App selbst** erfasst: mobile Seite `/ernaehrung/` (PWA, nur Manifest,
kein Service Worker), keine externe Tracker-App.

| Baustein | Umsetzung |
|---|---|
| Lebensmittel | Schweizer Nährwertdatenbank (BLV, `data/Schweizer_Nahrwertdatenbank.xlsx`, ~1.250 Einträge), Import per `flask --app main.py import-blv <pfad>` (idempotent, eigene Portionen bleiben) |
| Suche | `LIKE` auf normalisierter Spalte `search_name` (Kleinschreibung, ohne Umlaut-Punkte/Akzente); Rang: ganzes Wort am Anfang → Präfix → Wortanfang → Teiltreffer, dann Nutzungshäufigkeit |
| Barcode (optional) | Scan im Browser (`@zxing/browser`, CDN) oder Ziffern eintippen → Backend fragt Open Food Facts ab und speichert den Treffer als `source = off`. Kamera nur über HTTPS/localhost |
| Einträge | `food_log_entries` mit Nährwert-**Snapshot**; Schnelleinträge ohne Lebensmittel; Mahlzeit-Vorlagen; eigene Portion je Lebensmittel |
| Tagessumme | Jede Änderung am Log berechnet `intake_days` des Datums neu (leerer Tag → Datensatz gelöscht). Log-Einträge überschreiben damit einen per `PUT /api/intake` gesetzten Wert. |

Mit den Ist-Werten berechnet `/api/plan/today` Soll/Ist und die Energy Availability für den
aktuellen Tag; die mobile Seite fragt die vier Tagesparameter dafür in einem Mini-Formular ab.

## Betrieb auf dem Server

Server 161.97.157.97 (Windows), mehrere Projekte unter einer IP. Setup und Runbook liegen im
separaten Repo `server-infra`.

| Baustein | Umsetzung |
|---|---|
| Reverse Proxy | Caddy (Windows-Dienst), Let's-Encrypt-IP-Zertifikat (Profil `shortlived`) |
| Adressierung | `https://161.97.157.97/cpc/`. Caddy entfernt den Pfad und sendet `X-Forwarded-Prefix`; `serve.py` setzt `ProxyFix(x_prefix=1)`. Das Frontend nutzt nur relative URLs. Später auf Subdomains umstellbar, ohne den Code zu ändern. |
| App-Server | `serve.py` → waitress auf `127.0.0.1:8101` (Port über `CPC_PORT`), WinSW-Dienst |
| Login | `backend/auth.py`: ein Passwort (`PASSWORD_HASH`), permanente Session (365 Tage), Cookie `cpc_session` (Secure, HttpOnly, SameSite=Lax). API ohne Session → 401, Seiten → `/login`. Manifest und Icon sind öffentlich. Ohne `PASSWORD_HASH` (lokale Entwicklung) ist kein Login nötig. |
| Secrets | `instance/config.py` (nicht versioniert): `SECRET_KEY`, `PASSWORD_HASH`; Hash per `flask --app main.py hash-password` |

## Offene Punkte (aus Recherche)

- Kraft-Platzierung: Die Kraft-Recherche empfiehlt Kraft am harten Radtag (danach bzw. ≥6 h später),
  die Ausdauer-Recherche und `data-model.yaml` Mo/Do an lockeren Tagen. Umgesetzt ist Mo/Do.
- Progressionsschritte innerhalb der Phasen (z. B. Sweet Spot 3×10 → 3×12 → 2×20) und die Zuordnung
  der Kraftübungen aus Phase 2/3 zu Einheit A/B sind Annahmen; die Recherche nennt nur Start/Ziel
- Rad-kcal weiter über MET-Stufen; mit FTP wären kJ aus den Watt-Vorgaben genauer

- Mehrere User mit eigenen Daten (heute Einzel-Login): bräuchte `user_id` in allen Tabellen
- Baseline-Fallback: %HFmax-Schätzformel für VT1/VT2 (Prozentwerte, HFmax-Quelle) zurückgestellt
- Energy-Availability-Historie braucht ein Trainings-Log (Garmin-Import)

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
- Betrieb: waitress hinter Caddy (siehe „Betrieb auf dem Server“)
- Datenimport: manueller CSV-Export aus Garmin Connect (MVP)
