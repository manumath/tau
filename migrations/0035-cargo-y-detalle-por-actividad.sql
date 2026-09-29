-- Cargo y «unidad o grupo» calculados (PLAN.md, sección 27).
--
-- 1. El detalle de la carga horaria pasa a registrarse por actividad (investigación, extensión y
--    servicios, gestión, otras): «unidad o grupo» del perfil muestra el de extensión y el de gestión.
--    El detalle único que había se asigna a la actividad si solo una (fuera de docencia) tenía
--    horas; si no, pasa a la nota del periodo para no perderlo.
-- 2. El cargo y la unidad o grupo ya no se escriben en el perfil: se calculan del vínculo (carga de
--    investigación) y de los proyectos. Se quitan las columnas investigador.cargo y .unidad.

ALTER TABLE vinculo ADD COLUMN detalle_investigacion TEXT;
ALTER TABLE vinculo ADD COLUMN detalle_extension TEXT;
ALTER TABLE vinculo ADD COLUMN detalle_gestion TEXT;
ALTER TABLE vinculo ADD COLUMN detalle_otras TEXT;

UPDATE vinculo SET detalle_investigacion = carga_detalle
WHERE carga_detalle IS NOT NULL AND carga_investigacion > 0 AND carga_extension = 0 AND carga_gestion = 0
  AND carga_otras = 0;
UPDATE vinculo SET detalle_extension = carga_detalle
WHERE carga_detalle IS NOT NULL AND carga_extension > 0 AND carga_investigacion = 0 AND carga_gestion = 0
  AND carga_otras = 0;
UPDATE vinculo SET detalle_gestion = carga_detalle
WHERE carga_detalle IS NOT NULL AND carga_gestion > 0 AND carga_investigacion = 0 AND carga_extension = 0
  AND carga_otras = 0;
UPDATE vinculo SET detalle_otras = carga_detalle
WHERE carga_detalle IS NOT NULL AND carga_otras > 0 AND carga_investigacion = 0 AND carga_extension = 0
  AND carga_gestion = 0;
UPDATE vinculo SET nota = TRIM(COALESCE(nota || ' · ', '') || 'Carga: ' || carga_detalle)
WHERE carga_detalle IS NOT NULL AND detalle_investigacion IS NULL AND detalle_extension IS NULL
  AND detalle_gestion IS NULL AND detalle_otras IS NULL;

ALTER TABLE vinculo DROP COLUMN carga_detalle;
ALTER TABLE investigador DROP COLUMN cargo;
ALTER TABLE investigador DROP COLUMN unidad;
