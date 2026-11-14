-- PLAN §72, etapa 7: brechas baratas del plan de mejora (acciones A4.4 y A4.5).
-- vacante_admision: las vacantes ofertadas y los postulantes de cada admisión (semestre I o II) del programa de pregrado;
-- los admitidos no se guardan: salen de las cohortes cargadas.
-- rendimiento_asignatura: los agregados del Sistema de Seguimiento Académico por asignatura y gestión (inscritos,
-- aprobados, reprobados, abandonos), sin RU, nombres ni notas (decisión del usuario del 14-nov-2026). No cambia datos.
CREATE TABLE vacante_admision (
    id             INTEGER PRIMARY KEY,
    anio           INTEGER NOT NULL,
    ciclo          TEXT    NOT NULL CHECK (ciclo IN ('I', 'II')),
    vacantes       INTEGER NOT NULL CHECK (vacantes >= 0),
    postulantes    INTEGER CHECK (postulantes IS NULL OR postulantes >= 0),
    nota           TEXT,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (anio, ciclo)
);

CREATE TABLE rendimiento_asignatura (
    id            INTEGER PRIMARY KEY,
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id) ON DELETE CASCADE,
    anio          INTEGER NOT NULL,
    ciclo         TEXT    NOT NULL CHECK (ciclo IN ('I', 'II', 'INV', 'VER')),
    inscritos     INTEGER NOT NULL CHECK (inscritos >= 0),
    aprobados     INTEGER NOT NULL CHECK (aprobados >= 0),
    reprobados    INTEGER NOT NULL CHECK (reprobados >= 0),
    abandonos     INTEGER NOT NULL CHECK (abandonos >= 0),
    cargado_por   INTEGER REFERENCES usuario(id),
    cargado_en    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (asignatura_id, anio, ciclo),
    CHECK (aprobados + reprobados + abandonos <= inscritos)
);
CREATE INDEX ix_rendimiento_gestion ON rendimiento_asignatura (anio, ciclo);
