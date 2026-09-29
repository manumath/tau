-- Centro de avisos (PLAN.md, sección 33): cada aviso queda en el sistema (campana y página «Avisos»)
-- y, según la preferencia de cada persona, se envía por correo al momento, en un resumen semanal o
-- no se envía. Reemplaza la casilla «Avisos por correo» (avisos_correo): desactivada = «nunca».

CREATE TABLE notificacion (
    id          INTEGER PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    asunto      TEXT NOT NULL,
    texto       TEXT,
    url         TEXT,                          -- ruta dentro del sistema (p. ej. /proyectos/3?tab=pendientes)
    creada_en   TEXT NOT NULL DEFAULT (datetime('now')),
    leida_en    TEXT,
    resumida_en TEXT                           -- ya incluida en un resumen semanal por correo
);
CREATE INDEX ix_notificacion_usuario ON notificacion (usuario_id, leida_en, creada_en);

ALTER TABLE usuario ADD COLUMN frecuencia_avisos TEXT NOT NULL DEFAULT 'inmediato'
    CHECK (frecuencia_avisos IN ('inmediato', 'semanal', 'nunca'));
ALTER TABLE usuario ADD COLUMN ultimo_resumen TEXT;
UPDATE usuario SET frecuencia_avisos = 'nunca' WHERE avisos_correo = 0;
ALTER TABLE usuario DROP COLUMN avisos_correo;
