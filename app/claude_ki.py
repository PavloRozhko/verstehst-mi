"""KI-Übersetzung mit Claude über die Anthropic API (statt gemma3 auf dem Jetson).

Gleicher Prompt und gleiche Liste geprüfter Wörter wie bei gemma3 (app/ki_hochdeutsch.py),
nur das Modell ist ein anderes. Claude läuft nicht auf dem Jetson, sondern bei Anthropic:
Ohne Internet gibt es keine KI-Übersetzung, nur die Wortbedeutungen.
Vorteil: gemma3 muss nicht im Speicher liegen (~3,5 GB frei, z. B. für ein größeres Whisper).

Einschalten (siehe docs/jetson-setup.md):
    VERSTEHST_MI_KI=claude
    ANTHROPIC_API_KEY=sk-ant-...

Unterschied zu gemma3: Claude kennt keine Temperatur 0. Die gleiche Frage kann also
leicht unterschiedliche Antworten geben.
"""

import os
import time

from app.ki_hochdeutsch import ANTWORT_TIMEOUT, SYSTEM, frage_text

CLAUDE_MODELL = "claude-opus-5-5"
# Kurze Sätze, kaum Nachdenken nötig: "low" ist am schnellsten und günstigsten
AUFWAND = "low"
# Die Antwort ist ein Satz; das Modell denkt aber vorher (bei Opus 5.5 immer an)
MAX_TOKENS = 2000


class KeineAntwort(Exception):
    """Claude hat abgelehnt oder keinen Text geliefert."""


def claude_chat(system, frage, client=None, modell=CLAUDE_MODELL, timeout=ANTWORT_TIMEOUT):
    """Schickt eine Frage an Claude und gibt (Antwort, Sekunden) zurück – wie ollama_chat.

    Fehler (kein Internet, falscher Schlüssel, Zeit abgelaufen) werden weitergegeben.
    Lehnt ein Modell ab, versucht die API von selbst ein anderes (fallbacks="default").
    """
    if client is None:
        import anthropic                      # erst hier: ohne Claude wird es nicht gebraucht
        client = anthropic.Anthropic()        # liest ANTHROPIC_API_KEY
    start = time.perf_counter()
    antwort = client.with_options(timeout=timeout, max_retries=1).beta.messages.create(
        model=modell,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": frage}],
        output_config={"effort": AUFWAND},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if antwort.stop_reason == "refusal":
        raise KeineAntwort("Claude hat die Antwort abgelehnt")
    text = "".join(b.text for b in antwort.content if b.type == "text").strip()
    if not text:
        raise KeineAntwort(f"keine Antwort (stop_reason={antwort.stop_reason})")
    return text, time.perf_counter() - start


def claude_fragen(satz, paare, client=None, modell=CLAUDE_MODELL):
    """Steirisch -> Hochdeutsch bei Claude erfragen (für Skripte). Gibt (Antwort, Sekunden)."""
    return claude_chat(SYSTEM, frage_text(satz, paare), client=client, modell=modell)


class ClaudeModell:
    """Gleiche Schnittstelle wie ki_hochdeutsch.KiModell, aber ohne Laden.

    "Bereit" heißt hier nur: ein API-Schlüssel ist gesetzt. Ob Internet da ist, zeigt
    erst die erste Frage; schlägt sie fehl, gibt es nur die Wortbedeutungen.
    """

    def __init__(self, client=None, modell=CLAUDE_MODELL):
        """client: nur für Tests (Ersatz für anthropic.Anthropic())."""
        self.client = client
        self.modell = modell
        self.bereit = False
        self.laedt = False
        self.letzter_fehler = None

    def aufwaermen(self):
        """Prüft nur, ob ein Schlüssel da ist (nichts zu laden). Gibt bereit zurück."""
        if self.client is None and not os.environ.get("ANTHROPIC_API_KEY"):
            self.bereit = False
            self.letzter_fehler = "ANTHROPIC_API_KEY fehlt"
        else:
            self.bereit = True
            self.letzter_fehler = None
        return self.bereit

    def im_hintergrund_aufwaermen(self):
        """Wie bei KiModell; hier geht es sofort, darum ohne eigenen Thread."""
        self.aufwaermen()

    def fragen(self, satz, paare):
        """Eine Frage an Claude (mit der Zeitgrenze der App)."""
        return claude_fragen(satz, paare, client=self.client, modell=self.modell)
