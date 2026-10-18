"use strict";

const SOURCE_LABEL = { measured: "gemessen", estimated: "geschätzt" };

const GOAL_MODES = {
  bodyfat: { label: "Ziel-Körperfett (%)", placeholder: "16", field: "target_bodyfat_pct" },
  weight: { label: "Zielgewicht (kg)", placeholder: "68", field: "target_weight_kg" },
};

function setGoalMode(mode) {
  const form = $("profile-form");
  form.elements.goal_mode.value = mode;
  $("goal-label").textContent = GOAL_MODES[mode].label;
  form.elements.goal_value.placeholder = GOAL_MODES[mode].placeholder;
}

const NEW_PROFILE_DEFAULTS = { evening_training_days: [1, 2, 3, 4], equipment_missing: [] };

// Rendert die Auswahllisten; die Backend-404-Antwort liefert sie auch ohne bestehendes Profil mit,
// damit alles vor dem ersten Speichern ausfuellbar ist.
function checkboxLabels(options, checked) {
  return options.map((o) => {
    const box = el("input");
    box.type = "checkbox";
    box.value = o.id;
    box.checked = checked.includes(o.id);
    const label = el("label");
    label.className = "chip";
    label.append(box, ` ${o.label}`);
    return label;
  });
}

async function loadProfile() {
  const { ok, data } = await api("GET", "/api/profile");
  const form = $("profile-form");
  form.elements.activity_level.replaceChildren(...data.activity_levels.map((l) => {
    const option = el("option", `${l.label} (× ${l.factor})`);
    option.value = l.id;
    return option;
  }));
  for (const [name, options] of [["sex", data.sex_options], ["sport", data.sport_options]]) {
    form.elements[name].replaceChildren(...options.map((o) => {
      const option = el("option", o.label);
      option.value = o.id;
      return option;
    }));
  }
  form.elements.strength_focus.replaceChildren(...data.focus_options.map((f) => {
    const option = el("option", f.label);
    option.value = f.id;
    return option;
  }));
  form.elements.rest_weekday.replaceChildren(...data.weekday_options.map((o) => {
    const option = el("option", o.label);
    option.value = o.id;
    return option;
  }));
  form.elements.rest_weekday.value = ok ? data.rest_weekday : 1; // Standard: Dienstag
  const current = ok ? data : NEW_PROFILE_DEFAULTS;
  $("equipment-missing").replaceChildren(
    $("equipment-missing").querySelector("legend"),
    ...checkboxLabels(data.equipment_options, current.equipment_missing));
  $("evening-days").replaceChildren(
    $("evening-days").querySelector("legend"),
    ...checkboxLabels(data.weekday_options, current.evening_training_days));
  if (ok) {
    const level = data.activity_levels.find((l) => l.id === data.activity_level);
    const focus = data.focus_options.find((f) => f.id === data.strength_focus);
    $("ftp-heading").hidden = $("ftp-box").hidden = data.sport === "running";
    $("profile-view").textContent =
      `Alter ${data.age}, Grösse ${data.height_cm} cm, Programmstart ${data.program_start_date}, Alltag ${level.label} (× ${level.factor}), Kraft-Fokus ${focus.label}`;
    for (const key of ["age", "height_cm", "program_start_date", "activity_level", "sex", "sport", "strength_focus", "benchmark_interval_weeks"]) {
      form.elements[key].value = data[key];
    }
  } else {
    $("profile-view").textContent = "Noch kein Profil angelegt.";
  }
  const weightGoal = ok && data.target_weight_kg !== null;
  setGoalMode(weightGoal ? "weight" : "bodyfat");
  const goal = weightGoal ? data.target_weight_kg : ok ? data.target_bodyfat_pct : null;
  form.elements.goal_value.value = goal === null ? "" : goal;
  form.dataset.exists = ok ? "1" : "";
}

async function saveProfile(event) {
  event.preventDefault();
  const form = event.target;
  const method = form.dataset.exists ? "PUT" : "POST";
  const body = formToObject(form);
  const { goal_mode: goalMode, goal_value: goalValue } = body;
  delete body.goal_mode;
  delete body.goal_value;
  body.rest_weekday = Number(body.rest_weekday);
  if (goalValue !== undefined) body[GOAL_MODES[goalMode].field] = Number(goalValue);
  body.equipment_missing = [...form.querySelectorAll("#equipment-missing input:checked")].map((box) => box.value);
  body.evening_training_days = [...form.querySelectorAll("#evening-days input:checked")].map((box) => Number(box.value));
  const { ok, data } = await api(method, "/api/profile", body);
  setMsg("profile-msg", ok ? "" : data.error);
  if (ok) await Promise.all([loadProfile(), loadBaseline(), loadToday()]);
}

const BASELINE_LABELS = {
  rmr_kcal: ["Ruheumsatz (kcal)", 0],
  ffm_kg: ["Fettfreie Masse (kg)", 1],
  bodyfat_pct: ["Körperfett (%)", 1],
  skinfold_sum_mm: ["Hautfaltensumme (mm)", 1],
  phase_angle_deg: ["Phasenwinkel (°)", 1],
  vt1_hr: ["VT1 Puls (bpm)", 0],
  vt1_watts: ["VT1 Leistung (W)", 0],
  vt2_hr: ["VT2 Puls (bpm)", 0],
  vt2_watts: ["VT2 Leistung (W)", 0],
  fatmax_watts: ["FatMax Leistung (W)", 0],
  fatmax_hr: ["FatMax Puls (bpm)", 0],
  mfo_g_min: ["Max. Fettoxidation (g/min)", 2],
  target_bodyfat_pct: ["Ziel-Körperfett (%)", 1],
};

async function saveBaselineField(name, input) {
  const { ok, data } = await api("PUT", `/api/baseline/${name}`, { value: Number(input.value) });
  setMsg("baseline-msg", ok ? "" : data.error);
  if (ok) await Promise.all([loadBaseline(), loadProfile(), loadToday()]);
}

async function loadBaseline() {
  const { ok, data } = await api("GET", "/api/baseline");
  const view = $("baseline-view");
  if (!ok) {
    view.textContent = data.error || "Messwerte nicht verfügbar.";
    return;
  }
  const hasEstimates = data.fields.rmr_kcal.value !== null; // Schaetzwerte entstehen erst aus einem Check-in
  const hint = $("baseline-hint");
  if (hasEstimates) {
    hint.textContent = "Bis zur Messung gelten Schätzwerte aus den Berechnungen.";
  } else {
    const link = el("a", "Zu den Check-ins");
    link.href = "../checkins/";
    hint.replaceChildren("Initialer Check-in fehlt: Schätzwerte entstehen aus dem ersten Check-in. ", link);
  }
  const table = document.createElement("table");
  const head = table.insertRow();
  for (const title of ["Feld", "Wert", "Quelle", ""]) head.append(el("th", title));
  const names = [...Object.keys(BASELINE_LABELS), ...Object.keys(data.fields)];
  for (const name of new Set(names)) {
    const f = data.fields[name];
    if (!f) continue;
    const [label, digits] = BASELINE_LABELS[name] || [name, 1];
    const row = table.insertRow();
    row.insertCell().textContent = label;
    const input = el("input");
    input.type = "number";
    input.step = "any";
    input.min = "0";
    input.value = f.value === null ? "" : fmt(f.value, digits);
    input.placeholder = "–";
    input.setAttribute("aria-label", label);
    row.insertCell().append(input);
    row.insertCell().textContent = f.source ? SOURCE_LABEL[f.source] : "–";
    const save = el("button", "Speichern");
    save.type = "button";
    save.addEventListener("click", () => saveBaselineField(name, input));
    row.insertCell().append(save);
  }
  const derived = [
    ["Verhältnis RMR (abgeleitet)", data.derived.rmr_ratio === null ? "–" : fmt(data.derived.rmr_ratio, 2)],
    ["Zielgewicht (abgeleitet)", data.derived.target_weight_kg === null ? "–" : `${fmt(data.derived.target_weight_kg, 1)} kg`],
  ];
  for (const [label, value] of derived) {
    const row = table.insertRow();
    row.insertCell().textContent = label;
    row.insertCell().textContent = value;
    row.insertCell().textContent = "berechnet";
    row.insertCell();
  }
  view.replaceChildren(table);
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
  const imported = t.imported.filter((a) => a.is_ride || a.is_run || a.is_strength);
  if (imported.length) {
    for (const a of imported) parts.push(`Garmin: ${a.name || a.type}${a.minutes ? ` (${fmt(a.minutes)} min)` : ""}`);
  } else if (t.status === "skipped") parts.push("abgesagt");
  else {
    if (t.cycling) parts.push(`Rad: ${t.cycling.title} (${fmt(t.cycling.minutes)} min)`);
    if (t.strength) parts.push(t.strength.title);
  }
  const training = document.createElement("p");
  training.textContent = `Training: ${parts.length ? parts.join(" · ") : "Ruhetag"} – Tagestyp ${plan.day_type}`;
  training.append(" ", infoLink("tagestyp"));
  box.appendChild(training);

  const n = plan.nutrition;
  box.appendChild(makeTable(["kcal", "Wert"], [
    ["Grundumsatz (BMR)", fmt(n.bmr_kcal)],
    [`Alltag (BMR × ${n.non_exercise_factor})`, fmt(n.non_exercise_kcal)],
    ["Rad", fmt(n.cycling_kcal)],
    ["Kraft", fmt(n.strength_kcal)],
    ["Erhaltung", fmt(n.maintenance_kcal)],
    ["Defizit", fmt(n.deficit_kcal)],
    ["Ziel", fmt(n.target_kcal)],
  ]));

  const m = plan.macros;
  const src = document.createElement("p");
  src.textContent = `Ziele basieren auf ${SOURCE_LABEL[plan.targets_source]}en Werten (RMR/FFM).`;
  src.append(" ", infoLink("kcalziel"));
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
    ea.append(" ", infoLink("ea"));
    box.appendChild(ea);
  }

  if (!plan.zones.available) {
    const hint = document.createElement("p");
    hint.className = "hint";
    hint.textContent = plan.zones.message;
    hint.append(" ", infoLink("ftp"));
    box.appendChild(hint);
    return;
  }
  const rows = plan.zones.zones.map((z) => [
    z.zone_id,
    z.pct_ftp_max === null ? `>${z.pct_ftp_min}%` : `${z.pct_ftp_min}–${z.pct_ftp_max}%`,
    z.watts_max === null ? `>${z.watts_min} W` : `${z.watts_min}–${z.watts_max} W`,
  ]);
  const zonesTitle = el("p", "Trainingszonen ");
  zonesTitle.append(infoLink("zonentabelle"));
  box.appendChild(zonesTitle);
  box.appendChild(makeTable([`Zone (FTP ${plan.zones.ftp_watts} W)`, "% FTP", "Watt"], rows));
}

async function loadToday() {
  const { ok, data } = await api("GET", "/api/plan/today");
  setMsg("today-msg", ok ? "" : data.error);
  if (ok) renderToday(data);
  else $("today-result").replaceChildren();
}

$("profile-form").addEventListener("submit", saveProfile);
$("today-refresh").addEventListener("click", loadToday);
for (const radio of $("profile-form").elements.goal_mode) {
  radio.addEventListener("change", () => setGoalMode(radio.value));
}
$("intervals-sync").addEventListener("click", () => syncIntervals(false));

// Startwerte: nur Anzeige; Erfassen laeuft ueber die Check-ins
const startwerte = { readOnly: true };
function loadAll() {
  loadProfile();
  loadBaseline();
  loadToday();
  mountFtp($("ftp-box"), startwerte);
  mountBenchmark($("benchmark-box"), startwerte);
}

async function loadIntervalsStatus() {
  const { ok, data } = await api("GET", "/api/intervals/status");
  if (!ok) return null;
  $("intervals-sync").hidden = !data.configured;
  $("intervals-view").textContent = data.configured
    ? `Letzter Sync: ${data.last_sync ? new Date(data.last_sync).toLocaleString("de-CH") : "noch nie"} · `
      + `${data.activities} Aktivitäten, ${data.wellness_days} Wellness-Tage`
    : "Nicht konfiguriert: INTERVALS_ICU_API_KEY in instance/config.py eintragen (intervals.icu → Settings → Developer Settings).";
  setMsg("intervals-msg", data.last_error ? `Letzter Fehler: ${data.last_error}` : "");
  return data;
}

async function syncIntervals(ifStale) {
  const status = await loadIntervalsStatus();
  if (!status || !status.configured) return;
  const { data } = await api("POST", `/api/intervals/sync${ifStale ? "?if_stale=1" : ""}`);
  await loadIntervalsStatus();
  if (data.synced) {
    loadAll();
    if (data.notes.length) setMsg("intervals-msg", data.notes.join(" "));
  } else if (data.error) {
    setMsg("intervals-msg", data.error);
  }
}

// Zuruecksetzen: Button erst aktiv, wenn das Bestaetigungswort stimmt (Server prueft es nochmals)
const RESET_WORD = "ZURÜCKSETZEN";
$("reset-form").elements.confirm.addEventListener("input", (event) => {
  $("reset-form").querySelector("button").disabled = event.target.value.trim() !== RESET_WORD;
});
$("reset-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const { ok, data } = await api("POST", "/api/admin/reset", { confirm: event.target.elements.confirm.value.trim() });
  if (!ok) {
    setMsg("reset-msg", data.error);
    return;
  }
  event.target.reset();
  event.target.querySelector("button").disabled = true;
  setMsg("reset-msg", `Zurückgesetzt${data.backup ? ` – Backup: ${data.backup}` : ""}. Bitte Profil neu anlegen.`);
  await loadAll();
});

loadAll();
syncIntervals(true);
