"use strict";

const $ = (id) => document.getElementById(id);

async function api(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  // relativ aufloesen, damit die App auch unter einem Pfad-Praefix (z.B. /cpc/) laeuft
  const response = await fetch(path.replace(/^\//, ""), options);
  const data = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, data };
}

function formToObject(form) {
  const result = {};
  for (const [key, value] of new FormData(form)) {
    if (value !== "") result[key] = value;
  }
  return result;
}

function fmt(value, digits = 0) {
  return Number(value).toFixed(digits);
}

function setMsg(id, text) {
  $(id).textContent = text || "";
}

function makeTable(headers, rows) {
  const table = document.createElement("table");
  const head = table.insertRow();
  for (const h of headers) {
    const th = document.createElement("th");
    th.textContent = h;
    head.appendChild(th);
  }
  for (const row of rows) {
    const tr = table.insertRow();
    for (const cell of row) tr.insertCell().textContent = cell;
  }
  return table;
}

async function loadProfile() {
  const { ok, data } = await api("GET", "/api/profile");
  const form = $("profile-form");
  if (ok) {
    $("profile-view").textContent =
      `Alter ${data.age}, Grösse ${data.height_cm} cm, Programmstart ${data.program_start_date}`;
    for (const key of ["age", "height_cm", "program_start_date"]) form.elements[key].value = data[key];
  } else {
    $("profile-view").textContent = "Noch kein Profil angelegt.";
  }
  form.dataset.exists = ok ? "1" : "";
}

async function saveProfile(event) {
  event.preventDefault();
  const form = event.target;
  const method = form.dataset.exists ? "PUT" : "POST";
  const { ok, data } = await api(method, "/api/profile", formToObject(form));
  setMsg("profile-msg", ok ? "" : data.error);
  if (ok) await Promise.all([loadProfile(), loadBaseline()]);
}

async function loadCheckins() {
  const { data } = await api("GET", "/api/checkins");
  const rows = (data || []).map((c) => [
    c.checkin_date, fmt(c.weight_kg, 1), fmt(c.bodyfat_pct, 1), fmt(c.muscle_kg, 1), fmt(c.ffm_kg, 1),
  ]);
  const table = makeTable(["Datum", "Gewicht kg", "KF %", "Muskel kg", "FFM kg"], rows);
  table.id = "checkin-table";
  $("checkin-table").replaceWith(table);
}

async function saveCheckin(event) {
  event.preventDefault();
  const { ok, data } = await api("POST", "/api/checkins", formToObject(event.target));
  setMsg("checkin-msg", ok ? "" : data.error);
  if (ok) await Promise.all([loadCheckins(), loadBaseline(), loadReview(), loadToday()]);
}

async function loadSignals() {
  const { data } = await api("GET", "/api/signals");
  const latest = (data || [])[0];
  $("signals-view").textContent = latest
    ? `Letzter Fragebogen: ${latest.date} (Schlaf ${latest.sleep}, Beine ${latest.legs}, Hunger ${latest.hunger}, `
      + `Rücken ${latest.back}, Anstrengung ${latest.effort}${latest.resting_hr ? `, Ruhe-HF ${latest.resting_hr}` : ""})`
    : "Noch kein Fragebogen erfasst.";
}

async function saveSignals(event) {
  event.preventDefault();
  const body = {};
  for (const [key, value] of new FormData(event.target)) if (value !== "") body[key] = Number(value);
  const { ok, data } = await api("POST", "/api/signals", body);
  setMsg("signals-msg", ok ? "" : data.error);
  if (ok) await Promise.all([loadSignals(), loadReview()]);
}

const SEVERITY_LABEL = { alert: "Dringend", warn: "Achtung", info: "Hinweis" };

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function loadReview() {
  const { ok, data } = await api("GET", "/api/review");
  if (!ok) {
    setMsg("review-msg", data.error);
    return;
  }
  setMsg("review-msg", "");
  const s = data.summary;
  const num = (v, d = 0, unit = "") => (v === null || v === undefined ? "–" : `${fmt(v, d)}${unit}`);
  $("review-summary").replaceChildren(makeTable(["Kennzahl", "Wert"], [
    ["Gewicht / Ziel", `${num(s.weight_kg, 1, " kg")} / ${num(s.target_weight_kg, 1, " kg")}`],
    ["Trend (2 Wochen)", s.trend_kg_per_week === null ? "–" : `${num(s.trend_kg_per_week, 2, " kg")}/Woche (${num(s.trend_pct_per_week, 2, " %")})`],
    ["FTP / W/kg", `${num(s.ftp_watts, 0, " W")} / ${num(s.watts_per_kg, 2)}`],
    ["Defizit heute", num(s.deficit_kcal, 0, " kcal")],
    ["Ø Energy Availability 7 Tage", num(s.energy_availability_avg, 1, " kcal/kg FFM")],
  ]));

  const findings = data.findings.map((f) => {
    const box = el("div", undefined, `finding ${f.severity}`);
    box.append(el("strong", `${SEVERITY_LABEL[f.severity]}: ${f.title}`), el("p", f.detail), el("p", `Quelle: ${f.source}`, "source"));
    if (f.action) {
      const accept = el("button", `Übernehmen: ${f.action.label}`);
      accept.addEventListener("click", () => decide(f.key, "accepted"));
      box.append(accept);
    }
    const dismiss = el("button", f.action ? "Verwerfen" : "Erledigt");
    dismiss.addEventListener("click", () => decide(f.key, "dismissed"));
    box.append(dismiss);
    return box;
  });
  $("review-findings").replaceChildren(...(findings.length ? findings : [el("p", "Keine offenen Befunde.")]));

  const rows = data.adjustments.map((a) => {
    const row = el("div");
    const period = a.end_date ? `${a.start_date} bis ${a.end_date}` : `ab ${a.start_date}`;
    row.append(el("span", `${a.active ? "● aktiv" : "○ beendet"} · ${a.label} (${period}) `));
    const undo = el("button", "Rückgängig");
    undo.addEventListener("click", () => undoAdjustment(a.id));
    row.append(undo);
    return row;
  });
  $("review-adjustments").replaceChildren(...(rows.length ? rows : [el("p", "Keine Anpassungen.")]));
}

async function decide(key, decision) {
  const { ok, data } = await api("POST", "/api/review/decisions", { key, decision });
  setMsg("review-msg", ok ? "" : data.error);
  await Promise.all([loadReview(), loadToday()]);
}

async function undoAdjustment(id) {
  const { ok, data } = await api("DELETE", `/api/adjustments/${id}`);
  setMsg("review-msg", ok ? "" : data.error);
  await Promise.all([loadReview(), loadToday()]);
}

async function loadFtp() {
  const { ok, data } = await api("GET", "/api/checkins/ftp-tests/latest");
  $("ftp-view").textContent = ok
    ? `Aktuelle FTP: ${data.ftp_watts} W (Test ${data.test_date})`
    : "FTP noch nicht getestet (Zwift-Ramp-Test steht aus).";
}

async function saveFtp(event) {
  event.preventDefault();
  const { ok, data } = await api("POST", "/api/checkins/ftp-tests", formToObject(event.target));
  setMsg("ftp-msg", ok ? "" : data.error);
  if (ok) await Promise.all([loadFtp(), loadReview()]);
}

const SOURCE_LABEL = { measured: "gemessen", estimated: "geschätzt" };

function localToday() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

async function loadBaseline() {
  const { ok, data } = await api("GET", "/api/baseline");
  const view = $("baseline-view");
  if (!ok) {
    view.textContent = data.error || "Messwerte nicht verfügbar.";
    return;
  }
  const select = $("baseline-field");
  if (!select.options.length) {
    for (const name of Object.keys(data.fields)) select.add(new Option(name, name));
  }
  const rows = Object.entries(data.fields).map(([name, f]) => [
    name,
    f.value === null ? "–" : fmt(f.value, 1),
    f.source ? SOURCE_LABEL[f.source] : "–",
  ]);
  rows.push(["rmr_ratio (abgeleitet)", fmt(data.derived.rmr_ratio, 2), "berechnet"]);
  rows.push(["target_weight_kg (abgeleitet)", fmt(data.derived.target_weight_kg, 1), "berechnet"]);
  view.replaceChildren(makeTable(["Feld", "Wert", "Quelle"], rows));
}

async function saveBaseline(event) {
  event.preventDefault();
  const form = event.target;
  const { ok, data } = await api("PUT", `/api/baseline/${form.elements.field.value}`, {
    value: Number(form.elements.value.value),
  });
  setMsg("baseline-msg", ok ? "" : data.error);
  if (ok) await loadBaseline();
}

async function loadIntake() {
  const { ok, data } = await api("GET", `/api/intake/${localToday()}`);
  $("intake-view").textContent = ok
    ? `${fmt(data.kcal)} kcal, P ${fmt(data.protein_g)} g, KH ${fmt(data.carbs_g)} g, F ${fmt(data.fat_g)} g`
    : "Heute noch nichts erfasst.";
}

async function saveIntake(event) {
  event.preventDefault();
  const body = Object.fromEntries(Object.entries(formToObject(event.target)).map(([k, v]) => [k, Number(v)]));
  const { ok, data } = await api("PUT", `/api/intake/${localToday()}`, body);
  setMsg("intake-msg", ok ? "" : data.error);
  if (ok) await loadIntake();
}

function renderToday(plan) {
  const box = $("today-result");
  box.replaceChildren();

  const p = plan.phase;
  const info = document.createElement("p");
  info.textContent = `${plan.date} – Phase: ${p.phase_id} (${p.phase_start} bis ${p.phase_end || "offen"}, Tag ${p.day_in_phase})`;
  box.appendChild(info);

  const t = plan.training;
  const parts = [];
  if (t.status === "skipped") parts.push("abgesagt");
  else {
    if (t.cycling) parts.push(`Rad: ${t.cycling.title} (${fmt(t.cycling.minutes)} min)`);
    if (t.strength) parts.push(t.strength.title);
  }
  const training = document.createElement("p");
  training.textContent = `Training: ${parts.length ? parts.join(" · ") : "Ruhetag"} – Tagestyp ${plan.day_type}`;
  box.appendChild(training);

  const n = plan.nutrition;
  box.appendChild(makeTable(["kcal", "Wert"], [
    ["Grundumsatz (BMR)", fmt(n.bmr_kcal)],
    ["Alltag (BMR × 1.45)", fmt(n.non_exercise_kcal)],
    ["Rad", fmt(n.cycling_kcal)],
    ["Kraft", fmt(n.strength_kcal)],
    ["Erhaltung", fmt(n.maintenance_kcal)],
    ["Defizit", fmt(n.deficit_kcal)],
    ["Ziel", fmt(n.target_kcal)],
  ]));

  const m = plan.macros;
  const src = document.createElement("p");
  src.textContent = `Ziele basieren auf ${SOURCE_LABEL[plan.targets_source]}en Werten (RMR/FFM).`;
  box.appendChild(src);
  const intake = plan.intake;
  box.appendChild(makeTable(intake ? ["Makro", "Soll", "Ist"] : ["Makro", "Soll"], [
    ["kcal", fmt(n.target_kcal), ...(intake ? [fmt(intake.kcal)] : [])],
    ["Protein g", fmt(m.protein_g), ...(intake ? [fmt(intake.protein_g)] : [])],
    ["Fett g", fmt(m.fat_g), ...(intake ? [fmt(intake.fat_g)] : [])],
    ["Kohlenhydrate g", fmt(m.carbs_g), ...(intake ? [fmt(intake.carbs_g)] : [])],
  ]));
  if (intake) {
    const ea = document.createElement("p");
    ea.textContent = `Energy Availability: ${fmt(intake.energy_availability, 1)} kcal/kg FFM`;
    box.appendChild(ea);
  }

  if (!plan.zones.available) {
    const hint = document.createElement("p");
    hint.className = "hint";
    hint.textContent = plan.zones.message;
    box.appendChild(hint);
    return;
  }
  const rows = plan.zones.zones.map((z) => [
    z.zone_id,
    z.pct_ftp_max === null ? `>${z.pct_ftp_min}%` : `${z.pct_ftp_min}–${z.pct_ftp_max}%`,
    z.watts_max === null ? `>${z.watts_min} W` : `${z.watts_min}–${z.watts_max} W`,
  ]);
  box.appendChild(makeTable([`Zone (FTP ${plan.zones.ftp_watts} W)`, "% FTP", "Watt"], rows));
}

async function loadToday() {
  const { ok, data } = await api("GET", "/api/plan/today");
  setMsg("today-msg", ok ? "" : data.error);
  if (ok) renderToday(data);
  else $("today-result").replaceChildren();
}

$("profile-form").addEventListener("submit", saveProfile);
$("checkin-form").addEventListener("submit", saveCheckin);
$("signals-form").addEventListener("submit", saveSignals);
$("ftp-form").addEventListener("submit", saveFtp);
$("today-refresh").addEventListener("click", loadToday);
$("baseline-form").addEventListener("submit", saveBaseline);
$("intake-form").addEventListener("submit", saveIntake);

loadProfile();
loadCheckins();
loadFtp();
loadBaseline();
loadIntake();
loadToday();
loadSignals();
loadReview();
