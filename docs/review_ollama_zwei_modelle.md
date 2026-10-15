# Review: Zwei Sprachmodelle über Ollama auf dem Jetson

Stand: 15.10.2026 · Gerät: NVIDIA Jetson Orin Nano Super, 8 GB RAM (CPU und GPU teilen sich diesen Speicher)

## Worum es geht

Über Ollama wurden auf dem Jetson zwei Modelle getestet: **gemma3:4b** und **llama3.1:8b**.
Beide liefen als Dienst auf `localhost:11434`, **gleichzeitig mit Whisper** (Spracherkennung, auf der CPU).
Test am 07.10.: Beide Modelle erklären Einträge aus dem Wörterbuch (`scripts/llm_test.py`).

## Ergebnis im Vergleich

| | gemma3:4b | llama3.1:8b |
|---|---|---|
| Größe auf der SSD (`ollama list`) | 3,3 GB | 4,9 GB |
| Schichten auf der GPU | 35 von 35 | 29 von 33 |
| Zeit pro Erklärung | Median 3,1 s | Median 4,7–5,5 s, max. 7,1 s |
| Bewertung (10 Einträge) | 4 gut / 4 teils / 2 falsch | 6 gut / 4 teils / 0 falsch |
| **Freier RAM neben Whisper** | **ca. 454 MB verfügbar, 666 MB Swap belegt** (Messung 15.10.) | **nur 330 MB frei, Swap wird benutzt** (07.10.) |

## Der Speicher war der entscheidende Punkt

- Mit **llama3.1:8b** blieben neben Whisper nur noch **330 MB RAM frei**. Das System musste auf
  Swap (Auslagerung auf die SSD) ausweichen. Das macht die Antworten langsamer und ist in einer
  Live-Vorführung ein Risiko: Ein weiterer Prozess kann den Speicher ganz füllen.
- 4 der 33 Schichten passten nicht auf die GPU und liefen auf der CPU, auch das ein Zeichen für
  knappen Speicher.
- **gemma3:4b** passte am 07.10. vollständig auf die GPU, der Speicher reichte damals neben Whisper.
- llama3.1:8b hat zwar besser erklärt (0 falsch statt 2), aber die Ursache der Fehler lag in den
  Daten (Situation und Ton fehlen im Wörterbuch), nicht im Modell.

**Entscheidung (07.10.):** gemma3:4b wird verwendet, llama3.1:8b ist „für die Vorführung zu knapp
im Speicher“ (`docs/experimente.md`).

## Wie gemma heute läuft

`ollama ps` am 14.10., während die App lief:

| Modell | Größe im Speicher | Verteilung | Kontext | Runner | geladen bis |
|---|---|---|---|---|---|
| gemma3:4b (ID c30276f7dffe) | 3,5 GB | 49 % CPU / 51 % GPU | 4096 | llamacpp | Forever |

- Die App hält das Modell dauerhaft im Speicher (`keep_alive=-1`). Das erste Laden dauert ca. 70 s,
  danach antwortet die KI in ca. 0,7 s pro Satz.
- Am 14.10. lief gemma nur etwa zur Hälfte auf der GPU, am 07.10. noch vollständig (35/35).
  Der Grund ist nicht geprüft. Vermutung: anderer Runner (llama.cpp) oder weniger freier
  Speicher beim Laden.

## Nebenbefund: zwei Kopien von gemma3:4b

`ollama list` zeigt gemma3:4b zweimal:

- **c30276f7dffe** (über llama.cpp, auch als `llamacpp:c30276…` gelistet): wird von der App benutzt.
- **aa1cd77181b3** (normales `ollama pull`): wird nicht benutzt, belegt ca. 3,2 GB auf der SSD.

Alle Modelle zusammen belegen 11 GB auf der SSD. Die zweite Kopie kostet nur SSD-Platz, **keinen
RAM**, weil Ollama nur das geladene Modell im Speicher hält. Sie kann nach der Präsentation
entfernt werden.

## Messung vom 15.10. (gemma3:4b + Whisper, App läuft)

```
$ free -h
               total        used        free      shared  buff/cache   available
Mem:           7.3Gi       6.9Gi       221Mi       1.9Mi       456Mi       454Mi
Swap:          8.0Gi       666Mi       7.3Gi

$ tegrastats
RAM 7021/7485MB  SWAP 683/8192MB (cached 168MB)  GR3D_FREQ 0%
```

| Wert | Bedeutung |
|---|---|
| 7,3 GiB gesamt | Von den 8 GB bleiben ca. 7,3 GiB für Linux, CPU und GPU zusammen. |
| 6,9 GiB belegt | Fast der ganze Speicher ist in Gebrauch. |
| **454 MiB verfügbar** | So viel kann ein neues Programm noch bekommen (Spalte `available`). |
| **666 MiB Swap** | Ein Teil liegt schon auf der SSD ausgelagert. |
| GPU 0 % | Im Moment der Messung wurde nichts gefragt (Leerlauf). |

**Wichtig:** Auch mit dem kleineren gemma3:4b ist der Speicher fast voll. Der Unterschied zu
llama3.1:8b (330 MB frei) ist kleiner als erwartet, nur ca. 120 MB. Die Messungen stammen aber
von verschiedenen Tagen und Situationen und sind nur grob vergleichbar. Vermutung (nicht geprüft):
Die App hält gemma dauerhaft im Speicher (3,5 GB laut `ollama ps`), dazu kommen Whisper,
der Webserver und das System.

Für die Vorführung heißt das: keine weiteren Programme auf dem Jetson starten (Browser,
zweites Modell, `ollama run` mit llama3.1:8b), sonst wird stärker ausgelagert und die KI
antwortet langsamer.

## Fazit

Bei 8 GB gemeinsamem Speicher entscheidet nicht die Qualität, sondern der freie RAM.
llama3.1:8b erklärt etwas besser, lässt neben Whisper aber nur 330 MB frei und braucht Swap.
gemma3:4b ist kleiner und schneller, aber auch damit bleiben nur ca. 454 MB verfügbar und
666 MB liegen im Swap. Für die Vorführung reicht das, eine Reserve gibt es kaum.

Quellen: `docs/experimente.md` (Repo), Übergabe vom 07.10. (Google Drive), `ollama list` und
`ollama ps` vom 14.10., `free -h` und `tegrastats` vom 15.10. (Projekt-Chat).
