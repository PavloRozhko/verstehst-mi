// Oberfläche für verstehst-mi: schickt die Eingabe an /api/uebersetzen
// und zeigt das Ergebnis an. Kein Framework, nur einfaches JavaScript.
//
// Aufbau dieser Datei:
//   Suchen       – Eingabe (Tippen, Enter, Richtung, derb) -> /api/uebersetzen
//   Anzeige      – Karten für Übersetzung, "Meintest du …?" und Beispiele
//   KI           – Knopf "Ganzen Satz mit KI übersetzen" -> /api/ki_uebersetzung
//   Sprache      – Mikrofon aufnehmen -> /api/sprache (Whisper)
//   Status       – Fußzeile: Einträge, KI bereit?

// --- Elemente der Seite und Zustand -------------------------------------------
const eingabe = document.getElementById("eingabe");
const formular = document.getElementById("formular");
const derb = document.getElementById("derb");
const ergebnis = document.getElementById("ergebnis");
const von = document.getElementById("von");
const nach = document.getElementById("nach");
const mikro = document.getElementById("mikro");
const sprachhinweis = document.getElementById("sprachhinweis");

let richtung = "st-de";  // "st-de" = Steirisch -> Hochdeutsch, "de-st" = umgekehrt
let timer = null;        // wartet nach dem Tippen kurz, bevor gesucht wird

// --- Richtung tauschen ---------------------------------------------------
// Klick auf ⇄: Richtung, Beschriftungen und Beispiel im Feld wechseln, neu suchen.
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
// Beim Tippen: 300 ms warten, dann suchen (nicht bei jedem Buchstaben eine Anfrage).
eingabe.addEventListener("input", () => {
  sprachhinweis.textContent = "";
  clearTimeout(timer);
  timer = setTimeout(suchen, 300);
});

// Enter: sofort suchen, ohne die Seite neu zu laden.
formular.addEventListener("submit", (e) => {
  e.preventDefault();
  suchen();
});

// Schalter "derbe Ausdrücke": gleiche Eingabe neu suchen.
derb.addEventListener("change", suchen);

// Fragt /api/uebersetzen nach dem Text im Eingabefeld und zeigt das Ergebnis an.
// Ist das Feld leer, wird das alte Ergebnis gelöscht.
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
    if (daten.text === eingabe.value.trim()) anzeigen(daten, text);
  } catch (fehler) {
    ergebnis.replaceChildren(element("p", "leer", "Server nicht erreichbar: " + fehler.message));
  }
}

// --- Anzeige ------------------------------------------------------------------
// Texte werden immer mit textContent gesetzt (nie innerHTML), damit
// Eingaben nie als HTML ausgeführt werden.

// Erzeugt ein HTML-Element mit CSS-Klasse und Text (Text immer sicher als textContent).
function element(tag, klasse, text) {
  const el = document.createElement(tag);
  if (klasse) el.className = klasse;
  if (text !== undefined) el.textContent = text;
  return el;
}

// Der Text in der Zielsprache eines Treffers (je nach Richtung).
function ziel(t) {
  return richtung === "st-de" ? t.hochdeutsch : t.dialekt;
}

// Der Text in der Ausgangssprache eines Treffers (je nach Richtung).
function quelle(t) {
  return richtung === "st-de" ? t.dialekt : t.hochdeutsch;
}

// Eine Karte für einen Treffer: Übersetzung groß, Original klein, darunter Marken.
// haupt = hervorgehoben (exakter Treffer); anklickbar = Klick übernimmt den Treffer.
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

// Überschrift + Karten für eine Gruppe von Treffern (leer, wenn es keine gibt).
function abschnitt(titel, treffer, optionen) {
  if (treffer.length === 0) return [];
  return [element("h2", null, titel), ...treffer.map((t) => karte(t, optionen))];
}

// Zeigt das Suchergebnis an. Ohne exakten Treffer (ab 2 Wörtern, nur Steirisch ->
// Hochdeutsch) kommt darunter der KI-Knopf; in die andere Richtung ein Hinweis.
function anzeigen(daten, text) {
  const teile = [
    ...abschnitt("Übersetzung", daten.uebersetzungen, { haupt: true }),
    ...abschnitt("Meintest du …?", daten.vorschlaege, { anklickbar: true }),
    ...abschnitt("In Sätzen", daten.beispiele, { anklickbar: true }),
  ];

  const kiMoeglich = richtung === "st-de" && daten.uebersetzungen.length === 0
    && text.trim().split(/\s+/).length >= 2;

  if (teile.length === 0) {
    teile.push(element("p", "leer", kiMoeglich
      ? "Der ganze Satz steht nicht im Wörterbuch."
      : "Kein Treffer im Wörterbuch. Probier eine andere Schreibweise oder ein einzelnes Wort."));
  }
  if (kiMoeglich) teile.push(kiBereich(text));
  // Gegenrichtung: bewusst keine KI (sie würde Dialekt erfinden, Spike 1)
  const satzOhneTreffer = richtung === "de-st" && daten.uebersetzungen.length === 0
    && text.trim().split(/\s+/).length >= 2;
  if (satzOhneTreffer) {
    teile.push(element("p", "fussnote",
      "Ganze Sätze übersetzt die KI nur Steirisch → Hochdeutsch. " +
      "In die andere Richtung würde sie Dialekt erfinden."));
  }
  ergebnis.replaceChildren(...teile);
}

// --- KI-Übersetzung Steirisch -> Hochdeutsch (/api/ki_uebersetzung) ------------
// Nur auf Knopfdruck: der Jetson rechnet immer nur EINE KI-Anfrage gleichzeitig.
// Die KI setzt den Satz aus GEPRÜFTEN Wortbedeutungen zusammen. Was sie dabei
// raten musste, wird markiert – das Ergebnis heißt immer "ungeprüft".

// Vereinheitlicht ein Wort wie app/uebersetzer.normalisieren() im Server
// ("geht's" -> "gehts"), damit die Markierungen zu den Wörtern der API passen.
function normalisieren(wort) {
  return wort.toLowerCase().replace(/['´`’‘]/g, "").replace(/ß/g, "ss")
    .replace(/[^\p{L}\p{N}_]/gu, "");
}

// Der Bereich mit dem Knopf "Ganzen Satz mit KI übersetzen" für diesen Text.
function kiBereich(text) {
  const bereich = element("section", "ki-bereich");
  const knopf = element("button", "ki-knopf", "🤖 Ganzen Satz mit KI übersetzen");
  knopf.type = "button";
  knopf.addEventListener("click", () => kiFragen(text, bereich, knopf));  // Klick: KI fragen
  bereich.append(knopf);
  return bereich;
}

// Fragt /api/ki_uebersetzung und ersetzt den Knopf durch das Ergebnis.
// Bei einem Fehler bleibt der Knopf als "Nochmal versuchen" stehen.
async function kiFragen(text, bereich, knopf) {
  knopf.disabled = true;
  knopf.textContent = "🤖 KI übersetzt …";
  try {
    const antwort = await fetch(`/api/ki_uebersetzung?${new URLSearchParams({ text })}`);
    const daten = await antwort.json().catch(() => ({}));
    if (!antwort.ok) throw new Error(daten.detail || `HTTP ${antwort.status}`);
    if (bereich.isConnected) bereich.replaceChildren(...kiErgebnis(daten, text, bereich));
  } catch (fehler) {
    knopf.disabled = false;
    knopf.textContent = "🤖 Nochmal versuchen";
    bereich.append(element("p", "warnung", "Hoppala: " + fehler.message));
  }
}

// Der Satz mit farbig markierten Wörtern: geprüft (grün) / abgeleitet (gelb) /
// unbekannt (rot). Leerzeichen und Satzzeichen bleiben wie eingegeben.
function satzMarkiert(text, daten) {
  const geprueft = new Set();
  const abgeleitet = new Set();
  for (const w of daten.woerter) {
    for (const teil of w.wort.split(" ")) (w.abgeleitet ? abgeleitet : geprueft).add(teil);
  }
  const unbekannt = new Set(daten.nicht_gefunden);

  const satz = element("div", "quelle satz");
  for (const stueck of text.split(/(\s+)/)) {
    const n = normalisieren(stueck);
    let klasse = null;
    if (unbekannt.has(n)) klasse = "wort-unbekannt";
    else if (geprueft.has(n)) klasse = "wort-geprueft";
    else if (abgeleitet.has(n)) klasse = "wort-abgeleitet";
    satz.append(klasse ? element("span", klasse, stueck) : stueck);
  }
  return satz;
}

// Liste "Wörter im Satz": jedes gefundene Wort mit geprüfter Bedeutung und Marken
// (geprüft / abgeleitet / derb), danach die Wörter, die nicht im Wörterbuch stehen.
function wortListe(daten) {
  const liste = element("ul", "wortliste");
  for (const w of daten.woerter) {
    const li = element("li");
    if (w.abgeleitet) {
      li.append(element("span", "wort-abgeleitet", w.wort), ` → ${w.dialekt} = ${w.hochdeutsch} `,
        element("span", "marke marke-abgeleitet", "abgeleitet"));
    } else {
      li.append(element("span", "wort-geprueft", w.dialekt), ` = ${w.hochdeutsch} `,
        element("span", "marke", "✅ geprüft"));
    }
    if (w.derb) li.append(element("span", "marke marke-derb", "derb"));
    liste.append(li);
  }
  for (const wort of daten.nicht_gefunden) {
    const li = element("li");
    li.append(element("span", "wort-unbekannt", wort), " – nicht im Wörterbuch");
    liste.append(li);
  }
  return liste;
}

// Baut die Anzeige für die Antwort von /api/ki_uebersetzung, je nach quelle:
//   "wörterbuch" – der Satz steht geprüft im Wörterbuch (grüne Karte)
//   "ki"         – KI-Übersetzung, gelb, "ungeprüft", mit Warnung bei fehlender Bedeutung
//   sonst        – KI nicht verfügbar: nur Wort für Wort, Hinweis + "Nochmal versuchen"
function kiErgebnis(daten, text, bereich) {
  if (daten.quelle === "wörterbuch") {
    const k = element("div", "karte haupt");
    k.append(element("div", "ziel", daten.uebersetzung), element("div", "quelle", text));
    const info = element("div", "info");
    info.append(element("span", "marke", "✅ geprüft (ganzer Satz im Wörterbuch)"));
    k.append(info);
    return [element("h2", null, "Übersetzung"), k];
  }

  const teile = [];
  if (daten.quelle === "ki") {
    const k = element("div", "karte ki");
    k.append(element("div", "ziel", daten.uebersetzung), satzMarkiert(text, daten));
    const info = element("div", "info");
    info.append(element("span", "marke marke-ki", "🤖 KI-Übersetzung (ungeprüft)"),
      ` ${daten.sekunden} s`);
    k.append(info);
    teile.push(element("h2", null, "KI-Übersetzung"), k);
    if (daten.bedeutung_fehlt.length > 0) {
      teile.push(element("p", "warnung",
        `⚠ Bitte prüfen: Die geprüfte Bedeutung von „${daten.bedeutung_fehlt.join("“, „")}“ ` +
        "kommt in der KI-Übersetzung nicht vor."));
    }
  } else {
    const k = element("div", "karte");
    k.append(satzMarkiert(text, daten));
    teile.push(element("h2", null, "Wort für Wort"), k);
    const hinweis = element("p", "warnung", daten.hinweis || "Keine KI-Übersetzung.");
    const nochmal = element("button", "ki-knopf klein", "🤖 Nochmal versuchen");
    nochmal.type = "button";
    nochmal.addEventListener("click", () => kiFragen(text, bereich, nochmal));  // erneut fragen
    hinweis.append(" ", nochmal);
    teile.push(hinweis);
  }

  teile.push(element("h2", null, "Wörter im Satz"), wortListe(daten));
  if (daten.nicht_gefunden.length > 0 && daten.quelle === "ki") {
    teile.push(element("p", "fussnote",
      "Rot markierte Wörter kennt das Wörterbuch nicht – dort hat die KI geraten."));
  }
  return teile;
}

// --- Spracheingabe ----------------------------------------------------------
// 1× tippen: Aufnahme startet. Nochmal tippen (oder nach 10 s): Aufnahme endet
// und wird an /api/sprache geschickt. Dort erkennt Whisper den Text.

const MAX_AUFNAHME_MS = 10000;

let aufnahme = null;     // MediaRecorder, solange aufgenommen wird
let stoppTimer = null;

// Der Browser erlaubt das Mikrofon nur über HTTPS oder auf localhost
const mikrofonMoeglich = Boolean(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);

// Klick auf 🎤: Aufnahme starten – oder, wenn sie schon läuft, beenden.
mikro.addEventListener("click", () => {
  if (aufnahme) {
    aufnahme.stop();
  } else {
    aufnahmeStarten();
  }
});

// Startet die Aufnahme. Am Ende (Klick oder nach 10 s) wird sie mit senden() verschickt.
// Ohne HTTPS oder ohne Erlaubnis gibt es nur einen Hinweis.
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

  // Neue Aufnahme = neuer Satz: altes Eingabefeld und altes Ergebnis weg,
  // sonst steht bei "Nix verstanden" noch der vorige Satz da
  clearTimeout(timer);
  eingabe.value = "";
  ergebnis.replaceChildren();

  const teile = [];
  aufnahme = new MediaRecorder(stream);
  // Der Browser liefert die Aufnahme in Stücken – alle sammeln
  aufnahme.addEventListener("dataavailable", (e) => teile.push(e.data));
  // Aufnahme zu Ende: Mikrofon freigeben und die Aufnahme verschicken
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

// Schickt die Aufnahme an /api/sprache. Der erkannte Text kommt ins Eingabefeld
// (zum Korrigieren), das Ergebnis wird wie bei getipptem Text angezeigt.
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
    // Erkannten Text ins Eingabefeld schreiben: Whisper verhört sich oft (Sprachtest
    // vom 11.10.). So kann man den Text korrigieren – die Suche läuft dann von selbst neu.
    eingabe.value = daten.erkannt;
    sprachhinweis.textContent =
      `Erkannt in ${daten.sekunden} s. Falsch verstanden? Text oben korrigieren.`;
    anzeigen(daten, daten.erkannt);
  } catch (fehler) {
    sprachhinweis.textContent = "Hoppala: " + fehler.message;
  } finally {
    mikro.disabled = false;
  }
}

// --- Status: Anzahl der Einträge, Spracherkennung bereit? --------------------
// Einmal beim Laden der Seite: Fußzeile füllen; ohne Whisper wird 🎤 gesperrt.
fetch("/api/status")
  .then((r) => r.json())
  .then((s) => {
    document.getElementById("status").textContent =
      `${s.eintraege} Einträge im Wörterbuch · KI ${s.ki ? "bereit" : "nicht bereit"}`;
    if (!s.sprache) {
      mikro.disabled = true;
      mikro.title = "Spracherkennung ist nicht bereit";
    }
  })
  .catch(() => {});