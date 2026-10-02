-- Premios, arbitraje de artículos y prestación de servicios (PLAN.md, sección 40): evidencia que
-- IAC-CINDA pide (2.2.1 d, 3.4.3; hoja 28 de la Guía de Antecedentes) y que no tenía dónde
-- registrarse. Decisión de la Dirección (1-oct-2026): son tipos de actividad, con roles nuevos y
-- unos campos propios.
--
-- - Arbitraje: una entrada por revista y año (1 de enero a 31 de diciembre), con la cantidad de
--   artículos arbitrados; la revista va en `institucion` y, si está en el catálogo, en `revista_id`.
-- - Prestación de servicios: la contraparte va en `institucion`; monto, moneda, origen del
--   financiamiento (interno o externo) e ingresos que generó para la unidad.

INSERT INTO tipo_actividad (nombre, orden) VALUES
    ('Premio o distinción', 130),
    ('Arbitraje de artículos', 140),
    ('Prestación de servicios', 150);

ALTER TABLE actividad ADD COLUMN cantidad INTEGER CHECK (cantidad IS NULL OR cantidad >= 0);
ALTER TABLE actividad ADD COLUMN revista_id INTEGER REFERENCES revista(id) ON DELETE SET NULL;
ALTER TABLE actividad ADD COLUMN monto INTEGER CHECK (monto IS NULL OR monto >= 0);
ALTER TABLE actividad ADD COLUMN moneda TEXT CHECK (moneda IS NULL OR moneda IN ('BOB', 'USD'));
ALTER TABLE actividad ADD COLUMN financiamiento TEXT CHECK (financiamiento IS NULL OR financiamiento IN ('interno', 'externo'));
ALTER TABLE actividad ADD COLUMN ingresos INTEGER CHECK (ingresos IS NULL OR ingresos >= 0);

-- Roles nuevos de los participantes: distinguido(a) (premio), revisor(a) (arbitraje) y responsable
-- (servicio). SQLite no cambia un CHECK: se reconstruye la tabla (nada la referencia).
CREATE TABLE actividad_participante_nueva (
    actividad_id    INTEGER NOT NULL REFERENCES actividad(id) ON DELETE CASCADE,
    orden           INTEGER NOT NULL,
    investigador_id INTEGER REFERENCES usuario(id),
    externo_id      INTEGER REFERENCES persona_externa(id),
    rol             TEXT    NOT NULL DEFAULT 'asistente'
                    CHECK (rol IN ('organizador', 'expositor', 'asistente', 'comite', 'distinguido', 'revisor',
                                   'responsable')),
    PRIMARY KEY (actividad_id, orden),
    CHECK ((investigador_id IS NULL) <> (externo_id IS NULL))
);
INSERT INTO actividad_participante_nueva (actividad_id, orden, investigador_id, externo_id, rol)
    SELECT actividad_id, orden, investigador_id, externo_id, rol FROM actividad_participante;
DROP TABLE actividad_participante;
ALTER TABLE actividad_participante_nueva RENAME TO actividad_participante;
CREATE INDEX ix_actividad_participante_inv ON actividad_participante (investigador_id);
