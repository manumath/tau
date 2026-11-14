-- Plan de mejora con actividades, reprogramación y aprobación (PLAN §72, etapa 2; retoma lo postergado en el §61).
--
-- - accion_mejora gana código («A4»), objetivo y eje. La prioridad guardada no cambia (alta, media, baja): se muestra como
--   P1, P2 y P3.
-- - actividad_mejora: lo que el plan del informe pide por actividad (línea base, meta, indicador, responsable, plazo,
--   presupuesto y fuente, medio de verificación y de difusión). El responsable puede ser una persona del sistema o, si no
--   lo es, una unidad en texto (DEAGEC, DTIC…). La línea base y la meta tienen texto y, si son numéricas, valor: con un
--   indicador del SIAC el avance se calcula de la línea base a la meta.
-- - reprogramacion_mejora: el responsable pide un plazo nuevo con su causa y la Dirección de Carrera lo aprueba o lo
--   rechaza (decisión del usuario del 14-nov-2026). Queda el historial de ambas cosas.
-- - avance_accion.actividad_id: el avance se registra en la actividad; la acción suma lo de sus actividades. Los avances
--   anteriores quedan en la acción (actividad_id nulo).
-- - marco_calidad.plan_resolucion y plan_aprobado_en: aprobado el plan, los plazos de las actividades solo cambian por
--   reprogramación.
-- Ningún dato existente cambia: las acciones de antes quedan como acciones sin actividades.
ALTER TABLE accion_mejora ADD COLUMN codigo TEXT;
ALTER TABLE accion_mejora ADD COLUMN objetivo TEXT;
ALTER TABLE accion_mejora ADD COLUMN eje TEXT;

ALTER TABLE marco_calidad ADD COLUMN plan_resolucion TEXT;
ALTER TABLE marco_calidad ADD COLUMN plan_aprobado_en TEXT;          -- AAAA-MM-DD

CREATE TABLE actividad_mejora (
    id                 INTEGER PRIMARY KEY,
    accion_id          INTEGER NOT NULL REFERENCES accion_mejora(id) ON DELETE CASCADE,
    codigo             TEXT,                 -- «4.2»
    descripcion        TEXT    NOT NULL,
    linea_base         TEXT,
    linea_base_valor   REAL,
    meta               TEXT,
    meta_valor         REAL,
    indicador_id       INTEGER REFERENCES indicador_calidad(id) ON DELETE SET NULL,
    responsable_id     INTEGER REFERENCES usuario(id),
    unidad_responsable TEXT,                 -- cuando no es una persona del sistema, o además de ella
    inicio             TEXT,                 -- AAAA-MM-DD
    plazo              TEXT    NOT NULL,     -- AAAA-MM-DD
    presupuesto        REAL    CHECK (presupuesto IS NULL OR presupuesto >= 0),   -- en bolivianos
    fuente             TEXT,                 -- fuente del presupuesto
    verificacion       TEXT,                 -- medio de verificación
    difusion           TEXT,                 -- medio de difusión
    estado             TEXT    NOT NULL DEFAULT 'pendiente'
                       CHECK (estado IN ('pendiente', 'en_curso', 'cumplida', 'cancelada')),
    cumplida_en        TEXT,
    motivo_cancelacion TEXT,
    creada_por         INTEGER REFERENCES usuario(id),
    creada_en          TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK ((estado = 'cumplida') = (cumplida_en IS NOT NULL)),
    CHECK ((estado = 'cancelada') = (motivo_cancelacion IS NOT NULL)),
    CHECK (inicio IS NULL OR inicio <= plazo)
);
CREATE INDEX ix_actividad_mejora_accion ON actividad_mejora (accion_id);
CREATE INDEX ix_actividad_mejora_responsable ON actividad_mejora (responsable_id, estado);
CREATE INDEX ix_actividad_mejora_plazo ON actividad_mejora (estado, plazo);

CREATE TABLE reprogramacion_mejora (
    id             INTEGER PRIMARY KEY,
    actividad_id   INTEGER NOT NULL REFERENCES actividad_mejora(id) ON DELETE CASCADE,
    plazo_anterior TEXT    NOT NULL,
    plazo_nuevo    TEXT    NOT NULL,
    causa          TEXT    NOT NULL,
    evidencia_id   INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    estado         TEXT    NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aprobada', 'rechazada')),
    solicitada_por INTEGER REFERENCES usuario(id),
    solicitada_en  TEXT    NOT NULL DEFAULT (datetime('now')),
    resuelta_por   INTEGER REFERENCES usuario(id),
    resuelta_en    TEXT,
    respuesta      TEXT,                     -- motivo del rechazo o nota de la aprobación
    CHECK ((estado = 'pendiente') = (resuelta_en IS NULL)),
    CHECK (estado <> 'rechazada' OR respuesta IS NOT NULL)
);
CREATE INDEX ix_reprogramacion_mejora_actividad ON reprogramacion_mejora (actividad_id, estado);

ALTER TABLE avance_accion ADD COLUMN actividad_id INTEGER REFERENCES actividad_mejora(id) ON DELETE CASCADE;
CREATE INDEX ix_avance_accion_actividad ON avance_accion (actividad_id);
