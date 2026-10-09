"""Experiment A (09.10.): Messung der Verbform-Regel (app/verbformen.py), ohne LLM.

Testsatz und Go-Kriterien wurden VOR der Regel festgelegt (tests/verbformen.csv,
docs/experimente.md):
  - ≥ 15 von 18 regulären Formen -> richtiger Infinitiv
  - 0 falsche Infinitive im ganzen Testsatz
  - ≤ 3 falsche Treffer bei den übrigen Wörtern der Phrasen (von Hand bewerten);
    die Phrasen von Satz 3 (scripts/rag_test_hochdeutsch.py) sind ausgenommen

Teil 1: Jede Form wird versteckt, dann sucht die Regel den Infinitiv.
Teil 2: Alle Wörter der Phrasen, die das Wörterbuch NICHT findet und bei denen die Regel
        trotzdem etwas liefert. Jede Zeile von Hand prüfen: stimmt der Infinitiv?

Aufruf (im Projektordner, mit aktiviertem .venv):
    python scripts/verbformen_test.py
"""

import copy
import csv
import sys
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))
sys.path.insert(0, str(PROJEKT / "scripts"))

from app.uebersetzer import STANDARD_DB, STEIRISCH_DEUTSCH, Uebersetzer, normalisieren  # noqa: E402
from app.verbformen import infinitiv_suchen  # noqa: E402
from app.vorschlag import sichere_treffer, suchformen  # noqa: E402
from rag_test_hochdeutsch import SATZ_3  # noqa: E402

MIN_REGULAER = 15


def lesen(pfad):
    with open(pfad, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def ohne_form(uebersetzer, dialekt, hochdeutsch):
    kopie = copy.copy(uebersetzer)
    kopie.eintraege = [e for e in uebersetzer.eintraege
                       if (e["zeile"]["dialekt"], e["zeile"]["hochdeutsch"])
                       != (dialekt, hochdeutsch)]
    return kopie


def testsatz(uebersetzer):
    """Gibt (richtig_regulaer, anzahl_regulaer, falsche) zurück."""
    zeilen = lesen(PROJEKT / "tests" / "verbformen.csv")
    richtig, regulaer, falsche = 0, 0, []
    print("Teil 1: Testsatz (Form versteckt)\n")
    for z in zeilen:
        versteckt = ohne_form(uebersetzer, z["form"], z["bedeutung"])
        gefunden = [t.dialekt for t in infinitiv_suchen(versteckt, normalisieren(z["form"]))]
        falsch = [g for g in gefunden if g != z["infinitiv"]]
        ok = z["infinitiv"] in gefunden
        if z["kategorie"] == "regulär":
            regulaer += 1
            richtig += ok
        if falsch:
            falsche.append((z["form"], falsch))
        zeichen = "✗" if falsch else ("✓" if ok else "–")
        print(f"  {zeichen} {z['kategorie']:13} {z['form']:10} -> "
              f"{', '.join(gefunden) or '(nichts)':16} erwartet: {z['infinitiv']}")
    return richtig, regulaer, falsche


def phrasen_woerter(uebersetzer):
    """Wörter aus Phrasen, die nur über die Regel gefunden werden."""
    ausgenommen = {normalisieren(s) for s, _ in SATZ_3}
    gesehen, ergebnis = set(), []
    for z in lesen(PROJEKT / "data" / "phrasen.csv"):
        if z["status"] not in ("richtig", "korrigiert"):
            continue
        satz = z["korrektur"] if z["status"] == "korrigiert" else z["dialekt"]
        if normalisieren(satz) in ausgenommen:
            continue
        for wort, formen in suchformen(satz).items():
            if wort in gesehen:
                continue
            gesehen.add(wort)
            if any(sichere_treffer(uebersetzer, f, STEIRISCH_DEUTSCH) for f in formen):
                continue
            treffer = infinitiv_suchen(uebersetzer, wort)
            if treffer:
                ergebnis.append((wort, treffer, satz, z["hochdeutsch"]))
    return ergebnis


def main():
    if not STANDARD_DB.exists():
        raise SystemExit("Datenbank fehlt – zuerst python scripts/import_csv.py ausführen")
    uebersetzer = Uebersetzer()

    richtig, regulaer, falsche = testsatz(uebersetzer)

    print("\nTeil 2: Wörter aus Phrasen, die nur die Regel findet (von Hand prüfen)\n")
    neu = phrasen_woerter(uebersetzer)
    for wort, treffer, satz, hochdeutsch in neu:
        ziel = ", ".join(f"{t.dialekt} = {t.hochdeutsch}" for t in treffer)
        print(f"  {wort:12} -> {ziel}\n      in: {satz}  ({hochdeutsch})")
    if not neu:
        print("  (keine)")

    print("\nErgebnis")
    print(f"  reguläre Formen richtig: {richtig}/{regulaer} (Ziel ≥ {MIN_REGULAER})"
          f"  {'✅' if richtig >= MIN_REGULAER else '❌'}")
    print(f"  falsche Infinitive im Testsatz: {len(falsche)} (Ziel 0)"
          f"  {'✅' if not falsche else '❌ ' + str(falsche)}")
    print(f"  Treffer in Phrasen zum Prüfen: {len(neu)} (Ziel: höchstens 3 falsche)")


if __name__ == "__main__":
    main()
