-- Catálogos desde la interfaz (PLAN.md, sección 47): tipos de actividad, tipos de producto e índices.
-- Decisión de la Dirección (2-oct-2026): los que ya existen son «del sistema» (el anexo, la Guía de
-- Antecedentes, el CV y las importaciones los reconocen por su nombre): solo se reordenan y se activan o
-- desactivan; en los índices, además, se puede cambiar si cuentan como indexado o arbitrado. Los que se
-- agreguen desde la interfaz se renombran y, si nadie los usó, se eliminan.

ALTER TABLE tipo_actividad ADD COLUMN del_sistema INTEGER NOT NULL DEFAULT 0 CHECK (del_sistema IN (0, 1));
ALTER TABLE tipo_producto  ADD COLUMN del_sistema INTEGER NOT NULL DEFAULT 0 CHECK (del_sistema IN (0, 1));
ALTER TABLE indice         ADD COLUMN del_sistema INTEGER NOT NULL DEFAULT 0 CHECK (del_sistema IN (0, 1));
UPDATE tipo_actividad SET del_sistema = 1;
UPDATE tipo_producto  SET del_sistema = 1;
UPDATE indice         SET del_sistema = 1;
