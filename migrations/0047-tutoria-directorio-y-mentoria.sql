-- Tutoría, directorio de egresados y mentoría (PLAN §49 y §50, etapa 5).
--
-- Tutoría: la Dirección de Carrera o la Coordinación académica asigna a cada estudiante un tutor (docente con vínculo).
-- Una asignación vigente por estudiante. Las reuniones son confidenciales: las ve su autor (el tutor) y la Dirección de
-- Carrera (que queda en la auditoría); el estudiante no las ve y el Comité solo ve cifras agregadas.
--
-- Directorio: el egresado figura solo si lo acepta (`visible`, con `consentimiento_en`), y solo dentro del sistema (lo ven
-- estudiantes con cuenta y el personal). Mentoría: el estudiante pide, el egresado acepta o no; el correo de cada uno
-- solo se comparte al aceptar.
CREATE TABLE tutoria_asignacion (
    id           INTEGER PRIMARY KEY,
    externo_id   INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    tutor_id     INTEGER NOT NULL REFERENCES usuario(id),
    desde        TEXT NOT NULL,
    hasta        TEXT,                              -- vacío = vigente
    asignado_por INTEGER REFERENCES usuario(id),
    creado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (hasta IS NULL OR hasta >= desde)
);
CREATE UNIQUE INDEX ux_tutoria_vigente ON tutoria_asignacion (externo_id) WHERE hasta IS NULL;
CREATE INDEX ix_tutoria_tutor ON tutoria_asignacion (tutor_id) WHERE hasta IS NULL;

CREATE TABLE tutoria_reunion (
    id             INTEGER PRIMARY KEY,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    tutor_id       INTEGER NOT NULL REFERENCES usuario(id),
    fecha          TEXT NOT NULL,
    modalidad      TEXT NOT NULL DEFAULT 'presencial' CHECK (modalidad IN ('presencial', 'virtual')),
    tema           TEXT NOT NULL CHECK (tema IN ('academico', 'economico', 'salud', 'vocacional', 'convivencia', 'otro')),
    resumen        TEXT,                            -- confidencial
    derivacion     TEXT NOT NULL DEFAULT 'ninguna' CHECK (derivacion IN ('ninguna', 'bienestar', 'psicologia', 'academica',
                                                                         'economica', 'salud', 'otra')),
    acuerdos       TEXT,
    creado_en      TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_tutoria_reunion_persona ON tutoria_reunion (externo_id, fecha);

CREATE TABLE perfil_egresado (
    externo_id        INTEGER PRIMARY KEY REFERENCES persona_externa(id) ON DELETE CASCADE,
    invitado_en       TEXT,
    visible           INTEGER NOT NULL DEFAULT 0 CHECK (visible IN (0, 1)),
    consentimiento_en TEXT,
    ocupacion         TEXT,
    institucion       TEXT,
    ciudad_pais       TEXT,
    areas             TEXT,                         -- intereses y áreas de trabajo, texto libre
    ofrece            TEXT NOT NULL DEFAULT '[]',   -- JSON: charla, mentoria, pasantia, posgrado, empleo
    detalle           TEXT,
    actualizado_en    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE solicitud_mentoria (
    id            INTEGER PRIMARY KEY,
    de_externo_id INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    a_externo_id  INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    tipo          TEXT NOT NULL CHECK (tipo IN ('mentoria', 'charla', 'pasantia', 'posgrado', 'empleo', 'otra')),
    mensaje       TEXT NOT NULL,
    estado        TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aceptada', 'rechazada')),
    creada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    respondida_en TEXT
);
CREATE INDEX ix_solicitud_destino ON solicitud_mentoria (a_externo_id, estado);
CREATE INDEX ix_solicitud_origen ON solicitud_mentoria (de_externo_id, estado);
