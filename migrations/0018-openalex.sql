-- Carga automática desde OpenAlex (punto 5 del análisis) y citas para medir impacto (IAC-CINDA 3.6.1).
ALTER TABLE producto ADD COLUMN openalex_id TEXT;            -- p. ej. W2125495920
ALTER TABLE producto ADD COLUMN citas INTEGER;                -- cited_by_count de OpenAlex
ALTER TABLE producto ADD COLUMN citas_actualizadas TEXT;      -- fecha de la última consulta
CREATE UNIQUE INDEX ux_producto_openalex ON producto (openalex_id) WHERE openalex_id IS NOT NULL;

-- Obras que el investigador descartó en la búsqueda (no son suyas o no quiere registrarlas):
-- no se le vuelven a proponer.
CREATE TABLE cosecha_descartada (
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    openalex_id TEXT NOT NULL,
    titulo      TEXT,
    fecha       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (usuario_id, openalex_id)
);
