-- Repositorio de evidencias del marco de calidad (PLAN §57, etapa 4).
--
-- Una evidencia es un documento subido (acta, resolución, convenio…), un enlace o un informe generado por el sistema, y
-- respalda uno o más criterios del marco. Los archivos (documentos e informes) guardan su huella SHA-256, para probar
-- después que el archivo entregado es el mismo; por eso no se reemplazan: se agrega otra evidencia. Los archivos se
-- guardan con nombre aleatorio en <datos>/evidencias (como los adjuntos), y no en `adjunto`, que solo admite PDF e imágenes
-- de actividades y productos.
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
    registrado_en  TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK ((tipo = 'enlace') = (url IS NOT NULL)),
    CHECK ((tipo = 'enlace') = (archivo IS NULL)),
    CHECK ((tipo = 'informe') = (informe IS NOT NULL)),
    CHECK (archivo IS NULL OR sha256 IS NOT NULL)
);
CREATE INDEX ix_evidencia_calidad_sha256 ON evidencia_calidad (sha256);

CREATE TABLE evidencia_criterio (
    evidencia_id INTEGER NOT NULL REFERENCES evidencia_calidad(id) ON DELETE CASCADE,
    criterio_id  INTEGER NOT NULL REFERENCES criterio_calidad(id) ON DELETE CASCADE,
    PRIMARY KEY (evidencia_id, criterio_id)
);
CREATE INDEX ix_evidencia_criterio_criterio ON evidencia_criterio (criterio_id);
