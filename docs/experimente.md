# Experimente mit dem lokalen Sprachmodell (LLM)

Stand: 08.10.2026 · Modell: `gemma3:4b` über Ollama auf dem Jetson Orin Nano Super (GPU),
gleichzeitig mit Whisper (CPU). Temperatur 0.

## Frage

Kann ein kleines, lokales Sprachmodell beim Übersetzen zwischen Steirisch und Hochdeutsch
helfen, **ohne Dialekt zu erfinden**? Grundlage ist immer das von Muttersprachlern geprüfte
Wörterbuch. Das Modell bekommt die passenden Einträge mitgeschickt
(RAG = *Retrieval-Augmented Generation*: erst nachschlagen, dann schreiben).

## Vorgehen

- Die **Go-Kriterien** wurden vor jedem Lauf festgelegt und danach nicht verändert.
- Testsätze wurden **vor** dem Lauf festgelegt (Git-Verlauf). Bewertet wurde von Hand:
  *gut / teils / falsch*.
- Den Prompt haben wir nicht an die Testsätze angepasst. Verbessert wurden nur Daten und
  Wortsuche, jeweils vor dem nächsten Lauf mit **neuen** Sätzen.

## Experiment 1 (07.10.): Wörterbuch-Einträge erklären

Das Modell erklärt Situation und Ton eines geprüften Eintrags (z. B. „freundlich“, „grob“).

| | gemma3:4b | llama3.1:8b |
|---|---|---|
| Zeit pro Erklärung | Median 3,1 s | Median 4,7–5,5 s |
| Bewertung (10 Einträge) | 4 gut / 4 teils / 2 falsch | 6 gut / 4 teils / 0 falsch |
| Speicher neben Whisper | ok | nur 330 MB frei, Swap |

**Ergebnis:** Die Schwäche liegt in den Daten (Situation und Ton fehlen im Wörterbuch), nicht
im Prompt. `llama3.1:8b` ist für die Vorführung zu knapp im Speicher.

## Spike 1: Hochdeutsch → Steirisch

Das Modell bekommt einen hochdeutschen Satz, der nicht im Wörterbuch steht, und die gefundenen
geprüften Wörter (`heute = heit`). Es soll nur diese Wörter als Dialekt verwenden.
Skript: `scripts/rag_test.py`, Logik: `app/vorschlag.py`.

**Kriterien:** ≤ 5 s · 0 erfundene Dialektwörter · ≥ 7/10 Sätze mit gefundenen Wörtern

| Kriterium | Ergebnis | |
|---|---|---|
| Zeit | 0,9 s (Median) | ✅ |
| Sätze mit gefundenen Wörtern | 9/10 – ohne LLM (Wort-für-Wort) ebenfalls 9/10 | ✅ |
| Erfundene Wörter | mindestens 5 + 1 Bedeutungsänderung | ❌ |

Beispiele: `zbus`, `zspät`, `kommet` (erfunden); `Schlüssel` → `schüssel` (Bedeutung
geändert); `koid` → `zoid` (geprüftes Wort verdorben).

**Entscheidung: no-go.** Ein 4B-Modell hält sich nicht an „nur diese Wörter“. Es bringt
gegenüber einfacher Wort-für-Wort-Ersetzung keinen Vorteil, aber neue Fehler.

## Spike 2: Steirisch → Hochdeutsch

Zielgruppe sind Menschen, die Deutsch lernen und in der Steiermark Dialekt hören.
Das Modell schreibt hier **nur Hochdeutsch**, der Dialekt kommt vom Benutzer.
Es bekommt die geprüften Bedeutungen der Wörter (`Hackn = die Arbeit`).
Skript: `scripts/rag_test_hochdeutsch.py`, Logik: `app/ki_hochdeutsch.py`.

Das Programm zeigt zusätzlich (ohne LLM):
- welche Wörter **nicht im Wörterbuch** stehen (dort muss das Modell raten),
- ⚠ wenn eine geprüfte Bedeutung in der Antwort nicht vorkommt (möglicher Widerspruch).

**Testsätze:** je 10 geprüfte Phrasen aus dem Wörterbuch, zufällig gezogen (feste Seeds).
Die Phrasen selbst werden für den Test „versteckt“. So gibt es eine richtige Antwort von
Muttersprachlern, ohne dass wir Dialekt erfinden.

**Kriterien:** ≤ 5 s · ≥ 7/10 *gut* · 0 Widersprüche zu geprüften Bedeutungen

### Satz 1

| Kriterium | Ergebnis | |
|---|---|---|
| Zeit | 0,9 s (Median) | ✅ |
| Bedeutung | 5 gut / 2 teils / 3 falsch → **5/10** | ❌ |
| Widersprüche | 1 („Der is ma zwida“ → „Wir sind unwillig“) | ❌ |

Gut: Das Modell wählt die passende Bedeutung (`owa` → „aber“ statt „herunter“, `a` → „ein“
statt „auch“). Schlecht: Zwei von drei Fehlern betreffen Wörter, die im Wörterbuch fehlten
(`Gschropp` wurde zu „Glocke“, `los … zua` blieb unverstanden).

**Entscheidung: vorerst no-go – die Ursache sind Datenlücken.**

### Zwischen Satz 1 und Satz 2

1. **Satz 2 festgelegt**, bevor neue Wörter gesammelt wurden (Commit `276670a`).
2. **Wörterbuch ergänzt:** Aus den Phrasen (ohne die Phrasen von Satz 2) wurden 116 Wörter
   gewonnen, die in der Wörter-Tabelle fehlten (z. B. `hob`, `is`, `ka`, `Wort` = warte).
   Muttersprachler haben sie geprüft: 113 richtig, 3 falsch (`voll`, `schifft`, `Gschropp`).
   Dazu kamen 2 neue Wörter. Die Wörter-Tabelle wuchs von 455 auf 570 Einträge.
3. **Wortsuche verbessert:** `d'`/`z'` am Wortanfang werden abgetrennt (`z'teia` → `teia`).
   Ausdrücke aus zwei Wörtern werden als ein Eintrag gefunden (`auf d'Nocht` = am Abend).

### Satz 2

| Kriterium | Ergebnis | |
|---|---|---|
| Zeit | 0,8 s (Median) | ✅ |
| Bedeutung | 7 gut / 1 teils / 2 falsch → **7/10** | ✅ |
| Widersprüche | 0 | ✅ |

Die beiden Fehler: eine Redewendung wörtlich übersetzt („Do hauts ma den Vogl aussi“ →
„Da hauts uns den Vogel hinaus“ statt „Das ist ja völlig irre“) und ein unbekanntes Verb
falsch geraten (`suderst` = jammerst). In **beiden** Fällen hat das Programm die
unbekannten Wörter angezeigt.

**Entscheidung: go – mit Kennzeichnung.** Die KI-Übersetzung wird als
„KI-Übersetzung (ungeprüft)“ angezeigt, zusammen mit den geprüften Wortbedeutungen und den
markierten unbekannten Wörtern.

## Einschränkungen

- Nur 2 × 10 Sätze: Die Ergebnisse (5/10 und 7/10) sind eine Tendenz, keine Messung.
- Die Testsätze stammen aus dem Wörterbuch. Ein Teil der Wörter wurde aus denselben Phrasen
  gewonnen, das Ergebnis ist also eher etwas zu gut.
- Das erste Laden des Modells dauert etwa 70 s. Für die Vorführung muss das Modell beim Start
  geladen und im Speicher gehalten werden.
- Redewendungen kann das Modell nicht übersetzen, wenn sie nicht als Phrase im Wörterbuch
  stehen.

## Erkenntnisse

1. **Daten schlagen Prompt.** Die größten Verbesserungen kamen aus dem Wörterbuch, nicht aus
   dem Prompt.
2. **Richtung ist entscheidend.** Ein kleines Modell kann gut Hochdeutsch schreiben, aber
   keinen steirischen Dialekt.
3. **Ehrlich anzeigen, wo geraten wird.** Fehler traten dort auf, wo das Programm unbekannte
   Wörter gemeldet hat. Diese Anzeige ist wichtiger als eine höhere Trefferquote.
4. **Menschen sind der Engpass.** Die Prüfung durch Muttersprachler ist der langsamste und
   wertvollste Teil des Projekts.

## Selbst nachvollziehen

```bash
python scripts/import_csv.py
python scripts/rag_test.py                          # Spike 1
python scripts/rag_test_hochdeutsch.py --satz 1     # Spike 2, Satz 1
python scripts/rag_test_hochdeutsch.py --satz 2     # Spike 2, Satz 2
# jeweils mit --ohne-ollama: nur Wortsuche, ohne Sprachmodell
```

Ergebnisse als CSV in `models/rag_test/` (nicht im Repository).
Hinweis: Die Läufe mit dem alten Wörterbuch (Spike 1, Spike 2 Satz 1) liefern mit dem
heutigen Wörterbuch andere Werte als oben.
