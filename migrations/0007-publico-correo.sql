-- Fase 7: perfiles públicos, avisos por correo y enlaces de un solo uso.

-- Preferencia de avisos por correo (propuestas y revisiones en proyectos).
ALTER TABLE usuario ADD COLUMN avisos_correo INTEGER NOT NULL DEFAULT 1 CHECK (avisos_correo IN (0, 1));

-- Enlaces de un solo uso: recuperar contraseña e invitar a una cuenta nueva.
-- Se guarda solo el hash SHA-256 del token: quien lea la BD no puede usar los enlaces.
CREATE TABLE token_acceso (
    id         INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    token_hash TEXT    NOT NULL UNIQUE,
    proposito  TEXT    NOT NULL CHECK (proposito IN ('recuperar', 'invitacion')),
    expira_en  TEXT    NOT NULL,
    usado_en   TEXT,
    creado_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_token_acceso_usuario ON token_acceso (usuario_id, proposito);
