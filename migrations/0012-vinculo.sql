-- Filiación y pertenencia, etapa E1: historial de vínculo de cada investigador(a) con el instituto.
--
-- Periodos sin superposición (lo controla la aplicación). fecha_inicio vacía = ingreso desconocido
-- (se trata como «desde siempre»); fecha_fin vacía = vigente. investigador.categoria queda como la
-- categoría del vínculo vigente, recalculada por la aplicación.

CREATE TABLE vinculo (
    id            INTEGER PRIMARY KEY,
    usuario_id    INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    categoria     TEXT NOT NULL
                  CHECK (categoria IN ('titular', 'contratado', 'interino', 'invitado', 'externo')),
    fecha_inicio  TEXT,
    fecha_fin     TEXT,
    jornada_horas INTEGER CHECK (jornada_horas IS NULL OR jornada_horas BETWEEN 1 AND 60),
    nota          TEXT,
    creado_por    INTEGER REFERENCES usuario(id),
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (fecha_fin IS NULL OR fecha_inicio IS NULL OR fecha_fin >= fecha_inicio)
);
CREATE INDEX ix_vinculo_usuario ON vinculo (usuario_id, fecha_inicio);

-- Cada investigador con categoría recibe un periodo vigente con ingreso desconocido.
INSERT INTO vinculo (usuario_id, categoria)
SELECT usuario_id, categoria FROM investigador WHERE categoria IS NOT NULL;
