-- Oportunidades para estudiantes y egresados (PLAN §67, etapa 4): becas, movilidad, pasantías, ayudantías de investigación y
-- empleo, con su postulación y decisión. Las publica la Dirección de Carrera o la Coordinación académica (el empleo, a
-- nombre de un empleador registrado, sin cuentas nuevas) y, las ayudantías de investigación, el responsable del proyecto.
CREATE TABLE oportunidad (
    id           INTEGER PRIMARY KEY,
    tipo         TEXT NOT NULL CHECK (tipo IN ('beca', 'movilidad', 'pasantia', 'ayudantia', 'empleo')),
    titulo       TEXT NOT NULL,
    descripcion  TEXT,
    requisitos   TEXT,
    organizacion TEXT,                                  -- quien ofrece (institución, empleador, proyecto)
    empleador_id INTEGER REFERENCES empleador(id) ON DELETE SET NULL,
    proyecto_id  INTEGER REFERENCES proyecto(id) ON DELETE SET NULL,   -- ayudantías de investigación
    plazas       INTEGER CHECK (plazas IS NULL OR plazas > 0),
    cierre       TEXT,                                  -- 'AAAA-MM-DD'; vacío = abierta hasta que se cierre
    enlace       TEXT,
    contacto     TEXT,
    para         TEXT NOT NULL DEFAULT 'estudiantes' CHECK (para IN ('estudiantes', 'egresados', 'todos')),
    estado       TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'publicada', 'cerrada')),
    creada_por   INTEGER NOT NULL REFERENCES usuario(id),
    creada_en    TEXT NOT NULL DEFAULT (datetime('now')),
    publicada_en TEXT
);
CREATE INDEX ix_oportunidad_estado ON oportunidad (estado, cierre);

CREATE TABLE postulacion_oportunidad (
    id             INTEGER PRIMARY KEY,
    oportunidad_id INTEGER NOT NULL REFERENCES oportunidad(id) ON DELETE CASCADE,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    mensaje        TEXT,
    estado         TEXT NOT NULL DEFAULT 'postulada'
                   CHECK (estado IN ('postulada', 'preseleccionada', 'seleccionada', 'no_seleccionada', 'retirada')),
    nota           TEXT,                                -- lo que dice quien decide
    creada_en      TEXT NOT NULL DEFAULT (datetime('now')),
    decidida_en    TEXT,
    decidida_por   INTEGER REFERENCES usuario(id),
    UNIQUE (oportunidad_id, externo_id)
);
