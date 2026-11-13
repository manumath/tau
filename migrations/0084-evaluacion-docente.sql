-- Evaluación docente con transparencia (PLAN §68, etapa 5).
--
-- Una evaluación por gestión: la Dirección de Carrera la crea con su instrumento (criterios congelados al anunciarla), la anuncia con
-- anticipación, la abre y la cierra. Los estudiantes inscritos (según la lista de curso) responden una vez por paralelo y de
-- forma anónima: la participación NO se enlaza con la respuesta (tabla sin rowid, sin hora) y la respuesta no tiene hora ni
-- autor. Los resultados de un docente solo se muestran desde 5 respuestas; el docente ve los suyos, puede agregar su contexto y ve
-- quién los consultó. No hay respuestas abiertas.
CREATE TABLE evaluacion_docente (
    id          INTEGER PRIMARY KEY,
    gestion_id  INTEGER NOT NULL UNIQUE REFERENCES gestion_academica(id) ON DELETE CASCADE,
    estado      TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'anunciada', 'abierta', 'cerrada')),
    abre_el     TEXT NOT NULL,                      -- fecha
    cierra_el   TEXT NOT NULL,                      -- fecha
    criterios   TEXT NOT NULL,                      -- JSON [[clave, texto], …]: el instrumento que se anunció
    anunciada_en TEXT,
    abierta_en  TEXT,
    cerrada_en  TEXT,
    retorno     TEXT,                               -- lo que la Carrera hizo con los resultados (se publica a los estudiantes)
    retorno_publicado_en TEXT,
    creada_por  INTEGER REFERENCES usuario(id),
    creada_en   TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (cierra_el >= abre_el)
);

-- Quién ya evaluó cada paralelo. Sin hora y sin rowid: no se puede cruzar con el orden de las respuestas.
CREATE TABLE evaluacion_participacion (
    evaluacion_id INTEGER NOT NULL REFERENCES evaluacion_docente(id) ON DELETE CASCADE,
    oferta_id     INTEGER NOT NULL REFERENCES oferta(id) ON DELETE CASCADE,
    externo_id    INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    PRIMARY KEY (evaluacion_id, oferta_id, externo_id)
) WITHOUT ROWID;

CREATE TABLE evaluacion_respuesta (
    id            INTEGER PRIMARY KEY,
    evaluacion_id INTEGER NOT NULL REFERENCES evaluacion_docente(id) ON DELETE CASCADE,
    oferta_id     INTEGER NOT NULL REFERENCES oferta(id) ON DELETE CASCADE
);
CREATE INDEX ix_evaluacion_respuesta ON evaluacion_respuesta (evaluacion_id, oferta_id);

CREATE TABLE evaluacion_valor (
    respuesta_id INTEGER NOT NULL REFERENCES evaluacion_respuesta(id) ON DELETE CASCADE,
    criterio     TEXT NOT NULL,
    valor        INTEGER NOT NULL CHECK (valor BETWEEN 1 AND 5),
    PRIMARY KEY (respuesta_id, criterio)
);

-- Contexto que el docente agrega a sus resultados (lo ve la Dirección junto con ellos).
CREATE TABLE evaluacion_contexto (
    evaluacion_id  INTEGER NOT NULL REFERENCES evaluacion_docente(id) ON DELETE CASCADE,
    usuario_id     INTEGER NOT NULL REFERENCES usuario(id),
    texto          TEXT NOT NULL,
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (evaluacion_id, usuario_id)
);

-- Bitácora que ve el propio docente: quién consultó sus resultados y cuándo.
CREATE TABLE evaluacion_consulta (
    id            INTEGER PRIMARY KEY,
    evaluacion_id INTEGER NOT NULL REFERENCES evaluacion_docente(id) ON DELETE CASCADE,
    docente_id    INTEGER NOT NULL REFERENCES usuario(id),
    consultor_id  INTEGER NOT NULL REFERENCES usuario(id),
    consultada_en TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_evaluacion_consulta ON evaluacion_consulta (evaluacion_id, docente_id);
