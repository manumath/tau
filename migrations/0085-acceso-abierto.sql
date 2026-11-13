-- Acceso abierto y datos de cada producto (PLAN §69, etapa 2).
--
-- Declaración propia de quienes firman el producto: dónde se puede leer el texto (en la revista, en un repositorio, bajo embargo o
-- no se puede) y si los datos o el código están disponibles. TAU no verifica los enlaces ni obliga a nada: es información para el
-- perfil público y para que el propio investigador vea qué le falta. Un producto sin fila está «sin declarar».
CREATE TABLE producto_acceso (
    producto_id    INTEGER PRIMARY KEY REFERENCES producto(id) ON DELETE CASCADE,
    texto          TEXT NOT NULL CHECK (texto IN ('abierto', 'depositado', 'embargo', 'cerrado', 'no_aplica')),
    version        TEXT CHECK (version IS NULL OR version IN ('preprint', 'aceptada', 'publicada')),
    enlace         TEXT,                          -- dónde leer el texto (sitio de la revista o repositorio)
    licencia       TEXT CHECK (licencia IS NULL OR licencia IN ('cc_by', 'cc_by_sa', 'cc_by_nc', 'cc_by_nc_sa', 'cc_by_nd',
                                                                 'cc_by_nc_nd', 'cc0', 'otra', 'sin_licencia')),
    embargo_hasta  TEXT,                          -- fecha desde la que se puede depositar (solo con texto = 'embargo')
    datos          TEXT CHECK (datos IS NULL OR datos IN ('publicados', 'a_pedido', 'reservados', 'no_hay')),
    datos_enlace   TEXT,                          -- repositorio, DOI o código (solo con datos = 'publicados')
    nota           TEXT,
    declarado_por  INTEGER NOT NULL REFERENCES usuario(id),
    declarado_en   TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT
);
CREATE INDEX ix_producto_acceso_texto ON producto_acceso (texto);
