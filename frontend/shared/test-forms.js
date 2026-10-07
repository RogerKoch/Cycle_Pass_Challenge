"use strict";

// FTP-Test und Kraft-Benchmark (Erfassen + Anzeige), gebraucht auf Check-ins und Profil (Startwerte).
// Braucht ui.js; mit history zusaetzlich chart.js. Optionen: { startOnly, history, onSaved }
//   startOnly: Formular nur zeigen, solange noch kein Test existiert (Startwerte im Profil).
//   history:   Chart und Verlaufstabelle anzeigen (Check-ins).
//   onSaved:   wird nach erfolgreichem Speichern aufgerufen (z.B. Review neu laden).

const FTP_HTML = `
  <div data-view></div>
  <div class="chart" data-chart hidden></div>
  <form data-form>
    <label>Beste 1-Min-Leistung (W) <input name="best_1min_power_watts" type="number" step="1" required></label>
    <label>Manuelle Korrektur (%) <input name="manual_correction_pct" type="number" step="0.5" placeholder="z.B. -3"></label>
    <button type="submit">Erfassen</button>
  </form>
  <p class="msg" data-msg></p>
  <div data-history hidden></div>`;

const BENCHMARK_HTML = `
  <div data-view></div>
  <div data-chart-box hidden>
    <label>Übung <select data-metric></select></label>
    <div class="chart" data-chart></div>
  </div>
  <form data-form>
    <label>Liegestütze am Stück <input name="pushup_reps" type="number" min="0" step="1"></label>
    <label>Variante <select name="pushup_variant"></select></label>
    <label>Inverted Rows am Stück <input name="row_reps" type="number" min="0" step="1"></label>
    <label>Side Plank (s, schwächere Seite) <input name="side_plank_s" type="number" min="0" step="1"></label>
    <label>Side Plank Ausführung <select name="side_plank_straight">
      <option value="false">Knie gebeugt</option><option value="true">Beine gestreckt</option></select></label>
    <label>Single-Leg Glute Bridge (s, schwächere Seite) <input name="sl_bridge_s" type="number" min="0" step="1"></label>
    <label>Plank (s) <input name="plank_s" type="number" min="0" step="1"></label>
    <button type="submit">Erfassen</button>
  </form>
  <p class="msg" data-msg></p>
  <div data-history hidden></div>
  <div data-milestones></div>`;

const STAGE_TEXT = {
  rows_feet_elevated: (v) => `Rows: ${v ? "Füsse erhöht" : "Füsse am Boden"}`,
  side_plank_straight: (v) => `Side Plank: ${v ? "gestreckt" : "Knie gebeugt"}`,
  glute_bridge_single_leg: (v) => `Glute Bridge: ${v ? "einbeinig" : "beidbeinig"}`,
};

const BENCHMARK_METRICS = [
  ["pushup_reps", "Liegestütze", "Wdh."],
  ["row_reps", "Inverted Rows", "Wdh."],
  ["side_plank_s", "Side Plank", "s"],
  ["sl_bridge_s", "Single-Leg Glute Bridge", "s"],
  ["plank_s", "Plank", "s"],
];

function checkinsLink(text) {
  const link = el("a", text);
  link.href = "../checkins/";
  return link;
}

const cell = (value, digits = 0) => (value === null || value === undefined ? "–" : fmt(value, digits));

function mountFtp(box, { startOnly = false, history = false, onSaved = async () => {} } = {}) {
  box.innerHTML = FTP_HTML;
  const view = box.querySelector("[data-view]");
  const form = box.querySelector("[data-form]");
  const msg = box.querySelector("[data-msg]");
  const chart = box.querySelector("[data-chart]");
  const table = box.querySelector("[data-history]");

  async function load() {
    const { ok, data } = await api("GET", "/api/checkins/ftp-tests");
    const tests = ok ? data : [];
    const latest = tests[0];
    view.textContent = latest
      ? `Aktuelle FTP: ${latest.ftp_watts} W (Test ${latest.test_date})`
      : "FTP noch nicht getestet (Zwift-Ramp-Test steht aus), Zonen sind bis dahin gesperrt.";
    if (startOnly) {
      form.hidden = Boolean(latest);
      if (latest) view.append(" · weitere Tests unter ", checkinsLink("Check-ins"));
    }
    if (history) {
      chart.hidden = table.hidden = false;
      lineChart(chart, [...tests].reverse().map((t) => ({ date: t.test_date, value: t.ftp_watts })),
        { unit: "W", decimals: 0, label: "FTP" });
      table.replaceChildren(makeTable(["Datum", "Beste 1 Min W", "Korrektur %", "FTP W"],
        tests.map((t) => [t.test_date, cell(t.best_1min_power_watts), cell(t.manual_correction_pct, 1), cell(t.ftp_watts)])));
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const { ok, data } = await api("POST", "/api/checkins/ftp-tests", formToObject(form));
    msg.textContent = ok ? "" : data.error;
    if (ok) {
      form.reset();
      await Promise.all([load(), onSaved()]);
    }
  });
  return load();
}

function mountBenchmark(box, { startOnly = false, history = false, onSaved = async () => {} } = {}) {
  box.innerHTML = BENCHMARK_HTML;
  const view = box.querySelector("[data-view]");
  const form = box.querySelector("[data-form]");
  const msg = box.querySelector("[data-msg]");
  const milestones = box.querySelector("[data-milestones]");
  const chartBox = box.querySelector("[data-chart-box]");
  const chart = box.querySelector("[data-chart]");
  const metric = box.querySelector("[data-metric]");
  const table = box.querySelector("[data-history]");
  let tests = [];

  metric.replaceChildren(...BENCHMARK_METRICS.map(([key, label]) => {
    const option = el("option", label);
    option.value = key;
    return option;
  }));

  function renderChart() {
    const [key, label, unit] = BENCHMARK_METRICS.find(([k]) => k === metric.value);
    const points = [...tests].reverse().filter((t) => t[key] !== null && t[key] !== undefined)
      .map((t) => ({ date: t.test_date, value: t[key] }));
    lineChart(chart, points, { unit, decimals: 0, label });
  }
  metric.addEventListener("change", renderChart);

  async function load() {
    const { ok, data } = await api("GET", "/api/strength-benchmarks");
    if (!ok) return;
    tests = data.tests;
    if (!form.elements.pushup_variant.options.length) {
      form.elements.pushup_variant.replaceChildren(...data.pushup_variants.map((v) => {
        const option = el("option", v.label);
        option.value = v.id;
        return option;
      }));
      form.elements.pushup_variant.value = "knie";
    }
    const variants = Object.fromEntries(data.pushup_variants.map((v) => [v.id, v.label]));
    const stages = [];
    if (data.stages.pushup_variant) stages.push(`Liegestütz: ${variants[data.stages.pushup_variant]}`);
    for (const [key, text] of Object.entries(STAGE_TEXT)) {
      if (data.stages[key] !== null) stages.push(text(data.stages[key]));
    }
    if (data.stages.core_advanced) stages.push("Hollow Body/Pallof freigeschaltet");
    const due = data.next_due <= localToday() ? "fällig" : `nächster Test ${data.next_due}`;
    view.textContent = data.current
      ? `Letzter Test ${data.current.test_date} · ${due} (alle ${data.interval_weeks} Wochen) · Stufen: ${stages.join(", ") || "–"}`
      : `Noch kein Test – Woche-0-Baseline ${due}.`;
    if (startOnly) {
      form.hidden = Boolean(data.current);
      milestones.hidden = true;
      if (data.current) view.append(" · weitere Tests unter ", checkinsLink("Check-ins"));
      return;
    }
    if (history) {
      chartBox.hidden = table.hidden = false;
      renderChart();
      table.replaceChildren(makeTable(["Datum", "Liegestütze", "Rows", "Side Plank s", "SL-Bridge s", "Plank s"],
        tests.map((t) => [t.test_date, cell(t.pushup_reps), cell(t.row_reps), cell(t.side_plank_s), cell(t.sl_bridge_s), cell(t.plank_s)])));
    }
    const mark = { true: "✓", false: "offen", null: "–" };
    milestones.replaceChildren(makeTable(["Woche", "Meilenstein", "Status"],
      data.milestones.map((m) => [`W${m.week}`, m.text, mark[m.achieved]])));
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = formToObject(form);
    if (!body.pushup_reps) delete body.pushup_variant;
    if (body.side_plank_s) body.side_plank_straight = body.side_plank_straight === "true";
    else delete body.side_plank_straight;
    const { ok, data } = await api("POST", "/api/strength-benchmarks", body);
    msg.textContent = ok ? "" : data.error;
    if (ok) {
      const variant = form.elements.pushup_variant.value;
      form.reset();
      form.elements.pushup_variant.value = variant;
      await Promise.all([load(), onSaved()]);
    }
  });
  return load();
}
