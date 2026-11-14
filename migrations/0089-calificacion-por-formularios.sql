-- Calificación de las auxiliaturas según los formularios del reglamento de 2023 (PLAN §70, etapa 4).
--
-- Los méritos (30 puntos) se califican con los formularios 2-1, 2-2 y 2-3 (seis secciones, cada una con su tope) y el examen oral (35) con la
-- rúbrica del formulario 4 (cinco criterios). Cada miembro del tribunal anota el detalle —cuántos cursos, años de experiencia, puntos por
-- criterio— y el sistema calcula su calificación de la fase, que sigue siendo la de `calificacion_auxiliatura` (el promedio de al menos tres
-- miembros). Las convocatorias del reglamento de 2021 no usan estas tablas. El sorteo del examen oral guarda los cinco temas propuestos y la
-- hora del sorteo (el postulante diserta dentro de las 24 horas: art. 18, b) y el orden y la hora de participación de cada postulante
-- (formulario 3).
CREATE TABLE calificacion_detalle (
    postulacion_id INTEGER NOT NULL REFERENCES postulacion_auxiliatura(id) ON DELETE CASCADE,
    fase           TEXT NOT NULL CHECK (fase IN ('meritos', 'oral')),
    miembro_id     INTEGER NOT NULL REFERENCES usuario(id),
    clave          TEXT NOT NULL,           -- la línea del formulario (p. ej. '1a', '4') o el criterio del oral
    cantidad       REAL NOT NULL CHECK (cantidad >= 0),
    PRIMARY KEY (postulacion_id, fase, miembro_id, clave)
);
ALTER TABLE item_auxiliatura ADD COLUMN temas_oral TEXT;           -- los cinco temas propuestos, uno por línea
ALTER TABLE item_auxiliatura ADD COLUMN tema_oral_en TEXT;         -- cuándo se sorteó (UTC)
ALTER TABLE postulacion_auxiliatura ADD COLUMN orden_oral INTEGER;
ALTER TABLE postulacion_auxiliatura ADD COLUMN hora_oral TEXT;
