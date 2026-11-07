-- Página pública de indicadores (PLAN §57, etapa 9; decisión 6 del 7-nov-2026): la Dirección de Carrera marca en el marco
-- qué indicadores se publican. Ninguno se publica hasta que se marque.
ALTER TABLE indicador_calidad ADD COLUMN publico INTEGER NOT NULL DEFAULT 0 CHECK (publico IN (0, 1));
