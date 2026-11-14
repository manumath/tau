-- Auxiliaturas según el Reglamento Específico de Auxiliares Académicos del Pregrado (PLAN §70, etapa 1).
--
-- La Res. HCU 424/2023 (modificada por la 364/2025) dejó sin efecto el reglamento de 2021 en que se basó el módulo (§58). Cada
-- convocatoria guarda con qué reglamento se hizo: las ya cargadas conservan el de 2021 (mínimos, categorías y plazos de entonces,
-- sin recalcular nada) y las nuevas nacen con el de 2023. Además, lo que el art. 11 pide que diga la convocatoria: dónde y en qué
-- horario se reciben los documentos, y la resolución del Consejo Facultativo que la aprueba (art. 27).
ALTER TABLE convocatoria_auxiliatura ADD COLUMN reglamento TEXT NOT NULL DEFAULT 'hcu_251_2021'
    CHECK (reglamento IN ('hcu_251_2021', 'hcu_424_2023'));
ALTER TABLE convocatoria_auxiliatura ADD COLUMN recepcion_lugar TEXT;     -- art. 11, e)
ALTER TABLE convocatoria_auxiliatura ADD COLUMN recepcion_horario TEXT;   -- art. 11, e)
ALTER TABLE convocatoria_auxiliatura ADD COLUMN resolucion_hcf TEXT;      -- resolución del Consejo Facultativo (art. 27, 1)
