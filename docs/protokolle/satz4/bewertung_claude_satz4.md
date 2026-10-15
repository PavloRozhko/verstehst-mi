# Satz 4: Bewertung von Claude (festgehalten vor Pavlos Bewertung)

Lauf: 14.10.2026, Ausgabe in `satz4_lauf.txt`. Diese Datei wurde geschrieben und mit sha256
festgehalten, **bevor** Pavlo bewertet hat. Danach wird sie nicht mehr geändert.

Maßstab wie bei Satz 1–3: Bewertet wird die **Bedeutung** der KI-Übersetzung im Vergleich
zur geprüften Übersetzung. *gut* = Sinn stimmt (kleine Stilfehler egal), *teils* = Sinn
erkennbar, aber etwas Wichtiges fehlt oder der Satz ist fehlerhaft, *falsch* = anderer Sinn.
Widerspruch = die KI schreibt etwas, das einer geprüften Wortbedeutung widerspricht.

| Nr | Dialekt | KI | Claude | Begründung |
|---|---|---|---|---|
| 1 | Des geht si ned aus. | Das geht nicht aus. | falsch | Ohne „sich“ heißt es „erlischt nicht / endet nicht“, nicht „reicht nicht“. `si` war versteckt. |
| 2 | I bin im Krankenstand. | Ich bin im Krankschreibung. | teils | Sinn erkennbar, aber grammatisch falsch („im“ + feminin). Kein Vorbild für Lernende. |
| 3 | I hob an Hunga. | Ich habe einen Hunger. | gut | Umgangssprachlich korrekt. `Hunga` war versteckt. |
| 4 | Do legst di nieda! | Du legst dich nieder! | teils | „Da“ fehlt, damit geht das Staunen verloren; liest sich wie Aufforderung. Grenzfall zu falsch. |
| 5 | I gfrei mi scho drauf. | Ich freue mich schon darauf. | gut | Wörtlich gleich. `gfrei` war versteckt. |
| 6 | Gebm S' ma a Viertl Kilo Topfn. | Geben Sie mir ein Viertel Kilo Quark. | gut | Nur Schreibweise. `ma` richtig als „mir“ gewählt (Wort-für-Wort: „man“). |
| 7 | Mia hom a Hetz ghobt. | Wir hatten Spaß. | gut | „viel“ fehlt, Sinn stimmt. ⚠ ist Fehlalarm (Präteritum statt Perfekt). |
| 8 | Wia kumm i auf'n Schöckl? | Wie komme ich auf einen Berg? | teils | Frage stimmt, aber der Name (das eigentliche Ziel) ist weg. `auf'n` war versteckt. |
| 9 | I hob mi vagangen. | Ich habe mich verlaufen. | gut | Wörtlich gleich, obwohl `vagangen` versteckt war. |
| 10 | Du host jo an festn Poscha. | Du hast einen großen Schaden. | teils | „Einen Schaden haben“ = verrückt sein ist umgangssprachlich richtig, für Lernende aber mehrdeutig; Hinweis „verrückt sein“ nicht genutzt. Grenzfall zu gut. |

## Ergebnis (Claude)

| Kriterium | Ergebnis | |
|---|---|---|
| Zeit | 0,7 s (Median), höchstens 1,0 s | ✅ |
| Bedeutung | 5 gut / 4 teils / 1 falsch → **5/10** | ❌ (Ziel ≥ 7) |
| Widersprüche | 1 fraglich (Nr. 4: `do` = da wurde zu „du“) | ❌ |

Grenzfälle: Nr. 4 (teils/falsch) und Nr. 10 (teils/gut). Auch mit Nr. 10 als gut wären es 6/10.

## Beobachtungen

- **`a`/`an` (Korrektur 11.10.):** In Nr. 3, 6, 7 und 10 kein einziges Mal „auch“ gewählt.
  In Satz 3 war „auch“ dreimal falsch (Nr. 4, 8, 10). Tendenz, kein Beweis (anderer Satz).
- **`mei` (Korrektur 14.10.):** kommt in Satz 4 nicht vor, Wirkung hier nicht messbar.
  `es`, `owa`, `Fetzn`, `sauba` kommen ebenfalls nicht vor.
- **Versteckte Wörter:** 4 von 7 Sätzen trotzdem gut (Nr. 3, 5, 6, 9). Die Fehler betreffen
  wie bei Satz 2 und 3 **feste Ausdrücke** (`geht si aus`, `Do legst di nieda`, `an Poscha hobn`)
  und einen **Eigennamen** (`Schöckl`).
- **⚠-Hinweis:** 3 Meldungen, davon 1 sinnvoll (Nr. 4), 2 Fehlalarme (Nr. 7, 10).

## Über alle Sätze

Satz 1: 5 · Satz 2: 7 · Satz 3: 3 · Satz 4: 5 (Claude) → **20 von 40 gut (50 %)**, wie bisher.
