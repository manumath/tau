-- Catálogos administrables. Se usan desde la fase 3 (actividades y productos).

CREATE TABLE tipo_actividad (
    id     INTEGER PRIMARY KEY,
    nombre TEXT    NOT NULL UNIQUE,
    orden  INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

INSERT INTO tipo_actividad (nombre, orden) VALUES
    ('Seminario', 10),
    ('Congreso', 20),
    ('Taller / Workshop', 30),
    ('Escuela', 40),
    ('Curso', 50),
    ('Visita de investigación', 60),
    ('Estadía de investigación', 70),
    ('Organización de evento', 80),
    ('Comité científico o editorial', 90),
    ('Charla de divulgación', 100);

-- admite_revision = 0: el producto es siempre 'sin_arbitraje' (p. ej. reporte de investigación).
CREATE TABLE tipo_producto (
    id              INTEGER PRIMARY KEY,
    nombre          TEXT    NOT NULL UNIQUE,
    admite_revision INTEGER NOT NULL DEFAULT 1 CHECK (admite_revision IN (0, 1)),
    orden           INTEGER NOT NULL DEFAULT 0,
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

INSERT INTO tipo_producto (nombre, admite_revision, orden) VALUES
    ('Artículo en revista', 1, 10),
    ('Artículo en actas de congreso', 1, 20),
    ('Libro', 1, 30),
    ('Capítulo de libro', 1, 40),
    ('Reporte de investigación', 0, 50),
    ('Preprint', 0, 60),
    ('Presentación', 0, 70),
    ('Software', 0, 80),
    ('Tesis dirigida', 0, 90);

-- Índices bibliográficos. Un producto es 'indexado' si figura en al menos un índice
-- con cuenta_como_indexado = 1; la política la decide el instituto desde el catálogo.
CREATE TABLE indice (
    id                   INTEGER PRIMARY KEY,
    nombre               TEXT    NOT NULL UNIQUE,
    cuenta_como_indexado INTEGER NOT NULL DEFAULT 1 CHECK (cuenta_como_indexado IN (0, 1)),
    orden                INTEGER NOT NULL DEFAULT 0,
    activo               INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

INSERT INTO indice (nombre, cuenta_como_indexado, orden) VALUES
    ('Web of Science (SCIE)', 1, 10),
    ('Web of Science (ESCI)', 1, 20),
    ('Scopus', 1, 30),
    ('SciELO', 1, 40),
    ('MathSciNet', 1, 50),
    ('zbMATH Open', 1, 60),
    ('Latindex Catálogo', 0, 70);
