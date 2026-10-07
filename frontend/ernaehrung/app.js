"use strict";

const $ = (id) => document.getElementById(id);

const MEALS = [
  ["fruehstueck", "Frühstück"],
  ["mittag", "Mittag"],
  ["abend", "Abend"],
  ["snack", "Snacks"],
  ["training", "Training"],
];
const MEAL_NAMES = Object.fromEntries(MEALS);
const ZXING_URL = "https://cdn.jsdelivr.net/npm/@zxing/browser@0.2.1/umd/zxing-browser.min.js";

const state = {
  date: localIso(new Date()),
  day: null,
  target: null, // {kcal, protein_g, carbs_g, fat_g} nur fuer heute
  meal: "fruehstueck",
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
const isToday = () => state.date === localIso(new Date());

function openDialog(id) {
  const dialog = $(id);
  if (!dialog.open) dialog.showModal();
}

function closeDialog(id) {
  const dialog = $(id);
  if (dialog.open) dialog.close();
}

// ---------------------------------------------------------------- Tag laden/rendern

async function loadDay() {
  const { ok, data } = await api("GET", `/api/food-log/${state.date}`);
  if (!ok) {
    $("summary-msg").textContent = data.error || "Tag konnte nicht geladen werden";
    return;
  }
  state.day = data;
  render();
}

function render() {
  const label = new Date(`${state.date}T12:00:00`).toLocaleDateString("de-CH", {
    weekday: "short", day: "numeric", month: "short",
  });
  $("date-label").textContent = isToday() ? `Heute, ${label}` : label;
  renderTotals();
  renderMeals();
}

function renderTotals() {
  const totals = state.day.totals;
  const target = isToday() ? state.target : null;
  const rows = [
    ["Protein", "protein_g"],
    ["KH", "carbs_g"],
    ["Fett", "fat_g"],
  ].map(([name, key]) => macroRow(name, totals[key], target ? target[key] : null, "g"));
  const kcalText = target ? `/ ${round(target.kcal)} kcal` : "kcal";
  const remaining = target ? el("span", { class: "hint" }, `noch ${round(target.kcal - totals.kcal)} kcal`) : null;
  $("totals").replaceChildren(
    el("div", { class: "kcal-head" },
      el("div", {}, el("span", { class: "kcal-big" }, String(round(totals.kcal))), ` ${kcalText}`),
      remaining),
    ...(target ? [bar(totals.kcal, target.kcal)] : []),
    ...rows,
  );
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

function renderMeals() {
  const sections = MEALS.map(([meal, name]) => {
    const entries = state.day.meals[meal];
    const kcal = entries.reduce((sum, e) => sum + e.kcal, 0);
    const items = entries.map((entry) =>
      el("li", { onclick: () => openEntry(entry) },
        el("span", { class: "name" }, entry.label, el("span", { class: "sub" }, entryAmount(entry))),
        el("span", { class: "kcal" }, `${round(entry.kcal)} kcal`)));
    return el("section", { class: "card" },
      el("div", { class: "meal-head" },
        el("h2", {}, name),
        el("span", { class: "meal-kcal" }, entries.length ? `${round(kcal)} kcal` : "")),
      items.length ? el("ul", { class: "list" }, ...items) : null,
      el("div", { class: "meal-actions" },
        el("button", { class: "primary", onclick: () => openSearch(meal) }, "+ Hinzufügen"),
        el("button", { onclick: () => openTemplates(meal) }, "Vorlagen")));
  });
  $("meals").replaceChildren(...sections);
}

// ---------------------------------------------------------------- Soll (nur heute)

async function loadTarget() {
  // Soll aus dem Trainingskalender (geplante bzw. zurueckgemeldete Einheit)
  const { ok, data } = await api("GET", "/api/plan/today");
  if (!ok) {
    state.target = null;
    $("summary-msg").textContent = `Soll nicht verfügbar: ${data.error}`;
    return;
  }
  $("summary-msg").textContent = data.event
    ? `🏁 ${data.event.name} · ${data.event.label}: ${data.timing_hints[0] || ""}`
    : "";
  state.target = { kcal: data.nutrition.target_kcal, ...data.macros };
}

// ---------------------------------------------------------------- Suche

let searchTimer = null;
let searchSeq = 0;

function openSearch(meal) {
  state.meal = meal;
  $("search-title").textContent = `${MEAL_NAMES[meal]} – hinzufügen`;
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
  $("amount-save").textContent = entry ? "Speichern" : "Hinzufügen";
  $("amount-delete").hidden = !entry;
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
    : await api("POST", "/api/food-log", { date: state.date, meal: state.meal, food_id: food.id, grams });
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

async function openEntry(entry) {
  if (entry.food_id === null) {
    if (confirm(`„${entry.label}“ (${round(entry.kcal)} kcal) löschen?`)) await deleteEntry(entry);
    return;
  }
  state.meal = entry.meal;
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
  const body = { date: state.date, meal: state.meal, label: form.label };
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
  $("template-title").textContent = `Vorlagen – ${MEAL_NAMES[meal]}`;
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
  const { ok, data } = await api("POST", `/api/meal-templates/${template.id}/apply`, { date: state.date, meal: state.meal });
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
  try {
    await loadZxing();
    // Nur Produkt-Barcodes, gruendlich suchen. DecodeHintType exportiert das UMD-Bundle nicht:
    // 2 = POSSIBLE_FORMATS, 3 = TRY_HARDER.
    const { EAN_13, EAN_8, UPC_A, UPC_E } = ZXingBrowser.BarcodeFormat;
    const hints = new Map([[2, [EAN_13, EAN_8, UPC_A, UPC_E]], [3, true]]);
    const reader = new ZXingBrowser.BrowserMultiFormatReader(hints);
    // Hohe Aufloesung: iPhones stellen erst ab ~20 cm scharf, bei 640x480 (Safari-Default)
    // sind die Striche aus dieser Distanz zu wenige Pixel breit.
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
  $("prev-day").addEventListener("click", () => { state.date = shiftDate(state.date, -1); loadDay(); });
  $("next-day").addEventListener("click", () => { state.date = shiftDate(state.date, 1); loadDay(); });
  $("date-label").addEventListener("click", () => { state.date = localIso(new Date()); loadDay(); });

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

bindEvents();
loadTarget().then(loadDay).then(() => {
  // Einsprung von der Heute-Seite: ?add=<mahlzeit> oeffnet direkt die Suche
  const meal = new URLSearchParams(location.search).get("add");
  if (meal in MEAL_NAMES) openSearch(meal);
});
