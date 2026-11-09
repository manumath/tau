-- Revocación de sesiones en el servidor (PLAN §62, etapa 1; auditoría del 8-nov-2026, hallazgo SEC-01).
--
-- La sesión es una cookie firmada sin estado: antes, «Salir» o cambiar la contraseña no invalidaban una copia de la
-- cookie. Cada sesión guarda ahora la versión de su cuenta al ingresar; salir, cambiar o restablecer la contraseña
-- la incrementan y toda cookie con una versión anterior deja de valer. Las sesiones abiertas antes de esta migración
-- valen como versión 0 (nadie pierde la sesión al desplegar).
ALTER TABLE usuario ADD COLUMN sesion_version INTEGER NOT NULL DEFAULT 0;

-- Límite de intentos de ingreso por IP (hallazgo SEC-02): se cuentan los fallos recientes de cada dirección.
CREATE INDEX ix_intento_login_ip_fecha ON intento_login (ip, fecha);
