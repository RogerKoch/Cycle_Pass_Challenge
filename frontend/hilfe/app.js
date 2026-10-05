"use strict";

const MARKED_URL = "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js";

function loadMarked() {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = MARKED_URL;
    script.onload = resolve;
    script.onerror = () => reject(new Error("Darstellung konnte nicht geladen werden"));
    document.head.append(script);
  });
}

async function render() {
  const content = document.getElementById("content");
  try {
    const [text] = await Promise.all([fetch("inhalt.md").then((r) => r.text()), loadMarked()]);
    content.innerHTML = marked.parse(text);
    // Anker (#ftp usw.) erst nach dem Rendern vorhanden
    if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
  } catch (error) {
    content.innerHTML = "";
    content.append(Object.assign(document.createElement("p"), { className: "msg", textContent: error.message }));
  }
}

render();
