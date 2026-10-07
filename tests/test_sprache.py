"""Tests für die Spracheingabe (/api/sprache) – ohne echtes Whisper-Modell.

Whisper selbst testen wir hier nicht (zu langsam, Modell nötig); dafür gibt es
scripts/whisper_benchmark.py mit echten Aufnahmen. Hier wird geprüft:
  - kann der Server die Formate der Browser lesen (webm/opus, ogg, mp4/aac)?
  - reagiert die API richtig auf gute und schlechte Aufnahmen?
"""

import io
from fractions import Fraction

import numpy as np
import pytest

from app.sprache import AudioFehler, Spracherkennung
from app.uebersetzer import STANDARD_DB


def ton(sekunden, format="webm", codec="libopus", rate=48000):
    """Erzeugt eine kleine Audiodatei (Sinuston) im Speicher – wie sie ein Browser schickt."""
    import av

    puffer = io.BytesIO()
    with av.open(puffer, "w", format=format) as datei:
        spur = datei.add_stream(codec, rate=rate)
        spur.layout = "mono"
        t = np.arange(int(sekunden * rate)) / rate
        signal = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        for i, start in enumerate(range(0, len(signal), 960)):
            stueck = signal[start:start + 960]
            frame = av.AudioFrame.from_ndarray(stueck.reshape(1, -1), format="flt", layout="mono")
            frame.sample_rate = rate
            frame.pts = start
            frame.time_base = Fraction(1, rate)
            for paket in spur.encode(frame):
                datei.mux(paket)
        for paket in spur.encode(None):
            datei.mux(paket)
    return puffer.getvalue()


# --- Audio lesen ---------------------------------------------------------------

@pytest.mark.parametrize("format, codec", [
    ("webm", "libopus"),   # Chrome, Firefox, Android
    ("ogg", "libopus"),    # ältere Firefox-Versionen
    ("mp4", "aac"),        # Safari / iPhone
])
def test_browser_formate_werden_gelesen(format, codec):
    audio = Spracherkennung().audio_lesen(ton(2, format, codec))
    assert abs(len(audio) / 16000 - 2) < 0.2   # 16 kHz für Whisper


def test_kaputte_datei_gibt_audiofehler():
    with pytest.raises(AudioFehler):
        Spracherkennung().audio_lesen(b"das ist keine Audiodatei")


def test_zu_kurze_aufnahme():
    with pytest.raises(AudioFehler, match="zu kurz"):
        Spracherkennung().audio_lesen(ton(0.1))


def test_zu_lange_aufnahme():
    with pytest.raises(AudioFehler, match="zu lang"):
        Spracherkennung().audio_lesen(ton(20))


def test_prompt_wird_geladen():
    assert "Griaß di" in Spracherkennung().prompt


# --- API mit einer "falschen" Spracherkennung ----------------------------------

class FalscheErkennung:
    """Ersetzt Whisper im Test: gibt einfach einen festen Text zurück."""

    def __init__(self, text="", fehler=None, bereit=True):
        self.text, self.fehler, self.bereit = text, fehler, bereit

    def erkennen(self, daten):
        if self.fehler:
            raise self.fehler
        return self.text


api = pytest.mark.skipif(not STANDARD_DB.exists(),
                         reason="Datenbank fehlt – zuerst scripts/import_csv.py ausführen")


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main

    def mit(erkennung):
        monkeypatch.setattr(app.main, "erkennung", erkennung)
        return TestClient(app.main.app)  # ohne "with": Whisper wird nicht geladen
    return mit


def senden(c, daten=b"audio", **params):
    return c.post("/api/sprache", content=daten, params=params,
                  headers={"Content-Type": "audio/webm"})


@api
def test_erkannter_dialekt_wird_gefunden(client):
    c = client(FalscheErkennung("Griaß di, wia geht's da?"))
    daten = senden(c).json()
    assert daten["erkannt"] == "Griaß di, wia geht's da?"
    assert daten["uebersetzungen"][0]["dialekt"].startswith("Griaß di")


@api
def test_halb_hochdeutsch_erkannt_findet_trotzdem(client):
    # Whisper schreibt Dialekt oft halb Hochdeutsch -> Suche in beiden Spalten
    c = client(FalscheErkennung("Ich habe Hunger"))
    daten = senden(c).json()
    alle = daten["uebersetzungen"] + daten["vorschlaege"]
    assert any("Hunga" in t["dialekt"] for t in alle)


@api
def test_nichts_erkannt_gibt_leeres_ergebnis(client):
    daten = senden(client(FalscheErkennung(""))).json()
    assert daten["erkannt"] == ""
    assert daten["uebersetzungen"] == [] and daten["vorschlaege"] == []


@api
def test_derb_nur_mit_schalter(client):
    c = client(FalscheErkennung("Hoit di Goschn!"))
    assert senden(c).json()["uebersetzungen"] == []
    assert senden(c, derb=True).json()["uebersetzungen"]


@api
def test_leere_aufnahme_400(client):
    assert senden(client(FalscheErkennung("x")), daten=b"").status_code == 400


@api
def test_zu_grosse_aufnahme_413(client):
    from app.main import MAX_AUDIO_BYTES
    antwort = senden(client(FalscheErkennung("x")), daten=b"0" * (MAX_AUDIO_BYTES + 1))
    assert antwort.status_code == 413


@api
def test_modell_nicht_geladen_503(client):
    assert senden(client(FalscheErkennung(bereit=False))).status_code == 503


@api
def test_audiofehler_wird_verstaendlich_gemeldet(client):
    antwort = senden(client(FalscheErkennung(fehler=AudioFehler("Aufnahme ist zu kurz"))))
    assert antwort.status_code == 400
    assert antwort.json()["detail"] == "Aufnahme ist zu kurz"


@api
def test_interner_fehler_verraet_keine_details(client):
    antwort = senden(client(FalscheErkennung(fehler=ValueError("geheimer Pfad /home/szf"))))
    assert antwort.status_code == 500
    assert "geheim" not in antwort.text


@api
def test_status_meldet_spracherkennung(client):
    assert client(FalscheErkennung()).get("/api/status").json()["sprache"] is True
