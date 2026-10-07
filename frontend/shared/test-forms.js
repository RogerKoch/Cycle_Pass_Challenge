"use strict";

// FTP-Test und Kraft-Benchmark (Erfassung + Anzeige), gebraucht auf Check-ins und Profil (Startwerte).
// Braucht ui.js. Optionen: { startOnly, onSaved }
//   startOnly: Formular nur zeigen, solange noch kein Test existiert (Startwerte im Profil).
//   onSaved:   wird nach erfolgreichem Speichern aufgerufen (z.B. Review neu laden).

const FTP_HTML = `
  <div data-view></div>
  <form data-form>
    <label>Beste 1-Min-Leistung (W) <input name="best_1min_power_watts" type="number" step="1" required></label>
    <label>Manuelle Korrektur (%) <input name="manual_correction_pct" type="number" step="0.5" placeholder="z.B. -3"></label>
    <button type="submit">Erfassen</button>
  </form>
  <p class="msg" data-msg></p>`;

const BENCHMARK_HTML = `
  <div data-view></div>
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
  <div data-milestones></div>`;

const STAGE_TEXT = {
  rows_feet_elevated: (v) => `Rows: ${v ? "Füsse erhöht" : "Füsse am Boden"}`,
  side_plank_straight: (v) => `Side Plank: ${v ? "gestreckt" : "Knie gebeugt"}`,
  glute_bridge_single_leg: (v) => `Glute Bridge: ${v ? "einbeinig" : "beidbeinig"}`,
};

function checkinsLink(text) {
  const link = el("a", text);
  link.href = "../checkins/";
  return link;
}

function mountFtp(box, { startOnly = false, onSaved = async () => {} } = {}) {
  box.innerHTML = FTP_HTML;
  const view = box.querySelector("[data-view]");
  const form = box.querySelector("[data-form]");
  const msg = box.querySelector("[data-msg]");

  async function load() {
    const { ok, data } = await api("GET", "/api/checkins/ftp-tests/latest");
    view.textContent = ok
      ? `Aktuelle FTP: ${data.ftp_watts} W (Test ${data.test_date})`
      : "FTP noch nicht getestet (Zwift-Ramp-Test steht aus).";
    if (startOnly) {
      form.hidden = ok;
      if (ok) view.append(" · weitere Tests unter ", checkinsLink("Check-ins"));
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const { ok, data } = await api("POST", "/api/checkins/ftp-tests", formToObject(form));
    msg.textContent = ok ? "" : data.error;
    if (ok) await Promise.all([load(), onSaved()]);
  });
  return load();
}

function mountBenchmark(box, { startOnly = false, onSaved = async () => {} } = {}) {
  box.innerHTML = BENCHMARK_HTML;
  const view = box.querySelector("[data-view]");
  const form = box.querySelector("[data-form]");
  const msg = box.querySelector("[data-msg]");
  const milestones = box.querySelector("[data-milestones]");

  async function load() {
    const { ok, data } = await api("GET", "/api/strength-benchmarks");
    if (!ok) return;
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
