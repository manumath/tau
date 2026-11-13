-- Equivalencias entre planes de estudio (PLAN §65, etapa 5).
--
-- Al reemplazar un plan por otro (o dos licenciaturas por una, o una por tres), cada asignatura del plan anterior debe
-- tener su equivalente en el nuevo. Como el catálogo de asignaturas lo comparten todos los planes, una asignatura que
-- está en los dos es equivalente por sí sola (misma sigla): solo se registran las que cambian. Una equivalencia es un
-- grupo: varias asignaturas del plan anterior (lado 'origen') equivalen a varias del nuevo (lado 'destino'), una a una
-- o agrupadas. Es solo del catálogo: TAU no guarda materias cursadas ni notas.
CREATE TABLE equivalencia (
    id              INTEGER PRIMARY KEY,
    plan_origen_id  INTEGER NOT NULL REFERENCES plan_estudios(id) ON DELETE CASCADE,
    plan_destino_id INTEGER NOT NULL REFERENCES plan_estudios(id) ON DELETE CASCADE,
    nota            TEXT,
    creado_en       TEXT NOT NULL DEFAULT (datetime('now')),
    creado_por      INTEGER REFERENCES usuario(id),
    CHECK (plan_origen_id <> plan_destino_id)
);
CREATE INDEX ix_equivalencia_destino ON equivalencia (plan_destino_id, plan_origen_id);

CREATE TABLE equivalencia_item (
    equivalencia_id INTEGER NOT NULL REFERENCES equivalencia(id) ON DELETE CASCADE,
    lado            TEXT NOT NULL CHECK (lado IN ('origen', 'destino')),
    asignatura_id   INTEGER NOT NULL REFERENCES asignatura(id),
    PRIMARY KEY (equivalencia_id, lado, asignatura_id)
);
