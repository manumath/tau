-- Resultado y designación de las auxiliaturas (PLAN §70, etapa 5): arts. 6, 13, 22, 23, 25, 26 y 27 del reglamento de 2023.
--
-- Invitaciones: si la asignatura no se cubrió tras dos convocatorias, se invita primero a quienes obtuvieron 51 a 55 puntos y, si no
-- aceptan, a los mejores estudiantes de la materia (los da Kardex: TAU solo registra a quién se invitó y qué respondió). Designaciones: un
-- auxiliar titular o invitado por plaza, con los documentos que se piden a los ganadores en 72 horas y el memorándum. La convocatoria
-- guarda el informe final de la comisión y las resoluciones de resultados, y la documentación que se entrega a Bienestar Social.
CREATE TABLE invitacion_auxiliatura (
    id             INTEGER PRIMARY KEY,
    item_id        INTEGER NOT NULL REFERENCES item_auxiliatura(id) ON DELETE CASCADE,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id),
    origen         TEXT NOT NULL CHECK (origen IN ('postulante', 'mejor_estudiante')),
    orden          INTEGER NOT NULL,
    puntaje        REAL,                      -- total del concurso (solo los postulantes)
    nota           TEXT,                      -- de dónde sale la invitación (p. ej. el promedio que certifica Kardex)
    estado         TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aceptada', 'rechazada')),
    creada_en      TEXT NOT NULL DEFAULT (datetime('now')),
    respondida_en  TEXT,
    registrada_por INTEGER REFERENCES usuario(id),
    UNIQUE (item_id, externo_id)
);
CREATE TABLE designacion_auxiliatura (
    id             INTEGER PRIMARY KEY,
    item_id        INTEGER NOT NULL REFERENCES item_auxiliatura(id) ON DELETE CASCADE,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id),
    categoria      TEXT NOT NULL CHECK (categoria IN ('titular', 'invitado')),
    postulacion_id INTEGER REFERENCES postulacion_auxiliatura(id) ON DELETE SET NULL,
    invitacion_id  INTEGER REFERENCES invitacion_auxiliatura(id) ON DELETE SET NULL,
    cert_deudas    TEXT,                      -- fechas en que se recibieron los documentos de los ganadores (art. 23)
    cert_procesos  TEXT,
    sigep          TEXT,
    memorandum     TEXT,                      -- número del memorándum de designación (arts. 25 y 26)
    memorandum_fecha TEXT,
    inicio         TEXT,
    fin            TEXT,
    creada_en      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (item_id, externo_id)
);
ALTER TABLE convocatoria_auxiliatura ADD COLUMN informe_final_en TEXT;            -- cuándo la comisión entregó su informe final (art. 22)
ALTER TABLE convocatoria_auxiliatura ADD COLUMN resolucion_resultados TEXT;       -- Consejo de Carrera: aprueba los resultados
ALTER TABLE convocatoria_auxiliatura ADD COLUMN resolucion_resultados_hcf TEXT;   -- Consejo Facultativo: homologa
CREATE TABLE documentacion_auxiliatura (
    convocatoria_id INTEGER NOT NULL REFERENCES convocatoria_auxiliatura(id) ON DELETE CASCADE,
    clave           TEXT NOT NULL CHECK (clave IN ('res_hcf_convocatoria', 'res_hcc_nomina', 'res_hcf_homologacion', 'memorandums',
                                                   'formularios', 'requisitos')),
    entregada_en    TEXT NOT NULL,            -- fecha en que la Dirección de Carrera la entregó a Bienestar Social (art. 27)
    registrada_por  INTEGER REFERENCES usuario(id),
    PRIMARY KEY (convocatoria_id, clave)
);
