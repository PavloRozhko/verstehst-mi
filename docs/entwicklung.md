# Entwicklung: vom leeren Repository zur Präsentation

Kurzfassung der Entwicklungsgeschichte (02.10.–15.10.2026). Quellen: Git-Verlauf und die
Übergabe-Notizen zwischen den Arbeitssitzungen. Uhrzeiten aus Git.

## Überblick

```
02.10  ▏ leeres Repository, Ordnerstruktur
05.10  ▏ README, Jetson-Setup
06.10  ███ Datenbank, Wörterbuchsuche, Tests, erste Webseite
07.10  ███ Sprache (Whisper), HTTPS, QR-Code, Autostart, erster LLM-Test
08.10  ██ Spike 1 (no-go), Spike 2 (Satz 1 no-go, Satz 2 go), experimente.md
09.10  ███ Verbformen, KI-Übersetzung auf dem Server und im Browser
10.10  ▏ keine Commits
11.10  ███ Sprachtest, Whisper-Filter, Satz 3 und DeepL, Refactoring
12.10  ▏ Daten (geprüft_von), README auf Deutsch
13.10  ▏ Schritt 5b (Ausspracheregeln, no-go), Satz 4 festgelegt
14.10  ██ Wort `mei`, Satz 4 (4/10), README mit 19 von 40
15.10  ▏ Präsentation
```

Das Projekt ist von unten nach oben gewachsen: erst Daten und Suche, dann die Webseite,
dann die Sprache und erst am Ende die KI.

## Tag für Tag

**06.10 – Wörterbuch und Suche.** Der wichtigste Tag. SQLite-Tabelle und `import_csv.py`
(die Datenbank wird bei jedem Start neu aus den CSV-Dateien gebaut), `uebersetzer.py` mit
fehlertoleranter Suche, danach Wörter, Regressionstests auf echten Daten (`faelle.csv`) und
die Suche „nach Klang“ (`lautschluessel`: Howora = Hawara). Fälle, die das Verfahren
grundsätzlich nicht lösen kann, sind als `xfail` markiert, statt Schwellen anzupassen. Am
Nachmittag die FastAPI-Webseite: ab jetzt ist das Wörterbuch am Handy benutzbar.

**07.10 – Sprache, Netz, Autostart.** Whisper-Messungen: `base` mit Prompt ist so gut wie
`small`, aber dreimal schneller (ca. 1,1 s). Spracheingabe im Browser, selbstsigniertes
HTTPS (ohne HTTPS gibt das Handy das Mikrofon nicht frei), QR-Code-Seite, systemd-Dienst.
Experiment 1: gemma3:4b und llama3.1:8b erklären Wörter; gemma3:4b gewählt, weil llama
neben Whisper fast den ganzen Speicher belegt. Sprachausgabe (Piper) gestrichen: Es gibt
keine steirische Stimme.

**08.10 – Zwei Spikes mit dem Sprachmodell.** Spike 1 (Hochdeutsch → Steirisch): **no-go**,
das Modell erfindet Dialektwörter (`zbus`, `zspät`). Spike 2 (Steirisch → Hochdeutsch):
Satz 1 5/10 (no-go, Lücken in den Daten), danach bessere Wortsuche (`d'`/`z'` abtrennen),
Satz 2 7/10, **go**.

**09.10 – Verbformen und KI in der App.** Erst der Testsatz für Experiment A, dann der Code:
`verbformen.py` führt Formen auf den Infinitiv zurück (`mochst` → `mochn`), 18/18, **go**.
Die KI kommt in den Server (`KiModell`, ein Auftrag nach dem anderen, 20 s Zeitlimit; bei
jedem Problem nur Wortbedeutungen) und in den Browser, gekennzeichnet als „ungeprüft“.

**11.10 – Prüfen, Filter, Refactoring.** Experiment S (Spracheingabe): 10/10 bei Phrasen aus
dem Whisper-Prompt, 8/13 bei anderen, 0/6 Sprache → KI; Tippen bleibt der Hauptweg.
Experiment F: Filter gegen erfundenen Text (Husten, Klatschen), 0 von 10 Geräuschen ergeben
Text, **go**. Satz 3 mit DeepL-Vergleich: 3/10, **no-go**, die KI bleibt Experiment.
Refactoring ohne Verhaltensänderung: `ollama_chat` nach `ollama.py`, die Wortsuche nach
`wortsuche.py`; jede Funktion bekam einen Kommentar.

**12.10 – Daten und README.** Spalte `geprüft_von` gefüllt („Kollege“, weil der Kollege
seinem Namen nicht zugestimmt hat). README auf Deutsch neu geschrieben.

**13.10 – Schritt 5b.** Sechs Ausspracheregeln rückwärts angewendet, zwei Läufe:
3 richtige von 75 unbekannten Wörtern, 0 falsche, **no-go** (siehe `experimente.md`).
Nebenbefund: `Mei` wurde als „ach Gott“ statt „meine“ erkannt. Satz 4 festgelegt.

**14.10 – Satz 4.** Eintrag `mei` ergänzt, dann ein Lauf: 4/10. Über alle vier Sätze
19 von 40 gut (48 %). README aktualisiert.

## Plan und Ergebnis

| Was | Plan | Tatsächlich |
|---|---|---|
| Spike mit LLM (RAG) | 08.10. | 08.10. |
| KI in der Oberfläche | 12.–13.10. | 09.10., drei Tage früher |
| Sprachtest | 10.–11.10. | 11.10. |
| Whisper-Filter | 14.10. | 11.10. |
| Satz 3 | 13.10. | 11.10. |
| Refactoring | nicht geplant | 11.10. |
| README auf Deutsch | 15.10. | 12.10. |
| Sprachausgabe (Piper) | Schritt 8 | gestrichen am 07.10. |
| Ausspracheregeln (Schritt 5b) | nur nach Prüfung durch eine Germanistin | 13.10. als Experiment, no-go |

Alle geplanten Funktionen waren am 12.10. fertig, drei Tage vor dem Einfrieren (15.10.).

## Anzahl der Tests

| Wann | Tests |
|---|---|
| 07.10., morgens | 107 passed, 3 xfailed |
| 07.10., abends | 130 passed, 3 xfailed |
| 11.10. | 231 passed, 3 xfailed |
| 14.10. | 236 passed, 3 xfailed |

Die drei `xfail` sind bekannte Grenzen des Buchstabenvergleichs (z. B. „Des is a Schas“
ähnelt „Des is a Pfusch“). Die Tests laufen nur von Hand (`python -m pytest`), es gibt
keine CI.

## Erst Kriterien, dann Ergebnis

Testsätze und Go-Kriterien wurden immer **vor** dem Lauf committet. Der Git-Verlauf zeigt das:

| Experiment | Testsatz / Protokoll | Ergebnis |
|---|---|---|
| Spike 2, Satz 3 | 09.10., 08:42 | 11.10., 15:44 |
| A: Verbformen | 09.10., 08:51 | 09.10., 09:10 |
| S: Spracheingabe | 11.10., 12:15 | 11.10., 13:05 |
| F: Whisper-Filter | 11.10., 13:42 | 11.10., 13:57 |
| Satz 3 mit DeepL | 11.10., 14:48 | 11.10., 15:44 |
| Satz 4 | 14.10., 08:15 | 14.10., 09:37 |

Bei Schritt 5b wurden die Kriterien außerhalb von Git mit sha256 festgehalten
(`docs/protokolle/5b/`). `test_testsaetze.py` und `test_verbformen_daten.py` schlagen fehl,
wenn jemand einen Testsatz nachträglich ändert.
