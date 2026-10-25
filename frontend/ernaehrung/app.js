"use strict";

const $ = (id) => document.getElementById(id);

const MEALS = [
  ["fruehstueck", "Frühstück"],
  ["snack", "Snack 1"],
  ["mittag", "Mittag"],
  ["training", "Snack 2"],
  ["abend", "Abend"],
];
const MEAL_NAMES = Object.fromEntries(MEALS);
const ZXING_URL = "https://cdn.jsdelivr.net/npm/@zxing/browser@0.2.1/umd/zxing-browser.min.js";

const state = {
  date: localIso(new Date()),
  day: null,
  view: "tag", // tag | woche | monat
  overview: [], // /api/plan/days (Woche/Monat): [{date, target, eaten}]
  target: null, // {kcal, protein_g, carbs_g, fat_g} fuer den gewaehlten Tag
  plan: null, // /api/plan/<datum> (Mahlzeiten, Fueling, Hinweise) oder null
  meal: "fruehstueck",
  planned: false, // Dialoge legen geplante statt gegessene Eintraege an
  amount: null, // {food, entry?}
  scanControls: null,
};

async function api(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  // relativ zur App-Wurzel aufloesen (Seite liegt unter <praefix>/ernaehrung/)
  const response = await fetch(`..${path}`, options);
  const data = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, data };
}

function localIso(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function shiftDate(iso, days) {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + days);
  return localIso(date);
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "onclick") node.addEventListener("click", value);
    else if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) if (child !== null && child !== undefined) node.append(child);
  return node;
}

const round = (value) => Math.round(Number(value));
const today = () => localIso(new Date());
const isToday = () => state.date === today();

function openDialog(id) {
  const dialog = $(id);
  if (!dialog.open) dialog.showModal();
}

function closeDialog(id) {
  const dialog = $(id);
  if (dialog.open) dialog.close();
}

// ---------------------------------------------------------------- Tag laden/rendern

// Tag (Tagebuch + Soll) und je nach Ansicht die Uebersicht; jede Aenderung laedt ueber diese Funktion neu
async function loadDay() {
  const range = overviewRange();
  const [log, plan, overview] = await Promise.all([
    api("GET", `/api/food-log/${state.date}`),
    api("GET", `/api/plan/${state.date}`),
    range ? api("GET", `/api/plan/days?from=${range[0]}&to=${range[1]}`) : null,
  ]);
  if (!log.ok) {
    $("summary-msg").textContent = log.data.error || "Tag konnte nicht geladen werden";
    return;
  }
  state.day = log.data;
  state.overview = overview && overview.ok ? overview.data.days : [];
  applyTarget(plan);
  render();
}

function applyTarget(plan) {
  if (!plan.ok) {
    state.target = null;
    state.plan = null;
    $("summary-msg").textContent = `Soll nicht verfügbar: ${plan.data.error}`;
    return;
  }
  const data = plan.data;
  $("summary-msg").textContent = data.event
    ? `🏁 ${data.event.name} · ${data.event.label}: ${data.timing_hints[0] || ""}`
    : "";
  state.target = { kcal: data.nutrition.target_kcal, ...data.macros };
  state.plan = data;
}

// ---------------------------------------------------------------- Ansichten (Tag/Woche/Monat)

const VIEWS = ["tag", "woche", "monat"];

function viewFromHash() {
  const hash = location.hash.slice(1);
  if (VIEWS.includes(hash)) return hash;
  return window.matchMedia("(min-width: 900px)").matches ? "monat" : "tag";
}

function mondayOf(iso) {
  const date = new Date(`${iso}T12:00:00`);
  return shiftDate(iso, -((date.getDay() + 6) % 7));
}

function overviewRange() {
  if (state.view === "woche") {
    const monday = mondayOf(state.date);
    return [monday, shiftDate(monday, 6)];
  }
  if (state.view === "monat") {
    const first = `${state.date.slice(0, 7)}-01`;
    const next = new Date(`${first}T12:00:00`);
    next.setMonth(next.getMonth() + 1);
    const last = shiftDate(localIso(next), -1);
    return [mondayOf(first), shiftDate(mondayOf(last), 6)];
  }
  return null;
}

function isoWeek(iso) {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7)); // Donnerstag der Woche
  const firstThursday = new Date(date.getFullYear(), 0, 4);
  return 1 + Math.round(((date - firstThursday) / 86400000 - 3 + ((firstThursday.getDay() + 6) % 7)) / 7);
}

function fmtDate(iso, options) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("de-CH", options);
}

function viewLabel() {
  if (state.view === "monat") return fmtDate(state.date, { month: "long", year: "numeric" });
  if (state.view === "woche") {
    const monday = mondayOf(state.date);
    const range = `${fmtDate(monday, { day: "numeric", month: "short" })}–${fmtDate(shiftDate(monday, 6), { day: "numeric", month: "short" })}`;
    return `KW ${isoWeek(state.date)} · ${range}`;
  }
  const label = fmtDate(state.date, { weekday: "short", day: "numeric", month: "short" });
  return isToday() ? `Heute, ${label}` : label;
}

function applyView() {
  $("month").hidden = state.view !== "monat";
  $("week").hidden = state.view !== "woche";
  $("cal-layout").classList.toggle("has-side", state.view !== "tag");
  for (const link of document.querySelectorAll("[data-view]")) {
    link.setAttribute("aria-current", link.dataset.view === state.view ? "page" : "false");
  }
}

// Pfeile der Kopfzeile: Tag +-1, Woche +-7, Monat +-1 Monat
function shiftView(direction) {
  if (state.view === "tag") state.date = shiftDate(state.date, direction);
  else if (state.view === "woche") state.date = shiftDate(state.date, 7 * direction);
  else {
    const date = new Date(`${state.date}T12:00:00`);
    date.setDate(1);
    date.setMonth(date.getMonth() + direction);
    const first = localIso(date);
    state.date = first.slice(0, 7) === today().slice(0, 7) ? today() : first;
  }
  return loadDay();
}

// Zustand eines Tages: vergangene Tage nach Ist/Soll, heute und Zukunft "offen"
function dayState(d) {
  if (!d.target) return { cls: "", diff: null };
  if (d.date >= today()) return { cls: "future", diff: null };
  if (!d.eaten) return { cls: "empty", diff: null };
  const ratio = d.eaten.kcal / d.target.kcal;
  const diff = d.eaten.kcal - d.target.kcal;
  return { cls: ratio < 0.9 ? "under" : ratio > 1.05 ? "over" : "ok", diff };
}

const signed = (value) => `${value > 0 ? "+" : value < 0 ? "−" : "±"}${Math.abs(round(value))}`;

function renderMonth() {
  const month = state.date.slice(0, 7);
  const head = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"].map((name) => el("div", { class: "dh" }, name));
  const cells = state.overview.map((d) => {
    const ds = dayState(d);
    const classes = ["cell", ds.cls, d.date.startsWith(month) ? "" : "out", d.date === today() ? "today" : "",
      d.date === state.date ? "sel" : "", d.planned ? "has-plan" : ""].join(" ");
    const text = d.target
      ? (d.eaten ? `${round(d.eaten.kcal)} / ${round(d.target.kcal)} kcal` : `Soll ${round(d.target.kcal)} kcal`)
      : "";
    const planText = d.planned ? `geplant ${round(d.planned.kcal)} kcal` : "";
    const title = [fmtDate(d.date, { weekday: "long", day: "numeric", month: "long" }), text, planText].filter(Boolean).join(" · ");
    return el("button", { class: classes, type: "button", title, "aria-label": title, onclick: () => selectDay(d.date) },
      el("span", { class: "num" }, String(Number(d.date.slice(8)))),
      d.eaten ? el("span", { class: "line" }, String(round(d.eaten.kcal))) : null,
      d.target ? el("span", { class: "line" }, d.eaten ? `/${round(d.target.kcal)}` : String(round(d.target.kcal))) : null,
      d.planned && !d.eaten ? el("span", { class: "line plan" }, `≈${round(d.planned.kcal)}`) : null);
  });
  $("month-grid").replaceChildren(...head, ...cells);
}

function renderWeek() {
  const items = state.overview.map((d) => {
    const ds = dayState(d);
    const detail = d.target
      ? `${d.eaten ? `Ist ${round(d.eaten.kcal)}` : "Ist –"} · Soll ${round(d.target.kcal)} kcal`
        + (d.planned ? ` · geplant ${round(d.planned.kcal)}` : "")
      : "kein Soll";
    const classes = [ds.cls, d.date === state.date ? "current" : ""].join(" ");
    return el("li", { class: classes, onclick: () => selectDay(d.date) },
      el("span", { class: "name" }, fmtDate(d.date, { weekday: "short", day: "numeric", month: "short" }),
        el("span", { class: "sub" }, detail)),
      el("span", { class: "kcal" }, ds.diff === null ? "" : `${signed(ds.diff)} kcal`));
  });
  $("week-list").replaceChildren(...items);
}

async function selectDay(iso) {
  state.date = iso;
  await loadDay();
}

function render() {
  $("date-label").textContent = viewLabel();
  applyView();
  if (state.view === "monat") renderMonth();
  if (state.view === "woche") renderWeek();
  renderTotals();
  renderPlan();
  renderMeals();
  mountDayComment($("comment-card"), { base: "../", date: state.date });
}

// Verteilung des Tagessolls auf Mahlzeiten, Fueling waehrend der Fahrt und Timing-Hinweise
function renderPlan() {
  const plan = state.plan;
  $("plan-card").hidden = !plan;
  if (!plan) return;
  const m = plan.macros;
  const meals = plan.meals.map((meal) => el("tr", {},
    el("td", {}, meal.label, el("span", { class: "sub" }, meal.hint)),
    el("td", { class: "num" }, `${round(meal.kcal)} kcal`, el("span", { class: "sub" }, `${round(meal.protein_g)} g P · ${round(meal.carbs_g)} g KH · ${round(meal.fat_g)} g F`))));
  const fueling = plan.fueling && plan.fueling.carbs_g_per_hour_max > 0
    ? `Während der Fahrt: ${round(plan.fueling.carbs_g_per_hour_min)}–${round(plan.fueling.carbs_g_per_hour_max)} g KH/h `
      + `(gesamt ${round(plan.fueling.carbs_g_total_min)}–${round(plan.fueling.carbs_g_total_max)} g). ${plan.fueling.note}`
    : plan.fueling ? `Während der Fahrt: ${plan.fueling.note}` : null;
  // replaceChildren schreibt null als Text "null": nur echte Knoten uebergeben
  $("plan-card").replaceChildren(...[
    el("h2", {}, `Soll: ${round(plan.nutrition.target_kcal)} kcal`),
    el("p", { class: "hint" }, `Protein ${round(m.protein_g)} g · KH ${round(m.carbs_g)} g · Fett ${round(m.fat_g)} g`),
    el("table", { class: "plan-meals" }, el("tbody", {}, ...meals)),
    fueling ? el("p", { class: "hint" }, fueling) : null,
    ...plan.timing_hints.map((hint) => el("p", { class: "hint" }, hint)),
  ].filter((node) => node !== null));
}

function renderTotals() {
  const totals = state.day.totals;
  const target = state.target;
  const rows = [
    ["Protein", "protein_g"],
    ["KH", "carbs_g"],
    ["Fett", "fat_g"],
  ].map(([name, key]) => macroRow(name, totals[key], target ? target[key] : null, "g"));
  const kcalText = target ? `/ ${round(target.kcal)} kcal` : "kcal";
  const remaining = target && state.date >= today() ? el("span", { class: "hint" }, `noch ${round(target.kcal - totals.kcal)} kcal`) : null;
  $("totals").replaceChildren(
    el("div", { class: "kcal-head" },
      el("div", {}, el("span", { class: "kcal-big" }, String(round(totals.kcal))), ` ${kcalText}`),
      remaining),
    ...(target ? [bar(totals.kcal, target.kcal)] : []),
    ...rows,
    ...[diffLine(totals, target), plannedLine(target)].filter(Boolean),
  );
}

// Geplante (noch nicht gegessene) Eintraege des Tages
function plannedLine(target) {
  const planned = state.day.planned_totals;
  if (!planned || !planned.kcal) return null;
  const text = `Geplant: ${round(planned.kcal)} kcal${target ? ` (Soll ${round(target.kcal)})` : ""}`;
  const consume = state.date <= today()
    ? el("button", { type: "button", onclick: () => consumePlanned() }, "Alle geplanten übernehmen")
    : null;
  return el("div", { class: "plan-line" }, el("span", {}, text), consume);
}

// Abgeschlossene Tage: Abweichung zum Soll
function diffLine(totals, target) {
  if (!target || state.date >= today()) return null;
  if (!totals.kcal) return el("p", { class: "diff empty" }, "Nichts erfasst");
  const ds = dayState({ date: state.date, target, eaten: totals });
  const text = ds.cls === "ok" ? `im Soll (${signed(ds.diff)} kcal)` : `${signed(ds.diff)} kcal ${ds.diff < 0 ? "unter" : "über"} Soll`;
  return el("p", { class: `diff ${ds.cls}` }, text);
}

function bar(value, target) {
  const pct = target > 0 ? Math.min(100, (value / target) * 100) : 0;
  const node = el("div", { class: value > target * 1.05 ? "bar over" : "bar" }, el("span"));
  node.firstChild.style.width = `${pct}%`;
  return node;
}

function macroRow(name, value, target, unit) {
  return el("div", { class: "macro" },
    el("span", {}, name),
    target ? bar(value, target) : el("span"),
    el("span", { class: "num" }, target ? `${round(value)} / ${round(target)} ${unit}` : `${round(value)} ${unit}`));
}

function entryAmount(entry) {
  if (entry.grams === null) return "";
  if (entry.portion_g) {
    const count = entry.grams / entry.portion_g;
    if (Math.abs(count * 2 - Math.round(count * 2)) < 0.01) return `${count} × ${entry.portion_label}`;
  }
  return `${round(entry.grams)} g`;
}

// Richtwerte je Log-Mahlzeit aus dem Tagesplan; Snack 1 -> "snack", Snack 2 -> "training" (Log-Schluessel)
const PLAN_SLOT_TO_MEAL = { snack_1: "snack", snack_2: "training" };

function mealTargets() {
  const targets = {};
  for (const slot of state.plan ? state.plan.meals : []) {
    targets[PLAN_SLOT_TO_MEAL[slot.slot] || slot.slot] = {
      kcal: slot.kcal, protein_g: slot.protein_g, carbs_g: slot.carbs_g, fat_g: slot.fat_g,
    };
  }
  return targets;
}

function renderMeals() {
  const future = state.date > today();
  const past = state.date < today();
  const targets = mealTargets();
  const sections = MEALS.map(([meal, name]) => {
    const entries = state.day.meals[meal];
    const eaten = entries.filter((e) => e.status === "eaten");
    const planned = entries.filter((e) => e.status === "planned");
    const kcal = eaten.reduce((sum, e) => sum + e.kcal, 0);
    const sumOf = (field) => eaten.reduce((sum, e) => sum + (e[field] || 0), 0);
    const goal = targets[meal];
    const plannedKcal = planned.reduce((sum, e) => sum + e.kcal, 0);
    const items = entries.map((entry) =>
      el("li", { class: entry.status === "planned" ? "planned-entry" : "", onclick: () => openEntry(entry) },
        el("span", { class: "name" }, entry.label, el("span", { class: "sub" },
          [entry.status === "planned" ? "geplant" : null, entryAmount(entry)].filter(Boolean).join(" · "))),
        el("span", { class: "kcal" }, `${round(entry.kcal)} kcal`)));
    const buttons = [];
    if (!future) buttons.push(el("button", { class: "primary", onclick: () => openSearch(meal) }, "+ Hinzufügen"));
    if (!past) buttons.push(el("button", { class: future ? "primary" : "", onclick: () => openSearch(meal, true) }, future ? "+ Planen" : "Planen"));
    buttons.push(el("button", { onclick: () => openTemplates(meal) }, "Vorlagen"));
    if (planned.length && !future) buttons.push(el("button", { onclick: () => consumePlanned(meal) }, "Alles übernehmen"));
    return el("section", { class: "card" },
      el("div", { class: "meal-head" },
        el("h2", {}, name),
        el("span", { class: "meal-kcal" },
          [eaten.length || goal ? `${round(kcal)}${goal ? ` / ${round(goal.kcal)}` : ""} kcal` : "",
            planned.length ? `+ ${round(plannedKcal)} geplant` : ""].filter(Boolean).join(" ")),
      ),
      goal ? el("p", { class: "hint" }, [["Protein", "protein_g"], ["KH", "carbs_g"], ["Fett", "fat_g"]]
        .map(([label, field]) => `${label} ${round(sumOf(field))} / ${round(goal[field])} g`).join(" · ")) : null,
      items.length ? el("ul", { class: "list" }, ...items) : null,
      el("div", { class: "meal-actions" }, ...buttons));
  });
  $("meals").replaceChildren(...sections);
}

async function consumePlanned(meal = null) {
  const body = { date: state.date, ...(meal ? { meal } : {}) };
  const { ok, data } = await api("POST", "/api/food-log/consume", body);
  if (!ok) {
    $("summary-msg").textContent = data.error;
    return;
  }
  await loadDay();
}

// ---------------------------------------------------------------- Suche

let searchTimer = null;
let searchSeq = 0;

function openSearch(meal, planned = false) {
  state.meal = meal;
  state.planned = planned;
  $("search-title").textContent = `${MEAL_NAMES[meal]} – ${planned ? "planen" : "hinzufügen"}`;
  $("search-input").value = "";
  openDialog("search-dialog");
  $("search-input").focus();
  runSearch("");
}

async function runSearch(query) {
  const seq = ++searchSeq;
  const { ok, data } = await api("GET", `/api/foods?q=${encodeURIComponent(query)}&limit=30`);
  if (seq !== searchSeq || !ok) return;
  $("search-hint").textContent = query ? "" : data.length ? "Zuletzt verwendet" : "Tippe, um zu suchen";
  const items = data.map((food) =>
    el("li", { onclick: () => openAmount(food) },
      el("span", { class: "name" }, food.name,
        el("span", { class: "sub" }, food.portion_label ? `1 ${food.portion_label} = ${round(food.portion_g)} g` : "")),
      el("span", { class: "kcal" }, `${round(food.kcal_100g)} kcal/100 g`)));
  if (query && !items.length) items.push(el("li", { class: "empty" }, "Nichts gefunden – „Eigenes“ anlegen?"));
  $("search-results").replaceChildren(...items);
}

// ---------------------------------------------------------------- Menge

function openAmount(food, entry = null) {
  state.amount = { food, entry };
  $("amount-title").textContent = food.name;
  $("amount-per100").textContent =
    `pro 100 g: ${round(food.kcal_100g)} kcal · P ${food.protein_100g} · KH ${food.carbs_100g} · F ${food.fat_100g}`;
  $("amount-save").textContent = entry ? "Speichern" : state.planned ? "Planen" : "Hinzufügen";
  $("amount-delete").hidden = !entry;
  $("amount-consume").hidden = !(entry && entry.status === "planned" && state.date <= today());
  $("amount-msg").textContent = "";
  $("portion-details").open = false;
  $("portion-name").value = food.portion_label || "";
  $("portion-grams").value = food.portion_g || "";
  const grams = entry ? entry.grams : food.portion_g || 100;
  setGrams(grams);
  renderPortionRow();
  openDialog("amount-dialog");
  $(food.portion_g ? "amount-count" : "amount-grams").focus();
}

function renderPortionRow() {
  const { food } = state.amount;
  $("portion-row").hidden = !food.portion_g;
  $("portion-label").textContent = food.portion_g ? `× ${food.portion_label} (${round(food.portion_g)} g)` : "";
}

function setGrams(grams) {
  const { food } = state.amount;
  $("amount-grams").value = round(grams * 10) / 10;
  if (food.portion_g) $("amount-count").value = round((grams / food.portion_g) * 100) / 100;
  updatePreview();
}

function updatePreview() {
  const { food } = state.amount;
  const factor = (Number($("amount-grams").value) || 0) / 100;
  $("amount-preview").textContent =
    `${round(food.kcal_100g * factor)} kcal · P ${round(food.protein_100g * factor)} g · ` +
    `KH ${round(food.carbs_100g * factor)} g · F ${round(food.fat_100g * factor)} g`;
}

async function saveAmount() {
  const { food, entry } = state.amount;
  const grams = Number($("amount-grams").value);
  const { ok, data } = entry
    ? await api("PATCH", `/api/food-log/${entry.id}`, { grams })
    : await api("POST", "/api/food-log", {
      date: state.date, meal: state.meal, food_id: food.id, grams, status: state.planned ? "planned" : "eaten",
    });
  if (!ok) {
    $("amount-msg").textContent = data.error;
    return;
  }
  closeDialog("amount-dialog");
  closeDialog("search-dialog");
  await loadDay();
}

async function deleteEntry(entry) {
  const { ok, data } = await api("DELETE", `/api/food-log/${entry.id}`);
  if (!ok) {
    $("amount-msg").textContent = data.error;
    return false;
  }
  await loadDay();
  return true;
}

async function savePortion() {
  const { food } = state.amount;
  const body = { portion_label: $("portion-name").value.trim() || null, portion_g: Number($("portion-grams").value) || null };
  const { ok, data } = await api("PATCH", `/api/foods/${food.id}`, body);
  if (!ok) {
    $("amount-msg").textContent = data.error;
    return;
  }
  Object.assign(food, data);
  $("portion-details").open = false;
  renderPortionRow();
  setGrams(Number($("amount-grams").value) || 0);
}

async function consumeEntry(entry) {
  const { ok, data } = await api("POST", `/api/food-log/${entry.id}/consume`);
  if (!ok) return data.error;
  await loadDay();
  return null;
}

async function openEntry(entry) {
  if (entry.food_id === null) {
    // Schnelleintraege haben keine Menge: nur uebernehmen (geplant) oder loeschen
    if (entry.status === "planned" && state.date <= today()
        && confirm(`„${entry.label}“ (${round(entry.kcal)} kcal) als gegessen übernehmen?`)) {
      await consumeEntry(entry);
    } else if (confirm(`„${entry.label}“ (${round(entry.kcal)} kcal) löschen?`)) {
      await deleteEntry(entry);
    }
    return;
  }
  state.meal = entry.meal;
  state.planned = entry.status === "planned";
  const { ok, data } = await api("GET", `/api/foods/${entry.food_id}`);
  if (!ok) {
    if (confirm(`„${entry.label}“ löschen?`)) await deleteEntry(entry);
    return;
  }
  openAmount(data, entry);
}

// ---------------------------------------------------------------- Schnelleintrag / eigenes Lebensmittel

function openQuick() {
  $("quick-form").reset();
  $("quick-msg").textContent = "";
  openDialog("quick-dialog");
}

async function submitQuick(event) {
  event.preventDefault();
  const form = Object.fromEntries(new FormData(event.target));
  const body = { date: state.date, meal: state.meal, label: form.label, status: state.planned ? "planned" : "eaten" };
  for (const key of ["kcal", "protein_g", "carbs_g", "fat_g"]) body[key] = Number(form[key]);
  const { ok, data } = await api("POST", "/api/food-log", body);
  if (!ok) {
    $("quick-msg").textContent = data.error;
    return;
  }
  closeDialog("quick-dialog");
  closeDialog("search-dialog");
  await loadDay();
}

function openCustom(prefill = {}) {
  const form = $("custom-form");
  form.reset();
  form.elements.name.value = prefill.name || $("search-input").value;
  form.elements.barcode.value = prefill.barcode || "";
  $("custom-msg").textContent = prefill.message || "";
  openDialog("custom-dialog");
}

async function submitCustom(event) {
  event.preventDefault();
  const form = Object.fromEntries(new FormData(event.target));
  const body = { name: form.name };
  for (const key of ["kcal_100g", "protein_100g", "carbs_100g", "fat_100g"]) body[key] = Number(form[key]);
  if (form.portion_label || form.portion_g) {
    body.portion_label = form.portion_label;
    body.portion_g = Number(form.portion_g) || null;
  }
  if (form.barcode) body.barcode = form.barcode;
  const { ok, data } = await api("POST", "/api/foods", body);
  if (!ok) {
    $("custom-msg").textContent = data.error;
    return;
  }
  closeDialog("custom-dialog");
  openAmount(data);
}

// ---------------------------------------------------------------- Vorlagen

async function openTemplates(meal) {
  state.meal = meal;
  state.planned = state.date > today(); // Zukunft: immer geplant; heute: per Haken
  $("template-title").textContent = `Vorlagen – ${MEAL_NAMES[meal]}${state.planned ? " (planen)" : ""}`;
  $("template-planned-label").hidden = state.date !== today();
  $("template-planned").checked = false;
  $("template-form").reset();
  $("template-msg").textContent = "";
  $("template-form").hidden = !state.day.meals[meal].some((e) => e.food_id !== null);
  openDialog("template-dialog");
  await renderTemplates();
}

async function renderTemplates() {
  const { ok, data } = await api("GET", "/api/meal-templates");
  if (!ok) return;
  const items = data.map((template) =>
    el("li", { onclick: () => applyTemplate(template) },
      el("span", { class: "name" }, template.name,
        el("span", { class: "sub" }, template.items.map((i) => i.name).join(", "))),
      el("span", { class: "kcal" }, `${round(template.kcal)} kcal`),
      el("button", {
        class: "icon-btn", "aria-label": "Vorlage löschen",
        onclick: (event) => { event.stopPropagation(); deleteTemplate(template); },
      }, "🗑")));
  if (!items.length) items.push(el("li", { class: "empty" }, "Noch keine Vorlagen"));
  $("template-list").replaceChildren(...items);
}

async function applyTemplate(template) {
  const { ok, data } = await api("POST", `/api/meal-templates/${template.id}/apply`, {
    date: state.date, meal: state.meal, status: state.planned || $("template-planned").checked ? "planned" : "eaten",
  });
  if (!ok) {
    $("template-msg").textContent = data.error;
    return;
  }
  closeDialog("template-dialog");
  await loadDay();
}

async function deleteTemplate(template) {
  if (!confirm(`Vorlage „${template.name}“ löschen?`)) return;
  await api("DELETE", `/api/meal-templates/${template.id}`);
  await renderTemplates();
}

async function submitTemplate(event) {
  event.preventDefault();
  const name = new FormData(event.target).get("name");
  const { ok, data } = await api("POST", "/api/meal-templates", { name, meal: state.meal, from_date: state.date });
  if (!ok) {
    $("template-msg").textContent = data.error;
    return;
  }
  event.target.reset();
  await renderTemplates();
}

// ---------------------------------------------------------------- Barcode

function loadZxing() {
  if (window.ZXingBrowser) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = el("script", { src: ZXING_URL });
    script.onload = resolve;
    script.onerror = () => reject(new Error("Scanner konnte nicht geladen werden"));
    document.head.append(script);
  });
}

async function openScan() {
  $("ean-form").reset();
  $("scan-msg").textContent = "";
  openDialog("scan-dialog");
  if (!window.isSecureContext || !navigator.mediaDevices) {
    $("scan-msg").textContent = "Kamera nur über HTTPS verfügbar – Ziffern eingeben.";
    $("scan-video").hidden = true;
    return;
  }
  $("scan-video").hidden = false;
  let nativeFailure = null;
  try {
    // Android/Chrome (Samsung): nativer Detector ist deutlich robuster als ZXing-JS.
    if ("BarcodeDetector" in window) {
      try {
        state.scanControls = await startNativeScan();
        return;
      } catch (error) { nativeFailure = error.message; /* schwarzes Bild o.ae.: weiter mit ZXing */ }
    }
    await loadZxing();
    // Nur Produkt-Barcodes, gruendlich suchen. DecodeHintType exportiert das UMD-Bundle nicht:
    // 2 = POSSIBLE_FORMATS, 3 = TRY_HARDER.
    const { EAN_13, EAN_8, UPC_A, UPC_E } = ZXingBrowser.BarcodeFormat;
    const hints = new Map([[2, [EAN_13, EAN_8, UPC_A, UPC_E]], [3, true]]);
    const reader = new ZXingBrowser.BrowserMultiFormatReader(hints);
    // Hohe Aufloesung: iPhones stellen erst ab ~20 cm scharf, bei 640x480 (Safari-Default)
    // sind die Striche aus dieser Distanz zu wenige Pixel breit.
    $("scan-msg").textContent = nativeFailure ? `Scanner: ZXing (nativ: ${nativeFailure})` : "Scanner: ZXing";
    state.scanControls = await reader.decodeFromConstraints(
      { video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } } },
      $("scan-video"),
      (result) => {
        if (result) {
          stopScan();
          lookupBarcode(result.getText());
        }
      });
  } catch (error) {
    $("scan-msg").textContent = `Kamera nicht verfügbar (${error.message}) – Ziffern eingeben.`;
    $("scan-video").hidden = true;
  }
}

async function startNativeScan() {
  const detector = new BarcodeDetector({ formats: ["ean_13", "ean_8", "upc_a", "upc_e"] });
  const video = $("scan-video");
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
  });
  const stopStream = () => stream.getTracks().forEach((t) => t.stop());
  video.srcObject = stream;
  try {
    await video.play();
    // Samsung liefert ohne Zusatz oft festen Fokus; Dauerfokus erst nach dem Start nachziehen (davor
    // blieb das Bild auf manchen Geraeten schwarz), falls unterstuetzt.
    const track = stream.getVideoTracks()[0];
    const caps = track.getCapabilities ? track.getCapabilities() : {};
    if (caps.focusMode && caps.focusMode.includes("continuous")) {
      await track.applyConstraints({ advanced: [{ focusMode: "continuous" }] }).catch(() => {});
    }
    // Kamerabild muss laufen, sonst auf ZXing ausweichen
    const before = video.currentTime;
    await new Promise((resolve) => setTimeout(resolve, 1500));
    if (video.videoWidth === 0 || video.currentTime === before) throw new Error("Kein Kamerabild");
  } catch (error) {
    stopStream();
    video.srcObject = null;
    throw error;
  }
  let active = true;
  let reported = false;
  const tick = async () => {
    if (!active) return;
    try {
      const codes = await detector.detect(video);
      if (!reported) {
        reported = true;
        $("scan-msg").textContent = "Scanner: nativ";
      }
      if (codes.length) {
        stopScan();
        lookupBarcode(codes[0].rawValue);
        return;
      }
    } catch (error) {
      // Frame noch nicht bereit; bleibt der Fehler bestehen, sieht man ihn im Dialog
      if (!reported) $("scan-msg").textContent = `Scanner: nativ, Fehler: ${error.message}`;
    }
    setTimeout(tick, 150);
  };
  tick();
  return {
    stop() {
      active = false;
      stopStream();
      video.srcObject = null;
    },
  };
}

function stopScan() {
  if (state.scanControls) state.scanControls.stop();
  state.scanControls = null;
}

async function lookupBarcode(ean) {
  $("scan-msg").textContent = "Suche…";
  const { ok, status, data } = await api("GET", `/api/foods/barcode/${encodeURIComponent(ean)}`);
  if (ok) {
    closeDialog("scan-dialog");
    openAmount(data);
    return;
  }
  if (status === 404) {
    closeDialog("scan-dialog");
    openCustom({
      name: data.name || "",
      barcode: ean,
      message: data.name ? "Nährwerte fehlen bei Open Food Facts – bitte von der Packung abtippen." : "Barcode unbekannt – bitte erfassen.",
    });
    return;
  }
  $("scan-msg").textContent = data.error || "Fehler bei der Suche";
}

// ---------------------------------------------------------------- Events

function bindEvents() {
  $("prev-day").addEventListener("click", () => shiftView(-1));
  $("next-day").addEventListener("click", () => shiftView(1));
  $("date-label").addEventListener("click", () => selectDay(today()));
  window.addEventListener("hashchange", () => { state.view = viewFromHash(); loadDay(); });

  $("search-input").addEventListener("input", (event) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => runSearch(event.target.value.trim()), 200);
  });
  $("open-scan").addEventListener("click", openScan);
  $("open-quick").addEventListener("click", openQuick);
  $("open-custom").addEventListener("click", () => openCustom());

  $("amount-count").addEventListener("input", (event) => {
    const { food } = state.amount;
    $("amount-grams").value = round((Number(event.target.value) || 0) * food.portion_g * 10) / 10;
    updatePreview();
  });
  $("amount-grams").addEventListener("input", () => setGramsFromInput());
  $("amount-save").addEventListener("click", saveAmount);
  $("amount-consume").addEventListener("click", async () => {
    const { entry } = state.amount;
    const grams = Number($("amount-grams").value);
    if (grams !== entry.grams) {
      const saved = await api("PATCH", `/api/food-log/${entry.id}`, { grams });
      if (!saved.ok) {
        $("amount-msg").textContent = saved.data.error;
        return;
      }
    }
    const error = await consumeEntry(entry);
    if (error) $("amount-msg").textContent = error;
    else closeDialog("amount-dialog");
  });
  $("amount-delete").addEventListener("click", async () => {
    if (await deleteEntry(state.amount.entry)) closeDialog("amount-dialog");
  });
  $("portion-save").addEventListener("click", savePortion);

  $("quick-form").addEventListener("submit", submitQuick);
  $("custom-form").addEventListener("submit", submitCustom);
  $("template-form").addEventListener("submit", submitTemplate);
  $("ean-form").addEventListener("submit", (event) => {
    event.preventDefault();
    stopScan();
    lookupBarcode(new FormData(event.target).get("ean"));
  });
  $("scan-dialog").addEventListener("close", stopScan);

  for (const button of document.querySelectorAll("[data-close]")) {
    button.addEventListener("click", () => button.closest("dialog").close());
  }
}

function setGramsFromInput() {
  const { food } = state.amount;
  const grams = Number($("amount-grams").value) || 0;
  if (food.portion_g) $("amount-count").value = round((grams / food.portion_g) * 100) / 100;
  updatePreview();
}

state.view = viewFromHash();
bindEvents();
loadDay().then(() => {
  // Einsprung von der Heute-Seite: ?add=<mahlzeit> oeffnet direkt die Suche
  const meal = new URLSearchParams(location.search).get("add");
  if (meal in MEAL_NAMES) openSearch(meal);
});
