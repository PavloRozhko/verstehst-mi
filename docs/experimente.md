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

### Satz 3 (Abschlussmessung, festgelegt am 09.10.)

10 neue Phrasen (Seed 20261009, ohne Satz 1 und 2). Zusätzlich werden die Wörter versteckt,
die am 08.10. aus diesen Phrasen gewonnen wurden – sonst wäre Satz 3 leichter als Satz 2.
Gleiche Go-Kriterien. **Nur ein Lauf, am 13.10.**, nach den Verbformen (A) und dem Backend.

**Vorgezogen auf den 11.10.** (festgelegt vor dem Lauf): Die Voraussetzungen (A, Backend)
sind erfüllt. Seit dem Festlegen wurde nur an Spracheingabe und Oberfläche gearbeitet, nicht
an der KI-Kette. Die Phrasen von Satz 3 hat vor dem Lauf niemand angesehen. Es bleibt bei
**einem** Lauf.

**Vergleich mit DeepL (festgelegt vor dem Lauf):** Dieselben 10 Phrasen werden von Hand in
DeepL (kostenlose Web-Version) eingegeben, Ausgangssprache „Deutsch“ eingestellt (Steirisch
gibt es dort nicht). Notiert wird auch, welche Sprache DeepL von selbst erkennt. Bewertung
gleich wie oben (*gut / teils / falsch*), durch dieselbe Person. Kein Go-Kriterium – nur
Vergleich. Einschränkung: DeepL hat unser geprüftes Wörterbuch nicht; der Vergleich zeigt
also den Wert der geprüften Daten, nicht welches Modell „besser“ ist.
Nachtrag vor der Eingabe in DeepL: „Deutsch → Deutsch“ bietet DeepL nicht an. Darum
Ausgangssprache Deutsch, **Zielsprache Englisch**; bewertet wurde der Sinn der englischen
Übersetzung.

**Ergebnis (11.10.):** Zwei Personen haben unabhängig bewertet (Pavlo; Claude – dessen
Bewertung wurde vorher mit sha256 festgehalten). Übereinstimmung: 8 von 10, bei *gut* 10 von 10.

| Nr | Dialekt | KI-Übersetzung | Pavlo | Claude | DeepL (→ Englisch) | DeepL |
|---|---|---|---|---|---|---|
| 1 | Des is ma Blunzn. | Das ist eine Blutwurst. | falsch | falsch | That's a real head-scratcher. | falsch |
| 2 | Es kummt a Gwitta. | Ein Gewitter kommt. | gut | gut | A storm is coming. | gut |
| 3 | Is des koid heit! | Es ist heute kalt! | gut | gut | It's cold today! | gut |
| 4 | Moagn is a a Tog. | Morgen ist ein Tag. | teils | teils | Moagn is a Tog. (als Bretonisch erkannt) | falsch |
| 5 | Deis passt so, danke. | Das passt, danke. | teils | teils | That works fine, thanks. | teils |
| 6 | I kenn mi ned aus. | Ich kenne mich nicht aus. | gut | gut | I don't know much about it. | gut |
| 7 | Pass auf, es is glott! | Pass auf, es passt! | falsch | falsch | Watch out, it's hot! (Alternative: slippery) | teils |
| 8 | A Bier geht scho no. | Auch ein Bier geht noch. | falsch | teils | One more beer is fine. | gut |
| 9 | Gib ma des amoi. | Nimm dieses Mal. | falsch | falsch | Give me that, will you? (+ 3 Alternativen) | teils |
| 10 | A Brettljausn und a Gspritzta, bitte. | Auch eine kalte Platte … und eine Weinschorle, bitte. | falsch | teils | A Brettljausn and a Gspritzta, please. | falsch |

| Kriterium | Ergebnis | |
|---|---|---|
| Zeit | 0,7 s (Median), höchstens 1,3 s | ✅ |
| Bedeutung | **3 gut** (beide Bewerter) / 2–4 teils / 3–5 falsch → **3/10** | ❌ |
| Widersprüche | Pavlo: 4 (Nr. 1, 7, 8, 9) · Claude: 1 fraglich (Nr. 9) | ❌ |

**Vergleich mit DeepL:** verstehst-mi 3 gut (Pavlo: 3 / 2 / 5) – DeepL 4 gut / 3 teils /
3 falsch. Auf diesem Satz war DeepL also etwas besser. Die Fehler sind verschieden: DeepL lässt
Unbekanntes oft **unübersetzt** stehen (`Brettljausn`, `Moagn is a Tog`) – man sieht, dass es
nicht verstanden hat. Unser Modell schreibt **flüssige, aber falsche** Sätze.

**Ursachen (aus den Daten):**

- `a = auch (auch: ein/eine)`: dreimal wurde „auch“ gewählt (Nr. 4, 8, 10). Im Eintrag steht
  „auch“ einmal als Bedeutung und einmal als Hinweis – für ein kleines Modell verwirrend.
- Redewendung (Nr. 1): `Blunzn` wörtlich übersetzt; Redewendungen fehlen im Wörterbuch.
- Verstecktes Wort (Nr. 7, `glott`): als unbekannt angezeigt, vom Modell falsch geraten.

**Wichtig für die Einordnung:** Alle 10 Phrasen stehen im Wörterbuch. In der App bekommt man
für sie die **geprüfte** Übersetzung; der KI-Knopf erscheint dort gar nicht. Die KI wird nur
für Sätze benutzt, die nicht im Wörterbuch stehen. Über alle drei Sätze: 5 + 7 + 3 =
**15 von 30 gut (50 %)**.

**Entscheidung: no-go für „KI als verlässliche Übersetzung“.** Die KI bleibt als
**Experiment** in der App: nur auf Knopfdruck, als „ungeprüft“ gekennzeichnet, mit geprüften
Wortbedeutungen und markierten unbekannten Wörtern. In der Vorführung werden diese Zahlen
offen gezeigt.

**Datenkorrektur danach (11.10., Wirkung nicht gemessen):** Einträge, in denen „auch“ als
Hinweis stand, einheitlich mit Semikolon geschrieben – Bedeutungen unverändert:
`a` = ein/eine; auch · `owa` = herunter; aber · `Fetzn` = der Lappen; der Rausch ·
`sauba` = sauber; toll. Einen neuen, unbenutzten Testsatz gibt es nicht mehr; Satz 3 noch
einmal laufen zu lassen wäre Anpassen an den Test. Die Wirkung bleibt daher offen.

## Experiment A: Verbformen (Testsatz festgelegt am 09.10.)

**Problem:** Im Wörterbuch steht meist nur der Infinitiv (`suachn` = suchen). Im Satz kommt
das Verb gebeugt vor (`suachst`, `gsuacht`) und wird nicht gefunden.

**Idee (ohne LLM):** Steht ein Wort nicht im Wörterbuch, typische Endungen abtrennen
(`-st`, `-t`, `-ts`, `g-…-t`, `g-…-n`, nackter Stamm) und einen geprüften Infinitiv suchen.
Nur regelmäßige Verben. Ergebnis wird als **„abgeleitet“** angezeigt, nicht als „geprüft“.

**Testsatz (ohne neue Prüfung durch Muttersprachler):** `tests/verbformen.csv` – alle
41 geprüften gebeugten Formen, deren Infinitiv im Wörterbuch steht. Im Test wird die Form
versteckt; die Regel muss den Infinitiv finden. Die Einteilung wurde von Hand gemacht,
**bevor** die Regel geschrieben wurde:

| Kategorie | Anzahl | Bedeutung |
|---|---|---|
| regulär | 18 | Stamm bleibt gleich (`mochst` → `mochn`, `heat` → `hean`) |
| Klitikon | 3 | angehängtes `'s` / `'n` (`gfreit's`) – nur beobachtet, nicht bewertet |
| unregelmäßig | 20 | Stamm ändert sich (`host` → `hom`, `muass` → `miassn`, `foahrst` → `foahn`) |

**Go-Kriterien (vor dem ersten Lauf festgelegt):**

- mindestens 80 % der regulären Formen → richtiger Infinitiv (≥ 15 von 18)
- 0 falsche Infinitive im ganzen Testsatz (bei unregelmäßigen ist „nichts gefunden“ richtig)
- höchstens 3 falsche Treffer bei den übrigen Wörtern der Phrasen (jeder wird angezeigt
  und von Hand bewertet); die Phrasen von Satz 3 sind ausgenommen
- alle bisherigen Tests grün, keine spürbare Verlangsamung

**Ergebnis (09.10., `scripts/verbformen_test.py`):**

| Kriterium | Ergebnis | |
|---|---|---|
| reguläre Formen | **18/18** | ✅ |
| falsche Infinitive | **0** (alle 20 unregelmäßigen: nichts gefunden) | ✅ |
| Klitikon (nur beobachtet) | 2/3 (`gfreit's`, `gfriat's`; nicht `schaust'n`) | – |
| Treffer in Phrasen | 4, alle richtig: `red` → redn, `schau` → schaun, `kenn` → kenna, `suderst` → sudern | ✅ |
| Tests / Zeit | alle grün; 173 → 180 ms pro Satz (Wortsuche) | ✅ |

`suderst` war einer der zwei Fehler von Satz 2. Satz 2 ist aber schon verbraucht – ob die
Regel der KI-Übersetzung wirklich hilft, zeigt erst Satz 3.

**Entscheidung: go.** Die Regel läuft nur, wenn ein Wort sonst nicht gefunden wird, und nur
in der Richtung Steirisch → Hochdeutsch. Gefundene Infinitive heißen „abgeleitet“.

## Experiment S: Spracheingabe (Protokoll festgelegt am 11.10.)

**Frage:** Wie zuverlässig ist die Spracheingabe (Whisper `base`, CPU) für die Vorführung?
Und was muss am 14.10. verbessert werden?

**Testsatz:** `docs/sprachtest_protokoll.csv`, 45 Aufnahmen, festgelegt **vor** dem ersten
Sprechen:

| Block | Anzahl | Inhalt |
|---|---|---|
| A ruhig | 23 | Phrasen aus dem Wörterbuch, 10 davon auch im Whisper-Prompt |
| B Hintergrund | 6 | wie A, mit Fernseher/Musik |
| C leise | 3 | wie A, leise, ca. 1 m Abstand |
| D ohne Sprache | 3 | Stille, nur Geräusch, Husten |
| E KI-Knopf | 6 | Sätze **nicht** im Wörterbuch, nur aus geprüften Wörtern gebaut (Satz selbst ungeprüft); erwartete Bedeutung vorher eingetragen |
| F Flur | 4 | zwei Sätze, die im Flur falsch erkannt wurden, je normal und leise |

**Ablauf:** Jede Zeile einmal sprechen, in der Reihenfolge, ohne Wiederholung. Erkannter
Text und Sekunden kommen aus dem Log (`journalctl -u verstehst-mi`), das Ergebnis von der
Seite. Sprecher ist kein Muttersprachler – das Ergebnis gilt für diese Aussprache.

**Ziele (vor dem Lauf festgelegt):**

- A, im Prompt: mindestens 8 von 10 *richtig* oder *vorschlag*
- A, nicht im Prompt: nur gemessen (Grundlage für die Entscheidungen unten)
- D: 0 Übersetzungen (kein erfundener Text)
- E: KI mindestens 4 von 6 *gut*, keine *falsch*
- Zeit Spracherkennung: Median höchstens 3 s

**Entscheidungen für den 14.10. (vorher festgelegt):**

- D liefert Text → Filter für unsichere Ergebnisse bauen (`no_speech_prob`, Wiederholungen).
- Ein geprüftes Wort wird in A/B/C/F mindestens zweimal falsch erkannt → ins Whisper-Prompt.
  Danach gilt dieser Test nicht mehr als Messung; eine neue Messung bräuchte neue Sätze.
- Leise (C, F) deutlich schlechter als normal → Hinweis „nah ans Mikrofon“ für die Vorführung.
- Ziele für A oder D verfehlt → in der Vorführung Tippen als Hauptweg, Sprache als Zusatz.

**Ergebnis (11.10., zu Hause, Handy im WLAN):**

| Kriterium | Ergebnis | |
|---|---|---|
| A, im Prompt | **10/10** richtig oder vorschlag | ✅ |
| A, nicht im Prompt | 8/13 richtig oder vorschlag, 4 keiner, 1 falsch | – |
| B Hintergrund / C leise | 5/6 / 2/3 | – |
| D ohne Sprache | Stille und Geräusch: nichts; **Husten: zweimal erfundener Text** („Der Schalz, der Schalz, …“), je ca. 13 s | ❌ |
| E KI-Knopf | **0 gut**, 2 teils, 4 falsch | ❌ |
| Zeit | Median **1,5 s** (ohne die zwei Ausreißer von 13 s) | ✅ |

Einzelwerte: `docs/sprachtest_protokoll.csv`.

**Beobachtungen:**

- **E scheitert an der Spracherkennung, nicht am Modell.** In allen 6 Sätzen kam schon falscher
  Text beim Modell an (`Das Bette ist heizlich`, `Herst, gumm ham`). Das Modell „repariert“ ihn
  zu einem flüssigen, aber falschen Satz („Die Polizei hat das Fahrrad vergessen“,
  „Herzlich willkommen“). Sprache → KI vervielfacht Fehler, und das Ergebnis klingt überzeugend.
  Gegenbeispiel außerhalb von E (Nr. 12): `Ich fuwa mi am Radl` → richtig „Ich fahre mit dem Fahrrad“.
- **Erfundener Text blockiert den Jetson** (13 s statt 1,5 s); andere Handys müssen warten.
- **Leise ist schwächer:** Flur-Sätze leise 0/2 (`Da Krampus kummt!` leise → nichts erkannt).
- **Mindestens zweimal falsch erkannt** (geprüfte Wörter): `wia` (3×), `I` (4× → „Ich“),
  `Hawara`, `beinand`, `Geh` (je 2×).
- Sprecher ist kein Muttersprachler; die Sätze in E sind selbst gebaut und ungeprüft.

**Entscheidungen:**

- Nach der festgelegten Regel (D verfehlt): **in der Vorführung Tippen als Hauptweg,
  Sprache als Zusatz** – Sprache vor allem für Phrasen aus dem Wörterbuch.
- Für E gab es vorher keine Regel. Am 11.10. entschieden: Die KI wird in der Vorführung mit
  **getipptem** Text gezeigt. Der erkannte Text kommt künftig ins Eingabefeld, damit man ihn
  vor Suche und KI korrigieren kann.
- 14.10.: Filter für erfundenen Text (Wiederholungen, `no_speech_prob`), Wörter oben ins
  Whisper-Prompt. Danach ist dieser Test keine Messung mehr.
- **Umgesetzt am 11.10.:** Filter siehe Experiment F. Prompt (`data/whisper_prompt.txt`) um
  geprüfte Phrasen mit `wia`, `Geh`, `Hawara`, `beinand` ergänzt. `I` → „Ich“ lässt sich so
  nicht beheben (`I` stand schon im Prompt); die Suche findet die Phrasen trotzdem.
  Der Prompt hat jetzt 198 Tokens – faster-whisper nimmt höchstens 223, der Rest würde still
  abgeschnitten. Wirkung nicht gemessen (keine neuen Testsätze).

## Experiment F: Filter gegen erfundenen Text (festgelegt am 11.10.)

**Problem (aus Experiment S):** Bei Husten erfindet Whisper Text („Ja, ja, ja, …“) und
rechnet dabei 13 s – so lange warten alle anderen Handys.

**Änderung (`app/sprache.py`, vorgezogen vom 14.10.):**

- Whisper erzeugt höchstens 48 Tokens pro Aufnahme → eine Schleife bricht früh ab.
- Text wird verworfen („Nix verstanden“), wenn: die Token-Grenze erreicht ist, der Text
  zu gleichförmig ist (Kompression > 2,4, Whisper-Standard), ein Wort mindestens 4-mal
  vorkommt und die Hälfte des Textes ausmacht, oder ein typischer erfundener Untertitel-Satz
  kommt („Untertitel …“, „Vielen Dank fürs Zuschauen“).
- `no_speech_prob` wird nur protokolliert, nicht gefiltert: Ohne Daten wäre jede Grenze
  geraten und könnte leise Sprache wegfiltern.
- Unit-Tests: Alle 39 Texte, die Whisper am 11.10. bei echter Sprache erkannt hat (auch die
  falsch gehörten), bleiben erhalten; beide Schleifen werden verworfen.

**Testsatz:** `docs/filtertest_protokoll.csv`, 20 neue Aufnahmen auf dem Jetson:
10 Geräusche (Husten, Räuspern, Klatschen, Klopfen, Stille) und zur Kontrolle die 10
Phrasen aus Block A, die im Prompt stehen.

**Go-Kriterien (vor dem Lauf festgelegt):**

- Geräusche: 0 von 10 zeigen Text an, jede Antwort höchstens 3 s
- Kontrolle: der Filter verwirft 0 von 10, mindestens 9 von 10 *richtig* oder *vorschlag*
- alle Tests grün

**Bei no-go:** Filter verwirft echte Sprache → Regel lockern, die Version ohne Filter bleibt
in Git. Geräusche erzeugen weiter Text → in der Vorführung bleibt Tippen der Hauptweg (gilt
ohnehin, siehe Experiment S).

**Ergebnis (11.10., Jetson, Handy im WLAN):**

| Kriterium | Ergebnis | |
|---|---|---|
| Geräusche: 0 von 10 mit Text | **0 von 10** | ✅ |
| Geräusche: jede Antwort ≤ 3 s | höchstens **2,1 s** (vorher 13 s) | ✅ |
| Kontrolle: nichts verworfen | **0 von 10** verworfen | ✅ |
| Kontrolle: ≥ 9 von 10 richtig/vorschlag | **10 von 10** (6 richtig, 4 vorschlag), je 1,1–1,2 s | ✅ |
| Tests | 230 passed, 3 xfailed | ✅ |

Einzelwerte: `docs/filtertest_protokoll.csv`.

**Beobachtungen:**

- Der Filter war nötig: In 3 von 10 Geräuschen hat Whisper wieder Text erfunden
  („Puh! Puh! …“, „Schau, schau, …“, „Hörn. Hörn. …“). Alle drei wurden verworfen, zwei
  davon über die Token-Grenze nach 2,1 s.
- In den übrigen 7 Fällen fand schon die Stille-Erkennung (VAD) keine Sprache (0,1–1,2 s).
- `no_speech_prob` trennt in diesem kleinen Test deutlich: erfundener Text 0,62–0,90,
  echte Sprache 0,01–0,05. Wird vorerst nicht als Filter genutzt (nur 13 Werte).

**Entscheidung: go.** Der Filter bleibt. Tippen bleibt trotzdem der Hauptweg in der
Vorführung (Experiment S: Whisper verhört sich bei nicht geübten Sätzen oft).

## Einschränkungen

- Nur 3 × 10 Sätze: Die Ergebnisse (5/10, 7/10, 3/10) schwanken stark – eine Tendenz,
  keine genaue Messung. Zusammen: 15 von 30 gut.
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
python scripts/verbformen_test.py                   # Experiment A (ohne LLM)
# jeweils mit --ohne-ollama: nur Wortsuche, ohne Sprachmodell
```

Ergebnisse als CSV in `models/rag_test/` (nicht im Repository).
Hinweis: Die Läufe mit dem alten Wörterbuch (Spike 1, Spike 2 Satz 1) liefern mit dem
heutigen Wörterbuch andere Werte als oben.
