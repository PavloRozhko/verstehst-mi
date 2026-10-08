"""Spike 08.10.: Kann gemma3:4b Sätze, die NICHT im Wörterbuch stehen, nur mit
geprüften Wörtern ins Steirische übertragen? (Logik: app/vorschlag.py)

Go-Kriterien:
  - höchstens 5 s pro Satz
  - 0 erfundene Dialektwörter (Wörter mit "?" in der Ausgabe von Hand prüfen)
  - mindestens 7 von 10 Sätzen verwenden gefundene Wörter

Aufruf (im Projektordner, mit aktiviertem .venv; der Dienst verstehst-mi darf laufen –
so ist der Speicher wie bei der Präsentation):
    python scripts/rag_test.py                 # mit gemma3:4b
    python scripts/rag_test.py --ohne-ollama   # nur Wörtersuche + Vergleich ohne LLM

Ergebnis: models/rag_test/<modell>.csv – Spalte "bewertung" (gut / teils / falsch) ausfüllen.

Markierungen in der Ausgabe:
  ✓ geprüft (gefundenes Wort)    W geprüft (Wörterbuch, aber nicht gesucht)
  = Hochdeutsch aus dem Satz     ~ gebeugte Form (Regel B, prüfen)    ? verdächtig
"""

import argparse
import csv
import sys
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))   # damit "app" gefunden wird

from app import vorschlag as v                     # noqa: E402
from app.uebersetzer import STANDARD_DB, Uebersetzer  # noqa: E402

AUSGABE = PROJEKT / "models" / "rag_test"   # models/ steht in .gitignore

# Vor dem ersten Lauf festgelegt (08.10.). 1, 2 und 5 wurden ersetzt, weil ähnliche
# Phrasen schon im Wörterbuch stehen ("I hob ka Zeit.", "Waun is Feierobnd?").
SAETZE = [
    "Heute habe ich keinen Hunger.",
    "Machen wir heute früher Feierabend?",
    "Die Arbeit ist heute anstrengend.",
    "Gehen wir nach der Pause etwas essen?",
    "Ich verstehe die Frage nicht.",
    "Am Donnerstag haben wir frei.",
    "Hast du den Schlüssel gesehen?",
    "Das Wetter ist heute schlecht.",
    "Mir ist kalt, mach bitte das Fenster zu.",
    "Der Bus kommt schon wieder zu spät.",
]

ZEICHEN = {v.GEPRUEFT: "✓", v.WOERTERBUCH: "W", v.HOCHDEUTSCH: "=",
           v.ABGELEITET: "~", v.VERDAECHTIG: "?"}
MAX_SEKUNDEN = 5.0


def markiert(markierungen):
    return " ".join(f"{wort}[{ZEICHEN[art]}]" for wort, art in markierungen)


def main():
    parser = argparse.ArgumentParser(description="RAG-Spike: KI-Vorschlag testen")
    parser.add_argument("--modell", default=v.MODELL)
    parser.add_argument("--ohne-ollama", action="store_true",
                        help="nur Wörtersuche und Vergleich ohne LLM")
    args = parser.parse_args()

    if not STANDARD_DB.exists():
        raise SystemExit("Datenbank fehlt – zuerst python scripts/import_csv.py ausführen")
    uebersetzer = Uebersetzer()
    woerterbuch = v.alle_dialektwoerter(uebersetzer)

    if args.ohne_ollama:
        def fragen(satz, paare):
            return v.ohne_llm(satz, paare), 0.0
    else:
        def fragen(satz, paare):
            return v.ollama_fragen(satz, paare, modell=args.modell)

        print(f"Lade {args.modell} …")
        try:
            _, ladezeit = fragen(SAETZE[0], [])
        except OSError as fehler:
            raise SystemExit(f"Ollama nicht erreichbar ({fehler}). Läuft der Dienst ollama?")
        print(f"Erste Antwort (inkl. Laden): {ladezeit:.1f} s\n")

    AUSGABE.mkdir(parents=True, exist_ok=True)
    name = "ohne_llm" if args.ohne_ollama else args.modell.replace(":", "_").replace("/", "_")
    datei = AUSGABE / f"{name}.csv"

    zeiten, mit_treffern, verdaechtig = [], 0, 0
    with open(datei, "w", newline="", encoding="utf-8-sig") as f:
        schreiber = csv.writer(f, delimiter=";")
        schreiber.writerow(["satz", "gefundene_woerter", "ohne_llm", "vorschlag", "markiert",
                            "verdaechtig", "sekunden", "bewertung (gut/teils/falsch)",
                            "kommentar"])
        for satz in SAETZE:
            vs = v.vorschlagen(uebersetzer, satz, fragen=fragen, woerterbuch=woerterbuch)
            if vs.woerterbuch_phrase:
                print(f"ÜBERSPRUNGEN (steht im Wörterbuch: {vs.woerterbuch_phrase}): {satz}\n")
                continue
            arten = [art for _, art in vs.markierungen]
            fragwuerdig = [w for w, art in vs.markierungen if art == v.VERDAECHTIG]
            zeiten.append(vs.sekunden)
            mit_treffern += v.GEPRUEFT in arten
            verdaechtig += len(fragwuerdig)
            paare = ", ".join(f"{p.suchwort}={p.dialekt}" for p in vs.paare)
            schreiber.writerow([satz, paare, v.ohne_llm(satz, vs.paare), vs.text,
                                markiert(vs.markierungen), " ".join(fragwuerdig),
                                f"{vs.sekunden:.1f}", "", ""])
            print(f"[{vs.sekunden:4.1f} s] {satz}\n"
                  f"    Wörter:   {paare or '(keine)'}\n"
                  f"    ohne LLM: {v.ohne_llm(satz, vs.paare)}\n"
                  f"    LLM:      {markiert(vs.markierungen)}\n")

    zeiten.sort()
    print("Legende: ✓ geprüft  W Wörterbuch  = Hochdeutsch  ~ gebeugt (prüfen)  ? verdächtig")
    print(f"Sätze mit gefundenen Wörtern im Ergebnis: {mit_treffern}/{len(zeiten)} (Ziel ≥ 7)")
    print(f"Verdächtige Wörter: {verdaechtig} (von Hand prüfen, Ziel: 0 erfundene)")
    if not args.ohne_ollama and zeiten:
        langsam = sum(z > MAX_SEKUNDEN for z in zeiten)
        print(f"Zeit: Median {zeiten[len(zeiten) // 2]:.1f} s, langsamste {zeiten[-1]:.1f} s, "
              f"über {MAX_SEKUNDEN:.0f} s: {langsam}")
    print(f"Gespeichert: {datei.relative_to(PROJEKT)}")


if __name__ == "__main__":
    main()
