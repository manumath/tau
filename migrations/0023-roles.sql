-- Fase 2, paso 2 (PLAN.md, sección 23): roles con alcance (unidad) y vigencia.
--
-- Los asigna solo Administración del sistema, a pedido de las direcciones. Un rol que termina no
-- se borra: se le pone fecha de término (queda la historia de quién tuvo qué y cuándo).
CREATE TABLE rol_asignado (
    id           INTEGER PRIMARY KEY,
    usuario_id   INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    rol          TEXT NOT NULL CHECK (rol IN ('administracion_sistema', 'direccion_instituto',
                                              'direccion_carrera', 'coordinacion_academica',
                                              'comite_acreditacion', 'gestion_datos')),
    unidad_id    INTEGER NOT NULL REFERENCES unidad(id),
    desde        TEXT NOT NULL,
    hasta        TEXT,
    nota         TEXT,                        -- p. ej., «Pedido de la Dirección, nota 12/2026»
    asignado_por INTEGER REFERENCES usuario(id),
    creado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (hasta IS NULL OR hasta >= desde)
);
CREATE INDEX ix_rol_asignado_usuario ON rol_asignado (usuario_id, rol);

-- Transición sin pérdidas: quien hoy administra recibe Administración del sistema (UMSA) y
-- Dirección del Instituto (IIMAT), que juntas equivalen a lo que hoy puede hacer.
INSERT INTO rol_asignado (usuario_id, rol, unidad_id, desde, nota)
    SELECT id, 'administracion_sistema', 1, date('now', 'localtime'), 'Asignado al crear los roles (antes: administrador)'
    FROM usuario WHERE es_admin = 1;
INSERT INTO rol_asignado (usuario_id, rol, unidad_id, desde, nota)
    SELECT id, 'direccion_instituto', 4, date('now', 'localtime'), 'Asignado al crear los roles (antes: administrador)'
    FROM usuario WHERE es_admin = 1;

-- La marca de administración deja de existir: los roles son la única fuente.
ALTER TABLE usuario DROP COLUMN es_admin;
