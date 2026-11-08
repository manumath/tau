-- Áreas de investigación y catálogo oficial de líneas (PLAN §60, 8-nov-2026).
-- Las líneas se agrupan en áreas (Álgebra, Geometría y Topología, Análisis, Matemática Aplicada, Educación
-- Matemática). La Dirección del Instituto mantiene áreas y líneas desde /admin/lineas.
-- Se cargan las líneas oficiales: las que ya existían con el mismo nombre (sin distinguir mayúsculas) solo reciben
-- su área; las demás se agregan. Las líneas anteriores que no figuran en la lista oficial no se tocan: quedan sin
-- área, vigentes, para que la Dirección les ponga fecha de término o un área (es su decisión, no de la migración).

CREATE TABLE area_investigacion (
    id             INTEGER PRIMARY KEY,
    nombre         TEXT NOT NULL,
    orden          INTEGER NOT NULL DEFAULT 0,
    creado_en      TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT
);
CREATE UNIQUE INDEX ux_area_investigacion_nombre ON area_investigacion (lower(nombre));

ALTER TABLE linea_investigacion ADD COLUMN area_id INTEGER REFERENCES area_investigacion(id);
CREATE INDEX ix_linea_area ON linea_investigacion (area_id);

INSERT INTO area_investigacion (nombre, orden) VALUES
    ('Álgebra', 1), ('Geometría y Topología', 2), ('Análisis', 3), ('Matemática Aplicada', 4),
    ('Educación Matemática', 5);

CREATE TEMP TABLE _oficial (area TEXT, nombre TEXT, orden INTEGER);
INSERT INTO _oficial VALUES
    ('Álgebra', 'Estructuras algebraicas ordenadas', 1),
    ('Álgebra', 'Grupos finitos', 2),
    ('Álgebra', 'Problemas inversos de autovalores', 3),
    ('Geometría y Topología', 'Teoría geométrica de control', 4),
    ('Geometría y Topología', 'Topologías finitas y aplicaciones a otras áreas científicas', 5),
    ('Geometría y Topología', 'Geometría diferencial', 6),
    ('Análisis', 'Teoría de distribuciones en el contexto de las EDP', 7),
    ('Análisis', 'Teoría ergódica', 8),
    ('Análisis', 'Análisis intervalar', 9),
    ('Matemática Aplicada', 'Optimización matemática', 10),
    ('Matemática Aplicada', 'Matemática aplicada y análisis de datos', 11),
    ('Matemática Aplicada', 'Teoría de control. Modelos aplicados a la biología', 12),
    ('Matemática Aplicada', 'Sistemas dinámicos', 13),
    ('Matemática Aplicada', 'Teoría de grafos finitos y aplicaciones a otras áreas científicas', 14),
    ('Educación Matemática', 'Educación matemática: Teoría de la Respuesta al Ítem', 15);

-- Las que ya existían: área y orden oficial (el nombre se conserva tal cual).
UPDATE linea_investigacion SET
    area_id = (SELECT a.id FROM _oficial o JOIN area_investigacion a ON a.nombre = o.area
               WHERE lower(o.nombre) = lower(linea_investigacion.nombre)),
    orden = (SELECT o.orden FROM _oficial o WHERE lower(o.nombre) = lower(linea_investigacion.nombre))
WHERE lower(nombre) IN (SELECT lower(nombre) FROM _oficial);

-- Las nuevas.
INSERT INTO linea_investigacion (nombre, area_id, orden)
SELECT o.nombre, a.id, o.orden FROM _oficial o JOIN area_investigacion a ON a.nombre = o.area
WHERE lower(o.nombre) NOT IN (SELECT lower(nombre) FROM linea_investigacion);

-- Las anteriores sin área van al final, en su orden.
UPDATE linea_investigacion SET orden = 100 + orden WHERE area_id IS NULL;

DROP TABLE _oficial;
