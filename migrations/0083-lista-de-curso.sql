-- Lista de estudiantes por paralelo (PLAN §68, etapa 4).
--
-- La lista oficial la genera el sistema de notas (Kardex). Cuando ese sistema ofrezca una API restringida, TAU la consultará
-- en el momento y no guardará nada (`app/academico/listas.py`, proveedor «api»). Mientras tanto, la Dirección de Carrera o la
-- Coordinación cargan el CSV que entrega Kardex y esta tabla actúa como una copia temporal: se retira al concluir la gestión.
-- TAU no guarda notas ni asistencia; solo identifica a quienes están inscritos para que el docente de ese paralelo los vea.
CREATE TABLE lista_curso (
    id         INTEGER PRIMARY KEY,
    oferta_id  INTEGER NOT NULL REFERENCES oferta(id) ON DELETE CASCADE,
    ru         TEXT NOT NULL,                      -- registro universitario
    apellidos  TEXT NOT NULL,
    nombres    TEXT NOT NULL,
    correo     TEXT,
    cargado_en TEXT NOT NULL DEFAULT (datetime('now')),
    cargado_por INTEGER REFERENCES usuario(id),
    UNIQUE (oferta_id, ru)
);
