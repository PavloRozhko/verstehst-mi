"""Kern des Übersetzers: sucht Einträge im geprüften Wörterbuch.

Die Suche ist tolerant gegenüber Tippfehlern, Groß-/Kleinschreibung,
Satzzeichen und Schreibvarianten (z. B. "Kaunst ma helfn" findet
"Kaunst ma helfen?").

Schnelltest im Terminal:
    python3 -m app.uebersetzer st-de "kaunst ma helfn"
    python3 -m app.uebersetzer de-st "Kartoffeln"
"""

import re
import sqlite3
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

STANDARD_DB = Path(__file__).resolve().parent.parent / "data" / "verstehst_mi.db"

# Richtungen
STEIRISCH_DEUTSCH = "st-de"
DEUTSCH_STEIRISCH = "de-st"

# Ab welcher Ähnlichkeit (0..1) ein Eintrag als Treffer gilt
SCHWELLE = 0.75
# Sehr kurze Eingaben brauchen eine höhere Ähnlichkeit, sonst gibt es Zufallstreffer
SCHWELLE_KURZ = 0.85

ARTIKEL = ("der ", "die ", "das ", "ein ", "eine ")


@dataclass
class Treffer:
    dialekt: str
    hochdeutsch: str
    typ: str          # "wort" oder "phrase"
    thema: str | None
    derb: bool
    art: str          # "exakt", "ähnlich" oder "in Phrase"
    score: float      # 0..1, wie gut der Treffer passt


def normalisieren(text):
    """Vereinheitlicht Text für den Vergleich.

    "Griaß di, wia geht's da?"  ->  "griass di wia gehts da"
    """
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)       # Erklärungen in Klammern entfernen
    text = re.sub(r"['´`’‘]", "", text)          # Apostrophe weg: geht's = gehts
    text = text.replace("ß", "ss")
    text = re.sub(r"[^\w\s]", " ", text)          # restliche Satzzeichen weg
    return " ".join(text.split())                 # Mehrfach-Leerzeichen zusammenfassen


def varianten(text, typ):
    """Zerlegt ein Feld in einzelne vergleichbare Varianten.

    "die Zwischenmahlzeit; die Brotzeit" -> ["zwischenmahlzeit", "brotzeit"]
    """
    ergebnis = []
    for teil in re.split(r";| / ", text):
        teil = normalisieren(teil)
        if typ == "wort":
            for artikel in ARTIKEL:
                if teil.startswith(artikel):
                    teil = teil[len(artikel):]
                    break
        if teil:
            ergebnis.append(teil)
    return ergebnis


def aehnlichkeit(a, b):
    return SequenceMatcher(None, a, b).ratio()


def teil_score(suche, varianten_liste):
    """Prüft, ob die Suche als ganze Wörter in einer Variante vorkommt.

    "wie geht es dir" steckt in "gruss dich wie geht es dir".
    Je größer der Anteil der Phrase, desto höher der Score (0.5 .. 0.7).
    """
    beste = 0.0
    for v in varianten_liste:
        if f" {suche} " in f" {v} ":
            beste = max(beste, 0.5 + 0.2 * len(suche) / len(v))
    return round(beste, 2)


class Uebersetzer:
    def __init__(self, db_pfad=STANDARD_DB):
        """Lädt alle Einträge einmal in den Speicher (bei ein paar hundert Einträgen schnell)."""
        verbindung = sqlite3.connect(db_pfad)
        verbindung.row_factory = sqlite3.Row
        zeilen = verbindung.execute(
            "SELECT dialekt, hochdeutsch, typ, thema, derb FROM eintraege"
        ).fetchall()
        verbindung.close()

        self.eintraege = []
        for z in zeilen:
            self.eintraege.append({
                "zeile": z,
                STEIRISCH_DEUTSCH: varianten(z["dialekt"], z["typ"]),
                DEUTSCH_STEIRISCH: varianten(z["hochdeutsch"], z["typ"]),
            })

    def uebersetzen(self, text, richtung=STEIRISCH_DEUTSCH, mit_derb=False, limit=5):
        """Gibt eine nach Qualität sortierte Liste von Treffern zurück."""
        if richtung not in (STEIRISCH_DEUTSCH, DEUTSCH_STEIRISCH):
            raise ValueError(f"Unbekannte Richtung: {richtung}")

        suche = normalisieren(text)
        if not suche:
            return []

        schwelle = SCHWELLE_KURZ if len(suche) <= 4 else SCHWELLE
        treffer = []

        for eintrag in self.eintraege:
            z = eintrag["zeile"]
            if z["derb"] and not mit_derb:
                continue

            beste = max(aehnlichkeit(suche, v) for v in eintrag[richtung])
            if beste == 1.0:
                art = "exakt"
            elif beste >= schwelle:
                art = "ähnlich"
            elif z["typ"] == "phrase" and (teil := teil_score(suche, eintrag[richtung])):
                # Eingabe kommt als ganze Wörter in einer Phrase vor -> als Beispiel zeigen
                art, beste = "in Phrase", teil
            else:
                continue

            treffer.append(Treffer(
                dialekt=z["dialekt"],
                hochdeutsch=z["hochdeutsch"],
                typ=z["typ"],
                thema=z["thema"],
                derb=bool(z["derb"]),
                art=art,
                score=round(beste, 2),
            ))

        treffer.sort(key=lambda t: t.score, reverse=True)
        return treffer[:limit]


def main():
    if len(sys.argv) != 3:
        print('Aufruf: python3 -m app.uebersetzer st-de|de-st "Text"')
        raise SystemExit(1)

    richtung, text = sys.argv[1], sys.argv[2]
    ergebnisse = Uebersetzer().uebersetzen(text, richtung)
    if not ergebnisse:
        print("Kein Treffer im Wörterbuch.")
    for t in ergebnisse:
        quelle, ziel = (t.dialekt, t.hochdeutsch) if richtung == STEIRISCH_DEUTSCH else (t.hochdeutsch, t.dialekt)
        print(f"[{t.art:9}] {t.score:.2f}  {quelle}  →  {ziel}")


if __name__ == "__main__":
    main()