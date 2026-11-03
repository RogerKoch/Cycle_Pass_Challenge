"""Wochenanalyse der Ernaehrung: Ist gegen die Slots des Tagesablaufs (engine.day_timeline).

Reine Funktionen ohne DB-Zugriff. Gemuese und Ballaststoffe werden nicht bewertet (nicht erfasst).
"""

from dataclasses import dataclass, field
from datetime import date

TOLERANCE_UP = 1.10  # Spiel nach oben ueber dem Ziel (kcal, KH)
TOLERANCE_DOWN = 0.90
DINNER_HEAVY_RATIO = 1.30
SNACKS_LOW_RATIO = 0.60
FAT_LOW_WARN_RATIO = 0.70
PROTEIN_EVENING_SHARE_GAP = 0.12
TRAINING_GAP_RATIO = 0.05

MACROS = ("kcal", "protein_g", "carbs_g", "fat_g")
SPORT_LOG_KEYS = ("pre", "intra", "post", "training")  # training = Altwert
MAIN_SLOT_ORDER = ("fruehstueck", "snack", "mittag", "snack_nachmittag", "abend")
SEVERITY_ORDER = {"warn": 0, "info": 1}


@dataclass
class DayInput:
    """Plan und Ist eines Tages. `plan` = Timeline-Slots als Dicts, `eaten` = Summen je Log-Mahlzeit."""

    day: date
    plan: list[dict]
    eaten: dict[str, dict[str, float]] = field(default_factory=dict)


def _zero() -> dict[str, float]:
    return dict.fromkeys(MACROS, 0.0)


def _add(total: dict[str, float], values: dict[str, float]) -> None:
    for key in MACROS:
        total[key] += values.get(key, 0.0)


def _target_slot(log_key: str, plan_meals: dict[str, dict], trained: bool) -> str:
    """Ordnet einen Log-Eintrag dem Plan-Slot zu, der ihn aufgenommen hat (Sport, entfallener Snack, Post-Mahlzeit)."""
    if log_key in SPORT_LOG_KEYS:
        if log_key == "post":
            for host in ("abend", "mittag"):
                if host in plan_meals and "Post" in plan_meals[host]["label"]:
                    return host
        if trained or log_key == "training":
            return "sport"
    if log_key == "snack" and "snack" not in plan_meals:
        return "mittag"
    return log_key


def _pct(eaten: float, plan: float) -> int | None:
    return round(eaten / plan * 100) if plan else None


def review_days(days: list[DayInput]) -> dict:
    """Vergleicht Ist und Soll pro Slot und Tag, mit Hinweisen.

    Args:
        days: Tage des Zeitraums; nur Tage mit gegessenen Eintraegen zaehlen.

    Returns:
        Dict mit `days_logged`, `slots` (Ø Soll/Ist je Slot), `daily` (Ø Tagessummen), `findings` und `notes`.
    """
    logged = [d for d in days if d.eaten]
    result: dict = {
        "days_logged": len(logged), "slots": [], "daily": {}, "findings": [],
        "notes": ["Gemüse und Ballaststoffe werden nicht erfasst und deshalb nicht bewertet."],
    }
    if not logged:
        return result

    plan_sum: dict[str, dict[str, float]] = {}
    eaten_sum: dict[str, dict[str, float]] = {}
    entry_days: dict[str, int] = {}
    labels: dict[str, str] = {}
    daily_plan, daily_eaten = _zero(), _zero()
    training_days = pre_missing = post_missing = 0
    training_gap_kcal = 0.0
    for d in logged:
        plan_meals = {s["slot"]: s for s in d.plan if s["kind"] == "meal"}
        sport_plan = [s for s in d.plan if s["kind"] == "sport"]
        trained = bool(sport_plan)
        day_plan, day_eaten = _zero(), _zero()
        for s in d.plan:
            _add(day_plan, s)
        for values in d.eaten.values():
            _add(day_eaten, values)
        _add(daily_plan, day_plan)
        _add(daily_eaten, day_eaten)

        for slot, s in plan_meals.items():
            labels[slot] = s["label"]
            _add(plan_sum.setdefault(slot, _zero()), s)
        if trained:
            labels["sport"] = "Sport-Verpflegung (Pre, Intra, Post)"
            for s in sport_plan:
                _add(plan_sum.setdefault("sport", _zero()), s)
        grouped: dict[str, dict[str, float]] = {}
        for key, values in d.eaten.items():
            _add(grouped.setdefault(_target_slot(key, plan_meals, trained), _zero()), values)
        for slot, values in grouped.items():
            _add(eaten_sum.setdefault(slot, _zero()), values)
            entry_days[slot] = entry_days.get(slot, 0) + 1

        if trained:
            training_days += 1
            training_gap_kcal += day_plan["kcal"] - day_eaten["kcal"]
            if "pre" not in d.eaten and "training" not in d.eaten:
                pre_missing += 1
            if any(s["slot"] == "post" for s in sport_plan) and "post" not in d.eaten and "training" not in d.eaten:
                post_missing += 1

    n = len(logged)
    for slot in (*MAIN_SLOT_ORDER, "sport"):
        if slot not in plan_sum and slot not in eaten_sum:
            continue
        plan_avg = {k: v / n for k, v in plan_sum.get(slot, _zero()).items()}
        eaten_avg = {k: v / n for k, v in eaten_sum.get(slot, _zero()).items()}
        result["slots"].append({
            "slot": slot, "label": labels.get(slot, slot), "plan": plan_avg, "eaten": eaten_avg,
            "days_with_entry": entry_days.get(slot, 0), "pct_kcal": _pct(eaten_avg["kcal"], plan_avg["kcal"]),
        })
    plan_avg = {k: v / n for k, v in daily_plan.items()}
    eaten_avg = {k: v / n for k, v in daily_eaten.items()}
    result["daily"] = {k: {"plan": plan_avg[k], "eaten": eaten_avg[k], "pct": _pct(eaten_avg[k], plan_avg[k])} for k in MACROS}
    result["findings"] = _findings(
        {s["slot"]: s for s in result["slots"]}, plan_avg, eaten_avg, training_days, pre_missing, post_missing,
        training_gap_kcal / training_days if training_days else 0.0,
    )
    return result


def _findings(
    slots: dict[str, dict], plan: dict, eaten: dict, training_days: int, pre_missing: int, post_missing: int,
    training_gap_kcal: float,
) -> list[dict]:
    """Regelbasierte Hinweise mit konkreter Handlung, schwerwiegendste zuerst."""
    out: list[dict] = []

    def add(id_: str, severity: str, title: str, detail: str) -> None:
        out.append({"id": id_, "severity": severity, "title": title, "detail": detail})

    dinner = slots.get("abend")
    if dinner and dinner["plan"]["kcal"] and dinner["eaten"]["kcal"] / dinner["plan"]["kcal"] > DINNER_HEAVY_RATIO:
        add("dinner_heavy", "warn", "Abendessen zu gross",
            f"Ø {dinner['eaten']['kcal']:.0f} statt {dinner['plan']['kcal']:.0f} kcal. Kohlenhydrate und Menge in die "
            "Zwischenmahlzeiten und das Mittagessen verschieben (Kaiser-König-Bettler).")
    snack_plan = sum(slots[s]["plan"]["kcal"] for s in ("snack", "snack_nachmittag") if s in slots)
    snack_eaten = sum(slots[s]["eaten"]["kcal"] for s in ("snack", "snack_nachmittag") if s in slots)
    if snack_plan and snack_eaten / snack_plan < SNACKS_LOW_RATIO:
        add("snacks_small", "warn", "Zwischenmahlzeiten zu klein",
            f"Ø {snack_eaten:.0f} statt {snack_plan:.0f} kcal. Frucht plus Nüsse oder Kerne (ca. 250 kcal) einplanen, Wecker stellen.")
    fat_ratio = eaten["fat_g"] / plan["fat_g"] if plan["fat_g"] else 1.0
    if fat_ratio < TOLERANCE_DOWN:
        add("fat_low", "warn" if fat_ratio < FAT_LOW_WARN_RATIO else "info", "Fett unter Ziel",
            f"Ø {eaten['fat_g']:.0f} statt {plan['fat_g']:.0f} g. Nüsse, Kerne, Avocado oder Rapsöl HOLL in Zwischenmahlzeiten "
            "und Hauptmahlzeiten ergänzen (Vitamin E, Zellmembranen).")
    if eaten["protein_g"] < plan["protein_g"] * TOLERANCE_DOWN:
        add("protein_low", "warn", "Eiweiss unter Ziel",
            f"Ø {eaten['protein_g']:.0f} statt {plan['protein_g']:.0f} g. Eiweiss gleichmässig auf alle Mahlzeiten verteilen.")
    for key, label in (("kcal", "Energie"), ("carbs_g", "Kohlenhydrate")):
        if plan[key] and eaten[key] > plan[key] * TOLERANCE_UP:
            add(f"{key}_high", "info", f"{label} über dem Toleranzbereich",
                f"Ø {eaten[key]:.0f} bei Ziel {plan[key]:.0f} (+{(eaten[key] / plan[key] - 1) * 100:.0f} %).")
    if eaten["kcal"] < plan["kcal"] * TOLERANCE_DOWN:
        add("kcal_low", "warn", "Energie unter Ziel",
            f"Ø {eaten['kcal']:.0f} statt {plan['kcal']:.0f} kcal. Nicht hungern: regelmässig essen, nichts auslassen.")
    if training_days and training_gap_kcal > plan["kcal"] * TRAINING_GAP_RATIO:
        add("training_underfed", "warn", "Trainingstage unter Ziel",
            f"An Trainingstagen fehlen Ø {training_gap_kcal:.0f} kcal. Pre, Intra und Post zusätzlich zu den Mahlzeiten essen.")
    if pre_missing:
        add("pre_missing", "warn", "Pre-Snack fehlt",
            f"An {pre_missing} von {training_days} Trainingstagen ohne Pre-Snack (25 g KH, 30–60 min vor dem Training).")
    if post_missing:
        add("post_missing", "warn", "Post-Training fehlt",
            f"An {post_missing} von {training_days} Trainingstagen ohne Post-Shake (25–30 g Eiweiss innerhalb 30–60 min).")
    if dinner and eaten["protein_g"] and plan["protein_g"]:
        plan_share = dinner["plan"]["protein_g"] / plan["protein_g"]
        eaten_share = dinner["eaten"]["protein_g"] / eaten["protein_g"]
        if eaten_share > plan_share + PROTEIN_EVENING_SHARE_GAP:
            add("protein_evening", "info", "Eiweiss zu spät am Tag",
                f"{eaten_share * 100:.0f} % des Eiweisses am Abend (Plan {plan_share * 100:.0f} %). "
                "Frühstück und Zwischenmahlzeiten mit Quark, Skyr, Ei oder Pulver ergänzen.")
    out.sort(key=lambda f: SEVERITY_ORDER[f["severity"]])
    return out
