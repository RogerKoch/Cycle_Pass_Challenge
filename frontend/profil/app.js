"use strict";

const SOURCE_LABEL = { measured: "gemessen", estimated: "geschätzt" };

async function loadProfile() {
  const { ok, data } = await api("GET", "/api/profile");
  const form = $("profile-form");
  if (ok) {
    const level = data.activity_levels.find((l) => l.id === data.activity_level);
    const focus = data.focus_options.find((f) => f.id === data.strength_focus);
    $("profile-view").textContent =
      `Alter ${data.age}, Grösse ${data.height_cm} cm, Programmstart ${data.program_start_date}, Alltag ${level.label} (× ${level.factor}), Kraft-Fokus ${focus.label}`;
    form.elements.activity_level.replaceChildren(...data.activity_levels.map((l) => {
      const option = el("option", `${l.label} (× ${l.factor})`);
      option.value = l.id;
      return option;
    }));
    form.elements.strength_focus.replaceChildren(...data.focus_options.map((f) => {
      const option = el("option", f.label);
      option.value = f.id;
      return option;
    }));
    for (const key of ["age", "height_cm", "program_start_date", "activity_level", "strength_focus", "benchmark_interval_weeks"]) {
      form.elements[key].value = data[key];
    }
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
  if (ok) await Promise.all([loadProfile(), loadBaseline(), loadToday()]);
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
  if (ok) await Promise.all([loadBaseline(), loadToday()]);
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
  const imported = t.imported.filter((a) => a.is_ride || a.is_strength);
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
$("baseline-form").addEventListener("submit", saveBaseline);
$("intervals-sync").addEventListener("click", () => syncIntervals(false));

// Startwerte: Formulare nur, solange noch kein Test existiert; ein neuer FTP aendert die Zonen
const startwerte = { startOnly: true, onSaved: loadToday };
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

loadAll();
syncIntervals(true);
