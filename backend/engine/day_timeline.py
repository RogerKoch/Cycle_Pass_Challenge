"""Tagesablauf (Timeline) der Ernaehrung nach einem Massnahmenplan (Ernaehrungsberatung).

Fuenf Mahlzeiten mit festen kcal-Anteilen (Kaiser-Koenig-Bettler) plus Sport-Verpflegung (Pre, Intra, Post)
rund um die eine Tageseinheit. Quelle: docs/research/tagesablauf-sportverpflegung.md.

Die Basis-Tageswerte (ohne Sport) stehen im Profil; Tagesziel = Basis + Summe der Sport-Slots, ohne Defizit.
"""

from dataclasses import dataclass, field, replace

from backend.engine.nutrition_calc import HARD_INTENSITIES, CyclingIntensity, Fueling

REFERENCE_KCAL = 2050.0  # Summe der Mahlzeiten-kcal im Massnahmenplan; Skalierungsbasis
STRENGTH_MINUTES = 50  # Krafteinheit im selben Block wie das Rad (Rad, dann Kraft)
EVENING_START = 18 * 60  # Training nach der Arbeit
MORNING_START = 10 * 60  # Training nach dem Fruehstueck (Wochenende)
PRE_LEAD_MINUTES = 45  # Pre-Snack 30-60 min vor dem Start
POST_DINNER_DELAY = 15  # Abendessen nach dem Training (Post-Workout-Mahlzeit)
LUNCH_MERGE_FROM = 11 * 60  # Morgentraining, das spaeter endet, ersetzt das Mittagessen durch die Post-Mahlzeit
LONG_RIDE_MINUTES = 120

SLOT_MEAL = "meal"
SLOT_SPORT = "sport"

PRE = (117.0, 2.0, 25.0, 1.0)  # kcal, Protein, KH, Fett (Massnahmenplan: ~120 kcal, ~25 g KH)
POST_STANDARD = (217.0, 28.0, 15.0, 5.0)  # Variante 1: Shake mit Beeren, ~220 kcal
POST_LONG = (371.0, 30.0, 38.0, 11.0)  # Variante 3: nach langen oder harten Einheiten, ~370 kcal


@dataclass
class BaseTargets:
    """Gemessene Basis-Tageswerte ohne Sport."""

    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None = None

    @classmethod
    def from_profile(cls, profile: object) -> "BaseTargets | None":
        """Liest die Basiswerte aus dem Profil; None, solange kcal/Eiweiss/KH/Fett nicht alle gesetzt sind."""
        values = [getattr(profile, name, None) for name in ("base_kcal", "base_protein_g", "base_carbs_g", "base_fat_g")]
        if any(v is None for v in values):
            return None
        return cls(*values, fiber_g=getattr(profile, "base_fiber_g", None))


@dataclass
class TimelineSlot:
    """Eine Mahlzeit oder Sport-Verpflegung zu einer Uhrzeit."""

    slot: str
    time: str
    kind: str
    label: str
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    hint: str
    options: list[str] = field(default_factory=list)


# (slot, Bezeichnung, kcal bei 2050, Eiweiss/KH/Fett in % der kcal, Hinweis, Beispiele)
_MAIN_MEALS: list[tuple[str, str, float, tuple[float, float, float], str, list[str]]] = [
    ("fruehstueck", "Frühstück", 550, (22, 44, 34), "Innerhalb 1 h nach dem Aufstehen (Kaiser).",
     ["40 g Haferflocken, 15 g Mandeln, 100 ml Milch, 150 g Magerquark, 200 g Beeren, 14 g Kokosflocken",
      "125 g Bauernbrot, 10 g Butter, 90 g Ei, 40 g Hinterschinken"]),
    ("snack", "Zwischenmahlzeit Vormittag", 275, (9, 50, 41), "Frucht und Fett, Wecker stellen falls vergessen.",
     ["260 g Apfel + 22 g Mandeln", "160 g Banane + 21 g Nüsse"]),
    ("mittag", "Mittagessen", 555, (27, 43, 30), "König: kalt oder mikrowellengeeignet, Gemüse nicht vergessen.",
     ["150 g Gemüse, 160 g Pouletbrust, 190 g Reis gekocht, 45 g Avocado, 6 ml Olivenöl",
      "150 g Gemüse, 170 g Tofu, 145 g Vollkornteigwaren gekocht, 100 g Tomatensauce"]),
    ("snack_nachmittag", "Zwischenmahlzeit Nachmittag", 250, (12, 43, 45), "Frucht und Fett.",
     ["200 g Apfel + 23 g Nüsse", "255 g Beeren + 23 g Kerne"]),
    ("abend", "Abendessen", 420, (29, 28, 43), "Bettler: Menge optional, hast du weniger Hunger, darfst du weniger essen.",
     ["150 g Ofengemüse, 100 g Pouletbrust, 155 g Kartoffeln, 15 ml Rapsöl HOLL",
      "150 g Gemüse, 250 g Skyr, 28 g Darvida, 15 ml Olivenöl"]),
]

_PRE_OPTIONS = ["120 g Banane", "45 g Laugenbrötli", "50 g Weissbrot", "25 g Lebkuchen mit Schokolade"]
_POST_STANDARD_OPTIONS = ["30 g Proteinpulver + 150 g Beeren + 100 ml Sojadrink", "330 ml Protein-Drink (Fertigprodukt)"]
_POST_LONG_OPTIONS = ["30 g Proteinpulver + 90 g Banane + 140-200 ml Milch + 15 g Mandelmus"]


def _clock(minutes: int) -> str:
    """Minuten seit Mitternacht als HH:MM."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _round_up_5(minutes: int) -> int:
    return -(-minutes // 5) * 5


def sport_fueling(cycling_minutes: float, intensity: CyclingIntensity | None, strength_minutes: float = 0.0) -> Fueling | None:
    """Kohlenhydrate waehrend der Einheit nach Massnahmenplan §06.

    Args:
        cycling_minutes: Dauer der Radeinheit (0 ohne Rad).
        intensity: Intensitaet der Radeinheit.
        strength_minutes: Dauer der Krafteinheit im selben Block.

    Returns:
        Fueling, oder None ohne Training.
    """
    if cycling_minutes <= 0:
        if strength_minutes <= 0:
            return None
        hours = strength_minutes / 60
        return Fueling(0.0, 30.0, 0.0, 30.0 * hours, "Wasser, oder 0.5 l Sportgetränk mit 30 g Pulver.")
    hours = cycling_minutes / 60
    if intensity in HARD_INTENSITIES or cycling_minutes > LONG_RIDE_MINUTES:
        low, high = 60.0, 90.0
        note = ("Glukose und Fruktose mischen; hohe Mengen über mehrere Wochen antrainieren "
                "(Start bei 40–60 g/h), ab Minute 20–30 alle 15–20 min.")
    elif cycling_minutes > 60:
        low, high = 40.0, 60.0
        note = "Ab Minute 20–30 alle 15–20 min ein paar Schlucke oder ein Stück."
    else:
        low, high, note = 0.0, 0.0, "Wasser 0.5 l genügt, wenn der Pre-Snack gegessen ist."
    return Fueling(low, high, low * hours, high * hours, note)


def _post_values(cycling_minutes: float, intensity: CyclingIntensity | None) -> tuple[tuple[float, float, float, float], list[str]]:
    long_or_hard = cycling_minutes >= LONG_RIDE_MINUTES or (intensity in HARD_INTENSITIES and cycling_minutes > 90)
    return (POST_LONG, _POST_LONG_OPTIONS) if long_or_hard else (POST_STANDARD, _POST_STANDARD_OPTIONS)


def _scaled_meals(base: BaseTargets) -> dict[str, TimelineSlot]:
    """Hauptmahlzeiten: kcal skaliert auf base.kcal, Makros so verteilt, dass die Gramm-Summen den Basiswerten entsprechen."""
    kcal_scale = base.kcal / REFERENCE_KCAL
    raw = {
        slot: (kcal * kcal_scale, kcal * kcal_scale * p / 400, kcal * kcal_scale * c / 400, kcal * kcal_scale * f / 900)
        for slot, _, kcal, (p, c, f), _, _ in _MAIN_MEALS
    }
    sums = [sum(v[i] for v in raw.values()) for i in (1, 2, 3)]
    factors = [target / total if total else 0.0 for target, total in zip((base.protein_g, base.carbs_g, base.fat_g), sums)]
    return {
        slot: TimelineSlot(
            slot=slot, time="", kind=SLOT_MEAL, label=label, kcal=raw[slot][0],
            protein_g=raw[slot][1] * factors[0], carbs_g=raw[slot][2] * factors[1], fat_g=raw[slot][3] * factors[2],
            hint=hint, options=list(options),
        )
        for slot, label, _, _, hint, options in _MAIN_MEALS
    }


def _absorb(target: TimelineSlot, protein_g: float, carbs_g: float, fat_g: float, kcal: float) -> TimelineSlot:
    """Addiert Werte (z. B. Post-Workout oder entfallender Snack) auf eine Mahlzeit."""
    return replace(target, kcal=target.kcal + kcal, protein_g=target.protein_g + protein_g,
                   carbs_g=target.carbs_g + carbs_g, fat_g=target.fat_g + fat_g)


def build_timeline(
    base: BaseTargets,
    cycling_minutes: float,
    intensity: CyclingIntensity | None,
    strength_sessions: int,
    evening: bool,
    weekend: bool,
) -> list[TimelineSlot]:
    """Baut den Tagesablauf mit Uhrzeiten, Mengen und Beispielen.

    Mo–Fr (`evening`): Training 18:00, Post-Workout und Abendessen fallen zusammen. Sonst Training 10:00 nach dem
    Fruehstueck; endet es ab 11:00, ersetzt die Post-Mahlzeit das Mittagessen, der Vormittags-Snack entfaellt.

    Args:
        base: Basis-Tageswerte ohne Sport.
        cycling_minutes: Radzeit des Tages (0 ohne Rad).
        intensity: Intensitaet der Radeinheit.
        strength_sessions: Anzahl Krafteinheiten (direkt nach dem Rad im selben Block).
        evening: Training nach der Arbeit.
        weekend: Samstag oder Sonntag (spaeteres Fruehstueck).

    Returns:
        Slots nach Uhrzeit sortiert; Mahlzeiten (kind "meal") summieren sich ohne Sport auf `base`.
    """
    meals = _scaled_meals(base)
    times = {"fruehstueck": (8 if weekend else 7) * 60, "snack": 10 * 60, "mittag": 12 * 60 + 30,
             "snack_nachmittag": 15 * 60 + 30, "abend": 18 * 60 + 30}
    strength_minutes = STRENGTH_MINUTES if strength_sessions > 0 else 0
    duration = int(cycling_minutes) + strength_minutes
    sport: list[TimelineSlot] = []

    if duration > 0:
        start = EVENING_START if evening else MORNING_START
        end = _round_up_5(start + duration)
        fueling = sport_fueling(cycling_minutes, intensity, strength_minutes)
        intra_carbs = (fueling.carbs_g_total_min + fueling.carbs_g_total_max) / 2
        (post_kcal, post_p, post_c, post_f), post_options = _post_values(cycling_minutes, intensity)
        pre_kcal, pre_p, pre_c, pre_f = PRE

        sport.append(TimelineSlot("pre", _clock(start - PRE_LEAD_MINUTES), SLOT_SPORT, "Pre-Training", pre_kcal, pre_p, pre_c, pre_f,
                                  "30–60 min vor dem Training, auch wenn die letzte Mahlzeit 2–3 h her ist.", _PRE_OPTIONS))
        sport.append(TimelineSlot("intra", _clock(start), SLOT_SPORT, "Während dem Training", intra_carbs * 4, 0.0, intra_carbs, 0.0,
                                  f"{_clock(start)}–{_clock(end)}: {fueling.note}",
                                  [f"{fueling.carbs_g_per_hour_min:.0f}–{fueling.carbs_g_per_hour_max:.0f} g KH pro Stunde"]
                                  if fueling.carbs_g_per_hour_max else []))
        if evening:
            meals["abend"] = replace(
                _absorb(meals["abend"], post_p, post_c, post_f, post_kcal),
                label="Abendessen (Post-Workout)",
                hint=("Direkt nach dem Training: ≥ 30 g Eiweiss + Kohlenhydrate, Recovery. Unter der Woche zu spät für "
                      "«4 h vor dem Schlafen», die Menge darf bei wenig Hunger sinken."),
            )
            times["abend"] = end + POST_DINNER_DELAY
        else:
            post = TimelineSlot("post", _clock(end), SLOT_SPORT, "Post-Training", post_kcal, post_p, post_c, post_f,
                                "Innerhalb 30–60 min nach dem Training; nach Kraft immer 25–30 g Eiweiss.", post_options)
            snack = meals.pop("snack")  # morgens trainiert: Vormittags-Snack entfaellt, kcal gehen ins Mittagessen
            lunch = _absorb(meals["mittag"], snack.protein_g, snack.carbs_g, snack.fat_g, snack.kcal)
            if end >= LUNCH_MERGE_FROM:
                meals["mittag"] = replace(
                    _absorb(lunch, post.protein_g, post.carbs_g, post.fat_g, post.kcal),
                    label="Mittagessen (Post-Training)", hint="Direkt nach dem Training, ersetzt Post-Shake und Mittagessen.",
                )
                times["mittag"] = end
            else:
                meals["mittag"] = lunch
                sport.append(post)

    slots = [replace(slot, time=_clock(times[slot.slot])) for slot in meals.values()] + sport
    return sorted(slots, key=lambda s: s.time)


def timeline_totals(slots: list[TimelineSlot]) -> tuple[float, float, float, float]:
    """Summe (kcal, Eiweiss, KH, Fett) aller Slots."""
    return (sum(s.kcal for s in slots), sum(s.protein_g for s in slots),
            sum(s.carbs_g for s in slots), sum(s.fat_g for s in slots))
