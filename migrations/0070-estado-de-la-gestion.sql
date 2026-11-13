-- Ciclo de vida de las gestiones académicas (PLAN §66, etapa 1; decisiones del 13-nov-2026).
--
-- Una gestión pasa por tres estados: PLANIFICACIÓN (se arma la oferta y se asignan docentes; se edita libremente y se
-- puede borrar), ACTIVA (el semestre está en marcha: los cambios piden motivo y fecha de efecto) y CONCLUIDA (historial,
-- solo lectura). Activar, concluir y reabrir son de la Dirección de Carrera.
--
-- Las gestiones que ya existen se clasifican por sus fechas, sin perder nada: las que ya terminaron quedan concluidas
-- (historial), las que están en curso, activas, y las que aún no empiezan, en planificación. La fecha de «hoy» es la de
-- La Paz (UTC-4).
ALTER TABLE gestion_academica ADD COLUMN estado TEXT NOT NULL DEFAULT 'planificacion'
    CHECK (estado IN ('planificacion', 'activa', 'concluida'));
ALTER TABLE gestion_academica ADD COLUMN activada_en       TEXT;
ALTER TABLE gestion_academica ADD COLUMN activada_por      INTEGER REFERENCES usuario(id);
ALTER TABLE gestion_academica ADD COLUMN concluida_en      TEXT;
ALTER TABLE gestion_academica ADD COLUMN concluida_por     INTEGER REFERENCES usuario(id);
ALTER TABLE gestion_academica ADD COLUMN motivo_conclusion TEXT;      -- solo si se concluyó antes de su término

UPDATE gestion_academica SET
    estado = CASE WHEN fecha_fin < date('now', '-4 hours') THEN 'concluida'
                  WHEN fecha_inicio <= date('now', '-4 hours') THEN 'activa' ELSE 'planificacion' END,
    activada_en = CASE WHEN fecha_inicio <= date('now', '-4 hours') THEN fecha_inicio END,
    concluida_en = CASE WHEN fecha_fin < date('now', '-4 hours') THEN fecha_fin END;
