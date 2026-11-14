-- Modalidades, segunda convocatoria y requisitos opcionales de las auxiliaturas (PLAN §70, etapa 2).
--
-- El reglamento de 2023 (art. 7) reconoce auxiliares de docencia, de investigación (con la Beca Tesis) y de interacción social: la
-- modalidad admite ahora los cuatro valores (hay que recrear la tabla para cambiar el CHECK; los hijos —ítems y requisitos— conservan
-- sus filas porque se enlazan por id). Una segunda convocatoria (arts. 13 y 14) recuerda de cuál primera viene. Un requisito puede ser
-- opcional (p. ej. el certificado de conclusión, solo para egresados: art. 23, 4) y los que verifica el sistema dicen cuál verifican.
DROP TABLE IF EXISTS convocatoria_auxiliatura_nueva;
CREATE TABLE convocatoria_auxiliatura_nueva (
    id          INTEGER PRIMARY KEY,
    gestion_id  INTEGER NOT NULL REFERENCES gestion_academica(id),
    modalidad   TEXT NOT NULL CHECK (modalidad IN ('docencia', 'investigacion', 'interaccion_social', 'beca_tesis')),
    numero      INTEGER NOT NULL DEFAULT 1 CHECK (numero IN (1, 2)),
    titulo      TEXT NOT NULL,
    publicacion TEXT,
    cierre      TEXT,
    examen      TEXT,
    lugar       TEXT,
    resolucion  TEXT,
    estado      TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'publicada', 'concluida')),
    creado_por  INTEGER NOT NULL REFERENCES usuario(id),
    creado_en   TEXT NOT NULL DEFAULT (datetime('now')),
    reglamento  TEXT NOT NULL DEFAULT 'hcu_251_2021' CHECK (reglamento IN ('hcu_251_2021', 'hcu_424_2023')),
    recepcion_lugar   TEXT,
    recepcion_horario TEXT,
    resolucion_hcf    TEXT,
    primera_id  INTEGER REFERENCES convocatoria_auxiliatura(id) ON DELETE SET NULL   -- la primera convocatoria de esta segunda
);
INSERT INTO convocatoria_auxiliatura_nueva (id, gestion_id, modalidad, numero, titulo, publicacion, cierre, examen, lugar, resolucion,
                                            estado, creado_por, creado_en, reglamento, recepcion_lugar, recepcion_horario, resolucion_hcf)
    SELECT id, gestion_id, modalidad, numero, titulo, publicacion, cierre, examen, lugar, resolucion,
           estado, creado_por, creado_en, reglamento, recepcion_lugar, recepcion_horario, resolucion_hcf FROM convocatoria_auxiliatura;
DROP TABLE convocatoria_auxiliatura;
ALTER TABLE convocatoria_auxiliatura_nueva RENAME TO convocatoria_auxiliatura;

ALTER TABLE requisito_auxiliatura ADD COLUMN opcional INTEGER NOT NULL DEFAULT 0 CHECK (opcional IN (0, 1));
ALTER TABLE requisito_auxiliatura ADD COLUMN clave TEXT;    -- de los que verifica el sistema: 'gestiones' (sin valor: el de 2021) o 'materias'
