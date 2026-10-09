"""Tests für /api/ki_uebersetzung und KiModell – ohne echtes Ollama.

Ein Mini-Server spielt Ollama (nur /api/chat), damit wir sehen, was wirklich
geschickt wird (z. B. keep_alive = -1). Braucht die Datenbank (scripts/import_csv.py).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import ki_hochdeutsch as ki
from app.uebersetzer import STANDARD_DB

pytestmark = pytest.mark.skipif(not STANDARD_DB.exists(), reason="Datenbank fehlt")

SATZ = "Wos tuast heit Blunzngraf?"   # nicht im Wörterbuch, "Blunzngraf" ist erfunden


class FalschesModell:
    """Ersetzt KiModell in der App."""

    def __init__(self, bereit=True, antwort="Was machst du heute?", fehler=None):
        self.bereit = bereit
        self.antwort = antwort
        self.fehler = fehler
        self.aufgewaermt = 0
        self.laedt = False
        self.letzter_fehler = None

    def fragen(self, satz, paare):
        if self.fehler:
            raise self.fehler
        return self.antwort, 0.1

    def im_hintergrund_aufwaermen(self):
        self.aufgewaermt += 1


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    return TestClient(app)        # ohne "with": Whisper und gemma werden NICHT geladen


def anfrage(client, monkeypatch, modell, text=SATZ):
    monkeypatch.setattr("app.main.ki_modell", modell)
    antwort = client.get("/api/ki_uebersetzung", params={"text": text})
    assert antwort.status_code == 200
    return antwort.json()


def test_ki_uebersetzung(client, monkeypatch):
    daten = anfrage(client, monkeypatch, FalschesModell())
    assert daten["quelle"] == "ki"
    assert daten["uebersetzung"] == "Was machst du heute?"
    assert daten["nicht_gefunden"] == ["blunzngraf"]
    assert {"wort": "heit", "dialekt": "heit", "hochdeutsch": "heute",
            "abgeleitet": False, "derb": False} in daten["woerter"]
    assert daten["hinweis"] is None


def test_phrase_aus_woerterbuch_ohne_ki(client, monkeypatch):
    modell = FalschesModell(fehler=AssertionError("KI darf nicht gefragt werden"))
    daten = anfrage(client, monkeypatch, modell, text="Heit is vü z'tuan.")
    assert daten["quelle"] == "wörterbuch"
    assert daten["uebersetzung"] == "Heute gibt es viel zu tun."


def test_ki_laedt_noch(client, monkeypatch):
    modell = FalschesModell(bereit=False)
    daten = anfrage(client, monkeypatch, modell)
    assert daten["quelle"] == "nur_woerter"
    assert daten["uebersetzung"] is None
    assert "lädt" in daten["hinweis"]
    assert daten["woerter"]                 # Wortbedeutungen gibt es trotzdem
    assert modell.aufgewaermt == 1


def test_ollama_laeuft_nicht(client, monkeypatch):
    modell = FalschesModell(bereit=False)
    modell.letzter_fehler = "Connection refused"
    daten = anfrage(client, monkeypatch, modell)
    assert daten["quelle"] == "nur_woerter"
    assert "nicht erreichbar" in daten["hinweis"]


def test_ki_fehler_gibt_nur_woerter(client, monkeypatch):
    modell = FalschesModell(fehler=OSError("Verbindung abgelehnt"))
    daten = anfrage(client, monkeypatch, modell)
    assert daten["quelle"] == "nur_woerter"
    assert modell.bereit is False and modell.aufgewaermt == 1


def test_ki_ausgeschaltet(client, monkeypatch):
    daten = anfrage(client, monkeypatch, None)
    assert daten["quelle"] == "nur_woerter"
    assert "ausgeschaltet" in daten["hinweis"]


def test_status_zeigt_ki(client, monkeypatch):
    monkeypatch.setattr("app.main.ki_modell", FalschesModell(bereit=True))
    assert client.get("/api/status").json()["ki"] is True
    monkeypatch.setattr("app.main.ki_modell", None)
    assert client.get("/api/status").json()["ki"] is False


def test_leerer_text(client):
    assert client.get("/api/ki_uebersetzung", params={"text": "  "}).status_code == 400


# --- KiModell gegen einen falschen Ollama-Server ---------------------------------------

@pytest.fixture
def falsches_ollama():
    anfragen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            laenge = int(self.headers["Content-Length"])
            anfragen.append(json.loads(self.rfile.read(laenge)))
            antwort = json.dumps({"message": {"content": " Was machst du heute? "}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(antwort)))
            self.end_headers()
            self.wfile.write(antwort)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/api/chat", anfragen
    server.shutdown()


def test_aufwaermen_haelt_modell_im_speicher(falsches_ollama):
    url, anfragen = falsches_ollama
    modell = ki.KiModell(url=url)
    assert modell.aufwaermen() is True
    assert modell.bereit
    assert anfragen[0]["keep_alive"] == -1
    assert anfragen[0]["model"] == "gemma3:4b"

    text, _ = modell.fragen("Wos tuast?", [])
    assert text == "Was machst du heute?"
    assert anfragen[1]["keep_alive"] == -1


def test_aufwaermen_ohne_ollama():
    modell = ki.KiModell(url="http://127.0.0.1:9/api/chat")   # Port 9: dort läuft nichts
    assert modell.aufwaermen() is False
    assert not modell.bereit and not modell.laedt
    assert modell.letzter_fehler


def test_derbes_wort_ist_markiert(client, monkeypatch):
    # "Bist deppat!" steht als Phrase im Wörterbuch – deshalb ein anderer Satz
    daten = anfrage(client, monkeypatch, FalschesModell(antwort="Der Kumpel ist dumm."),
                    text="Der Hawara is deppat.")
    assert daten["quelle"] == "ki"
    deppat = next(w for w in daten["woerter"] if w["wort"] == "deppat")
    assert deppat["derb"] is True
    assert "deppat" not in daten["nicht_gefunden"]
