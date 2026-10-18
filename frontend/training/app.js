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
const EVENT_PHASE_NAMES = { taper: "Taper", load: "Carb-Loading", event: "Eventtag", recovery: "Recovery" };

const state = {
  date: localIso(new Date()),
  day: null,
  week: null,
  month: null, // /api/calendar/month, nur in der Monatsansicht
  view: "tag", // tag | woche | monat
  events: [], // kommende Events
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
  const [day, week, month] = await Promise.all([
    api("GET", `/api/calendar/day/${state.date}`),
    api("GET", `/api/calendar/week/${state.date}`),
    state.view === "monat" ? api("GET", `/api/calendar/month/${state.date.slice(0, 7)}`) : null,
  ]);
  if (!day.ok || !week.ok) {
    $("page-msg").textContent = (day.data.error || week.data.error || "Laden fehlgeschlagen")
      + " – Profil unter Profil anlegen.";
    return;
  }
  $("page-msg").textContent = "";
  state.illustrations = await ILLUSTRATIONS;
  state.day = day.data;
  state.week = week.data;
  state.month = month && month.ok ? month.data : null;
  loadReviewBanner();
  const events = await api("GET", "/api/events");
  state.events = events.ok ? events.data : [];
  render();
}

function render() {
  $("date-label").textContent = viewLabel();
  applyView();
  renderDay();
  renderWeek();
  renderMonth();
  renderEvents();
}

// ---------------------------------------------------------------- Ansichten (Tag/Woche/Monat)

const VIEWS = ["tag", "woche", "monat"];

function viewFromHash() {
  const hash = location.hash.slice(1);
  if (VIEWS.includes(hash)) return hash;
  return window.matchMedia("(min-width: 900px)").matches ? "monat" : "tag";
}

function isoWeek(iso) {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7)); // Donnerstag der Woche
  const firstThursday = new Date(date.getFullYear(), 0, 4);
  return 1 + Math.round(((date - firstThursday) / 86400000 - 3 + ((firstThursday.getDay() + 6) % 7)) / 7);
}

function viewLabel() {
  if (state.view === "monat") {
    return new Date(`${state.date}T12:00:00`).toLocaleDateString("de-CH", { month: "long", year: "numeric" });
  }
  if (state.view === "woche") {
    const days = state.week ? state.week.days : null;
    const range = days ? `${fmtDate(days[0].date, { day: "numeric", month: "short" })}–${fmtDate(days[6].date, { day: "numeric", month: "short" })}` : "";
    return `KW ${isoWeek(state.date)}${range ? ` · ${range}` : ""}`;
  }
  const label = fmtDate(state.date);
  return state.date === today() ? `Heute, ${label}` : label;
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
  return load();
}

// Zustand eines Tages fuer Kalenderzelle und Wochenliste: gemacht / abweichend / geplant / nicht erfasst / abgesagt
function dayState(d) {
  if (!d.started || (!d.cycling && !d.strength && !hasImportedTraining(d) && d.status === "planned")) {
    return { cls: d.started ? "rest" : "", icon: "" };
  }
  if (d.status === "skipped") return { cls: "skipped", icon: STATUS_ICONS.skipped };
  if (d.status === "modified") return { cls: "modified", icon: STATUS_ICONS.modified };
  if (d.status === "done" || hasImportedTraining(d)) return { cls: "done", icon: STATUS_ICONS.done };
  return d.date < today() ? { cls: "open", icon: "…" } : { cls: "planned", icon: "" };
}

function cellText(d) {
  const parts = [];
  if (d.event) parts.push(`🏁 ${d.event.label}`);
  if (d.cycling) parts.push(`🚴 ${round(d.cycling.minutes)}'`);
  if (d.strength) parts.push(`💪 ${d.strength.session_id}`);
  return parts;
}

function renderMonth() {
  if (state.view !== "monat" || !state.month) return;
  const month = state.date.slice(0, 7);
  const head = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"].map((name) => el("div", { class: "dh" }, name));
  const cells = state.month.weeks.flatMap((week) => week.days).map((d) => {
    const ds = dayState(d);
    const classes = ["cell", ds.cls, d.date.startsWith(month) ? "" : "out", d.date === today() ? "today" : "",
      d.date === state.date ? "sel" : ""].join(" ");
    const parts = cellText(d);
    const title = [fmtDate(d.date, { weekday: "long", day: "numeric", month: "long" }), ...parts, ds.icon].filter(Boolean).join(" · ");
    return el("button", { class: classes, type: "button", title, "aria-label": title, onclick: () => onMonthDay(d.date) },
      el("span", { class: "num" }, String(Number(d.date.slice(8)))),
      // Symbole nebeneinander (umbrechen bei wenig Platz), Status-Haken eigene Zeile
      parts.length ? el("span", { class: "line parts" }, ...parts.map((text) => el("span", {}, text))) : null,
      ds.icon ? el("span", { class: "line" }, ds.icon) : null);
  });
  $("month-grid").replaceChildren(...head, ...cells);
}

async function onMonthDay(iso) {
  state.date = iso;
  await load();
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
  stopActiveTimer();
  const day = state.day;
  const cards = [phaseLine(day)];
  if (!day.started) {
    cards.push(el("section", { class: "card" }, el("p", { class: "hint" }, "Vor dem Programmstart ist nichts geplant.")));
    $("day").replaceChildren(...cards);
    return;
  }
  if (day.event) cards.push(eventCard(day.event));
  for (const warning of day.warnings) cards.push(el("p", { class: "warning" }, `⚠ ${warning.message}`));
  if (day.note) cards.push(el("p", { class: "hint" }, `Notiz: ${day.note}`));
  if (day.imported.length) cards.push(importedCard(day.imported));
  if (!day.cycling && !day.strength) {
    const running = day.sport === "running";
    cards.push(el("section", { class: "card" }, el("h2", {}, running ? "Kein Plan" : "Ruhetag"),
      el("p", { class: "card-sub" }, running ? "Lauf über „Angepasst“ erfassen oder per intervals.icu importieren." : "Nur Mobility.")));
  }
  if (day.cycling) cards.push(cyclingCard(day.cycling));
  if (day.strength) cards.push(strengthCard(day.strength));
  cards.push(mobilityCard(day.mobility));
  cards.push(actionsCard(day));
  const comment = el("section", { class: "card day-comment" });
  mountDayComment(comment, { base: "../", date: state.date });
  cards.push(comment);
  $("day").replaceChildren(...cards);
}

function eventCard(event) {
  const phase = EVENT_PHASE_NAMES[event.phase] || event.phase;
  const upcoming = state.events.find((e) => e.name === event.name && e.event_date === event.event_date);
  return el("section", { class: "card banner" },
    el("h2", {}, `🏁 ${event.name} · ${event.label}`),
    el("p", { class: "card-sub" }, `${phase} · Priorität ${event.priority} · ${fmtDate(event.event_date)} `, infoLink("events")),
    upcoming ? el("button", { onclick: () => openEventPrep(upcoming) }, "Countdown anzeigen") : null);
}

function phaseLine(day) {
  return el("div", { class: "phase-line" },
    el("span", { class: "badge" }, `${PHASE_NAMES[day.phase.phase_id] || day.phase.phase_id} · Woche ${day.phase.week_in_phase}`),
    infoLink("phasen"),
    day.phase.deload ? el("span", { class: "badge warn" }, "Erholungswoche") : null,
    hasImportedTraining(day)
      ? el("span", { class: "badge" }, "erledigt (Garmin)")
      : day.status !== "planned" ? el("span", { class: "badge muted" }, STATUS_NAMES[day.status]) : null);
}

// ⓘ-Link auf einen Abschnitt der Erklaer-Seite
const infoLink = (anchor) => el("a", { class: "info", href: `../hilfe/#${anchor}`, "aria-label": "Erklärung" }, "ⓘ");

const hasImportedTraining = (day) => day.imported.some((a) => a.is_ride || a.is_run || a.is_strength);

// Blendet die Aktivitaet nur in dieser App aus (intervals.icu/Garmin bleiben unveraendert)
async function removeImported(activity) {
  const label = activity.name || activity.type;
  if (!confirm(`„${label}“ aus der App entfernen? In intervals.icu/Garmin bleibt sie bestehen.`)) return;
  const { ok, data } = await api("DELETE", `/api/intervals/activities/${encodeURIComponent(activity.icu_id)}`);
  if (!ok) $("page-msg").textContent = data.error || "Entfernen fehlgeschlagen";
  else await load();
}

function importedCard(activities) {
  const items = activities.map((a) => {
    const facts = [
      a.minutes ? fmtMinutes(a.minutes) : null,
      a.kilojoules ? `${round(a.kilojoules)} kJ` : a.kcal ? `${round(a.kcal)} kcal` : null,
      a.weighted_watts ? `NP ${round(a.weighted_watts)} W` : a.avg_watts ? `Ø ${round(a.avg_watts)} W` : null,
      a.avg_hr ? `Ø ${round(a.avg_hr)} bpm` : null,
      a.training_load ? `Load ${round(a.training_load)}` : null,
    ].filter(Boolean).join(" · ");
    const remove = el("button", { type: "button", onclick: () => removeImported(a) }, "Entfernen");
    return el("li", {}, `${a.is_ride ? "🚴" : a.is_run ? "🏃" : a.is_strength ? "💪" : "•"} ${a.name || a.type}`,
      el("span", { class: "sub" }, facts), remove);
  });
  return el("section", { class: "card" },
    el("h2", {}, "⌚ Garmin-Ist"),
    el("p", { class: "card-sub" }, "Aus intervals.icu – zählt für Ernährung und Review vor der manuellen Rückmeldung."),
    el("ul", { class: "exercises" }, ...items));
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
    el("p", { class: "card-sub" }, `${fmtMinutes(cycling.minutes)}${cycling.adjusted ? " · angepasst" : ""}${cycling.ftp_watts ? ` · FTP ${cycling.ftp_watts} W` : ""} `,
      infoLink("zonentabelle")),
    cycling.message ? el("p", { class: "warning" }, cycling.message) : null,
    el("table", { class: "segments" }, el("tbody", {}, ...rows)),
    cycling.note ? el("p", { class: "hint" }, cycling.note) : null,
    cycling.zwift_hint ? el("p", { class: "hint" }, `Zwift: ${cycling.zwift_hint}`) : null,
    el("p", { class: "hint" }, el("a", { href: `../api/calendar/day/${state.date}/zwo`, download: "" }, "⬇ Zwift-Workout (.zwo)"),
      " · wird automatisch über intervals.icu an Zwift geschickt ", infoLink("zwift")));
}

function strengthCard(strength) {
  const phase = strength.phase;
  const items = strength.exercises.map((e) => el("li", {},
    el("span", { class: "dose" }, `${e.sets} × ${e.reps}`),
    e.name,
    e.rest || e.note ? el("span", { class: "sub" }, [e.rest ? `Pause ${e.rest}` : null, e.note].filter(Boolean).join(" · ")) : null,
    e.original ? el("span", { class: "sub" }, `Getauscht gegen: ${e.original}`) : null,
    timerButton(e.reps),
    swapControl(e),
    illustration(e.name, strength.session_id)));
  return el("section", { class: "card" },
    el("h2", {}, `💪 ${strength.title}`),
    el("p", { class: "card-sub" },
      `${strength.duration_minutes} min · Phase ${phase.number}: ${phase.title} · Tempo ${phase.tempo} `,
      infoLink("kraftphasen")),
    strength.note ? el("p", { class: "warning" }, strength.note) : null,
    el("ul", { class: "exercises" }, ...items));
}

// ---------------------------------------------------------------- Timer

// "20–40 s" / "8 min" am Anfang der Reps -> Sekunden (obere Grenze). Steht die Zeit nicht vorn
// ("6–8 je Seite, 3–5 s halten"), ist sie nur Haltedauer pro Wiederholung -> kein Timer.
function parseDuration(reps) {
  const match = /^(\d+)(?:–(\d+))?\s*(s|min)\b/.exec(reps || "");
  if (!match) return null;
  return Number(match[2] || match[1]) * (match[3] === "min" ? 60 : 1);
}

function formatClock(seconds) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

let stopActiveTimer = () => {};

function beep() {
  try {
    const context = new AudioContext();
    const oscillator = context.createOscillator();
    oscillator.connect(context.destination);
    oscillator.frequency.value = 880;
    oscillator.start();
    oscillator.stop(context.currentTime + 0.4);
  } catch {
    // kein Ton verfuegbar: Vibration/Anzeige genuegen
  }
  if (navigator.vibrate) navigator.vibrate([300, 150, 300]);
}

// Countdown-Button fuer Uebungen mit Zeitangabe; Klick startet, nochmaliger Klick setzt zurueck
function timerButton(reps) {
  const seconds = parseDuration(reps);
  if (!seconds) return null;
  const button = el("button", { type: "button", class: "timer" }, `⏱ ${formatClock(seconds)}`);
  let handle = null;
  let wakeLock = null;
  const reset = () => {
    clearInterval(handle);
    handle = null;
    button.textContent = `⏱ ${formatClock(seconds)}`;
    button.classList.remove("running");
    if (wakeLock) wakeLock.release().catch(() => {});
    wakeLock = null;
  };
  button.addEventListener("click", async () => {
    if (handle) return reset();
    stopActiveTimer();
    stopActiveTimer = reset;
    let remaining = seconds;
    button.classList.add("running");
    button.textContent = `⏱ ${formatClock(remaining)}`;
    handle = setInterval(() => {
      remaining -= 1;
      if (remaining > 0) {
        button.textContent = `⏱ ${formatClock(remaining)}`;
        return;
      }
      reset();
      beep();
    }, 1000);
    try {
      wakeLock = await navigator.wakeLock.request("screen");
    } catch {
      // Wake-Lock nicht unterstuetzt oder abgelehnt: Timer laeuft trotzdem
    }
  });
  return button;
}

// Tausch gilt dauerhaft, bis er hier wieder geaendert wird (Material fehlt, Alternative waehlen)
function swapControl(exercise) {
  if (!exercise.alternatives || !exercise.alternatives.length) return null;
  const original = exercise.original || exercise.name;
  const choose = async (alternative) => {
    const { ok, data } = alternative === null
      ? await api("DELETE", "/api/exercises/swap", { original })
      : await api("PUT", "/api/exercises/swap", { original, alternative });
    if (!ok) $("page-msg").textContent = data.error || "Tauschen fehlgeschlagen";
    else await load();
  };
  const options = [original, ...exercise.alternatives].filter((name) => name !== exercise.name);
  return el("details", { class: "swap" },
    el("summary", {}, "Übung tauschen"),
    ...options.map((name) => el("button", { type: "button", onclick: () => choose(name === original ? null : name) },
      name === original ? `Zurück zu ${name}` : name)));
}

function mobilityCard(mobility) {
  return el("section", { class: "card" },
    el("details", {},
      el("summary", {}, "🧘 Mobility (5–10 min, zum Abschluss)"),
      el("ul", { class: "exercises" }, ...mobility.map((e) => el("li", {},
        el("span", { class: "dose" }, `${e.sets} × ${e.reps}`), e.name,
        e.note ? el("span", { class: "sub" }, e.note) : null,
        timerButton(e.reps),
        illustration(e.name))))));
}

// sessionId: Bloecke wie "Aufwärmen/Mobility" bestehen je Krafteinheit aus anderen Teiluebungen
function illustration(name, sessionId) {
  const illustrations = state.illustrations || {};
  const entry = illustrations[name];
  if (!entry) return null;
  if (!entry.parts) {
    return el("details", { class: "illus" }, el("summary", {}, "Skizze & Video"), ...illustrationContent(name, entry));
  }
  const parts = (entry.parts[sessionId] || []).filter((part) => illustrations[part]);
  if (!parts.length) return null;
  return el("details", { class: "illus" },
    el("summary", {}, "Skizzen & Video"),
    ...parts.flatMap((part) => [el("h4", {}, part), ...illustrationContent(part, illustrations[part])]));
}

function illustrationContent(name, entry) {
  const video = `https://www.youtube.com/results?search_query=${encodeURIComponent(entry.video)}`;
  return [
    el("img", { src: `img/exercises/${entry.img}`, alt: name, loading: "lazy" }),
    el("a", { href: video, target: "_blank", rel: "noopener" }, "▶ Video-Suche auf YouTube"),
  ];
}

function actionsCard(day) {
  const isPast = day.date < today();
  const isFuture = day.date > today();
  const buttons = [];
  if (hasImportedTraining(day)) {
    if (!isPast && day.status === "planned") buttons.push(el("button", { onclick: openPlan }, "Anpassen"));
  } else if (day.status === "planned") {
    if (!isPast) buttons.push(el("button", { onclick: openPlan }, "Anpassen"));
    if (!isFuture) {
      buttons.push(el("button", { class: "primary", onclick: () => setStatus({ status: "done" }) }, "✓ Erledigt"));
      buttons.push(el("button", { onclick: openModified }, day.sport === "running" ? "✎ Lauf erfassen" : "✎ Angepasst"));
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
  const running = state.day.sport === "running";
  $("modified-title").textContent = running ? "Training erfassen" : "Angepasst gefahren";
  $("modified-minutes-label").textContent = running ? "Minuten Lauf" : "Minuten Rad";
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
    if (d.event) parts.push(`🏁 ${d.event.label}`);
    if (d.cycling) parts.push(`🚴 ${d.cycling.title} · ${fmtMinutes(d.cycling.minutes)}`);
    if (d.strength) parts.push(`💪 Kraft ${d.strength.session_id}`);
    const ds = dayState(d);
    const classes = [
      d.date === today() ? "today" : "",
      ds.cls,
      d.date === state.date ? "current" : "",
      d.date === state.swapFirst ? "selected" : "",
    ].join(" ");
    return el("li", { class: classes, onclick: () => onWeekDay(d.date) },
      el("span", { class: "day-tag" }, fmtDate(d.date, { weekday: "short", day: "numeric" })),
      el("span", { class: "name", title: [...parts, ds.icon].filter(Boolean).join(" · ") },
        el("span", { class: "full" }, parts.length ? parts.join(" · ") : (d.started ? "Ruhetag" : "–"),
          d.warnings.length ? el("span", { class: "sub" }, `⚠ ${d.warnings[0].message}`) : null),
        // Desktop-Wochenleiste: nur Symbole wie im Monat (Details im Tooltip und im Tag)
        el("span", { class: "compact" },
          ...cellText(d).map((text) => el("span", { class: "line" }, text)),
          d.warnings.length ? el("span", { class: "line" }, "⚠") : null)),
      el("span", { class: "kcal" }, ds.icon));
  });
  $("week-list").replaceChildren(...items);
}

// ---------------------------------------------------------------- Events

function renderEvents() {
  const items = state.events.map((e) => el("li", { onclick: () => openEventPrep(e) },
    el("span", { class: "day-tag" }, fmtDate(e.event_date, { day: "numeric", month: "short" })),
    el("span", { class: "name" }, `${e.priority} · ${e.name}`,
      el("span", { class: "sub" }, `${fmtMinutes(e.expected_minutes)} · ${e.kind === "rennen" ? "Rennen" : "Tour"}`)),
    el("span", { class: "kcal" }, "›")));
  $("event-list").replaceChildren(...(items.length ? items : [el("li", {}, el("span", { class: "name" }, "Keine kommenden Events."))]));
}

function openEventDialog() {
  const form = $("event-form");
  form.reset();
  form.elements.event_date.value = state.date;
  $("event-msg").textContent = "";
  openDialog("event-dialog");
}

async function submitEvent(submitEvt) {
  submitEvt.preventDefault();
  const form = new FormData(submitEvt.target);
  const body = {
    name: form.get("name"),
    event_date: form.get("event_date"),
    expected_minutes: Number(form.get("expected_minutes")),
    priority: form.get("priority"),
    kind: form.get("kind"),
  };
  const { ok, data } = await api("POST", "/api/events", body);
  if (!ok) {
    $("event-msg").textContent = data.error;
    return;
  }
  $("event-dialog").close();
  await load();
}

async function openEventPrep(event) {
  $("event-prep-title").textContent = `${event.name} · ${fmtDate(event.event_date)}`;
  const { ok, data } = await api("GET", `/api/events/${event.id}/prep`);
  const body = $("event-prep-body");
  if (!ok) {
    body.replaceChildren(el("p", { class: "warning" }, data.error || "Laden fehlgeschlagen"));
    openDialog("event-prep-dialog");
    return;
  }
  const rows = data.days.map((d) => el("li", {},
    el("span", { class: "day-tag" }, `${d.label} · ${fmtDate(d.date, { weekday: "short", day: "numeric" })}`),
    el("span", { class: "name" },
      [EVENT_PHASE_NAMES[d.phase],
        d.volume_pct !== null ? `Volumen ${d.volume_pct} %` : null,
        d.carbs_g ? `KH ${d.carbs_g} g (${d.carbs_g_per_kg} g/kg)` : null,
        d.deficit_factor < 1 ? (d.deficit_factor === 0 ? "kein Defizit" : "halbes Defizit") : null,
        d.strength_blocked ? "keine Kraft" : null].filter(Boolean).join(" · "),
      ...d.hints.map((hint) => el("span", { class: "sub" }, hint)))));
  body.replaceChildren(
    el("ul", { class: "list" }, ...rows),
    el("p", { class: "hint" }, `KH-Mengen für ${data.weight_kg} kg (letzter Check-in).`),
    el("button", { class: "danger", onclick: () => deleteEvent(event) }, "Event löschen"));
  openDialog("event-prep-dialog");
}

async function deleteEvent(event) {
  if (!confirm(`Event „${event.name}“ löschen? Der Plan fällt auf den Standard zurück.`)) return;
  const { ok, data } = await api("DELETE", `/api/events/${event.id}`);
  if (!ok) {
    $("event-list-msg").textContent = data.error;
    return;
  }
  $("event-prep-dialog").close();
  await load();
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
  $("prev-day").addEventListener("click", () => shiftView(-1));
  $("next-day").addEventListener("click", () => shiftView(1));
  window.addEventListener("hashchange", () => { state.view = viewFromHash(); load(); });
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
  $("event-add").addEventListener("click", openEventDialog);
  $("event-form").addEventListener("submit", submitEvent);
  $("cancel-form").addEventListener("submit", submitCancel);
  for (const button of document.querySelectorAll("[data-close]")) {
    button.addEventListener("click", () => button.closest("dialog").close());
  }
}

async function syncIntervals() {
  // Auto-Sync beim Oeffnen (Server synchronisiert hoechstens alle 30 min); Fehler zeigt das Profil
  const status = await api("GET", "/api/intervals/status");
  if (status.ok && status.data.configured) await api("POST", "/api/intervals/sync?if_stale=1");
}

state.view = viewFromHash();
bindEvents();
syncIntervals().finally(load);
