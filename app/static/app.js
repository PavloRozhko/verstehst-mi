// Oberfläche für verstehst-mi: schickt die Eingabe an /api/uebersetzen
// und zeigt das Ergebnis an. Kein Framework, nur einfaches JavaScript.

const eingabe = document.getElementById("eingabe");
const formular = document.getElementById("formular");
const derb = document.getElementById("derb");
const ergebnis = document.getElementById("ergebnis");
const von = document.getElementById("von");
const nach = document.getElementById("nach");

let richtung = "st-de";
let timer = null;

// --- Richtung tauschen ---------------------------------------------------
document.getElementById("tauschen").addEventListener("click", () => {
  richtung = richtung === "st-de" ? "de-st" : "st-de";
  const steirischZuerst = richtung === "st-de";
  von.textContent = steirischZuerst ? "Steirisch" : "Hochdeutsch";
  nach.textContent = steirischZuerst ? "Hochdeutsch" : "Steirisch";
  eingabe.placeholder = steirischZuerst
    ? "z. B. Griaß di, wia geht's da?"
    : "z. B. Ich habe Hunger";
  suchen();
});

// --- Suchen: beim Tippen (mit kurzer Pause) und bei Enter ------------------
eingabe.addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(suchen, 300);
});

formular.addEventListener("submit", (e) => {
  e.preventDefault();
  suchen();
});

derb.addEventListener("change", suchen);

async function suchen() {
  const text = eingabe.value.trim();
  if (!text) {
    ergebnis.replaceChildren();
    return;
  }

  const parameter = new URLSearchParams({ text, richtung, derb: derb.checked });
  try {
    const antwort = await fetch(`/api/uebersetzen?${parameter}`);
    if (!antwort.ok) throw new Error(`HTTP ${antwort.status}`);
    const daten = await antwort.json();
    // Nur anzeigen, wenn sich die Eingabe inzwischen nicht geändert hat
    if (daten.text === eingabe.value.trim()) anzeigen(daten);
  } catch (fehler) {
    ergebnis.replaceChildren(element("p", "leer", "Server nicht erreichbar: " + fehler.message));
  }
}

// --- Anzeige ------------------------------------------------------------------
// Texte werden immer mit textContent gesetzt (nie innerHTML), damit
// Eingaben nie als HTML ausgeführt werden.

function element(tag, klasse, text) {
  const el = document.createElement(tag);
  if (klasse) el.className = klasse;
  if (text !== undefined) el.textContent = text;
  return el;
}

function ziel(t) {
  return richtung === "st-de" ? t.hochdeutsch : t.dialekt;
}

function quelle(t) {
  return richtung === "st-de" ? t.dialekt : t.hochdeutsch;
}

function karte(t, { haupt = false, anklickbar = false } = {}) {
  const k = element(anklickbar ? "button" : "div", haupt ? "karte haupt" : "karte");
  if (anklickbar) k.type = "button";
  k.append(element("div", "ziel", ziel(t)), element("div", "quelle", quelle(t)));

  const info = element("div", "info");
  info.append(element("span", "marke", "✅ geprüft"));
  if (t.thema) info.append(element("span", "marke", t.thema));
  if (t.art === "ähnlich") info.append(` Ähnlichkeit ${Math.round(t.score * 100)} %`);
  k.append(info);

  // Klick auf einen Vorschlag übernimmt ihn als neue Eingabe
  if (anklickbar) {
    k.addEventListener("click", () => {
      eingabe.value = quelle(t);
      suchen();
    });
  }
  return k;
}

function abschnitt(titel, treffer, optionen) {
  if (treffer.length === 0) return [];
  return [element("h2", null, titel), ...treffer.map((t) => karte(t, optionen))];
}

function anzeigen(daten) {
  const teile = [
    ...abschnitt("Übersetzung", daten.uebersetzungen, { haupt: true }),
    ...abschnitt("Meintest du …?", daten.vorschlaege, { anklickbar: true }),
    ...abschnitt("In Sätzen", daten.beispiele, { anklickbar: true }),
  ];

  if (teile.length === 0) {
    teile.push(element("p", "leer",
      "Kein Treffer im Wörterbuch. Probier eine andere Schreibweise oder ein einzelnes Wort."));
  }
  ergebnis.replaceChildren(...teile);
}

// --- Status: Anzahl der Einträge -------------------------------------------
fetch("/api/status")
  .then((r) => r.json())
  .then((s) => {
    document.getElementById("status").textContent = `${s.eintraege} Einträge im Wörterbuch`;
  })
  .catch(() => {});