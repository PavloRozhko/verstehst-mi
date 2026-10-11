"""Wörter eines Satzes einzeln im Wörterbuch nachschlagen.

Grundlage für die KI-Übersetzung (app/ki_hochdeutsch.py): Das Sprachmodell bekommt nur
die Wortbedeutungen, die hier gefunden werden. Darum gilt: lieber ein Wort NICHT finden
als ein falsches. Ein unbekanntes Wort wird in der App angezeigt; ein falsch gefundenes
würde das Modell in die Irre führen, ohne dass man es sieht.

Ablauf in woerter_suchen():
  1. Ausdrücke aus zwei Wörtern, die als EIN Eintrag im Wörterbuch stehen ("auf d'Nocht").
  2. Jedes Wort einzeln, auch ohne angehängtes d'/z' ("z'teia" -> "teia").
  3. Nichts gefunden (nur Dialekt): vielleicht eine gebeugte Verbform (app/verbformen.py).
"""

import re
from dataclasses import dataclass

from app.uebersetzer import DEUTSCH_STEIRISCH, STEIRISCH_DEUTSCH, normalisieren, varianten
from app.verbformen import infinitiv_suchen

# Für ein einzelnes Wort reicht "ähnlich" nicht: "nach" fand "Mei" (= ach), "der" fand "oda".
# Ein ähnlicher Treffer zählt nur, wenn die Bedeutung mit dem Suchwort fast gleich beginnt
# ("habe" -> "haben" ja, "nach" -> "ach" nein).
WORT_SCHWELLE = 0.85
# Kurze Wörter nur exakt: "bitte" fand sonst "hantig" (= bitter), "keine" fand "kana" (= keiner)
AEHNLICH_AB = 6     # Zeichen
# Höchstens so viele Einträge pro Wort (z. B. "Pfusch" und "pfuschn")
MAX_PRO_WORT = 2

# Im Dialekt hängen Artikel und "zu" oft am Wort: d'Nocht (die Nacht), z'teia (zu teuer)
VORSILBE = re.compile(r"\b[dz]['’´`](\w+)", re.IGNORECASE)


@dataclass
class Wortpaar:
    """Ein gefundenes Wort: was im Satz stand und was im Wörterbuch dazu steht."""

    suchwort: str       # Wort aus dem Eingabesatz (normalisiert)
    dialekt: str
    hochdeutsch: str
    abgeleitet: bool = False    # über eine Verbform gefunden (app/verbformen.py), nicht geprüft
    derb: bool = False          # derber Ausdruck (wird nur mit mit_derb=True gefunden)


def sicherer_treffer(suchwort, treffer, richtung=DEUTSCH_STEIRISCH):
    """Entscheidet, ob ein Treffer der Wortsuche sicher genug ist.

    Genaue Treffer (score 1.0) sind immer sicher. Ähnliche nur, wenn das Suchwort lang
    genug ist und die Gegenseite fast gleich beginnt – sonst "findet" man Zufälle.
    """
    if treffer.score == 1.0:
        return True
    if treffer.score < WORT_SCHWELLE or len(suchwort) < AEHNLICH_AB:
        return False
    stamm = suchwort[:-1] if len(suchwort) > 3 else suchwort
    gesucht_in = treffer.hochdeutsch if richtung == DEUTSCH_STEIRISCH else treffer.dialekt
    return any(v.startswith(stamm) for v in varianten(gesucht_in, "wort"))


def suchformen(satz):
    """Gibt zu jedem Wort die Formen zurück, nach denen gesucht wird.

    "Des is ma z'teia." -> {"zteia": ["zteia", "teia"], ...}
    """
    abgetrennt = {normalisieren(m.group(0)): normalisieren(m.group(1))
                  for m in VORSILBE.finditer(satz)}
    return {w: [w] + ([abgetrennt[w]] if w in abgetrennt else [])
            for w in normalisieren(satz).split()}


def sichere_treffer(uebersetzer, wort, richtung, mit_derb=False):
    """Sucht ein einzelnes Wort und gibt nur sichere Wort-Treffer zurück (keine Phrasen)."""
    return [
        t for t in uebersetzer.uebersetzen(wort, richtung, mit_derb=mit_derb, limit=5)
        if t.typ == "wort" and t.art != "in Phrase" and sicherer_treffer(wort, t, richtung)
    ]


def woerter_suchen(uebersetzer, satz, richtung=DEUTSCH_STEIRISCH, mit_derb=False):
    """Sucht jedes Wort des Satzes einzeln (nur Wörter, nur sichere Treffer).

    richtung: DEUTSCH_STEIRISCH (Satz ist Hochdeutsch) oder STEIRISCH_DEUTSCH (Satz ist Dialekt)
    mit_derb: True = auch derbe Ausdrücke finden (für die KI-Übersetzung, siehe ki_hochdeutsch)

    Gibt eine Liste von Wortpaar zurück. Jedes Dialektwort kommt höchstens einmal vor.
    """
    paare, gesehen = [], set()

    def aufnehmen(suchwort, treffer):
        """Übernimmt bis zu MAX_PRO_WORT Treffer, die noch nicht in der Liste sind."""
        for t in treffer[:MAX_PRO_WORT]:
            if t.dialekt not in gesehen:
                gesehen.add(t.dialekt)
                paare.append(Wortpaar(suchwort, t.dialekt, t.hochdeutsch,
                                      abgeleitet=t.art == "abgeleitet", derb=t.derb))

    # 1. Ausdrücke aus zwei Wörtern ("auf d'Nocht") – nur exakt
    woerter = normalisieren(satz).split()
    for paar in (" ".join(woerter[i:i + 2]) for i in range(len(woerter) - 1)):
        aufnehmen(paar, [t for t in sichere_treffer(uebersetzer, paar, richtung, mit_derb)
                         if t.score == 1.0])

    # 2. Jedes Wort einzeln (auch ohne d'/z')
    formen = suchformen(satz)
    for wort in woerter:
        for form in formen[wort]:
            treffer = sichere_treffer(uebersetzer, form, richtung, mit_derb)
            if treffer:
                aufnehmen(wort, treffer)
                break
        else:
            # 3. Nichts gefunden: vielleicht eine gebeugte Verbform (Experiment A, nur Dialekt)
            if richtung == STEIRISCH_DEUTSCH:
                aufnehmen(wort, infinitiv_suchen(uebersetzer, wort, mit_derb))
    return paare
