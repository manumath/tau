-- Contexto boliviano (UMSA) y filiación, etapa E2.

-- Los montos se registran en bolivianos. (El valor por omisión de la columna sigue siendo 'CLP' en
-- el esquema; la aplicación siempre indica la moneda al crear un proyecto.)
UPDATE proyecto SET moneda = 'BOB' WHERE moneda = 'CLP';

-- ¿El autor del instituto firmó la publicación con la filiación del instituto (IIMAT, CMAT, FCPN o
-- UMSA; vale la doble filiación)? NULL = sin declarar. Solo para autores del instituto.
ALTER TABLE producto_autor ADD COLUMN filiacion_instituto INTEGER CHECK (filiacion_instituto IN (0, 1));
