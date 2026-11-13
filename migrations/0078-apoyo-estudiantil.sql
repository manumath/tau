-- Apoyo estudiantil (PLAN §67, etapa 8; decisión del 13-nov-2026).
--
-- El estudiante pide apoyo en un clic y ve las señales que TAU observa de él (se calculan al momento, no se guardan). Su tutor(a)
-- y la Dirección de Carrera ven los CASOS abiertos: los que él pidió o los que su tutor(a) o la Dirección abrieron avisándole.
-- Ningún caso dura más de un semestre sin renovarse (`vence_el`). La conversación del caso la ven las dos partes: no hay notas
-- ocultas al estudiante. Las notas confidenciales de tutoría no entran aquí.
CREATE TABLE caso_apoyo (
    id            INTEGER PRIMARY KEY,
    externo_id    INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    origen        TEXT NOT NULL CHECK (origen IN ('estudiante', 'tutor', 'direccion')),
    abierto_por   INTEGER NOT NULL REFERENCES usuario(id),
    tema          TEXT NOT NULL CHECK (tema IN ('academico', 'economico', 'salud', 'vocacional', 'convivencia', 'otro')),
    motivo        TEXT NOT NULL,
    estado        TEXT NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto', 'en_seguimiento', 'cerrado')),
    derivacion    TEXT NOT NULL DEFAULT 'ninguna',
    vence_el      TEXT NOT NULL,                      -- 'AAAA-MM-DD'; pasada esta fecha sin renovarse, el caso vence
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT,
    cerrado_en    TEXT
);
CREATE INDEX ix_caso_apoyo_externo ON caso_apoyo (externo_id, estado);

CREATE TABLE caso_apoyo_mensaje (
    id          INTEGER PRIMARY KEY,
    caso_id     INTEGER NOT NULL REFERENCES caso_apoyo(id) ON DELETE CASCADE,
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id),
    del_estudiante INTEGER NOT NULL CHECK (del_estudiante IN (0, 1)),
    texto       TEXT NOT NULL,
    creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);
