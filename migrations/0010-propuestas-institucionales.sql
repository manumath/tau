-- Ajustes tras las pruebas, etapa C: propuestas de proyectos institucionales.
--
-- Un proyecto institucional rige por periodos anuales (octubre a septiembre). Cada periodo
-- tiene una propuesta: la del proyecto nuevo o la de continuidad. `periodo` es el año de inicio:
-- 2026 = 1-oct-2026 a 30-sep-2027.

-- Plazos de presentación que la administración cambió. Sin fila, el plazo es todo septiembre
-- del año `periodo`.
CREATE TABLE convocatoria (
    periodo         INTEGER PRIMARY KEY,
    abre            TEXT NOT NULL,
    cierra          TEXT NOT NULL,
    actualizado_por INTEGER REFERENCES usuario(id),
    actualizado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (cierra >= abre)
);

CREATE TABLE propuesta_institucional (
    id                   INTEGER PRIMARY KEY,
    proyecto_id          INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    periodo              INTEGER NOT NULL,
    modalidad            TEXT NOT NULL CHECK (modalidad IN ('nuevo', 'continuidad')),
    -- Contenido propio de la propuesta (al aceptarse, los datos básicos pasan al proyecto).
    nombre               TEXT NOT NULL,
    descripcion          TEXT,
    objetivo_general     TEXT,
    metodologia          TEXT,
    resultados_esperados TEXT,
    bibliografia         TEXT,
    estado               TEXT NOT NULL DEFAULT 'borrador'
                         CHECK (estado IN ('borrador', 'enviada', 'aceptada', 'condicional',
                                           'rechazada', 'retirada')),
    proponente_id        INTEGER NOT NULL REFERENCES usuario(id),
    creada_en            TEXT NOT NULL DEFAULT (datetime('now')),
    actualizada_en       TEXT,
    enviada_en           TEXT,
    envios               INTEGER NOT NULL DEFAULT 0,  -- cuántas veces se envió (reenvíos tras condiciones)
    copia_enviada        TEXT,                        -- JSON con lo que revisa la administración
    decidida_por         INTEGER REFERENCES usuario(id),
    decidida_en          TEXT,
    comentario           TEXT,                        -- condiciones o motivo del rechazo
    UNIQUE (proyecto_id, periodo)
);
CREATE INDEX ix_propuesta_periodo ON propuesta_institucional (periodo, estado);

CREATE TABLE propuesta_objetivo (
    id           INTEGER PRIMARY KEY,
    propuesta_id INTEGER NOT NULL REFERENCES propuesta_institucional(id) ON DELETE CASCADE,
    orden        INTEGER NOT NULL,
    texto        TEXT NOT NULL
);

CREATE TABLE propuesta_actividad_prevista (
    id           INTEGER PRIMARY KEY,
    propuesta_id INTEGER NOT NULL REFERENCES propuesta_institucional(id) ON DELETE CASCADE,
    orden        INTEGER NOT NULL,
    descripcion  TEXT NOT NULL,
    mes_previsto TEXT                                 -- 'AAAA-MM', dentro del periodo
);

-- Historia de cada propuesta: envíos, decisiones, retiro.
CREATE TABLE propuesta_evento (
    id           INTEGER PRIMARY KEY,
    propuesta_id INTEGER NOT NULL REFERENCES propuesta_institucional(id) ON DELETE CASCADE,
    accion       TEXT NOT NULL,     -- enviada, aceptada, condicional, rechazada, retirada
    comentario   TEXT,
    usuario_id   INTEGER REFERENCES usuario(id),
    fecha        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_propuesta_evento ON propuesta_evento (propuesta_id, fecha);

-- Avisos automáticos ya enviados (p. ej., el recordatorio de continuidad), para no repetirlos.
CREATE TABLE aviso_enviado (
    clave TEXT PRIMARY KEY,
    fecha TEXT NOT NULL DEFAULT (datetime('now'))
);
