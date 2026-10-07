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
