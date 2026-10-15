# Jetson Setup

## Hardware
- NVIDIA Jetson Orin Nano Developer Kit, 8 GB RAM
- 512 GB NVMe SSD (System läuft vom SSD)

## Software
- Jetson Linux R39.2.1
- Python 3.12.3

## Fernzugriff
- SSH mit Schlüssel (ohne Passwort)
- Entwicklung mit VS Code + Remote-SSH
- GitHub-Zugriff per SSH-Schlüssel
## Autostart (systemd)

Der Server startet nach dem Einschalten automatisch – mit HTTPS und voller
Taktfrequenz (`jetson_clocks`). Einrichten (einmalig, im Projektordner):

```bash
bash scripts/autostart_einrichten.sh
```

Danach ist die Seite unter `https://<IP-des-Jetson>:8000` erreichbar,
der QR-Code unter `https://<IP-des-Jetson>:8000/qr`.

| Befehl | Wozu |
|---|---|
| `systemctl status verstehst-mi` | Läuft der Dienst? |
| `journalctl -u verstehst-mi -f` | Log live ansehen |
| `sudo systemctl restart verstehst-mi` | Nach Code-Änderungen neu starten |
| `sudo systemctl stop verstehst-mi` | Anhalten, z. B. um `uvicorn` von Hand zu starten |
| `sudo systemctl disable verstehst-mi` | Autostart ausschalten |

Hinweis: Solange der Dienst läuft, ist Port 8000 belegt. Ein zweiter, von Hand
gestarteter `uvicorn` auf Port 8000 meldet dann „address already in use“.

## KI-Übersetzung mit Claude statt gemma3

Statt gemma3 auf dem Jetson kann Claude (Anthropic API) die Sätze übersetzen. Prompt und
geprüfte Wörter sind dieselben (`app/claude_ki.py`). gemma3 wird dann nicht geladen, das
spart ca. 3,5 GB Speicher. Dafür braucht der Jetson Internet, und jede Anfrage kostet
etwas. Ohne Internet zeigt die App nur die Wortbedeutungen.

1. API-Schlüssel anlegen: <https://platform.claude.com> → API Keys (Guthaben aufladen).
2. Im Projektordner auf dem Jetson:

   ```bash
   git pull
   .venv/bin/pip install -r requirements.txt
   printf 'VERSTEHST_MI_KI=claude\nANTHROPIC_API_KEY=sk-ant-...\n' > .env
   chmod 600 .env
   bash scripts/autostart_einrichten.sh   # Dienst neu installieren (liest jetzt .env)
   ```

3. Prüfen: `journalctl -u verstehst-mi -f`, dann in der App einen Satz mit dem KI-Knopf
   übersetzen. Die Fußzeile zeigt „KI bereit“.

Zurück zu gemma3: in `.env` die Zeile `VERSTEHST_MI_KI=claude` löschen und
`sudo systemctl restart verstehst-mi`.

Testsätze mit Claude laufen lassen (gleiche Sätze wie bei gemma3):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/rag_test_hochdeutsch.py --satz 4 --claude
```

