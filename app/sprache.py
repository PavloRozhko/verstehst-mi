"""Spracherkennung mit Whisper (faster-whisper) für den Web-Server.

Das Modell wird EINMAL beim Start des Servers geladen (dauert ein paar Sekunden)
und dann für jede Aufnahme wiederverwendet.

Einstellungen aus dem Benchmark (Schritt 7b):
    Modell "base" + Prompt  ->  ca. 1 s pro Satz auf dem Jetson (CPU)
    temperature=0           ->  keine Wiederholungen mit höherer "Temperatur",
                                die vorher bis zu 20 s gedauert haben

Filter gegen erfundenen Text (Sprachtest vom 11.10.: Husten -> "Ja, ja, ja, …",
13 s lang). Whisper "erfindet" bei Geräuschen manchmal Text, oft als Endlosschleife:
    MAX_TOKENS     ->  eine Schleife bricht früh ab (ca. 1–2 s statt 13 s)
    verwerfen()    ->  verdächtiger Text wird nicht angezeigt ("Nix verstanden")
"""

import io
import logging
import os
import re
import threading
from collections import Counter
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
MODELL_ORDNER = PROJEKT / "models" / "whisper"
PROMPT_DATEI = PROJEKT / "data" / "whisper_prompt.txt"

MODELL = "base"
# Längere Aufnahmen werden abgelehnt: ein Satz dauert selten über 15 s
MAX_SEKUNDEN = 15

# Höchstens so viele Text-Bausteine (Tokens) pro Aufnahme. Ein Satz braucht etwa
# 10–25, 48 reichen für über 30 Wörter. Wer die Grenze erreicht, steckt fast
# immer in einer Schleife.
MAX_TOKENS = 48

# Ab diesem Wert ist der Text "zu gleichförmig" (Whisper-eigenes Maß, wie stark
# sich der Text zusammenpacken lässt). 2,4 ist der Standardwert von Whisper.
MAX_KOMPRESSION = 2.4

# Bekannte Sätze, die Whisper bei Stille oder Geräusch erfindet: Es wurde mit
# vielen Videos samt Untertiteln trainiert. (Allgemein bekannt, NICHT aus
# unseren Testaufnahmen abgeleitet.)
ERFUNDENE_SAETZE = (
    "untertitel",
    "vielen dank fürs zuschauen",
    "danke fürs zuschauen",
    "bis zum nächsten mal",
    "abonniert den kanal",
)

log = logging.getLogger("uvicorn.error")


class AudioFehler(Exception):
    """Die Aufnahme konnte nicht gelesen werden (falsches Format, leer, kaputt)."""


def prompt_laden(pfad=PROMPT_DATEI):
    """Liest den Whisper-Prompt (typische Dialektsätze) als eine Zeile; None ohne Datei."""
    if not pfad.exists():
        return None
    return " ".join(pfad.read_text(encoding="utf-8").split())


def woerter(text):
    """Zerlegt Text in kleingeschriebene Wörter (für die Suche nach Wiederholungen)."""
    return re.findall(r"[\wäöüß']+", text.lower())


def verwerfen(text, segmente):
    """Gibt den Grund zurück, warum der Text verdächtig ist – oder None, wenn er ok ist.

    segmente: die Abschnitte von Whisper (mit .tokens und .compression_ratio).
    """
    # "- 4": Zeitmarken zählen bei Whisper auch als Tokens, im Abschnitt fehlen sie
    if any(len(s.tokens) >= MAX_TOKENS - 4 for s in segmente):
        return "Token-Grenze erreicht (Schleife)"
    if any(s.compression_ratio > MAX_KOMPRESSION for s in segmente):
        return "zu gleichförmig"

    liste = woerter(text)
    if len(liste) >= 4:
        _wort, anzahl = Counter(liste).most_common(1)[0]
        if anzahl >= 4 and anzahl / len(liste) >= 0.5:
            return "Wiederholung"

    klein = text.lower()
    if any(satz in klein for satz in ERFUNDENE_SAETZE):
        return "typischer erfundener Satz"
    return None


class Spracherkennung:
    """Whisper für den Server: einmal laden, dann jede Aufnahme mit erkennen() umwandeln."""

    def __init__(self, modell_name=MODELL, threads=None):
        """Merkt sich die Einstellungen; das Modell lädt erst laden()."""
        self.modell_name = modell_name
        self.threads = threads or os.cpu_count() or 4
        self.prompt = prompt_laden()
        self.modell = None
        # Whisper soll immer nur EINE Aufnahme gleichzeitig rechnen.
        # Zwei parallel wären nicht schneller (gleiche CPU-Kerne), nur beide langsamer.
        self._sperre = threading.Lock()

    @property
    def bereit(self):
        """True, sobald das Modell geladen ist."""
        return self.modell is not None

    def laden(self):
        """Lädt Whisper von der Festplatte (models/whisper). Dauert ein paar Sekunden."""
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
                max_new_tokens=MAX_TOKENS,         # Schleifen früh abbrechen
            )
            # Erst beim Durchlaufen der Segmente wird wirklich gerechnet
            segmente = list(segmente)

        text = " ".join(s.text.strip() for s in segmente).strip()
        for s in segmente:  # Werte fürs Protokoll: helfen später beim Einstellen
            log.info("Whisper-Abschnitt: no_speech=%.2f logprob=%.2f kompression=%.2f "
                     "tokens=%d", s.no_speech_prob, s.avg_logprob, s.compression_ratio,
                     len(s.tokens))
        grund = verwerfen(text, segmente) if text else None
        if grund:
            log.info("Whisper-Text verworfen (%s): %r", grund, text[:120])
            return ""
        return text
