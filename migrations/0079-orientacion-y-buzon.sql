-- Bienestar y orientación del estudiante (PLAN §67, etapa 9; decisión del 13-nov-2026): preguntas frecuentes, directorio de
-- servicios de apoyo y un buzón de consultas, reclamos y sugerencias. Lo atienden la Dirección de Carrera y la Coordinación
-- académica. Una consulta puede enviarse ANÓNIMA: no se guarda quién la envió (ni la hora, solo el día) y no recibe respuesta
-- personal: se responde publicándola en las preguntas frecuentes.
CREATE TABLE pregunta_frecuente (
    id         INTEGER PRIMARY KEY,
    categoria  TEXT NOT NULL,                       -- p. ej. «Trámites», «Becas», «Grado»
    pregunta   TEXT NOT NULL,
    respuesta  TEXT NOT NULL,
    orden      INTEGER NOT NULL DEFAULT 0,
    publicada  INTEGER NOT NULL DEFAULT 1 CHECK (publicada IN (0, 1)),
    creada_por INTEGER REFERENCES usuario(id),
    creada_en  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE servicio_apoyo (
    id          INTEGER PRIMARY KEY,
    tipo        TEXT NOT NULL CHECK (tipo IN ('bienestar', 'psicologia', 'salud', 'economica', 'academica', 'otro')),
    nombre      TEXT NOT NULL,
    descripcion TEXT,
    contacto    TEXT,
    horario     TEXT,
    enlace      TEXT,
    orden       INTEGER NOT NULL DEFAULT 0,
    activo      INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE consulta (
    id             INTEGER PRIMARY KEY,
    tipo           TEXT NOT NULL CHECK (tipo IN ('consulta', 'reclamo', 'sugerencia')),
    asunto         TEXT NOT NULL,
    texto          TEXT NOT NULL,
    anonima        INTEGER NOT NULL DEFAULT 0 CHECK (anonima IN (0, 1)),
    externo_id     INTEGER REFERENCES persona_externa(id) ON DELETE SET NULL,   -- vacío si es anónima
    estado         TEXT NOT NULL DEFAULT 'recibida' CHECK (estado IN ('recibida', 'en_atencion', 'respondida', 'cerrada')),
    respuesta      TEXT,
    respondida_por INTEGER REFERENCES usuario(id),
    respondida_en  TEXT,
    pregunta_id    INTEGER REFERENCES pregunta_frecuente(id) ON DELETE SET NULL, -- la FAQ en que se publicó la respuesta
    creada_en      TEXT NOT NULL,                  -- anónimas: solo la fecha
    CHECK (anonima = 0 OR externo_id IS NULL)
);
CREATE INDEX ix_consulta_estado ON consulta (estado, creada_en);
CREATE INDEX ix_consulta_externo ON consulta (externo_id);
