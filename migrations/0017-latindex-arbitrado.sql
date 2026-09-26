-- Decisión del instituto: Latindex Catálogo no cuenta como indexado, pero sí como arbitrado (una
-- revista que figura en él tiene arbitraje certificado aunque el catálogo no diga «revisión por pares»).
ALTER TABLE indice ADD COLUMN cuenta_como_arbitrado INTEGER NOT NULL DEFAULT 0
    CHECK (cuenta_como_arbitrado IN (0, 1));
UPDATE indice SET cuenta_como_arbitrado = 1 WHERE nombre = 'Latindex Catálogo';
