-- Ajustes tras las pruebas, etapa B: proyectos individuales e institucionales.
-- Los proyectos existentes pasan a ser individuales (decisión del instituto).

ALTER TABLE proyecto ADD COLUMN tipo TEXT NOT NULL DEFAULT 'individual'
    CHECK (tipo IN ('individual', 'institucional'));
CREATE INDEX ix_proyecto_tipo ON proyecto (tipo, estado);
