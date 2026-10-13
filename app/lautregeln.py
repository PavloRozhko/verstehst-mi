"""Schritt 5b (Experiment, 13.10.): Dialektwort -> Hochdeutsch über Ausspracheregeln.

Nur die 6 Regeln aus der Tabelle "Regeln", die als verlässlich gelten (3, 4, 5, 11, 12, 16).
Die Regeln beschreiben Hochdeutsch -> Dialekt; hier laufen sie rückwärts:

    wassa -> wasser (3)    essn -> essen (4)    schul -> schule (5)
    gmacht -> gemacht (11) i -> ich (12)        leit -> leut -> leute (16 + 5)

Ein Kandidat zählt nur, wenn es das Wort in der hochdeutschen Spalte des Wörterbuchs gibt.
So erfinden die Regeln keine Wörter. Das Ergebnis ist "abgeleitet", nicht geprüft.
"""

from app.uebersetzer import normalisieren

VOKALE = set("aeiouäöü")
# Regel 12: -ch fällt weg, aber nur bei diesen Wörtern
OHNE_CH = {"i": "ich", "mi": "mich", "di": "dich", "si": "sich"}


def _regel_3(w):
    """-er -> -a, rückwärts: wassa -> wasser."""
    return [w[:-1] + "er"] if len(w) > 2 and w.endswith("a") else []


def _regel_4(w):
    """-en -> -n, rückwärts: essn -> essen (nur nach Konsonant)."""
    return [w[:-1] + "en"] if len(w) > 2 and w.endswith("n") and w[-2] not in VOKALE else []


def _regel_5(w):
    """-e fällt weg, rückwärts: schul -> schule."""
    return [w + "e"] if len(w) > 2 and not w.endswith("e") else []


def _regel_11(w):
    """ge- -> g-, rückwärts: gmacht -> gemacht."""
    return ["ge" + w[1:]] if len(w) > 3 and w[0] == "g" and w[1] not in VOKALE else []


def _regel_16(w):
    """eu/äu -> ei, rückwärts: leit -> leut / läut."""
    return [w.replace("ei", "eu", 1), w.replace("ei", "äu", 1)] if "ei" in w else []


REGELN = {3: _regel_3, 4: _regel_4, 5: _regel_5, 11: _regel_11, 16: _regel_16}


def kandidaten(wort):
    """Alle Formen, die durch Rückwärts-Anwendung der Regeln entstehen.

    Gibt {Form: (Regelnummern, …)} zurück. Jede Regel wird höchstens einmal angewendet.
    """
    wort = normalisieren(wort)
    if wort in OHNE_CH:
        return {OHNE_CH[wort]: (12,)}
    ergebnis = {}
    stapel = [(wort, ())]
    while stapel:
        form, benutzt = stapel.pop()
        for nr, regel in REGELN.items():
            if nr in benutzt:
                continue
            for neu in regel(form):
                regeln = tuple(sorted(benutzt + (nr,)))
                if neu != wort and neu not in ergebnis:
                    ergebnis[neu] = regeln
                    stapel.append((neu, regeln))
    return ergebnis


def hochdeutsch_vorschlagen(wort, vokabular):
    """Kandidaten, die als Wort im Hochdeutsch-Vokabular vorkommen.

    vokabular: Menge normalisierter hochdeutscher Wörter (z. B. ki_hochdeutsch.hochdeutsche_woerter).
    Gibt eine Liste (Hochdeutsch, Regeln) zurück, die mit den wenigsten Regeln zuerst.
    """
    treffer = [(form, regeln) for form, regeln in kandidaten(wort).items() if form in vokabular]
    return sorted(treffer, key=lambda t: (len(t[1]), t[0]))
