"""Automatische Tests für den Übersetzer-Kern.

Ausführen (im Projektordner, mit aktiviertem .venv):
    pytest
"""

import sqlite3
from pathlib import Path

import pytest

from app.uebersetzer import (
    DEUTSCH_STEIRISCH,
    STEIRISCH_DEUTSCH,
    Uebersetzer,
    normalisieren,
    varianten,
)

SCHEMA = Path(__file__).resolve().parent.parent / "app" / "schema.sql"

TESTDATEN = [
    # typ, dialekt, hochdeutsch, thema, derb
    ("phrase", "Griaß di, wia geht's da?", "Grüß dich, wie geht es dir?", "Begrüßung", 0),
    ("phrase", "Kaunst ma helfen?", "Kannst du mir helfen?", "Alltag", 0),
    ("phrase", "Brauchn S' a Sackerl?", "Brauchen Sie eine Tüte?", "Einkaufen", 0),
    ("phrase", "Hoit di Goschn!", "Halt den Mund! (derb)", "derb", 1),
    ("wort", "Sackerl", "die Tüte", "Einkaufen", 0),
    ("wort", "Erdäpfl", "die Kartoffeln", "Essen", 0),
    ("wort", "Jausn", "die Zwischenmahlzeit; die Brotzeit", "Essen", 0),
    ("wort", "Servus", "hallo; tschüss", "Begrüßung", 0),
    ("wort", "Baba", "tschüss", "Begrüßung", 0),
]


@pytest.fixture
def uebersetzer(tmp_path):
    """Baut eine kleine Test-Datenbank, unabhängig von den echten CSV-Daten."""
    db = tmp_path / "test.db"
    verbindung = sqlite3.connect(db)
    verbindung.executescript(SCHEMA.read_text(encoding="utf-8"))
    verbindung.executemany(
        "INSERT INTO eintraege (typ, dialekt, hochdeutsch, thema, derb, quelle) "
        "VALUES (?, ?, ?, ?, ?, 'test')",
        TESTDATEN,
    )
    verbindung.commit()
    verbindung.close()
    return Uebersetzer(db)


# --- Hilfsfunktionen ---------------------------------------------------------

def test_normalisieren_entfernt_satzzeichen_und_apostrophe():
    assert normalisieren("Griaß di, wia geht's da?") == "griass di wia gehts da"


def test_normalisieren_vereinheitlicht_apostroph_varianten():
    assert normalisieren("Haum´s") == normalisieren("Haum's") == "haums"


def test_normalisieren_entfernt_klammern():
    assert normalisieren("Halt den Mund! (derb)") == "halt den mund"


def test_varianten_trennt_bedeutungen_und_entfernt_artikel():
    assert varianten("die Zwischenmahlzeit; die Brotzeit", "wort") == ["zwischenmahlzeit", "brotzeit"]


# --- Steirisch -> Deutsch ------------------------------------------------------

def test_exakter_treffer_ohne_satzzeichen(uebersetzer):
    t = uebersetzer.uebersetzen("griass di wia gehts da", STEIRISCH_DEUTSCH)
    assert t[0].hochdeutsch == "Grüß dich, wie geht es dir?"
    assert t[0].art == "exakt"


def test_tippfehler_wird_toleriert(uebersetzer):
    t = uebersetzer.uebersetzen("kaunst ma helfn", STEIRISCH_DEUTSCH)
    assert t[0].dialekt == "Kaunst ma helfen?"
    assert t[0].art == "ähnlich"


def test_wort_findet_auch_phrase_als_beispiel(uebersetzer):
    t = uebersetzer.uebersetzen("Sackerl", STEIRISCH_DEUTSCH)
    assert t[0].dialekt == "Sackerl"
    assert any(x.art == "in Phrase" for x in t)


def test_unbekannter_text_liefert_nichts(uebersetzer):
    assert uebersetzer.uebersetzen("xyz blabla", STEIRISCH_DEUTSCH) == []


def test_leere_eingabe_liefert_nichts(uebersetzer):
    assert uebersetzer.uebersetzen("  ?! ", STEIRISCH_DEUTSCH) == []


def test_derbe_eintraege_standardmaessig_ausgeblendet(uebersetzer):
    assert uebersetzer.uebersetzen("Hoit di Goschn", STEIRISCH_DEUTSCH) == []
    assert uebersetzer.uebersetzen("Hoit di Goschn", STEIRISCH_DEUTSCH, mit_derb=True)


# --- Deutsch -> Steirisch ------------------------------------------------------

def test_artikel_wird_ignoriert(uebersetzer):
    t = uebersetzer.uebersetzen("Kartoffeln", DEUTSCH_STEIRISCH)
    assert t[0].dialekt == "Erdäpfl"


def test_zweite_bedeutung_wird_gefunden(uebersetzer):
    t = uebersetzer.uebersetzen("Brotzeit", DEUTSCH_STEIRISCH)
    assert t[0].dialekt == "Jausn"


def test_mehrere_dialektvarianten(uebersetzer):
    t = uebersetzer.uebersetzen("tschüss", DEUTSCH_STEIRISCH)
    assert {"Servus", "Baba"} <= {x.dialekt for x in t}


def test_teil_einer_phrase_wird_gefunden(uebersetzer):
    t = uebersetzer.uebersetzen("wie geht es dir", DEUTSCH_STEIRISCH)
    assert t[0].dialekt == "Griaß di, wia geht's da?"
    assert t[0].art == "in Phrase"


def test_unbekannte_richtung_wirft_fehler(uebersetzer):
    with pytest.raises(ValueError):
        uebersetzer.uebersetzen("Servus", "xx-yy")