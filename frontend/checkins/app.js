"use strict";

const SEVERITY_LABEL = { alert: "Dringend", warn: "Achtung", info: "Hinweis" };
const TABS = ["woechentlich", "ftp", "benchmark"];
const TABLE_ROWS = 10;
const METRICS = {
  weight_kg: { label: "Gewicht", unit: "kg" },
  bodyfat_pct: { label: "Körperfett", unit: "%" },
  muscle_kg: { label: "Muskelmasse", unit: "kg" },
};

const state = { checkins: [], targetWeight: null, showAll: false };

// ---------------------------------------------------------------- Reiter

function showTab() {
  const hash = location.hash.slice(1);
  const tab = TABS.includes(hash) ? hash : "woechentlich";
  for (const name of TABS) $(name).hidden = name !== tab;
  for (const link of document.querySelectorAll("[data-tab]")) {
    link.setAttribute("aria-current", link.dataset.tab === tab ? "page" : "false");
  }
  // Anker innerhalb eines Reiters (z.B. #review) erst nach dem Einblenden anspringen
  if (hash && !TABS.includes(hash)) document.getElementById(hash)?.scrollIntoView();
}

// ---------------------------------------------------------------- Check-ins

function renderChart() {
  const key = $("chart-metric").value;
  const { label, unit } = METRICS[key];
  const points = [...state.checkins].reverse().map((c) => ({ date: c.checkin_date, value: c[key] }));
  lineChart($("checkin-chart"), points, {
    unit, label, target: key === "weight_kg" ? state.targetWeight : null,
  });
}

function renderCheckinTable() {
  const shown = state.showAll ? state.checkins : state.checkins.slice(0, TABLE_ROWS);
  const rows = shown.map((c) => [
    c.checkin_date, fmt(c.weight_kg, 1), fmt(c.bodyfat_pct, 1), fmt(c.muscle_kg, 1), fmt(c.ffm_kg, 1),
    c.source === "intervals" ? "Garmin" : "manuell",
  ]);
  const table = makeTable(["Datum", "Gewicht kg", "KF %", "Muskel kg", "FFM kg", "Quelle"], rows);
  table.id = "checkin-table";
  $("checkin-table").replaceWith(table);
  $("checkin-more").hidden = state.checkins.length <= TABLE_ROWS;
  $("checkin-more").textContent = state.showAll ? "Weniger anzeigen" : `Alle anzeigen (${state.checkins.length})`;
}

async function loadCheckins() {
  const { data } = await api("GET", "/api/checkins");
  state.checkins = data || [];
  renderCheckinTable();
  renderChart();
}

async function saveCheckin(event) {
  event.preventDefault();
  const { ok, data } = await api("POST", "/api/checkins", formToObject(event.target));
  setMsg("checkin-msg", ok ? "" : data.error);
  if (ok) {
    event.target.reset();
    await Promise.all([loadCheckins(), loadReview()]);
  }
}

// ---------------------------------------------------------------- Fragebogen

async function loadSignals() {
  const { data } = await api("GET", "/api/signals");
  const rows = (data || []).slice(0, 8).map((s) => [
    s.date, s.sleep, s.legs, s.hunger, s.back, s.effort, s.resting_hr ?? "–",
  ]);
  const table = makeTable(["Datum", "Schlaf", "Beine", "Hunger", "Rücken", "Anstrengung", "Ruhe-HF"], rows);
  table.id = "signals-table";
  $("signals-table").replaceWith(table);
}

async function saveSignals(event) {
  event.preventDefault();
  const body = {};
  for (const [key, value] of new FormData(event.target)) if (value !== "") body[key] = Number(value);
  const { ok, data } = await api("POST", "/api/signals", body);
  setMsg("signals-msg", ok ? "" : data.error);
  if (ok) await Promise.all([loadSignals(), loadReview()]);
}

// ---------------------------------------------------------------- Review

async function loadReview() {
  const { ok, data } = await api("GET", "/api/review");
  if (!ok) {
    setMsg("review-msg", data.error);
    return;
  }
  setMsg("review-msg", "");
  const s = data.summary;
  state.targetWeight = s.target_weight_kg ?? null;
  renderChart();
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
  await loadReview();
}

async function undoAdjustment(id) {
  const { ok, data } = await api("DELETE", `/api/adjustments/${id}`);
  setMsg("review-msg", ok ? "" : data.error);
  await loadReview();
}

// ---------------------------------------------------------------- Start

$("checkin-form").addEventListener("submit", saveCheckin);
$("signals-form").addEventListener("submit", saveSignals);
$("chart-metric").addEventListener("change", renderChart);
$("checkin-more").addEventListener("click", () => {
  state.showAll = !state.showAll;
  renderCheckinTable();
});
window.addEventListener("hashchange", showTab);

const testOptions = { history: true, onSaved: loadReview };
function loadAll() {
  loadCheckins();
  loadSignals();
  loadReview();
  mountFtp($("ftp-box"), testOptions);
  mountBenchmark($("benchmark-box"), testOptions);
}

// Neue Garmin-Waagen-Daten kommen per Sync; der Server synchronisiert hoechstens alle 30 min
async function syncIfStale() {
  const status = await api("GET", "/api/intervals/status");
  if (!status.ok || !status.data.configured) return;
  const { data } = await api("POST", "/api/intervals/sync?if_stale=1");
  if (data.synced) loadAll();
}

showTab();
loadAll();
syncIfStale();
