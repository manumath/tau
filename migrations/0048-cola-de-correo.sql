-- Cola persistente de correo (PLAN §56, etapa 4).
--
-- Antes, en modo smtp, cada correo esperaba en una cola en memoria: se perdía si la máquina se reiniciaba o
-- se desplegaba una versión nueva, y un fallo del servidor SMTP solo quedaba en el registro. Ahora cada
-- correo se guarda aquí dentro de la misma transacción que lo origina (si esta se revierte, el correo no
-- sale), se envía en cuanto se confirma y, si falla, el mantenimiento lo reintenta con esperas crecientes.
--
-- Privacidad: los correos llevan enlaces personales (ingreso, recuperación, encuestas). La fila se borra
-- al enviarse o al agotar los intentos; no queda un historial de mensajes enviados.
CREATE TABLE correo_pendiente (
    id                INTEGER PRIMARY KEY,
    para              TEXT    NOT NULL,
    asunto            TEXT    NOT NULL,
    mensaje           BLOB    NOT NULL,          -- el mensaje completo (EML), con su Message-ID fijo
    intentos          INTEGER NOT NULL DEFAULT 0,
    proximo_intento   TEXT    NOT NULL DEFAULT (datetime('now')),   -- UTC, como AHORA
    ultimo_error      TEXT,
    creado_en         TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_correo_pendiente_proximo ON correo_pendiente (proximo_intento);
