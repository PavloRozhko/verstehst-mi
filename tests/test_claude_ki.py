"""Tests für die KI-Übersetzung mit Claude (app/claude_ki.py), ohne echte API.

Ein Ersatz-Client merkt sich die Anfrage und gibt eine feste Antwort zurück.
"""

from types import SimpleNamespace

import pytest

from app import claude_ki
from app import ki_hochdeutsch as ki
from app.wortsuche import Wortpaar


class ErsatzClient:
    """Tut so wie anthropic.Anthropic(): with_options(...).beta.messages.create(...)."""

    def __init__(self, text="Ich habe Hunger.", stop_reason="end_turn", fehler=None):
        self.antwort = SimpleNamespace(
            stop_reason=stop_reason,
            content=[SimpleNamespace(type="thinking", thinking=""),
                     SimpleNamespace(type="text", text=text)],
        )
        self.fehler = fehler
        self.anfragen = []
        self.optionen = {}
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def with_options(self, **optionen):
        self.optionen = optionen
        return self

    def _create(self, **anfrage):
        if self.fehler:
            raise self.fehler
        self.anfragen.append(anfrage)
        return self.antwort


PAARE = [Wortpaar("hob", "habe (ich)", "hob")]


def test_gleicher_prompt_wie_gemma():
    client = ErsatzClient()
    text, sekunden = claude_ki.claude_fragen("I hob an Hunga.", PAARE, client=client)
    assert text == "Ich habe Hunger."
    assert sekunden >= 0
    anfrage = client.anfragen[0]
    assert anfrage["system"] == ki.SYSTEM
    assert anfrage["messages"] == [
        {"role": "user", "content": ki.frage_text("I hob an Hunga.", PAARE)}]
    assert anfrage["model"] == claude_ki.CLAUDE_MODELL
    assert client.optionen["timeout"] == ki.ANTWORT_TIMEOUT


def test_ablehnung_ist_ein_fehler():
    client = ErsatzClient(text="", stop_reason="refusal")
    with pytest.raises(claude_ki.KeineAntwort):
        claude_ki.claude_fragen("I hob an Hunga.", PAARE, client=client)


def test_ohne_schluessel_nicht_bereit(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    modell = claude_ki.ClaudeModell()
    assert modell.aufwaermen() is False
    assert modell.letzter_fehler == "ANTHROPIC_API_KEY fehlt"


def test_mit_schluessel_bereit(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    modell = claude_ki.ClaudeModell()
    modell.im_hintergrund_aufwaermen()
    assert modell.bereit and modell.letzter_fehler is None


def test_modell_fragt_claude():
    modell = claude_ki.ClaudeModell(client=ErsatzClient(text="Wir hatten viel Spaß."))
    assert modell.aufwaermen()
    text, _ = modell.fragen("Mia hom a Hetz ghobt.", PAARE)
    assert text == "Wir hatten viel Spaß."


def test_kein_internet_gibt_fehler_weiter():
    modell = claude_ki.ClaudeModell(client=ErsatzClient(fehler=OSError("kein Netz")))
    modell.aufwaermen()
    with pytest.raises(OSError):
        modell.fragen("I hob an Hunga.", PAARE)
