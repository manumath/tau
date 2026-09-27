-- Fase 3, paso 3.1 (PLAN.md, sección 24): catálogo curricular.
--
-- Programa (Licenciatura en Matemática…) → plan de estudios con vigencia (el plan 2017 y el nuevo
-- coexisten mientras haya estudiantes en el antiguo) → asignaturas ubicadas en el plan (semestre,
-- tipo, horas o créditos) con sus requisitos. La asignatura es un catálogo único por sigla: las
-- horas son del plan (MAT-278 no tiene las mismas horas en todos los planes).
CREATE TABLE programa (
    id        INTEGER PRIMARY KEY,
    nombre    TEXT NOT NULL UNIQUE,
    nivel     TEXT NOT NULL CHECK (nivel IN ('licenciatura', 'maestria', 'doctorado', 'especialidad', 'diplomado')),
    unidad_id INTEGER NOT NULL REFERENCES unidad(id)
);

CREATE TABLE plan_estudios (
    id                INTEGER PRIMARY KEY,
    programa_id       INTEGER NOT NULL REFERENCES programa(id),
    nombre            TEXT NOT NULL,                 -- «Plan 2017»
    resolucion        TEXT,                          -- «HCU 041/2017»
    vigente_desde     INTEGER NOT NULL,              -- año
    vigente_hasta     INTEGER,                       -- año del último ingreso (NULL = vigente)
    sistema           TEXT NOT NULL CHECK (sistema IN ('horas', 'creditos')),
    semanas_semestre  INTEGER,                       -- sistema de horas: horas semanales × semanas
    horas_por_credito INTEGER,                       -- sistema de créditos
    nota_minima       INTEGER,
    -- Totales que declara el documento del plan (para comparar con la suma de sus asignaturas).
    total_teoricas    INTEGER,
    total_practicas   INTEGER,
    total_laboratorio INTEGER,
    total_creditos    INTEGER,
    creado_en         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (programa_id, nombre)
);

CREATE TABLE asignatura (
    id           INTEGER PRIMARY KEY,
    sigla        TEXT NOT NULL UNIQUE,               -- «MAT-111»
    nombre       TEXT NOT NULL,
    departamento TEXT NOT NULL,                      -- prefijo de la sigla: MAT, FIS, INF…
    de_la_carrera INTEGER NOT NULL DEFAULT 1 CHECK (de_la_carrera IN (0, 1))  -- 0: la dicta otra unidad
);

-- Ubicación de una asignatura en un plan. Las casillas de electiva («5.º semestre: Electiva A»)
-- no tienen asignatura: se llenan con una de la lista de electivas del mismo grupo.
CREATE TABLE plan_asignatura (
    id                INTEGER PRIMARY KEY,
    plan_id           INTEGER NOT NULL REFERENCES plan_estudios(id) ON DELETE CASCADE,
    asignatura_id     INTEGER REFERENCES asignatura(id),
    tipo              TEXT NOT NULL CHECK (tipo IN ('obligatoria', 'trabajo_final', 'electiva', 'electiva_a',
                                                    'electiva_b', 'casilla_electiva', 'casilla_electiva_a',
                                                    'casilla_electiva_b')),
    semestre          INTEGER,
    ciclo             TEXT,
    horas_teoricas    INTEGER,
    horas_practicas   INTEGER,
    horas_laboratorio INTEGER,
    creditos          INTEGER,
    orden             INTEGER NOT NULL DEFAULT 0,
    CHECK ((asignatura_id IS NULL) = (tipo LIKE 'casilla%'))
);
CREATE UNIQUE INDEX ux_plan_asignatura ON plan_asignatura (plan_id, asignatura_id) WHERE asignatura_id IS NOT NULL;

-- Requisito formal: otra asignatura (por sigla, tal como la nombra el plan, aunque no exista) o una
-- condición («egresado»).
CREATE TABLE requisito (
    id                 INTEGER PRIMARY KEY,
    plan_asignatura_id INTEGER NOT NULL REFERENCES plan_asignatura(id) ON DELETE CASCADE,
    sigla              TEXT,
    condicion          TEXT CHECK (condicion IN ('egresado')),
    CHECK ((sigla IS NULL) <> (condicion IS NULL))
);

-- Inconsistencias del documento del plan, marcadas para revisión de la Dirección Académica.
CREATE TABLE observacion_plan (
    id           INTEGER PRIMARY KEY,
    plan_id      INTEGER NOT NULL REFERENCES plan_estudios(id) ON DELETE CASCADE,
    tipo         TEXT NOT NULL,                      -- totales, requisito, duplicada, nombre, documento
    detalle      TEXT NOT NULL,
    estado       TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'resuelta')),
    resolucion   TEXT,
    resuelta_por INTEGER REFERENCES usuario(id),
    resuelta_en  TEXT,
    creado_en    TEXT NOT NULL DEFAULT (datetime('now'))
);
