"""Web-Server für verstehst-mi.

Start (im Projektordner, mit aktiviertem .venv):
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Dann im Browser: http://<jetson-adresse>:8000

Ohne Spracherkennung starten (schneller, z. B. zum Testen der Oberfläche):
    VERSTEHST_MI_OHNE_SPRACHE=1 uvicorn app.main:app --host 0.0.0.0 --port 8000

Ohne KI-Übersetzung starten (nur Wortbedeutungen, Ollama wird nicht gefragt):
    VERSTEHST_MI_OHNE_KI=1 uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app import ki_hochdeutsch
from app.netz import lan_ip, qr_svg

from app.sprache import AudioFehler, Spracherkennung
from app.uebersetzer import DEUTSCH_STEIRISCH, STEIRISCH_DEUTSCH, Uebersetzer

STATIC = Path(__file__).resolve().parent / "static"
# 15 s Sprache als webm/opus sind ca. 100–300 KB; 2 MB lässt viel Luft
MAX_AUDIO_BYTES = 2 * 1024 * 1024

log = logging.getLogger("uvicorn.error")

# Das Wörterbuch wird einmal beim Start geladen
uebersetzer = Uebersetzer()
erkennung = Spracherkennung()
# None = KI ausgeschaltet; sonst wird gemma3 beim Start im Hintergrund geladen (~70 s)
ki_modell = None if os.environ.get("VERSTEHST_MI_OHNE_KI") == "1" else ki_hochdeutsch.KiModell()


@asynccontextmanager
async def lebenszyklus(app):
    """Läuft einmal beim Start des Servers: lädt Whisper und (im Hintergrund) gemma3.

    Klappt das nicht (z. B. Modell fehlt und kein Internet), läuft der Server
    trotzdem weiter – nur ohne Spracheingabe bzw. ohne KI-Übersetzung.
    """
    if ki_modell is None:
        log.info("KI-Übersetzung ausgeschaltet (VERSTEHST_MI_OHNE_KI=1)")
    else:
        # im Hintergrund: der Server ist sofort erreichbar, die KI kommt nach ~70 s dazu
        ki_modell.im_hintergrund_aufwaermen()
    if os.environ.get("VERSTEHST_MI_OHNE_SPRACHE") == "1":
        log.info("Spracherkennung ausgeschaltet (VERSTEHST_MI_OHNE_SPRACHE=1)")
    else:
        start = time.perf_counter()
        try:
            await run_in_threadpool(erkennung.laden)
            log.info("Whisper '%s' geladen in %.1f s", erkennung.modell_name,
                     time.perf_counter() - start)
        except Exception:
            log.exception("Whisper konnte nicht geladen werden – Spracheingabe ist aus")
    yield


app = FastAPI(title="verstehst-mi", description="Steirisch ↔ Hochdeutsch",
              lifespan=lebenszyklus)


def fuer_anzeige(treffer):
    """Teilt Treffer in Übersetzungen, Vorschläge und Beispiele auf.

    Gibt es einen exakten Treffer, werden ähnliche Treffer nicht mehr gezeigt –
    sonst erscheint z. B. bei "Der is ma zwida" auch "Des is ma z'teia".
    """
    exakt = [t for t in treffer if t.art == "exakt"]
    aehnlich = [t for t in treffer if t.art == "ähnlich"]
    beispiele = [t for t in treffer if t.art == "in Phrase"]

    return {
        "uebersetzungen": [asdict(t) for t in exakt],
        "vorschlaege": [] if exakt else [asdict(t) for t in aehnlich],
        "beispiele": [asdict(t) for t in beispiele],
    }


@app.get("/api/uebersetzen")
def uebersetzen(
    text: str = Query(..., max_length=300),
    richtung: str = Query(STEIRISCH_DEUTSCH),
    derb: bool = Query(False),
):
    if richtung not in (STEIRISCH_DEUTSCH, DEUTSCH_STEIRISCH):
        raise HTTPException(status_code=400, detail="richtung muss st-de oder de-st sein")

    treffer = uebersetzer.uebersetzen(text, richtung, mit_derb=derb, limit=8)
    return {"text": text, "richtung": richtung, **fuer_anzeige(treffer)}


@app.post("/api/sprache")
async def sprache(request: Request, derb: bool = Query(False)):
    """Nimmt eine Aufnahme aus dem Browser (als rohe Bytes) und sucht sie im Wörterbuch.

    Fehlermeldungen sind kurz und für Menschen gedacht; Details landen nur im Server-Log.
    """
    if not erkennung.bereit:
        raise HTTPException(status_code=503, detail="Spracherkennung ist nicht bereit")

    if int(request.headers.get("content-length") or 0) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Aufnahme ist zu groß")
    daten = await request.body()
    if not daten:
        raise HTTPException(status_code=400, detail="Keine Aufnahme erhalten")
    if len(daten) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Aufnahme ist zu groß")

    start = time.perf_counter()
    try:
        # Whisper rechnet in einem eigenen Thread, damit der Server nicht blockiert
        text = await run_in_threadpool(erkennung.erkennen, daten)
    except AudioFehler as fehler:
        raise HTTPException(status_code=400, detail=str(fehler))
    except Exception:
        log.exception("Fehler bei der Spracherkennung")
        raise HTTPException(status_code=500, detail="Spracherkennung fehlgeschlagen")
    sekunden = round(time.perf_counter() - start, 1)
    log.info("Sprache erkannt in %.1f s: %r", sekunden, text)

    treffer = uebersetzer.sprache_suchen(text, mit_derb=derb, limit=8) if text else []
    return {"erkannt": text, "sekunden": sekunden, **fuer_anzeige(treffer)}


@app.get("/api/ki_uebersetzung")
def ki_uebersetzung(text: str = Query(..., max_length=300)):
    """Steirisch -> Hochdeutsch für ganze Sätze (Experiment, "ungeprüft").

    quelle: "wörterbuch" (geprüfte Phrase), "ki" (KI aus geprüften Wörtern) oder
    "nur_woerter" (KI nicht bereit – nur die Wortbedeutungen, siehe hinweis).
    Gibt nie einen Fehler zurück, nur weil die KI fehlt.
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="Bitte einen Satz eingeben")

    start = time.perf_counter()
    e = ki_hochdeutsch.uebersetzen_fuer_app(uebersetzer, text, ki_modell)
    sekunden = round(time.perf_counter() - start, 1)
    log.info("KI-Übersetzung (%s) in %.1f s: %r -> %r", e.quelle, sekunden, text,
             e.woerterbuch_phrase or e.text)
    return {
        "text": text,
        "quelle": e.quelle,
        "uebersetzung": e.woerterbuch_phrase or e.text or None,
        "woerter": [
            {"wort": p.suchwort, "dialekt": p.dialekt, "hochdeutsch": p.hochdeutsch,
             "abgeleitet": p.abgeleitet, "derb": p.derb}
            for p in e.paare
        ],
        "nicht_gefunden": e.nicht_gefunden,
        "bedeutung_fehlt": [p.dialekt for p in e.bedeutung_fehlt],
        "hinweis": e.hinweis,
        "sekunden": sekunden,
    }


@app.get("/api/status")
def status():
    return {"eintraege": len(uebersetzer.eintraege), "sprache": erkennung.bereit,
            "ki": bool(ki_modell and ki_modell.bereit)}


def seiten_adresse(request):
    """Adresse, die Handys im WLAN aufrufen sollen, z. B. https://192.168.1.50:8000

    Protokoll und Port kommen aus der aktuellen Anfrage (läuft der Server mit HTTPS,
    steht auch im QR-Code https). Die IP wird immer neu ermittelt – auch wenn die
    Seite am Jetson selbst über localhost geöffnet wird.
    """
    port = request.url.port
    standard = {"http": 80, "https": 443}[request.url.scheme]
    port_teil = f":{port}" if port and port != standard else ""
    return f"{request.url.scheme}://{lan_ip()}{port_teil}"


@app.get("/api/adresse")
def adresse(request: Request):
    return {"url": seiten_adresse(request)}


@app.get("/api/qr.svg")
def qr(request: Request):
    return Response(qr_svg(seiten_adresse(request)), media_type="image/svg+xml",
                    headers={"Cache-Control": "no-store"})


@app.get("/qr")
def qr_seite():
    """Seite für Beamer/Bildschirm: großer QR-Code + Anleitung."""
    return FileResponse(STATIC / "qr.html")


# Statische Dateien (HTML, CSS, JS) – muss als Letztes kommen, sonst verdeckt es /api
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")