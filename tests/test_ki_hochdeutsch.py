"""Tests für die KI-Übersetzung Dialekt -> Hochdeutsch (app/ki_hochdeutsch.py),
ohne echtes Sprachmodell. Braucht die echte Datenbank (scripts/import_csv.py).
"""

import pytest

from app import ki_hochdeutsch as ki
from app.uebersetzer import STANDARD_DB, STEIRISCH_DEUTSCH, Uebersetzer
from app.vorschlag import Wortpaar, woerter_suchen

pytestmark = pytest.mark.skipif(
    not STANDARD_DB.exists(),
    reason="Datenbank fehlt – zuerst scripts/import_csv.py ausführen",
)


@pytest.fixture(scope="module")
def uebersetzer():
    return Uebersetzer()


def test_findet_dialektwoerter(uebersetzer):
    paare = woerter_suchen(uebersetzer, "Heit is vü z'tuan.", STEIRISCH_DEUTSCH)
    assert {(p.dialekt, p.hochdeutsch) for p in paare} >= {("heit", "heute"), ("vü", "viel")}


def test_nicht_gefunden(uebersetzer):
    # "Blunzngraf" ist erfunden und steht sicher nie im Wörterbuch
    satz = "Heit vü Blunzngraf."
    paare = woerter_suchen(uebersetzer, satz, STEIRISCH_DEUTSCH)
    assert ki.nicht_gefunden(satz, paare) == ["blunzngraf"]


def test_phrase_im_woerterbuch_braucht_kein_llm(uebersetzer):
    def fragen(*_):
        raise AssertionError("LLM darf nicht gefragt werden")

    e = ki.uebersetzen(uebersetzer, "Heit is vü z'tuan.", fragen=fragen)
    assert e.woerterbuch_phrase == "Heute gibt es viel zu tun."


def test_versteckte_phrase_fragt_llm(uebersetzer):
    gefragt = []

    def fragen(satz, paare):
        gefragt.append(ki.frage_text(satz, paare))
        return "Heute gibt es viel zu tun.", 0.5

    e = ki.uebersetzen(uebersetzer, "Heit is vü z'tuan.", fragen=fragen, phrase_zuerst=False)
    assert "- heit = heute" in gefragt[0]
    assert e.text == "Heute gibt es viel zu tun."
    # heute und viel kommen in der Antwort vor (unabhängig davon, welche Wörter neu dazukommen)
    assert not {"heit", "vü"} & {p.suchwort for p in e.bedeutung_fehlt}


OWA = Wortpaar("owa", "owa", "herunter (auch: aber)")


def test_bedeutung_in_klammern_zaehlt():
    assert ki.bedeutung_fehlt("Das ist aber lecker!", [OWA]) == []


def test_bedeutung_fehlt_wird_gemeldet():
    assert ki.bedeutung_fehlt("Das ist oben lecker!", [OWA]) == [OWA]


def test_gebeugte_form_zaehlt():
    paar = Wortpaar("hom", "hom", "haben")
    assert ki.bedeutung_fehlt("Wir habt frei.", [paar]) == []


def test_ein_eintrag_pro_wort_reicht():
    paare = [Wortpaar("pfusch", "Pfusch", "die Schwarzarbeit; die schlampige Arbeit"),
             Wortpaar("pfusch", "pfuschn", "pfuschen; unsauber arbeiten")]
    assert ki.bedeutung_fehlt("Das ist schlampige Arbeit.", paare) == []


def test_ohne_llm_nimmt_erste_bedeutung():
    assert ki.ohne_llm("Des is owa guat", [OWA]) == "des is herunter guat"
