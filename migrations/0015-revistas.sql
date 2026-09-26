-- Catálogo de revistas con su indexación verificada por año (sección 14 del plan).

CREATE TABLE revista (
    id              INTEGER PRIMARY KEY,
    titulo          TEXT NOT NULL,
    issn            TEXT UNIQUE,                  -- impreso, forma 1234-567X
    eissn           TEXT UNIQUE,                  -- electrónico
    pais            TEXT,
    editorial       TEXT,
    url             TEXT,
    arbitrada       INTEGER CHECK (arbitrada IN (0, 1)),       -- revisión por pares
    acceso_abierto  INTEGER CHECK (acceso_abierto IN (0, 1)),
    estado          TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'verificada')),
    nota            TEXT,
    propuesta_por   INTEGER REFERENCES usuario(id),
    verificada_por  INTEGER REFERENCES usuario(id),
    verificada_en   TEXT,
    creado_en       TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en  TEXT
);
CREATE INDEX ix_revista_titulo ON revista (titulo);

-- La revista figura en el índice entre `desde` y `hasta` (años; hasta vacío = vigente).
CREATE TABLE revista_indice (
    id             INTEGER PRIMARY KEY,
    revista_id     INTEGER NOT NULL REFERENCES revista(id) ON DELETE CASCADE,
    indice_id      INTEGER NOT NULL REFERENCES indice(id),
    desde          INTEGER NOT NULL,
    hasta          INTEGER,
    cuartil        TEXT CHECK (cuartil IN ('Q1', 'Q2', 'Q3', 'Q4')),
    fuente         TEXT,                          -- p. ej. «Lista maestra de Scopus, junio 2026»
    evidencia_url  TEXT,
    verificado_por INTEGER REFERENCES usuario(id),
    verificado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (hasta IS NULL OR hasta >= desde)
);
CREATE INDEX ix_revista_indice ON revista_indice (revista_id, indice_id);

ALTER TABLE producto ADD COLUMN revista_id INTEGER REFERENCES revista(id) ON DELETE SET NULL;
CREATE INDEX ix_producto_revista ON producto (revista_id);
