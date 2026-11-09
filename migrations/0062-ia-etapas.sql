-- IA con criterio humano, etapas 1b, 2 y 4 (PLAN §59).
-- 1. `ia_cierre`: decisión documentada de la Dirección de Carrera al cerrar el piloto de una función (ampliar, ajustar o
--    retirar), con su fundamento. «Retirar» además apaga la función (lo hace el código).
-- 2. `producto_linea`: líneas de investigación asignadas directamente a un producto. Hasta ahora un producto solo
--    heredaba las líneas de sus proyectos; la clasificación asistida (función producto_clasificar) guarda aquí solo lo
--    que la persona confirma.
-- 3. `capacitacion`: se agrega el área «ia_digital» (IA y competencias digitales, etapa 4). Cambiar el CHECK exige
--    recrear la tabla; se copian todas las filas y los índices (ninguna tabla la referencia).

CREATE TABLE ia_cierre (
    id            INTEGER PRIMARY KEY,
    funcion_clave TEXT NOT NULL,
    decision      TEXT NOT NULL CHECK (decision IN ('ampliar', 'ajustar', 'retirar')),
    fundamento    TEXT NOT NULL,
    decidido_por  INTEGER NOT NULL REFERENCES usuario(id),
    fecha         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_ia_cierre_funcion ON ia_cierre (funcion_clave, fecha);

CREATE TABLE producto_linea (
    producto_id  INTEGER NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    linea_id     INTEGER NOT NULL REFERENCES linea_investigacion(id),
    asignado_por INTEGER REFERENCES usuario(id),
    asignado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (producto_id, linea_id)
);
CREATE INDEX ix_producto_linea_linea ON producto_linea (linea_id);

CREATE TABLE capacitacion_nueva (
    id             INTEGER PRIMARY KEY,
    usuario_id     INTEGER NOT NULL REFERENCES usuario(id),
    titulo         TEXT NOT NULL,
    institucion    TEXT,
    area           TEXT NOT NULL CHECK (area IN ('disciplinar', 'pedagogica', 'investigacion', 'gestion', 'ia_digital',
                                                 'otra')),
    horas          INTEGER CHECK (horas IS NULL OR horas BETWEEN 1 AND 2000),
    fecha_inicio   TEXT NOT NULL,
    fecha_fin      TEXT NOT NULL,                -- cuenta en el año en que concluyó
    evidencia_id   INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (fecha_fin >= fecha_inicio)
);
INSERT INTO capacitacion_nueva SELECT id, usuario_id, titulo, institucion, area, horas, fecha_inicio, fecha_fin,
                                      evidencia_id, registrado_por, registrado_en FROM capacitacion;
DROP TABLE capacitacion;
ALTER TABLE capacitacion_nueva RENAME TO capacitacion;
CREATE INDEX ix_capacitacion_fin ON capacitacion (fecha_fin);
CREATE INDEX ix_capacitacion_usuario ON capacitacion (usuario_id);
