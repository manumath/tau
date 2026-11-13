-- Menciones de un plan de estudios (PLAN §65, etapa 4; decisión del 12-nov-2026).
--
-- Una mención es un itinerario dentro de un plan: un énfasis de la misma titulación (si los títulos difieren, son
-- programas distintos y no menciones). Define qué asignaturas del plan le son propias (obligatorias de la mención u
-- optativas), el semestre en que se elige y lo mínimo que se pide: cuántas de sus asignaturas y cuántos créditos (o,
-- en un plan por horas, cuántas horas del semestre completo: horas semanales por las semanas del semestre). Lo que no
-- pertenece a ninguna mención es el tronco común. Hoy no hay menciones cargadas.
CREATE TABLE mencion (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plan_estudios(id) ON DELETE CASCADE,
    nombre             TEXT NOT NULL,
    descripcion        TEXT,
    semestre_eleccion  INTEGER,
    minimo_asignaturas INTEGER,
    minimo_medida      INTEGER,
    creado_en          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (plan_id, nombre)
);

CREATE TABLE mencion_asignatura (
    mencion_id         INTEGER NOT NULL REFERENCES mencion(id) ON DELETE CASCADE,
    plan_asignatura_id INTEGER NOT NULL REFERENCES plan_asignatura(id) ON DELETE CASCADE,
    obligatoria        INTEGER NOT NULL DEFAULT 1 CHECK (obligatoria IN (0, 1)),
    PRIMARY KEY (mencion_id, plan_asignatura_id)
);
CREATE INDEX ix_mencion_asignatura_pa ON mencion_asignatura (plan_asignatura_id);
