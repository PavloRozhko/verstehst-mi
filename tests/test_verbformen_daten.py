"""Prüft den Testsatz für Experiment A (tests/verbformen.csv), noch ohne Regel.

Der Testsatz ist am 09.10. festgelegt (docs/experimente.md). Diese Tests merken,
wenn er versehentlich geändert wird oder nicht mehr zum Wörterbuch passt.
"""

import csv
from collections import Counter
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
KATEGORIEN = {"regulär": 18, "Klitikon": 3, "unregelmäßig": 20}


def lesen(pfad):
    with open(pfad, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


TESTSATZ = lesen(PROJEKT / "tests" / "verbformen.csv")
WOERTER = {z["id"]: z for z in lesen(PROJEKT / "data" / "woerter.csv")}


def test_anzahl_je_kategorie():
    assert Counter(z["kategorie"] for z in TESTSATZ) == KATEGORIEN


def test_jede_form_nur_einmal():
    assert len({z["id"] for z in TESTSATZ}) == len(TESTSATZ)


def test_form_und_infinitiv_sind_geprueft():
    for z in TESTSATZ:
        form, infinitiv = WOERTER[z["id"]], WOERTER[z["infinitiv_id"]]
        assert (form["dialekt"], form["hochdeutsch"]) == (z["form"], z["bedeutung"])
        assert infinitiv["dialekt"] == z["infinitiv"]
        assert form["status"] == infinitiv["status"] == "richtig"
        assert form["wortart"] == infinitiv["wortart"] == "Verb"
