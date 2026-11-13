-- Cambios con el semestre activo (PLAN §66, etapa 3; decisiones del 13-nov-2026).
--
-- Con la gestión activa no se borra nada: una materia que se cierra queda marcada con la fecha y el motivo
-- (`retirada_en`), una que entra con el semestre en marcha guarda su fecha (`agregada_en`), y un docente que cambia
-- conserva su fila con el primer y el último día en que dictó (`desde`, `hasta`; vacíos = todo el semestre). Así el
-- historial dice quién dictó qué y entre cuándo, y la carga horaria puede contarse por meses dictados. Cada cambio queda
-- además en `gestion_cambio`, con su motivo y quién lo registró.
ALTER TABLE oferta ADD COLUMN agregada_en   TEXT;
ALTER TABLE oferta ADD COLUMN retirada_en   TEXT;
ALTER TABLE oferta ADD COLUMN motivo_retiro TEXT;
ALTER TABLE oferta_docente ADD COLUMN desde TEXT;
ALTER TABLE oferta_docente ADD COLUMN hasta TEXT;

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
CREATE INDEX ix_gestion_cambio_gestion ON gestion_cambio (gestion_id, fecha_efecto);
