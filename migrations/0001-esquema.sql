-- Esquema base de TAU (PLAN §74, 16-nov-2026).
--
-- Reemplaza las 96 migraciones que se acumularon hasta esa fecha: el sistema empieza de cero y ninguna base anterior
-- se conserva. Es el esquema que dejaban aquellas migraciones, tabla por tabla, sin los datos de ninguna unidad: los
-- planes de estudio, el marco de calidad, las líneas de investigación y la clasificación MSC los trae la instancia
-- (instancias/<nombre>/, scripts/instalar.py). Aquí quedan solo los datos de referencia que sirven a cualquier unidad:
-- tipos de producto y de actividad, índices, y las cuatro unidades con nombres genéricos (universidad, facultad,
-- carrera e instituto), que cada instalación renombra.
--
-- Las migraciones siguientes parten de aquí: 0002, 0003…

CREATE TABLE usuario (
    id                INTEGER PRIMARY KEY,
    email             TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    nombres           TEXT    NOT NULL,
    apellidos         TEXT    NOT NULL,
    pass_hash         TEXT    NOT NULL,
    activo            INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    debe_cambiar_pass INTEGER NOT NULL DEFAULT 1 CHECK (debe_cambiar_pass IN (0, 1)),
    creado_en         TEXT    NOT NULL DEFAULT (datetime('now')),
    ultimo_acceso     TEXT
, frecuencia_avisos TEXT NOT NULL DEFAULT 'inmediato'
    CHECK (frecuencia_avisos IN ('inmediato', 'semanal', 'nunca')), ultimo_resumen TEXT, sesion_version INTEGER NOT NULL DEFAULT 0);

CREATE TABLE investigador (
    usuario_id     INTEGER PRIMARY KEY REFERENCES usuario(id) ON DELETE CASCADE,
    orcid          TEXT,
    mr_id          TEXT,
    zbmath_id      TEXT,
    arxiv_id       TEXT,
    scholar_url    TEXT,
    bio            TEXT,
    perfil_publico INTEGER NOT NULL DEFAULT 0 CHECK (perfil_publico IN (0, 1))
, pagina_web TEXT, foto TEXT, actualizado_en TEXT);

CREATE TABLE intento_login (
    id    INTEGER PRIMARY KEY,
    email TEXT    NOT NULL COLLATE NOCASE,
    ip    TEXT,
    exito INTEGER NOT NULL CHECK (exito IN (0, 1)),
    fecha TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE auditoria (
    id         INTEGER PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuario(id),
    accion     TEXT NOT NULL,
    entidad    TEXT,
    entidad_id INTEGER,
    detalle    TEXT,
    fecha      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE tipo_actividad (
    id     INTEGER PRIMARY KEY,
    nombre TEXT    NOT NULL UNIQUE,
    orden  INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
, del_sistema INTEGER NOT NULL DEFAULT 0 CHECK (del_sistema IN (0, 1)));

CREATE TABLE tipo_producto (
    id              INTEGER PRIMARY KEY,
    nombre          TEXT    NOT NULL UNIQUE,
    admite_revision INTEGER NOT NULL DEFAULT 1 CHECK (admite_revision IN (0, 1)),
    orden           INTEGER NOT NULL DEFAULT 0,
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
, del_sistema INTEGER NOT NULL DEFAULT 0 CHECK (del_sistema IN (0, 1)));

CREATE TABLE indice (
    id                   INTEGER PRIMARY KEY,
    nombre               TEXT    NOT NULL UNIQUE,
    cuenta_como_indexado INTEGER NOT NULL DEFAULT 1 CHECK (cuenta_como_indexado IN (0, 1)),
    orden                INTEGER NOT NULL DEFAULT 0,
    activo               INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
, cuenta_como_arbitrado INTEGER NOT NULL DEFAULT 0
    CHECK (cuenta_como_arbitrado IN (0, 1)), del_sistema INTEGER NOT NULL DEFAULT 0 CHECK (del_sistema IN (0, 1)));

CREATE TABLE msc (
    codigo      TEXT PRIMARY KEY,
    nivel       INTEGER NOT NULL CHECK (nivel IN (1, 2, 3)),
    texto       TEXT NOT NULL,          -- con TeX en línea: '\(p\)-adic theory'
    texto_plano TEXT NOT NULL,          -- sin TeX, para búsquedas: 'p-adic theory'
    descripcion TEXT
);

CREATE TABLE investigador_msc (
    usuario_id INTEGER NOT NULL REFERENCES investigador(usuario_id) ON DELETE CASCADE,
    codigo     TEXT    NOT NULL REFERENCES msc(codigo),
    principal  INTEGER NOT NULL DEFAULT 0 CHECK (principal IN (0, 1)),
    orden      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (usuario_id, codigo)
);

CREATE TABLE persona_externa (
    id          INTEGER PRIMARY KEY,
    nombres     TEXT NOT NULL,
    apellidos   TEXT NOT NULL,
    institucion TEXT,
    pais        TEXT,
    email       TEXT,
    orcid       TEXT,
    usuario_id  INTEGER REFERENCES usuario(id),
    creado_por  INTEGER REFERENCES usuario(id),
    creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE actividad (
    id             INTEGER PRIMARY KEY,
    tipo_id        INTEGER NOT NULL REFERENCES tipo_actividad(id),
    titulo         TEXT    NOT NULL,
    institucion    TEXT,                     -- organizadora o anfitriona
    lugar          TEXT,                     -- ciudad o sede
    pais           TEXT,
    fecha_inicio   TEXT    NOT NULL,         -- ISO 8601 (AAAA-MM-DD)
    fecha_fin      TEXT,
    modalidad      TEXT    NOT NULL DEFAULT 'presencial'
                   CHECK (modalidad IN ('presencial', 'virtual', 'hibrida')),
    ambito         TEXT    NOT NULL DEFAULT 'nacional'
                   CHECK (ambito IN ('local', 'nacional', 'internacional')),
    url            TEXT,
    descripcion    TEXT,
    creado_por     INTEGER NOT NULL REFERENCES usuario(id),
    creado_en      TEXT    NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT, cantidad INTEGER CHECK (cantidad IS NULL OR cantidad >= 0), revista_id INTEGER REFERENCES revista(id) ON DELETE SET NULL, monto INTEGER CHECK (monto IS NULL OR monto >= 0), moneda TEXT CHECK (moneda IS NULL OR moneda IN ('BOB', 'USD')), financiamiento TEXT CHECK (financiamiento IS NULL OR financiamiento IN ('interno', 'externo')), ingresos INTEGER CHECK (ingresos IS NULL OR ingresos >= 0),
    CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);

CREATE TABLE producto (
    id                 INTEGER PRIMARY KEY,
    tipo_id            INTEGER NOT NULL REFERENCES tipo_producto(id),
    titulo             TEXT    NOT NULL,
    anio               INTEGER NOT NULL,
    estado_publicacion TEXT    NOT NULL DEFAULT 'publicado'
                       CHECK (estado_publicacion IN ('en_preparacion', 'enviado', 'aceptado', 'publicado')),
    revision           TEXT    NOT NULL DEFAULT 'sin_arbitraje'
                       CHECK (revision IN ('indexado', 'arbitrado', 'sin_arbitraje')),
    medio              TEXT,                 -- revista, editorial, actas, repositorio…
    volumen            TEXT,
    numero             TEXT,
    paginas            TEXT,
    doi                TEXT UNIQUE,          -- normalizado en minúsculas, sin https://doi.org/
    arxiv_id           TEXT UNIQUE,          -- sin versión: 2401.01234, math/0501001
    url                TEXT,
    resumen            TEXT,
    actividad_id       INTEGER REFERENCES actividad(id) ON DELETE SET NULL,  -- p. ej. presentación en un congreso
    creado_por         INTEGER NOT NULL REFERENCES usuario(id),
    creado_en          TEXT    NOT NULL DEFAULT (datetime('now')),
    actualizado_en     TEXT
, mes INTEGER CHECK (mes BETWEEN 1 AND 12), revista_id INTEGER REFERENCES revista(id) ON DELETE SET NULL, openalex_id TEXT, citas INTEGER, citas_actualizadas TEXT, publicado_como_id INTEGER REFERENCES producto(id) ON DELETE SET NULL);

CREATE TABLE producto_autor (
    producto_id     INTEGER NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    orden           INTEGER NOT NULL,
    investigador_id INTEGER REFERENCES usuario(id),
    externo_id      INTEGER REFERENCES persona_externa(id), filiacion_instituto INTEGER CHECK (filiacion_instituto IN (0, 1)),
    PRIMARY KEY (producto_id, orden),
    CHECK ((investigador_id IS NULL) <> (externo_id IS NULL))
);

CREATE TABLE producto_indice (
    producto_id INTEGER NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    indice_id   INTEGER NOT NULL REFERENCES indice(id),
    PRIMARY KEY (producto_id, indice_id)
);

CREATE TABLE proyecto (
    id                    INTEGER PRIMARY KEY,
    codigo                TEXT UNIQUE,          -- código de la agencia (p. ej. FONDECYT 1260001)
    nombre                TEXT NOT NULL,
    descripcion           TEXT,
    objetivo_general      TEXT,
    fuente_financiamiento TEXT,
    monto                 INTEGER,              -- en unidades de `moneda`, sin decimales
    moneda                TEXT NOT NULL DEFAULT 'CLP',
    fecha_inicio          TEXT,
    fecha_fin             TEXT,
    estado                TEXT NOT NULL DEFAULT 'vigente'
                          CHECK (estado IN ('formulacion', 'vigente', 'finalizado')),
    creado_por            INTEGER NOT NULL REFERENCES usuario(id),
    creado_en             TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en        TEXT, tipo TEXT NOT NULL DEFAULT 'individual'
    CHECK (tipo IN ('individual', 'institucional')), ambito TEXT CHECK (ambito IN ('nacional', 'internacional')), clase TEXT
    CHECK (clase IS NULL OR clase IN ('investigacion', 'interaccion_social')),
    CHECK (fecha_fin IS NULL OR fecha_inicio IS NULL OR fecha_fin >= fecha_inicio)
);

CREATE TABLE proyecto_objetivo (
    id          INTEGER PRIMARY KEY,
    proyecto_id INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    orden       INTEGER NOT NULL,
    texto       TEXT    NOT NULL
);

CREATE TABLE proyecto_participante (
    id              INTEGER PRIMARY KEY,
    proyecto_id     INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    investigador_id INTEGER REFERENCES usuario(id),
    externo_id      INTEGER REFERENCES persona_externa(id),
    rol             TEXT NOT NULL CHECK (rol IN ('responsable', 'co_responsable', 'co_investigador',
                                                 'postdoc', 'tesista', 'colaborador')),
    fecha_desde     TEXT,
    fecha_hasta     TEXT,                       -- NULL = vigente
    CHECK ((investigador_id IS NULL) <> (externo_id IS NULL)),
    UNIQUE (proyecto_id, investigador_id),
    UNIQUE (proyecto_id, externo_id)
);

CREATE TABLE actividad_proyecto (
    actividad_id                INTEGER NOT NULL REFERENCES actividad(id) ON DELETE CASCADE,
    proyecto_id                 INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    estado                      TEXT NOT NULL DEFAULT 'pendiente'
                                CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    responsable_participante_id INTEGER REFERENCES proyecto_participante(id) ON DELETE SET NULL,
    propuesto_por               INTEGER NOT NULL REFERENCES usuario(id),
    propuesto_en                TEXT NOT NULL DEFAULT (datetime('now')),
    revisado_por                INTEGER REFERENCES usuario(id),
    revisado_en                 TEXT,
    comentario                  TEXT,
    PRIMARY KEY (actividad_id, proyecto_id)
);

CREATE TABLE producto_proyecto (
    producto_id   INTEGER NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    proyecto_id   INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    estado        TEXT NOT NULL DEFAULT 'pendiente'
                  CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    propuesto_por INTEGER NOT NULL REFERENCES usuario(id),
    propuesto_en  TEXT NOT NULL DEFAULT (datetime('now')),
    revisado_por  INTEGER REFERENCES usuario(id),
    revisado_en   TEXT,
    comentario    TEXT, agradece INTEGER CHECK (agradece IN (0, 1)),
    PRIMARY KEY (producto_id, proyecto_id)
);

CREATE TABLE convocatoria (
    periodo         INTEGER PRIMARY KEY,
    abre            TEXT NOT NULL,
    cierra          TEXT NOT NULL,
    actualizado_por INTEGER REFERENCES usuario(id),
    actualizado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (cierra >= abre)
);

CREATE TABLE propuesta_institucional (
    id                   INTEGER PRIMARY KEY,
    proyecto_id          INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    periodo              INTEGER NOT NULL,
    modalidad            TEXT NOT NULL CHECK (modalidad IN ('nuevo', 'continuidad')),
    -- Contenido propio de la propuesta (al aceptarse, los datos básicos pasan al proyecto).
    nombre               TEXT NOT NULL,
    descripcion          TEXT,
    objetivo_general     TEXT,
    metodologia          TEXT,
    resultados_esperados TEXT,
    bibliografia         TEXT,
    estado               TEXT NOT NULL DEFAULT 'borrador'
                         CHECK (estado IN ('borrador', 'enviada', 'aceptada', 'condicional',
                                           'rechazada', 'retirada')),
    proponente_id        INTEGER NOT NULL REFERENCES usuario(id),
    creada_en            TEXT NOT NULL DEFAULT (datetime('now')),
    actualizada_en       TEXT,
    enviada_en           TEXT,
    envios               INTEGER NOT NULL DEFAULT 0,  -- cuántas veces se envió (reenvíos tras condiciones)
    copia_enviada        TEXT,                        -- JSON con lo que revisa la administración
    decidida_por         INTEGER REFERENCES usuario(id),
    decidida_en          TEXT,
    comentario           TEXT,                        -- condiciones o motivo del rechazo
    UNIQUE (proyecto_id, periodo)
);

CREATE TABLE propuesta_objetivo (
    id           INTEGER PRIMARY KEY,
    propuesta_id INTEGER NOT NULL REFERENCES propuesta_institucional(id) ON DELETE CASCADE,
    orden        INTEGER NOT NULL,
    texto        TEXT NOT NULL
);

CREATE TABLE propuesta_actividad_prevista (
    id           INTEGER PRIMARY KEY,
    propuesta_id INTEGER NOT NULL REFERENCES propuesta_institucional(id) ON DELETE CASCADE,
    orden        INTEGER NOT NULL,
    descripcion  TEXT NOT NULL,
    mes_previsto TEXT                                 -- 'AAAA-MM', dentro del periodo
, actividad_id INTEGER
    REFERENCES actividad(id) ON DELETE SET NULL);

CREATE TABLE propuesta_evento (
    id           INTEGER PRIMARY KEY,
    propuesta_id INTEGER NOT NULL REFERENCES propuesta_institucional(id) ON DELETE CASCADE,
    accion       TEXT NOT NULL,     -- enviada, aceptada, condicional, rechazada, retirada
    comentario   TEXT,
    usuario_id   INTEGER REFERENCES usuario(id),
    fecha        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE aviso_enviado (
    clave TEXT PRIMARY KEY,
    fecha TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE revista (
    id              INTEGER PRIMARY KEY,
    titulo          TEXT NOT NULL,
    issn            TEXT UNIQUE,                  -- impreso, forma 1234-567X
    eissn           TEXT UNIQUE,                  -- electrónico
    pais            TEXT,
    editorial       TEXT,
    url             TEXT,
    arbitrada       INTEGER CHECK (arbitrada IN (0, 1)),       -- revisión por pares
    acceso_abierto  INTEGER CHECK (acceso_abierto IN (0, 1)),
    estado          TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'verificada')),
    nota            TEXT,
    propuesta_por   INTEGER REFERENCES usuario(id),
    verificada_por  INTEGER REFERENCES usuario(id),
    verificada_en   TEXT,
    creado_en       TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en  TEXT
);

CREATE TABLE revista_indice (
    id             INTEGER PRIMARY KEY,
    revista_id     INTEGER NOT NULL REFERENCES revista(id) ON DELETE CASCADE,
    indice_id      INTEGER NOT NULL REFERENCES indice(id),
    desde          INTEGER NOT NULL,
    hasta          INTEGER,
    cuartil        TEXT CHECK (cuartil IN ('Q1', 'Q2', 'Q3', 'Q4')),
    fuente         TEXT,                          -- p. ej. «Lista maestra de Scopus, junio 2026»
    evidencia_url  TEXT,
    verificado_por INTEGER REFERENCES usuario(id),
    verificado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (hasta IS NULL OR hasta >= desde)
);

CREATE TABLE cosecha_descartada (
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    openalex_id TEXT NOT NULL,
    titulo      TEXT,
    fecha       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (usuario_id, openalex_id)
);

CREATE TABLE estudiante (
    id             INTEGER PRIMARY KEY,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    nivel          TEXT NOT NULL CHECK (nivel IN ('licenciatura', 'maestria', 'doctorado')),
    programa       TEXT,                       -- p. ej. «Licenciatura en Matemática»
    del_programa   INTEGER NOT NULL DEFAULT 1 CHECK (del_programa IN (0, 1)),  -- de la Carrera / UMSA
    desde          INTEGER NOT NULL,           -- año de ingreso
    hasta          INTEGER,                    -- año de egreso (vacío = cursando)
    titulado       INTEGER NOT NULL DEFAULT 0 CHECK (titulado IN (0, 1)),
    registrado_por INTEGER REFERENCES usuario(id),
    creado_en      TEXT NOT NULL DEFAULT (datetime('now')), registro_universitario TEXT, cohorte_anio INTEGER, cohorte_ciclo TEXT CHECK (cohorte_ciclo IN ('I', 'II')), plan_id INTEGER REFERENCES plan_estudios(id), estado TEXT NOT NULL DEFAULT 'cursando'
    CHECK (estado IN ('cursando', 'egresado', 'titulado', 'retirado', 'congelado')), ultimo_anio INTEGER, ultimo_ciclo TEXT CHECK (ultimo_ciclo IN ('I', 'II')), fecha_egreso TEXT, fecha_titulacion TEXT, modalidad_titulacion TEXT
    CHECK (modalidad_titulacion IN ('tesis', 'proyecto_grado', 'trabajo_dirigido', 'examen_grado', 'excelencia', 'otra')), motivo_retiro TEXT CHECK (motivo_retiro IN ('academico', 'no_academico')), via_ingreso TEXT CHECK (via_ingreso IN ('ordinaria', 'especial')), sexo TEXT CHECK (sexo IN ('hombre', 'mujer')), edad_ingreso INTEGER, otra_ciudad INTEGER CHECK (otra_ciudad IN (0, 1)), extranjero INTEGER CHECK (extranjero IN (0, 1)), colegio TEXT CHECK (colegio IN ('publico', 'privado')),
    CHECK (hasta IS NULL OR hasta >= desde)
);

CREATE TABLE proyecto_contraparte (
    id          INTEGER PRIMARY KEY,
    proyecto_id INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    institucion TEXT NOT NULL,
    pais        TEXT,
    creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE linea_investigacion (
    id             INTEGER PRIMARY KEY,
    nombre         TEXT NOT NULL,
    descripcion    TEXT,
    vigente_desde  TEXT,
    vigente_hasta  TEXT,
    orden          INTEGER NOT NULL DEFAULT 0,
    creado_por     INTEGER REFERENCES usuario(id),
    creado_en      TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT, area_id INTEGER REFERENCES area_investigacion(id),
    CHECK (vigente_hasta IS NULL OR vigente_desde IS NULL OR vigente_hasta >= vigente_desde)
);

CREATE TABLE proyecto_linea (
    proyecto_id INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    linea_id    INTEGER NOT NULL REFERENCES linea_investigacion(id),
    PRIMARY KEY (proyecto_id, linea_id)
);

CREATE TABLE propuesta_linea (
    propuesta_id INTEGER NOT NULL REFERENCES propuesta_institucional(id) ON DELETE CASCADE,
    linea_id     INTEGER NOT NULL REFERENCES linea_investigacion(id),
    PRIMARY KEY (propuesta_id, linea_id)
);

CREATE TABLE investigador_linea (
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    linea_id   INTEGER NOT NULL REFERENCES linea_investigacion(id),
    PRIMARY KEY (usuario_id, linea_id)
);

CREATE TABLE unidad (
    id          INTEGER PRIMARY KEY,
    sigla       TEXT NOT NULL UNIQUE,
    nombre      TEXT NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('universidad', 'facultad', 'carrera', 'instituto')),
    superior_id INTEGER REFERENCES unidad(id)
);

CREATE TABLE "vinculo" (
    id            INTEGER PRIMARY KEY,
    usuario_id    INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    unidad_id     INTEGER NOT NULL REFERENCES unidad(id),
    categoria     TEXT NOT NULL
                  CHECK (categoria IN ('titular', 'contratado', 'interino', 'invitado', 'externo')),
    fecha_inicio  TEXT,
    fecha_fin     TEXT,
    jornada_horas INTEGER CHECK (jornada_horas IS NULL OR jornada_horas BETWEEN 1 AND 60),
    nota          TEXT,
    creado_por    INTEGER REFERENCES usuario(id),
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')), horas_contratadas INTEGER
    CHECK (horas_contratadas IS NULL OR horas_contratadas IN (32, 64, 96, 128, 160)), carga_docencia INTEGER NOT NULL DEFAULT 0
    CHECK (carga_docencia BETWEEN 0 AND 160 AND carga_docencia % 32 = 0), carga_investigacion INTEGER NOT NULL DEFAULT 0
    CHECK (carga_investigacion BETWEEN 0 AND 160 AND carga_investigacion % 32 = 0), carga_extension INTEGER NOT NULL DEFAULT 0
    CHECK (carga_extension BETWEEN 0 AND 160 AND carga_extension % 32 = 0), carga_gestion INTEGER NOT NULL DEFAULT 0
    CHECK (carga_gestion BETWEEN 0 AND 160 AND carga_gestion % 32 = 0), carga_otras INTEGER NOT NULL DEFAULT 0
    CHECK (carga_otras BETWEEN 0 AND 160 AND carga_otras % 32 = 0), motivo_termino TEXT
    CHECK (motivo_termino IS NULL OR motivo_termino IN
           ('fin_contrato', 'renuncia', 'retiro', 'despido', 'fallecimiento', 'otro')), detalle_investigacion TEXT, detalle_extension TEXT, detalle_gestion TEXT, detalle_otras TEXT,
    CHECK (fecha_fin IS NULL OR fecha_inicio IS NULL OR fecha_fin >= fecha_inicio)
);

CREATE TABLE grado_academico (
    id          INTEGER PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    nivel       TEXT NOT NULL CHECK (nivel IN ('doctorado', 'maestria', 'especialidad', 'licenciatura',
                                               'tecnico', 'otro')),
    titulo      TEXT,              -- p. ej., «Doctor en Matemáticas»
    institucion TEXT,
    pais        TEXT,
    anio        INTEGER,
    creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE datos_personales (
    usuario_id       INTEGER PRIMARY KEY REFERENCES usuario(id) ON DELETE CASCADE,
    fecha_nacimiento TEXT,
    actualizado_por  INTEGER REFERENCES usuario(id),
    actualizado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE programa (
    id        INTEGER PRIMARY KEY,
    nombre    TEXT NOT NULL UNIQUE,
    nivel     TEXT NOT NULL CHECK (nivel IN ('licenciatura', 'maestria', 'doctorado', 'especialidad', 'diplomado')),
    unidad_id INTEGER NOT NULL REFERENCES unidad(id)
, titulo TEXT);

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
    creado_en         TEXT NOT NULL DEFAULT (datetime('now')), reforma_id INTEGER REFERENCES reforma_curricular(id), estado TEXT NOT NULL DEFAULT 'vigente'
    CHECK (estado IN ('elaboracion', 'vigente', 'cierre', 'cerrado')), en_vigencia_en  TEXT, en_vigencia_por INTEGER REFERENCES usuario(id), cierre_en       TEXT, cierre_por      INTEGER REFERENCES usuario(id), cerrado_en      TEXT, cerrado_por     INTEGER REFERENCES usuario(id), motivo_cierre   TEXT, duracion_semestres INTEGER,
    UNIQUE (programa_id, nombre)
);

CREATE TABLE asignatura (
    id           INTEGER PRIMARY KEY,
    sigla        TEXT NOT NULL UNIQUE,               -- «MAT-111»
    nombre       TEXT NOT NULL,
    departamento TEXT NOT NULL,                      -- prefijo de la sigla: MAT, FIS, INF…
    de_la_carrera INTEGER NOT NULL DEFAULT 1 CHECK (de_la_carrera IN (0, 1))  -- 0: la dicta otra unidad
, linea_formativa TEXT, area_id INTEGER REFERENCES area_investigacion(id), linea_id INTEGER REFERENCES linea_investigacion(id));

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

CREATE TABLE requisito (
    id                 INTEGER PRIMARY KEY,
    plan_asignatura_id INTEGER NOT NULL REFERENCES plan_asignatura(id) ON DELETE CASCADE,
    sigla              TEXT,
    condicion          TEXT CHECK (condicion IN ('egresado')),
    CHECK ((sigla IS NULL) <> (condicion IS NULL))
);

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

CREATE TABLE gestion_academica (
    id           INTEGER PRIMARY KEY,
    anio         INTEGER NOT NULL,
    tipo         TEXT NOT NULL CHECK (tipo IN ('I', 'INV', 'II', 'VER')),
    fecha_inicio TEXT NOT NULL,
    fecha_fin    TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'planificacion'
    CHECK (estado IN ('planificacion', 'activa', 'concluida')), activada_en       TEXT, activada_por      INTEGER REFERENCES usuario(id), concluida_en      TEXT, concluida_por     INTEGER REFERENCES usuario(id), motivo_conclusion TEXT,
    UNIQUE (anio, tipo),
    CHECK (fecha_fin >= fecha_inicio)
);

CREATE TABLE oferta (
    id            INTEGER PRIMARY KEY,
    gestion_id    INTEGER NOT NULL REFERENCES gestion_academica(id),
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id),
    paralelo      TEXT NOT NULL DEFAULT 'A',
    inscritos     INTEGER CHECK (inscritos IS NULL OR inscritos >= 0),
    creado_por    INTEGER REFERENCES usuario(id),
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')), agregada_en   TEXT, retirada_en   TEXT, motivo_retiro TEXT,
    UNIQUE (gestion_id, asignatura_id, paralelo)
);

CREATE TABLE oferta_docente (
    id              INTEGER PRIMARY KEY,
    oferta_id       INTEGER NOT NULL REFERENCES oferta(id) ON DELETE CASCADE,
    usuario_id      INTEGER NOT NULL REFERENCES usuario(id),
    rol             TEXT NOT NULL DEFAULT 'titular' CHECK (rol IN ('titular', 'auxiliar')), desde TEXT, hasta TEXT,
    UNIQUE (oferta_id, usuario_id)
);

CREATE TABLE participante_carga (
    id              INTEGER PRIMARY KEY,
    participante_id INTEGER NOT NULL REFERENCES proyecto_participante(id) ON DELETE CASCADE,
    vinculo_id      INTEGER NOT NULL REFERENCES vinculo(id) ON DELETE CASCADE,
    horas           INTEGER NOT NULL CHECK (horas BETWEEN 32 AND 160 AND horas % 32 = 0),
    desde           TEXT NOT NULL,             -- desde cuándo rige (dentro del periodo de vínculo)
    asignada_por    INTEGER REFERENCES usuario(id),
    asignada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (participante_id, vinculo_id)
);

CREATE TABLE aviso_carga (
    id              INTEGER PRIMARY KEY,
    proyecto_id     INTEGER NOT NULL REFERENCES proyecto(id) ON DELETE CASCADE,
    participante_id INTEGER NOT NULL REFERENCES proyecto_participante(id) ON DELETE CASCADE,
    vinculo_id      INTEGER NOT NULL REFERENCES vinculo(id) ON DELETE CASCADE,
    tipo            TEXT NOT NULL CHECK (tipo IN ('desvinculado', 'nuevo_vinculo')),
    creado_en       TEXT NOT NULL DEFAULT (datetime('now')),
    atendido_en     TEXT,
    atendido_por    INTEGER REFERENCES usuario(id),
    UNIQUE (participante_id, vinculo_id, tipo)
);

CREATE TABLE notificacion (
    id          INTEGER PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    asunto      TEXT NOT NULL,
    texto       TEXT,
    url         TEXT,                          -- ruta dentro del sistema (p. ej. /proyectos/3?tab=pendientes)
    creada_en   TEXT NOT NULL DEFAULT (datetime('now')),
    leida_en    TEXT,
    resumida_en TEXT                           -- ya incluida en un resumen semanal por correo
);

CREATE TABLE informe_programado (
    informe       TEXT NOT NULL,
    ocasion       TEXT NOT NULL,
    enviado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    destinatarios INTEGER NOT NULL DEFAULT 0,   -- a cuántas personas llegó (0: no había nada que avisar)
    PRIMARY KEY (informe, ocasion)
);

CREATE TABLE "actividad_participante" (
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

CREATE TABLE producto_msc (
    producto_id INTEGER NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    codigo      TEXT    NOT NULL REFERENCES msc(codigo),
    orden       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (producto_id, codigo)
);

CREATE TABLE "token_acceso" (
    id         INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    token_hash TEXT    NOT NULL UNIQUE,
    proposito  TEXT    NOT NULL CHECK (proposito IN ('recuperar', 'invitacion', 'acceso')),
    expira_en  TEXT    NOT NULL,
    usado_en   TEXT,
    creado_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE cuenta_estudiante (
    externo_id        INTEGER PRIMARY KEY REFERENCES persona_externa(id) ON DELETE CASCADE,
    usuario_id        INTEGER NOT NULL UNIQUE REFERENCES usuario(id) ON DELETE CASCADE,
    consentimiento_en TEXT,                     -- cuándo aceptó el uso de sus datos (vacío = aún no)
    creada_por        INTEGER REFERENCES usuario(id),
    creada_en         TEXT NOT NULL DEFAULT (datetime('now'))
, comparte_plan_tutor INTEGER NOT NULL DEFAULT 0
    CHECK (comparte_plan_tutor IN (0, 1)));

CREATE TABLE actividad_estudiantil (
    id             INTEGER PRIMARY KEY,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    tipo           TEXT NOT NULL CHECK (tipo IN ('ayudantia', 'olimpiada', 'congreso', 'pasantia', 'beca', 'movilidad',
                                                 'semillero', 'charla', 'voluntariado', 'otra')),
    titulo         TEXT NOT NULL,
    descripcion    TEXT,
    institucion    TEXT,
    fecha_inicio   TEXT NOT NULL,               -- AAAA-MM-DD
    fecha_fin      TEXT,
    estado         TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'verificada', 'observada')),
    observacion    TEXT,                        -- lo que pide corregir quien verifica
    verificado_por INTEGER REFERENCES usuario(id),
    verificado_en  TEXT,
    creado_en      TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);

CREATE TABLE pregunta (
    id          INTEGER PRIMARY KEY,
    encuesta_id INTEGER NOT NULL REFERENCES encuesta(id) ON DELETE CASCADE,
    orden       INTEGER NOT NULL,
    texto       TEXT NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('escala', 'si_no', 'opcion', 'multiple', 'texto')),
    opciones    TEXT,                            -- JSON: lista de textos (opcion y multiple)
    obligatoria INTEGER NOT NULL DEFAULT 1 CHECK (obligatoria IN (0, 1))
, clave TEXT);

CREATE TABLE invitacion_encuesta (
    id           INTEGER PRIMARY KEY,
    encuesta_id  INTEGER NOT NULL REFERENCES encuesta(id) ON DELETE CASCADE,
    externo_id   INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    email        TEXT NOT NULL,
    grupo        INTEGER,                        -- año de ingreso (cohorte) al invitar
    token        TEXT UNIQUE,                    -- vacío una vez respondida o cerrada la encuesta
    enviada_en   TEXT,
    recordada_en TEXT,
    respondida_en TEXT,                          -- anónimas: solo la fecha
    creada_en    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (encuesta_id, externo_id)
);

CREATE TABLE respuesta (
    id            INTEGER PRIMARY KEY,
    encuesta_id   INTEGER NOT NULL REFERENCES encuesta(id) ON DELETE CASCADE,
    invitacion_id INTEGER REFERENCES invitacion_encuesta(id) ON DELETE SET NULL,   -- vacío en las anónimas
    grupo         INTEGER,
    enviada_en    TEXT NOT NULL                  -- anónimas: solo la fecha
);

CREATE TABLE respuesta_item (
    respuesta_id INTEGER NOT NULL REFERENCES respuesta(id) ON DELETE CASCADE,
    pregunta_id  INTEGER NOT NULL REFERENCES pregunta(id) ON DELETE CASCADE,
    valor        TEXT NOT NULL                   -- una fila por valor (varias en «multiple»)
);

CREATE TABLE seguimiento_egresado (
    externo_id      INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    hito            TEXT NOT NULL CHECK (hito IN ('6m', '1a', '3a', '5a')),
    encuesta_id     INTEGER REFERENCES encuesta(id) ON DELETE SET NULL,
    estado          TEXT NOT NULL CHECK (estado IN ('invitado', 'omitido')),
    programado_para TEXT NOT NULL,            -- fecha del hito (titulación + 6 meses, 1, 3 o 5 años)
    creado_en       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (externo_id, hito)
);

CREATE TABLE tutoria_asignacion (
    id           INTEGER PRIMARY KEY,
    externo_id   INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    tutor_id     INTEGER NOT NULL REFERENCES usuario(id),
    desde        TEXT NOT NULL,
    hasta        TEXT,                              -- vacío = vigente
    asignado_por INTEGER REFERENCES usuario(id),
    creado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (hasta IS NULL OR hasta >= desde)
);

CREATE TABLE tutoria_reunion (
    id             INTEGER PRIMARY KEY,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    tutor_id       INTEGER NOT NULL REFERENCES usuario(id),
    fecha          TEXT NOT NULL,
    modalidad      TEXT NOT NULL DEFAULT 'presencial' CHECK (modalidad IN ('presencial', 'virtual')),
    tema           TEXT NOT NULL CHECK (tema IN ('academico', 'economico', 'salud', 'vocacional', 'convivencia', 'otro')),
    resumen        TEXT,                            -- confidencial
    derivacion     TEXT NOT NULL DEFAULT 'ninguna' CHECK (derivacion IN ('ninguna', 'bienestar', 'psicologia', 'academica',
                                                                         'economica', 'salud', 'otra')),
    acuerdos       TEXT,
    creado_en      TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE perfil_egresado (
    externo_id        INTEGER PRIMARY KEY REFERENCES persona_externa(id) ON DELETE CASCADE,
    invitado_en       TEXT,
    visible           INTEGER NOT NULL DEFAULT 0 CHECK (visible IN (0, 1)),
    consentimiento_en TEXT,
    ocupacion         TEXT,
    institucion       TEXT,
    ciudad_pais       TEXT,
    areas             TEXT,                         -- intereses y áreas de trabajo, texto libre
    ofrece            TEXT NOT NULL DEFAULT '[]',   -- JSON: charla, mentoria, pasantia, posgrado, empleo
    detalle           TEXT,
    actualizado_en    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE solicitud_mentoria (
    id            INTEGER PRIMARY KEY,
    de_externo_id INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    a_externo_id  INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    tipo          TEXT NOT NULL CHECK (tipo IN ('mentoria', 'charla', 'pasantia', 'posgrado', 'empleo', 'otra')),
    mensaje       TEXT NOT NULL,
    estado        TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aceptada', 'rechazada')),
    creada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    respondida_en TEXT
);

CREATE TABLE correo_pendiente (
    id                INTEGER PRIMARY KEY,
    para              TEXT    NOT NULL,
    asunto            TEXT    NOT NULL,
    mensaje           BLOB    NOT NULL,          -- el mensaje completo (EML), con su Message-ID fijo
    intentos          INTEGER NOT NULL DEFAULT 0,
    proximo_intento   TEXT    NOT NULL DEFAULT (datetime('now')),   -- UTC, como AHORA
    ultimo_error      TEXT,
    creado_en         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE "rol_asignado" (
    id           INTEGER PRIMARY KEY,
    usuario_id   INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    rol          TEXT NOT NULL CHECK (rol IN ('administracion_sistema', 'direccion_instituto',
                                              'direccion_carrera', 'coordinacion_academica',
                                              'comision_calidad', 'gestion_datos')),
    unidad_id    INTEGER NOT NULL REFERENCES unidad(id),
    desde        TEXT NOT NULL,
    hasta        TEXT,
    nota         TEXT,                        -- p. ej., «Pedido de la Dirección, nota 12/2026»
    asignado_por INTEGER REFERENCES usuario(id),
    creado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (hasta IS NULL OR hasta >= desde)
);

CREATE TABLE marco_calidad (
    id            INTEGER PRIMARY KEY,
    unidad_id     INTEGER NOT NULL REFERENCES unidad(id),
    nombre        TEXT    NOT NULL,
    version       TEXT    NOT NULL,
    descripcion   TEXT,
    vigente_desde TEXT,
    vigente_hasta TEXT,
    ventana_anios INTEGER NOT NULL DEFAULT 5 CHECK (ventana_anios BETWEEN 1 AND 10),  -- años de evidencia
    creado_en     TEXT    NOT NULL DEFAULT (datetime('now')), plan_resolucion TEXT, plan_aprobado_en TEXT,
    UNIQUE (unidad_id, version),
    CHECK (vigente_hasta IS NULL OR vigente_desde IS NULL OR vigente_hasta >= vigente_desde)
);

CREATE TABLE nivel_escala (
    id          INTEGER PRIMARY KEY,
    marco_id    INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    valor       INTEGER NOT NULL,
    nombre      TEXT    NOT NULL,
    descripcion TEXT,
    UNIQUE (marco_id, valor)
);

CREATE TABLE atributo_calidad (
    id          INTEGER PRIMARY KEY,
    marco_id    INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    clave       TEXT    NOT NULL,
    nombre      TEXT    NOT NULL,
    descripcion TEXT,
    UNIQUE (marco_id, clave)
);

CREATE TABLE dimension_calidad (
    id          INTEGER PRIMARY KEY,
    marco_id    INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    codigo      TEXT    NOT NULL,
    nombre      TEXT    NOT NULL,
    descripcion TEXT,
    referencia  TEXT,                       -- con qué políticas o dimensiones institucionales se alinea
    UNIQUE (marco_id, codigo)
);

CREATE TABLE criterio_calidad (
    id           INTEGER PRIMARY KEY,
    dimension_id INTEGER NOT NULL REFERENCES dimension_calidad(id),
    codigo       TEXT    NOT NULL,
    nombre       TEXT    NOT NULL,
    descripcion  TEXT,
    UNIQUE (dimension_id, codigo)
);

CREATE TABLE indicador_calidad (
    id            INTEGER PRIMARY KEY,
    criterio_id   INTEGER NOT NULL REFERENCES criterio_calidad(id),
    codigo        TEXT    NOT NULL,
    nombre        TEXT    NOT NULL,
    tipo          TEXT    NOT NULL CHECK (tipo IN ('estructura', 'proceso', 'resultado', 'percepcion', 'contexto')),
    formula       TEXT,                     -- en palabras, como la leen la Comisión y los pares
    fuente        TEXT    NOT NULL DEFAULT 'manual' CHECK (fuente = 'manual' OR fuente LIKE 'auto:_%'),
    unidad_medida TEXT,
    frecuencia    TEXT    NOT NULL DEFAULT 'anual' CHECK (frecuencia IN ('anual', 'semestral', 'por_periodo')),
    sentido       TEXT    NOT NULL DEFAULT 'mayor' CHECK (sentido IN ('mayor', 'menor', 'informativo')),
    responsable   TEXT,
    referencia    TEXT,                     -- p. ej., el objetivo de la Política de Calidad y su meta
    activo        INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)), publico INTEGER NOT NULL DEFAULT 0 CHECK (publico IN (0, 1)),
    UNIQUE (criterio_id, codigo)
);

CREATE TABLE indicador_atributo (
    indicador_id INTEGER NOT NULL REFERENCES indicador_calidad(id) ON DELETE CASCADE,
    atributo_id  INTEGER NOT NULL REFERENCES atributo_calidad(id) ON DELETE CASCADE,
    PRIMARY KEY (indicador_id, atributo_id)
);

CREATE TABLE meta_indicador (
    id           INTEGER PRIMARY KEY,
    indicador_id INTEGER NOT NULL REFERENCES indicador_calidad(id) ON DELETE CASCADE,
    anio         INTEGER NOT NULL CHECK (anio BETWEEN 2000 AND 2100),
    valor        REAL    NOT NULL,
    nota         TEXT,
    UNIQUE (indicador_id, anio)
);

CREATE TABLE valor_indicador (
    id             INTEGER PRIMARY KEY,
    indicador_id   INTEGER NOT NULL REFERENCES indicador_calidad(id) ON DELETE CASCADE,
    anio           INTEGER NOT NULL CHECK (anio BETWEEN 2000 AND 2100),
    valor          REAL    NOT NULL,
    n              INTEGER CHECK (n IS NULL OR n >= 0),   -- base del cálculo (respuestas, personas…), si la hay
    fuente         TEXT,                                  -- de dónde sale: acta, encuesta, registro…
    nota           TEXT,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (indicador_id, anio)
);

CREATE TABLE valor_automatico (
    indicador_id INTEGER NOT NULL REFERENCES indicador_calidad(id) ON DELETE CASCADE,
    anio         INTEGER NOT NULL,
    valor        REAL,
    n            INTEGER,
    detalle      TEXT,
    calculado_en TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (indicador_id, anio)
);

CREATE TABLE cierre_calidad (
    id         INTEGER PRIMARY KEY,
    marco_id   INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    anio       INTEGER NOT NULL,
    cerrado_por INTEGER REFERENCES usuario(id),
    cerrado_en TEXT    NOT NULL DEFAULT (datetime('now')),
    nota       TEXT,
    UNIQUE (marco_id, anio)
);

CREATE TABLE valor_cierre (
    cierre_id    INTEGER NOT NULL REFERENCES cierre_calidad(id) ON DELETE CASCADE,
    indicador_id INTEGER NOT NULL REFERENCES indicador_calidad(id) ON DELETE CASCADE,
    valor        REAL,
    n            INTEGER,
    detalle      TEXT,
    meta         REAL,
    PRIMARY KEY (cierre_id, indicador_id)
);

CREATE TABLE evidencia_calidad (
    id             INTEGER PRIMARY KEY,
    marco_id       INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    tipo           TEXT    NOT NULL CHECK (tipo IN ('documento', 'enlace', 'informe')),
    titulo         TEXT    NOT NULL,
    descripcion    TEXT,
    fecha          TEXT,                       -- fecha del documento (AAAA-MM-DD)
    vigente_hasta  TEXT,                       -- vacía: no vence
    url            TEXT,                       -- solo los enlaces
    informe        TEXT,                       -- solo los informes: qué informe del sistema
    parametros     TEXT,                       -- periodo u opciones con que se generó el informe
    archivo        TEXT    UNIQUE,             -- nombre aleatorio en <datos>/evidencias
    nombre_archivo TEXT,                       -- nombre original, para mostrar y descargar
    mime           TEXT,
    tamano         INTEGER,
    sha256         TEXT,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT    NOT NULL DEFAULT (datetime('now')), actividad_id INTEGER REFERENCES actividad_mejora(id) ON DELETE SET NULL,
    CHECK ((tipo = 'enlace') = (url IS NOT NULL)),
    CHECK ((tipo = 'enlace') = (archivo IS NULL)),
    CHECK ((tipo = 'informe') = (informe IS NOT NULL)),
    CHECK (archivo IS NULL OR sha256 IS NOT NULL)
);

CREATE TABLE evidencia_criterio (
    evidencia_id INTEGER NOT NULL REFERENCES evidencia_calidad(id) ON DELETE CASCADE,
    criterio_id  INTEGER NOT NULL REFERENCES criterio_calidad(id) ON DELETE CASCADE,
    PRIMARY KEY (evidencia_id, criterio_id)
);

CREATE TABLE autoevaluacion (
    id              INTEGER PRIMARY KEY,
    marco_id        INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    nombre          TEXT    NOT NULL,
    desde_anio      INTEGER NOT NULL CHECK (desde_anio BETWEEN 2000 AND 2100),
    hasta_anio      INTEGER NOT NULL CHECK (hasta_anio BETWEEN 2000 AND 2100),
    estado          TEXT    NOT NULL DEFAULT 'en_curso' CHECK (estado IN ('en_curso', 'concluida')),
    analisis_global TEXT,
    creada_por      INTEGER REFERENCES usuario(id),
    creada_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    concluida_por   INTEGER REFERENCES usuario(id),
    concluida_en    TEXT,
    CHECK (desde_anio <= hasta_anio),
    CHECK ((estado = 'concluida') = (concluida_en IS NOT NULL))
);

CREATE TABLE juicio_criterio (
    id                INTEGER PRIMARY KEY,
    autoevaluacion_id INTEGER NOT NULL REFERENCES autoevaluacion(id) ON DELETE CASCADE,
    criterio_id       INTEGER NOT NULL REFERENCES criterio_calidad(id),
    nivel             INTEGER,
    nivel_nombre      TEXT,
    juicio            TEXT,
    fortalezas        TEXT,
    debilidades       TEXT,
    actualizado_por   INTEGER REFERENCES usuario(id),
    actualizado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (autoevaluacion_id, criterio_id),
    CHECK ((nivel IS NULL) = (nivel_nombre IS NULL))
);

CREATE TABLE sintesis_dimension (
    autoevaluacion_id INTEGER NOT NULL REFERENCES autoevaluacion(id) ON DELETE CASCADE,
    dimension_id      INTEGER NOT NULL REFERENCES dimension_calidad(id),
    sintesis          TEXT    NOT NULL,
    actualizado_por   INTEGER REFERENCES usuario(id),
    actualizado_en    TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (autoevaluacion_id, dimension_id)
);

CREATE TABLE evaluacion_externa (
    id              INTEGER PRIMARY KEY,
    marco_id        INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    organismo       TEXT    NOT NULL,
    tipo            TEXT    NOT NULL DEFAULT 'acreditacion' CHECK (tipo IN ('acreditacion', 'pares', 'otra')),
    fecha_visita    TEXT,
    fecha_dictamen  TEXT,
    resultado       TEXT,                    -- dictamen en palabras (acreditada, con observaciones…)
    vigente_hasta   TEXT,
    evidencia_id    INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    nota            TEXT,
    creada_por      INTEGER REFERENCES usuario(id),
    creada_en       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE recomendacion_externa (
    id            INTEGER PRIMARY KEY,
    evaluacion_id INTEGER NOT NULL REFERENCES evaluacion_externa(id) ON DELETE CASCADE,
    texto         TEXT    NOT NULL,
    criterio_id   INTEGER REFERENCES criterio_calidad(id) ON DELETE SET NULL
);

CREATE TABLE accion_mejora (
    id                INTEGER PRIMARY KEY,
    marco_id          INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    titulo            TEXT    NOT NULL,
    descripcion       TEXT,
    origen            TEXT    NOT NULL CHECK (origen IN ('autoevaluacion', 'externa', 'otro')),
    autoevaluacion_id INTEGER REFERENCES autoevaluacion(id) ON DELETE SET NULL,
    debilidad         TEXT,                  -- copia de la debilidad que la origina
    recomendacion_id  INTEGER REFERENCES recomendacion_externa(id) ON DELETE SET NULL,
    criterio_id       INTEGER REFERENCES criterio_calidad(id) ON DELETE SET NULL,
    responsable_id    INTEGER REFERENCES usuario(id),
    plazo             TEXT    NOT NULL,      -- AAAA-MM-DD
    indicador_id      INTEGER REFERENCES indicador_calidad(id) ON DELETE SET NULL,
    meta              REAL,
    prioridad         TEXT    NOT NULL DEFAULT 'media' CHECK (prioridad IN ('alta', 'media', 'baja')),
    estado            TEXT    NOT NULL DEFAULT 'pendiente'
                      CHECK (estado IN ('pendiente', 'en_curso', 'cumplida', 'cancelada')),
    cumplida_en       TEXT,                  -- AAAA-MM-DD
    motivo_cancelacion TEXT,
    creada_por        INTEGER REFERENCES usuario(id),
    creada_en         TEXT    NOT NULL DEFAULT (datetime('now')), codigo TEXT, objetivo TEXT, eje TEXT,
    CHECK ((estado = 'cumplida') = (cumplida_en IS NOT NULL)),
    CHECK ((estado = 'cancelada') = (motivo_cancelacion IS NOT NULL))
);

CREATE TABLE avance_accion (
    id             INTEGER PRIMARY KEY,
    accion_id      INTEGER NOT NULL REFERENCES accion_mejora(id) ON DELETE CASCADE,
    fecha          TEXT    NOT NULL,
    texto          TEXT    NOT NULL,
    porcentaje     INTEGER CHECK (porcentaje IS NULL OR porcentaje BETWEEN 0 AND 100),
    evidencia_id   INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT    NOT NULL DEFAULT (datetime('now'))
, actividad_id INTEGER REFERENCES actividad_mejora(id) ON DELETE CASCADE);

CREATE TABLE "encuesta" (
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
, retorno              TEXT, acciones             TEXT, retorno_publicado_en TEXT);

CREATE TABLE empleador (
    id            INTEGER PRIMARY KEY,
    externo_id    INTEGER NOT NULL UNIQUE REFERENCES persona_externa(id),   -- la persona de contacto (con su correo)
    organizacion  TEXT NOT NULL,
    sector        TEXT NOT NULL CHECK (sector IN ('educacion', 'investigacion', 'publico', 'privado', 'otro')),
    cargo         TEXT,                                                     -- del contacto
    activo        INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),       -- solo los activos reciben encuestas
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE convenio (
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

CREATE TABLE actividad_convenio (
    id             INTEGER PRIMARY KEY,
    convenio_id    INTEGER NOT NULL REFERENCES convenio(id) ON DELETE CASCADE,
    fecha          TEXT NOT NULL,
    descripcion    TEXT NOT NULL,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE impacto_proyecto (
    proyecto_id    INTEGER PRIMARY KEY REFERENCES proyecto(id) ON DELETE CASCADE,
    beneficiarios  INTEGER CHECK (beneficiarios IS NULL OR beneficiarios >= 0),
    descripcion    TEXT,                         -- a quiénes llegó y qué cambió
    comprobado     INTEGER NOT NULL DEFAULT 0 CHECK (comprobado IN (0, 1)),
    evidencia_id   INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (comprobado = 0 OR evidencia_id IS NOT NULL)
);

CREATE TABLE comunicado (
    id           INTEGER PRIMARY KEY,
    tipo         TEXT NOT NULL CHECK (tipo IN ('comunicado', 'convocatoria', 'evento')),
    titulo       TEXT NOT NULL,
    texto        TEXT NOT NULL DEFAULT '',
    publica_como TEXT NOT NULL CHECK (publica_como IN ('direccion_carrera', 'direccion_instituto',
                                                       'coordinacion_academica', 'proyecto')),
    proyecto_id  INTEGER REFERENCES proyecto(id) ON DELETE SET NULL,
    para_todos   INTEGER NOT NULL DEFAULT 0 CHECK (para_todos IN (0, 1)),
    inicio       TEXT,                     -- evento: 'AAAA-MM-DDTHH:MM' (hora local)
    lugar        TEXT,
    confirmar    INTEGER NOT NULL DEFAULT 0 CHECK (confirmar IN (0, 1)),   -- pide confirmar asistencia
    enlace       TEXT,                     -- p. ej., la convocatoria de auxiliaturas a la que lleva
    estado       TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'publicado', 'cancelado')),
    creado_por   INTEGER NOT NULL REFERENCES usuario(id),
    creado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    publicado_en TEXT
, inscripcion INTEGER NOT NULL DEFAULT 0 CHECK (inscripcion IN (0, 1)), cupos       INTEGER CHECK (cupos IS NULL OR cupos > 0), certificado INTEGER NOT NULL DEFAULT 0 CHECK (certificado IN (0, 1)), horas       INTEGER CHECK (horas IS NULL OR horas > 0));

CREATE TABLE comunicado_destinatario (
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id) ON DELETE CASCADE,
    usuario_id    INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    respuesta     TEXT CHECK (respuesta IN ('asistire', 'no_podre')),
    respondido_en TEXT,
    asistio       INTEGER CHECK (asistio IN (0, 1)),    -- lo registra el organizador después del evento
    PRIMARY KEY (comunicado_id, usuario_id)
);

CREATE TABLE requisito_auxiliatura (
    id              INTEGER PRIMARY KEY,
    convocatoria_id INTEGER NOT NULL REFERENCES convocatoria_auxiliatura(id) ON DELETE CASCADE,
    texto           TEXT NOT NULL,
    acredita        TEXT NOT NULL CHECK (acredita IN ('documento', 'declaracion', 'sistema')),
    orden           INTEGER NOT NULL DEFAULT 0
, opcional INTEGER NOT NULL DEFAULT 0 CHECK (opcional IN (0, 1)), clave TEXT);

CREATE TABLE item_auxiliatura (
    id              INTEGER PRIMARY KEY,
    convocatoria_id INTEGER NOT NULL REFERENCES convocatoria_auxiliatura(id) ON DELETE CASCADE,
    asignatura_id   INTEGER REFERENCES asignatura(id),
    proyecto_id     INTEGER REFERENCES proyecto(id) ON DELETE SET NULL,
    titulo          TEXT NOT NULL,          -- «MAT-102 Cálculo II» o el nombre del proyecto
    plazas          INTEGER NOT NULL DEFAULT 1 CHECK (plazas BETWEEN 1 AND 20),
    horas           INTEGER NOT NULL DEFAULT 40 CHECK (horas IN (20, 40)),
    fase            TEXT NOT NULL DEFAULT 'postulacion'
                    CHECK (fase IN ('postulacion', 'habilitacion', 'meritos', 'escrito', 'oral', 'concluido')),
    tema_oral       TEXT
, temas_oral TEXT, tema_oral_en TEXT);

CREATE TABLE tribunal_auxiliatura (
    item_id    INTEGER NOT NULL REFERENCES item_auxiliatura(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    tipo       TEXT NOT NULL CHECK (tipo IN ('docente', 'estudiante')),
    PRIMARY KEY (item_id, usuario_id)
);

CREATE TABLE postulacion_auxiliatura (
    id         INTEGER PRIMARY KEY,
    item_id    INTEGER NOT NULL REFERENCES item_auxiliatura(id) ON DELETE CASCADE,
    externo_id INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    propuesta  TEXT NOT NULL DEFAULT '',
    estado     TEXT NOT NULL DEFAULT 'borrador'
               CHECK (estado IN ('borrador', 'enviada', 'no_habilitada', 'eliminada', 'titular', 'no_seleccionada',
                                 'empate')),
    fase_fin   TEXT,                       -- fase en que quedó fuera (no habilitada o bajo el mínimo)
    enviada_en TEXT, orden_oral INTEGER, hora_oral TEXT,
    UNIQUE (item_id, externo_id)
);

CREATE TABLE postulacion_requisito (
    id             INTEGER PRIMARY KEY,    -- los documentos son adjuntos de la entidad 'requisito_postulacion'
    postulacion_id INTEGER NOT NULL REFERENCES postulacion_auxiliatura(id) ON DELETE CASCADE,
    requisito_id   INTEGER NOT NULL REFERENCES requisito_auxiliatura(id) ON DELETE CASCADE,
    declarado      INTEGER NOT NULL DEFAULT 0 CHECK (declarado IN (0, 1)),
    UNIQUE (postulacion_id, requisito_id)
);

CREATE TABLE calificacion_auxiliatura (
    postulacion_id INTEGER NOT NULL REFERENCES postulacion_auxiliatura(id) ON DELETE CASCADE,
    fase           TEXT NOT NULL CHECK (fase IN ('habilitacion', 'meritos', 'escrito', 'oral')),
    miembro_id     INTEGER NOT NULL REFERENCES usuario(id),
    valor          REAL NOT NULL CHECK (valor >= 0 AND valor <= 35),
    observacion    TEXT,
    registrado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (postulacion_id, fase, miembro_id)
);

CREATE TABLE fase_auxiliatura (
    item_id     INTEGER NOT NULL REFERENCES item_auxiliatura(id) ON DELETE CASCADE,
    fase        TEXT NOT NULL CHECK (fase IN ('postulacion', 'habilitacion', 'meritos', 'escrito', 'oral')),
    cerrada_por INTEGER REFERENCES usuario(id),
    cerrada_en  TEXT NOT NULL DEFAULT (datetime('now')),   -- desde aquí corren las 24 horas para impugnar (art. 21)
    PRIMARY KEY (item_id, fase)
);

CREATE TABLE impugnacion_auxiliatura (
    id             INTEGER PRIMARY KEY,
    postulacion_id INTEGER NOT NULL REFERENCES postulacion_auxiliatura(id) ON DELETE CASCADE,
    fase           TEXT NOT NULL CHECK (fase IN ('habilitacion', 'meritos', 'escrito', 'oral')),
    presentada_en  TEXT NOT NULL,          -- fecha en que se presentó
    texto          TEXT NOT NULL,
    resolucion     TEXT,                   -- vacía: pendiente
    resuelta_en    TEXT,
    registrada_por INTEGER REFERENCES usuario(id),
    creado_en      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE tramite_grado (
    id          INTEGER PRIMARY KEY,
    externo_id  INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    tipo        TEXT NOT NULL CHECK (tipo IN ('perfil', 'final')),
    perfil_id   INTEGER REFERENCES tramite_grado(id),   -- el documento final, del perfil aprobado
    modalidad   TEXT NOT NULL DEFAULT 'proyecto_grado' CHECK (modalidad IN ('proyecto_grado', 'tesis')),
    titulo      TEXT NOT NULL,
    tutor_id    INTEGER REFERENCES usuario(id),
    secciones   TEXT NOT NULL DEFAULT '{}',              -- JSON {clave: texto en LaTeX}
    estado      TEXT NOT NULL DEFAULT 'borrador'
                CHECK (estado IN ('borrador', 'con_tutor', 'enviado', 'en_revision', 'observado', 'favorable',
                                  'aprobado', 'rechazado', 'defendido', 'reprobado')),
    ronda       INTEGER NOT NULL DEFAULT 0,
    plazo       TEXT,                                   -- vence la revisión del tribunal de la ronda actual
    comentario_tutor TEXT,
    resolucion  TEXT,                                   -- número de la resolución que aprueba el perfil
    reunion_en  TEXT,                                   -- final: reunión del tribunal con el postulante y el tutor
    defensa_en  TEXT,                                   -- final: fecha de la defensa
    creado_en   TEXT NOT NULL DEFAULT (datetime('now')),
    enviado_en  TEXT,
    cerrado_en  TEXT
);

CREATE TABLE tribunal_grado (
    tramite_id   INTEGER NOT NULL REFERENCES tramite_grado(id) ON DELETE CASCADE,
    usuario_id   INTEGER NOT NULL REFERENCES usuario(id),
    designado_por INTEGER REFERENCES usuario(id),
    designado_en TEXT NOT NULL DEFAULT (datetime('now')),
    nota_defensa INTEGER CHECK (nota_defensa BETWEEN 1 AND 100),
    PRIMARY KEY (tramite_id, usuario_id)
);

CREATE TABLE informe_grado (
    id         INTEGER PRIMARY KEY,
    tramite_id INTEGER NOT NULL REFERENCES tramite_grado(id) ON DELETE CASCADE,
    ronda      INTEGER NOT NULL,
    miembro_id INTEGER NOT NULL REFERENCES usuario(id),
    aspectos   TEXT NOT NULL DEFAULT '{}',              -- JSON {aspecto: 'suficiente' | 'observado'} (art. 35)
    dictamen   TEXT NOT NULL CHECK (dictamen IN ('aprobado', 'observado', 'no_aprobado')),
    fundamento TEXT,
    enviado_en TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (tramite_id, ronda, miembro_id)
);

CREATE TABLE observacion_grado (
    id           INTEGER PRIMARY KEY,
    informe_id   INTEGER NOT NULL REFERENCES informe_grado(id) ON DELETE CASCADE,
    numero       INTEGER NOT NULL,
    texto        TEXT NOT NULL,
    respuesta    TEXT,
    respondida_en TEXT
);

CREATE TABLE recordatorio_grado (
    tramite_id INTEGER NOT NULL REFERENCES tramite_grado(id) ON DELETE CASCADE,
    ronda      INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    tipo       TEXT NOT NULL CHECK (tipo IN ('por_vencer', 'vencido')),
    PRIMARY KEY (tramite_id, ronda, usuario_id, tipo)
);

CREATE TABLE area_investigacion (
    id             INTEGER PRIMARY KEY,
    nombre         TEXT NOT NULL,
    orden          INTEGER NOT NULL DEFAULT 0,
    creado_en      TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT
);

CREATE TABLE ia_politica (
    id               INTEGER PRIMARY KEY,
    version          INTEGER NOT NULL UNIQUE,
    texto            TEXT NOT NULL,
    creado_por       INTEGER REFERENCES usuario(id),
    creado_en        TEXT NOT NULL DEFAULT (datetime('now')),
    aprobada_por     INTEGER REFERENCES usuario(id),
    fecha_aprobacion TEXT,
    vigente          INTEGER NOT NULL DEFAULT 0 CHECK (vigente IN (0, 1))
);

CREATE TABLE ia_funcion (
    clave           TEXT PRIMARY KEY,
    activa          INTEGER NOT NULL DEFAULT 0 CHECK (activa IN (0, 1)),
    responsable_id  INTEGER REFERENCES usuario(id),
    actualizado_por INTEGER REFERENCES usuario(id),
    actualizado_en  TEXT,
    CHECK (activa = 0 OR responsable_id IS NOT NULL)
);

CREATE TABLE ia_uso (
    id                INTEGER PRIMARY KEY,
    funcion_clave     TEXT NOT NULL,
    usuario_id        INTEGER NOT NULL REFERENCES usuario(id),
    creado_en         TEXT NOT NULL DEFAULT (datetime('now')),
    terminado_en      TEXT,
    proveedor         TEXT CHECK (proveedor IN ('local', 'externo')),
    modelo            TEXT,
    version_prompt    INTEGER NOT NULL,
    hash_entrada      TEXT NOT NULL,
    nivel_datos       INTEGER NOT NULL CHECK (nivel_datos BETWEEN 0 AND 2),
    seudonimizado     INTEGER NOT NULL DEFAULT 0 CHECK (seudonimizado IN (0, 1)),
    estado            TEXT NOT NULL DEFAULT 'generando'
                      CHECK (estado IN ('generando', 'borrador_ia', 'aprobada', 'editada', 'rechazada', 'error')),
    error             TEXT,
    entidad_tipo      TEXT,
    entidad_id        INTEGER,
    revisor_id        INTEGER REFERENCES usuario(id),
    fecha_decision    TEXT,
    motivo            TEXT,
    distancia_edicion REAL CHECK (distancia_edicion IS NULL OR distancia_edicion BETWEEN 0 AND 1),
    valoracion        INTEGER CHECK (valoracion IS NULL OR valoracion BETWEEN 1 AND 5)
);

CREATE TABLE ia_salida (
    uso_id         INTEGER PRIMARY KEY REFERENCES ia_uso(id) ON DELETE CASCADE,
    texto_generado TEXT NOT NULL,
    texto_final    TEXT
);

CREATE TABLE ia_cierre (
    id            INTEGER PRIMARY KEY,
    funcion_clave TEXT NOT NULL,
    decision      TEXT NOT NULL CHECK (decision IN ('ampliar', 'ajustar', 'retirar')),
    fundamento    TEXT NOT NULL,
    decidido_por  INTEGER NOT NULL REFERENCES usuario(id),
    fecha         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE producto_linea (
    producto_id  INTEGER NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    linea_id     INTEGER NOT NULL REFERENCES linea_investigacion(id),
    asignado_por INTEGER REFERENCES usuario(id),
    asignado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (producto_id, linea_id)
);

CREATE TABLE "capacitacion" (
    id             INTEGER PRIMARY KEY,
    usuario_id     INTEGER NOT NULL REFERENCES usuario(id),
    titulo         TEXT NOT NULL,
    institucion    TEXT,
    area           TEXT NOT NULL CHECK (area IN ('disciplinar', 'pedagogica', 'investigacion', 'gestion', 'ia_digital',
                                                 'otra')),
    horas          INTEGER CHECK (horas IS NULL OR horas BETWEEN 1 AND 2000),
    fecha_inicio   TEXT NOT NULL,
    fecha_fin      TEXT NOT NULL,                -- cuenta en el año en que concluyó
    evidencia_id   INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (fecha_fin >= fecha_inicio)
);

CREATE TABLE reforma_curricular (
    id            INTEGER PRIMARY KEY,
    nombre        TEXT NOT NULL UNIQUE,               -- «Plan 2017»
    resolucion    TEXT,                               -- «HCU 041/2017»
    vigente_desde INTEGER NOT NULL,                   -- año en que rige
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    creado_por    INTEGER REFERENCES usuario(id)
);

CREATE TABLE plan_ciclo (
    id             INTEGER PRIMARY KEY,
    plan_id        INTEGER NOT NULL REFERENCES plan_estudios(id) ON DELETE CASCADE,
    nombre         TEXT NOT NULL,
    semestre_desde INTEGER NOT NULL,
    semestre_hasta INTEGER NOT NULL,
    CHECK (semestre_hasta >= semestre_desde),
    UNIQUE (plan_id, nombre)
);

CREATE TABLE mencion (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plan_estudios(id) ON DELETE CASCADE,
    nombre             TEXT NOT NULL,
    descripcion        TEXT,
    semestre_eleccion  INTEGER,
    minimo_asignaturas INTEGER,
    minimo_medida      INTEGER,
    creado_en          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (plan_id, nombre)
);

CREATE TABLE mencion_asignatura (
    mencion_id         INTEGER NOT NULL REFERENCES mencion(id) ON DELETE CASCADE,
    plan_asignatura_id INTEGER NOT NULL REFERENCES plan_asignatura(id) ON DELETE CASCADE,
    obligatoria        INTEGER NOT NULL DEFAULT 1 CHECK (obligatoria IN (0, 1)),
    PRIMARY KEY (mencion_id, plan_asignatura_id)
);

CREATE TABLE equivalencia (
    id              INTEGER PRIMARY KEY,
    plan_origen_id  INTEGER NOT NULL REFERENCES plan_estudios(id) ON DELETE CASCADE,
    plan_destino_id INTEGER NOT NULL REFERENCES plan_estudios(id) ON DELETE CASCADE,
    nota            TEXT,
    creado_en       TEXT NOT NULL DEFAULT (datetime('now')),
    creado_por      INTEGER REFERENCES usuario(id),
    CHECK (plan_origen_id <> plan_destino_id)
);

CREATE TABLE equivalencia_item (
    equivalencia_id INTEGER NOT NULL REFERENCES equivalencia(id) ON DELETE CASCADE,
    lado            TEXT NOT NULL CHECK (lado IN ('origen', 'destino')),
    asignatura_id   INTEGER NOT NULL REFERENCES asignatura(id),
    PRIMARY KEY (equivalencia_id, lado, asignatura_id)
);

CREATE TABLE gestion_cambio (
    id                  INTEGER PRIMARY KEY,
    gestion_id          INTEGER NOT NULL REFERENCES gestion_academica(id) ON DELETE CASCADE,
    fecha_efecto        TEXT NOT NULL,                  -- primer día en que rige el cambio
    tipo                TEXT NOT NULL CHECK (tipo IN ('agregar_materia', 'retirar_materia', 'agregar_docente',
                                                      'reasignar_docente', 'retirar_docente')),
    asignatura_id       INTEGER REFERENCES asignatura(id),
    paralelo            TEXT,
    docente_anterior_id INTEGER REFERENCES usuario(id),
    docente_nuevo_id    INTEGER REFERENCES usuario(id),
    rol                 TEXT,
    motivo              TEXT NOT NULL CHECK (motivo IN ('renuncia', 'fallecimiento', 'licencia', 'reasignacion',
                                                        'falta_inscritos', 'error_planificacion', 'necesidad', 'otro')),
    detalle             TEXT,
    registrado_por      INTEGER REFERENCES usuario(id),
    registrado_en       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE estudiante_aprobada (
    externo_id    INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id),
    marcada_en    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (externo_id, asignatura_id)
);

CREATE TABLE tutoria_solicitud (
    id            INTEGER PRIMARY KEY,
    externo_id    INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    tutor_id      INTEGER NOT NULL REFERENCES usuario(id),
    tema          TEXT NOT NULL CHECK (tema IN ('academico', 'economico', 'salud', 'vocacional', 'convivencia', 'otro')),
    mensaje       TEXT,
    estado        TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'programada', 'atendida', 'cancelada')),
    fecha_reunion TEXT,                         -- 'AAAA-MM-DDTHH:MM' cuando el tutor la programa
    respuesta     TEXT,                         -- lo que el tutor le dice (lugar, indicaciones)
    creada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    actualizada_en TEXT
);

CREATE TABLE oportunidad (
    id           INTEGER PRIMARY KEY,
    tipo         TEXT NOT NULL CHECK (tipo IN ('beca', 'movilidad', 'pasantia', 'ayudantia', 'empleo')),
    titulo       TEXT NOT NULL,
    descripcion  TEXT,
    requisitos   TEXT,
    organizacion TEXT,                                  -- quien ofrece (institución, empleador, proyecto)
    empleador_id INTEGER REFERENCES empleador(id) ON DELETE SET NULL,
    proyecto_id  INTEGER REFERENCES proyecto(id) ON DELETE SET NULL,   -- ayudantías de investigación
    plazas       INTEGER CHECK (plazas IS NULL OR plazas > 0),
    cierre       TEXT,                                  -- 'AAAA-MM-DD'; vacío = abierta hasta que se cierre
    enlace       TEXT,
    contacto     TEXT,
    para         TEXT NOT NULL DEFAULT 'estudiantes' CHECK (para IN ('estudiantes', 'egresados', 'todos')),
    estado       TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'publicada', 'cerrada')),
    creada_por   INTEGER NOT NULL REFERENCES usuario(id),
    creada_en    TEXT NOT NULL DEFAULT (datetime('now')),
    publicada_en TEXT
);

CREATE TABLE postulacion_oportunidad (
    id             INTEGER PRIMARY KEY,
    oportunidad_id INTEGER NOT NULL REFERENCES oportunidad(id) ON DELETE CASCADE,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    mensaje        TEXT,
    estado         TEXT NOT NULL DEFAULT 'postulada'
                   CHECK (estado IN ('postulada', 'preseleccionada', 'seleccionada', 'no_seleccionada', 'retirada')),
    nota           TEXT,                                -- lo que dice quien decide
    creada_en      TEXT NOT NULL DEFAULT (datetime('now')),
    decidida_en    TEXT,
    decidida_por   INTEGER REFERENCES usuario(id),
    UNIQUE (oportunidad_id, externo_id)
);

CREATE TABLE tema_grado (
    id           INTEGER PRIMARY KEY,
    docente_id   INTEGER NOT NULL REFERENCES usuario(id),
    titulo       TEXT NOT NULL,
    descripcion  TEXT,
    requisitos   TEXT,                                -- conocimientos previos que conviene tener
    linea_id     INTEGER REFERENCES linea_investigacion(id) ON DELETE SET NULL,
    modalidad    TEXT NOT NULL DEFAULT 'cualquiera' CHECK (modalidad IN ('proyecto_grado', 'tesis', 'cualquiera')),
    cupos        INTEGER NOT NULL DEFAULT 1 CHECK (cupos > 0),
    estado       TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'publicado', 'retirado')),
    creado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    publicado_en TEXT
);

CREATE TABLE solicitud_tema (
    id            INTEGER PRIMARY KEY,
    tema_id       INTEGER NOT NULL REFERENCES tema_grado(id) ON DELETE CASCADE,
    externo_id    INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    mensaje       TEXT,
    estado        TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aceptada', 'rechazada', 'retirada')),
    respuesta     TEXT,
    creada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    respondida_en TEXT,
    UNIQUE (tema_id, externo_id)
);

CREATE TABLE inscripcion_evento (
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id) ON DELETE CASCADE,
    usuario_id    INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    estado        TEXT NOT NULL CHECK (estado IN ('inscrito', 'espera')),
    creada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (comunicado_id, usuario_id)
);

CREATE TABLE caso_apoyo (
    id            INTEGER PRIMARY KEY,
    externo_id    INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    origen        TEXT NOT NULL CHECK (origen IN ('estudiante', 'tutor', 'direccion')),
    abierto_por   INTEGER NOT NULL REFERENCES usuario(id),
    tema          TEXT NOT NULL CHECK (tema IN ('academico', 'economico', 'salud', 'vocacional', 'convivencia', 'otro')),
    motivo        TEXT NOT NULL,
    estado        TEXT NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto', 'en_seguimiento', 'cerrado')),
    derivacion    TEXT NOT NULL DEFAULT 'ninguna',
    vence_el      TEXT NOT NULL,                      -- 'AAAA-MM-DD'; pasada esta fecha sin renovarse, el caso vence
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT,
    cerrado_en    TEXT
);

CREATE TABLE caso_apoyo_mensaje (
    id          INTEGER PRIMARY KEY,
    caso_id     INTEGER NOT NULL REFERENCES caso_apoyo(id) ON DELETE CASCADE,
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id),
    del_estudiante INTEGER NOT NULL CHECK (del_estudiante IN (0, 1)),
    texto       TEXT NOT NULL,
    creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE pregunta_frecuente (
    id         INTEGER PRIMARY KEY,
    categoria  TEXT NOT NULL,                       -- p. ej. «Trámites», «Becas», «Grado»
    pregunta   TEXT NOT NULL,
    respuesta  TEXT NOT NULL,
    orden      INTEGER NOT NULL DEFAULT 0,
    publicada  INTEGER NOT NULL DEFAULT 1 CHECK (publicada IN (0, 1)),
    creada_por INTEGER REFERENCES usuario(id),
    creada_en  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE servicio_apoyo (
    id          INTEGER PRIMARY KEY,
    tipo        TEXT NOT NULL CHECK (tipo IN ('bienestar', 'psicologia', 'salud', 'economica', 'academica', 'otro')),
    nombre      TEXT NOT NULL,
    descripcion TEXT,
    contacto    TEXT,
    horario     TEXT,
    enlace      TEXT,
    orden       INTEGER NOT NULL DEFAULT 0,
    activo      INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE consulta (
    id             INTEGER PRIMARY KEY,
    tipo           TEXT NOT NULL CHECK (tipo IN ('consulta', 'reclamo', 'sugerencia')),
    asunto         TEXT NOT NULL,
    texto          TEXT NOT NULL,
    anonima        INTEGER NOT NULL DEFAULT 0 CHECK (anonima IN (0, 1)),
    externo_id     INTEGER REFERENCES persona_externa(id) ON DELETE SET NULL,   -- vacío si es anónima
    estado         TEXT NOT NULL DEFAULT 'recibida' CHECK (estado IN ('recibida', 'en_atencion', 'respondida', 'cerrada')),
    respuesta      TEXT,
    respondida_por INTEGER REFERENCES usuario(id),
    respondida_en  TEXT,
    pregunta_id    INTEGER REFERENCES pregunta_frecuente(id) ON DELETE SET NULL, -- la FAQ en que se publicó la respuesta
    creada_en      TEXT NOT NULL,                  -- anónimas: solo la fecha
    CHECK (anonima = 0 OR externo_id IS NULL)
);

CREATE TABLE "adjunto" (
    id         INTEGER PRIMARY KEY,
    entidad    TEXT    NOT NULL CHECK (entidad IN ('actividad', 'producto', 'actividad_estudiantil',
                                                  'convocatoria_auxiliatura', 'requisito_postulacion', 'tramite_grado',
                                                  'recurso')),
    entidad_id INTEGER NOT NULL,
    nombre     TEXT    NOT NULL,
    archivo    TEXT    NOT NULL UNIQUE,
    mime       TEXT    NOT NULL,
    tamano     INTEGER NOT NULL,
    subido_por INTEGER NOT NULL REFERENCES usuario(id),
    subido_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE recurso (
    id          INTEGER PRIMARY KEY,
    tipo        TEXT NOT NULL CHECK (tipo IN ('apunte', 'guia', 'examen', 'libro', 'enlace', 'otro')),
    titulo      TEXT NOT NULL,
    descripcion TEXT,
    enlace      TEXT,                                   -- un enlace externo (en lugar de, o además de, un archivo)
    anio        INTEGER,                                -- gestión a la que corresponde (exámenes pasados)
    autor_id    INTEGER NOT NULL REFERENCES usuario(id),
    estado      TEXT NOT NULL DEFAULT 'publicado' CHECK (estado IN ('publicado', 'retirado')),
    creado_en   TEXT NOT NULL DEFAULT (datetime('now')),
    retirado_en TEXT,
    retirado_por INTEGER REFERENCES usuario(id)
);

CREATE TABLE recurso_asignatura (
    recurso_id    INTEGER NOT NULL REFERENCES recurso(id) ON DELETE CASCADE,
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id),
    PRIMARY KEY (recurso_id, asignatura_id)
);

CREATE TABLE preferencia_oferta (
    id            INTEGER PRIMARY KEY,
    gestion_id    INTEGER NOT NULL REFERENCES gestion_academica(id) ON DELETE CASCADE,
    usuario_id    INTEGER NOT NULL REFERENCES usuario(id),
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id),
    nivel         TEXT NOT NULL CHECK (nivel IN ('prefiere', 'no_puede')),
    nota          TEXT,
    UNIQUE (gestion_id, usuario_id, asignatura_id)
);

CREATE TABLE preferencia_gestion (
    gestion_id     INTEGER NOT NULL REFERENCES gestion_academica(id) ON DELETE CASCADE,
    usuario_id     INTEGER NOT NULL REFERENCES usuario(id),
    indisponible   TEXT NOT NULL DEFAULT '',     -- turnos sin disponibilidad: 'lun-manana,mar-tarde'
    comentario     TEXT,
    actualizada_en TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (gestion_id, usuario_id)
);

CREATE TABLE programa_analitico (
    id            INTEGER PRIMARY KEY,
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id),
    gestion_id    INTEGER NOT NULL REFERENCES gestion_academica(id) ON DELETE CASCADE,
    autor_id      INTEGER NOT NULL REFERENCES usuario(id),
    estado        TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'publicado')),
    version       INTEGER,                         -- se asigna al publicar (1, 2, …); NULL en el borrador
    objetivos     TEXT,
    contenido     TEXT,                            -- unidades temáticas, una por línea
    metodologia   TEXT,
    evaluacion    TEXT,
    bibliografia  TEXT,                            -- una referencia por línea
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    publicado_en  TEXT
);

CREATE TABLE lista_curso (
    id         INTEGER PRIMARY KEY,
    oferta_id  INTEGER NOT NULL REFERENCES oferta(id) ON DELETE CASCADE,
    ru         TEXT NOT NULL,                      -- registro universitario
    apellidos  TEXT NOT NULL,
    nombres    TEXT NOT NULL,
    correo     TEXT,
    cargado_en TEXT NOT NULL DEFAULT (datetime('now')),
    cargado_por INTEGER REFERENCES usuario(id),
    UNIQUE (oferta_id, ru)
);

CREATE TABLE evaluacion_docente (
    id          INTEGER PRIMARY KEY,
    gestion_id  INTEGER NOT NULL UNIQUE REFERENCES gestion_academica(id) ON DELETE CASCADE,
    estado      TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'anunciada', 'abierta', 'cerrada')),
    abre_el     TEXT NOT NULL,                      -- fecha
    cierra_el   TEXT NOT NULL,                      -- fecha
    criterios   TEXT NOT NULL,                      -- JSON [[clave, texto], …]: el instrumento que se anunció
    anunciada_en TEXT,
    abierta_en  TEXT,
    cerrada_en  TEXT,
    retorno     TEXT,                               -- lo que la Carrera hizo con los resultados (se publica a los estudiantes)
    retorno_publicado_en TEXT,
    creada_por  INTEGER REFERENCES usuario(id),
    creada_en   TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (cierra_el >= abre_el)
);

CREATE TABLE evaluacion_participacion (
    evaluacion_id INTEGER NOT NULL REFERENCES evaluacion_docente(id) ON DELETE CASCADE,
    oferta_id     INTEGER NOT NULL REFERENCES oferta(id) ON DELETE CASCADE,
    externo_id    INTEGER NOT NULL REFERENCES persona_externa(id) ON DELETE CASCADE,
    PRIMARY KEY (evaluacion_id, oferta_id, externo_id)
) WITHOUT ROWID;

CREATE TABLE evaluacion_respuesta (
    id            INTEGER PRIMARY KEY,
    evaluacion_id INTEGER NOT NULL REFERENCES evaluacion_docente(id) ON DELETE CASCADE,
    oferta_id     INTEGER NOT NULL REFERENCES oferta(id) ON DELETE CASCADE
);

CREATE TABLE evaluacion_valor (
    respuesta_id INTEGER NOT NULL REFERENCES evaluacion_respuesta(id) ON DELETE CASCADE,
    criterio     TEXT NOT NULL,
    valor        INTEGER NOT NULL CHECK (valor BETWEEN 1 AND 5),
    PRIMARY KEY (respuesta_id, criterio)
);

CREATE TABLE evaluacion_contexto (
    evaluacion_id  INTEGER NOT NULL REFERENCES evaluacion_docente(id) ON DELETE CASCADE,
    usuario_id     INTEGER NOT NULL REFERENCES usuario(id),
    texto          TEXT NOT NULL,
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (evaluacion_id, usuario_id)
);

CREATE TABLE evaluacion_consulta (
    id            INTEGER PRIMARY KEY,
    evaluacion_id INTEGER NOT NULL REFERENCES evaluacion_docente(id) ON DELETE CASCADE,
    docente_id    INTEGER NOT NULL REFERENCES usuario(id),
    consultor_id  INTEGER NOT NULL REFERENCES usuario(id),
    consultada_en TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE producto_acceso (
    producto_id    INTEGER PRIMARY KEY REFERENCES producto(id) ON DELETE CASCADE,
    texto          TEXT NOT NULL CHECK (texto IN ('abierto', 'depositado', 'embargo', 'cerrado', 'no_aplica')),
    version        TEXT CHECK (version IS NULL OR version IN ('preprint', 'aceptada', 'publicada')),
    enlace         TEXT,                          -- dónde leer el texto (sitio de la revista o repositorio)
    licencia       TEXT CHECK (licencia IS NULL OR licencia IN ('cc_by', 'cc_by_sa', 'cc_by_nc', 'cc_by_nc_sa', 'cc_by_nd',
                                                                 'cc_by_nc_nd', 'cc0', 'otra', 'sin_licencia')),
    embargo_hasta  TEXT,                          -- fecha desde la que se puede depositar (solo con texto = 'embargo')
    datos          TEXT CHECK (datos IS NULL OR datos IN ('publicados', 'a_pedido', 'reservados', 'no_hay')),
    datos_enlace   TEXT,                          -- repositorio, DOI o código (solo con datos = 'publicados')
    nota           TEXT,
    declarado_por  INTEGER NOT NULL REFERENCES usuario(id),
    declarado_en   TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT
);

CREATE TABLE "convocatoria_auxiliatura" (
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
, comision_resolucion TEXT, comision_resolucion_hcf TEXT, informe_final_en TEXT, resolucion_resultados TEXT, resolucion_resultados_hcf TEXT);

CREATE TABLE calificacion_detalle (
    postulacion_id INTEGER NOT NULL REFERENCES postulacion_auxiliatura(id) ON DELETE CASCADE,
    fase           TEXT NOT NULL CHECK (fase IN ('meritos', 'oral')),
    miembro_id     INTEGER NOT NULL REFERENCES usuario(id),
    clave          TEXT NOT NULL,           -- la línea del formulario (p. ej. '1a', '4') o el criterio del oral
    cantidad       REAL NOT NULL CHECK (cantidad >= 0),
    PRIMARY KEY (postulacion_id, fase, miembro_id, clave)
);

CREATE TABLE invitacion_auxiliatura (
    id             INTEGER PRIMARY KEY,
    item_id        INTEGER NOT NULL REFERENCES item_auxiliatura(id) ON DELETE CASCADE,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id),
    origen         TEXT NOT NULL CHECK (origen IN ('postulante', 'mejor_estudiante')),
    orden          INTEGER NOT NULL,
    puntaje        REAL,                      -- total del concurso (solo los postulantes)
    nota           TEXT,                      -- de dónde sale la invitación (p. ej. el promedio que certifica Kardex)
    estado         TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aceptada', 'rechazada')),
    creada_en      TEXT NOT NULL DEFAULT (datetime('now')),
    respondida_en  TEXT,
    registrada_por INTEGER REFERENCES usuario(id),
    UNIQUE (item_id, externo_id)
);

CREATE TABLE designacion_auxiliatura (
    id             INTEGER PRIMARY KEY,
    item_id        INTEGER NOT NULL REFERENCES item_auxiliatura(id) ON DELETE CASCADE,
    externo_id     INTEGER NOT NULL REFERENCES persona_externa(id),
    categoria      TEXT NOT NULL CHECK (categoria IN ('titular', 'invitado')),
    postulacion_id INTEGER REFERENCES postulacion_auxiliatura(id) ON DELETE SET NULL,
    invitacion_id  INTEGER REFERENCES invitacion_auxiliatura(id) ON DELETE SET NULL,
    cert_deudas    TEXT,                      -- fechas en que se recibieron los documentos de los ganadores (art. 23)
    cert_procesos  TEXT,
    sigep          TEXT,
    memorandum     TEXT,                      -- número del memorándum de designación (arts. 25 y 26)
    memorandum_fecha TEXT,
    inicio         TEXT,
    fin            TEXT,
    creada_en      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (item_id, externo_id)
);

CREATE TABLE documentacion_auxiliatura (
    convocatoria_id INTEGER NOT NULL REFERENCES convocatoria_auxiliatura(id) ON DELETE CASCADE,
    clave           TEXT NOT NULL CHECK (clave IN ('res_hcf_convocatoria', 'res_hcc_nomina', 'res_hcf_homologacion', 'memorandums',
                                                   'formularios', 'requisitos')),
    entregada_en    TEXT NOT NULL,            -- fecha en que la Dirección de Carrera la entregó a Bienestar Social (art. 27)
    registrada_por  INTEGER REFERENCES usuario(id),
    PRIMARY KEY (convocatoria_id, clave)
);

CREATE TABLE actividad_mejora (
    id                 INTEGER PRIMARY KEY,
    accion_id          INTEGER NOT NULL REFERENCES accion_mejora(id) ON DELETE CASCADE,
    codigo             TEXT,                 -- «4.2»
    descripcion        TEXT    NOT NULL,
    linea_base         TEXT,
    linea_base_valor   REAL,
    meta               TEXT,
    meta_valor         REAL,
    indicador_id       INTEGER REFERENCES indicador_calidad(id) ON DELETE SET NULL,
    responsable_id     INTEGER REFERENCES usuario(id),
    unidad_responsable TEXT,                 -- cuando no es una persona del sistema, o además de ella
    inicio             TEXT,                 -- AAAA-MM-DD
    plazo              TEXT    NOT NULL,     -- AAAA-MM-DD
    presupuesto        REAL    CHECK (presupuesto IS NULL OR presupuesto >= 0),   -- en bolivianos
    fuente             TEXT,                 -- fuente del presupuesto
    verificacion       TEXT,                 -- medio de verificación
    difusion           TEXT,                 -- medio de difusión
    estado             TEXT    NOT NULL DEFAULT 'pendiente'
                       CHECK (estado IN ('pendiente', 'en_curso', 'cumplida', 'cancelada')),
    cumplida_en        TEXT,
    motivo_cancelacion TEXT,
    creada_por         INTEGER REFERENCES usuario(id),
    creada_en          TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK ((estado = 'cumplida') = (cumplida_en IS NOT NULL)),
    CHECK ((estado = 'cancelada') = (motivo_cancelacion IS NOT NULL)),
    CHECK (inicio IS NULL OR inicio <= plazo)
);

CREATE TABLE reprogramacion_mejora (
    id             INTEGER PRIMARY KEY,
    actividad_id   INTEGER NOT NULL REFERENCES actividad_mejora(id) ON DELETE CASCADE,
    plazo_anterior TEXT    NOT NULL,
    plazo_nuevo    TEXT    NOT NULL,
    causa          TEXT    NOT NULL,
    evidencia_id   INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    estado         TEXT    NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aprobada', 'rechazada')),
    solicitada_por INTEGER REFERENCES usuario(id),
    solicitada_en  TEXT    NOT NULL DEFAULT (datetime('now')),
    resuelta_por   INTEGER REFERENCES usuario(id),
    resuelta_en    TEXT,
    respuesta      TEXT,                     -- motivo del rechazo o nota de la aprobación
    CHECK ((estado = 'pendiente') = (resuelta_en IS NULL)),
    CHECK (estado <> 'rechazada' OR respuesta IS NOT NULL)
);

CREATE TABLE corte_mejora (
    id            INTEGER PRIMARY KEY,
    marco_id      INTEGER NOT NULL REFERENCES marco_calidad(id) ON DELETE CASCADE,
    tipo          TEXT    NOT NULL CHECK (tipo IN ('trimestral', 'anual', 'bienal')),
    fecha         TEXT    NOT NULL,                       -- AAAA-MM-DD: fecha del corte
    estado        TEXT    NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto', 'cerrado')),
    conclusion    TEXT,
    evidencia_id  INTEGER REFERENCES evidencia_calidad(id) ON DELETE SET NULL,
    abierto_por   INTEGER REFERENCES usuario(id),
    abierto_en    TEXT    NOT NULL DEFAULT (datetime('now')),
    cerrado_por   INTEGER REFERENCES usuario(id),
    cerrado_en    TEXT,
    CHECK ((estado = 'cerrado') = (cerrado_en IS NOT NULL))
);

CREATE TABLE corte_actividad (
    id             INTEGER PRIMARY KEY,
    corte_id       INTEGER NOT NULL REFERENCES corte_mejora(id) ON DELETE CASCADE,
    actividad_id   INTEGER REFERENCES actividad_mejora(id) ON DELETE SET NULL,
    accion_codigo  TEXT,
    accion_titulo  TEXT    NOT NULL,
    prioridad      TEXT    NOT NULL,
    codigo         TEXT,
    descripcion    TEXT    NOT NULL,
    responsable    TEXT,
    plazo          TEXT    NOT NULL,
    estado         TEXT    NOT NULL,
    avance         REAL,
    semaforo       TEXT    NOT NULL,
    ultimo_avance  TEXT,
    ultimo_texto   TEXT,
    atencion       TEXT    CHECK (atencion IN ('vencida', 'en_riesgo', 'sin_avance')),
    comentario     TEXT,
    comentado_por  INTEGER REFERENCES usuario(id),
    comentado_en   TEXT,
    UNIQUE (corte_id, actividad_id)
);

CREATE TABLE vacante_admision (
    id             INTEGER PRIMARY KEY,
    anio           INTEGER NOT NULL,
    ciclo          TEXT    NOT NULL CHECK (ciclo IN ('I', 'II')),
    vacantes       INTEGER NOT NULL CHECK (vacantes >= 0),
    postulantes    INTEGER CHECK (postulantes IS NULL OR postulantes >= 0),
    nota           TEXT,
    registrado_por INTEGER REFERENCES usuario(id),
    registrado_en  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (anio, ciclo)
);

CREATE TABLE rendimiento_asignatura (
    id            INTEGER PRIMARY KEY,
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id) ON DELETE CASCADE,
    anio          INTEGER NOT NULL,
    ciclo         TEXT    NOT NULL CHECK (ciclo IN ('I', 'II', 'INV', 'VER')),
    inscritos     INTEGER NOT NULL CHECK (inscritos >= 0),
    aprobados     INTEGER NOT NULL CHECK (aprobados >= 0),
    reprobados    INTEGER NOT NULL CHECK (reprobados >= 0),
    abandonos     INTEGER NOT NULL CHECK (abandonos >= 0),
    cargado_por   INTEGER REFERENCES usuario(id),
    cargado_en    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (asignatura_id, anio, ciclo),
    CHECK (aprobados + reprobados + abandonos <= inscritos)
);

CREATE TABLE comentario_piloto (
    id           INTEGER PRIMARY KEY,
    ruta         TEXT    NOT NULL,
    rol          TEXT    NOT NULL,
    texto        TEXT    NOT NULL CHECK (length(texto) BETWEEN 3 AND 2000),
    dia          TEXT    NOT NULL DEFAULT (date('now', 'localtime')),
    atendido_en  TEXT,
    atendido_por INTEGER REFERENCES usuario(id),
    nota         TEXT
);

CREATE TABLE modulo (
    clave        TEXT PRIMARY KEY,
    activo       INTEGER NOT NULL DEFAULT 0 CHECK (activo IN (0, 1)),
    cambiado_por INTEGER REFERENCES usuario(id),
    cambiado_en  TEXT
);


CREATE INDEX ix_intento_login_email_fecha ON intento_login (email, fecha);
CREATE INDEX ix_auditoria_entidad ON auditoria (entidad, entidad_id);
CREATE UNIQUE INDEX ux_investigador_msc_principal
    ON investigador_msc (usuario_id) WHERE principal = 1;
CREATE INDEX ix_investigador_msc_codigo ON investigador_msc (codigo);
CREATE INDEX ix_actividad_fecha ON actividad (fecha_inicio);
CREATE INDEX ix_producto_anio ON producto (anio);
CREATE INDEX ix_producto_autor_inv ON producto_autor (investigador_id);
CREATE INDEX ix_proyecto_objetivo ON proyecto_objetivo (proyecto_id, orden);
CREATE INDEX ix_proyecto_participante_inv ON proyecto_participante (investigador_id);
CREATE INDEX ix_actividad_proyecto_estado ON actividad_proyecto (proyecto_id, estado);
CREATE INDEX ix_producto_proyecto_estado ON producto_proyecto (proyecto_id, estado);
CREATE INDEX ix_proyecto_tipo ON proyecto (tipo, estado);
CREATE INDEX ix_propuesta_periodo ON propuesta_institucional (periodo, estado);
CREATE INDEX ix_propuesta_evento ON propuesta_evento (propuesta_id, fecha);
CREATE INDEX ix_revista_titulo ON revista (titulo);
CREATE INDEX ix_revista_indice ON revista_indice (revista_id, indice_id);
CREATE INDEX ix_producto_revista ON producto (revista_id);
CREATE UNIQUE INDEX ux_producto_openalex ON producto (openalex_id) WHERE openalex_id IS NOT NULL;
CREATE INDEX ix_estudiante_externo ON estudiante (externo_id);
CREATE INDEX ix_proyecto_contraparte ON proyecto_contraparte (proyecto_id);
CREATE INDEX ix_investigador_linea ON investigador_linea (linea_id);
CREATE INDEX ix_proyecto_linea ON proyecto_linea (linea_id);
CREATE INDEX ix_vinculo_usuario ON vinculo (usuario_id, unidad_id, fecha_inicio);
CREATE INDEX ix_grado_academico_usuario ON grado_academico (usuario_id);
CREATE UNIQUE INDEX ux_plan_asignatura ON plan_asignatura (plan_id, asignatura_id) WHERE asignatura_id IS NOT NULL;
CREATE INDEX ix_oferta_docente_usuario ON oferta_docente (usuario_id);
CREATE INDEX ix_participante_carga_vinculo ON participante_carga (vinculo_id);
CREATE INDEX ix_aviso_carga_proyecto ON aviso_carga (proyecto_id, atendido_en);
CREATE INDEX ix_notificacion_usuario ON notificacion (usuario_id, leida_en, creada_en);
CREATE INDEX ix_actividad_participante_inv ON actividad_participante (investigador_id);
CREATE INDEX ix_producto_msc_codigo ON producto_msc (codigo);
CREATE UNIQUE INDEX ux_producto_publicado_como ON producto (publicado_como_id) WHERE publicado_como_id IS NOT NULL;
CREATE UNIQUE INDEX ux_estudiante_ru ON estudiante (registro_universitario) WHERE registro_universitario IS NOT NULL;
CREATE INDEX ix_estudiante_cohorte ON estudiante (cohorte_anio, cohorte_ciclo);
CREATE INDEX ix_token_acceso_usuario ON token_acceso (usuario_id, proposito);
CREATE INDEX ix_actividad_estudiantil_persona ON actividad_estudiantil (externo_id);
CREATE INDEX ix_actividad_estudiantil_estado ON actividad_estudiantil (estado);
CREATE INDEX ix_pregunta_encuesta ON pregunta (encuesta_id, orden);
CREATE INDEX ix_respuesta_encuesta ON respuesta (encuesta_id);
CREATE INDEX ix_respuesta_item ON respuesta_item (pregunta_id);
CREATE UNIQUE INDEX ux_tutoria_vigente ON tutoria_asignacion (externo_id) WHERE hasta IS NULL;
CREATE INDEX ix_tutoria_tutor ON tutoria_asignacion (tutor_id) WHERE hasta IS NULL;
CREATE INDEX ix_tutoria_reunion_persona ON tutoria_reunion (externo_id, fecha);
CREATE INDEX ix_solicitud_destino ON solicitud_mentoria (a_externo_id, estado);
CREATE INDEX ix_solicitud_origen ON solicitud_mentoria (de_externo_id, estado);
CREATE INDEX ix_correo_pendiente_proximo ON correo_pendiente (proximo_intento);
CREATE INDEX ix_rol_asignado_usuario ON rol_asignado (usuario_id, rol);
CREATE INDEX ix_criterio_calidad_dimension ON criterio_calidad (dimension_id);
CREATE INDEX ix_indicador_calidad_criterio ON indicador_calidad (criterio_id);
CREATE INDEX ix_indicador_atributo_atributo ON indicador_atributo (atributo_id);
CREATE INDEX ix_evidencia_calidad_sha256 ON evidencia_calidad (sha256);
CREATE INDEX ix_evidencia_criterio_criterio ON evidencia_criterio (criterio_id);
CREATE UNIQUE INDEX ux_autoevaluacion_en_curso ON autoevaluacion (marco_id) WHERE estado = 'en_curso';
CREATE INDEX ix_juicio_criterio_criterio ON juicio_criterio (criterio_id);
CREATE INDEX ix_accion_mejora_plazo ON accion_mejora (estado, plazo);
CREATE INDEX ix_accion_mejora_responsable ON accion_mejora (responsable_id);
CREATE UNIQUE INDEX ux_encuesta_hito ON encuesta (hito) WHERE hito IS NOT NULL AND estado != 'cerrada';
CREATE INDEX ix_actividad_convenio ON actividad_convenio (convenio_id, fecha);
CREATE INDEX ix_comunicado_estado ON comunicado (estado, publicado_en);
CREATE INDEX ix_destinatario_usuario ON comunicado_destinatario (usuario_id);
CREATE INDEX ix_tramite_grado_externo ON tramite_grado (externo_id);
CREATE UNIQUE INDEX ux_area_investigacion_nombre ON area_investigacion (lower(nombre));
CREATE INDEX ix_linea_area ON linea_investigacion (area_id);
CREATE INDEX ix_ia_uso_funcion ON ia_uso (funcion_clave, creado_en);
CREATE INDEX ix_ia_uso_entidad ON ia_uso (entidad_tipo, entidad_id);
CREATE INDEX ix_ia_cierre_funcion ON ia_cierre (funcion_clave, fecha);
CREATE INDEX ix_producto_linea_linea ON producto_linea (linea_id);
CREATE INDEX ix_capacitacion_fin ON capacitacion (fecha_fin);
CREATE INDEX ix_capacitacion_usuario ON capacitacion (usuario_id);
CREATE INDEX ix_intento_login_ip_fecha ON intento_login (ip, fecha);
CREATE UNIQUE INDEX ux_plan_vigente ON plan_estudios (programa_id) WHERE estado = 'vigente';
CREATE INDEX ix_plan_reforma ON plan_estudios (reforma_id);
CREATE INDEX ix_mencion_asignatura_pa ON mencion_asignatura (plan_asignatura_id);
CREATE INDEX ix_equivalencia_destino ON equivalencia (plan_destino_id, plan_origen_id);
CREATE INDEX ix_gestion_cambio_gestion ON gestion_cambio (gestion_id, fecha_efecto);
CREATE INDEX ix_tutoria_solicitud_tutor ON tutoria_solicitud (tutor_id, estado);
CREATE INDEX ix_tutoria_solicitud_externo ON tutoria_solicitud (externo_id, estado);
CREATE INDEX ix_oportunidad_estado ON oportunidad (estado, cierre);
CREATE INDEX ix_tema_grado_estado ON tema_grado (estado, docente_id);
CREATE INDEX ix_caso_apoyo_externo ON caso_apoyo (externo_id, estado);
CREATE INDEX ix_consulta_estado ON consulta (estado, creada_en);
CREATE INDEX ix_consulta_externo ON consulta (externo_id);
CREATE INDEX ix_adjunto_entidad ON adjunto (entidad, entidad_id);
CREATE INDEX ix_recurso_estado ON recurso (estado, creado_en);
CREATE INDEX ix_preferencia_oferta_asignatura ON preferencia_oferta (gestion_id, asignatura_id);
CREATE UNIQUE INDEX ux_programa_borrador ON programa_analitico (asignatura_id, gestion_id) WHERE estado = 'borrador';
CREATE UNIQUE INDEX ux_programa_version ON programa_analitico (asignatura_id, gestion_id, version) WHERE version IS NOT NULL;
CREATE INDEX ix_programa_asignatura ON programa_analitico (asignatura_id, estado);
CREATE INDEX ix_evaluacion_respuesta ON evaluacion_respuesta (evaluacion_id, oferta_id);
CREATE INDEX ix_evaluacion_consulta ON evaluacion_consulta (evaluacion_id, docente_id);
CREATE INDEX ix_producto_acceso_texto ON producto_acceso (texto);
CREATE INDEX ix_actividad_mejora_accion ON actividad_mejora (accion_id);
CREATE INDEX ix_actividad_mejora_responsable ON actividad_mejora (responsable_id, estado);
CREATE INDEX ix_actividad_mejora_plazo ON actividad_mejora (estado, plazo);
CREATE INDEX ix_reprogramacion_mejora_actividad ON reprogramacion_mejora (actividad_id, estado);
CREATE INDEX ix_avance_accion_actividad ON avance_accion (actividad_id);
CREATE INDEX ix_corte_mejora_marco ON corte_mejora (marco_id, fecha);
CREATE INDEX ix_corte_actividad_corte ON corte_actividad (corte_id, atencion);
CREATE INDEX ix_rendimiento_gestion ON rendimiento_asignatura (anio, ciclo);
CREATE INDEX ix_comentario_piloto_pendientes ON comentario_piloto (atendido_en, dia);
CREATE INDEX ix_evidencia_calidad_actividad ON evidencia_calidad (actividad_id);

-- Datos de referencia.

INSERT INTO unidad (id, sigla, nombre, tipo, superior_id) VALUES
    (1, 'UNIV', 'Universidad', 'universidad', NULL),
    (2, 'FAC', 'Facultad', 'facultad', 1),
    (3, 'CARR', 'Carrera', 'carrera', 2),
    (4, 'INST', 'Instituto', 'instituto', 3);

INSERT INTO tipo_producto (id, nombre, admite_revision, orden, activo, del_sistema) VALUES
    (1, 'Artículo en revista', 1, 10, 1, 1),
    (2, 'Artículo en actas de congreso', 1, 20, 1, 1),
    (3, 'Libro', 1, 30, 1, 1),
    (4, 'Capítulo de libro', 1, 40, 1, 1),
    (5, 'Reporte de investigación', 0, 50, 1, 1),
    (6, 'Preprint', 0, 60, 1, 1),
    (7, 'Presentación', 0, 70, 1, 1),
    (8, 'Software', 0, 80, 1, 1),
    (9, 'Tesis dirigida', 0, 90, 1, 1),
    (10, 'Patente', 0, 100, 1, 1),
    (11, 'Traducción', 0, 110, 1, 1);

INSERT INTO tipo_actividad (id, nombre, orden, activo, del_sistema) VALUES
    (1, 'Seminario', 10, 1, 1),
    (2, 'Congreso', 20, 1, 1),
    (3, 'Taller / Workshop', 30, 1, 1),
    (4, 'Escuela', 40, 1, 1),
    (5, 'Curso', 50, 1, 1),
    (6, 'Visita de investigación', 60, 1, 1),
    (7, 'Estancia o pasantía de investigación', 70, 1, 1),
    (8, 'Organización de evento', 80, 1, 1),
    (9, 'Comité científico o editorial', 90, 1, 1),
    (10, 'Charla de divulgación', 100, 1, 1),
    (11, 'Transferencia de conocimiento', 110, 1, 1),
    (12, 'Participación en red de investigación', 120, 1, 1),
    (13, 'Premio o distinción', 130, 1, 1),
    (14, 'Arbitraje de artículos', 140, 1, 1),
    (15, 'Prestación de servicios', 150, 1, 1);

INSERT INTO indice (id, nombre, cuenta_como_indexado, orden, activo, cuenta_como_arbitrado, del_sistema) VALUES
    (1, 'Web of Science (SCIE)', 1, 10, 1, 0, 1),
    (2, 'Web of Science (ESCI)', 1, 20, 1, 0, 1),
    (3, 'Scopus', 1, 30, 1, 0, 1),
    (4, 'SciELO', 1, 40, 1, 0, 1),
    (5, 'MathSciNet', 1, 50, 1, 0, 1),
    (6, 'zbMATH Open', 1, 60, 1, 0, 1),
    (7, 'Latindex Catálogo', 0, 70, 1, 1, 1);
