#!/usr/bin/env bash
# Richtet den Autostart ein: verstehst-mi läuft dann nach jedem Einschalten von selbst.
#
# Aufruf (im Projektordner, als normaler Benutzer – sudo fragt nach dem Passwort):
#     bash scripts/autostart_einrichten.sh
#
# Danach nützliche Befehle:
#     systemctl status verstehst-mi          läuft er?
#     journalctl -u verstehst-mi -f          Log live ansehen (Strg+C beendet)
#     sudo systemctl restart verstehst-mi    nach Code-Änderungen neu starten
#     sudo systemctl stop verstehst-mi       anhalten (z. B. zum Entwickeln)
#     sudo systemctl disable verstehst-mi    Autostart wieder ausschalten

set -euo pipefail

PROJEKT="$(cd "$(dirname "$0")/.." && pwd)"
BENUTZER="$(id -un)"
ZIEL=/etc/systemd/system/verstehst-mi.service

if [[ "$BENUTZER" == "root" ]]; then
  echo "Bitte OHNE sudo aufrufen – der Dienst soll als normaler Benutzer laufen."
  exit 1
fi

# Voraussetzungen prüfen
[[ -x "$PROJEKT/.venv/bin/uvicorn" ]] || { echo "Fehlt: .venv mit uvicorn"; exit 1; }
[[ -d "$PROJEKT/models/whisper" ]] || echo "Hinweis: models/whisper fehlt – dann ohne Spracheingabe."
if [[ ! -f "$PROJEKT/certs/zertifikat.pem" ]]; then
  echo "Kein Zertifikat gefunden – wird erstellt."
  bash "$PROJEKT/scripts/zertifikat_erstellen.sh"
fi

# Platzhalter ersetzen und Dienst installieren
sed -e "s|@PROJEKT@|$PROJEKT|g" -e "s|@BENUTZER@|$BENUTZER|g" \
    "$PROJEKT/deploy/verstehst-mi.service" | sudo tee "$ZIEL" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable verstehst-mi
sudo systemctl restart verstehst-mi

echo
echo "Fertig. Status:"
sleep 3
systemctl --no-pager --lines=5 status verstehst-mi || true
