"use strict";

// Gemeinsame Navigation. Seite markiert sich mit <body data-nav="<key>">.
// Links relativ zum Prefix (Server haengt unter /cpc/), daher Basis aus der eigenen Script-URL.
(() => {
  const base = new URL("../", document.currentScript.src);

  const ICONS = {
    heute: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4"/>',
    training: '<circle cx="5.5" cy="17" r="3.5"/><circle cx="18.5" cy="17" r="3.5"/><path d="M5.5 17 9 9h6l3.5 8M9 9l3 8M14 6h2.5"/>',
    ernaehrung: '<path d="M12 7c-2-2-6-1-6 4 0 4 3 8 6 8s6-4 6-8c0-5-4-6-6-4zM12 7c0-2 1-3 3-4"/>',
    profil: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.5-6.5 8-6.5s8 2.5 8 6.5"/>',
    hilfe: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 1-1 1.7M12 17h.01"/>',
  };

  const ITEMS = [
    { key: "heute", label: "Heute", path: "" },
    { key: "training", label: "Training", path: "training/" },
    { key: "ernaehrung", label: "Ernährung", path: "ernaehrung/" },
    { key: "profil", label: "Profil", path: "profil/" },
    { key: "hilfe", label: "Hilfe", path: "hilfe/" },
  ];

  const active = document.body.dataset.nav;
  const nav = document.createElement("nav");
  nav.className = "nav";
  nav.setAttribute("aria-label", "Hauptnavigation");

  const brand = document.createElement("div");
  brand.className = "nav-brand";
  brand.textContent = "Alpenpässe";
  nav.append(brand);

  for (const item of ITEMS) {
    const link = document.createElement("a");
    link.className = "nav-item";
    link.href = new URL(item.path, base).href;
    if (item.key === active) link.setAttribute("aria-current", "page");
    link.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[item.key]}</svg>`;
    link.append(Object.assign(document.createElement("span"), { textContent: item.label }));
    nav.append(link);
  }

  const logout = document.createElement("form");
  logout.className = "nav-logout";
  logout.method = "post";
  logout.action = new URL("logout", base).href;
  logout.append(Object.assign(document.createElement("button"), { type: "submit", textContent: "Abmelden" }));
  nav.append(logout);

  document.body.prepend(nav);
})();
