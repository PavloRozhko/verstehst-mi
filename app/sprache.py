"""Spracherkennung mit Whisper (faster-whisper) für den Web-Server.

Das Modell wird EINMAL beim Start des Servers geladen (dauert ein paar Sekunden)
und dann für jede Aufnahme wiederverwendet.

Einstellungen aus dem Benchmark (Schritt 7b):
    Modell "base" + Prompt  ->  ca. 1 s pro Satz auf dem Jetson (CPU)
    temperature=0           ->  keine Wiederholungen mit höherer "Temperatur",
                                die vorher bis zu 20 s gedauert haben
"""

import io
import os
import threading
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
MODELL_ORDNER = PROJEKT / "models" / "whisper"
PROMPT_DATEI = PROJEKT / "data" / "whisper_prompt.txt"

MODELL = "base"
# Längere Aufnahmen werden abgelehnt: ein Satz dauert selten über 15 s
MAX_SEKUNDEN = 15


class AudioFehler(Exception):
    """Die Aufnahme konnte nicht gelesen werden (falsches Format, leer, kaputt)."""


def prompt_laden(pfad=PROMPT_DATEI):
    if not pfad.exists():
        return None
    return " ".join(pfad.read_text(encoding="utf-8").split())


class Spracherkennung:
    def __init__(self, modell_name=MODELL, threads=None):
        self.modell_name = modell_name
        self.threads = threads or os.cpu_count() or 4
        self.prompt = prompt_laden()
        self.modell = None
        # Whisper soll immer nur EINE Aufnahme gleichzeitig rechnen.
        # Zwei parallel wären nicht schneller (gleiche CPU-Kerne), nur beide langsamer.
        self._sperre = threading.Lock()

    @property
    def bereit(self):
        return self.modell is not None

    def laden(self):
        from faster_whisper import WhisperModel  # erst hier importieren: Tests brauchen es nicht

        self.modell = WhisperModel(
            self.modell_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=self.threads,
            download_root=str(MODELL_ORDNER),
        )

    def audio_lesen(self, daten):
        """Wandelt die Aufnahme (webm/ogg/mp4/wav …) in Rohdaten für Whisper um."""
        from faster_whisper import decode_audio

        try:
            audio = decode_audio(io.BytesIO(daten))  # 16 kHz, mono
        except Exception as fehler:  # PyAV wirft je nach Format verschiedene Fehler
            raise AudioFehler("Aufnahme konnte nicht gelesen werden") from fehler

        sekunden = len(audio) / 16000
        if sekunden < 0.3:
            raise AudioFehler("Aufnahme ist zu kurz")
        if sekunden > MAX_SEKUNDEN:
            raise AudioFehler(f"Aufnahme ist zu lang (max. {MAX_SEKUNDEN} s)")
        return audio

    def erkennen(self, daten):
        """Gibt den erkannten Text zurück ("" wenn nichts verstanden wurde)."""
        if not self.bereit:
            raise RuntimeError("Modell ist noch nicht geladen")

        audio = self.audio_lesen(daten)
        with self._sperre:
            segmente, _info = self.modell.transcribe(
                audio,
                language="de",
                beam_size=1,
                temperature=0,                     # nur EIN Versuch, keine Wiederholungen
                vad_filter=True,                   # Stille am Anfang/Ende ignorieren
                condition_on_previous_text=False,  # jeder Satz für sich
                initial_prompt=self.prompt,
            )
            # Erst beim Durchlaufen der Segmente wird wirklich gerechnet
            return " ".join(s.text.strip() for s in segmente).strip()
