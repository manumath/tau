-- Duración y ciclos de cada plan (PLAN §65, etapa 3).
--
-- `duracion_semestres` permite comprobar que cada semestre del plan tiene asignaturas (antes se deducía del último
-- semestre con asignaturas). `plan_ciclo` define los ciclos (básico, intermedio…) como rangos de semestres: el ciclo de
-- cada asignatura se deduce del semestre, y deja de ser un texto libre que cada fila escribe a su manera.
-- Se migra lo que había: la duración es el último semestre con asignaturas y los ciclos, el rango de semestres en
-- que ya aparecía cada nombre.
ALTER TABLE plan_estudios ADD COLUMN duracion_semestres INTEGER;
UPDATE plan_estudios SET duracion_semestres =
    (SELECT MAX(semestre) FROM plan_asignatura WHERE plan_id = plan_estudios.id);

CREATE TABLE plan_ciclo (
    id             INTEGER PRIMARY KEY,
    plan_id        INTEGER NOT NULL REFERENCES plan_estudios(id) ON DELETE CASCADE,
    nombre         TEXT NOT NULL,
    semestre_desde INTEGER NOT NULL,
    semestre_hasta INTEGER NOT NULL,
    CHECK (semestre_hasta >= semestre_desde),
    UNIQUE (plan_id, nombre)
);
INSERT INTO plan_ciclo (plan_id, nombre, semestre_desde, semestre_hasta)
    SELECT plan_id, ciclo, MIN(semestre), MAX(semestre) FROM plan_asignatura
    WHERE ciclo IS NOT NULL AND semestre IS NOT NULL GROUP BY plan_id, ciclo;
