# verstehst-mi – Steirisch ↔ Hochdeutsch

Ein Lernprojekt auf dem **NVIDIA Jetson Orin Nano Super**: ein Übersetzer zwischen
steirischem Dialekt und Hochdeutsch, der **ohne Internet** läuft. Man öffnet ihn mit dem
Handy im WLAN, tippt oder spricht einen Satz und bekommt die Bedeutung.

**Für wen?** Für Menschen, die Deutsch lernen, in der Steiermark leben und im Alltag Dialekt
hören („Waun is Feierobnd?“, „I hob an Hunga.“).

**Grundidee:** Verlässlich ist nur, was Muttersprachler geprüft haben. Alles andere zeigt die
App ehrlich als *abgeleitet* oder *ungeprüft* an.

## Was die App kann

| Funktion | Wie verlässlich? |
|---|---|
| **Wörterbuch**: Wörter und Phrasen in beide Richtungen nachschlagen, tolerant bei Tippfehlern und anderer Schreibweise („Meintest du …?“) | ✅ von Muttersprachlern geprüft |
| **Konjugierte Verben** finden (`suachst` → `suachn` = suchen), nur Steirisch → Hochdeutsch | *abgeleitet* (Regel, kein Muttersprachler) |
| **Spracheingabe** (Whisper): Der erkannte Text landet im Eingabefeld und kann vor der Suche korrigiert werden | gut bei Phrasen aus dem Wörterbuch, schwächer bei fremden Sätzen |
| **KI-Übersetzung** ganzer Sätze, nur Steirisch → Hochdeutsch, nur auf Knopfdruck. Die KI bekommt die geprüften Wortbedeutungen mit; unbekannte Wörter werden markiert | 🤖 Experiment, *ungeprüft* (siehe Ergebnisse) |
| **Derbe Ausdrücke** nur, wenn der Schalter „derbe Ausdrücke anzeigen“ an ist | ✅ geprüft, gekennzeichnet |
| **QR-Code** (`/qr`), damit Handys im WLAN die Seite schnell öffnen | – |

### Was die App bewusst nicht kann

- **Keinen Dialekt erfinden.** Hochdeutsch → Steirisch kommt nur aus dem Wörterbuch. Ein
  Versuch mit KI hat erfundene Wörter geliefert (`zbus`, `zspät`) und wurde verworfen.
- **Keine Sprachausgabe.** Es gibt keine steirische Stimme für Piper.
- **Keine Redewendungen**, die nicht als Phrase im Wörterbuch stehen. „Des is ma Blunzn“
  wird von der KI wörtlich übersetzt („Blutwurst“), gemeint ist „Das ist mir egal“.

## Ergebnisse auf einen Blick

Alle Tests wurden **vor** dem Lauf festgelegt und danach nicht angepasst. Ausführlich:
[docs/experimente.md](docs/experimente.md).

| Experiment | Ergebnis | Entscheidung |
|---|---|---|
| KI: Hochdeutsch → Steirisch | erfundene Dialektwörter | **no-go** |
| KI: Steirisch → Hochdeutsch (4 × 10 neue Sätze) | 5/10, 7/10, 3/10, 4/10 gut → **19 von 40 (48 %)**, 0,7–1,0 s pro Satz | bleibt als **Experiment**, „ungeprüft“ |
| Vergleich mit DeepL (Satz 3, 10 Sätze) | verstehst-mi 3 gut, DeepL 4 gut | DeepL lässt Unbekanntes stehen; unsere KI schreibt flüssige, aber falsche Sätze |
| Konjugierte Verben (Regel ohne KI) | 18 von 18 regulären Formen, 0 falsche | **go** |
| Spracheingabe: Phrasen aus dem Whisper-Prompt | 10 von 10 | ok |
| Spracheingabe: andere Phrasen | 8 von 13 | Tippen ist der Hauptweg |
| Spracheingabe → KI | 0 von 6 gut | KI nur mit getipptem Text |
| Filter gegen erfundenen Text (Husten, Klatschen …) | 0 von 10 mit Text, höchstens 2,1 s (vorher bis 13 s) | **go** |

**Wichtigste Erkenntnis:** Bessere Daten haben mehr gebracht als ein besserer Prompt. Viele
Fehler passieren dort, wo ein Wort oder eine Redewendung im Wörterbuch fehlt – unbekannte
Wörter markiert die App deshalb.

## So funktioniert es

```
Handy (Browser, WLAN) ──HTTPS──> Jetson: FastAPI-Server (Port 8000)
                                   ├─ Wörterbuch: SQLite aus data/*.csv
                                   ├─ Whisper "base" (CPU): Sprache → Text
                                   └─ Ollama, gemma3:4b (GPU): KI-Übersetzung
```

1. Eingabe tippen oder sprechen (Whisper macht daraus Text).
2. Steht der Satz im Wörterbuch, kommt die **geprüfte** Übersetzung. Fertig.
3. Sonst zeigt die App die geprüften Bedeutungen der einzelnen Wörter und markiert unbekannte
   Wörter. Auf Knopfdruck schreibt die KI daraus einen hochdeutschen Satz („ungeprüft“).

## Daten

| Tabelle | Einträge in der App | Geprüft |
|---|---|---|
| Wörter (`data/woerter.csv`) | 570 | von Muttersprachlern |
| Phrasen (`data/phrasen.csv`) | 210 | von Muttersprachlern |

Übernommen werden nur Zeilen mit Status `richtig` oder `korrigiert`; `falsch` und `offen`
werden übersprungen. Die Spalte `geprüft_von` enthält „Kollege“: Namen werden auf Wunsch
nicht genannt. Herzlichen Dank für die Hilfe!

Mehrere Bedeutungen eines Wortes stehen mit Semikolon in einer Zelle
(`a` = ein/eine; auch). Die Tabellen werden in Google Sheets gepflegt und als CSV exportiert.

## Installation auf dem Jetson

Getestet mit Jetson Linux R39.2.1 und Python 3.12. Details zur Hardware und zum Autostart:
[docs/jetson-setup.md](docs/jetson-setup.md).

```bash
git clone https://github.com/PavloRozhko/verstehst-mi.git
cd verstehst-mi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/import_csv.py              # baut data/verstehst_mi.db aus den CSV-Dateien
```

Für die KI: [Ollama](https://ollama.com/download) installieren und das Modell laden
(ca. 3,3 GB):

```bash
ollama pull gemma3:4b
```

Whisper einmal herunterladen (Modell `base`, nach `models/whisper/`). Das geht mit dem
Benchmark-Skript und einer beliebigen kurzen Sprachaufnahme (WAV, MP3 oder M4A, z. B. vom Handy):

```bash
python scripts/whisper_benchmark.py aufnahme.m4a --modelle base
```

Beim ersten Lauf lädt das Skript das Modell aus dem Internet und misst danach die
Geschwindigkeit. Ohne Aufnahme geht es auch so:

```bash
python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8', download_root='models/whisper')"
```

Dieser Schritt ist nötig, weil der Dienst bewusst offline startet und nichts nachlädt.

Autostart mit HTTPS einrichten (erstellt auch das Zertifikat):

```bash
bash scripts/autostart_einrichten.sh
```

Danach: `https://<IP-des-Jetson>:8000`, QR-Code unter `https://<IP-des-Jetson>:8000/qr`.
Wichtig: **https**, nicht http. Am Jetson selbst geht auch `https://localhost:8000`.
Der Browser warnt beim ersten Besuch, weil das Zertifikat selbst signiert ist
(„Erweitert → Weiter zu …“). HTTPS ist nötig, weil Browser das Mikrofon sonst nicht erlauben.

**Hinweise:**

- **Andere IP-Adresse** (anderes WLAN): `bash scripts/zertifikat_erstellen.sh`, dann
  `sudo systemctl restart verstehst-mi`.
- **Ohne Internet:** Nach den Downloads oben läuft alles offline.
- **KI braucht etwa 70 s**, bis sie nach dem Start bereit ist. Die Fußzeile der Seite zeigt,
  ob Spracheingabe und KI bereit sind. Bis dahin funktioniert das Wörterbuch normal.

## Installation auf einem neuen Rechner (ohne Jetson)

Geht auf jedem Linux-Rechner, auch unter Windows mit WSL2. Kurz getestet mit Python 3.13
(Linux). Ohne NVIDIA-Grafikkarte ist die KI langsamer.

```bash
git clone https://github.com/PavloRozhko/verstehst-mi.git
cd verstehst-mi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/import_csv.py
python -m pytest                           # sollte grün sein
```

Optional für die KI: [Ollama](https://ollama.com/download) installieren und
`ollama pull gemma3:4b` ausführen.

Server starten (nur auf diesem Rechner, ohne Zertifikat):

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Dann im Browser **auf demselben Rechner** `http://localhost:8000` öffnen. `localhost` heißt
immer „dieser Rechner“: Vom Laptop aus erreicht man so nicht den Jetson. Auf `localhost`
erlauben Browser das Mikrofon auch ohne HTTPS. Für Handys im WLAN braucht es HTTPS, siehe oben.

Teile abschalten, die fehlen oder zu langsam sind:

```bash
VERSTEHST_MI_OHNE_KI=1 uvicorn app.main:app --host 127.0.0.1 --port 8000        # ohne Ollama
VERSTEHST_MI_OHNE_SPRACHE=1 uvicorn app.main:app --host 127.0.0.1 --port 8000   # ohne Whisper
```

Fehlt Ollama oder Whisper, läuft der Server trotzdem – nur ohne diesen Teil.

## Tests

```bash
python -m pytest
```

Stand 12.10.2026: 231 bestanden, 3 als bekannte Grenze markiert (`xfail`). Die Tests brauchen
weder Whisper noch Ollama.

## Projektstruktur

```
app/
  main.py            Web-Server (FastAPI): Seiten und API
  uebersetzer.py     Suche im Wörterbuch (tolerant gegenüber Tippfehlern)
  wortsuche.py       Wörter eines Satzes einzeln nachschlagen (für die KI)
  verbformen.py      konjugierte Verben → Infinitiv (abgeleitet)
  ki_hochdeutsch.py  KI-Übersetzung Steirisch → Hochdeutsch (Experiment)
  ollama.py          Verbindung zum lokalen Sprachmodell
  sprache.py         Spracherkennung mit Whisper + Filter gegen erfundenen Text
  netz.py            Adresse im WLAN und QR-Code
  vorschlag.py       KI Hochdeutsch → Steirisch (no-go, nicht in der App)
  static/            Weboberfläche (HTML, CSS, JavaScript)
data/                Wörterbuch als CSV, Whisper-Prompt
deploy/              systemd-Dienst für den Autostart
docs/                Experimente, Testprotokolle, Jetson-Setup, Modell-Review
scripts/             Import, Experimente, Zertifikat, Autostart
tests/               automatische Tests
```

## Einschränkungen

- **Kleiner Wortschatz:** 570 Wörter und 210 Phrasen. Was fehlt, muss die KI raten.
- **Die KI-Zahlen sind eine Tendenz, keine genaue Messung:** nur 4 × 10 Sätze, die Ergebnisse
  schwanken stark (5/10, 7/10, 3/10, 4/10).
- **Die KI klingt sicher, auch wenn sie falsch liegt.** Deshalb heißt sie „ungeprüft“ und zeigt
  die geprüften Wortbedeutungen daneben.
- **Spracheingabe:** getestet mit einem Sprecher, der kein Muttersprachler ist. Bei Sätzen
  außerhalb des Whisper-Prompts verhört sich Whisper oft. Leise Sprache wird schlechter erkannt.
- **Wörter mit zwei Bedeutungen** (`es` = ihr oder es, `a` = ein oder auch): Das Wörterbuch
  kennt beide, den Zusammenhang sieht nur die KI.
- **Redewendungen** fehlen im Wörterbuch.
- **Regionale Unterschiede** in der Steiermark sind kaum abgebildet.

## Lizenz

Code: [MIT](LICENSE).
