"""Tests für den KI-Vorschlag (app/vorschlag.py) – ohne echtes Sprachmodell.

Die Antwort von Ollama wird durch einen kleinen Test-Server ersetzt.
Braucht die echte Datenbank: vorher `python scripts/import_csv.py` ausführen.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import vorschlag as v
from app.uebersetzer import STANDARD_DB, Uebersetzer

pytestmark = pytest.mark.skipif(
    not STANDARD_DB.exists(),
    reason="Datenbank fehlt – zuerst scripts/import_csv.py ausführen",
)


@pytest.fixture(scope="module")
def uebersetzer():
    return Uebersetzer()


@pytest.fixture(scope="module")
def woerterbuch(uebersetzer):
    return v.alle_dialektwoerter(uebersetzer)


def dialekte(paare):
    return {p.dialekt for p in paare}


def test_findet_sichere_woerter(uebersetzer):
    paare = v.woerter_suchen(uebersetzer, "Das Wetter ist heute schlecht.")
    assert {"Wetta", "heit", "des"} <= dialekte(paare)


@pytest.mark.parametrize("satz, falsch", [
    ("Gehen wir nach der Pause?", {"Mei", "oda", "schaun", "gebm"}),   # nach≈ach, der≈oder
    ("Mach bitte das Fenster zu.", {"hantig"}),                        # bitte≈bitter
    ("Ich habe keine Zeit.", {"kana"}),                                # keine≈keiner
])
def test_keine_zufallstreffer(uebersetzer, satz, falsch):
    assert not dialekte(v.woerter_suchen(uebersetzer, satz)) & falsch


def test_satz_im_woerterbuch_braucht_kein_llm(uebersetzer):
    def fragen(*_):
        raise AssertionError("LLM darf nicht gefragt werden")

    vs = v.vorschlagen(uebersetzer, "Ich habe heute keine Zeit.", fragen=fragen)
    assert vs.woerterbuch_phrase == "I hob ka Zeit."


def test_ohne_llm_ersetzt_wort_fuer_wort(uebersetzer):
    satz = "Am Donnerstag haben wir frei."
    assert v.ohne_llm(satz, v.woerter_suchen(uebersetzer, satz)) == "am Pfinsta hom mia frei"


def test_markieren(uebersetzer, woerterbuch):
    satz = "Am Donnerstag haben wir frei."
    paare = v.woerter_suchen(uebersetzer, satz)
    ergebnis = dict(v.markieren("Am Pfinsta hobn ma frei, Blunzngraf!", satz, paare, woerterbuch))
    assert ergebnis["pfinsta"] == v.GEPRUEFT
    assert ergebnis["ma"] == v.GEPRUEFT          # "ma" = wir (nachgestellt)
    assert ergebnis["frei"] == v.HOCHDEUTSCH
    assert ergebnis["hobn"] == v.ABGELEITET      # Regel B: gebeugt aus "hom"
    assert ergebnis["blunzngraf"] == v.VERDAECHTIG     # nicht gesucht, nicht im Wörterbuch


def test_kurze_woerter_nie_abgeleitet(woerterbuch):
    paare = [v.Wortpaar("ich", "i", "ich")]
    assert dict(v.markieren("ix", "x", paare, woerterbuch))["ix"] == v.VERDAECHTIG


class FalscherOllama(BaseHTTPRequestHandler):
    anfragen = []

    def do_POST(self):
        laenge = int(self.headers["Content-Length"])
        FalscherOllama.anfragen.append(json.loads(self.rfile.read(laenge)))
        antwort = json.dumps({"message": {"content": "  Des Wetta is heit schiach.\n"}})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(antwort.encode("utf-8"))

    def log_message(self, *_):
        pass


@pytest.fixture
def ollama_url():
    server = HTTPServer(("127.0.0.1", 0), FalscherOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/api/chat"
    server.shutdown()


def test_ganzer_ablauf_mit_falschem_ollama(uebersetzer, woerterbuch, ollama_url):
    FalscherOllama.anfragen.clear()

    def fragen(satz, paare):
        return v.ollama_fragen(satz, paare, url=ollama_url)

    vs = v.vorschlagen(uebersetzer, "Das Wetter ist heute schlecht.",
                       fragen=fragen, woerterbuch=woerterbuch)

    anfrage = FalscherOllama.anfragen[0]
    assert anfrage["model"] == v.MODELL
    assert anfrage["options"]["temperature"] == 0
    assert "das Wetter = Wetta" in anfrage["messages"][1]["content"]

    assert vs.text == "Des Wetta is heit schiach."
    ergebnis = dict(vs.markierungen)
    assert ergebnis["wetta"] == v.GEPRUEFT
    assert ergebnis["schiach"] != v.GEPRUEFT     # nicht gesucht -> nie als geprüft zeigen
