-- Fase 3, pasos 3.2 y 3.3 (PLAN.md, sección 24): gestiones académicas, oferta de asignaturas y
-- asignación docente.
--
-- Gestión: año y tipo (I, INV, II, VER). El código («I-2026», «VER-2026») se arma al mostrarla; el
-- orden sale de las fechas. VER-2026 se dicta en enero de 2027 (se cuenta con la gestión anterior).
CREATE TABLE gestion_academica (
    id           INTEGER PRIMARY KEY,
    anio         INTEGER NOT NULL,
    tipo         TEXT NOT NULL CHECK (tipo IN ('I', 'INV', 'II', 'VER')),
    fecha_inicio TEXT NOT NULL,
    fecha_fin    TEXT NOT NULL,
    UNIQUE (anio, tipo),
    CHECK (fecha_fin >= fecha_inicio)
);

-- Oferta: una asignatura de la Carrera dictada en una gestión, por paralelo. Sirve a todos los
-- planes que incluyen la asignatura (la sigla es la misma).
CREATE TABLE oferta (
    id            INTEGER PRIMARY KEY,
    gestion_id    INTEGER NOT NULL REFERENCES gestion_academica(id),
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id),
    paralelo      TEXT NOT NULL DEFAULT 'A',
    inscritos     INTEGER CHECK (inscritos IS NULL OR inscritos >= 0),
    creado_por    INTEGER REFERENCES usuario(id),
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (gestion_id, asignatura_id, paralelo)
);

-- Asignación docente: quién dicta un paralelo y con cuántas horas semanales.
CREATE TABLE oferta_docente (
    id              INTEGER PRIMARY KEY,
    oferta_id       INTEGER NOT NULL REFERENCES oferta(id) ON DELETE CASCADE,
    usuario_id      INTEGER NOT NULL REFERENCES usuario(id),
    rol             TEXT NOT NULL DEFAULT 'titular' CHECK (rol IN ('titular', 'auxiliar')),
    horas_semanales INTEGER NOT NULL CHECK (horas_semanales BETWEEN 1 AND 40),
    UNIQUE (oferta_id, usuario_id)
);
CREATE INDEX ix_oferta_docente_usuario ON oferta_docente (usuario_id);
