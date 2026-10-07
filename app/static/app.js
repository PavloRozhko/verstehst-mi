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
  sprachhinweis.textContent = "";
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

// --- Spracheingabe ----------------------------------------------------------
// 1× tippen: Aufnahme startet. Nochmal tippen (oder nach 10 s): Aufnahme endet
// und wird an /api/sprache geschickt. Dort erkennt Whisper den Text.

const mikro = document.getElementById("mikro");
const sprachhinweis = document.getElementById("sprachhinweis");
const MAX_AUFNAHME_MS = 10000;

let aufnahme = null;     // MediaRecorder, solange aufgenommen wird
let stoppTimer = null;

// Der Browser erlaubt das Mikrofon nur über HTTPS oder auf localhost
const mikrofonMoeglich = Boolean(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);

mikro.addEventListener("click", () => {
  if (aufnahme) {
    aufnahme.stop();
  } else {
    aufnahmeStarten();
  }
});

async function aufnahmeStarten() {
  if (!mikrofonMoeglich) {
    sprachhinweis.textContent =
      "Das Mikrofon geht nur über HTTPS oder auf localhost. Bitte Text eintippen.";
    return;
  }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    sprachhinweis.textContent = "Kein Zugriff aufs Mikrofon. Bitte im Browser erlauben.";
    return;
  }

  const teile = [];
  aufnahme = new MediaRecorder(stream);
  aufnahme.addEventListener("dataavailable", (e) => teile.push(e.data));
  aufnahme.addEventListener("stop", () => {
    clearTimeout(stoppTimer);
    stream.getTracks().forEach((spur) => spur.stop());  // Mikrofon wieder freigeben
    const blob = new Blob(teile, { type: aufnahme.mimeType });
    aufnahme = null;
    mikro.classList.remove("aktiv");
    senden(blob);
  });

  aufnahme.start();
  stoppTimer = setTimeout(() => aufnahme?.stop(), MAX_AUFNAHME_MS);
  mikro.classList.add("aktiv");
  mikro.setAttribute("aria-label", "Aufnahme beenden");
  sprachhinweis.textContent = "Sprich jetzt … (nochmal 🎤 tippen zum Beenden)";
}

async function senden(blob) {
  mikro.disabled = true;
  mikro.setAttribute("aria-label", "Sprechen");
  sprachhinweis.textContent = "Wird erkannt …";

  try {
    const antwort = await fetch(`/api/sprache?derb=${derb.checked}`, {
      method: "POST",
      headers: { "Content-Type": blob.type || "application/octet-stream" },
      body: blob,
    });
    const daten = await antwort.json().catch(() => ({}));
    if (!antwort.ok) throw new Error(daten.detail || `HTTP ${antwort.status}`);

    if (!daten.erkannt) {
      sprachhinweis.textContent = "Nix verstanden. Bitte nochmal deutlich sprechen.";
      return;
    }
    sprachhinweis.textContent = `Erkannt: „${daten.erkannt}“ (${daten.sekunden} s)`;
    eingabe.value = "";  // sonst passt das Eingabefeld nicht zum Ergebnis
    anzeigen(daten);
  } catch (fehler) {
    sprachhinweis.textContent = "Hoppala: " + fehler.message;
  } finally {
    mikro.disabled = false;
  }
}

// --- Status: Anzahl der Einträge, Spracherkennung bereit? --------------------
fetch("/api/status")
  .then((r) => r.json())
  .then((s) => {
    document.getElementById("status").textContent = `${s.eintraege} Einträge im Wörterbuch`;
    if (!s.sprache) {
      mikro.disabled = true;
      mikro.title = "Spracherkennung ist nicht bereit";
    }
  })
  .catch(() => {});