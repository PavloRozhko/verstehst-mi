"""Tests für die Verbform-Regel (app/verbformen.py, Experiment A)."""

import copy
import csv
from pathlib import Path

import pytest

from app.uebersetzer import (
    DEUTSCH_STEIRISCH,
    STANDARD_DB,
    STEIRISCH_DEUTSCH,
    Uebersetzer,
    normalisieren,
)
from app.verbformen import infinitiv_suchen, staemme_der_form
from app.vorschlag import woerter_suchen

PROJEKT = Path(__file__).resolve().parent.parent


def test_staemme_einer_form():
    # "mochs" (nur -t ab) entsteht nebenbei, passt aber zu keinem Infinitiv
    assert staemme_der_form("mochst") == {"mochst", "mochs", "moch"}
    assert "kumm" in staemme_der_form("kummts")
    assert "moch" in staemme_der_form("gmocht")


def test_zu_kurze_staemme_zaehlen_nicht():
    assert staemme_der_form("is") == set()
    assert "ho" not in staemme_der_form("host")


mit_db = pytest.mark.skipif(not STANDARD_DB.exists(), reason="Datenbank fehlt")


@pytest.fixture(scope="module")
def uebersetzer():
    return Uebersetzer()


def ohne(uebersetzer, dialekt):
    kopie = copy.copy(uebersetzer)
    kopie.eintraege = [e for e in uebersetzer.eintraege if e["zeile"]["dialekt"] != dialekt]
    return kopie


@mit_db
def test_go_kriterien_testsatz(uebersetzer):
    """Die Go-Kriterien aus docs/experimente.md (Teil 1) bleiben erfüllt."""
    with open(PROJEKT / "tests" / "verbformen.csv", encoding="utf-8-sig", newline="") as f:
        zeilen = list(csv.DictReader(f))
    richtig, falsche = 0, []
    for z in zeilen:
        gefunden = [t.dialekt for t in infinitiv_suchen(ohne(uebersetzer, z["form"]),
                                                         normalisieren(z["form"]))]
        falsche += [(z["form"], g) for g in gefunden if g != z["infinitiv"]]
        richtig += z["kategorie"] == "regulär" and z["infinitiv"] in gefunden
    assert richtig >= 15
    assert falsche == []


@mit_db
def test_gebeugte_form_ist_kein_infinitiv(uebersetzer):
    # "host'n" (= hast du denn) steht als Verb im Wörterbuch, ist aber kein Infinitiv
    assert infinitiv_suchen(ohne(uebersetzer, "host"), "host") == []


@mit_db
def test_satz_findet_abgeleitete_form(uebersetzer):
    paare = woerter_suchen(ohne(uebersetzer, "mochst"), "Wos mochst?", STEIRISCH_DEUTSCH)
    paar = next(p for p in paare if p.suchwort == "mochst")
    assert (paar.dialekt, paar.hochdeutsch, paar.abgeleitet) == ("mochn", "machen", True)


@mit_db
def test_geprueftes_wort_hat_vorrang(uebersetzer):
    paare = woerter_suchen(uebersetzer, "Wos mochst?", STEIRISCH_DEUTSCH)
    paar = next(p for p in paare if p.suchwort == "mochst")
    assert (paar.dialekt, paar.abgeleitet) == ("mochst", False)


@mit_db
def test_nur_richtung_dialekt(uebersetzer):
    paare = woerter_suchen(ohne(uebersetzer, "mochst"), "mochst", DEUTSCH_STEIRISCH)
    assert not any(p.abgeleitet for p in paare)
