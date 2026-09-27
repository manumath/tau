-- Líneas de investigación institucionales (IAC-CINDA; Guía de Antecedentes, hojas 2, 19–23 y 25).
--
-- Las líneas cambian con el tiempo: cada una tiene un periodo de vigencia. Una línea que deja de
-- regir no se borra (proyectos, propuestas y perfiles la conservan en su historia): se le pone
-- fecha de término. `vigente_desde` NULL = rige desde antes de registrarse en el portal.
CREATE TABLE linea_investigacion (
    id             INTEGER PRIMARY KEY,
    nombre         TEXT NOT NULL,
    descripcion    TEXT,
    vigente_desde  TEXT,
    vigente_hasta  TEXT,
    orden          INTEGER NOT NULL DEFAULT 0,
    creado_por     INTEGER REFERENCES usuario(id),
    creado_en      TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT,
    CHECK (vigente_hasta IS NULL OR vigente_desde IS NULL OR vigente_hasta >= vigente_desde)
);

-- Líneas a las que adscribe cada proyecto (en los institucionales, las de la propuesta aceptada).
CREATE TABLE proyecto_linea (
    proyecto_id INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    linea_id    INTEGER NOT NULL REFERENCES linea_investigacion(id),
    PRIMARY KEY (proyecto_id, linea_id)
);

-- Líneas elegidas en cada propuesta institucional (obligatorio al menos una para enviarla).
CREATE TABLE propuesta_linea (
    propuesta_id INTEGER NOT NULL REFERENCES propuesta_institucional(id) ON DELETE CASCADE,
    linea_id     INTEGER NOT NULL REFERENCES linea_investigacion(id),
    PRIMARY KEY (propuesta_id, linea_id)
);

-- Adscripción voluntaria de cada investigador (desde su perfil).
CREATE TABLE investigador_linea (
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    linea_id   INTEGER NOT NULL REFERENCES linea_investigacion(id),
    PRIMARY KEY (usuario_id, linea_id)
);
CREATE INDEX ix_investigador_linea ON investigador_linea (linea_id);
CREATE INDEX ix_proyecto_linea ON proyecto_linea (linea_id);

-- Líneas del programa según la Guía de Antecedentes (hoja 2).
INSERT INTO linea_investigacion (id, nombre, orden) VALUES
    (1, 'Sistemas Dinámicos', 1),
    (2, 'Estructuras Algebraicas Ordenadas', 2),
    (3, 'Teoría de Control', 3),
    (4, 'Modelos Matemáticos y Computación', 4),
    (5, 'Optimización Matemática', 5),
    (6, 'Áreas Fundamentales Complementarias', 6);
