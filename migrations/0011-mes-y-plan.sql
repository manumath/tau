-- Ajustes tras las pruebas, etapa D: informes por periodo (octubre–septiembre) y por rango.
--
-- Mes de publicación (opcional) de los productos: sin él, un producto no se puede ubicar en un
-- periodo que no coincide con el año calendario.
ALTER TABLE producto ADD COLUMN mes INTEGER CHECK (mes BETWEEN 1 AND 12);

-- Seguimiento del plan: cada actividad prevista de una propuesta aceptada puede marcarse como
-- realizada, enlazándola con la actividad registrada.
ALTER TABLE propuesta_actividad_prevista ADD COLUMN actividad_id INTEGER
    REFERENCES actividad(id) ON DELETE SET NULL;
