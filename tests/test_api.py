"""Tests für den Web-Server (ohne echten Browser).

Der TestClient von FastAPI schickt Anfragen direkt an die App.
Braucht die Datenbank: vorher `python3 scripts/import_csv.py` ausführen.
"""

import pytest

from app.uebersetzer import STANDARD_DB

pytestmark = pytest.mark.skipif(
    not STANDARD_DB.exists(),
    reason="Datenbank fehlt – zuerst scripts/import_csv.py ausführen",
)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    return TestClient(app)


def test_startseite_wird_ausgeliefert(client):
    antwort = client.get("/")
    assert antwort.status_code == 200
    assert "verstehst mi?" in antwort.text


def test_status_zeigt_anzahl_eintraege(client):
    assert client.get("/api/status").json()["eintraege"] > 0


def test_exakter_treffer(client):
    daten = client.get("/api/uebersetzen", params={"text": "Servus", "richtung": "st-de"}).json()
    assert daten["uebersetzungen"][0]["dialekt"] == "Servus"


def test_bei_exaktem_treffer_keine_vorschlaege(client):
    # Ohne diese Regel käme bei "Der is ma zwida" auch "Des is ma z'teia"
    daten = client.get("/api/uebersetzen", params={"text": "Der is ma zwida."}).json()
    assert daten["uebersetzungen"]
    assert daten["vorschlaege"] == []


def test_tippfehler_liefert_vorschlag(client):
    daten = client.get("/api/uebersetzen", params={"text": "Mohlzeit"}).json()
    assert daten["uebersetzungen"] == []
    assert daten["vorschlaege"][0]["dialekt"].startswith("Mahlzeit")


def test_derb_nur_mit_schalter(client):
    ohne = client.get("/api/uebersetzen", params={"text": "Hoit di Goschn!"}).json()
    mit = client.get("/api/uebersetzen", params={"text": "Hoit di Goschn!", "derb": True}).json()
    assert ohne["uebersetzungen"] == []
    assert mit["uebersetzungen"]


def test_falsche_richtung_gibt_fehler_400(client):
    antwort = client.get("/api/uebersetzen", params={"text": "Servus", "richtung": "xx"})
    assert antwort.status_code == 400


def test_zu_langer_text_wird_abgelehnt(client):
    antwort = client.get("/api/uebersetzen", params={"text": "a" * 301})
    assert antwort.status_code == 422