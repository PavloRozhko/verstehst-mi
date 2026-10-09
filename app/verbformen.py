"""Experiment A (09.10.): gebeugte Verbformen auf einen geprüften Infinitiv zurückführen.

Im Wörterbuch steht meist nur der Infinitiv ("mochn" = machen). Im Satz kommt das Verb
gebeugt vor ("mochst", "gmocht") und wird nicht gefunden. Diese Regel trennt typische
Endungen ab und sucht einen geprüften Infinitiv mit GENAU demselben Stamm.

    mochst  -> moch  -> mochn   (= machen)
    gmocht  -> moch  -> mochn
    kummts  -> kumm  -> kumman  (= kommen)

Bewusst einfach und vorsichtig:
  - nur Verben, deren Stamm gleich bleibt (regelmäßig); "host" -> "hom" findet sie NICHT
  - Stamm und Infinitiv müssen exakt passen, keine Ähnlichkeitssuche
  - das Ergebnis ist "abgeleitet", nicht "geprüft"

Schnelltest im Terminal:
    python -m app.verbformen mochst gmocht kummts host
"""

import sys

from app.uebersetzer import STEIRISCH_DEUTSCH, Treffer, Uebersetzer, normalisieren, varianten

# Endungen gebeugter Formen: ihr kummts / du kummst / er kummt
FORM_ENDUNGEN = ("ts", "st", "t")
# Endungen des Infinitivs im Wörterbuch: kumm-an, moch-n, kenn-a
INFINITIV_ENDUNGEN = ("an", "en", "n", "a")
# Kürzere Stämme ergeben Zufallstreffer
MIN_STAMM = 3


def staemme_der_form(wort):
    """Mögliche Stämme eines (normalisierten) Wortes.

    "mochst" -> {"mochst", "mochs", "moch"}, "gmocht" -> {"gmocht", "gmoch", "moch"}
    Das Wort selbst zählt mit: Befehl und ich-Form sind oft der nackte Stamm ("moch", "kumm").
    """
    staemme = {wort}
    for endung in FORM_ENDUNGEN:
        if wort.endswith(endung):
            staemme.add(wort[:-len(endung)])
    # Partizip: g-…-t (gmocht) oder g-…-n (gsogn)
    if wort.startswith("g") and wort[-1:] in ("t", "n"):
        staemme.add(wort[1:-1])
    return {s for s in staemme if len(s) >= MIN_STAMM}


def ist_infinitiv(zeile, dialekt):
    """Ein Verb-Eintrag, der wie ein Infinitiv aussieht.

    Gebeugte Formen stehen auch als Verb im Wörterbuch ("host'n" = hast du denn,
    "gsehn" = gesehen). Sie zählen nicht: Die Bedeutung muss EIN Wort sein, darf nicht
    mit "ge" beginnen (Partizip) und der Dialekt muss auf -n oder -a enden.
    """
    if zeile["typ"] != "wort" or zeile["wortart"] != "Verb":
        return False
    bedeutung = varianten(zeile["hochdeutsch"], "wort")
    if not bedeutung or " " in bedeutung[0] or bedeutung[0].startswith("ge"):
        return False
    return dialekt.endswith(("n", "a"))


def infinitive(uebersetzer, mit_derb=False):
    """{Stamm: [Einträge]} aller geprüften Infinitive."""
    ergebnis = {}
    for eintrag in uebersetzer.eintraege:
        zeile = eintrag["zeile"]
        if zeile["derb"] and not mit_derb:
            continue
        for dialekt in eintrag[STEIRISCH_DEUTSCH]:
            if " " in dialekt or not ist_infinitiv(zeile, dialekt):
                continue
            for endung in INFINITIV_ENDUNGEN:
                if dialekt.endswith(endung):
                    stamm = dialekt[:-len(endung)]
                    liste = ergebnis.setdefault(stamm, [])
                    if zeile not in liste:
                        liste.append(zeile)
    return ergebnis


def infinitiv_suchen(uebersetzer, wort, mit_derb=False):
    """Geprüfte Infinitive, auf die das (normalisierte) Wort zurückgeführt werden kann.

    Gibt Treffer mit art="abgeleitet" zurück (leer, wenn nichts passt).
    """
    index = infinitive(uebersetzer, mit_derb)
    treffer, gesehen = [], set()
    for stamm in sorted(staemme_der_form(wort), key=len, reverse=True):
        for zeile in index.get(stamm, []):
            if zeile["dialekt"] in gesehen:
                continue
            gesehen.add(zeile["dialekt"])
            treffer.append(Treffer(
                dialekt=zeile["dialekt"],
                hochdeutsch=zeile["hochdeutsch"],
                typ="wort",
                thema=zeile["thema"],
                derb=bool(zeile["derb"]),
                art="abgeleitet",
                score=0.0,
            ))
    return treffer


def main():
    uebersetzer = Uebersetzer()
    for wort in sys.argv[1:]:
        gefunden = infinitiv_suchen(uebersetzer, normalisieren(wort))
        ziel = ", ".join(f"{t.dialekt} = {t.hochdeutsch}" for t in gefunden) or "-"
        print(f"{wort:12} -> {ziel}")


if __name__ == "__main__":
    main()
