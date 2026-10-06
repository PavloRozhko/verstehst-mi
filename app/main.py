"""Web-Server für verstehst-mi.

Start (im Projektordner, mit aktiviertem .venv):
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Dann im Browser: http://<jetson-adresse>:8000
"""

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from app.uebersetzer import DEUTSCH_STEIRISCH, STEIRISCH_DEUTSCH, Uebersetzer

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="verstehst-mi", description="Steirisch ↔ Hochdeutsch")

# Das Wörterbuch wird einmal beim Start geladen
uebersetzer = Uebersetzer()


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


@app.get("/api/status")
def status():
    return {"eintraege": len(uebersetzer.eintraege)}


# Statische Dateien (HTML, CSS, JS) – muss als Letztes kommen, sonst verdeckt es /api
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")