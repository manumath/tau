-- Motor de encuestas (PLAN §49, etapa 3): satisfacción, clima, bienestar, abandono y, después, seguimiento de
-- egresados (PLAN §50). Una encuesta se arma con preguntas, se abre a un público (estudiantes que cursan o
-- egresados, con filtro opcional por año de ingreso) y cada persona responde con un enlace personal sin cuenta.
--
-- Anónimas: la respuesta NO guarda a qué invitación corresponde (`respuesta.invitacion_id` queda vacío) y las
-- fechas se guardan sin hora; solo se conoce el año de ingreso (`grupo`), que se publica únicamente si hay al
-- menos 5 respuestas en el grupo. Nominales: la respuesta enlaza a su invitación (y con ella a la persona).
--
-- `invitacion_encuesta.token` es el enlace personal. Se guarda tal cual (hace falta reenviarlo en los
-- recordatorios) y se borra al responder y al cerrar la encuesta: solo existe mientras sirve.
CREATE TABLE encuesta (
    id            INTEGER PRIMARY KEY,
    titulo        TEXT NOT NULL,
    descripcion   TEXT,
    tipo          TEXT NOT NULL CHECK (tipo IN ('satisfaccion', 'clima', 'bienestar', 'abandono', 'egresados',
                                                'perfil_egreso', 'otra')),
    anonima       INTEGER NOT NULL CHECK (anonima IN (0, 1)),
    publico       TEXT NOT NULL CHECK (publico IN ('estudiantes', 'egresados')),
    cohorte_desde INTEGER,                       -- año de ingreso (filtro opcional del público)
    cohorte_hasta INTEGER,
    cierra_el     TEXT,                          -- fecha límite (AAAA-MM-DD), opcional
    estado        TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'abierta', 'cerrada')),
    creada_por    INTEGER REFERENCES usuario(id),
    creada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    abierta_en    TEXT,
    cerrada_en    TEXT
);

CREATE TABLE pregunta (
    id          INTEGER PRIMARY KEY,
    encuesta_id INTEGER NOT NULL REFERENCES encuesta(id) ON DELETE CASCADE,
    orden       INTEGER NOT NULL,
    texto       TEXT NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('escala', 'si_no', 'opcion', 'multiple', 'texto')),
    opciones    TEXT,                            -- JSON: lista de textos (opcion y multiple)
    obligatoria INTEGER NOT NULL DEFAULT 1 CHECK (obligatoria IN (0, 1))
);
CREATE INDEX ix_pregunta_encuesta ON pregunta (encuesta_id, orden);

CREATE TABLE invitacion_encuesta (
    id           INTEGER PRIMARY KEY,
    encuesta_id  INTEGER NOT NULL REFERENCES encuesta(id) ON DELETE CASCADE,
    externo_id   INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    email        TEXT NOT NULL,
    grupo        INTEGER,                        -- año de ingreso (cohorte) al invitar
    token        TEXT UNIQUE,                    -- vacío una vez respondida o cerrada la encuesta
    enviada_en   TEXT,
    recordada_en TEXT,
    respondida_en TEXT,                          -- anónimas: solo la fecha
    creada_en    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (encuesta_id, externo_id)
);

CREATE TABLE respuesta (
    id            INTEGER PRIMARY KEY,
    encuesta_id   INTEGER NOT NULL REFERENCES encuesta(id) ON DELETE CASCADE,
    invitacion_id INTEGER REFERENCES invitacion_encuesta(id) ON DELETE SET NULL,   -- vacío en las anónimas
    grupo         INTEGER,
    enviada_en    TEXT NOT NULL                  -- anónimas: solo la fecha
);
CREATE INDEX ix_respuesta_encuesta ON respuesta (encuesta_id);

CREATE TABLE respuesta_item (
    respuesta_id INTEGER NOT NULL REFERENCES respuesta(id) ON DELETE CASCADE,
    pregunta_id  INTEGER NOT NULL REFERENCES pregunta(id) ON DELETE CASCADE,
    valor        TEXT NOT NULL                   -- una fila por valor (varias en «multiple»)
);
CREATE INDEX ix_respuesta_item ON respuesta_item (pregunta_id);
