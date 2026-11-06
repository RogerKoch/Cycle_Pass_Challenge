"use strict";

// Gemeinsames Eingabeverhalten: Wert beim Antippen markieren (direkt ueberschreiben) und
// vorbelegte Werte als "Vorschlag" kennzeichnen (CSS: input.suggested), bis der Nutzer tippt.

const SUGGESTABLE = 'input:not([type="checkbox"]):not([type="radio"]):not([type="date"]):not([type="range"]):not([type="file"]):not([type="hidden"])';

function markSuggestion(input) {
  input.classList.toggle("suggested", input.matches(SUGGESTABLE) && input.value !== "" && !input.readOnly && !input.disabled);
}

// Per Skript gesetzte Werte (Standardwerte, Daten vom Server) = Vorschlag; Tippen des Nutzers ruft den Setter nicht auf
const valueProperty = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
Object.defineProperty(HTMLInputElement.prototype, "value", {
  ...valueProperty,
  set(newValue) {
    valueProperty.set.call(this, newValue);
    markSuggestion(this);
  },
});

document.addEventListener("input", (event) => {
  if (event.target.classList) event.target.classList.remove("suggested");
});

document.addEventListener("focusin", (event) => {
  const input = event.target;
  if (input.matches && input.matches(SUGGESTABLE)) setTimeout(() => input.select(), 0); // iOS markiert erst nach dem Tap
});

document.addEventListener("reset", (event) => {
  setTimeout(() => event.target.querySelectorAll("input").forEach(markSuggestion), 0);
});

document.addEventListener("DOMContentLoaded", () => document.querySelectorAll("input").forEach(markSuggestion));
