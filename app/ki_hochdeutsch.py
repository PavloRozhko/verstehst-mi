"""KI-Übersetzung Dialekt -> Hochdeutsch (Experiment, Spike 2 vom 08.10.).

Zielgruppe: Menschen, die Deutsch lernen und in der Steiermark Dialekt hören.
Das Modell schreibt NUR Hochdeutsch – Dialekt kommt immer vom Benutzer.

Ablauf:
  1. Steht der Satz im Wörterbuch?  -> geprüfter Eintrag, kein LLM.
  2. Jedes Dialektwort im Wörterbuch suchen (app/vorschlag.woerter_suchen).
     Derbe Ausdrücke zählen mit (seit 09.10.): Wer "deppat" hört, soll die Bedeutung
     erfahren. Sie sind in der Antwort als derb markiert.
  3. Das Modell bekommt Satz + geprüfte Bedeutungen und schreibt den Satz auf Hochdeutsch.
  4. Prüfen (ohne LLM, nur Hinweise zum Nachsehen):
     - welche Wörter NICHT im Wörterbuch stehen (dort musste das Modell raten)
     - welche geprüfte Bedeutung in der Antwort nicht vorkommt (vielleicht widersprochen)
"""

import logging
import re
import threading
import time
from dataclasses import dataclass, field

from app.uebersetzer import SCHWELLE, STEIRISCH_DEUTSCH, normalisieren, varianten
from app.vorschlag import MODELL, OLLAMA, Wortpaar, ollama_chat, woerter_suchen

log = logging.getLogger("uvicorn.error")

SYSTEM = """Du hilfst Menschen, die Deutsch lernen und in der Steiermark leben.
Du bekommst einen Satz im steirischen Dialekt und eine Liste GEPRÜFTER Wörter aus einem
Wörterbuch (Steirisch = Hochdeutsch).

Schreib den Satz in einfachem, korrektem Hochdeutsch.

Regeln:
- Die Bedeutungen aus der Liste sind richtig. Verwende sie.
- Hat ein Wort mehrere Bedeutungen, wähle die, die im Satz passt.
- Gib nur den hochdeutschen Satz aus: keine Erklärung, keine Anführungszeichen."""


@dataclass
class KiUebersetzung:
    satz: str
    woerterbuch_phrase: str | None = None   # gefunden -> kein LLM nötig
    paare: list[Wortpaar] = field(default_factory=list)
    nicht_gefunden: list[str] = field(default_factory=list)
    text: str = ""
    bedeutung_fehlt: list[Wortpaar] = field(default_factory=list)
    sekunden: float = 0.0
    wie_hochdeutsch: list[str] = field(default_factory=list)   # siehe hochdeutsch_abtrennen
    quelle: str = ""            # "wörterbuch", "ki" oder "nur_woerter" (siehe uebersetzen_fuer_app)
    hinweis: str | None = None  # kurze Meldung für die Oberfläche, z. B. "KI lädt noch"


def phrase_suchen(uebersetzer, satz):
    for t in uebersetzer.uebersetzen(satz, STEIRISCH_DEUTSCH, mit_derb=True, limit=1):
        if t.typ == "phrase" and t.score >= SCHWELLE:
            return t.hochdeutsch
    return None


def frage_text(satz, paare):
    if paare:
        liste = "\n".join(f"- {p.dialekt} = {p.hochdeutsch}" for p in paare)
    else:
        liste = "(keine)"
    return f"Satz: {satz}\nGeprüfte Wörter:\n{liste}"


def ollama_fragen(satz, paare, modell=MODELL, url=OLLAMA):
    return ollama_chat(SYSTEM, frage_text(satz, paare), modell=modell, url=url)


def ohne_llm(satz, paare):
    """Vergleichswert: jedes gefundene Wort durch seine erste Bedeutung ersetzen.

    Ausdrücke aus zwei Wörtern ("auf d'Nocht") ersetzt der Vergleichswert nicht.
    """
    ersatz = {}
    for p in paare:
        if " " not in p.suchwort:
            ersatz.setdefault(p.suchwort, varianten(p.hochdeutsch, "wort")[0])
    return " ".join(ersatz.get(w, w) for w in normalisieren(satz).split())


def nicht_gefunden(satz, paare):
    gefunden = {w for p in paare for w in p.suchwort.split()}
    return [w for w in normalisieren(satz).split() if w not in gefunden]


def bedeutungswoerter(hochdeutsch):
    """'owa = herunter (auch: aber)' -> {'herunter', 'auch', 'aber'} (Klammern zählen mit)."""
    text = re.sub(r"[^\w\s]", " ", hochdeutsch.lower().replace("ß", "ss"))
    return {w for w in text.split() if len(w) >= 2}


def kommt_vor(wort, antwort_woerter):
    """Grober Vergleich über den Wortanfang: 'haben' passt zu 'habe', 'hast'."""
    stamm = wort[:max(3, len(wort) - 2)]
    return any(a.startswith(stamm) for a in antwort_woerter)


def bedeutung_fehlt(antwort, paare):
    """Paare, deren geprüfte Bedeutung in der Antwort nicht vorkommt (zum Nachsehen).

    Gibt es für ein Wort mehrere Einträge ("Pfusch", "pfuschn"), reicht einer davon.
    """
    antwort_woerter = normalisieren(antwort).split()

    def verwendet(p):
        return any(kommt_vor(w, antwort_woerter) for w in bedeutungswoerter(p.hochdeutsch))

    ok = {p.suchwort for p in paare if verwendet(p)}
    fehlend, gesehen = [], set()
    for p in paare:
        if p.suchwort not in ok and p.suchwort not in gesehen:
            gesehen.add(p.suchwort)
            fehlend.append(p)
    return fehlend


def uebersetzen(uebersetzer, satz, fragen=ollama_fragen, phrase_zuerst=True):
    """Kompletter Ablauf. phrase_zuerst=False nur für Tests mit "versteckten" Phrasen."""
    ergebnis = KiUebersetzung(satz=satz)
    if phrase_zuerst:
        ergebnis.woerterbuch_phrase = phrase_suchen(uebersetzer, satz)
        if ergebnis.woerterbuch_phrase:
            return ergebnis
    ergebnis.paare = woerter_suchen(uebersetzer, satz, STEIRISCH_DEUTSCH, mit_derb=True)
    ergebnis.nicht_gefunden = nicht_gefunden(satz, ergebnis.paare)
    ergebnis.text, ergebnis.sekunden = fragen(satz, ergebnis.paare)
    ergebnis.bedeutung_fehlt = bedeutung_fehlt(ergebnis.text, ergebnis.paare)
    return ergebnis


# --- Für die App (Backend, 09.10.) -------------------------------------------------------

# Antwortzeit im Normalfall: unter 1 s. Mehr Geduld hat am Handy niemand.
ANTWORT_TIMEOUT = 20      # Sekunden
# Das erste Laden des Modells dauert auf dem Jetson etwa 70 s
LADE_TIMEOUT = 300        # Sekunden

WOERTERBUCH = "wörterbuch"
KI = "ki"
NUR_WOERTER = "nur_woerter"


class KiModell:
    """Hält gemma3 bei Ollama dauerhaft im Speicher und fragt es nacheinander.

    - aufwaermen(): lädt das Modell (keep_alive = -1: nie wieder entladen)
    - Klappt eine Frage nicht, gilt das Modell als nicht bereit und wird im
      Hintergrund neu geladen. Bis dahin gibt es nur die Wortbedeutungen.
    """

    def __init__(self, modell=MODELL, url=OLLAMA):
        self.modell = modell
        self.url = url
        self.bereit = False
        self.laedt = False
        self.letzter_fehler = None              # Text des letzten Ladefehlers (für den Hinweis)
        self._sperre = threading.Lock()         # immer nur EINE Frage an den Jetson
        self._lade_sperre = threading.Lock()

    def _chat(self, frage, num_predict, timeout):
        return ollama_chat(SYSTEM, frage, modell=self.modell, url=self.url,
                           num_predict=num_predict, keep_alive=-1, timeout=timeout)

    def aufwaermen(self):
        """Lädt das Modell (blockiert). Gibt True zurück, wenn es geklappt hat."""
        if not self._lade_sperre.acquire(blocking=False):
            return False            # lädt schon in einem anderen Thread
        self.laedt = True
        start = time.perf_counter()
        try:
            with self._sperre:
                self._chat(frage_text("Servus!", []), num_predict=1, timeout=LADE_TIMEOUT)
            self.bereit = True
            self.letzter_fehler = None
            log.info("KI-Modell %s bereit nach %.1f s", self.modell, time.perf_counter() - start)
        except Exception as fehler:
            self.bereit = False
            self.letzter_fehler = str(fehler)
            log.warning("KI-Modell %s nicht erreichbar: %s", self.modell, fehler)
        finally:
            self.laedt = False
            self._lade_sperre.release()
        return self.bereit

    def im_hintergrund_aufwaermen(self):
        if not self.laedt:
            threading.Thread(target=self.aufwaermen, daemon=True).start()

    def fragen(self, satz, paare):
        """Wie ollama_fragen, aber mit kurzer Zeitgrenze und nur eine Frage gleichzeitig."""
        with self._sperre:
            return self._chat(frage_text(satz, paare), num_predict=60, timeout=ANTWORT_TIMEOUT)


def hochdeutsche_woerter(uebersetzer):
    """Alle Wörter aus der HOCHDEUTSCHEN Spalte der geprüften Daten ("der", "so", "und" …)."""
    return {w for e in uebersetzer.eintraege
            for w in normalisieren(e["zeile"]["hochdeutsch"]).split()}


def hochdeutsch_abtrennen(uebersetzer, ergebnis):
    """Unbekannte Wörter, die auch Hochdeutsch sind, nicht als "geraten" zeigen.

    "Der Hawara is deppat." -> "der" steht nicht als Dialektwort im Wörterbuch, kommt aber
    in der hochdeutschen Spalte vor. Lernende verstehen es; rot markiert verwirrt es nur.
    Grenze: Ein Dialektwort, das zufällig wie ein anderes hochdeutsches Wort aussieht,
    wird dann nicht mehr als unbekannt markiert.
    """
    hochdeutsch = hochdeutsche_woerter(uebersetzer)
    ergebnis.wie_hochdeutsch = [w for w in ergebnis.nicht_gefunden if w in hochdeutsch]
    ergebnis.nicht_gefunden = [w for w in ergebnis.nicht_gefunden if w not in hochdeutsch]
    return ergebnis


def uebersetzen_fuer_app(uebersetzer, satz, ki_modell):
    """Wie uebersetzen(), aber ohne Fehler nach außen. Setzt quelle und hinweis:

      wörterbuch   – der Satz steht geprüft im Wörterbuch (kein LLM)
      ki           – KI-Übersetzung (ungeprüft) aus geprüften Wortbedeutungen
      nur_woerter  – KI nicht bereit oder Fehler: nur die Wortbedeutungen
    """
    def nur_woerter(hinweis):
        ergebnis = KiUebersetzung(satz=satz, quelle=NUR_WOERTER, hinweis=hinweis)
        ergebnis.paare = woerter_suchen(uebersetzer, satz, STEIRISCH_DEUTSCH, mit_derb=True)
        ergebnis.nicht_gefunden = nicht_gefunden(satz, ergebnis.paare)
        return hochdeutsch_abtrennen(uebersetzer, ergebnis)

    phrase = phrase_suchen(uebersetzer, satz)
    if phrase:
        return KiUebersetzung(satz=satz, woerterbuch_phrase=phrase, quelle=WOERTERBUCH)

    if ki_modell is None:
        return nur_woerter("KI ist ausgeschaltet.")
    if not ki_modell.bereit:
        # Ist das letzte Laden gescheitert, läuft Ollama vermutlich nicht
        if getattr(ki_modell, "letzter_fehler", None) and not ki_modell.laedt:
            hinweis = "KI gerade nicht erreichbar – nur Wortbedeutungen."
        else:
            hinweis = "KI lädt noch – bitte gleich noch einmal versuchen."
        ki_modell.im_hintergrund_aufwaermen()
        return nur_woerter(hinweis)

    try:
        ergebnis = uebersetzen(uebersetzer, satz, fragen=ki_modell.fragen, phrase_zuerst=False)
    except Exception as fehler:
        log.warning("KI-Übersetzung fehlgeschlagen: %s", fehler)
        ki_modell.bereit = False
        ki_modell.im_hintergrund_aufwaermen()
        return nur_woerter("KI gerade nicht erreichbar – nur Wortbedeutungen.")
    if not ergebnis.text:
        return nur_woerter("KI hat nichts geantwortet – nur Wortbedeutungen.")
    ergebnis.quelle = KI
    return hochdeutsch_abtrennen(uebersetzer, ergebnis)
