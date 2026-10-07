"use strict";

// Kleines Linienchart als Inline-SVG (ohne Bibliothek). Farben ueber CSS-Klassen in forms.css.
// points: [{ date: "YYYY-MM-DD", value }], aeltester Punkt zuerst. Optionen: { target, unit, decimals, label }
function lineChart(container, points, options = {}) {
  const { target = null, unit = "", decimals = 1, label = "" } = options;
  // Breite = Containerbreite, damit Schrift in echten Pixeln skaliert; bei Groessenaenderung (auch Reiter einblenden) neu zeichnen
  container._chart = { points, options };
  if (!container._observer) {
    container._observer = new ResizeObserver(() => {
      if (container.clientWidth && container.clientWidth !== container._width) lineChart(container, ...Object.values(container._chart));
    });
    container._observer.observe(container);
  }
  container._width = container.clientWidth;
  container.replaceChildren();
  if (!points.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "Noch keine Daten.";
    container.append(empty);
    return;
  }

  const NS = "http://www.w3.org/2000/svg";
  const node = (tag, attrs = {}, text) => {
    const n = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) n.setAttribute(key, value);
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const W = Math.max(260, Math.min(container.clientWidth || 560, 760)), H = Math.round(Math.max(130, Math.min(W * 0.3, 190)));
  const left = 44, right = 16, top = 14, bottom = 26;
  const num = (v) => Number(v).toFixed(decimals).replace(".", ",");
  const short = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString("de-CH", { day: "numeric", month: "numeric" });

  const values = points.map((p) => p.value).concat(target === null ? [] : [target]);
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  if (lo === hi) { lo -= 1; hi += 1; }
  const margin = (hi - lo) * 0.1;
  lo -= margin;
  hi += margin;
  const times = points.map((p) => new Date(`${p.date}T12:00:00`).getTime());
  const t0 = times[0];
  const t1 = times[times.length - 1];
  const x = (t) => (t1 === t0 ? (left + W - right) / 2 : left + ((t - t0) / (t1 - t0)) * (W - left - right));
  const y = (v) => top + ((hi - v) / (hi - lo)) * (H - top - bottom);

  const last = points[points.length - 1];
  const svg = node("svg", {
    viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `${label}: ${points.length} Messungen, zuletzt ${num(last.value)} ${unit} am ${short(last.date)}`,
  });
  for (const tick of [lo + margin, (lo + hi) / 2, hi - margin]) {
    svg.append(node("line", { class: "grid", x1: left, x2: W - right, y1: y(tick), y2: y(tick) }),
      node("text", { x: left - 6, y: y(tick) + 4, "text-anchor": "end" }, num(tick)));
  }
  if (target !== null) {
    svg.append(node("line", { class: "target", x1: left, x2: W - right, y1: y(target), y2: y(target) }),
      node("text", { x: W - right, y: y(target) - 4, "text-anchor": "end" }, `Ziel ${num(target)}`));
  }
  svg.append(node("polyline", { class: "line", points: points.map((p, i) => `${x(times[i])},${y(p.value)}`).join(" ") }));
  points.forEach((p, i) => {
    const dot = node("circle", { class: "dot", cx: x(times[i]), cy: y(p.value), r: 3.5 });
    dot.append(node("title", {}, `${short(p.date)}: ${num(p.value)} ${unit}`));
    svg.append(dot);
  });
  svg.append(node("text", { x: x(t0), y: H - 6, "text-anchor": t1 === t0 ? "middle" : "start" }, short(points[0].date)));
  if (t1 !== t0) svg.append(node("text", { x: x(t1), y: H - 6, "text-anchor": "end" }, short(last.date)));
  container.append(svg);
}
