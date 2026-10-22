-- Seguimiento de egresados (PLAN §50, etapa 4).
--
-- Quien se titula (`estudiante.estado = 'titulado'`, con fecha de titulación) pasa a ser egresado: no hay una tabla
-- aparte, se deduce. Se le hace seguimiento a los 6 meses, 1, 3 y 5 años de titularse con una encuesta por hito.
--
-- `encuesta.hito`: encuesta de seguimiento continuo. Se abre sin invitar a nadie y recibe una invitación por
-- egresado cuando éste cumple el hito. Solo puede haber una abierta por hito.
-- `pregunta.clave`: de qué trata la pregunta (situación laboral, posgrado, utilidad…), para calcular indicadores sin
-- depender del texto.
-- `seguimiento_egresado`: qué hito se le invitó a cada egresado (o se omitió: si al activar el seguimiento ya pasaron
-- varios hitos, se invita solo al último y los anteriores quedan omitidos, para no escribirle cuatro veces).
ALTER TABLE encuesta ADD COLUMN hito TEXT CHECK (hito IN ('6m', '1a', '3a', '5a'));
ALTER TABLE pregunta ADD COLUMN clave TEXT;
CREATE UNIQUE INDEX ux_encuesta_hito ON encuesta (hito) WHERE hito IS NOT NULL AND estado != 'cerrada';

CREATE TABLE seguimiento_egresado (
    externo_id      INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    hito            TEXT NOT NULL CHECK (hito IN ('6m', '1a', '3a', '5a')),
    encuesta_id     INTEGER REFERENCES encuesta(id) ON DELETE SET NULL,
    estado          TEXT NOT NULL CHECK (estado IN ('invitado', 'omitido')),
    programado_para TEXT NOT NULL,            -- fecha del hito (titulación + 6 meses, 1, 3 o 5 años)
    creado_en       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (externo_id, hito)
);
