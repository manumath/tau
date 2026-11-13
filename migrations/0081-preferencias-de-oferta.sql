-- Preferencias del docente para la oferta de una gestión (PLAN §68, etapa 2).
--
-- Antes de armar la oferta, cada docente dice qué materias prefiere dictar o no puede dictar, y en qué turnos no tiene
-- disponibilidad. La Coordinación las ve al asignar docentes; es una ayuda, no una asignación: nada se asigna solo.
-- Solo las ve la propia persona y quienes arman la oferta (`gestionar_oferta`). Se editan mientras la gestión está en
-- planificación.
CREATE TABLE preferencia_oferta (
    id            INTEGER PRIMARY KEY,
    gestion_id    INTEGER NOT NULL REFERENCES gestion_academica(id) ON DELETE CASCADE,
    usuario_id    INTEGER NOT NULL REFERENCES usuario(id),
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id),
    nivel         TEXT NOT NULL CHECK (nivel IN ('prefiere', 'no_puede')),
    nota          TEXT,
    UNIQUE (gestion_id, usuario_id, asignatura_id)
);
CREATE INDEX ix_preferencia_oferta_asignatura ON preferencia_oferta (gestion_id, asignatura_id);

CREATE TABLE preferencia_gestion (
    gestion_id     INTEGER NOT NULL REFERENCES gestion_academica(id) ON DELETE CASCADE,
    usuario_id     INTEGER NOT NULL REFERENCES usuario(id),
    indisponible   TEXT NOT NULL DEFAULT '',     -- turnos sin disponibilidad: 'lun-manana,mar-tarde'
    comentario     TEXT,
    actualizada_en TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (gestion_id, usuario_id)
);
