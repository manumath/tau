-- Reformas curriculares y estados de los planes de estudio (PLAN §65, etapa 1; decisiones del 12-nov-2026).
--
-- Lo que se revisa cada 10 años es el conjunto de planes, no cada uno: una REFORMA CURRICULAR (hoy, la del 2017,
-- HCU 041/2017) agrupa los planes de sus programas: dos licenciaturas y dos maestrías terminales, y la próxima
-- puede traer uno, dos o tres. Cada plan tiene un ESTADO: en elaboración (borrador, solo lo ven quienes lo elaboran),
-- vigente, en proceso de cierre (sin nuevos ingresos; `vigente_hasta` guarda el año del último ingreso) o cerrado.
-- Solo puede haber un plan vigente por programa.
--
-- Los planes ya cargados quedan agrupados por su nombre («Plan 2017»): vigentes si `vigente_hasta` es nulo y
-- en proceso de cierre si ya tenían año de último ingreso. No se pierde nada. `vigente_desde` sigue siendo obligatorio:
-- un borrador lleva el año de su reforma.
CREATE TABLE reforma_curricular (
    id            INTEGER PRIMARY KEY,
    nombre        TEXT NOT NULL UNIQUE,               -- «Plan 2017»
    resolucion    TEXT,                               -- «HCU 041/2017»
    vigente_desde INTEGER NOT NULL,                   -- año en que rige
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    creado_por    INTEGER REFERENCES usuario(id)
);

ALTER TABLE plan_estudios ADD COLUMN reforma_id INTEGER REFERENCES reforma_curricular(id);
ALTER TABLE plan_estudios ADD COLUMN estado TEXT NOT NULL DEFAULT 'vigente'
    CHECK (estado IN ('elaboracion', 'vigente', 'cierre', 'cerrado'));
ALTER TABLE plan_estudios ADD COLUMN en_vigencia_en  TEXT;       -- cuándo y quién lo puso en vigencia
ALTER TABLE plan_estudios ADD COLUMN en_vigencia_por INTEGER REFERENCES usuario(id);
ALTER TABLE plan_estudios ADD COLUMN cierre_en       TEXT;       -- cuándo pasó a «en proceso de cierre»
ALTER TABLE plan_estudios ADD COLUMN cierre_por      INTEGER REFERENCES usuario(id);
ALTER TABLE plan_estudios ADD COLUMN cerrado_en      TEXT;
ALTER TABLE plan_estudios ADD COLUMN cerrado_por     INTEGER REFERENCES usuario(id);
ALTER TABLE plan_estudios ADD COLUMN motivo_cierre   TEXT;       -- resolución o motivo del cierre

INSERT INTO reforma_curricular (nombre, resolucion, vigente_desde)
    SELECT nombre, MIN(resolucion), MIN(vigente_desde) FROM plan_estudios GROUP BY nombre;
UPDATE plan_estudios SET
    reforma_id = (SELECT r.id FROM reforma_curricular r WHERE r.nombre = plan_estudios.nombre),
    estado = CASE WHEN vigente_hasta IS NULL THEN 'vigente' ELSE 'cierre' END;

CREATE UNIQUE INDEX ux_plan_vigente ON plan_estudios (programa_id) WHERE estado = 'vigente';
CREATE INDEX ix_plan_reforma ON plan_estudios (reforma_id);
