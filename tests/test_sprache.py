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


# --- Filter gegen erfundenen Text (Sprachtest vom 11.10.) -------------------------

import zlib
from types import SimpleNamespace

from app import sprache


def abschnitt(text, tokens=None):
    """Nachgebauter Whisper-Abschnitt. Kompression wie bei Whisper berechnet."""
    roh = text.encode("utf-8")
    return SimpleNamespace(
        text=text,
        tokens=list(range(tokens if tokens is not None else 2 * len(text.split()) + 2)),
        compression_ratio=len(roh) / len(zlib.compress(roh)),
        no_speech_prob=0.1, avg_logprob=-0.4,
    )


# Alles, was Whisper am 11.10. bei echter Sprache erkannt hat – auch falsch Gehörtes.
# Der Filter darf davon NICHTS verwerfen (falsch gehört ist nicht erfunden).
ECHTE_SPRACHE = [
    "Mahlzeit!", "Woß ist los?", "Des passt scho.", "I woaß ned.", "Wos kost des?",
    "Ich hob an Hunga.", "Gemma wos essn.", "Zoin, bitte!", "Ab hier, kich scho no.",
    "Gemma ham.", "Zainettschop.", "Sein Netz, so geschämig.", "Ich fuwa mi am Radl.",
    "Bros beihand.", "Der Scherf ist halt grantig.", "Ich hob mich vergangen.",
    "Schau no.", "Ich schau no.", "Gehbitte.", "Mia moch na paus.", "Niemand schürm mit.",
    "Wehr spätis.", "Griaß di, wie geht's da?", "Husten, Porusche.",
    "Ich kieh an noaof ons.", "Prost bei Hand.", "Wär spätis.", "Kebite.",
    "Die Poe hottest Radel vergessen.", "Heiz, Hop, Iuna.", "Hier, top, Hunga.",
    "Der Haarekung, Teintnett.", "Das Bette ist heizlich.", "Des Maidel ist geschenk.",
    "Herst, gumm ham.", "Das ist Harder für mir.", "Das ist Ravacher von mir.",
    "Des ist sach, Adagafomia.", "Der Krampus kommt.",
]


@pytest.mark.parametrize("text", ECHTE_SPRACHE)
def test_echte_sprache_wird_nicht_verworfen(text):
    assert sprache.verwerfen(text, [abschnitt(text)]) is None


def test_normaler_satz_mit_wiederholtem_wort_bleibt():
    text = "Des is ned so, des is ned so schlimm."
    assert sprache.verwerfen(text, [abschnitt(text)]) is None


@pytest.mark.parametrize("text", [
    "Ja, " * 30 + "ja",                       # Husten am 11.10.
    "Der Schalz, " * 20 + "der Schal",        # Husten am 11.10.
])
def test_schleifen_werden_verworfen(text):
    assert sprache.verwerfen(text, [abschnitt(text)]) is not None


def test_token_grenze_wird_verworfen():
    text = "irgendwas ganz anderes ohne Wiederholung"
    assert sprache.verwerfen(text, [abschnitt(text, tokens=sprache.MAX_TOKENS)]) is not None


def test_kurze_wiederholung_wird_verworfen():
    assert sprache.verwerfen("Ja, ja, ja, ja.", [abschnitt("Ja, ja, ja, ja.")]) is not None


@pytest.mark.parametrize("text", [
    "Untertitel im Auftrag des ZDF, 2021",
    "Vielen Dank fürs Zuschauen!",
])
def test_typische_erfundene_saetze(text):
    assert sprache.verwerfen(text, [abschnitt(text)]) is not None


class FalschesModell:
    """Ersetzt WhisperModel: liefert feste Abschnitte und merkt sich die Einstellungen."""

    def __init__(self, *texte):
        self.texte, self.optionen = texte, None

    def transcribe(self, audio, **optionen):
        self.optionen = optionen
        return iter([abschnitt(t) for t in self.texte]), None


def erkennung_mit(modell):
    e = Spracherkennung()
    e.modell = modell
    return e


def test_erkennen_begrenzt_tokens():
    modell = FalschesModell("Des passt scho.")
    assert erkennung_mit(modell).erkennen(ton(2)) == "Des passt scho."
    assert modell.optionen["max_new_tokens"] == sprache.MAX_TOKENS


def test_erkennen_gibt_leer_bei_schleife():
    modell = FalschesModell("Ja, " * 30 + "ja")
    assert erkennung_mit(modell).erkennen(ton(2)) == ""


def test_prompt_plus_tokens_passt_ins_modell():
    # Whisper verarbeitet höchstens 448 Tokens (Prompt + Antwort). Grobe, sichere
    # Schätzung ohne Tokenizer: höchstens 4 Tokens pro Wort im Prompt.
    prompt = Spracherkennung().prompt
    assert 4 * len(prompt.split()) + sprache.MAX_TOKENS + 10 < 448


def test_prompt_wird_nicht_abgeschnitten():
    # faster-whisper nimmt vom Prompt nur die LETZTEN 223 Tokens – was davor steht, fällt
    # still weg. Gemessen am 11.10. mit dem Whisper-Tokenizer: 198 Tokens bei 476 Zeichen.
    # Ohne Tokenizer im Test prüfen wir die Zeichen: 500 Zeichen ≈ 213 Tokens.
    assert len(Spracherkennung().prompt) <= 500
