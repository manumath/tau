-- IA con criterio humano, etapa 0a (PLAN §59): política de uso, funciones activables y registro de cada uso.
-- El catálogo de funciones (nombre, módulo, nivel de datos, quién aprueba) vive en el código (app/ia/funciones.py);
-- aquí solo se guarda si cada una está activa y quién responde por ella. Todo nace apagado.

-- Política de uso de la IA, por versiones; solo una vigente (la aprobada más reciente).
CREATE TABLE ia_politica (
    id               INTEGER PRIMARY KEY,
    version          INTEGER NOT NULL UNIQUE,
    texto            TEXT NOT NULL,
    creado_por       INTEGER REFERENCES usuario(id),
    creado_en        TEXT NOT NULL DEFAULT (datetime('now')),
    aprobada_por     INTEGER REFERENCES usuario(id),
    fecha_aprobacion TEXT,
    vigente          INTEGER NOT NULL DEFAULT 0 CHECK (vigente IN (0, 1))
);

-- Activación de cada función del catálogo (apagada por omisión) y su responsable.
CREATE TABLE ia_funcion (
    clave           TEXT PRIMARY KEY,
    activa          INTEGER NOT NULL DEFAULT 0 CHECK (activa IN (0, 1)),
    responsable_id  INTEGER REFERENCES usuario(id),
    actualizado_por INTEGER REFERENCES usuario(id),
    actualizado_en  TEXT,
    CHECK (activa = 0 OR responsable_id IS NOT NULL)
);

-- Cada invocación y su desenlace (base de la medición). Ninguna salida surte efecto sin una decisión humana:
-- generando → borrador_ia → aprobada | editada | rechazada (o error).
CREATE TABLE ia_uso (
    id                INTEGER PRIMARY KEY,
    funcion_clave     TEXT NOT NULL,
    usuario_id        INTEGER NOT NULL REFERENCES usuario(id),
    creado_en         TEXT NOT NULL DEFAULT (datetime('now')),
    terminado_en      TEXT,
    proveedor         TEXT CHECK (proveedor IN ('local', 'externo')),
    modelo            TEXT,
    version_prompt    INTEGER NOT NULL,
    hash_entrada      TEXT NOT NULL,
    nivel_datos       INTEGER NOT NULL CHECK (nivel_datos BETWEEN 0 AND 2),
    seudonimizado     INTEGER NOT NULL DEFAULT 0 CHECK (seudonimizado IN (0, 1)),
    estado            TEXT NOT NULL DEFAULT 'generando'
                      CHECK (estado IN ('generando', 'borrador_ia', 'aprobada', 'editada', 'rechazada', 'error')),
    error             TEXT,
    entidad_tipo      TEXT,
    entidad_id        INTEGER,
    revisor_id        INTEGER REFERENCES usuario(id),
    fecha_decision    TEXT,
    motivo            TEXT,
    distancia_edicion REAL CHECK (distancia_edicion IS NULL OR distancia_edicion BETWEEN 0 AND 1),
    valoracion        INTEGER CHECK (valoracion IS NULL OR valoracion BETWEEN 1 AND 5)
);
CREATE INDEX ix_ia_uso_funcion ON ia_uso (funcion_clave, creado_en);
CREATE INDEX ix_ia_uso_entidad ON ia_uso (entidad_tipo, entidad_id);

-- Texto propuesto por el modelo y texto finalmente aprobado por la persona.
CREATE TABLE ia_salida (
    uso_id         INTEGER PRIMARY KEY REFERENCES ia_uso(id) ON DELETE CASCADE,
    texto_generado TEXT NOT NULL,
    texto_final    TEXT
);
