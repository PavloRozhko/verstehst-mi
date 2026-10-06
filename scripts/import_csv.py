"""Importiert die geprüften CSV-Dateien aus data/ in die SQLite-Datenbank.

Aufruf (im Projektordner):
    python3 scripts/import_csv.py

Regeln:
    status = richtig     -> Eintrag wird übernommen
    status = korrigiert  -> die Spalte "korrektur" ersetzt den Dialekt-Text
    status = falsch/offen -> Eintrag wird übersprungen
"""

import csv
import sqlite3
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
DATEN = PROJEKT / "data"
DB_DATEI = DATEN / "verstehst_mi.db"
SCHEMA = PROJEKT / "app" / "schema.sql"

# Welche CSV-Datei enthält welchen Eintragstyp
QUELLEN = {
    "phrasen.csv": "phrase",
    "woerter.csv": "wort",
}

PFLICHTSPALTEN = {"id", "dialekt", "hochdeutsch", "status", "korrektur"}


def bereinigen(text):
    """Entfernt Leerzeichen am Rand und vereinheitlicht Apostrophe."""
    if text is None:
        return ""
    text = text.strip()
    # ´ und ` werden oft statt ' getippt (z. B. "Haum´s")
    for zeichen in ("´", "`", "’", "‘"):
        text = text.replace(zeichen, "'")
    return text


def zeile_verarbeiten(zeile, typ, dateiname):
    """Wandelt eine CSV-Zeile in einen Datensatz um.

    Gibt (datensatz, None) zurück, oder (None, grund) wenn die Zeile übersprungen wird.
    """
    status = bereinigen(zeile["status"]).lower()
    dialekt = bereinigen(zeile["dialekt"])
    korrektur = bereinigen(zeile["korrektur"])
    hochdeutsch = bereinigen(zeile["hochdeutsch"])
    thema = bereinigen(zeile.get("thema"))

    if status == "korrigiert":
        if not korrektur:
            return None, "korrigiert, aber Spalte 'korrektur' ist leer"
        dialekt = korrektur
    elif status != "richtig":
        return None, f"status = {status or 'leer'}"

    if not dialekt or not hochdeutsch:
        return None, "Dialekt oder Hochdeutsch fehlt"

    datensatz = {
        "typ": typ,
        "dialekt": dialekt,
        "hochdeutsch": hochdeutsch,
        "thema": thema or None,
        "wortart": bereinigen(zeile.get("wortart")) or None,
        "derb": 1 if thema.lower() == "derb" else 0,
        "kommentar": bereinigen(zeile.get("kommentar")) or None,
        "geprueft_von": bereinigen(zeile.get("geprüft_von")) or None,
        "quelle": f"{dateiname}#{bereinigen(zeile['id'])}",
    }
    return datensatz, None


def datei_importieren(verbindung, pfad, typ):
    """Liest eine CSV-Datei und schreibt gültige Zeilen in die Datenbank."""
    importiert = 0
    uebersprungen = []

    # utf-8-sig entfernt ein eventuelles BOM, das Excel/Sheets manchmal schreibt
    with open(pfad, encoding="utf-8-sig", newline="") as datei:
        leser = csv.DictReader(datei)
        fehlend = PFLICHTSPALTEN - set(leser.fieldnames or [])
        if fehlend:
            raise ValueError(f"{pfad.name}: Spalten fehlen: {', '.join(sorted(fehlend))}")

        for zeile in leser:
            datensatz, grund = zeile_verarbeiten(zeile, typ, pfad.name)
            if datensatz is None:
                uebersprungen.append((zeile["id"], grund))
                continue
            try:
                verbindung.execute(
                    """INSERT INTO eintraege
                       (typ, dialekt, hochdeutsch, thema, wortart, derb,
                        kommentar, geprueft_von, quelle)
                       VALUES (:typ, :dialekt, :hochdeutsch, :thema, :wortart, :derb,
                               :kommentar, :geprueft_von, :quelle)""",
                    datensatz,
                )
                importiert += 1
            except sqlite3.IntegrityError:
                uebersprungen.append((zeile["id"], "Duplikat"))

    return importiert, uebersprungen


def main():
    DB_DATEI.unlink(missing_ok=True)  # Datenbank immer frisch aus den CSVs bauen
    verbindung = sqlite3.connect(DB_DATEI)
    verbindung.executescript(SCHEMA.read_text(encoding="utf-8"))

    for dateiname, typ in QUELLEN.items():
        pfad = DATEN / dateiname
        if not pfad.exists():
            print(f"– {dateiname}: nicht vorhanden, übersprungen")
            continue

        try:
            importiert, uebersprungen = datei_importieren(verbindung, pfad, typ)
        except ValueError as fehler:
            print(f"✗ FEHLER: {fehler}")
            verbindung.close()
            raise SystemExit(1)
        print(f"✓ {dateiname}: {importiert} importiert, {len(uebersprungen)} übersprungen")
        for zeilen_id, grund in uebersprungen:
            print(f"    Zeile id={zeilen_id}: {grund}")

    verbindung.commit()
    gesamt = verbindung.execute("SELECT COUNT(*) FROM eintraege").fetchone()[0]
    verbindung.close()
    print(f"\nDatenbank: {DB_DATEI.relative_to(PROJEKT)} ({gesamt} Einträge)")


if __name__ == "__main__":
    main()