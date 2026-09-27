-- Fase 3, paso 3.4 (PLAN.md, sección 24): carga horaria semestral.
--
-- La carga se cuenta en unidades de 32 h/mes. Cada persona tiene una sola carga contratada por
-- semestre (32, 64, 96, 128 o 160 h/mes) y la Dirección de Carrera la distribuye: cada materia
-- asignada como titular (grado o maestría) son 32 h/mes; investigación, extensión, gestión y otras,
-- múltiplos de 32 h/mes. Los auxiliares y los cursos de verano e invierno no suman a la carga.

-- La asignación docente ya no lleva horas: cada materia de un titular cuenta 32 h/mes.
ALTER TABLE oferta_docente DROP COLUMN horas_semanales;

CREATE TABLE carga_semestral (
    id                INTEGER PRIMARY KEY,
    usuario_id        INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    gestion_id        INTEGER NOT NULL REFERENCES gestion_academica(id),   -- solo semestres I y II
    horas_contratadas INTEGER NOT NULL CHECK (horas_contratadas IN (32, 64, 96, 128, 160)),
    registrada_por    INTEGER REFERENCES usuario(id),
    actualizado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (usuario_id, gestion_id)
);

CREATE TABLE carga_actividad (
    id       INTEGER PRIMARY KEY,
    carga_id INTEGER NOT NULL REFERENCES carga_semestral(id) ON DELETE CASCADE,
    tipo     TEXT NOT NULL CHECK (tipo IN ('investigacion', 'extension', 'gestion', 'otras')),
    horas    INTEGER NOT NULL CHECK (horas BETWEEN 32 AND 160 AND horas % 32 = 0),
    detalle  TEXT
);
CREATE INDEX ix_carga_actividad ON carga_actividad (carga_id);
