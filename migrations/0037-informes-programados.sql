-- Informes programados (PLAN.md, sección 39): la preparación del semestre, la carga docente, la
-- memoria anual y la calidad de datos se envían solos, en fechas fijas, a quienes tienen el rol.
-- Esta tabla registra cada envío (informe + ocasión, p. ej. 'preparacion' + 'I-2027:4 semanas')
-- para que salga una sola vez aunque la revisión corra cada hora.

CREATE TABLE informe_programado (
    informe       TEXT NOT NULL,
    ocasion       TEXT NOT NULL,
    enviado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    destinatarios INTEGER NOT NULL DEFAULT 0,   -- a cuántas personas llegó (0: no había nada que avisar)
    PRIMARY KEY (informe, ocasion)
);
