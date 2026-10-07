"""Experiment: Kann ein lokales Sprachmodell (LLM) Wörterbuch-Einträge gut erklären?

Idee (Variante B): Dialekt und Übersetzung kommen IMMER aus dem geprüften Wörterbuch.
Das Modell schreibt nur eine kurze ERKLÄRUNG auf Hochdeutsch – nie selbst Dialekt.

Voraussetzung: Ollama läuft auf dem Jetson (http://localhost:11434) und das Modell
ist geladen, z. B.  ollama pull gemma3:4b

Aufruf (im Projektordner, mit aktiviertem .venv):
    python scripts/llm_test.py gemma3:4b             # Satz 1: zum Verbessern des Prompts
    python scripts/llm_test.py gemma3:4b --satz 2    # Satz 2: neue Einträge, nur zum Bewerten

Warum zwei Sätze? Den Prompt verbessern wir mit Satz 1. Würden wir mit denselben
Einträgen auch bewerten, wäre das Ergebnis geschönt ("auf den Test hin optimiert").
Satz 2 hat das Modell mit dem neuen Prompt noch nie gesehen – das ist der ehrliche Test.

Ergebnis: models/llm_test/<modell>_satz<N>.csv – zum Bewerten durch Muttersprachler
(Spalte "bewertung": gut / teils / falsch).
"""

import argparse
import csv
import json
import sqlite3
import time
import urllib.request
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
DB = PROJEKT / "data" / "verstehst_mi.db"
AUSGABE = PROJEKT / "models" / "llm_test"   # models/ steht in .gitignore
OLLAMA = "http://localhost:11434/api/chat"

# Bewusst gemischt: Grüße, Redewendungen, Wörter, ein mehrdeutiger und ein derber Ausdruck
SATZ_1 = [
    "Griaß di, wia geht's da?",
    "Mahlzeit!",
    "Des passt scho.",
    "Na no na ned.",
    "Sei ned so gschamig!",
    "Der Chef is heit grantig.",
    "Bist deppat!",
    "Schleich di!",
    "Paradeiser",
    "Hawara",
]

# Zufällig gezogen (ohne Satz 1), erst NACH der Prompt-Verbesserung verwendet
SATZ_2 = [
    "Wos is'n des für a Gschiss?",
    "Deis is ma wurscht.",
    "Mia segn uns.",
    "Des is ma z'teia.",
    "Mia is fad.",
    "Kumm, loss den Schas, gemma ham.",
    "Rauchfang",
    "Na servas",
    "fuxn",
    "Hackn",
]

# Version 2 – nach Satz 1 verbessert:
# - Thema nicht mehr mitschicken (das Modell hat "Familie" als Situation übernommen)
# - Ausdruck nicht wiederholen (es hat "Der Chef ist heit" falsch zitiert)
# - nichts über Herkunft/Region behaupten ("Paradeiser" ist nicht nur steirisch)
SYSTEM = """Du bist ein Sprachhelfer für Menschen, die Deutsch lernen und in der Steiermark leben.
Du bekommst einen GEPRÜFTEN Eintrag aus einem Wörterbuch: einen Ausdruck aus dem steirischen
Dialekt und seine hochdeutsche Bedeutung. Die Bedeutung ist richtig. Widersprich ihr nicht.

Schreib genau 2 kurze Sätze in einfachem Hochdeutsch (Niveau B1):
1. In welcher Alltagssituation sagt man das?
2. Wie klingt es: freundlich, neutral, locker, ironisch oder grob?

Regeln:
- Beginne direkt mit der Erklärung. Wiederhole oder zitiere den Ausdruck NICHT.
- Schreib selbst NIE Dialekt und erfinde keine Beispielsätze.
- Sag nichts über Herkunft, Region oder Geschichte des Ausdrucks.
- Wenn du etwas nicht sicher weißt, lass es weg."""


def eintrag_laden(verbindung, dialekt):
    zeile = verbindung.execute(
        "SELECT dialekt, hochdeutsch, thema, derb FROM eintraege WHERE dialekt = ?",
        (dialekt,),
    ).fetchone()
    if zeile is None:
        raise SystemExit(f"Nicht im Wörterbuch: {dialekt!r} – zuerst scripts/import_csv.py ausführen")
    return zeile


def frage_text(eintrag):
    dialekt, hochdeutsch, _thema, derb = eintrag
    return (f"Ausdruck: {dialekt}\n"
            f"Bedeutung: {hochdeutsch}\n"
            f"Derb: {'ja' if derb else 'nein'}")


def erklaeren(modell, eintrag, url=OLLAMA):
    """Fragt Ollama und gibt (Erklärung, Sekunden, Tokens pro Sekunde) zurück."""
    anfrage = {
        "model": modell,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": frage_text(eintrag)},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 120},
        "keep_alive": "10m",   # Modell zwischen den Fragen im Speicher lassen
    }
    daten = json.dumps(anfrage).encode("utf-8")
    req = urllib.request.Request(url, data=daten, headers={"Content-Type": "application/json"})

    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as antwort:
        ergebnis = json.load(antwort)
    sekunden = time.perf_counter() - start

    text = ergebnis["message"]["content"].strip()
    # Ollama meldet, wie viele Tokens erzeugt wurden und wie lange das gedauert hat (ns)
    tokens = ergebnis.get("eval_count", 0)
    dauer_ns = ergebnis.get("eval_duration", 0)
    tps = tokens / (dauer_ns / 1e9) if dauer_ns else 0.0
    return text, sekunden, tps


def main():
    parser = argparse.ArgumentParser(description="LLM-Erklärungen testen")
    parser.add_argument("modell", help="z. B. gemma3:4b")
    parser.add_argument("--satz", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    modell = args.modell

    verbindung = sqlite3.connect(DB)
    eintraege = [eintrag_laden(verbindung, d) for d in (SATZ_1 if args.satz == 1 else SATZ_2)]
    verbindung.close()

    # Aufwärmen: die erste Anfrage lädt das Modell in den Speicher (zählt nicht)
    print(f"Lade {modell} …")
    try:
        _, ladezeit, _ = erklaeren(modell, eintraege[0])
    except OSError as fehler:
        raise SystemExit(f"Ollama nicht erreichbar ({fehler}). Läuft 'ollama serve'?")
    print(f"Erste Antwort (inkl. Laden): {ladezeit:.1f} s\n")

    AUSGABE.mkdir(parents=True, exist_ok=True)
    datei = AUSGABE / f"{modell.replace(':', '_').replace('/', '_')}_satz{args.satz}.csv"
    zeiten = []
    with open(datei, "w", newline="", encoding="utf-8-sig") as f:   # -sig: Excel erkennt UTF-8
        schreiber = csv.writer(f, delimiter=";")
        schreiber.writerow(["dialekt", "bedeutung", "erklaerung", "sekunden", "tokens_pro_s",
                            "bewertung (gut/teils/falsch)", "kommentar"])
        for eintrag in eintraege:
            text, sekunden, tps = erklaeren(modell, eintrag)
            zeiten.append(sekunden)
            schreiber.writerow([eintrag[0], eintrag[1], text, f"{sekunden:.1f}", f"{tps:.1f}", "", ""])
            print(f"[{sekunden:4.1f} s | {tps:4.1f} tok/s] {eintrag[0]}\n    {text}\n")

    zeiten.sort()
    print(f"Median: {zeiten[len(zeiten) // 2]:.1f} s, langsamste: {zeiten[-1]:.1f} s")
    print(f"Gespeichert: {datei.relative_to(PROJEKT)}")


if __name__ == "__main__":
    main()
