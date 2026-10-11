"""Spike 1 (Experiment, NICHT in der App): Hochdeutsch -> Steirisch mit dem Sprachmodell.

Ergebnis am 07./08.10.: no-go. Das Modell hat Dialektwörter erfunden ("zbus", "kommet").
Der Code bleibt nur, damit der Versuch nachvollziehbar ist (scripts/rag_test.py,
docs/experimente.md). In der App gibt es die KI nur für Steirisch -> Hochdeutsch
(app/ki_hochdeutsch.py).

Ablauf (RAG = "Retrieval-Augmented Generation", also: erst nachschlagen, dann schreiben):
  1. Steht der ganze Satz schon im Wörterbuch?  -> dann gilt der geprüfte Eintrag, kein LLM.
  2. Jedes Wort im Wörterbuch suchen (nur sichere Treffer, app/wortsuche.py).
  3. Das Sprachmodell bekommt Satz + gefundene Wörter und darf NUR diese als Dialekt verwenden.
  4. Jedes Wort der Antwort wird geprüft und markiert (siehe markieren()).

Regel "B" (vereinbart am 08.10.): Verben aus der Liste darf das Modell beugen
("hom" -> "hob"). Solche Formen sind NICHT geprüft und werden eigens markiert.
"""

from dataclasses import dataclass, field

from app.ollama import MODELL, OLLAMA, ollama_chat
from app.uebersetzer import (
    DEUTSCH_STEIRISCH,
    SCHWELLE,
    Uebersetzer,
    aehnlichkeit,
    normalisieren,
    varianten,
)
from app.wortsuche import Wortpaar, woerter_suchen

# Ein Antwortwort gilt als gebeugte Form eines gefundenen Wortes, wenn es gleich beginnt
# und ähnlich ist ("hob"/"hobn"/"host" ~ "hom"). Grob, deshalb nur als "bitte prüfen" markiert.
ABGELEITET_AB = 0.5
GLEICHER_ANFANG = 2     # Zeichen

# Markierungen für jedes Wort der Antwort
GEPRUEFT = "geprüft"            # steht so in der Liste der gefundenen Wörter
WOERTERBUCH = "wörterbuch"      # geprüftes Wort, aber nicht für diesen Satz gefunden
HOCHDEUTSCH = "hochdeutsch"     # unverändert aus dem Originalsatz übernommen
ABGELEITET = "abgeleitet"       # vermutlich gebeugte Form eines gefundenen Wortes (Regel B)
VERDAECHTIG = "verdächtig"      # nichts davon -> möglicherweise erfunden

SYSTEM = """Du überträgst einen hochdeutschen Satz in den steirischen Dialekt.
Du bekommst eine Liste GEPRÜFTER Wörter aus einem Wörterbuch (Hochdeutsch = Steirisch).

Regeln:
- Für steirische Wörter verwendest du NUR Wörter aus der Liste.
- Verben aus der Liste darfst du an den Satz anpassen (Person, Zeit).
- Für alles, was nicht in der Liste steht, schreibst du das hochdeutsche Wort aus dem Originalsatz.
- Erfinde keine Dialektwörter, auch wenn du welche kennst.
- Gib nur den fertigen Satz aus: keine Erklärung, keine Anführungszeichen."""


@dataclass
class Vorschlag:
    """Ergebnis für einen hochdeutschen Satz (Spike 1)."""

    satz: str
    woerterbuch_phrase: str | None = None     # gefunden -> kein LLM nötig
    paare: list[Wortpaar] = field(default_factory=list)
    text: str = ""                            # Antwort des Modells
    markierungen: list[tuple[str, str]] = field(default_factory=list)  # (Wort, Markierung)
    sekunden: float = 0.0


def phrase_suchen(uebersetzer, satz):
    """Gibt den Dialekt-Eintrag zurück, wenn der ganze hochdeutsche Satz (fast) im
    Wörterbuch steht – sonst None."""
    for t in uebersetzer.uebersetzen(satz, DEUTSCH_STEIRISCH, limit=1):
        if t.typ == "phrase" and t.score >= SCHWELLE:
            return t.dialekt
    return None


def ohne_llm(satz, paare):
    """Vergleichswert ohne Sprachmodell: jedes Wort durch den ersten Dialekt-Treffer ersetzen."""
    ersatz = {}
    for p in paare:
        ersatz.setdefault(p.suchwort, p.dialekt)
    return " ".join(ersatz.get(w, w) for w in normalisieren(satz).split())


def frage_text(satz, paare):
    """Baut die Frage an das Modell: Satz + Liste "Hochdeutsch = Steirisch"."""
    if paare:
        liste = "\n".join(f"- {p.hochdeutsch} = {p.dialekt}" for p in paare)
    else:
        liste = "(keine)"
    return f"Satz: {satz}\nGeprüfte Wörter:\n{liste}"


def ollama_fragen(satz, paare, modell=MODELL, url=OLLAMA):
    """Hochdeutsch -> Steirisch (Spike 1). Gibt (Antwort, Sekunden) zurück."""
    return ollama_chat(SYSTEM, frage_text(satz, paare), modell=modell, url=url)


def alle_dialektwoerter(uebersetzer):
    """Alle geprüften Dialekt-Wörter (normalisiert), auch einzelne Wörter aus Phrasen."""
    woerter = set()
    for e in uebersetzer.eintraege:
        for v in e["st-de"]:
            woerter.update(v.split())
    return woerter


def markieren(antwort, satz, paare, woerterbuch):
    """Ordnet jedem Wort der Antwort eine Markierung zu (siehe Konstanten oben)."""
    gefunden = set()
    for p in paare:
        for v in varianten(p.dialekt, "wort"):
            gefunden.update(v.split())
    original = set(normalisieren(satz).split())

    ergebnis = []
    for wort in normalisieren(antwort).split():
        if wort in gefunden:
            art = GEPRUEFT
        elif wort in original:
            art = HOCHDEUTSCH
        elif wort in woerterbuch:
            art = WOERTERBUCH
        elif len(wort) >= 3 and any(
            len(g) >= 3 and wort[:GLEICHER_ANFANG] == g[:GLEICHER_ANFANG]
            and aehnlichkeit(wort, g) >= ABGELEITET_AB
            for g in gefunden
        ):
            art = ABGELEITET
        else:
            art = VERDAECHTIG
        ergebnis.append((wort, art))
    return ergebnis


def vorschlagen(uebersetzer, satz, fragen=ollama_fragen, woerterbuch=None):
    """Kompletter Ablauf für einen Satz. `fragen` ist austauschbar (Tests ohne Ollama)."""
    vorschlag = Vorschlag(satz=satz)
    vorschlag.woerterbuch_phrase = phrase_suchen(uebersetzer, satz)
    if vorschlag.woerterbuch_phrase:
        return vorschlag
    vorschlag.paare = woerter_suchen(uebersetzer, satz)
    vorschlag.text, vorschlag.sekunden = fragen(satz, vorschlag.paare)
    if woerterbuch is None:
        woerterbuch = alle_dialektwoerter(uebersetzer)
    vorschlag.markierungen = markieren(vorschlag.text, satz, vorschlag.paare, woerterbuch)
    return vorschlag


if __name__ == "__main__":
    import sys
    u = Uebersetzer()
    for s in sys.argv[1:] or ["Das Wetter ist heute schlecht."]:
        print(s, "->", phrase_suchen(u, s) or ohne_llm(s, woerter_suchen(u, s)))
