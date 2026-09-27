-- Fase 2, paso 4b (PLAN.md, sección 23): varios grados académicos por persona (Guía de
-- Antecedentes, hoja 10: grados con su institución). Reemplazan el campo único
-- `investigador.grado`, que se migra como primer grado (el texto libre, como título).
CREATE TABLE grado_academico (
    id          INTEGER PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    nivel       TEXT NOT NULL CHECK (nivel IN ('doctorado', 'maestria', 'especialidad', 'licenciatura',
                                               'tecnico', 'otro')),
    titulo      TEXT,              -- p. ej., «Doctor en Matemáticas»
    institucion TEXT,
    pais        TEXT,
    anio        INTEGER,
    creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_grado_academico_usuario ON grado_academico (usuario_id);

INSERT INTO grado_academico (usuario_id, nivel, titulo)
    SELECT usuario_id,
           CASE grado WHEN 'Doctorado' THEN 'doctorado' WHEN 'Magíster' THEN 'maestria'
                      WHEN 'Licenciatura o título profesional' THEN 'licenciatura' ELSE 'otro' END,
           CASE WHEN grado IN ('Doctorado', 'Magíster', 'Licenciatura o título profesional', 'Otro') THEN NULL
                ELSE grado END
    FROM investigador WHERE grado IS NOT NULL AND trim(grado) != '';

ALTER TABLE investigador DROP COLUMN grado;
