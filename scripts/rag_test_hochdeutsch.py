"""Spike 2 (08.10.): Kann gemma3:4b steirische Sätze mit Hilfe geprüfter Wörter
richtig ins Hochdeutsche übertragen? (Logik: app/ki_hochdeutsch.py)

Testsätze: 10 geprüfte Phrasen aus dem Wörterbuch, zufällig gezogen (Seed 20261008) aus
allen nicht derben Phrasen mit mindestens 4 Wörtern und mindestens 2 Wörtern in der
Wörter-Tabelle. Die Phrasen selbst werden "versteckt" (keine Phrasensuche) – so gibt es
eine richtige Antwort von Muttersprachlern, ohne dass wir Dialekt erfinden.
Einschränkung: Die Wörter-Tabelle stammt teilweise aus denselben Phrasen,
das Ergebnis ist also eher etwas zu gut.

Go-Kriterien (vor dem ersten Lauf festgelegt):
  - höchstens 5 s pro Satz
  - Bedeutung richtig ("gut") in mindestens 7 von 10 Sätzen (Bewertung von Hand)
  - 0 Sätze, in denen das Modell einer geprüften Bedeutung widerspricht
  - Wörter, die nicht im Wörterbuch stehen, werden angezeigt (macht das Programm)

Aufruf (im Projektordner, mit aktiviertem .venv; Dienst verstehst-mi darf laufen):
    python scripts/rag_test_hochdeutsch.py
    python scripts/rag_test_hochdeutsch.py --ohne-ollama

Ergebnis: models/rag_test/hochdeutsch_<modell>.csv – Spalte "bewertung" ausfüllen.
"""

import argparse
import csv
import sys
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from app import ki_hochdeutsch as ki                  # noqa: E402
from app.uebersetzer import STANDARD_DB, Uebersetzer  # noqa: E402
from app.vorschlag import MODELL                      # noqa: E402

AUSGABE = PROJEKT / "models" / "rag_test"
MAX_SEKUNDEN = 5.0

# (Dialekt, geprüfte hochdeutsche Bedeutung) – aus data/phrasen.csv
SAETZE = [
    ("Deis Gschropp heat ned auf zum Plärrn.", "Das Kind hört nicht auf zu weinen."),
    ("Heit is vü z'tuan.", "Heute gibt es viel zu tun."),
    ("Wos tuast heit auf d'Nocht?", "Was machst du heute Abend?"),
    ("Der is ma zwida.", "Der ist mir unsympathisch."),
    ("Wia weit is des?", "Wie weit ist das?"),
    ("Wia vü Kinda host?", "Wie viele Kinder hast du?"),
    ("Des is owa gschmackig!", "Das ist aber lecker!"),
    ("Heast, los amoi zua!", "Hör mal, hör mal zu!"),
    ("Des is a Pfusch.", "Das ist schlampig gemacht."),
    ("Wos is'n des für a Gschiss?", "Was ist das für ein unnötiges Getue?"),
]


def main():
    parser = argparse.ArgumentParser(description="Spike 2: Dialekt -> Hochdeutsch")
    parser.add_argument("--modell", default=MODELL)
    parser.add_argument("--ohne-ollama", action="store_true")
    args = parser.parse_args()

    if not STANDARD_DB.exists():
        raise SystemExit("Datenbank fehlt – zuerst python scripts/import_csv.py ausführen")
    uebersetzer = Uebersetzer()

    if args.ohne_ollama:
        def fragen(satz, paare):
            return ki.ohne_llm(satz, paare), 0.0
    else:
        def fragen(satz, paare):
            return ki.ollama_fragen(satz, paare, modell=args.modell)

        print(f"Lade {args.modell} …")
        try:
            _, ladezeit = fragen("Servus!", [])
        except OSError as fehler:
            raise SystemExit(f"Ollama nicht erreichbar ({fehler}). Läuft der Dienst ollama?")
        print(f"Erste Antwort (inkl. Laden): {ladezeit:.1f} s\n")

    AUSGABE.mkdir(parents=True, exist_ok=True)
    name = "ohne_llm" if args.ohne_ollama else args.modell.replace(":", "_").replace("/", "_")
    datei = AUSGABE / f"hochdeutsch_{name}.csv"

    zeiten, mit_hinweis = [], 0
    with open(datei, "w", newline="", encoding="utf-8-sig") as f:
        schreiber = csv.writer(f, delimiter=";")
        schreiber.writerow(["dialekt", "erwartet (geprüft)", "ki_uebersetzung", "ohne_llm",
                            "gefundene_woerter", "nicht_im_woerterbuch", "bedeutung_fehlt",
                            "sekunden", "bewertung (gut/teils/falsch)", "kommentar"])
        for satz, erwartet in SAETZE:
            e = ki.uebersetzen(uebersetzer, satz, fragen=fragen, phrase_zuerst=False)
            paare = ", ".join(f"{p.dialekt}={p.hochdeutsch}" for p in e.paare)
            fehlt = ", ".join(p.dialekt for p in e.bedeutung_fehlt)
            zeiten.append(e.sekunden)
            mit_hinweis += bool(e.bedeutung_fehlt)
            schreiber.writerow([satz, erwartet, e.text, ki.ohne_llm(satz, e.paare), paare,
                                " ".join(e.nicht_gefunden), fehlt, f"{e.sekunden:.1f}", "", ""])
            print(f"[{e.sekunden:4.1f} s] {satz}\n"
                  f"    erwartet:      {erwartet}\n"
                  f"    KI:            {e.text}\n"
                  f"    ohne LLM:      {ki.ohne_llm(satz, e.paare)}\n"
                  f"    Wörterbuch:    {paare or '(keine)'}\n"
                  f"    nicht drin:    {' '.join(e.nicht_gefunden) or '-'}\n"
                  + (f"    ⚠ Bedeutung nicht verwendet: {fehlt}\n" if fehlt else ""))

    zeiten.sort()
    print(f"Sätze mit ⚠ (von Hand prüfen, ob widersprochen): {mit_hinweis}/{len(zeiten)}")
    if not args.ohne_ollama:
        langsam = sum(z > MAX_SEKUNDEN for z in zeiten)
        print(f"Zeit: Median {zeiten[len(zeiten) // 2]:.1f} s, langsamste {zeiten[-1]:.1f} s, "
              f"über {MAX_SEKUNDEN:.0f} s: {langsam}")
    print("Bedeutung bitte in der CSV bewerten: gut / teils / falsch (Ziel: ≥ 7 gut)")
    print(f"Gespeichert: {datei.relative_to(PROJEKT)}")


if __name__ == "__main__":
    main()
