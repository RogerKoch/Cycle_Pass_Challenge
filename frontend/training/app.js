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
const STATUS_ICONS = { planned: "", done: "✓", modified: "✎", skipped: "✗" };

const state = {
  date: localIso(new Date()),
  day: null,
  week: null,
  plan: null, // /api/plan/today, nur fuer heute
  swapMode: false,
  swapFirst: null, // im Tauschmodus der zuerst angetippte Tag
};

// Uebungsname -> {img, video}; fehlt die Datei, gibt es einfach keine Skizzen
const ILLUSTRATIONS = fetch("img/exercises/index.json")
  .then((response) => (response.ok ? response.json() : {}))
  .catch(() => ({}));

async function api(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  // relativ zur App-Wurzel aufloesen (Seite liegt unter <praefix>/training/)
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
  for (const child of children) if (child !== null && child !== undefined && child !== false) node.append(child);
  return node;
}

const round = (value) => Math.round(Number(value));
const today = () => localIso(new Date());

function fmtMinutes(minutes) {
  const m = round(minutes);
  return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")} h` : `${m} min`;
}

function fmtDate(iso, options = { weekday: "short", day: "numeric", month: "short" }) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("de-CH", options);
}

function range(low, high, unit) {
  if (low === null || low === undefined) return "–";
  return low === high || high === null ? `${low}${unit}` : `${low}–${high}${unit}`;
}

function openDialog(id) {
  const dialog = $(id);
  if (!dialog.open) dialog.showModal();
}

// ---------------------------------------------------------------- Laden

async function load() {
  const [day, week] = await Promise.all([
    api("GET", `/api/calendar/day/${state.date}`),
    api("GET", `/api/calendar/week/${state.date}`),
  ]);
  if (!day.ok || !week.ok) {
    $("page-msg").textContent = (day.data.error || week.data.error || "Laden fehlgeschlagen")
      + " – Profil im Dashboard anlegen.";
    return;
  }
  $("page-msg").textContent = "";
  state.illustrations = await ILLUSTRATIONS;
  state.day = day.data;
  state.week = week.data;
  state.plan = null;
  loadReviewBanner();
  if (state.date === today()) {
    const plan = await api("GET", "/api/plan/today");
    state.plan = plan.ok ? plan.data : { error: plan.data.error };
  }
  render();
}

function render() {
  const label = fmtDate(state.date);
  $("date-label").textContent = state.date === today() ? `Heute, ${label}` : label;
  renderDay();
  renderWeek();
}

async function loadReviewBanner() {
  const { ok, data } = await api("GET", "/api/review");
  const banner = $("review-banner");
  const count = ok ? data.findings.length : 0;
  banner.hidden = count === 0;
  if (!count) return;
  const urgent = data.findings.some((f) => f.severity === "alert");
  banner.className = urgent ? "card banner alert" : "card banner";
  banner.textContent = `${urgent ? "⚠ " : ""}${count} offene${count === 1 ? "r Hinweis" : " Hinweise"} im Check-in-Review →`;
}

// ---------------------------------------------------------------- Tag

function renderDay() {
  const day = state.day;
  const cards = [phaseLine(day)];
  if (!day.started) {
    cards.push(el("section", { class: "card" }, el("p", { class: "hint" }, "Vor dem Programmstart ist nichts geplant.")));
    $("day").replaceChildren(...cards);
    return;
  }
  for (const warning of day.warnings) cards.push(el("p", { class: "warning" }, `⚠ ${warning.message}`));
  if (day.note) cards.push(el("p", { class: "hint" }, `Notiz: ${day.note}`));
  if (!day.cycling && !day.strength) {
    cards.push(el("section", { class: "card" }, el("h2", {}, "Ruhetag"), el("p", { class: "card-sub" }, "Nur Mobility.")));
  }
  if (day.cycling) cards.push(cyclingCard(day.cycling));
  if (day.strength) cards.push(strengthCard(day.strength));
  cards.push(mobilityCard(day.mobility));
  cards.push(actionsCard(day));
  if (state.plan) cards.push(nutritionCard(state.plan));
  $("day").replaceChildren(...cards);
}

function phaseLine(day) {
  return el("div", { class: "phase-line" },
    el("span", { class: "badge" }, `${PHASE_NAMES[day.phase.phase_id] || day.phase.phase_id} · Woche ${day.phase.week_in_phase}`),
    day.phase.deload ? el("span", { class: "badge warn" }, "Erholungswoche") : null,
    day.status !== "planned" ? el("span", { class: "badge muted" }, STATUS_NAMES[day.status]) : null);
}

function cyclingCard(cycling) {
  const rows = cycling.segments.map((s) => {
    const work = s.pct_ftp_low !== null && s.pct_ftp_low >= 76;
    const target = s.watts_low !== null
      ? el("span", {}, range(s.watts_low, s.watts_high, " W"), el("span", { class: "sub" }, range(s.pct_ftp_low, s.pct_ftp_high, " %")))
      : range(s.pct_ftp_low, s.pct_ftp_high, " % FTP");
    return el("tr", { class: work ? "work" : "" },
      el("td", {}, s.label, s.cadence_rpm ? el("span", { class: "sub" }, `${s.cadence_rpm} rpm`) : null),
      el("td", { class: "num" }, fmtMinutes(s.minutes)),
      el("td", { class: "num" }, target));
  });
  return el("section", { class: "card" },
    el("h2", {}, `🚴 ${cycling.title}`),
    el("p", { class: "card-sub" }, `${fmtMinutes(cycling.minutes)}${cycling.adjusted ? " · angepasst" : ""}${cycling.ftp_watts ? ` · FTP ${cycling.ftp_watts} W` : ""}`),
    cycling.message ? el("p", { class: "warning" }, cycling.message) : null,
    el("table", { class: "segments" }, el("tbody", {}, ...rows)),
    cycling.note ? el("p", { class: "hint" }, cycling.note) : null,
    cycling.zwift_hint ? el("p", { class: "hint" }, `Zwift: ${cycling.zwift_hint}`) : null);
}

function strengthCard(strength) {
  const phase = strength.phase;
  const items = strength.exercises.map((e) => el("li", {},
    el("span", { class: "dose" }, `${e.sets} × ${e.reps}`),
    e.name,
    e.rest || e.note ? el("span", { class: "sub" }, [e.rest ? `Pause ${e.rest}` : null, e.note].filter(Boolean).join(" · ")) : null,
    illustration(e.name)));
  return el("section", { class: "card" },
    el("h2", {}, `💪 ${strength.title}`),
    el("p", { class: "card-sub" },
      `${strength.duration_minutes} min · Phase ${phase.number}: ${phase.title} · Tempo ${phase.tempo}`),
    strength.note ? el("p", { class: "warning" }, strength.note) : null,
    el("ul", { class: "exercises" }, ...items));
}

function mobilityCard(mobility) {
  return el("section", { class: "card" },
    el("details", {},
      el("summary", {}, "🧘 Mobility (5–10 min, nach dem Fahren)"),
      el("ul", { class: "exercises" }, ...mobility.map((e) => el("li", {},
        el("span", { class: "dose" }, `${e.sets} × ${e.reps}`), e.name,
        e.note ? el("span", { class: "sub" }, e.note) : null,
        illustration(e.name))))));
}

function illustration(name) {
  const entry = (state.illustrations || {})[name];
  if (!entry) return null;
  const video = `https://www.youtube.com/results?search_query=${encodeURIComponent(entry.video)}`;
  return el("details", { class: "illus" },
    el("summary", {}, "Skizze & Video"),
    el("img", { src: `img/exercises/${entry.img}`, alt: name, loading: "lazy" }),
    el("a", { href: video, target: "_blank", rel: "noopener" }, "▶ Video-Suche auf YouTube"));
}

function actionsCard(day) {
  const isPast = day.date < today();
  const isFuture = day.date > today();
  const buttons = [];
  if (day.status === "planned") {
    if (!isPast) buttons.push(el("button", { onclick: openPlan }, "Anpassen"));
    if (!isFuture) {
      buttons.push(el("button", { class: "primary", onclick: () => setStatus({ status: "done" }) }, "✓ Erledigt"));
      buttons.push(el("button", { onclick: openModified }, "✎ Angepasst"));
    }
    buttons.push(el("button", { class: "danger", onclick: () => openDialog("cancel-dialog") }, isFuture ? "Absagen" : "✗ Ausgefallen"));
  } else {
    buttons.push(el("button", { onclick: () => setStatus({ status: "planned" }) },
      day.status === "skipped" ? "Absage aufheben" : "Rückmeldung zurücksetzen"));
  }
  const reschedule = day.reschedule_options.map((iso) =>
    el("button", { onclick: () => swap(day.date, iso) }, `Auf ${fmtDate(iso, { weekday: "short" })} verschieben`));
  return el("section", { class: "card" },
    el("div", { class: "actions-row" }, ...buttons),
    reschedule.length ? el("p", { class: "hint" }, "Schlüsseleinheit nachholen:") : null,
    reschedule.length ? el("div", { class: "actions-row" }, ...reschedule) : null,
    el("p", { class: "msg", id: "action-msg" }));
}

function nutritionCard(plan) {
  if (plan.error) {
    return el("section", { class: "card" }, el("h2", {}, "🍽 Ernährung"), el("p", { class: "hint" }, `Nicht verfügbar: ${plan.error}`));
  }
  const m = plan.macros;
  const meals = plan.meals.map((meal) => el("tr", {},
    el("td", {}, meal.label, el("span", { class: "sub" }, meal.hint)),
    el("td", { class: "num" }, `${round(meal.kcal)} kcal`, el("span", { class: "sub" }, `${round(meal.protein_g)} g P`))));
  const fueling = plan.fueling && plan.fueling.carbs_g_per_hour_max > 0
    ? `Während der Fahrt: ${round(plan.fueling.carbs_g_per_hour_min)}–${round(plan.fueling.carbs_g_per_hour_max)} g KH/h `
      + `(gesamt ${round(plan.fueling.carbs_g_total_min)}–${round(plan.fueling.carbs_g_total_max)} g). ${plan.fueling.note}`
    : plan.fueling ? `Während der Fahrt: ${plan.fueling.note}` : null;
  return el("section", { class: "card" },
    el("h2", {}, `🍽 Ernährung: ${round(plan.nutrition.target_kcal)} kcal`),
    el("p", { class: "card-sub" }, `Protein ${round(m.protein_g)} g · KH ${round(m.carbs_g)} g · Fett ${round(m.fat_g)} g`),
    el("table", { class: "meals" }, el("tbody", {}, ...meals)),
    fueling ? el("p", { class: "hint" }, fueling) : null,
    ...plan.timing_hints.map((hint) => el("p", { class: "hint" }, hint)),
    el("p", { class: "hint" }, el("a", { href: "../ernaehrung/" }, "Zum Ernährungs-Tagebuch →")));
}

// ---------------------------------------------------------------- Aktionen

async function setStatus(body) {
  const { ok, data } = await api("PATCH", `/api/calendar/day/${state.date}`, body);
  if (!ok) {
    $("action-msg").textContent = data.error;
    return false;
  }
  await load();
  return true;
}

function openPlan() {
  const day = state.day;
  const select = $("plan-slot");
  select.replaceChildren(
    el("option", { value: "" }, "kein Rad"),
    ...day.slot_options.map((o) => el("option", { value: o.slot }, `${o.title} (${fmtMinutes(o.minutes)})`)));
  select.value = day.cycling ? day.cycling.slot : "";
  const form = $("plan-form");
  form.elements.planned_minutes.value = day.cycling && day.cycling.adjustable ? round(day.cycling.minutes) : "";
  form.elements.strength_session.value = day.strength ? day.strength.session_id : "";
  updateMinutesField();
  $("plan-msg").textContent = "";
  openDialog("plan-dialog");
}

function updateMinutesField() {
  const option = state.day.slot_options.find((o) => o.slot === $("plan-slot").value);
  const adjustable = Boolean(option && option.adjustable);
  $("plan-minutes-label").hidden = !adjustable;
  if (!adjustable) $("plan-form").elements.planned_minutes.value = "";
}

async function submitPlan(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const slot = form.get("cycling_slot") || null;
  const minutes = form.get("planned_minutes");
  const option = state.day.slot_options.find((o) => o.slot === slot);
  const body = {
    cycling_slot: slot,
    strength_session: form.get("strength_session") || null,
    // Standarddauer der Einheit nicht als Override speichern
    planned_minutes: minutes && option && option.adjustable && Number(minutes) !== round(option.minutes) ? Number(minutes) : null,
  };
  const { ok, data } = await api("PUT", `/api/calendar/day/${state.date}/plan`, body);
  if (!ok) {
    $("plan-msg").textContent = data.error;
    return;
  }
  $("plan-dialog").close();
  await load();
}

function openModified() {
  const form = $("modified-form");
  const cycling = state.day.cycling;
  form.elements.actual_minutes.value = cycling ? round(cycling.minutes) : 0;
  form.elements.actual_intensity.value = cycling ? cycling.intensity : "moderat_base";
  form.elements.actual_strength_done.checked = Boolean(state.day.strength);
  $("modified-msg").textContent = "";
  openDialog("modified-dialog");
}

async function submitModified(event) {
  event.preventDefault();
  const form = event.target;
  const { ok, data } = await api("PATCH", `/api/calendar/day/${state.date}`, {
    status: "modified",
    actual_minutes: Number(form.elements.actual_minutes.value),
    actual_intensity: form.elements.actual_intensity.value,
    actual_strength_done: form.elements.actual_strength_done.checked,
  });
  if (!ok) {
    $("modified-msg").textContent = data.error;
    return;
  }
  $("modified-dialog").close();
  await load();
}

async function submitCancel(event) {
  event.preventDefault();
  const note = new FormData(event.target).get("note").trim();
  const { ok, data } = await api("PATCH", `/api/calendar/day/${state.date}`, { status: "skipped", note: note || null });
  if (!ok) {
    $("cancel-msg").textContent = data.error;
    return;
  }
  event.target.reset();
  $("cancel-dialog").close();
  await load();
}

async function swap(dateA, dateB) {
  const { ok, data } = await api("POST", "/api/calendar/swap", { date_a: dateA, date_b: dateB });
  if (!ok) {
    $("week-msg").textContent = data.error;
    const actionMsg = $("action-msg");
    if (actionMsg) actionMsg.textContent = data.error;
    return;
  }
  $("week-msg").textContent = "";
  await load();
}

// ---------------------------------------------------------------- Woche

function renderWeek() {
  $("swap-toggle").textContent = state.swapMode ? "Abbrechen" : "Tauschen";
  $("swap-hint").hidden = !state.swapMode;
  const items = state.week.days.map((d) => {
    const parts = [];
    if (d.cycling) parts.push(`🚴 ${d.cycling.title} · ${fmtMinutes(d.cycling.minutes)}`);
    if (d.strength) parts.push(`💪 Kraft ${d.strength.session_id}`);
    const classes = [
      d.date === today() ? "today" : "",
      d.status === "skipped" ? "skipped" : "",
      d.date === state.swapFirst ? "selected" : "",
    ].join(" ");
    return el("li", { class: classes, onclick: () => onWeekDay(d.date) },
      el("span", { class: "day-tag" }, fmtDate(d.date, { weekday: "short", day: "numeric" })),
      el("span", { class: "name" }, parts.length ? parts.join(" · ") : (d.started ? "Ruhetag" : "–"),
        d.warnings.length ? el("span", { class: "sub" }, `⚠ ${d.warnings[0].message}`) : null),
      el("span", { class: "kcal" }, STATUS_ICONS[d.status]));
  });
  $("week-list").replaceChildren(...items);
}

async function onWeekDay(iso) {
  if (!state.swapMode) {
    state.date = iso;
    await load();
    return;
  }
  if (state.swapFirst === null) {
    state.swapFirst = iso;
    renderWeek();
    return;
  }
  const first = state.swapFirst;
  state.swapFirst = null;
  state.swapMode = false;
  if (first === iso) {
    renderWeek();
    return;
  }
  await swap(first, iso);
  renderWeek();
}

async function resetWeek() {
  if (!confirm("Alle heutigen und künftigen, nicht erledigten Tage dieser Woche auf den Standard zurücksetzen?")) return;
  const { ok, data } = await api("POST", `/api/calendar/week/${state.date}/reset`);
  if (!ok) {
    $("week-msg").textContent = data.error;
    return;
  }
  await load();
}

function bindEvents() {
  $("prev-day").addEventListener("click", () => { state.date = shiftDate(state.date, -1); load(); });
  $("next-day").addEventListener("click", () => { state.date = shiftDate(state.date, 1); load(); });
  $("date-label").addEventListener("click", () => { state.date = today(); load(); });
  $("swap-toggle").addEventListener("click", () => {
    state.swapMode = !state.swapMode;
    state.swapFirst = null;
    $("week-msg").textContent = "";
    renderWeek();
  });
  $("week-reset").addEventListener("click", resetWeek);
  $("plan-slot").addEventListener("change", updateMinutesField);
  $("plan-form").addEventListener("submit", submitPlan);
  $("modified-form").addEventListener("submit", submitModified);
  $("cancel-form").addEventListener("submit", submitCancel);
  for (const button of document.querySelectorAll("[data-close]")) {
    button.addEventListener("click", () => button.closest("dialog").close());
  }
}

bindEvents();
load();
