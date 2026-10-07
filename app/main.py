"""Web-Server für verstehst-mi.

Start (im Projektordner, mit aktiviertem .venv):
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Dann im Browser: http://<jetson-adresse>:8000

Ohne Spracherkennung starten (schneller, z. B. zum Testen der Oberfläche):
    VERSTEHST_MI_OHNE_SPRACHE=1 uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles

from app.sprache import AudioFehler, Spracherkennung
from app.uebersetzer import DEUTSCH_STEIRISCH, STEIRISCH_DEUTSCH, Uebersetzer

STATIC = Path(__file__).resolve().parent / "static"
# 15 s Sprache als webm/opus sind ca. 100–300 KB; 2 MB lässt viel Luft
MAX_AUDIO_BYTES = 2 * 1024 * 1024

log = logging.getLogger("uvicorn.error")

# Das Wörterbuch wird einmal beim Start geladen
uebersetzer = Uebersetzer()
erkennung = Spracherkennung()


@asynccontextmanager
async def lebenszyklus(app):
    """Läuft einmal beim Start des Servers: lädt das Whisper-Modell.

    Klappt das nicht (z. B. Modell fehlt und kein Internet), läuft der Server
    trotzdem weiter – nur ohne Spracheingabe.
    """
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


@app.get("/api/status")
def status():
    return {"eintraege": len(uebersetzer.eintraege), "sprache": erkennung.bereit}


# Statische Dateien (HTML, CSS, JS) – muss als Letztes kommen, sonst verdeckt es /api
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")