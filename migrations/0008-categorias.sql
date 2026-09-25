-- Ajustes tras las pruebas, etapa A: categoría de cada investigador(a).
-- La asigna la administración. Vacía = «sin categoría» (las cuentas existentes quedan así
-- hasta que la administración la complete).

ALTER TABLE investigador ADD COLUMN categoria TEXT
    CHECK (categoria IN ('titular', 'contratado', 'interino', 'invitado', 'externo'));
