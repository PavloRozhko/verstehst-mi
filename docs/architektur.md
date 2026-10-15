# Architektur: Wer hängt von wem ab

Stand: 15.10.2026. „A → B“ heißt: A importiert oder ruft B. Wer eine Funktion ändert, sieht
hier, wer sie benutzt.

## Ebenen

Es gibt keine zyklischen Importe. Die unterste Ebene importiert nichts aus dem Projekt.

```
Ebene 4   main.py  (FastAPI-Server, alle /api/...-Adressen)
             │
Ebene 3   ki_hochdeutsch.py      vorschlag.py (Spike 1, von der App nicht benutzt)
             │                       │
Ebene 2   wortsuche.py  ◄────────────┘
             │
          verbformen.py
             │
Ebene 1   uebersetzer.py   ollama.py   sprache.py   netz.py   (lautregeln.py, Schritt 5b)
```

| Datei | importiert aus dem Projekt |
|---|---|
| `uebersetzer.py`, `ollama.py`, `sprache.py`, `netz.py` | nichts |
| `verbformen.py` | `uebersetzer` |
| `wortsuche.py` | `uebersetzer`, `verbformen` |
| `ki_hochdeutsch.py` | `uebersetzer`, `wortsuche`, `ollama` |
| `vorschlag.py` | `uebersetzer`, `wortsuche`, `ollama` |
| `lautregeln.py` | `uebersetzer` |
| `main.py` | `uebersetzer`, `sprache`, `netz`, `ki_hochdeutsch` |

`main.py` importiert weder `vorschlag.py` noch `lautregeln.py`. Beide sind Experimente
(no-go); nur `scripts/rag_test.py`, `scripts/regeln_test.py` und `tests/test_vorschlag.py`
brauchen sie.

Fremde Bibliotheken: `fastapi`, `uvicorn` (Server), `faster-whisper`, `av<19` (Sprache),
`segno` (QR-Code), `pytest`, `httpx` (Tests). `ollama.py` spricht Ollama über `urllib` an;
Ollama läuft als eigener Dienst auf `localhost:11434`.

## Weg einer Anfrage

### Wörterbuch: `/api/uebersetzen`

```
app.js: suchen() → GET /api/uebersetzen → main.uebersetzen()
  → Uebersetzer.uebersetzen()  (normalisieren, lautschluessel, beste_aehnlichkeit, teil_score)
  → main.fuer_anzeige()        teilt in „genau“, „Meintest du …?“ und Beispiele
→ app.js: anzeigen()
```

### Spracheingabe: `/api/sprache`

```
app.js: aufnahmeStarten() → senden() → POST /api/sprache → main.sprache()
  → Spracherkennung.erkennen()  (audio_lesen: 0,3–15 s; Whisper; verwerfen: Filter)
  → Uebersetzer.sprache_suchen()  sucht in beiden Spalten
  → main.fuer_anzeige()
→ app.js: erkannter Text ins Eingabefeld, dann anzeigen()
```

### KI-Übersetzung: `/api/ki_uebersetzung`

```
app.js: kiFragen() → GET /api/ki_uebersetzung → main.ki_uebersetzung()
  → ki_hochdeutsch.uebersetzen_fuer_app()
      → phrase_suchen()                 steht der ganze Satz im Wörterbuch?
      sonst, wenn die KI bereit ist:
      → uebersetzen()
          → wortsuche.woerter_suchen()   Wortpaare, einzelne Wörter, d'/z', Verbformen
          → nicht_gefunden()
          → KiModell.fragen() → frage_text(), ollama_chat()
          → bedeutung_fehlt()            hat die KI geprüfte Bedeutungen ignoriert?
      → hochdeutsch_abtrennen()          „der“, „so“ nicht als unbekannt markieren
      bei Fehler oder ohne KI: nur Wortbedeutungen
→ app.js: kiErgebnis() → satzMarkiert(), wortListe()
```

`uebersetzen()` bekommt die Funktion `fragen` als Parameter: Der Server gibt
`KiModell.fragen`, die Skripte `ollama_fragen` oder `ohne_llm`, die Tests eine Attrappe.
Deshalb laufen die Tests ohne Ollama.

### Start des Servers

```
uvicorn app.main:app
  → Uebersetzer() liest die Datenbank einmal in den Speicher
  → main.lebenszyklus()
      → KiModell.im_hintergrund_aufwaermen()   ca. 70 s, im Hintergrund
      → Spracherkennung.laden()                einige Sekunden
```

## Daten

```
Google Sheets (Wörter, Phrasen) ──Export von Hand──► data/woerter.csv, data/phrasen.csv
  ──scripts/import_csv.py (+ app/schema.sql)──► data/verstehst_mi.db (nicht in Git)
  ──Uebersetzer.__init__──► Suche im Speicher
```

Nicht in Git: `data/verstehst_mi.db`, `models/` (Whisper), `certs/*.pem`.

Auf dem Jetson startet `deploy/verstehst-mi.service` bei jedem Boot `jetson_clocks`,
`import_csv.py` (Datenbank immer frisch nach `git pull`) und uvicorn mit HTTPS.

## Praktische Hinweise

- Änderungen an `uebersetzer.py` betreffen alles: danach alle Tests laufen lassen
  (`python scripts/import_csv.py && python -m pytest`).
- `verbformen.py` und `wortsuche.py` betreffen nur die KI-Übersetzung, nicht die normale
  Wörterbuchsuche.
- `sprache.py` und `netz.py` hängen von nichts im Projekt ab.
- Ohne Ollama startet der Server trotzdem (nur Wortbedeutungen); ohne Whisper ist nur das
  Mikrofon aus.
- `normalisieren()` gibt es zweimal: in Python und in `app.js`. Wer die Regeln in einer
  ändert, muss die andere prüfen, sonst passt die Markierung im Browser nicht mehr zur Suche.
- Die letzte Zeile von `main.py` hängt `static/` an `/`. Sie muss am Ende stehen, sonst
  verdeckt sie die `/api/...`-Adressen.
- Nach einer Änderung an den CSV-Dateien reicht ein Neustart des Dienstes.
