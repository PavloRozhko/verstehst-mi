#!/usr/bin/env bash
# Erstellt ein selbst signiertes HTTPS-Zertifikat für den Jetson.
#
# Warum? Browser erlauben das Mikrofon nur über HTTPS (oder auf localhost).
# Ein selbst signiertes Zertifikat ist von keiner Stelle "beglaubigt", darum zeigt
# der Browser beim ersten Besuch eine Warnung. Nach "Erweitert -> Weiter zu …"
# funktioniert die Seite inklusive Mikrofon.
#
# Aufruf (im Projektordner):
#     bash scripts/zertifikat_erstellen.sh
#
# Neu ausführen, wenn sich die IP-Adresse des Jetson ändert.
#
# iPhone/Safari ist strenger als Chrome: ohne "extendedKeyUsage=serverAuth"
# und mit mehr als 825 Tagen Laufzeit lässt Safari die Seite gar nicht öffnen
# (der Knopf "Website besuchen" tut dann nichts).
# Der private Schlüssel (certs/schluessel.pem) darf NIE auf GitHub landen –
# der Ordner certs/ steht deshalb in .gitignore.

set -euo pipefail

ORDNER="$(cd "$(dirname "$0")/.." && pwd)/certs"
mkdir -p "$ORDNER"

# Alle IPv4-Adressen des Jetson + Hostname ins Zertifikat schreiben
SAN="DNS:localhost,DNS:$(hostname),DNS:$(hostname).local,IP:127.0.0.1"
for ip in $(hostname -I); do
  [[ "$ip" == *.* ]] && SAN="$SAN,IP:$ip"   # nur IPv4
done

openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout "$ORDNER/schluessel.pem" \
  -out "$ORDNER/zertifikat.pem" \
  -subj "/CN=verstehst-mi" \
  -addext "subjectAltName=$SAN" \
  -addext "basicConstraints=critical,CA:FALSE" \
  -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
  -addext "extendedKeyUsage=serverAuth" 2>/dev/null

chmod 600 "$ORDNER/schluessel.pem"

echo "Zertifikat erstellt in $ORDNER"
echo "Gültig für: $SAN"
echo
echo "Server starten mit:"
echo "  uvicorn app.main:app --host 0.0.0.0 --port 8000 \\"
echo "      --ssl-keyfile certs/schluessel.pem --ssl-certfile certs/zertifikat.pem"
