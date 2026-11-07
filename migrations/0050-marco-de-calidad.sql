-- Marco de calidad como datos (PLAN §57, etapa 2). El Sistema Interno de Aseguramiento de la Calidad (SIAC) de la
-- Carrera trabaja con un marco propio, guardado aquí y no en el código: marco → dimensiones → criterios → indicadores.
-- Los criterios de calidad de la Política de Calidad de la UMSA (pertinencia, equidad, eficacia…) no son un nivel más:
-- son atributos que se marcan en cada indicador. Las metas son por año. Un marco por unidad evaluable; se empieza por
-- la Carrera (la migración 0051 carga su borrador desde datos/calidad/marco-carrera/).
CREATE TABLE marco_calidad (
    id            INTEGER PRIMARY KEY,
    unidad_id     INTEGER NOT NULL REFERENCES unidad(id),
    nombre        TEXT    NOT NULL,
    version       TEXT    NOT NULL,
    descripcion   TEXT,
    vigente_desde TEXT,
    vigente_hasta TEXT,
    ventana_anios INTEGER NOT NULL DEFAULT 5 CHECK (ventana_anios BETWEEN 1 AND 10),  -- años de evidencia
    creado_en     TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (unidad_id, version),
    CHECK (vigente_hasta IS NULL OR vigente_desde IS NULL OR vigente_hasta >= vigente_desde)
);

-- Escala de valoración de los juicios por criterio (configurable; por omisión, 4 niveles).
CREATE TABLE nivel_escala (
    id          INTEGER PRIMARY KEY,
    marco_id    INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    valor       INTEGER NOT NULL,
    nombre      TEXT    NOT NULL,
    descripcion TEXT,
    UNIQUE (marco_id, valor)
);

CREATE TABLE atributo_calidad (
    id          INTEGER PRIMARY KEY,
    marco_id    INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    clave       TEXT    NOT NULL,
    nombre      TEXT    NOT NULL,
    descripcion TEXT,
    UNIQUE (marco_id, clave)
);

CREATE TABLE dimension_calidad (
    id          INTEGER PRIMARY KEY,
    marco_id    INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    codigo      TEXT    NOT NULL,
    nombre      TEXT    NOT NULL,
    descripcion TEXT,
    referencia  TEXT,                       -- con qué políticas o dimensiones institucionales se alinea
    UNIQUE (marco_id, codigo)
);

CREATE TABLE criterio_calidad (
    id           INTEGER PRIMARY KEY,
    dimension_id INTEGER NOT NULL REFERENCES dimension_calidad(id),
    codigo       TEXT    NOT NULL,
    nombre       TEXT    NOT NULL,
    descripcion  TEXT,
    UNIQUE (dimension_id, codigo)
);

CREATE TABLE indicador_calidad (
    id            INTEGER PRIMARY KEY,
    criterio_id   INTEGER NOT NULL REFERENCES criterio_calidad(id),
    codigo        TEXT    NOT NULL,
    nombre        TEXT    NOT NULL,
    tipo          TEXT    NOT NULL CHECK (tipo IN ('estructura', 'proceso', 'resultado', 'percepcion', 'contexto')),
    formula       TEXT,                     -- en palabras, como la leen la Comisión y los pares
    fuente        TEXT    NOT NULL DEFAULT 'manual' CHECK (fuente = 'manual' OR fuente LIKE 'auto:_%'),
    unidad_medida TEXT,
    frecuencia    TEXT    NOT NULL DEFAULT 'anual' CHECK (frecuencia IN ('anual', 'semestral', 'por_periodo')),
    sentido       TEXT    NOT NULL DEFAULT 'mayor' CHECK (sentido IN ('mayor', 'menor', 'informativo')),
    responsable   TEXT,
    referencia    TEXT,                     -- p. ej., el objetivo de la Política de Calidad y su meta
    activo        INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    UNIQUE (criterio_id, codigo)
);

CREATE TABLE indicador_atributo (
    indicador_id INTEGER NOT NULL REFERENCES indicador_calidad(id) ON DELETE CASCADE,
    atributo_id  INTEGER NOT NULL REFERENCES atributo_calidad(id) ON DELETE CASCADE,
    PRIMARY KEY (indicador_id, atributo_id)
);

CREATE TABLE meta_indicador (
    id           INTEGER PRIMARY KEY,
    indicador_id INTEGER NOT NULL REFERENCES indicador_calidad(id) ON DELETE CASCADE,
    anio         INTEGER NOT NULL CHECK (anio BETWEEN 2000 AND 2100),
    valor        REAL    NOT NULL,
    nota         TEXT,
    UNIQUE (indicador_id, anio)
);

CREATE INDEX ix_criterio_calidad_dimension ON criterio_calidad (dimension_id);
CREATE INDEX ix_indicador_calidad_criterio ON indicador_calidad (criterio_id);
CREATE INDEX ix_indicador_atributo_atributo ON indicador_atributo (atributo_id);
