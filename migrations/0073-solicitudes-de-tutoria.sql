-- Tutoría desde el estudiante (PLAN §67, etapa 3).
--
-- El estudiante pide una reunión a su tutor(a) y ve su estado; el tutor la programa o la atiende. Esto NO es una reunión
-- registrada (esas, con sus notas, siguen siendo confidenciales del tutor y de la Dirección): es solo la solicitud.
CREATE TABLE tutoria_solicitud (
    id            INTEGER PRIMARY KEY,
    externo_id    INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    tutor_id      INTEGER NOT NULL REFERENCES usuario(id),
    tema          TEXT NOT NULL CHECK (tema IN ('academico', 'economico', 'salud', 'vocacional', 'convivencia', 'otro')),
    mensaje       TEXT,
    estado        TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'programada', 'atendida', 'cancelada')),
    fecha_reunion TEXT,                         -- 'AAAA-MM-DDTHH:MM' cuando el tutor la programa
    respuesta     TEXT,                         -- lo que el tutor le dice (lugar, indicaciones)
    creada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    actualizada_en TEXT
);
CREATE INDEX ix_tutoria_solicitud_tutor ON tutoria_solicitud (tutor_id, estado);
CREATE INDEX ix_tutoria_solicitud_externo ON tutoria_solicitud (externo_id, estado);
