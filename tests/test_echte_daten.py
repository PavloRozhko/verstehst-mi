"""Regressionstests mit dem echten, geprüften Wörterbuch.

Die Testfälle stehen in tests/faelle.csv – ein neuer Test ist einfach eine neue Zeile:

    richtung  eingabe          erwartet           notiz
    st-de     Mohlzeit         Guten Appetit! ... Tippfehler
    st-de     Hoit di Goschn!                     leer = es darf KEIN Treffer kommen

"erwartet" ist die Übersetzung (bei st-de der hochdeutsche Text, bei de-st der Dialekt).
Der Test besteht, wenn "erwartet" unter den besten Treffern ist.

Diese Tests brauchen die Datenbank: vorher `python3 scripts/import_csv.py` ausführen.
"""

import csv
from pathlib import Path

import pytest

from app.uebersetzer import STANDARD_DB, STEIRISCH_DEUTSCH, Uebersetzer

FAELLE = Path(__file__).resolve().parent / "faelle.csv"

pytestmark = pytest.mark.skipif(
    not STANDARD_DB.exists(),
    reason="Datenbank fehlt – zuerst scripts/import_csv.py ausführen",
)


def faelle_laden():
    with open(FAELLE, encoding="utf-8-sig", newline="") as datei:
        return [
            pytest.param(
                zeile["richtung"].strip(),
                zeile["eingabe"],
                zeile["erwartet"].strip(),
                id=f"{zeile['richtung']}: {zeile['eingabe']}",
            )
            for zeile in csv.DictReader(datei)
        ]


def ziel(treffer, richtung):
    """Die Übersetzung, also die 'andere Seite' des Treffers."""
    return treffer.hochdeutsch if richtung == STEIRISCH_DEUTSCH else treffer.dialekt


@pytest.fixture(scope="module")
def uebersetzer():
    return Uebersetzer()


@pytest.mark.parametrize("richtung, eingabe, erwartet", faelle_laden())
def test_echter_fall(uebersetzer, richtung, eingabe, erwartet):
    treffer = uebersetzer.uebersetzen(eingabe, richtung)
    gefunden = [f"{ziel(t, richtung)} ({t.art} {t.score})" for t in treffer]

    if not erwartet:
        assert treffer == [], f"Erwartet: kein Treffer. Bekommen: {gefunden}"
        return

    assert treffer, "Kein Treffer, erwartet war: " + erwartet

    # Mehrere Treffer können gleich gut sein (z. B. "tschüss" -> Servus, Baba ...)
    bester_score = treffer[0].score
    beste = [ziel(t, richtung) for t in treffer if t.score == bester_score]
    assert erwartet in beste, f"Erwartet: {erwartet!r}. Bekommen: {gefunden}"