-- Internacionalización (IAC-CINDA 3.5.2 c y 3.6.3 h): ámbito de los proyectos e instituciones
-- contraparte con su país.
ALTER TABLE proyecto ADD COLUMN ambito TEXT CHECK (ambito IN ('nacional', 'internacional'));

CREATE TABLE proyecto_contraparte (
    id          INTEGER PRIMARY KEY,
    proyecto_id INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    institucion TEXT NOT NULL,
    pais        TEXT,
    creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_proyecto_contraparte ON proyecto_contraparte (proyecto_id);
