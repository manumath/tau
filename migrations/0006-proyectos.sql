-- Fase 4: proyectos, participantes y vínculo (con aprobación) de actividades y productos.

CREATE TABLE proyecto (
    id                    INTEGER PRIMARY KEY,
    codigo                TEXT UNIQUE,          -- código de la agencia (p. ej. FONDECYT 1260001)
    nombre                TEXT NOT NULL,
    descripcion           TEXT,
    objetivo_general      TEXT,
    fuente_financiamiento TEXT,
    monto                 INTEGER,              -- en unidades de `moneda`, sin decimales
    moneda                TEXT NOT NULL DEFAULT 'CLP',
    fecha_inicio          TEXT,
    fecha_fin             TEXT,
    estado                TEXT NOT NULL DEFAULT 'vigente'
                          CHECK (estado IN ('formulacion', 'vigente', 'finalizado')),
    creado_por            INTEGER NOT NULL REFERENCES usuario(id),
    creado_en             TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en        TEXT,
    CHECK (fecha_fin IS NULL OR fecha_inicio IS NULL OR fecha_fin >= fecha_inicio)
);

CREATE TABLE proyecto_objetivo (
    id          INTEGER PRIMARY KEY,
    proyecto_id INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    orden       INTEGER NOT NULL,
    texto       TEXT    NOT NULL
);
CREATE INDEX ix_proyecto_objetivo ON proyecto_objetivo (proyecto_id, orden);

CREATE TABLE proyecto_participante (
    id              INTEGER PRIMARY KEY,
    proyecto_id     INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    investigador_id INTEGER REFERENCES usuario(id),
    externo_id      INTEGER REFERENCES persona_externa(id),
    rol             TEXT NOT NULL CHECK (rol IN ('responsable', 'co_responsable', 'co_investigador',
                                                 'postdoc', 'tesista', 'colaborador')),
    fecha_desde     TEXT,
    fecha_hasta     TEXT,                       -- NULL = vigente
    CHECK ((investigador_id IS NULL) <> (externo_id IS NULL)),
    UNIQUE (proyecto_id, investigador_id),
    UNIQUE (proyecto_id, externo_id)
);
CREATE INDEX ix_proyecto_participante_inv ON proyecto_participante (investigador_id);

-- Vínculos con aprobación. Lo propone un participante; lo aprueba o rechaza un responsable.
CREATE TABLE actividad_proyecto (
    actividad_id                INTEGER NOT NULL REFERENCES actividad(id) ON DELETE CASCADE,
    proyecto_id                 INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    estado                      TEXT NOT NULL DEFAULT 'pendiente'
                                CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    responsable_participante_id INTEGER REFERENCES proyecto_participante(id) ON DELETE SET NULL,
    propuesto_por               INTEGER NOT NULL REFERENCES usuario(id),
    propuesto_en                TEXT NOT NULL DEFAULT (datetime('now')),
    revisado_por                INTEGER REFERENCES usuario(id),
    revisado_en                 TEXT,
    comentario                  TEXT,
    PRIMARY KEY (actividad_id, proyecto_id)
);
CREATE INDEX ix_actividad_proyecto_estado ON actividad_proyecto (proyecto_id, estado);

CREATE TABLE producto_proyecto (
    producto_id   INTEGER NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    proyecto_id   INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    estado        TEXT NOT NULL DEFAULT 'pendiente'
                  CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    propuesto_por INTEGER NOT NULL REFERENCES usuario(id),
    propuesto_en  TEXT NOT NULL DEFAULT (datetime('now')),
    revisado_por  INTEGER REFERENCES usuario(id),
    revisado_en   TEXT,
    comentario    TEXT,
    PRIMARY KEY (producto_id, proyecto_id)
);
CREATE INDEX ix_producto_proyecto_estado ON producto_proyecto (proyecto_id, estado);
