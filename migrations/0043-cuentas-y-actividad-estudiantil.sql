-- Cuentas de estudiantes y actividad estudiantil declarada (PLAN §49, etapa 2).
--
-- Una cuenta de estudiante se une a su ficha (`persona_externa`) por `cuenta_estudiante`, no por
-- `persona_externa.usuario_id`: esa columna dice «esta persona externa pasó a ser investigadora» (PLAN §42)
-- y hace desaparecer a la persona de los selectores de externos; un estudiante con cuenta debe seguir
-- pudiendo figurar como tesista o coautor. Las cuentas se crean sin contraseña (`SIN_ACCESO`): se ingresa con
-- un enlace al correo (token de propósito «acceso»).
--
-- `token_acceso.proposito` tiene un CHECK: se recrea la tabla para admitir «acceso» (los enlaces pendientes se
-- conservan).
CREATE TABLE token_acceso_nueva (
    id         INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    token_hash TEXT    NOT NULL UNIQUE,
    proposito  TEXT    NOT NULL CHECK (proposito IN ('recuperar', 'invitacion', 'acceso')),
    expira_en  TEXT    NOT NULL,
    usado_en   TEXT,
    creado_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO token_acceso_nueva (id, usuario_id, token_hash, proposito, expira_en, usado_en, creado_en)
    SELECT id, usuario_id, token_hash, proposito, expira_en, usado_en, creado_en FROM token_acceso;
DROP TABLE token_acceso;
ALTER TABLE token_acceso_nueva RENAME TO token_acceso;
CREATE INDEX ix_token_acceso_usuario ON token_acceso (usuario_id, proposito);

CREATE TABLE cuenta_estudiante (
    externo_id        INTEGER PRIMARY KEY REFERENCES persona_externa(id) ON DELETE CASCADE,
    usuario_id        INTEGER NOT NULL UNIQUE REFERENCES usuario(id) ON DELETE CASCADE,
    consentimiento_en TEXT,                     -- cuándo aceptó el uso de sus datos (vacío = aún no)
    creada_por        INTEGER REFERENCES usuario(id),
    creada_en         TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Lo que el estudiante declara haber hecho (ayudantías, olimpiadas, pasantías…). La Dirección o la
-- Coordinación académica lo verifica; si el estudiante lo edita, vuelve a quedar pendiente.
CREATE TABLE actividad_estudiantil (
    id             INTEGER PRIMARY KEY,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    tipo           TEXT NOT NULL CHECK (tipo IN ('ayudantia', 'olimpiada', 'congreso', 'pasantia', 'beca', 'movilidad',
                                                 'semillero', 'charla', 'voluntariado', 'otra')),
    titulo         TEXT NOT NULL,
    descripcion    TEXT,
    institucion    TEXT,
    fecha_inicio   TEXT NOT NULL,               -- AAAA-MM-DD
    fecha_fin      TEXT,
    estado         TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'verificada', 'observada')),
    observacion    TEXT,                        -- lo que pide corregir quien verifica
    verificado_por INTEGER REFERENCES usuario(id),
    verificado_en  TEXT,
    creado_en      TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);
CREATE INDEX ix_actividad_estudiantil_persona ON actividad_estudiantil (externo_id);
CREATE INDEX ix_actividad_estudiantil_estado ON actividad_estudiantil (estado);
