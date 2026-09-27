-- Fase 3, paso 3.4 (revisión): la carga horaria contratada se registra en el vínculo con la Carrera.
--
-- Cada periodo de vínculo con la Carrera lleva la carga total contratada (32, 64, 96, 128 o 160
-- h/mes) y su distribución por actividad (docencia, investigación, extensión, gestión, otras), en
-- múltiplos de 32 h/mes que suman la carga contratada. Un cambio de carga es un nuevo periodo
-- («Registrar cambio»). La vista semestral compara la docencia prevista con la asignada en la oferta.

ALTER TABLE vinculo ADD COLUMN horas_contratadas INTEGER
    CHECK (horas_contratadas IS NULL OR horas_contratadas IN (32, 64, 96, 128, 160));
ALTER TABLE vinculo ADD COLUMN carga_docencia INTEGER NOT NULL DEFAULT 0
    CHECK (carga_docencia BETWEEN 0 AND 160 AND carga_docencia % 32 = 0);
ALTER TABLE vinculo ADD COLUMN carga_investigacion INTEGER NOT NULL DEFAULT 0
    CHECK (carga_investigacion BETWEEN 0 AND 160 AND carga_investigacion % 32 = 0);
ALTER TABLE vinculo ADD COLUMN carga_extension INTEGER NOT NULL DEFAULT 0
    CHECK (carga_extension BETWEEN 0 AND 160 AND carga_extension % 32 = 0);
ALTER TABLE vinculo ADD COLUMN carga_gestion INTEGER NOT NULL DEFAULT 0
    CHECK (carga_gestion BETWEEN 0 AND 160 AND carga_gestion % 32 = 0);
ALTER TABLE vinculo ADD COLUMN carga_otras INTEGER NOT NULL DEFAULT 0
    CHECK (carga_otras BETWEEN 0 AND 160 AND carga_otras % 32 = 0);
ALTER TABLE vinculo ADD COLUMN carga_detalle TEXT;

-- Lo registrado por semestre (tablas de la 0030) pasa al vínculo con la Carrera vigente al inicio de
-- ese semestre, si aún no tiene carga. La docencia prevista es lo que no ocupan las otras actividades.
UPDATE vinculo SET
    horas_contratadas = (SELECT c.horas_contratadas FROM carga_semestral c JOIN gestion_academica g ON g.id = c.gestion_id
                         WHERE c.usuario_id = vinculo.usuario_id
                           AND COALESCE(vinculo.fecha_inicio, '0000-01-01') <= g.fecha_inicio
                           AND COALESCE(vinculo.fecha_fin, '9999-12-31') >= g.fecha_inicio
                         ORDER BY g.fecha_inicio DESC LIMIT 1)
WHERE horas_contratadas IS NULL AND unidad_id = (SELECT id FROM unidad WHERE sigla = 'CMAT');

UPDATE vinculo SET
    carga_investigacion = MIN(160, (SELECT COALESCE(SUM(a.horas), 0) FROM carga_actividad a
        JOIN carga_semestral c ON c.id = a.carga_id JOIN gestion_academica g ON g.id = c.gestion_id
        WHERE a.tipo = 'investigacion' AND c.usuario_id = vinculo.usuario_id
          AND g.id = (SELECT g2.id FROM carga_semestral c2 JOIN gestion_academica g2 ON g2.id = c2.gestion_id
                      WHERE c2.usuario_id = vinculo.usuario_id
                        AND COALESCE(vinculo.fecha_inicio, '0000-01-01') <= g2.fecha_inicio
                        AND COALESCE(vinculo.fecha_fin, '9999-12-31') >= g2.fecha_inicio
                      ORDER BY g2.fecha_inicio DESC LIMIT 1))),
    carga_extension = MIN(160, (SELECT COALESCE(SUM(a.horas), 0) FROM carga_actividad a
        JOIN carga_semestral c ON c.id = a.carga_id JOIN gestion_academica g ON g.id = c.gestion_id
        WHERE a.tipo = 'extension' AND c.usuario_id = vinculo.usuario_id
          AND g.id = (SELECT g2.id FROM carga_semestral c2 JOIN gestion_academica g2 ON g2.id = c2.gestion_id
                      WHERE c2.usuario_id = vinculo.usuario_id
                        AND COALESCE(vinculo.fecha_inicio, '0000-01-01') <= g2.fecha_inicio
                        AND COALESCE(vinculo.fecha_fin, '9999-12-31') >= g2.fecha_inicio
                      ORDER BY g2.fecha_inicio DESC LIMIT 1))),
    carga_gestion = MIN(160, (SELECT COALESCE(SUM(a.horas), 0) FROM carga_actividad a
        JOIN carga_semestral c ON c.id = a.carga_id JOIN gestion_academica g ON g.id = c.gestion_id
        WHERE a.tipo = 'gestion' AND c.usuario_id = vinculo.usuario_id
          AND g.id = (SELECT g2.id FROM carga_semestral c2 JOIN gestion_academica g2 ON g2.id = c2.gestion_id
                      WHERE c2.usuario_id = vinculo.usuario_id
                        AND COALESCE(vinculo.fecha_inicio, '0000-01-01') <= g2.fecha_inicio
                        AND COALESCE(vinculo.fecha_fin, '9999-12-31') >= g2.fecha_inicio
                      ORDER BY g2.fecha_inicio DESC LIMIT 1))),
    carga_otras = MIN(160, (SELECT COALESCE(SUM(a.horas), 0) FROM carga_actividad a
        JOIN carga_semestral c ON c.id = a.carga_id JOIN gestion_academica g ON g.id = c.gestion_id
        WHERE a.tipo = 'otras' AND c.usuario_id = vinculo.usuario_id
          AND g.id = (SELECT g2.id FROM carga_semestral c2 JOIN gestion_academica g2 ON g2.id = c2.gestion_id
                      WHERE c2.usuario_id = vinculo.usuario_id
                        AND COALESCE(vinculo.fecha_inicio, '0000-01-01') <= g2.fecha_inicio
                        AND COALESCE(vinculo.fecha_fin, '9999-12-31') >= g2.fecha_inicio
                      ORDER BY g2.fecha_inicio DESC LIMIT 1)))
WHERE horas_contratadas IS NOT NULL AND unidad_id = (SELECT id FROM unidad WHERE sigla = 'CMAT');

-- Si las actividades superaban lo contratado, se dejan en cero para que la Dirección las revise.
UPDATE vinculo SET carga_investigacion = 0, carga_extension = 0, carga_gestion = 0, carga_otras = 0
WHERE horas_contratadas IS NOT NULL
  AND carga_investigacion + carga_extension + carga_gestion + carga_otras > horas_contratadas;
UPDATE vinculo SET carga_docencia = horas_contratadas - carga_investigacion - carga_extension - carga_gestion - carga_otras
WHERE horas_contratadas IS NOT NULL;

DROP TABLE carga_actividad;
DROP TABLE carga_semestral;
