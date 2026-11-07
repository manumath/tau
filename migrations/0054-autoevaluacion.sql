-- Autoevaluación con el marco de calidad (PLAN §57, etapa 5).
--
-- - autoevaluacion: un proceso por marco, con el periodo que evalúa (años) y su estado. Solo una en curso por marco;
--   al concluirla, sus juicios ya no se cambian (la Dirección de Carrera puede reabrirla, y queda en la auditoría).
-- - juicio_criterio: por criterio, el nivel en la escala del marco (con su nombre de ese momento, por si la escala cambia
--   después), el juicio fundado, las fortalezas y las debilidades (una por línea: el plan de mejora partirá de ellas).
-- - sintesis_dimension: la síntesis de cada dimensión; el análisis global va en la autoevaluación.
-- Un criterio con juicios no se elimina del marco (la referencia no tiene ON DELETE: la base lo impide).
CREATE TABLE autoevaluacion (
    id              INTEGER PRIMARY KEY,
    marco_id        INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    nombre          TEXT    NOT NULL,
    desde_anio      INTEGER NOT NULL CHECK (desde_anio BETWEEN 2000 AND 2100),
    hasta_anio      INTEGER NOT NULL CHECK (hasta_anio BETWEEN 2000 AND 2100),
    estado          TEXT    NOT NULL DEFAULT 'en_curso' CHECK (estado IN ('en_curso', 'concluida')),
    analisis_global TEXT,
    creada_por      INTEGER REFERENCES usuario(id),
    creada_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    concluida_por   INTEGER REFERENCES usuario(id),
    concluida_en    TEXT,
    CHECK (desde_anio <= hasta_anio),
    CHECK ((estado = 'concluida') = (concluida_en IS NOT NULL))
);
CREATE UNIQUE INDEX ux_autoevaluacion_en_curso ON autoevaluacion (marco_id) WHERE estado = 'en_curso';

CREATE TABLE juicio_criterio (
    id                INTEGER PRIMARY KEY,
    autoevaluacion_id INTEGER NOT NULL REFERENCES autoevaluacion(id) ON DELETE CASCADE,
    criterio_id       INTEGER NOT NULL REFERENCES criterio_calidad(id),
    nivel             INTEGER,
    nivel_nombre      TEXT,
    juicio            TEXT,
    fortalezas        TEXT,
    debilidades       TEXT,
    actualizado_por   INTEGER REFERENCES usuario(id),
    actualizado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (autoevaluacion_id, criterio_id),
    CHECK ((nivel IS NULL) = (nivel_nombre IS NULL))
);
CREATE INDEX ix_juicio_criterio_criterio ON juicio_criterio (criterio_id);

CREATE TABLE sintesis_dimension (
    autoevaluacion_id INTEGER NOT NULL REFERENCES autoevaluacion(id) ON DELETE CASCADE,
    dimension_id      INTEGER NOT NULL REFERENCES dimension_calidad(id),
    sintesis          TEXT    NOT NULL,
    actualizado_por   INTEGER REFERENCES usuario(id),
    actualizado_en    TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (autoevaluacion_id, dimension_id)
);
