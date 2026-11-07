-- Cifras de los indicadores del marco de calidad (PLAN §57, etapa 3).
--
-- - valor_indicador: lo que se registra a mano para un indicador manual, por año.
-- - valor_automatico: la última cifra calculada en el año de los indicadores automáticos que solo se pueden medir «a hoy»
--   (cobertura de la tutoría, observaciones pendientes…). El mantenimiento la guarda una vez al día; al terminar el año
--   queda la del último día, que es la que se usa para ese año.
-- - cierre_calidad y valor_cierre: al cerrar un año, sus cifras y metas se congelan, para que un informe ya entregado no
--   cambie si después se corrigen los datos. Se puede reabrir (queda en la auditoría).
CREATE TABLE valor_indicador (
    id             INTEGER PRIMARY KEY,
    indicador_id   INTEGER NOT NULL REFERENCES indicador_calidad(id) ON DELETE CASCADE,
    anio           INTEGER NOT NULL CHECK (anio BETWEEN 2000 AND 2100),
    valor          REAL    NOT NULL,
    n              INTEGER CHECK (n IS NULL OR n >= 0),   -- base del cálculo (respuestas, personas…), si la hay
    fuente         TEXT,                                  -- de dónde sale: acta, encuesta, registro…
    nota           TEXT,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (indicador_id, anio)
);

CREATE TABLE valor_automatico (
    indicador_id INTEGER NOT NULL REFERENCES indicador_calidad(id) ON DELETE CASCADE,
    anio         INTEGER NOT NULL,
    valor        REAL,
    n            INTEGER,
    detalle      TEXT,
    calculado_en TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (indicador_id, anio)
);

CREATE TABLE cierre_calidad (
    id         INTEGER PRIMARY KEY,
    marco_id   INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    anio       INTEGER NOT NULL,
    cerrado_por INTEGER REFERENCES usuario(id),
    cerrado_en TEXT    NOT NULL DEFAULT (datetime('now')),
    nota       TEXT,
    UNIQUE (marco_id, anio)
);

CREATE TABLE valor_cierre (
    cierre_id    INTEGER NOT NULL REFERENCES cierre_calidad(id) ON DELETE CASCADE,
    indicador_id INTEGER NOT NULL REFERENCES indicador_calidad(id) ON DELETE CASCADE,
    valor        REAL,
    n            INTEGER,
    detalle      TEXT,
    meta         REAL,
    PRIMARY KEY (cierre_id, indicador_id)
);
