-- Fase 2, paso 4c (PLAN.md, sección 23): datos personales de la persona académica. Hoy, la fecha
-- de nacimiento (Guía de Antecedentes, hoja 11: distribución por edad del cuerpo académico).
--
-- La registra y la ve solo Administración del sistema; la propia persona la ve en «Mi perfil»,
-- sin editarla. Los informes usan tramos de edad, nunca la fecha. Tabla aparte para que ninguna
-- consulta general (u.*, i.*) la arrastre por descuido.
CREATE TABLE datos_personales (
    usuario_id       INTEGER PRIMARY KEY REFERENCES usuario(id) ON DELETE CASCADE,
    fecha_nacimiento TEXT,
    actualizado_por  INTEGER REFERENCES usuario(id),
    actualizado_en   TEXT NOT NULL DEFAULT (datetime('now'))
);
