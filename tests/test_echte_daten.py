"""Regressionstests mit dem echten, geprüften Wörterbuch.

Die Testfälle stehen in tests/faelle.csv – ein neuer Test ist einfach eine neue Zeile:

    richtung  eingabe          erwartet           notiz
    st-de     Mohlzeit         Guten Appetit! ... Tippfehler
    st-de     Hoit di Goschn!                     leer = es darf KEIN Treffer kommen

"erwartet" ist die Übersetzung (bei st-de der hochdeutsche Text, bei de-st der Dialekt).
Richtung "sprache": "eingabe" ist das, was Whisper erkannt hat, "erwartet" ist der
Dialekt-Eintrag, der gefunden werden soll (Suche in beiden Spalten).
Der Test besteht, wenn "erwartet" unter den besten Treffern ist.

Optionale Spalte "grenze": steht dort "ja", ist der Fall eine BEKANNTE GRENZE der
Methode. Der Test läuft trotzdem, wird aber als "xfail" (erwarteter Fehlschlag)
gezählt. Besteht er eines Tages, meldet pytest "XPASS" – dann kann "ja" weg.

Diese Tests brauchen die Datenbank: vorher `python3 scripts/import_csv.py` ausführen.
"""

import csv
from pathlib import Path

import pytest

from app.uebersetzer import STANDARD_DB, STEIRISCH_DEUTSCH, Uebersetzer, normalisieren

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
                marks=bekannte_grenze(zeile),
            )
            for zeile in csv.DictReader(datei)
        ]


def bekannte_grenze(zeile):
    """Markiert Fälle mit grenze=ja als erwarteten Fehlschlag."""
    if (zeile.get("grenze") or "").strip().lower() == "ja":
        return pytest.mark.xfail(reason=zeile.get("notiz") or "bekannte Grenze", strict=False)
    return ()


def ziel(treffer, richtung):
    """Die Übersetzung, also die 'andere Seite' des Treffers."""
    return treffer.hochdeutsch if richtung == STEIRISCH_DEUTSCH else treffer.dialekt


def suchen(uebersetzer, eingabe, richtung):
    if richtung == "sprache":
        return uebersetzer.sprache_suchen(eingabe, mit_derb=True)
    return uebersetzer.uebersetzen(eingabe, richtung)


@pytest.fixture(scope="module")
def uebersetzer():
    return Uebersetzer()


@pytest.mark.parametrize("richtung, eingabe, erwartet", faelle_laden())
def test_echter_fall(uebersetzer, richtung, eingabe, erwartet):
    treffer = suchen(uebersetzer, eingabe, richtung)
    gefunden = [f"{ziel(t, richtung)} ({t.art} {t.score})" for t in treffer]

    if not erwartet:
        assert treffer == [], f"Erwartet: kein Treffer. Bekommen: {gefunden}"
        return

    assert treffer, "Kein Treffer, erwartet war: " + erwartet

    # Mehrere Treffer können gleich gut sein (z. B. "tschüss" -> Servus, Baba ...)
    bester_score = treffer[0].score
    # Vergleich ohne Groß-/Kleinschreibung und Satzzeichen: "Ich" = "ich"
    beste = [normalisieren(ziel(t, richtung)) for t in treffer if t.score == bester_score]
    assert normalisieren(erwartet) in beste, f"Erwartet: {erwartet!r}. Bekommen: {gefunden}"