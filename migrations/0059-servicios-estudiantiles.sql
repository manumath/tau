-- Servicios para estudiantes (PLAN §58; decisiones del 7-nov-2026): comunicados y eventos con convocados, convocatorias
-- a auxiliaturas con tribunal por ítem (Reglamento General de Auxiliares Académicos, Res. HCU 251/2021) y trámites de
-- proyecto de grado (perfil y documento final) con tutor y tribunal (Reglamento General de Tipos y Modalidades de
-- Graduación, CEUB). `adjunto.entidad` admite los documentos de estos trámites: SQLite no cambia un CHECK, se recrea la
-- tabla conservando todos los adjuntos.
CREATE TABLE adjunto_nueva (
    id         INTEGER PRIMARY KEY,
    entidad    TEXT    NOT NULL CHECK (entidad IN ('actividad', 'producto', 'actividad_estudiantil',
                                                  'convocatoria_auxiliatura', 'requisito_postulacion', 'tramite_grado')),
    entidad_id INTEGER NOT NULL,
    nombre     TEXT    NOT NULL,             -- nombre original, solo para mostrar y descargar
    archivo    TEXT    NOT NULL UNIQUE,      -- nombre aleatorio en <datos>/adjuntos
    mime       TEXT    NOT NULL,
    tamano     INTEGER NOT NULL,
    subido_por INTEGER NOT NULL REFERENCES usuario(id),
    subido_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO adjunto_nueva (id, entidad, entidad_id, nombre, archivo, mime, tamano, subido_por, subido_en)
    SELECT id, entidad, entidad_id, nombre, archivo, mime, tamano, subido_por, subido_en FROM adjunto;
DROP TABLE adjunto;
ALTER TABLE adjunto_nueva RENAME TO adjunto;
CREATE INDEX ix_adjunto_entidad ON adjunto (entidad, entidad_id);

-- --- Comunicados y eventos --------------------------------------------------------------------------------------------
-- Los publica una dirección, la Coordinación académica o el responsable de un proyecto. «Para todos» llega a todas las
-- cuentas activas; si no, a los convocados. La asistencia la registra el organizador, solo si no es para todos.
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
);
CREATE INDEX ix_comunicado_estado ON comunicado (estado, publicado_en);

CREATE TABLE comunicado_destinatario (
    comunicado_id INTEGER NOT NULL REFERENCES comunicado(id) ON DELETE CASCADE,
    usuario_id    INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    respuesta     TEXT CHECK (respuesta IN ('asistire', 'no_podre')),
    respondido_en TEXT,
    asistio       INTEGER CHECK (asistio IN (0, 1)),    -- lo registra el organizador después del evento
    PRIMARY KEY (comunicado_id, usuario_id)
);
CREATE INDEX ix_destinatario_usuario ON comunicado_destinatario (usuario_id);

-- --- Auxiliaturas ------------------------------------------------------------------------------------------------------
-- Convocatoria de una gestión (de docencia o de investigación), con requisitos, ítems (materia o proyecto, plazas, horas)
-- y un tribunal de dos docentes y dos estudiantes por ítem. Se publica solo con el número de la resolución del Consejo.
CREATE TABLE convocatoria_auxiliatura (
    id          INTEGER PRIMARY KEY,
    gestion_id  INTEGER NOT NULL REFERENCES gestion_academica(id),
    modalidad   TEXT NOT NULL CHECK (modalidad IN ('docencia', 'investigacion')),
    numero      INTEGER NOT NULL DEFAULT 1 CHECK (numero IN (1, 2)),   -- primera o segunda convocatoria (art. 10–11)
    titulo      TEXT NOT NULL,
    publicacion TEXT,                      -- fecha de publicación
    cierre      TEXT,                      -- cierre de la recepción: 'AAAA-MM-DDTHH:MM'
    examen      TEXT,                      -- examen escrito: 'AAAA-MM-DDTHH:MM'
    lugar       TEXT,
    resolucion  TEXT,                      -- número (y fecha) de la resolución del Consejo de Carrera
    estado      TEXT NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'publicada', 'concluida')),
    creado_por  INTEGER NOT NULL REFERENCES usuario(id),
    creado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE requisito_auxiliatura (
    id              INTEGER PRIMARY KEY,
    convocatoria_id INTEGER NOT NULL REFERENCES convocatoria_auxiliatura(id) ON DELETE CASCADE,
    texto           TEXT NOT NULL,
    acredita        TEXT NOT NULL CHECK (acredita IN ('documento', 'declaracion', 'sistema')),
    orden           INTEGER NOT NULL DEFAULT 0
);

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
);

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
    enviada_en TEXT,
    UNIQUE (item_id, externo_id)
);

CREATE TABLE postulacion_requisito (
    id             INTEGER PRIMARY KEY,    -- los documentos son adjuntos de la entidad 'requisito_postulacion'
    postulacion_id INTEGER NOT NULL REFERENCES postulacion_auxiliatura(id) ON DELETE CASCADE,
    requisito_id   INTEGER NOT NULL REFERENCES requisito_auxiliatura(id) ON DELETE CASCADE,
    declarado      INTEGER NOT NULL DEFAULT 0 CHECK (declarado IN (0, 1)),
    UNIQUE (postulacion_id, requisito_id)
);

-- Calificación de cada miembro del tribunal por fase: habilitación (1 sí, 0 no), méritos (0–30), escrito (0–35) y oral
-- (0–35). La de la fase es el promedio; hacen falta al menos tres miembros (decisión 4 del 7-nov-2026).
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

-- Las impugnaciones se presentan por escrito fuera del sistema; TAU solo las registra (decisión 8 del 7-nov-2026).
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

-- --- Proyecto de grado ------------------------------------------------------------------------------------------------
-- Perfil y documento final: el estudiante lo prepara con su tutor, la Dirección o la Coordinación designa el tribunal y
-- todos sus miembros deben dictaminar (decisión 4); 15 días hábiles por revisión (decisión 3).
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
CREATE INDEX ix_tramite_grado_externo ON tramite_grado (externo_id);

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

-- Recordatorios ya enviados (3 días hábiles antes del plazo y al vencer), una vez por ronda y persona.
CREATE TABLE recordatorio_grado (
    tramite_id INTEGER NOT NULL REFERENCES tramite_grado(id) ON DELETE CASCADE,
    ronda      INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    tipo       TEXT NOT NULL CHECK (tipo IN ('por_vencer', 'vencido')),
    PRIMARY KEY (tramite_id, ronda, usuario_id, tipo)
);
