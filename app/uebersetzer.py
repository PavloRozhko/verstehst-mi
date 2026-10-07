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
KURZ_BIS = 4        # Zeichen
# Bei kurzen Wörtern darf der Kandidat nur wenig länger/kürzer sein:
# "Haube" -> "Haubn" ja (Tippfehler), "Schas" -> "Schnapsn" nein (anderes Wort)
LAENGE_PRUEFEN_BIS = 6      # Zeichen
MAX_LAENGENUNTERSCHIED = 2  # Zeichen
# Lautschlüssel erst ab dieser Länge – bei kurzen Wörtern ist er zu ungenau
# (z. B. "schas" -> "scha" ≈ "scho")
LAUT_AB = 6         # Zeichen

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


def vergleichbar(suche, kandidat):
    """Kurze Eingaben nur mit ähnlich langen Kandidaten vergleichen."""
    if len(suche) > LAENGE_PRUEFEN_BIS:
        return True
    return abs(len(suche) - len(kandidat)) <= MAX_LAENGENUNTERSCHIED


def beste_aehnlichkeit(suche, kandidaten):
    werte = [aehnlichkeit(suche, k) for k in kandidaten if vergleichbar(suche, k)]
    return max(werte, default=0.0)


def lautschluessel(text):
    """Vereinfachte 'Aussprache' für Dialekt-Schreibvarianten.

    Im Dialekt schreibt jeder anders: Hawara/Howora, Marüln/Marilen.
    Ähnlich klingende Buchstaben werden gleichgesetzt, Doppelbuchstaben vereinfacht:
    "howora" -> "hawara", "marüln" -> "mariln"

    Leerzeichen werden entfernt: die Spracherkennung trennt Wörter oft anders
    ("Gemobossessen" statt "Gemma wos essn").
    """
    for alt, neu in (("ie", "i"), ("ü", "i"), ("y", "i"), ("ö", "e"), ("ä", "e"), ("o", "a")):
        text = text.replace(alt, neu)
    text = text.replace(" ", "")
    return re.sub(r"(.)\1", r"\1", text)


# Der Lautschlüssel ist grob (jedes o wird a). Er zählt daher nur bei sehr hoher
# Ähnlichkeit, sonst gibt es Zufallstreffer wie "Goschn" -> "Gatsch".
LAUT_SCHWELLE = 0.85
# Ein Treffer nur über den Lautschlüssel ist nie ganz exakt
LAUT_MAXIMUM = 0.95


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
            dialekt = varianten(z["dialekt"], z["typ"])
            self.eintraege.append({
                "zeile": z,
                STEIRISCH_DEUTSCH: dialekt,
                DEUTSCH_STEIRISCH: varianten(z["hochdeutsch"], z["typ"]),
                # Lautschlüssel nur für den Dialekt: dort sind Schreibvarianten das Problem
                "laut": [lautschluessel(v) for v in dialekt],
            })

    def uebersetzen(self, text, richtung=STEIRISCH_DEUTSCH, mit_derb=False, limit=5):
        """Gibt eine nach Qualität sortierte Liste von Treffern zurück."""
        if richtung not in (STEIRISCH_DEUTSCH, DEUTSCH_STEIRISCH):
            raise ValueError(f"Unbekannte Richtung: {richtung}")

        suche = normalisieren(text)
        if not suche:
            return []

        schwelle = SCHWELLE_KURZ if len(suche) <= KURZ_BIS else SCHWELLE
        suche_laut = lautschluessel(suche)
        treffer = []

        for eintrag in self.eintraege:
            z = eintrag["zeile"]
            if z["derb"] and not mit_derb:
                continue

            beste = beste_aehnlichkeit(suche, eintrag[richtung])
            if richtung == STEIRISCH_DEUTSCH and beste < 1.0 and len(suche) >= LAUT_AB:
                laut = beste_aehnlichkeit(suche_laut, eintrag["laut"])
                if laut >= LAUT_SCHWELLE:
                    beste = max(beste, min(laut, LAUT_MAXIMUM))
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

    def sprache_suchen(self, text, mit_derb=False, limit=5):
        """Suche für gesprochene Eingaben: in BEIDEN Spalten.

        Die Spracherkennung kennt keinen Dialekt und schreibt oft halb Hochdeutsch:
        "Waun is Feierobnd?" wird zu "Wann ist Feier umt?". Das passt besser zur
        hochdeutschen Spalte. Deshalb wird in beiden Richtungen gesucht und pro
        Eintrag der bessere Treffer behalten.
        """
        beste = {}
        for richtung in (STEIRISCH_DEUTSCH, DEUTSCH_STEIRISCH):
            for t in self.uebersetzen(text, richtung, mit_derb=mit_derb, limit=limit * 2):
                schluessel = (t.dialekt, t.hochdeutsch)
                if schluessel not in beste or t.score > beste[schluessel].score:
                    beste[schluessel] = t
        return sorted(beste.values(), key=lambda t: t.score, reverse=True)[:limit]


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