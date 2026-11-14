-- PLAN §72, etapa 5: cortes de seguimiento del plan de mejora.
-- Un corte (trimestral, anual o bienal) congela el estado, el avance y el semáforo de cada actividad a su fecha, con los
-- textos copiados: el informe del corte se vuelve a imprimir igual aunque después cambien las actividades. La Comisión
-- comenta primero lo que pide atención (vencidas, en riesgo y sin avance desde el corte anterior). Al cerrarlo, su
-- informe queda como evidencia del marco. No cambia ningún dato existente.
CREATE TABLE corte_mejora (
    id            INTEGER PRIMARY KEY,
    marco_id      INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    tipo          TEXT    NOT NULL CHECK (tipo IN ('trimestral', 'anual', 'bienal')),
    fecha         TEXT    NOT NULL,                       -- AAAA-MM-DD: fecha del corte
    estado        TEXT    NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto', 'cerrado')),
    conclusion    TEXT,
    evidencia_id  INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    abierto_por   INTEGER REFERENCES usuario(id),
    abierto_en    TEXT    NOT NULL DEFAULT (datetime('now')),
    cerrado_por   INTEGER REFERENCES usuario(id),
    cerrado_en    TEXT,
    CHECK ((estado = 'cerrado') = (cerrado_en IS NOT NULL))
);
CREATE INDEX ix_corte_mejora_marco ON corte_mejora (marco_id, fecha);

CREATE TABLE corte_actividad (
    id             INTEGER PRIMARY KEY,
    corte_id       INTEGER NOT NULL REFERENCES corte_mejora(id) ON DELETE CASCADE,
    actividad_id   INTEGER REFERENCES actividad_mejora(id) ON DELETE SET NULL,
    accion_codigo  TEXT,
    accion_titulo  TEXT    NOT NULL,
    prioridad      TEXT    NOT NULL,
    codigo         TEXT,
    descripcion    TEXT    NOT NULL,
    responsable    TEXT,
    plazo          TEXT    NOT NULL,
    estado         TEXT    NOT NULL,
    avance         REAL,
    semaforo       TEXT    NOT NULL,
    ultimo_avance  TEXT,
    ultimo_texto   TEXT,
    atencion       TEXT    CHECK (atencion IN ('vencida', 'en_riesgo', 'sin_avance')),
    comentario     TEXT,
    comentado_por  INTEGER REFERENCES usuario(id),
    comentado_en   TEXT,
    UNIQUE (corte_id, actividad_id)
);
CREATE INDEX ix_corte_actividad_corte ON corte_actividad (corte_id, atencion);
