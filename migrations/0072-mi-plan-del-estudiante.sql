-- «Mi plan de estudios» del estudiante (PLAN §67, etapa 1; decisión del 13-nov-2026).
--
-- TAU no guarda materias cursadas ni notas (son de Seguimiento Académico). Esto es una ayuda PERSONAL: el estudiante marca
-- las asignaturas que aprobó para ver su avance en el plan y qué puede cursar. Las marcas son privadas: nunca van a informes
-- ni a la Dirección. Si el estudiante lo decide (`comparte_plan_tutor`), su tutor las ve en las reuniones. Se marcan por
-- asignatura (el catálogo es común a todos los planes), no por plan.
CREATE TABLE estudiante_aprobada (
    externo_id    INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id),
    marcada_en    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (externo_id, asignatura_id)
);
ALTER TABLE cuenta_estudiante ADD COLUMN comparte_plan_tutor INTEGER NOT NULL DEFAULT 0
    CHECK (comparte_plan_tutor IN (0, 1));
