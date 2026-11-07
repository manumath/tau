-- Aseguramiento de la Calidad (PLAN §57, etapa 8): los datos que pedían las políticas de la UMSA y que el sistema no
-- registraba. Con ellos, seis indicadores del marco de la Carrera pasan de manuales a calculados.
--
-- 1. Encuestas a académicos y a empleadores: `encuesta.publico` admite 'docentes' (académicos vinculados a la Carrera) y
--    'empleadores' (registro de empleadores), y `encuesta.tipo`, 'docentes' y 'empleadores'. SQLite no cambia un CHECK:
--    se recrea la tabla conservando todas las encuestas (fastmigrate corre sin claves foráneas activas, así que las
--    preguntas, invitaciones y respuestas que la referencian no se tocan).
-- 2. `empleador`: organizaciones que emplean a egresados y a quién escribirle (persona externa con correo).
-- 3. `capacitacion`: cursos, talleres y diplomados que siguió cada persona de la Carrera (Política de Calidad, objetivo 4).
-- 4. `convenio` y `actividad_convenio`: convenios con otras instituciones y lo que se hizo con ellos cada año
--    (Política de Internacionalización: alianzas).
-- 5. `impacto_proyecto`: beneficiarios e impacto comprobado de los proyectos de interacción social (objetivo 6).
--
-- Se puede repetir sin daño (IF NOT EXISTS): una primera versión falló en la última sentencia después de crear las
-- tablas, y una base que quedó así debe completar la migración al volver a correrla.
DROP TABLE IF EXISTS encuesta_nueva;
CREATE TABLE encuesta_nueva (
    id            INTEGER PRIMARY KEY,
    titulo        TEXT NOT NULL,
    descripcion   TEXT,
    tipo          TEXT NOT NULL CHECK (tipo IN ('satisfaccion', 'clima', 'bienestar', 'abandono', 'egresados',
                                                'perfil_egreso', 'docentes', 'empleadores', 'otra')),
    anonima       INTEGER NOT NULL CHECK (anonima IN (0, 1)),
    publico       TEXT NOT NULL CHECK (publico IN ('estudiantes', 'egresados', 'docentes', 'empleadores')),
    cohorte_desde INTEGER,                       -- año de ingreso (filtro opcional; solo estudiantes y egresados)
    cohorte_hasta INTEGER,
    cierra_el     TEXT,                          -- fecha límite (AAAA-MM-DD), opcional
    estado        TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'abierta', 'cerrada')),
    creada_por    INTEGER REFERENCES usuario(id),
    creada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    abierta_en    TEXT,
    cerrada_en    TEXT,
    hito          TEXT CHECK (hito IN ('6m', '1a', '3a', '5a'))
);
INSERT INTO encuesta_nueva (id, titulo, descripcion, tipo, anonima, publico, cohorte_desde, cohorte_hasta, cierra_el, estado,
                            creada_por, creada_en, abierta_en, cerrada_en, hito)
    SELECT id, titulo, descripcion, tipo, anonima, publico, cohorte_desde, cohorte_hasta, cierra_el, estado,
           creada_por, creada_en, abierta_en, cerrada_en, hito FROM encuesta;
DROP TABLE encuesta;
ALTER TABLE encuesta_nueva RENAME TO encuesta;
CREATE UNIQUE INDEX IF NOT EXISTS ux_encuesta_hito ON encuesta (hito) WHERE hito IS NOT NULL AND estado != 'cerrada';

CREATE TABLE IF NOT EXISTS empleador (
    id            INTEGER PRIMARY KEY,
    externo_id    INTEGER NOT NULL UNIQUE REFERENCES persona_externa(id),   -- la persona de contacto (con su correo)
    organizacion  TEXT NOT NULL,
    sector        TEXT NOT NULL CHECK (sector IN ('educacion', 'investigacion', 'publico', 'privado', 'otro')),
    cargo         TEXT,                                                     -- del contacto
    activo        INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),       -- solo los activos reciben encuestas
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS capacitacion (
    id             INTEGER PRIMARY KEY,
    usuario_id     INTEGER NOT NULL REFERENCES usuario(id),
    titulo         TEXT NOT NULL,
    institucion    TEXT,
    area           TEXT NOT NULL CHECK (area IN ('disciplinar', 'pedagogica', 'investigacion', 'gestion', 'otra')),
    horas          INTEGER CHECK (horas IS NULL OR horas BETWEEN 1 AND 2000),
    fecha_inicio   TEXT NOT NULL,
    fecha_fin      TEXT NOT NULL,                -- cuenta en el año en que concluyó
    evidencia_id   INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (fecha_fin >= fecha_inicio)
);
CREATE INDEX IF NOT EXISTS ix_capacitacion_fin ON capacitacion (fecha_fin);
CREATE INDEX IF NOT EXISTS ix_capacitacion_usuario ON capacitacion (usuario_id);

CREATE TABLE IF NOT EXISTS convenio (
    id             INTEGER PRIMARY KEY,
    contraparte    TEXT NOT NULL,
    pais           TEXT,
    ambito         TEXT NOT NULL CHECK (ambito IN ('nacional', 'internacional')),
    tipo           TEXT NOT NULL CHECK (tipo IN ('marco', 'especifico')),
    objeto         TEXT,
    fecha_firma    TEXT NOT NULL,
    vigente_hasta  TEXT,                         -- vacío: sin fecha de término
    evidencia_id   INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,   -- el texto firmado
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (vigente_hasta IS NULL OR vigente_hasta >= fecha_firma)
);

CREATE TABLE IF NOT EXISTS actividad_convenio (
    id             INTEGER PRIMARY KEY,
    convenio_id    INTEGER NOT NULL REFERENCES convenio(id) ON DELETE CASCADE,
    fecha          TEXT NOT NULL,
    descripcion    TEXT NOT NULL,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_actividad_convenio ON actividad_convenio (convenio_id, fecha);

CREATE TABLE IF NOT EXISTS impacto_proyecto (
    proyecto_id    INTEGER PRIMARY KEY REFERENCES proyecto(id) ON DELETE CASCADE,
    beneficiarios  INTEGER CHECK (beneficiarios IS NULL OR beneficiarios >= 0),
    descripcion    TEXT,                         -- a quiénes llegó y qué cambió
    comprobado     INTEGER NOT NULL DEFAULT 0 CHECK (comprobado IN (0, 1)),
    evidencia_id   INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (comprobado = 0 OR evidencia_id IS NOT NULL)
);

-- Indicadores que ahora calcula el sistema (solo si siguen manuales y sin cifras registradas a mano).
UPDATE indicador_calidad SET fuente = 'auto:' || CASE codigo
        WHEN 'D2.4.a' THEN 'perfil_titulados'
        WHEN 'D2.4.b' THEN 'perfil_empleadores'
        WHEN 'D4.3.a' THEN 'personal_capacitado'
        WHEN 'D6.4.a' THEN 'impacto_interaccion_social'
        WHEN 'D7.4.a' THEN 'convenios_activos'
        WHEN 'D8.3.b' THEN 'satisfaccion_empleadores' END
 WHERE codigo IN ('D2.4.a', 'D2.4.b', 'D4.3.a', 'D6.4.a', 'D7.4.a', 'D8.3.b') AND fuente = 'manual'
   AND NOT EXISTS (SELECT 1 FROM valor_indicador v WHERE v.indicador_id = indicador_calidad.id)
   AND criterio_id IN (SELECT c.id FROM criterio_calidad c JOIN dimension_calidad d ON d.id = c.dimension_id
                        JOIN marco_calidad m ON m.id = d.marco_id
                       WHERE m.unidad_id = (SELECT id FROM unidad WHERE sigla = 'CMAT'));
