"use strict";

// Gemeinsame Helfer der Formular-Seiten (Profil, Check-ins). Seiten liegen unter <praefix>/<seite>/.

const $ = (id) => document.getElementById(id);

async function api(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  // relativ aufloesen, damit die App auch unter einem Pfad-Praefix (z.B. /cpc/) laeuft
  const response = await fetch(`..${path}`, options);
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

function localToday() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
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

// ⓘ-Link auf einen Abschnitt der Erklaer-Seite
function infoLink(anchor) {
  const link = el("a", "ⓘ", "info");
  link.href = `../hilfe/#${anchor}`;
  link.setAttribute("aria-label", "Erklärung");
  return link;
}
