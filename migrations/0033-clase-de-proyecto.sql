-- Los proyectos institucionales son de dos clases: de investigación o de interacción social
-- (extensión). Los individuales no llevan clase. Los institucionales existentes son de investigación.
ALTER TABLE proyecto ADD COLUMN clase TEXT
    CHECK (clase IS NULL OR clase IN ('investigacion', 'interaccion_social'));
UPDATE proyecto SET clase = 'investigacion' WHERE tipo = 'institucional';
