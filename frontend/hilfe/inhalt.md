# Wie rechnet die App?

Alle Werte, Abkürzungen und Formeln – kurz erklärt. Beispiele rechnen mit 49 Jahren, 173 cm, 74 kg,
20 % Körperfett.

**Inhalt:** [1 · So funktioniert die App](#ablauf) · [2 · Begriffe A–Z](#begriffe) · [3 · Rad](#rad) ·
[4 · Kraft](#kraft) · [5 · Ernährung](#ernaehrung) · [6 · Check-in-Regeln](#regeln) · [7 · Quellen](#quellen)

<a id="ablauf"></a>

## 1 · So funktioniert die App

| Schritt | Was passiert |
|---|---|
| 1. Startwerte | Alter, Grösse, Programmstart, Gewicht/Körperfett von der Waage, später FTP. |
| 2. Pläne | Daraus entstehen drei abgestimmte Pläne: **Rad**, **Kraft**, **Ernährung** – alle in derselben Phase. |
| 3. Wöchentlich | Waage (Gewicht, Körperfett, Muskeln) + kurzer Fragebogen (Schlaf, Beine, Hunger, Rücken, Anstrengung). |
| 4. Review | Die App prüft feste Regeln und **schlägt** Anpassungen vor. Du bestätigst – nichts passiert automatisch. |
| 5. Alle 6–8 Wochen | Neuer FTP-Test → Zonen und Watt-Vorgaben werden neu berechnet. |

Trainings aus Garmin (über intervals.icu) zählen als Ist-Werte: sie ersetzen die Schätzung für den Tag.

<a id="begriffe"></a>

## 2 · Begriffe A–Z

<a id="alltag"></a>

### Alltagsfaktor (Alltag/Beruf)
- **Was:** wie viel du dich im Alltag bewegst – ohne Sport. Einstellbar im Profil.
- **Wozu:** Grundumsatz × Alltagsfaktor = Tagesbedarf ohne Training. Das Training rechnet die App separat dazu,
  darum hier **nicht** mitzählen.

| Stufe | Beispiel | Faktor |
|---|---|---|
| nur sitzend | kaum Bewegung, wenig gehen | 1,2 |
| Büro | sitzend, etwas gehen | 1,45 |
| gemischt sitzend/stehend | Lehrer, Verkauf mit Sitzanteil | 1,65 |
| überwiegend stehend/gehend | Handwerk, Pflege, Gastro | 1,85 |
| körperlich schwer | Bau, Landwirtschaft | 2,1 |

- **Beispiel:** Büro: 1.581 × 1,45 = **2.293 kcal**; körperlich schwer: 1.581 × 2,1 = **3.320 kcal**.

<a id="deload"></a>

### Deload / Erholungswoche
- **Was:** eine Woche mit deutlich weniger Training.
- **Wozu:** der Körper wird in der Erholung stärker, nicht im Training.
- **Wann:** planmässig in jeder Phase oder sofort, wenn die Erholung kippt (siehe [Regeln](#regeln)).

<a id="defizit"></a>

### Defizit
- **Was:** so viele kcal isst du pro Tag weniger, als du verbrauchst.
- **Wozu:** Fettabbau. 350 kcal/Tag ergeben grob 0,3 kg Fett pro Woche.
- **Berechnung:** 350 kcal/Tag in den Phasen Base und Build 1, sonst 0. Das Review kann es in 100-kcal-Schritten
  verkleinern.

<a id="diaetpause"></a>

### Diät-Pause
- **Was:** 7 Tage essen auf Erhaltung (Defizit 0).
- **Wozu:** nach 6–10 Wochen Defizit sinkt Stoffwechsel und Motivation – die Pause setzt das zurück.

<a id="ea"></a>

### Energy Availability (EA, Energieverfügbarkeit)
- **Was:** wie viel Energie nach dem Training für den Rest des Körpers übrig bleibt.
- **Wozu:** Frühwarnung. Unter 30 kcal pro kg FFM drohen Leistungsabfall, Muskelabbau, Hormonstörungen (RED-S).
- **Berechnung:** (gegessene kcal − Trainings-kcal) ÷ FFM.
- **Beispiel:** (3.100 − 1.184) ÷ 59,2 kg = **32,4 kcal/kg FFM** → ok.

<a id="ffm"></a>

### FFM (fettfreie Masse)
- **Was:** alles am Körper ausser Fett: Muskeln, Knochen, Organe, Wasser.
- **Wozu:** Basis für Protein und Zielgewicht – sie soll beim Abnehmen gleich bleiben.
- **Berechnung:** Gewicht × (1 − Körperfett % ÷ 100).
- **Beispiel:** 74 kg × 0,80 = **59,2 kg**.

<a id="ftp"></a>

### FTP (Functional Threshold Power)
- **Was:** die Leistung in Watt, die du etwa eine Stunde lang halten kannst.
- **Wozu:** Grundlage für alle Trainingszonen und Watt-Vorgaben.
- **Berechnung:** 75 % deiner besten 1-Minuten-Leistung im Ramp-Test. Optional manuelle Korrektur in %
  (Ramp-Test überschätzt Fahrer mit starkem Sprint oft um 3–5 %).
- **Beispiel:** beste Minute 300 W → FTP **225 W**.

<a id="grundumsatz"></a>

### Grundumsatz (BMR) / Ruheumsatz (RMR)
- **Was:** kcal, die der Körper in völliger Ruhe pro Tag braucht.
- **Wozu:** Ausgangspunkt für das Kalorienziel.
- **Berechnung:** geschätzt mit Mifflin-St Jeor: 10 × kg + 6,25 × cm − 5 × Alter + 5.
  Sobald ein **gemessener** RMR (Diagnostik) eingetragen ist, ersetzt er die Schätzung.
- **Beispiel:** 740 + 1.081 − 245 + 5 = **1.581 kcal**.

<a id="hm"></a>

### Hm (Höhenmeter)
- **Was:** Summe aller Anstiege einer Fahrt. Ziel der Passsaison: 3.000–4.500 Hm pro Tag.

<a id="kfa"></a>

### Körperfett % (KFA)
- **Was:** Anteil Fett am Körpergewicht, gemessen von der Garmin-Waage.
- **Wozu:** zeigt, ob du Fett oder Muskeln verlierst. Die Waage misst ungenau, aber der **Trend** ist brauchbar.

<a id="makros"></a>

### Makros (Makronährstoffe)
- **Was:** Protein, Kohlenhydrate (KH), Fett – in Gramm pro Tag.
- **Berechnung:** siehe [Ernährung](#ernaehrung).

<a id="phase"></a>

### Phase
- **Was:** Trainingsabschnitt mit eigenem Ziel (z. B. Base = Grundlage). Rad, Kraft und Ernährung wechseln
  gemeinsam die Phase.
- **Ablauf:** siehe [Rad](#rad).

<a id="skala"></a>

### Problem-Skala 0–3 (Fragebogen)
- **Was:** 0 kein · 1 leicht · 2 deutlich · 3 stark.
- **Wozu:** ab **2 (deutlich)** prüft die App eine Regel (z. B. Rücken → Core täglich).

<a id="reds"></a>

### RED-S
- **Was:** relativer Energiemangel im Sport – zu wenig essen für das Trainingspensum.
- **Folgen:** Leistung sinkt, Infekte, Muskelabbau. Darum die EA-Kontrolle.

<a id="ramp"></a>

### Ramp-Test
- **Was:** Zwift-Test: Start 100 W, jede Minute +20 W, bis nichts mehr geht. Dauer ca. 15–20 min.
- **Wozu:** liefert die beste 1-Minuten-Leistung → FTP.

<a id="ruhehf"></a>

### Ruhe-HF / HRV
- **Was:** Ruhepuls am Morgen / Herzfrequenz-Variabilität (aus Garmin).
- **Wozu:** Ruhepuls **+5 Schläge** oder HRV **−10 %** über mehrere Tage = Erholung kippt.

<a id="sweetspot"></a>

### Sweet Spot
- **Was:** 88–94 % der FTP – knapp unter der Schwelle.
- **Wozu:** viel Trainingswirkung bei noch vertretbarer Ermüdung.

<a id="tagestyp"></a>

### Tagestyp
- **Was:** Einordnung des Tages für die Kohlenhydrate.

| Tagestyp | Wann | KH pro kg |
|---|---|---|
| Ruhetag | kein Training | 3 g |
| moderater Tag | Kraft oder kurze/lockere Ausfahrt | 5 g |
| langer/harter Tag | ab 2 h Rad oder Intervalle/Tempo | 7 g |

<a id="taper"></a>

### Taper
- **Was:** die letzten Wochen vor der Passsaison: Umfang −40 bis −60 %, Intensität bleibt.
- **Wozu:** frisch und in Topform in die Saison starten.

<a id="zielgewicht"></a>

### Zielgewicht
- **Was:** Gewicht, bei dem du bei gleicher FFM 16 % Körperfett hättest (Ziel-KFA anpassbar).
- **Berechnung:** FFM ÷ (1 − 0,16).
- **Beispiel:** 57 kg ÷ 0,84 = **67,9 kg**.

<a id="zonen"></a>

### Zonen (Z1–Z7)
- **Was:** Intensitätsbereiche in % der FTP (Modell nach Coggan).
- **Tabelle:** siehe [Rad](#rad).

<a id="rad"></a>

## 3 · Rad

<a id="zonentabelle"></a>

### Trainingszonen

Berechnung: Zone = Prozent × FTP. Beispiel mit FTP 225 W.

| Zone | % FTP | Watt | Gefühl |
|---|---|---|---|
| Z1 aktive Erholung | bis 55 % | bis 123 | ganz locker |
| Z2 Grundlage | 55–75 % | 124–168 | Unterhaltung problemlos |
| Z3 Tempo | 76–87 % | 171–195 | zügig, Sätze statt Gespräch |
| Sweet Spot | 88–94 % | 198–211 | hart, aber lange haltbar |
| Z4 Schwelle | 95–105 % | 214–236 | ca. 20–60 min maximal |
| Z5 VO2max | 106–120 % | 239–270 | 3–8 min maximal |
| Z6/Z7 anaerob | über 120 % | über 270 | Sekunden bis 1–2 min |

Ohne FTP zeigt die App die Vorgaben nur in % – Watt kommen nach dem ersten Ramp-Test.

<a id="phasen"></a>

### Phasen

Die Phasen laufen ab dem Programmstart nacheinander ab.

| Phase | Dauer | Schwerpunkt Rad | Kraftphase | Defizit |
|---|---|---|---|---|
| Wiedereinstieg | 2 Wochen | locker, v. a. Z2 | 1 | nein |
| Base | 8 Wochen | Grundlage, Sweet Spot, Kraftausdauer am Berg | 1 | ja |
| Build 1 | 8 Wochen | Schwelle, Over-Unders | 2 | ja |
| Build 2 | 5 Wochen | VO2max, Back-to-Back-Tage | 3 | nein |
| Peak/Taper | 5 Wochen | passspezifisch, dann Umfang runter | 3 | nein |
| Passsaison | offen | Erhalt: 1 Intervall-Einheit/Woche | 3 | nein |

**FTP-Tests** sind fest eingeplant (jeweils Samstag): Wiedereinstieg Woche 1, Base Woche 8, Build 1 Woche 6,
Build 2 Woche 5.

<a id="zwift"></a>

### Zwift-Workouts
Die Radeinheiten der nächsten 7 Tage landen automatisch als Workout in Zwift.

| Schritt | Was passiert |
|---|---|
| App → intervals.icu | sofort nach jeder Kalender-Änderung (Tauschen, Anpassen, Absagen) und beim Öffnen der App (max. alle 30 min) |
| intervals.icu → Zwift | macht intervals.icu selbst; in Zwift unter *Workouts → Custom → Intervals.icu* bzw. auf dem Home-Screen |

- **Einmalig nötig:** intervals.icu → Settings → Zwift → *Connect*.
- **FTP:** Vorgaben sind % FTP – Zwift rechnet mit seiner eigenen FTP. FTP in Zwift und intervals.icu gleich halten.
- **%-Bereiche** (z. B. Sweet Spot 88–94 %) werden als Mittelwert vorgegeben (ERG-Modus).
- Abgesagte Tage werden in intervals.icu wieder entfernt; erledigte Tage bleiben unverändert.
- **Fallback:** In der Tagesansicht „⬇ Zwift-Workout (.zwo)“ herunterladen und nach
  `Dokumente\Zwift\Workouts\<Zwift-ID>\` kopieren (nur PC/Mac).

### Trainings-kcal
- **Mit Leistungsmesser (Garmin-Import):** 1 kJ Arbeit ≈ 1 kcal Verbrauch.
- **Ohne Leistung / Planung:** Tabellenwert pro Stunde je nach Intensität, auf dein Gewicht umgerechnet.

| Intensität | kcal/h bei 74 kg |
|---|---|
| leicht / Rekom | 503 |
| moderat / Grundlage | 592 |
| zügig / Tempo | 740 |
| Intervalle | 888 |
| sehr hart | 1.169 |

Garmins eigener Kalorienwert wird nicht verwendet (ohne Leistung oft zu tief).

<a id="kraft"></a>

## 4 · Kraft

<a id="kraftphasen"></a>

### Kraftphasen

| Kraftphase | Sätze | Wiederholungen | Pause | Tempo |
|---|---|---|---|---|
| 1 Anatomische Anpassung | 2–3 | 15–25 | 60–90 s | langsam & kontrolliert |
| 2 Kraft-/Muskelaufbau | 3 | 8–12 | 60–90 s | 2–3 s absenken |
| 3 Kraftausdauer & Erhalt | wie Übung | 10–15 | 45–60 s | kontrolliert, einzelne schwer-langsame Sätze |

Die Kraftphase folgt der Rad-Phase (Tabelle [Phasen](#phasen)). Neue Übungen kommen ab Phase 2 bzw. 3 dazu.

### Einheiten
- **Einheit A** (Mo): Push, Core, Gesäss. **Einheit B** (Do): Pull, Core, Beinstabilität. Je 50–55 min.
- Ab Build 2: nur noch 1 Einheit pro Woche (Mo, abwechselnd A/B).
- Kraft und harte Rad-Einheit am selben Tag: zuerst Rad, Kraft mit mindestens 6 h Abstand.
- **Abschluss:** jede Einheit endet mit der Mobility-Routine (5–10 min).
- **Beine platt** (Regel): Beinübungen fallen weg, je Übung 1 Satz weniger (≈ −20 %).
- **Rücken** (Regel): McGill Big 3 (Curl-Up, Side Plank, Bird Dog) täglich mit der Mobility.

<a id="kraft-fokus"></a>

### Kraft-Fokus
Im Profil wählbar. Der Fokus kommt **obendrauf** (ca. +10 min pro Einheit), der Rest bleibt wie geplant.

| Fokus | Krafteinheiten | Mobility |
|---|---|---|
| Kein Fokus | wie geplant | wie geplant |
| Bauch/Core | +1 Satz auf Core-Übungen · A: Plank · B: Plank (Phase 1) bzw. Reverse Crunch/Leg Raises (ab Phase 2) | + McGill Big 3 täglich |
| Oberkörper | +1 Satz auf Zug/Druck/Schulter · A: Scapular Push-ups · B: Band Pull-Aparts (Phase 1) | – |
| Beine/Gesäss | +1 Satz auf Bein-/Gesäss-Übungen · A: Clamshells · B: Step-ups · immer 2–3 Wdh. in Reserve | – |
| Mobility | – | +1 Satz je Drill, Pigeon fest |

- **Beine schonen:** Der Bein-Fokus pausiert in Peak/Taper, in der Passsaison und solange „Beine platt“ aktiv ist –
  dann zählt das Radtraining.
<a id="kraft-benchmark"></a>

### Kraft-Benchmark
Kurzer Test (ca. 10 min) im Dashboard erfassen – Standard alle 4 Wochen, im Profil auf 2–8 Wochen einstellbar.
Ist er fällig, erinnert das Check-in-Review. Teiltests sind erlaubt; es zählt der neueste Wert je Test.

| Test | So testen | Was die App daraus macht |
|---|---|---|
| Liegestütze am Stück | saubere Wdh. in deiner Variante | ab 15 Wdh. → nächste Variante (Wand → Inkline → Knie → Standard → Füsse erhöht → Deficit) |
| Inverted Rows am Stück | saubere Wdh. | ab 15 → Füsse erhöht |
| Side Plank | Sekunden, schwächere Seite, Knie/gestreckt | Knie ab 20 s → gestreckt |
| Single-Leg Glute Bridge | Halten in s, schwächere Seite | ab 60 s → einbeinig, sonst beidbeinig |
| Plank | Halten in s | Plank ≥ 2 min **und** Side Plank gestreckt ≥ 30 s → Hollow Body/Pallof schon vor ihrer Phase |

In der Krafteinheit steht dann „Deine Stufe: …“ statt der ganzen Progressionsliste.
Die Schwelle 15 Wdh. ist eine Annahme (oberes Ende des Rep-Bereichs); Reihenfolgen und Zielwerte stammen aus der Kraft-Recherche.

**Meilensteine** (Kraft-Recherche): W8 Standard-Liegestütz sauber · W12 Single-Leg Glute Bridge 60 s, Side Plank
gestreckt 30 s · W16 Bulgarian Split Squat 3× 10 · W20 Plank 2 min · W24 Re-Test aller Werte.

- **Flacher Bauch:** Gezielter Fettabbau am Bauch (Spot Reduction) funktioniert nicht. Der Bauch wird flacher über
  das Kaloriendefizit (Fettabbau) plus Core-Training (Spannung, Haltung). Der Core-Fokus verstärkt den zweiten Teil.

<a id="ernaehrung"></a>

## 5 · Ernährung

<a id="kcalziel"></a>

### Kalorienziel pro Tag

Die App rechnet jeden Tag neu – aus dem, was an diesem Tag trainiert wird.

| Baustein | Berechnung | Beispiel (2 h Grundlage) |
|---|---|---|
| Grundumsatz | Mifflin-St Jeor (oder gemessener RMR) | 1.581 |
| Alltag | Grundumsatz × [Alltagsfaktor](#alltag) (Büro 1,45) | 2.293 |
| + Rad | Trainings-kcal (siehe [Rad](#rad)) | + 1.184 |
| + Kraft | 300 kcal pro Einheit | + 0 |
| − Defizit | 350 kcal in Base/Build 1 | − 350 |
| **= Ziel** | | **3.127 kcal** |

Ruhetag im Beispiel: 2.293 − 350 = **1.943 kcal**.

<a id="makroziele"></a>

### Makros

| Nährstoff | Berechnung | Beispiel |
|---|---|---|
| Protein | 2,6 g pro kg FFM | 59,2 × 2,6 = **154 g** |
| Fett | 0,95 g pro kg Gewicht | 74 × 0,95 = **70 g** |
| Kohlenhydrate | 3 / 5 / 7 g pro kg je [Tagestyp](#tagestyp) | moderater Tag: 74 × 5 = **370 g** |

Protein richtet sich nach der FFM, damit es beim Abnehmen nicht mitsinkt.

### Mahlzeiten

| Mahlzeit | kcal | Hinweis |
|---|---|---|
| Frühstück | 25 % vom Rest | Grundversorgung |
| Snack 1 | 200 | vor dem Training: schnelle KH, wenig Fett |
| Mittagessen | 30 % vom Rest | kalt oder Mikrowelle |
| Snack 2 | 250 | direkt nach dem Training: KH + 20–25 g Protein |
| Abendessen | 30 % vom Rest | Erholung |

„Rest“ = Tagesziel minus beide Snacks. Protein wird ähnlich auf die Hauptmahlzeiten verteilt.

<a id="fueling"></a>

### Verpflegung unterwegs

| Fahrt | KH pro Stunde |
|---|---|
| unter 75 min | keine, Wasser reicht |
| 75–150 min | 30–60 g |
| über 150 min oder Intervalle/Tempo | 60–90 g, Mischung 2:1 Glukose:Fruktose |

Nach der Ausfahrt: 1,0–1,2 g KH pro kg in den ersten Stunden.

<a id="regeln"></a>

## 6 · Check-in-Regeln

Die App **schlägt vor** – angewendet wird erst, wenn du bestätigst. „Defizit −100 kcal“ wird nur
vorgeschlagen, solange ein Defizit läuft.

| Auslöser | Vorschlag |
|---|---|
| Gewicht fällt schneller als 0,7 % pro Woche (2-Wochen-Trend) | Defizit −100 kcal |
| Gewicht stagniert 2–4 Wochen trotz Defizit | Defizit −100 kcal |
| Zielgewicht erreicht | Erhaltung (Defizit 0) |
| 6–10 Wochen Defizit ohne Pause | Diät-Pause 7 Tage |
| EA im Schnitt unter 30 kcal/kg FFM (7 Tage) | Defizit −100 kcal |
| FTP sinkt über zwei Tests | Defizit 7 Tage pausieren, Fettabbau neu bewerten |
| FTP stagniert über zwei Tests | Erholungswoche |
| Schlaf oder Anstrengung ≥ 2, Ruhepuls +5 oder HRV −10 % | Erholungswoche sofort |
| Beine platt ≥ 2 in zwei Fragebögen nacheinander | Kraft reduzieren (4 Wochen) |
| Rücken ≥ 2 | Core täglich (4 Wochen) |
| Dauerhunger ≥ 2 | Defizit −100 kcal |

Zusätzlich erinnert die App an fällige Check-ins (Waage + Fragebogen, wöchentlich) und an geplante FTP-Tests.

<a id="quellen"></a>

## 7 · Quellen

| Thema | Grundlage |
|---|---|
| Zonen, FTP | Coggan-Leistungszonen; Zwift Ramp-Test |
| Grundumsatz | Mifflin-St Jeor (1990) |
| Rad-kcal | Ainsworth Compendium of Physical Activities (MET) |
| Gewichtsverlust | Garthe et al. (2011): max. 0,7 %/Woche bei Athleten |
| Energy Availability | RED-S-Konsens (IOC) |
| Rumpf | McGill Big 3 |

Die vollständigen Recherchen mit allen Quellen liegen im Projekt unter `docs/research/`.
