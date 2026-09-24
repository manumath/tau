-- Fase 2: perfil del investigador (foto, página web y áreas MSC2020).

ALTER TABLE investigador ADD COLUMN pagina_web TEXT;
-- Nombre del archivo en <directorio de datos>/fotos; NULL = sin foto.
ALTER TABLE investigador ADD COLUMN foto TEXT;
ALTER TABLE investigador ADD COLUMN actualizado_en TEXT;

-- Catálogo MSC2020 (lo llena 0004-msc2020.py).
--   nivel 1: '11-XX' (sección)  nivel 2: '11Axx' (subsección)  nivel 3: '11A05', '11-02'
CREATE TABLE msc (
    codigo      TEXT PRIMARY KEY,
    nivel       INTEGER NOT NULL CHECK (nivel IN (1, 2, 3)),
    texto       TEXT NOT NULL,          -- con TeX en línea: '\(p\)-adic theory'
    texto_plano TEXT NOT NULL,          -- sin TeX, para búsquedas: 'p-adic theory'
    descripcion TEXT
);

CREATE TABLE investigador_msc (
    usuario_id INTEGER NOT NULL REFERENCES investigador(usuario_id) ON DELETE CASCADE,
    codigo     TEXT    NOT NULL REFERENCES msc(codigo),
    principal  INTEGER NOT NULL DEFAULT 0 CHECK (principal IN (0, 1)),
    orden      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (usuario_id, codigo)
);
-- A lo sumo un área principal por investigador.
CREATE UNIQUE INDEX ux_investigador_msc_principal
    ON investigador_msc (usuario_id) WHERE principal = 1;
CREATE INDEX ix_investigador_msc_codigo ON investigador_msc (codigo);
