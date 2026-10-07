"""Tests für die Seite /qr und die Adresse des Jetson im WLAN."""

import ipaddress

import pytest

from app.netz import lan_ip, qr_svg
from app.uebersetzer import STANDARD_DB


def test_lan_ip_ist_gueltige_ipv4():
    ip = ipaddress.ip_address(lan_ip())
    assert ip.version == 4


def test_qr_svg_wird_erzeugt():
    svg = qr_svg("https://192.168.1.50:8000")
    assert svg.lstrip().startswith(b"<svg")


api = pytest.mark.skipif(not STANDARD_DB.exists(),
                         reason="Datenbank fehlt – zuerst scripts/import_csv.py ausführen")


def client(basis):
    from fastapi.testclient import TestClient

    from app.main import app
    return TestClient(app, base_url=basis)


@api
def test_adresse_mit_https_und_port(monkeypatch):
    monkeypatch.setattr("app.main.lan_ip", lambda: "192.168.1.50")
    url = client("https://localhost:8000").get("/api/adresse").json()["url"]
    # Auch wenn die Seite am Jetson über localhost geöffnet wird: im QR steht die WLAN-IP
    assert url == "https://192.168.1.50:8000"


@api
def test_adresse_ohne_standardport(monkeypatch):
    monkeypatch.setattr("app.main.lan_ip", lambda: "192.168.1.50")
    assert client("http://localhost").get("/api/adresse").json()["url"] == "http://192.168.1.50"


@api
def test_qr_bild_ist_svg():
    antwort = client("https://localhost:8000").get("/api/qr.svg")
    assert antwort.status_code == 200
    assert antwort.headers["content-type"].startswith("image/svg+xml")


@api
def test_qr_seite_wird_ausgeliefert():
    antwort = client("https://localhost:8000").get("/qr")
    assert antwort.status_code == 200
    assert "QR-Code" in antwort.text
