"use strict";

const $ = (id) => document.getElementById(id);

const PHASE_NAMES = {
  phase0_wiedereinstieg: "Wiedereinstieg",
  base: "Base",
  build1: "Build 1",
  build2: "Build 2",
  peak_taper: "Peak/Taper",
  passsaison: "Passsaison",
};
const STATUS_NAMES = { planned: "geplant", done: "erledigt", modified: "angepasst", skipped: "abgesagt" };
const STATUS_MARKS = { planned: "", done: "✓", modified: "✎", skipped: "✗" };
const MEALS = [
  ["fruehstueck", "Frühstück"],
  ["mittag", "Mittag"],
  ["abend", "Abend"],
  ["snack", "Snack"],
  ["training", "Training"],
];
const NO_TOTALS = { kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 };

async function api(path) {
  // relativ zur App-Wurzel aufloesen (Seite liegt direkt unter <praefix>/)
  const response = await fetch(path.replace(/^\//, ""));
  const data = await response.json().catch(() => ({}));
  return { ok: response.ok, data };
}

function localIso(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) if (child !== null && child !== undefined && child !== false) node.append(child);
  return node;
}

const round = (value) => Math.round(Number(value));
const today = () => localIso(new Date());

function fmtMinutes(minutes) {
  const m = round(minutes);
  return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")} h` : `${m} min`;
}

function fmtDate(iso, options) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("de-CH", options);
}

// ---------------------------------------------------------------- Training

function trainingCard(day) {
  const head = el("h2", {}, "🚴 Training heute");
  if (!day.started) {
    return [head, el("p", { class: "hint" }, "Vor dem Programmstart ist nichts geplant.")];
  }
  const done = day.imported.some((a) => a.is_ride || a.is_strength);
  const badges = el("p", { class: "card-sub" },
    el("span", { class: "badge" }, `${PHASE_NAMES[day.phase.phase_id] || day.phase.phase_id} · Woche ${day.phase.week_in_phase}`),
    " ",
    day.phase.deload ? el("span", { class: "badge warn" }, "Erholungswoche") : null,
    done
      ? el("span", { class: "badge" }, "erledigt (Garmin)")
      : day.status !== "planned" ? el("span", { class: "badge muted" }, STATUS_NAMES[day.status]) : null);
  const lines = [];
  if (day.event) lines.push(el("p", {}, `🏁 ${day.event.name} · ${day.event.label}`));
  if (day.cycling) lines.push(el("p", {}, el("strong", {}, day.cycling.title), ` · ${fmtMinutes(day.cycling.minutes)}`));
  if (day.strength) lines.push(el("p", {}, `💪 ${day.strength.title} · ${day.strength.duration_minutes} min`));
  if (!day.cycling && !day.strength) lines.push(el("p", {}, el("strong", {}, "Ruhetag"), " · nur Mobility"));
  for (const warning of day.warnings) lines.push(el("p", { class: "hint" }, `⚠ ${warning.message}`));
  return [head, badges, ...lines, el("a", { class: "action-link", href: "training/#tag" }, "Details und Anpassen →")];
}

// ---------------------------------------------------------------- Ernaehrung

function bar(value, target) {
  const pct = target > 0 ? Math.min(100, (value / target) * 100) : 0;
  return el("div", { class: value > target ? "bar over" : "bar" }, el("span", { style: `width: ${pct}%` }));
}

function macroRow(name, value, target) {
  return el("div", { class: "macro" }, el("span", {}, name), bar(value, target),
    el("span", { class: "num" }, `${round(value)} / ${round(target)} g`));
}

function nutritionCard(plan, totals) {
  const head = el("h2", {}, "🍽 Ernährung heute");
  if (plan.error) {
    return [head, el("p", { class: "hint" }, `Nicht verfügbar: ${plan.error}`),
      el("a", { class: "action-link", href: "profil/" }, "Zum Profil →")];
  }
  const target = plan.nutrition.target_kcal;
  const m = plan.macros;
  const meals = MEALS.map(([meal, name]) => el("a", { href: `ernaehrung/?add=${meal}` }, `+ ${name}`));
  return [
    head,
    el("div", { class: "kcal-head" },
      el("div", {}, el("span", { class: "kcal-big" }, String(round(totals.kcal))), ` / ${round(target)} kcal`),
      el("span", { class: "hint" }, `noch ${round(target - totals.kcal)} kcal`)),
    bar(totals.kcal, target),
    macroRow("Protein", totals.protein_g, m.protein_g),
    macroRow("KH", totals.carbs_g, m.carbs_g),
    macroRow("Fett", totals.fat_g, m.fat_g),
    el("div", { class: "meal-buttons" }, ...meals),
    el("a", { class: "action-link", href: "ernaehrung/" }, "Zum Ernährungs-Tagebuch →"),
  ];
}

// ---------------------------------------------------------------- Woche

function weekCard(week) {
  const days = week.days.map((d) => el("a", {
    href: "training/#woche",
    class: [d.date === today() ? "today" : "", d.status === "done" || d.status === "modified" ? "done" : "",
      d.status === "skipped" ? "skipped" : ""].join(" "),
  }, fmtDate(d.date, { weekday: "short" }), el("span", { class: "mark" }, `${d.cycling ? "🚴" : ""}${d.strength ? "💪" : ""}`),
    el("span", { class: "mark" }, STATUS_MARKS[d.status])));
  return [el("h2", {}, "Diese Woche"), el("div", { class: "week-strip" }, ...days)];
}

// ---------------------------------------------------------------- Review

async function loadReviewBanner() {
  const { ok, data } = await api("/api/review");
  const banner = $("review-banner");
  const count = ok ? data.findings.length : 0;
  banner.hidden = count === 0;
  if (!count) return;
  const urgent = data.findings.some((f) => f.severity === "alert");
  banner.className = urgent ? "card banner alert" : "card banner";
  banner.textContent = `${urgent ? "⚠ " : ""}${count} offene${count === 1 ? "r Hinweis" : " Hinweise"} im Check-in-Review →`;
}

// ---------------------------------------------------------------- Laden

async function load() {
  const iso = today();
  $("greeting").textContent = `Heute, ${fmtDate(iso, { weekday: "long", day: "numeric", month: "long" })}`;
  const [week, plan, log] = await Promise.all([
    api(`/api/calendar/week/${iso}`),
    api("/api/plan/today"),
    api(`/api/food-log/${iso}`),
  ]);
  if (!week.ok) {
    $("page-msg").textContent = `${week.data.error || "Laden fehlgeschlagen"} – Profil anlegen unter Profil.`;
    return;
  }
  const day = week.data.days.find((d) => d.date === iso);
  $("training-card").replaceChildren(...trainingCard(day));
  $("nutrition-card").replaceChildren(
    ...nutritionCard(plan.ok ? plan.data : { error: plan.data.error }, log.ok ? log.data.totals : NO_TOTALS));
  $("week-card").replaceChildren(...weekCard(week.data));
  loadReviewBanner();
}

load();
