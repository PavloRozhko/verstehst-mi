"""KI-Vorschlag (Experiment): einen hochdeutschen Satz, der NICHT im Wörterbuch steht,
mit Hilfe geprüfter Wörter ins Steirische übertragen.

Ablauf (RAG = "Retrieval-Augmented Generation", also: erst nachschlagen, dann schreiben):
  1. Steht der ganze Satz schon im Wörterbuch?  -> dann gilt der geprüfte Eintrag, kein LLM.
  2. Jedes Wort im Wörterbuch suchen (nur sichere Treffer).
  3. Das Sprachmodell bekommt Satz + gefundene Wörter und darf NUR diese als Dialekt verwenden.
  4. Jedes Wort der Antwort wird geprüft und markiert (siehe markieren()).

Regel "B" (vereinbart am 08.10.): Verben aus der Liste darf das Modell beugen
("hom" -> "hob"). Solche Formen sind NICHT geprüft und werden eigens markiert.
"""

import json
import re
import time
import urllib.request
from dataclasses import dataclass, field

from app.uebersetzer import (
    DEUTSCH_STEIRISCH,
    SCHWELLE,
    STEIRISCH_DEUTSCH,
    Uebersetzer,
    aehnlichkeit,
    normalisieren,
    varianten,
)
from app.verbformen import infinitiv_suchen

OLLAMA = "http://localhost:11434/api/chat"
MODELL = "gemma3:4b"

# Für ein einzelnes Wort reicht "ähnlich" nicht: "nach" fand "Mei" (= ach), "der" fand "oda".
# Ein ähnlicher Treffer zählt nur, wenn die Bedeutung mit dem Suchwort fast gleich beginnt
# ("habe" -> "haben" ja, "nach" -> "ach" nein).
WORT_SCHWELLE = 0.85
# Kurze Wörter nur exakt: "bitte" fand sonst "hantig" (= bitter), "keine" fand "kana" (= keiner)
AEHNLICH_AB = 6     # Zeichen
MAX_PRO_WORT = 2

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
class Wortpaar:
    suchwort: str       # Wort aus dem Eingabesatz (normalisiert)
    dialekt: str
    hochdeutsch: str
    abgeleitet: bool = False    # über eine Verbform gefunden (app/verbformen.py), nicht geprüft
    derb: bool = False          # derber Ausdruck (wird nur mit mit_derb=True gefunden)


@dataclass
class Vorschlag:
    satz: str
    woerterbuch_phrase: str | None = None     # gefunden -> kein LLM nötig
    paare: list[Wortpaar] = field(default_factory=list)
    text: str = ""                            # Antwort des Modells
    markierungen: list[tuple[str, str]] = field(default_factory=list)  # (Wort, Markierung)
    sekunden: float = 0.0


def sicherer_treffer(suchwort, treffer, richtung=DEUTSCH_STEIRISCH):
    if treffer.score == 1.0:
        return True
    if treffer.score < WORT_SCHWELLE or len(suchwort) < AEHNLICH_AB:
        return False
    stamm = suchwort[:-1] if len(suchwort) > 3 else suchwort
    gesucht_in = treffer.hochdeutsch if richtung == DEUTSCH_STEIRISCH else treffer.dialekt
    return any(v.startswith(stamm) for v in varianten(gesucht_in, "wort"))


# Im Dialekt hängen Artikel und "zu" oft am Wort: d'Nocht (die Nacht), z'teia (zu teuer)
VORSILBE = re.compile(r"\b[dz]['’´`](\w+)", re.IGNORECASE)


def suchformen(satz):
    """Zu jedem Wort die Formen, nach denen gesucht wird.

    "Des is ma z'teia." -> {"zteia": ["zteia", "teia"], ...}
    """
    abgetrennt = {normalisieren(m.group(0)): normalisieren(m.group(1))
                  for m in VORSILBE.finditer(satz)}
    return {w: [w] + ([abgetrennt[w]] if w in abgetrennt else [])
            for w in normalisieren(satz).split()}


def sichere_treffer(uebersetzer, wort, richtung, mit_derb=False):
    return [
        t for t in uebersetzer.uebersetzen(wort, richtung, mit_derb=mit_derb, limit=5)
        if t.typ == "wort" and t.art != "in Phrase" and sicherer_treffer(wort, t, richtung)
    ]


def woerter_suchen(uebersetzer, satz, richtung=DEUTSCH_STEIRISCH, mit_derb=False):
    """Sucht jedes Wort des Satzes einzeln (nur Wörter, nur sichere Treffer).

    richtung: DEUTSCH_STEIRISCH (Satz ist Hochdeutsch) oder STEIRISCH_DEUTSCH (Satz ist Dialekt)

    Zuerst Ausdrücke aus zwei Wörtern, die im Wörterbuch als EIN Eintrag stehen
    ("auf d'Nocht" = am Abend) – nur exakt. Dann jedes Wort einzeln.
    mit_derb=True: auch derbe Ausdrücke finden (für die KI-Übersetzung, siehe ki_hochdeutsch).
    """
    paare, gesehen = [], set()

    def aufnehmen(suchwort, treffer):
        for t in treffer[:MAX_PRO_WORT]:
            if t.dialekt not in gesehen:
                gesehen.add(t.dialekt)
                paare.append(Wortpaar(suchwort, t.dialekt, t.hochdeutsch,
                                      abgeleitet=t.art == "abgeleitet", derb=t.derb))

    woerter = normalisieren(satz).split()
    for paar in (" ".join(woerter[i:i + 2]) for i in range(len(woerter) - 1)):
        aufnehmen(paar, [t for t in sichere_treffer(uebersetzer, paar, richtung, mit_derb)
                         if t.score == 1.0])

    formen = suchformen(satz)
    for wort in woerter:
        for form in formen[wort]:
            treffer = sichere_treffer(uebersetzer, form, richtung, mit_derb)
            if treffer:
                aufnehmen(wort, treffer)
                break
        else:
            # Nichts gefunden: vielleicht eine gebeugte Verbform (Experiment A, nur Dialekt)
            if richtung == STEIRISCH_DEUTSCH:
                aufnehmen(wort, infinitiv_suchen(uebersetzer, wort, mit_derb))
    return paare


def phrase_suchen(uebersetzer, satz):
    """Gibt den Dialekt-Eintrag zurück, wenn der ganze Satz (fast) im Wörterbuch steht."""
    for t in uebersetzer.uebersetzen(satz, DEUTSCH_STEIRISCH, limit=1):
        if t.typ == "phrase" and t.score >= SCHWELLE:
            return t.dialekt
    return None


def ohne_llm(satz, paare):
    """Vergleichswert ohne Sprachmodell: jedes Wort durch den ersten Treffer ersetzen."""
    ersatz = {}
    for p in paare:
        ersatz.setdefault(p.suchwort, p.dialekt)
    return " ".join(ersatz.get(w, w) for w in normalisieren(satz).split())


def frage_text(satz, paare):
    if paare:
        liste = "\n".join(f"- {p.hochdeutsch} = {p.dialekt}" for p in paare)
    else:
        liste = "(keine)"
    return f"Satz: {satz}\nGeprüfte Wörter:\n{liste}"


def ollama_chat(system, frage, modell=MODELL, url=OLLAMA, num_predict=60,
                keep_alive="10m", timeout=180):
    """Eine Frage an Ollama. Gibt (Antwort, Sekunden) zurück.

    keep_alive: wie lange Ollama das Modell danach im Speicher hält (-1 = für immer).
    """
    anfrage = {
        "model": modell,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": frage},
        ],
        "stream": False,
        "options": {"temperature": 0, "num_predict": num_predict},
        "keep_alive": keep_alive,
    }
    req = urllib.request.Request(
        url, data=json.dumps(anfrage).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as antwort:
        ergebnis = json.load(antwort)
    return ergebnis["message"]["content"].strip(), time.perf_counter() - start


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
