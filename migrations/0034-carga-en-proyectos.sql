-- Término del vínculo y carga horaria de los participantes en proyectos (PLAN.md, sección 26).
--
-- 1. Contratados, interinos e invitados se vinculan por un periodo con término; los titulares no
--    tienen término, pero se puede terminar su vínculo (retiro, renuncia, despido, fallecimiento).
--    Se registra el motivo del término.
-- 2. En los proyectos institucionales, el responsable asigna a cada participante del instituto una
--    carga horaria (múltiplos de 32 h/mes) que sale de la carga de investigación (proyectos de
--    investigación) o de extensión (interacción social) de su vínculo. Rige solo mientras ese
--    periodo de vínculo está vigente: en un nuevo periodo no se reasigna sola.
-- 3. Avisos a los responsables: un participante con carga quedó desvinculado, o volvió a vincularse
--    y tiene carga libre para asignar.

ALTER TABLE vinculo ADD COLUMN motivo_termino TEXT
    CHECK (motivo_termino IS NULL OR motivo_termino IN
           ('fin_contrato', 'renuncia', 'retiro', 'despido', 'fallecimiento', 'otro'));

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
CREATE INDEX ix_participante_carga_vinculo ON participante_carga (vinculo_id);

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
CREATE INDEX ix_aviso_carga_proyecto ON aviso_carga (proyecto_id, atendido_en);
