-- Datenbankschema für verstehst-mi
-- Die Datenbank wird bei jedem Import komplett neu aus den CSV-Dateien gebaut.

DROP TABLE IF EXISTS eintraege;

CREATE TABLE eintraege (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    typ          TEXT    NOT NULL CHECK (typ IN ('wort', 'phrase')),
    dialekt      TEXT    NOT NULL,          -- geprüfte steirische Form
    hochdeutsch  TEXT    NOT NULL,          -- Bedeutungen, getrennt mit ";"
    thema        TEXT,                      -- z. B. Alltag, Essen, Arbeit
    wortart      TEXT,                      -- nur bei Wörtern
    derb         INTEGER NOT NULL DEFAULT 0, -- 1 = derber Ausdruck, standardmäßig ausblenden
    kommentar    TEXT,
    geprueft_von TEXT,
    quelle       TEXT    NOT NULL,          -- Herkunft, z. B. "phrasen.csv#11"
    UNIQUE (typ, dialekt, hochdeutsch)
);

CREATE INDEX idx_dialekt     ON eintraege (dialekt);
CREATE INDEX idx_hochdeutsch ON eintraege (hochdeutsch);