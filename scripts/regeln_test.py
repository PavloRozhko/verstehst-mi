"""Schritt 5b: Wie viele unbekannte Wörter übersetzen die 6 Ausspracheregeln richtig?

Kriterien und Testmenge wurden VOR dem Lauf festgelegt (13.10.).
Testmenge: alle importierten Phrasen. Pro Phrase werden die Wörter gesucht wie bei der
KI-Übersetzung; was nicht gefunden wird, bekommt einen Vorschlag über die Regeln.
Das hochdeutsche Vokabular kommt aus allen Einträgen AUSSER der geprüften Phrase.

    python scripts/regeln_test.py
"""

import sys
from collections import Counter
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from app import ki_hochdeutsch as ki                     # noqa: E402
from app.lautregeln import hochdeutsch_vorschlagen        # noqa: E402
from app.uebersetzer import STEIRISCH_DEUTSCH, Uebersetzer, normalisieren  # noqa: E402
from app.wortsuche import woerter_suchen                  # noqa: E402


def main():
    """Alle Phrasen prüfen, Ergebnis ausgeben."""
    u = Uebersetzer()
    zaehler = Counter()
    for e in u.eintraege:
        zaehler.update(set(normalisieren(e["zeile"]["hochdeutsch"]).split()))

    richtig, unbestaetigt, ohne, regeln_ok, regeln_nein = [], [], [], Counter(), Counter()
    phrasen = [e for e in u.eintraege if e["zeile"]["typ"] == "phrase"]
    for e in phrasen:
        z = e["zeile"]
        uebersetzung = set(normalisieren(z["hochdeutsch"]).split())
        # Vokabular ohne diese Phrase (sonst "sieht" der Test die Antwort)
        vokabular = {w for w, n in zaehler.items() if n - (w in uebersetzung) > 0}

        ergebnis = ki.KiUebersetzung(satz=z["dialekt"])
        ergebnis.paare = woerter_suchen(u, z["dialekt"], STEIRISCH_DEUTSCH, mit_derb=True)
        ergebnis.nicht_gefunden = ki.nicht_gefunden(z["dialekt"], ergebnis.paare)
        ki.hochdeutsch_abtrennen(u, ergebnis)

        for wort in ergebnis.nicht_gefunden:
            vorschlaege = hochdeutsch_vorschlagen(wort, vokabular)
            zeile = (wort, [v for v, _ in vorschlaege], z["dialekt"], z["hochdeutsch"])
            if not vorschlaege:
                ohne.append(zeile)
            elif any(v in uebersetzung for v, _ in vorschlaege):
                richtig.append(zeile)
                regeln_ok.update(r for v, rs in vorschlaege if v in uebersetzung for r in rs)
            else:
                unbestaetigt.append(zeile)
                regeln_nein.update(r for _v, rs in vorschlaege for r in rs)

    gesamt = len(richtig) + len(unbestaetigt) + len(ohne)
    vorgeschlagen = len(richtig) + len(unbestaetigt)
    praezision = len(richtig) / vorgeschlagen if vorgeschlagen else 0.0
    print(f"Phrasen: {len(phrasen)}, Zielwörter: {gesamt}")
    print(f"richtig: {len(richtig)}, nicht bestätigt: {len(unbestaetigt)}, ohne Vorschlag: {len(ohne)}")
    print(f"Präzision: {praezision:.0%}")
    ok = praezision >= 0.9 and len(richtig) >= 10
    print("Entscheidung:", "go" if ok else "no-go")
    print("Regeln in richtigen Vorschlägen:", dict(sorted(regeln_ok.items())))
    print("Regeln in nicht bestätigten Vorschlägen:", dict(sorted(regeln_nein.items())))
    for titel, liste in (("RICHTIG", richtig), ("NICHT BESTÄTIGT", unbestaetigt),
                         ("OHNE VORSCHLAG", ohne)):
        print(f"\n--- {titel} ({len(liste)})")
        for wort, v, dialekt, hd in liste:
            print(f"{wort:14} -> {', '.join(v) or '-':24} | {dialekt} = {hd}")


if __name__ == "__main__":
    main()
