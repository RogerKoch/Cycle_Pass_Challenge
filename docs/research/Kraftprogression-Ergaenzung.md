# Ergänzung: Progression im Kraftplan (Körpergewicht, Wiedereinsteiger 49 J.)

> Ergänzt `Trainingsplan Kraft.md`, ersetzt es nicht. Stand 2026-10-14. Kurz-Recherche, Evidenzniveau je Punkt angegeben.
> Auslöser: Rückmeldung «Kraftziele wirken zu einfach».

## Ausgangslage im Plan
- Recherche-Original (Zeile «Progression»): zuerst Technik und Wiederholungen steigern, dann Tempo verlangsamen,
  dann Hebel verlängern/instabiler machen, zuletzt Widerstandsbänder als externe Last.
- App vor dieser Ergänzung: nur *Wdh.-Schwelle (15) → Hebel*, höchstens eine Stufe je Test; Reps der Stufen-Übungen
  wurden durch die Phasen-Reps (Phase 1: 15–25) überschrieben, obwohl die Bibliothek 8–15 nennt.

## Funde

| # | Aussage | Quelle / Niveau | Umsetzung in der App |
|---|---|---|---|
| 1 | Lastprogression: Wenn 1–2 Wdh. über dem Ziel gelingen, Last um 2–10 % erhöhen. Progression auch über Wdh., Tempo, Hebel. | [ACSM Position Stand 2009](https://www.sportgeneeskunde.com/wp-content/uploads/ACSM-Position-Stand-Progression-Models-in-Resistance-Training-for-Healthy-Adults.pdf) – Konsenspapier, methodisch kritisiert | «Ziel nächster Test» = Testwert + 10 % (mind. +1) |
| 2 | Praxisregel: nächste Variante bei 3 × 12 sauberen Wdh.; Plateau bei 20–25 Wdh. pro Satz, dann härtere Variante statt mehr Wdh. | Coaching-Quelle ([Push-up-Progression](https://getfitcraft.com/guides/push-up-progression)), keine Studie | Level-up-Schwelle 12 statt 15; ab 20 Wdh. zwei Stufen |
| 3 | Sätze meist mit 1–3 Wdh. in Reserve (RIR) | Coaching-Quelle ([Barbell Medicine](https://www.barbellmedicine.com/blog/push-ups-chest-hypertrophy/)); deckt sich mit Kraft-Recherche («2–3 RIR») | Hinweis «2–3 Wdh. in Reserve» an Stufen-Übungen |
| 4 | Bei hohen Wdh. ist die Nähe zum Versagen schwer einzuschätzen, der Reiz je Satz sinkt | wie 3 | Reps der Stufen-Übungen aus Bibliothek (8–15), nicht Phasen-Reps (15–25) |
| 5 | Masters-Radfahrer: Einbeinarbeit priorisieren, Erholung braucht länger, Entlastungswoche alle 3–4 Wochen | Coaching-Blogs ([Roadman](https://roadmancycling.com/answers/strength-training-for-masters-cyclists)), kaum Studien | **Nicht** umgesetzt (Option für später) |
| 6 | Single-Leg-Bridge-Ausdauer: junge Gesunde ca. 60–80 s je Bein (SD 25–34 s), abhängig von Abbruchkriterium | [IJSPT 2026](https://ijspt.scholasticahq.com/article/154592-establishing-normative-values-and-clinician-assessment-accuracy-for-the-single-leg-bridge-endurance-test) | Ziel 60 s bleibt als Meilenstein plausibel |

## Entscheidungen (Roger, 2026-10-14)
- Level-up bei 12 sauberen Wdh., ab 20 Wdh. zwei Stufen; am Ende der Leiter Tempo 3 s exzentrisch statt Zusatzlast.
- Keine Zusatzlast (Rucksack/Band) und keine Entlastungswoche in dieser Runde.
- Schwelle und Faktoren sind Konstanten in `backend/engine/strength_benchmarks.py` und per Test änderbar.

## Grenzen
- Fast alle Zahlen stammen aus Coaching-Quellen bzw. einem Konsenspapier, nicht aus kontrollierten Studien an
  Wiedereinsteigern über 45. Sie sind Startwerte; die Stufenanpassung läuft über die Benchmarks alle 4 Wochen.
- Körpergewichtstraining hat eine Obergrenze für Kraft/Hypertrophie (siehe Original-Recherche); Bänder/Last sind der
  nächste Hebel, falls die Leiter ausgereizt ist.
