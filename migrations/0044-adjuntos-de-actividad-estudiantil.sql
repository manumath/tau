-- La evidencia de la actividad estudiantil (PLAN §49) se guarda como adjunto: `adjunto.entidad` admite ahora
-- 'actividad_estudiantil'. SQLite no cambia un CHECK: se recrea la tabla conservando todos los adjuntos.
CREATE TABLE adjunto_nueva (
    id         INTEGER PRIMARY KEY,
    entidad    TEXT    NOT NULL CHECK (entidad IN ('actividad', 'producto', 'actividad_estudiantil')),
    entidad_id INTEGER NOT NULL,
    nombre     TEXT    NOT NULL,             -- nombre original, solo para mostrar y descargar
    archivo    TEXT    NOT NULL UNIQUE,      -- nombre aleatorio en <datos>/adjuntos
    mime       TEXT    NOT NULL,
    tamano     INTEGER NOT NULL,
    subido_por INTEGER NOT NULL REFERENCES usuario(id),
    subido_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO adjunto_nueva (id, entidad, entidad_id, nombre, archivo, mime, tamano, subido_por, subido_en)
    SELECT id, entidad, entidad_id, nombre, archivo, mime, tamano, subido_por, subido_en FROM adjunto;
DROP TABLE adjunto;
ALTER TABLE adjunto_nueva RENAME TO adjunto;
CREATE INDEX ix_adjunto_entidad ON adjunto (entidad, entidad_id);
