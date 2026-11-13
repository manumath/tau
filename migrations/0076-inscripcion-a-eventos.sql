-- Eventos con inscripción, cupos, lista de espera y certificado de participación (PLAN §67, etapa 6).
--
-- Un evento de «Comunicados y eventos» puede abrir inscripción: con cupos (vacío = sin límite) y, al llenarse, lista de espera
-- (si alguien cancela entra el primero de la lista). Si entrega certificado, lo recibe quien estuvo inscrito y cuya asistencia
-- registró el organizador (`comunicado_destinatario.asistio`, que ya existía). `horas` son las horas académicas que consigna.
ALTER TABLE comunicado ADD COLUMN inscripcion INTEGER NOT NULL DEFAULT 0 CHECK (inscripcion IN (0, 1));
ALTER TABLE comunicado ADD COLUMN cupos       INTEGER CHECK (cupos IS NULL OR cupos > 0);
ALTER TABLE comunicado ADD COLUMN certificado INTEGER NOT NULL DEFAULT 0 CHECK (certificado IN (0, 1));
ALTER TABLE comunicado ADD COLUMN horas       INTEGER CHECK (horas IS NULL OR horas > 0);

CREATE TABLE inscripcion_evento (
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id) ON DELETE CASCADE,
    usuario_id    INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    estado        TEXT NOT NULL CHECK (estado IN ('inscrito', 'espera')),
    creada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (comunicado_id, usuario_id)
);
