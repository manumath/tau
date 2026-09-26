-- Filiación y pertenencia, etapa E3: ¿la publicación agradece al proyecto? (lo exigen los fondos,
-- además de la filiación). Por producto y proyecto; NULL = sin declarar.
ALTER TABLE producto_proyecto ADD COLUMN agradece INTEGER CHECK (agradece IN (0, 1));
