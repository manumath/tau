-- Estudiantes en la investigación (IAC-CINDA 2.3.2, 2.3.4 y 3.6.1 d).
--
-- Los estudiantes y tesistas son personas externas (sin cuenta). Cada periodo de estudios dice en
-- qué nivel y programa estudiaba, desde y hasta qué año, y si se tituló. Con eso se sabe si una
-- persona era estudiante (o ya graduada) en la fecha de cada producto, proyecto o actividad.
CREATE TABLE estudiante (
    id             INTEGER PRIMARY KEY,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    nivel          TEXT NOT NULL CHECK (nivel IN ('licenciatura', 'maestria', 'doctorado')),
    programa       TEXT,                       -- p. ej. «Licenciatura en Matemática»
    del_programa   INTEGER NOT NULL DEFAULT 1 CHECK (del_programa IN (0, 1)),  -- de la Carrera / UMSA
    desde          INTEGER NOT NULL,           -- año de ingreso
    hasta          INTEGER,                    -- año de egreso (vacío = cursando)
    titulado       INTEGER NOT NULL DEFAULT 0 CHECK (titulado IN (0, 1)),
    registrado_por INTEGER REFERENCES usuario(id),
    creado_en      TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (hasta IS NULL OR hasta >= desde)
);
CREATE INDEX ix_estudiante_externo ON estudiante (externo_id);
