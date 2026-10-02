-- Áreas MSC2020 de los productos (PLAN.md, sección 45). Decisión de la Dirección (2-oct-2026): como en
-- las revistas y en zbMATH, un código principal y hasta 4 secundarios, de cualquier nivel del catálogo
-- (11-XX, 11Mxx, 11M06). El principal es el de `orden` 0; los informes agrupan por su sección (los dos
-- primeros caracteres del código). Los productos existentes quedan sin clasificar.

CREATE TABLE producto_msc (
    producto_id INTEGER NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    codigo      TEXT    NOT NULL REFERENCES msc(codigo),
    orden       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (producto_id, codigo)
);
CREATE INDEX ix_producto_msc_codigo ON producto_msc (codigo);
