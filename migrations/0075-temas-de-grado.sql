-- Banco de temas de grado (PLAN §67, etapa 5): los docentes publican temas de tesis o proyecto de grado y el estudiante pide
-- tutor sobre un tema. Si el docente acepta, el estudiante empieza su perfil con ese título y ese tutor.
CREATE TABLE tema_grado (
    id           INTEGER PRIMARY KEY,
    docente_id   INTEGER NOT NULL REFERENCES usuario(id),
    titulo       TEXT NOT NULL,
    descripcion  TEXT,
    requisitos   TEXT,                                -- conocimientos previos que conviene tener
    linea_id     INTEGER REFERENCES linea_investigacion(id) ON DELETE SET NULL,
    modalidad    TEXT NOT NULL DEFAULT 'cualquiera' CHECK (modalidad IN ('proyecto_grado', 'tesis', 'cualquiera')),
    cupos        INTEGER NOT NULL DEFAULT 1 CHECK (cupos > 0),
    estado       TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'publicado', 'retirado')),
    creado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    publicado_en TEXT
);
CREATE INDEX ix_tema_grado_estado ON tema_grado (estado, docente_id);

CREATE TABLE solicitud_tema (
    id            INTEGER PRIMARY KEY,
    tema_id       INTEGER NOT NULL REFERENCES tema_grado(id) ON DELETE CASCADE,
    externo_id    INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    mensaje       TEXT,
    estado        TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aceptada', 'rechazada', 'retirada')),
    respuesta     TEXT,
    creada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    respondida_en TEXT,
    UNIQUE (tema_id, externo_id)
);
