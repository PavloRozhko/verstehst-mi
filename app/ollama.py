"""Verbindung zum lokalen Sprachmodell (Ollama auf dem Jetson).

Ollama läuft als eigener Dienst auf localhost:11434 und hält das Modell im Speicher.
Hier steht nur die eine Funktion, die eine Frage schickt und die Antwort zurückgibt –
alle Teile des Projekts, die ein Sprachmodell fragen, benutzen sie.
"""

import json
import time
import urllib.request

OLLAMA = "http://localhost:11434/api/chat"
MODELL = "gemma3:4b"


def ollama_chat(system, frage, modell=MODELL, url=OLLAMA, num_predict=60,
                keep_alive="10m", timeout=180):
    """Schickt eine Frage an Ollama und wartet auf die Antwort.

    system:      Anweisungen an das Modell (Rolle und Regeln)
    frage:       die eigentliche Frage (Satz + Liste der geprüften Wörter)
    num_predict: höchstens so viele Tokens darf die Antwort haben
    keep_alive:  wie lange Ollama das Modell danach im Speicher hält (-1 = für immer)
    timeout:     so viele Sekunden wird höchstens gewartet

    Gibt (Antwort, Sekunden) zurück. Temperatur 0: gleiche Frage -> gleiche Antwort.
    Fehler (Ollama aus, Zeit abgelaufen) werden als Ausnahme weitergegeben.
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
