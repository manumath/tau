-- Productos y actividades que IAC-CINDA considera evidencia de I+D+i (criterio 3.6.3, d a j).

-- Productos: patentes y traducciones (sin arbitraje: no cuentan como artículos, pero se
-- registran e informan aparte).
INSERT INTO tipo_producto (nombre, admite_revision, orden) VALUES
    ('Patente', 0, 100),
    ('Traducción', 0, 110);

-- Actividades: estancias y pasantías en centros de investigación (se renombra la estadía para
-- usar la denominación del criterio), transferencia de conocimiento y redes de investigación.
UPDATE tipo_actividad SET nombre = 'Estancia o pasantía de investigación' WHERE nombre = 'Estadía de investigación';
INSERT INTO tipo_actividad (nombre, orden) VALUES
    ('Transferencia de conocimiento', 110),
    ('Participación en red de investigación', 120);
