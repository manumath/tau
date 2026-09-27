-- Fase 2, paso 1 (PLAN.md, sección 23): unidades y vínculo por unidad.
--
-- Jerarquía UMSA › FCPN › CMAT › IIMAT. Una persona puede estar vinculada a la Carrera, al
-- Instituto o a ambos, con categoría y jornada propias en cada uno. Los vínculos existentes son
-- con el Instituto (el portal nació como portal de investigación del IIMAT).
CREATE TABLE unidad (
    id          INTEGER PRIMARY KEY,
    sigla       TEXT NOT NULL UNIQUE,
    nombre      TEXT NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('universidad', 'facultad', 'carrera', 'instituto')),
    superior_id INTEGER REFERENCES unidad(id)
);
INSERT INTO unidad (id, sigla, nombre, tipo, superior_id) VALUES
    (1, 'UMSA', 'Universidad Mayor de San Andrés', 'universidad', NULL),
    (2, 'FCPN', 'Facultad de Ciencias Puras y Naturales', 'facultad', 1),
    (3, 'CMAT', 'Carrera de Matemática', 'carrera', 2),
    (4, 'IIMAT', 'Instituto de Investigación Matemática', 'instituto', 3);

-- vinculo con unidad_id obligatorio. SQLite no agrega una columna NOT NULL con clave foránea:
-- se reconstruye la tabla (nada la referencia).
CREATE TABLE vinculo_nuevo (
    id            INTEGER PRIMARY KEY,
    usuario_id    INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    unidad_id     INTEGER NOT NULL REFERENCES unidad(id),
    categoria     TEXT NOT NULL
                  CHECK (categoria IN ('titular', 'contratado', 'interino', 'invitado', 'externo')),
    fecha_inicio  TEXT,
    fecha_fin     TEXT,
    jornada_horas INTEGER CHECK (jornada_horas IS NULL OR jornada_horas BETWEEN 1 AND 60),
    nota          TEXT,
    creado_por    INTEGER REFERENCES usuario(id),
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (fecha_fin IS NULL OR fecha_inicio IS NULL OR fecha_fin >= fecha_inicio)
);
INSERT INTO vinculo_nuevo (id, usuario_id, unidad_id, categoria, fecha_inicio, fecha_fin, jornada_horas, nota,
                           creado_por, creado_en)
    SELECT id, usuario_id, 4, categoria, fecha_inicio, fecha_fin, jornada_horas, nota, creado_por, creado_en
    FROM vinculo;
DROP TABLE vinculo;
ALTER TABLE vinculo_nuevo RENAME TO vinculo;
CREATE INDEX ix_vinculo_usuario ON vinculo (usuario_id, unidad_id, fecha_inicio);
