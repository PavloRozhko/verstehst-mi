"""Prüft die festgelegten Testsätze in scripts/rag_test_hochdeutsch.py (ohne Sprachmodell).

Sinn: Satz 3 ist am 09.10. festgelegt. Diese Tests merken, wenn er versehentlich
geändert wird oder nicht mehr zu den Daten passt.
"""

import csv
import sys
from pathlib import Path

import pytest

from app.uebersetzer import STANDARD_DB, STEIRISCH_DEUTSCH, Uebersetzer, normalisieren
from app.vorschlag import woerter_suchen

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT / "scripts"))
import rag_test_hochdeutsch as rt  # noqa: E402


def geprueft(dateiname):
    """{normalisierter Dialekt: (Dialekt, Hochdeutsch)} aller übernommenen Zeilen."""
    ergebnis = {}
    with open(PROJEKT / "data" / dateiname, encoding="utf-8-sig", newline="") as f:
        for z in csv.DictReader(f):
            if z["status"] == "richtig":
                dialekt = z["dialekt"]
            elif z["status"] == "korrigiert":
                dialekt = z["korrektur"]
            else:
                continue
            ergebnis[normalisieren(dialekt)] = (dialekt.strip(), z["hochdeutsch"].strip())
    return ergebnis


def test_satz_3_hat_10_saetze():
    assert len(rt.SATZ_3) == 10
    assert len({normalisieren(s) for s, _ in rt.SATZ_3}) == 10


def test_satz_3_ohne_saetze_aus_satz_1_und_2():
    alt = {normalisieren(s) for s, _ in rt.SATZ_1 + rt.SATZ_2}
    assert not alt & {normalisieren(s) for s, _ in rt.SATZ_3}


def test_satz_3_stammt_aus_geprueften_phrasen():
    phrasen = geprueft("phrasen.csv")
    for satz, erwartet in rt.SATZ_3:
        assert phrasen[normalisieren(satz)] == (satz, erwartet)


def test_versteckte_woerter_gibt_es_wirklich():
    woerter = geprueft("woerter.csv")
    saetze = {s for s, _ in rt.SATZ_3}
    for satz, paare in rt.VERSTECKT_3.items():
        assert satz in saetze
        for dialekt, hochdeutsch in paare:
            assert woerter[normalisieren(dialekt)] == (dialekt, hochdeutsch)


@pytest.mark.skipif(not STANDARD_DB.exists(), reason="Datenbank fehlt")
def test_versteckte_woerter_werden_nicht_gefunden():
    uebersetzer = Uebersetzer()
    satz = "Glott is."   # bewusst KEIN Testsatz
    vorher = woerter_suchen(uebersetzer, satz, STEIRISCH_DEUTSCH)
    assert ("glott", "glatt") in {(p.dialekt, p.hochdeutsch) for p in vorher}

    ohne = rt.ohne_woerter(uebersetzer, {("glott", "glatt")})
    nachher = woerter_suchen(ohne, satz, STEIRISCH_DEUTSCH)
    assert ("glott", "glatt") not in {(p.dialekt, p.hochdeutsch) for p in nachher}
    # das Original bleibt unverändert
    assert len(uebersetzer.eintraege) == len(ohne.eintraege) + 1
