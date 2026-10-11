"""verstehst-mi: Steirisch ↔ Hochdeutsch auf dem Jetson.

Module:
    main.py           Web-Server (FastAPI): Seiten und API
    uebersetzer.py    Suche im geprüften Wörterbuch (tolerant gegenüber Tippfehlern)
    wortsuche.py      Wörter eines Satzes einzeln nachschlagen (für die KI)
    verbformen.py     gebeugte Verbformen auf den Infinitiv zurückführen (Experiment A)
    ki_hochdeutsch.py KI-Übersetzung Steirisch -> Hochdeutsch (Experiment, "ungeprüft")
    ollama.py         Verbindung zum lokalen Sprachmodell
    sprache.py        Spracherkennung mit Whisper (+ Filter gegen erfundenen Text)
    netz.py           Adresse im WLAN und QR-Code
    vorschlag.py      Spike 1: Hochdeutsch -> Steirisch (no-go, nicht in der App)
"""
