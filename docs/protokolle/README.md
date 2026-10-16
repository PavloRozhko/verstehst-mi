# Protokolle

Rohdaten zu den Experimenten in [`../experimente.md`](../experimente.md). Die Dateien liegen
**unverändert** hier, damit die sha256-Werte, die vor den Läufen festgehalten wurden, weiter
stimmen. Einige sind auf Ukrainisch geschrieben; die Zusammenfassung auf Deutsch steht in
`experimente.md`.

| Ordner | Inhalt | sha256 (Anfang) |
|---|---|---|
| `satz4/` | `satz4_lauf.txt`: Ausgabe des Laufs am 14.10. · `bewertung_claude_satz4.md`: Bewertung von Claude, festgehalten vor Pavlos Bewertung | `fc17beda…` (Bewertung) |
| `5b/` | `kriterien_5b.md`, `kriterien_5b_satz.md`, `satz_5b.csv`: vor dem Lauf festgelegt · `5b_lauf.txt`: Ausgabe von Lauf 1 · `ergebnis_5b*.md`: Auswertung | `2664030e…`, `a9884ea7…`, `65d844cc…` |
| `llm_test/` | Vergleich gemma3:4b und llama3.1:8b (Bedeutung, Erklärung, Sekunden, Tokens/s), 07.10. | – |
| `rag_test/` | Ergebnisse der RAG-Läufe: `ohne_llm.csv`, `gemma3_4b.csv` (Spike 1, 08.10.), `hochdeutsch_gemma3_4b*.csv` (Spike 2, Satz 1–4, 08.–14.10.); Kopien aus `models/rag_test/` | – |
| `whisper/` | `sprachtest_log.txt`: Spracherkennung mit Whisper · `filtertest_log.txt`: Filter gegen erfundenen Whisper-Text (beide 11.10., Auszug aus dem Dienst-Log) | – |

Prüfen: `sha256sum docs/protokolle/5b/* docs/protokolle/satz4/*`
