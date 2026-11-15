-- PLAN §72, etapa 11 (ensayo del piloto; decisión del 15-nov-2026): el responsable de una actividad del plan de mejora
-- sube la evidencia de esa actividad, aunque no tenga acceso al repositorio de evidencias. La evidencia queda en el
-- repositorio (la ve la Comisión de calidad) y ligada a la actividad; su responsable la ve y la elige en sus avances y
-- reprogramaciones, y no ve las demás. Las evidencias que ya había quedan sin actividad.
ALTER TABLE evidencia_calidad ADD COLUMN actividad_id INTEGER REFERENCES actividad_mejora(id) ON DELETE SET NULL;
CREATE INDEX ix_evidencia_calidad_actividad ON evidencia_calidad (actividad_id);
