-- Designación de la comisión calificadora de las auxiliaturas (PLAN §70, etapa 3).
--
-- El art. 15 del reglamento de 2023 pide que la comisión de méritos y examen de competencia la designe el Consejo de Carrera y la apruebe
-- el Consejo Facultativo. TAU guarda el número de ambas resoluciones por convocatoria (una sola resolución suele designar las comisiones
-- de todos sus ítems); sin la del Consejo de Carrera no se cierra la recepción para empezar a evaluar.
ALTER TABLE convocatoria_auxiliatura ADD COLUMN comision_resolucion TEXT;       -- Consejo de Carrera
ALTER TABLE convocatoria_auxiliatura ADD COLUMN comision_resolucion_hcf TEXT;   -- Consejo Facultativo (aprobación)
