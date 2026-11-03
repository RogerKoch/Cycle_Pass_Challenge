# Tagesablauf und Sport-Verpflegung

Allgemeine Regeln aus dem Massnahmenplan einer Ernährungsberatung, nach denen `backend/engine/day_timeline.py`
den Ernährungs-Tagesablauf berechnet. Personenbezogene Messwerte (Zellstruktur, Laktat, Schwellen, Kontaktdaten) stehen bewusst
nicht in diesem öffentlichen Repo; die persönlichen Basis-Tageswerte liegen im Profil (`user_profile.base_*`).
Ergänzt `ernaehrungsplan.md` (Formelmodus), ersetzt es nicht.

## Grundprinzipien
- Norm Carb: Kohlenhydrate in jeder Mahlzeit und rund um jedes Training, keine Mahlzeit auslassen, nicht reduzieren.
- Kaiser-König-Bettler: morgens am meisten, mittags viel, abends wenig. Das Abendessen ist von der Menge her optional.
- 3 Hauptmahlzeiten + 2 Zwischenmahlzeiten. Frühstück innerhalb 1 h nach dem Aufstehen. Abendessen idealerweise 4 h vor dem Schlafen.
- Kein Defizit, Ziel ist Struktur (Körperzusammensetzung statt Waage): regelmässig essen, genug Eiweiss, Krafttraining, Erholung.
- Korridor: Tagesziel ohne Sport ±~3 % ist grün; es muss nicht jeden Tag aufs Gramm stimmen.

## Mahlzeiten (Anteile am Basis-Tagesziel ohne Sport, Beispiel 2.050 kcal)
| Mahlzeit | kcal | Eiweiss / KH / Fett (% der kcal) |
|---|---|---|
| Frühstück (Kaiser) | 550 | 22 / 44 / 34 |
| Zwischenmahlzeit Vormittag | 275 | 9 / 50 / 41 |
| Mittagessen (König) | 555 | 27 / 43 / 30 |
| Zwischenmahlzeit Nachmittag | 250 | 12 / 43 / 45 |
| Abendessen (Bettler) | 420 | 29 / 28 / 43 |

Die Gramm-Summen der Makros entsprechen den Basiswerten im Profil; die Verteilung auf die Mahlzeiten folgt den Prozenten.

## Sport-Verpflegung (zusätzlich zu den Mahlzeiten)
- **Pre** (30–60 min vorher): ca. 120 kcal, ca. 25 g KH, auch wenn die letzte Mahlzeit 2–3 h zurückliegt.
- **Intra** (KH pro Stunde): locker bis 60 min nur Wasser; GA1 60–120 min 40–60 g; lang (>2 h) oder intensiv 60–90 g
  (Glukose + Fruktose). Hohe Mengen über Wochen antrainieren (Start 40–60 g/h), ab Minute 20–30 alle 15–20 min.
  Krafttraining 0–30 g.
- **Post** (innerhalb 30–60 min): Variante 1 ca. 220 kcal (30 g Proteinpulver + Beeren + Drink); Variante 3 ca. 370 kcal nach
  langen oder harten Einheiten (zusätzlich Banane und Mandelmus). Nach Krafttraining immer 25–30 g Eiweiss.
- Beispiel 45 min intensiv: zusätzlich ca. 600 kcal (95 g KH, 28 g Eiweiss, 10 g Fett).

## Umsetzung in der App
- Mo–Fr Training nach der Arbeit (18:00): Post-Workout und Abendessen fallen zusammen (spät unter der Woche; "4 h vor dem Schlafen" entfällt bewusst).
- Sa/So Training nach dem Frühstück (10:00): Vormittags-Snack entfällt; endet das Training ab 11:00, ersetzt die Post-Mahlzeit das Mittagessen.
- Toleranz in der Wochenanalyse: bis +10 % über dem Ziel bei kcal, KH und Fett; Eiweiss unter 90 % ist eine Abweichung, nach oben kein Limit (bis 2,0 g/kg).
