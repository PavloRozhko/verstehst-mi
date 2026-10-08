"""KI-Übersetzung Dialekt -> Hochdeutsch (Experiment, Spike 2 vom 08.10.).

Zielgruppe: Menschen, die Deutsch lernen und in der Steiermark Dialekt hören.
Das Modell schreibt NUR Hochdeutsch – Dialekt kommt immer vom Benutzer.

Ablauf:
  1. Steht der Satz im Wörterbuch?  -> geprüfter Eintrag, kein LLM.
  2. Jedes Dialektwort im Wörterbuch suchen (app/vorschlag.woerter_suchen).
  3. Das Modell bekommt Satz + geprüfte Bedeutungen und schreibt den Satz auf Hochdeutsch.
  4. Prüfen (ohne LLM, nur Hinweise zum Nachsehen):
     - welche Wörter NICHT im Wörterbuch stehen (dort musste das Modell raten)
     - welche geprüfte Bedeutung in der Antwort nicht vorkommt (vielleicht widersprochen)
"""

import re
from dataclasses import dataclass, field

from app.uebersetzer import SCHWELLE, STEIRISCH_DEUTSCH, normalisieren, varianten
from app.vorschlag import MODELL, OLLAMA, Wortpaar, ollama_chat, woerter_suchen

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


def phrase_suchen(uebersetzer, satz):
    for t in uebersetzer.uebersetzen(satz, STEIRISCH_DEUTSCH, limit=1):
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
    ergebnis.paare = woerter_suchen(uebersetzer, satz, STEIRISCH_DEUTSCH)
    ergebnis.nicht_gefunden = nicht_gefunden(satz, ergebnis.paare)
    ergebnis.text, ergebnis.sekunden = fragen(satz, ergebnis.paare)
    ergebnis.bedeutung_fehlt = bedeutung_fehlt(ergebnis.text, ergebnis.paare)
    return ergebnis
