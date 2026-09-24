-- Fase 3: personas externas, actividades, productos y adjuntos.
-- La vinculación con proyectos (actividad_proyecto, producto_proyecto) llega en la fase 4.

-- Personas sin cuenta (coautores, tesistas o colaboradores de otras instituciones).
-- Se registran una vez y se reutilizan; usuario_id se completa si luego reciben cuenta.
CREATE TABLE persona_externa (
    id          INTEGER PRIMARY KEY,
    nombres     TEXT NOT NULL,
    apellidos   TEXT NOT NULL,
    institucion TEXT,
    pais        TEXT,
    email       TEXT,
    orcid       TEXT,
    usuario_id  INTEGER REFERENCES usuario(id),
    creado_por  INTEGER REFERENCES usuario(id),
    creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- --- Actividades ---------------------------------------------------------------

CREATE TABLE actividad (
    id             INTEGER PRIMARY KEY,
    tipo_id        INTEGER NOT NULL REFERENCES tipo_actividad(id),
    titulo         TEXT    NOT NULL,
    institucion    TEXT,                     -- organizadora o anfitriona
    lugar          TEXT,                     -- ciudad o sede
    pais           TEXT,
    fecha_inicio   TEXT    NOT NULL,         -- ISO 8601 (AAAA-MM-DD)
    fecha_fin      TEXT,
    modalidad      TEXT    NOT NULL DEFAULT 'presencial'
                   CHECK (modalidad IN ('presencial', 'virtual', 'hibrida')),
    ambito         TEXT    NOT NULL DEFAULT 'nacional'
                   CHECK (ambito IN ('local', 'nacional', 'internacional')),
    url            TEXT,
    descripcion    TEXT,
    creado_por     INTEGER NOT NULL REFERENCES usuario(id),
    creado_en      TEXT    NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT,
    CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);
CREATE INDEX ix_actividad_fecha ON actividad (fecha_inicio);

CREATE TABLE actividad_participante (
    actividad_id    INTEGER NOT NULL REFERENCES actividad(id) ON DELETE CASCADE,
    orden           INTEGER NOT NULL,
    investigador_id INTEGER REFERENCES usuario(id),
    externo_id      INTEGER REFERENCES persona_externa(id),
    rol             TEXT    NOT NULL DEFAULT 'asistente'
                    CHECK (rol IN ('organizador', 'expositor', 'asistente', 'comite')),
    PRIMARY KEY (actividad_id, orden),
    CHECK ((investigador_id IS NULL) <> (externo_id IS NULL))
);
CREATE INDEX ix_actividad_participante_inv ON actividad_participante (investigador_id);

-- --- Productos -----------------------------------------------------------------

CREATE TABLE producto (
    id                 INTEGER PRIMARY KEY,
    tipo_id            INTEGER NOT NULL REFERENCES tipo_producto(id),
    titulo             TEXT    NOT NULL,
    anio               INTEGER NOT NULL,
    estado_publicacion TEXT    NOT NULL DEFAULT 'publicado'
                       CHECK (estado_publicacion IN ('en_preparacion', 'enviado', 'aceptado', 'publicado')),
    revision           TEXT    NOT NULL DEFAULT 'sin_arbitraje'
                       CHECK (revision IN ('indexado', 'arbitrado', 'sin_arbitraje')),
    medio              TEXT,                 -- revista, editorial, actas, repositorio…
    volumen            TEXT,
    numero             TEXT,
    paginas            TEXT,
    doi                TEXT UNIQUE,          -- normalizado en minúsculas, sin https://doi.org/
    arxiv_id           TEXT UNIQUE,          -- sin versión: 2401.01234, math/0501001
    url                TEXT,
    resumen            TEXT,
    actividad_id       INTEGER REFERENCES actividad(id) ON DELETE SET NULL,  -- p. ej. presentación en un congreso
    creado_por         INTEGER NOT NULL REFERENCES usuario(id),
    creado_en          TEXT    NOT NULL DEFAULT (datetime('now')),
    actualizado_en     TEXT
);
CREATE INDEX ix_producto_anio ON producto (anio);

CREATE TABLE producto_autor (
    producto_id     INTEGER NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    orden           INTEGER NOT NULL,
    investigador_id INTEGER REFERENCES usuario(id),
    externo_id      INTEGER REFERENCES persona_externa(id),
    PRIMARY KEY (producto_id, orden),
    CHECK ((investigador_id IS NULL) <> (externo_id IS NULL))
);
CREATE INDEX ix_producto_autor_inv ON producto_autor (investigador_id);

CREATE TABLE producto_indice (
    producto_id INTEGER NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    indice_id   INTEGER NOT NULL REFERENCES indice(id),
    PRIMARY KEY (producto_id, indice_id)
);

-- --- Adjuntos ------------------------------------------------------------------

CREATE TABLE adjunto (
    id         INTEGER PRIMARY KEY,
    entidad    TEXT    NOT NULL CHECK (entidad IN ('actividad', 'producto')),
    entidad_id INTEGER NOT NULL,
    nombre     TEXT    NOT NULL,             -- nombre original, solo para mostrar y descargar
    archivo    TEXT    NOT NULL UNIQUE,      -- nombre aleatorio en <datos>/adjuntos
    mime       TEXT    NOT NULL,
    tamano     INTEGER NOT NULL,
    subido_por INTEGER NOT NULL REFERENCES usuario(id),
    subido_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_adjunto_entidad ON adjunto (entidad, entidad_id);
