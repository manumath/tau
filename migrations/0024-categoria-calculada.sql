-- Fase 2, paso 4a (PLAN.md, sección 23): la categoría vigente se calcula del vínculo con el
-- Instituto (app.comun.vinculos.sql_categoria_vigente) en lugar de copiarse en `investigador`.
-- Así el módulo de vínculos (común) deja de escribir en la tabla del perfil de investigación, y
-- no hace falta sincronizarla cuando un periodo vence.
ALTER TABLE investigador DROP COLUMN categoria;
