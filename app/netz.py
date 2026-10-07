"""Adresse des Jetson im WLAN und QR-Code dafür (für die Seite /qr).

Die IP wird bei JEDEM Aufruf neu ermittelt. Bekommt der Jetson am Tag der
Präsentation eine andere Adresse, zeigt der QR-Code trotzdem die richtige.
"""

import io
import socket
import subprocess


def lan_ip():
    """Gibt die IPv4-Adresse zurück, unter der andere Geräte den Jetson erreichen.

    Trick: Wir "verbinden" einen UDP-Socket zu einer beliebigen Adresse. Dabei wird
    nichts gesendet – das Betriebssystem wählt nur die passende Netzwerkkarte aus,
    und deren Adresse lesen wir ab.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            if not ip.startswith("127."):
                return ip
    except OSError:
        pass  # z. B. kein Netz mit Standard-Route (eigener Hotspot)

    # Plan B: erste Adresse aus "hostname -I", die nicht 127.x ist
    try:
        ausgabe = subprocess.run(["hostname", "-I"], capture_output=True, text=True,
                                 timeout=2).stdout
        for ip in ausgabe.split():
            if "." in ip and not ip.startswith("127."):
                return ip
    except (OSError, subprocess.SubprocessError):
        pass
    return "127.0.0.1"


def qr_svg(text):
    """Erzeugt einen QR-Code als SVG (ohne Internet, ohne externe Dienste)."""
    import segno

    puffer = io.BytesIO()
    segno.make(text, error="m").save(puffer, kind="svg", scale=10, border=2,
                                     xmldecl=False, svgns=True)
    return puffer.getvalue()
