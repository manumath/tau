-- PLAN §72, etapa 9: comentarios del piloto con usuarios reales. Con PORTAL_PILOTO=1, cada pantalla lleva «Comentar esta
-- pantalla». Se guarda el texto, la ruta sin parámetros (los números de la dirección se reemplazan por «:id»), el rol y el
-- día: no la cuenta ni la hora ni los datos de la pantalla. La Administración del sistema los marca como atendidos.
-- No cambia datos.
CREATE TABLE comentario_piloto (
    id           INTEGER PRIMARY KEY,
    ruta         TEXT    NOT NULL,
    rol          TEXT    NOT NULL,
    texto        TEXT    NOT NULL CHECK (length(texto) BETWEEN 3 AND 2000),
    dia          TEXT    NOT NULL DEFAULT (date('now', 'localtime')),
    atendido_en  TEXT,
    atendido_por INTEGER REFERENCES usuario(id),
    nota         TEXT
);
CREATE INDEX ix_comentario_piloto_pendientes ON comentario_piloto (atendido_en, dia);
