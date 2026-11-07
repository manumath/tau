-- Plan de mejora y evaluación externa (PLAN §57, etapa 6).
--
-- - evaluacion_externa: una evaluación por pares o una acreditación (organismo en texto libre, sin catálogo de agencias),
--   con visita, dictamen, resultado y vigencia; el informe del organismo puede ser una evidencia del repositorio.
-- - recomendacion_externa: lo que recomendó el organismo, opcionalmente ligado a un criterio del marco.
-- - accion_mejora: cada acción del plan, con su origen (una debilidad de la autoevaluación, una recomendación externa u
--   otro), criterio, responsable, plazo, indicador y meta, prioridad y estado. La debilidad se copia en texto: el juicio
--   puede cambiar si se reabre la autoevaluación.
-- - avance_accion: los avances, con porcentaje opcional y una evidencia del repositorio si la hay.
-- Los avisos de vencimiento se registran en aviso_enviado (una vez por acción y por umbral).
CREATE TABLE evaluacion_externa (
    id              INTEGER PRIMARY KEY,
    marco_id        INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    organismo       TEXT    NOT NULL,
    tipo            TEXT    NOT NULL DEFAULT 'acreditacion' CHECK (tipo IN ('acreditacion', 'pares', 'otra')),
    fecha_visita    TEXT,
    fecha_dictamen  TEXT,
    resultado       TEXT,                    -- dictamen en palabras (acreditada, con observaciones…)
    vigente_hasta   TEXT,
    evidencia_id    INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    nota            TEXT,
    creada_por      INTEGER REFERENCES usuario(id),
    creada_en       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE recomendacion_externa (
    id            INTEGER PRIMARY KEY,
    evaluacion_id INTEGER NOT NULL REFERENCES evaluacion_externa(id) ON DELETE CASCADE,
    texto         TEXT    NOT NULL,
    criterio_id   INTEGER REFERENCES criterio_calidad(id) ON DELETE SET NULL
);

CREATE TABLE accion_mejora (
    id                INTEGER PRIMARY KEY,
    marco_id          INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    titulo            TEXT    NOT NULL,
    descripcion       TEXT,
    origen            TEXT    NOT NULL CHECK (origen IN ('autoevaluacion', 'externa', 'otro')),
    autoevaluacion_id INTEGER REFERENCES autoevaluacion(id) ON DELETE SET NULL,
    debilidad         TEXT,                  -- copia de la debilidad que la origina
    recomendacion_id  INTEGER REFERENCES recomendacion_externa(id) ON DELETE SET NULL,
    criterio_id       INTEGER REFERENCES criterio_calidad(id) ON DELETE SET NULL,
    responsable_id    INTEGER REFERENCES usuario(id),
    plazo             TEXT    NOT NULL,      -- AAAA-MM-DD
    indicador_id      INTEGER REFERENCES indicador_calidad(id) ON DELETE SET NULL,
    meta              REAL,
    prioridad         TEXT    NOT NULL DEFAULT 'media' CHECK (prioridad IN ('alta', 'media', 'baja')),
    estado            TEXT    NOT NULL DEFAULT 'pendiente'
                      CHECK (estado IN ('pendiente', 'en_curso', 'cumplida', 'cancelada')),
    cumplida_en       TEXT,                  -- AAAA-MM-DD
    motivo_cancelacion TEXT,
    creada_por        INTEGER REFERENCES usuario(id),
    creada_en         TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK ((estado = 'cumplida') = (cumplida_en IS NOT NULL)),
    CHECK ((estado = 'cancelada') = (motivo_cancelacion IS NOT NULL))
);
CREATE INDEX ix_accion_mejora_plazo ON accion_mejora (estado, plazo);
CREATE INDEX ix_accion_mejora_responsable ON accion_mejora (responsable_id);

CREATE TABLE avance_accion (
    id             INTEGER PRIMARY KEY,
    accion_id      INTEGER NOT NULL REFERENCES accion_mejora(id) ON DELETE CASCADE,
    fecha          TEXT    NOT NULL,
    texto          TEXT    NOT NULL,
    porcentaje     INTEGER CHECK (porcentaje IS NULL OR porcentaje BETWEEN 0 AND 100),
    evidencia_id   INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);
