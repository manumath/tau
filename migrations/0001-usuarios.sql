-- Fase 1: cuentas, perfil básico del investigador, intentos de login y auditoría.

CREATE TABLE usuario (
    id                INTEGER PRIMARY KEY,
    email             TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    nombres           TEXT    NOT NULL,
    apellidos         TEXT    NOT NULL,
    pass_hash         TEXT    NOT NULL,
    es_admin          INTEGER NOT NULL DEFAULT 0 CHECK (es_admin IN (0, 1)),
    activo            INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    debe_cambiar_pass INTEGER NOT NULL DEFAULT 1 CHECK (debe_cambiar_pass IN (0, 1)),
    creado_en         TEXT    NOT NULL DEFAULT (datetime('now')),
    ultimo_acceso     TEXT
);

-- Una cuenta es investigador si tiene fila aquí (un administrador puede no serlo).
CREATE TABLE investigador (
    usuario_id     INTEGER PRIMARY KEY REFERENCES usuario(id) ON DELETE CASCADE,
    grado          TEXT,
    cargo          TEXT,
    unidad         TEXT,
    orcid          TEXT,
    mr_id          TEXT,
    zbmath_id      TEXT,
    arxiv_id       TEXT,
    scholar_url    TEXT,
    bio            TEXT,
    perfil_publico INTEGER NOT NULL DEFAULT 0 CHECK (perfil_publico IN (0, 1))
);

CREATE TABLE intento_login (
    id    INTEGER PRIMARY KEY,
    email TEXT    NOT NULL COLLATE NOCASE,
    ip    TEXT,
    exito INTEGER NOT NULL CHECK (exito IN (0, 1)),
    fecha TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_intento_login_email_fecha ON intento_login (email, fecha);

CREATE TABLE auditoria (
    id         INTEGER PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuario(id),
    accion     TEXT NOT NULL,
    entidad    TEXT,
    entidad_id INTEGER,
    detalle    TEXT,
    fecha      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_auditoria_entidad ON auditoria (entidad, entidad_id);
