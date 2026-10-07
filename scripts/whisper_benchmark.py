"""Misst, wie schnell und wie gut Whisper auf dem Jetson erkennt.

Aufruf (im Projektordner, mit aktiviertem .venv):
    python scripts/whisper_benchmark.py aufnahme.m4a
    python scripts/whisper_benchmark.py aufnahme.m4a --modelle base small
    python scripts/whisper_benchmark.py aufnahme.m4a --prompt data/whisper_prompt.txt
    python scripts/whisper_benchmark.py aufnahme.m4a --uebersetzen

Beim ersten Lauf wird jedes Modell aus dem Internet geladen (nach models/whisper/).
"""

import argparse
import os
import sys
import time
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
MODELL_ORDNER = PROJEKT / "models" / "whisper"
sys.path.insert(0, str(PROJEKT))  # damit "app" importiert werden kann


def messen(modell_name, audio, args, prompt):
    from faster_whisper import WhisperModel

    start = time.perf_counter()
    modell = WhisperModel(
        modell_name,
        device=args.geraet,
        compute_type=args.rechenart,
        cpu_threads=args.threads,
        download_root=str(MODELL_ORDNER),
    )
    ladezeit = time.perf_counter() - start

    # Erster Durchlauf "wärmt auf", gemessen wird der zweite
    for _ in range(2):
        start = time.perf_counter()
        segmente, info = modell.transcribe(
            str(audio),
            language="de",          # Deutsch vorgeben: schneller und zuverlässiger
            beam_size=1,            # einfachste Suche: am schnellsten
            vad_filter=True,        # Stille am Anfang/Ende ignorieren
            initial_prompt=prompt,  # Beispieltext: zeigt Whisper typische Dialektwörter
        )
        text = " ".join(s.text.strip() for s in segmente)  # erst hier wird wirklich gerechnet
        erkennzeit = time.perf_counter() - start

    return ladezeit, erkennzeit, info.duration, text


def uebersetzung(text):
    """Was würde unser Übersetzer aus dem erkannten Text machen?"""
    from app.uebersetzer import Uebersetzer
    treffer = Uebersetzer().sprache_suchen(text, mit_derb=True, limit=1)
    if not treffer:
        return "—"
    t = treffer[0]
    return f"{t.dialekt} → {t.hochdeutsch} ({t.score})"


def main():
    parser = argparse.ArgumentParser(description="Whisper-Geschwindigkeit messen")
    parser.add_argument("audio", type=Path, help="WAV/MP3/M4A-Datei mit Sprache")
    parser.add_argument("--modelle", nargs="+", default=["tiny", "base", "small"])
    parser.add_argument("--geraet", default="cpu", help="cpu oder cuda")
    parser.add_argument("--rechenart", default="int8", help="int8 (CPU) oder float16 (GPU)")
    parser.add_argument("--threads", type=int, default=os.cpu_count(),
                        help="Anzahl CPU-Kerne (Standard: alle)")
    parser.add_argument("--prompt", type=Path, help="Textdatei mit typischen Dialektwörtern")
    parser.add_argument("--uebersetzen", action="store_true",
                        help="erkannten Text zusätzlich im Wörterbuch suchen")
    args = parser.parse_args()

    if not args.audio.exists():
        raise SystemExit(f"Datei nicht gefunden: {args.audio}")

    prompt = None
    if args.prompt:
        prompt = " ".join(args.prompt.read_text(encoding="utf-8").split())

    print(f"Audio: {args.audio.name} | Gerät: {args.geraet} | Threads: {args.threads} "
          f"| Prompt: {'ja' if prompt else 'nein'}\n")
    print(f"{'Modell':8} {'laden':>7} {'erkennen':>9} {'Audio':>6} {'Faktor':>7}  Text")
    for name in args.modelle:
        ladezeit, erkennzeit, dauer, text = messen(name, args.audio, args, prompt)
        faktor = erkennzeit / dauer if dauer else 0  # < 1 = schneller als Echtzeit
        print(f"{name:8} {ladezeit:6.1f}s {erkennzeit:8.2f}s {dauer:5.1f}s {faktor:6.2f}x  {text}")
        if args.uebersetzen:
            print(f"{'':45}→ {uebersetzung(text)}")


if __name__ == "__main__":
    main()