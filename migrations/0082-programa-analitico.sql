-- Programa analítico por asignatura y gestión (PLAN §68, etapa 3).
--
-- El titular de la materia en una gestión escribe el programa (objetivos, contenido, metodología, evaluación y
-- bibliografía). Cada publicación crea una versión que ya no se edita; el borrador es único por asignatura y gestión. El
-- estudiante ve la última versión publicada desde su plan de estudios; la Coordinación ve la cobertura.
CREATE TABLE programa_analitico (
    id            INTEGER PRIMARY KEY,
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id),
    gestion_id    INTEGER NOT NULL REFERENCES gestion_academica(id) ON DELETE CASCADE,
    autor_id      INTEGER NOT NULL REFERENCES usuario(id),
    estado        TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'publicado')),
    version       INTEGER,                         -- se asigna al publicar (1, 2, …); NULL en el borrador
    objetivos     TEXT,
    contenido     TEXT,                            -- unidades temáticas, una por línea
    metodologia   TEXT,
    evaluacion    TEXT,
    bibliografia  TEXT,                            -- una referencia por línea
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    publicado_en  TEXT
);
CREATE UNIQUE INDEX ux_programa_borrador ON programa_analitico (asignatura_id, gestion_id) WHERE estado = 'borrador';
CREATE UNIQUE INDEX ux_programa_version ON programa_analitico (asignatura_id, gestion_id, version) WHERE version IS NOT NULL;
CREATE INDEX ix_programa_asignatura ON programa_analitico (asignatura_id, estado);
