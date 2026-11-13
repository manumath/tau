-- Biblioteca y recursos (PLAN §67, etapa 10): apuntes, guías, exámenes pasados, libros y enlaces que suben los docentes y consultan
-- los estudiantes, por asignatura. Los archivos (PDF, PNG o JPG) usan los adjuntos del sistema: la tabla `adjunto` acepta la
-- entidad nueva «recurso» (SQLite exige recrearla para cambiar su CHECK).
CREATE TABLE adjunto_nueva (
    id         INTEGER PRIMARY KEY,
    entidad    TEXT    NOT NULL CHECK (entidad IN ('actividad', 'producto', 'actividad_estudiantil',
                                                  'convocatoria_auxiliatura', 'requisito_postulacion', 'tramite_grado',
                                                  'recurso')),
    entidad_id INTEGER NOT NULL,
    nombre     TEXT    NOT NULL,
    archivo    TEXT    NOT NULL UNIQUE,
    mime       TEXT    NOT NULL,
    tamano     INTEGER NOT NULL,
    subido_por INTEGER NOT NULL REFERENCES usuario(id),
    subido_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO adjunto_nueva SELECT id, entidad, entidad_id, nombre, archivo, mime, tamano, subido_por, subido_en FROM adjunto;
DROP TABLE adjunto;
ALTER TABLE adjunto_nueva RENAME TO adjunto;
CREATE INDEX ix_adjunto_entidad ON adjunto (entidad, entidad_id);

CREATE TABLE recurso (
    id          INTEGER PRIMARY KEY,
    tipo        TEXT NOT NULL CHECK (tipo IN ('apunte', 'guia', 'examen', 'libro', 'enlace', 'otro')),
    titulo      TEXT NOT NULL,
    descripcion TEXT,
    enlace      TEXT,                                   -- un enlace externo (en lugar de, o además de, un archivo)
    anio        INTEGER,                                -- gestión a la que corresponde (exámenes pasados)
    autor_id    INTEGER NOT NULL REFERENCES usuario(id),
    estado      TEXT NOT NULL DEFAULT 'publicado' CHECK (estado IN ('publicado', 'retirado')),
    creado_en   TEXT NOT NULL DEFAULT (datetime('now')),
    retirado_en TEXT,
    retirado_por INTEGER REFERENCES usuario(id)
);
CREATE INDEX ix_recurso_estado ON recurso (estado, creado_en);

CREATE TABLE recurso_asignatura (
    recurso_id    INTEGER NOT NULL REFERENCES recurso(id) ON DELETE CASCADE,
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id),
    PRIMARY KEY (recurso_id, asignatura_id)
);
