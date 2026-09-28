-- Dependencia única: el vínculo de cada persona es con la Carrera de Matemática (CMAT), de la que el
-- Instituto (IIMAT) forma parte. Solo la Dirección de Carrera define la categoría y el vínculo
-- (cambios, término, carga contratada); la Dirección del Instituto gestiona los proyectos.
--
-- Hasta ahora se llevaban periodos separados con el Instituto y con la Carrera. Se unen así:
--   1. los periodos con el Instituto que se superponen con alguno con la Carrera se descartan (manda
--      el de la Carrera, que lleva la carga horaria);
--   2. los demás pasan a la Carrera (dentro del Instituto no había superposiciones).

DELETE FROM vinculo
WHERE unidad_id = (SELECT id FROM unidad WHERE sigla = 'IIMAT')
  AND EXISTS (SELECT 1 FROM vinculo c
              WHERE c.usuario_id = vinculo.usuario_id
                AND c.unidad_id = (SELECT id FROM unidad WHERE sigla = 'CMAT')
                AND COALESCE(c.fecha_inicio, '0000-01-01') <= COALESCE(vinculo.fecha_fin, '9999-12-31')
                AND COALESCE(c.fecha_fin, '9999-12-31') >= COALESCE(vinculo.fecha_inicio, '0000-01-01'));

UPDATE vinculo SET unidad_id = (SELECT id FROM unidad WHERE sigla = 'CMAT')
WHERE unidad_id = (SELECT id FROM unidad WHERE sigla = 'IIMAT');
