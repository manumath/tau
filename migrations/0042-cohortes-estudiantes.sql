-- Cohortes y estado de los estudiantes de la Carrera (PLAN §49, etapa 1).
--
-- La tabla `estudiante` guardaba periodos de estudio para la investigación (PLAN §18). Ahora cada
-- periodo de licenciatura del programa propio puede llevar además su cohorte de ingreso, su estado y
-- los datos de admisión que piden las hojas 3 a 6 de la Guía de Antecedentes de IAC-CINDA. No se
-- guardan materias ni notas (son del sistema de Seguimiento Académico). La clave que une ambos
-- sistemas es el registro universitario.
--
-- Matrícula: no se guarda por ciclo. Un estudiante estuvo matriculado desde su cohorte hasta su
-- último ciclo matriculado (vacío = sigue cursando). Los congelamientos intermedios no se registran.
-- Privacidad: no se guarda la fecha de nacimiento ni el CI; el CSV de carga trae la fecha y solo se
-- conserva la edad al ingreso.
ALTER TABLE estudiante ADD COLUMN registro_universitario TEXT;
ALTER TABLE estudiante ADD COLUMN cohorte_anio INTEGER;
ALTER TABLE estudiante ADD COLUMN cohorte_ciclo TEXT CHECK (cohorte_ciclo IN ('I', 'II'));
ALTER TABLE estudiante ADD COLUMN plan_id INTEGER REFERENCES plan_estudios(id);
ALTER TABLE estudiante ADD COLUMN estado TEXT NOT NULL DEFAULT 'cursando'
    CHECK (estado IN ('cursando', 'egresado', 'titulado', 'retirado', 'congelado'));
ALTER TABLE estudiante ADD COLUMN ultimo_anio INTEGER;              -- último ciclo matriculado
ALTER TABLE estudiante ADD COLUMN ultimo_ciclo TEXT CHECK (ultimo_ciclo IN ('I', 'II'));
ALTER TABLE estudiante ADD COLUMN fecha_egreso TEXT;                -- AAAA-MM-DD
ALTER TABLE estudiante ADD COLUMN fecha_titulacion TEXT;
ALTER TABLE estudiante ADD COLUMN modalidad_titulacion TEXT
    CHECK (modalidad_titulacion IN ('tesis', 'proyecto_grado', 'trabajo_dirigido', 'examen_grado', 'excelencia', 'otra'));
ALTER TABLE estudiante ADD COLUMN motivo_retiro TEXT CHECK (motivo_retiro IN ('academico', 'no_academico'));
-- Admisión (hoja 3). Vacíos = sin dato.
ALTER TABLE estudiante ADD COLUMN via_ingreso TEXT CHECK (via_ingreso IN ('ordinaria', 'especial'));
ALTER TABLE estudiante ADD COLUMN sexo TEXT CHECK (sexo IN ('hombre', 'mujer'));
ALTER TABLE estudiante ADD COLUMN edad_ingreso INTEGER;
ALTER TABLE estudiante ADD COLUMN otra_ciudad INTEGER CHECK (otra_ciudad IN (0, 1));   -- de otra ciudad del país
ALTER TABLE estudiante ADD COLUMN extranjero INTEGER CHECK (extranjero IN (0, 1));
ALTER TABLE estudiante ADD COLUMN colegio TEXT CHECK (colegio IN ('publico', 'privado'));

CREATE UNIQUE INDEX ux_estudiante_ru ON estudiante (registro_universitario) WHERE registro_universitario IS NOT NULL;
CREATE INDEX ix_estudiante_cohorte ON estudiante (cohorte_anio, cohorte_ciclo);

-- Lo que ya había: titulados y egresados según los años registrados. Sin cohorte no entran a los indicadores.
UPDATE estudiante SET estado = 'titulado' WHERE titulado = 1;
UPDATE estudiante SET estado = 'egresado' WHERE titulado = 0 AND hasta IS NOT NULL;
