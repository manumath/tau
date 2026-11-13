-- Retorno de las encuestas a quienes participaron (PLAN §67, etapa 7): una encuesta cerrada puede publicar «lo que encontramos» y
-- «lo que haremos», que ven quienes fueron invitados, junto con los resultados agregados (nunca las respuestas abiertas). En una
-- encuesta anónima solo se publica si alcanzó el mínimo de respuestas.
ALTER TABLE encuesta ADD COLUMN retorno              TEXT;      -- lo que encontramos
ALTER TABLE encuesta ADD COLUMN acciones             TEXT;      -- lo que haremos
ALTER TABLE encuesta ADD COLUMN retorno_publicado_en TEXT;
