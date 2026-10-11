"use strict";

// Kommentar-Karte fuer einen Tag (ein Freitext pro Datum, leer speichern = loeschen).
// base: Praefix der API relativ zur Seite ("" auf Heute, "../" auf Training/Ernaehrung).
async function mountDayComment(container, { base, date }) {
  const url = `${base}api/day-comments/${date}`;
  const heading = document.createElement("h2");
  heading.textContent = "📝 Kommentar";
  const area = document.createElement("textarea");
  area.rows = 3;
  area.maxLength = 2000;
  area.placeholder = "Wie war der Tag? Beine, Schlaf, Besonderes …";
  area.style.width = "100%";
  const save = document.createElement("button");
  save.type = "button";
  save.textContent = "Speichern";
  const msg = document.createElement("p");
  msg.className = "hint";
  container.replaceChildren(heading, area, save, msg);
  try {
    const response = await fetch(url);
    area.value = response.ok ? (await response.json()).text : "";
  } catch {
    msg.textContent = "Kommentar nicht ladbar.";
  }
  save.addEventListener("click", async () => {
    try {
      const response = await fetch(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: area.value }),
      });
      const data = await response.json().catch(() => ({}));
      if (response.ok) area.value = data.text;
      msg.textContent = response.ok ? "gespeichert" : data.error || "Speichern fehlgeschlagen";
    } catch {
      msg.textContent = "Speichern fehlgeschlagen";
    }
  });
}
