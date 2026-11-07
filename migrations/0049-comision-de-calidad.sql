-- Módulo de Aseguramiento de la Calidad (PLAN §57, etapa 1): el rol «Comité de acreditación»
-- (comite_acreditacion) pasa a ser la «Comisión de calidad» (comision_calidad), con los mismos permisos de
-- lectura por ahora. El sistema deja de nombrar a una agencia en particular (decisión del 6-nov-2026).
-- SQLite no cambia un CHECK: se recrea la tabla conservando todas las asignaciones (vigentes e históricas).
-- Nada referencia a rol_asignado; los registros de auditoría anteriores conservan el nombre antiguo.
CREATE TABLE rol_asignado_nueva (
    id           INTEGER PRIMARY KEY,
    usuario_id   INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    rol          TEXT NOT NULL CHECK (rol IN ('administracion_sistema', 'direccion_instituto',
                                              'direccion_carrera', 'coordinacion_academica',
                                              'comision_calidad', 'gestion_datos')),
    unidad_id    INTEGER NOT NULL REFERENCES unidad(id),
    desde        TEXT NOT NULL,
    hasta        TEXT,
    nota         TEXT,                        -- p. ej., «Pedido de la Dirección, nota 12/2026»
    asignado_por INTEGER REFERENCES usuario(id),
    creado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (hasta IS NULL OR hasta >= desde)
);
INSERT INTO rol_asignado_nueva (id, usuario_id, rol, unidad_id, desde, hasta, nota, asignado_por, creado_en)
    SELECT id, usuario_id,
           CASE rol WHEN 'comite_acreditacion' THEN 'comision_calidad' ELSE rol END,
           unidad_id, desde, hasta, nota, asignado_por, creado_en
    FROM rol_asignado;
DROP TABLE rol_asignado;
ALTER TABLE rol_asignado_nueva RENAME TO rol_asignado;
CREATE INDEX ix_rol_asignado_usuario ON rol_asignado (usuario_id, rol);
