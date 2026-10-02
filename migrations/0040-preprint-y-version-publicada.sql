-- Enlace entre un preprint y su versión publicada, como registros separados (PLAN.md, sección 46).
-- Decisión de la Dirección (2-oct-2026): al registrar la versión publicada de un preprint ya registrado
-- se crea un registro nuevo enlazado y el preprint se conserva; en el CV, el perfil público y la
-- exportación BibTeX se lista solo la versión publicada (con el arXiv del preprint). Los artículos que
-- ya guardan su arXiv en el mismo registro quedan así.
--
-- La referencia va en el preprint: `publicado_como_id` apunta a su versión publicada. Una versión
-- publicada tiene a lo sumo un preprint enlazado.

ALTER TABLE producto ADD COLUMN publicado_como_id INTEGER REFERENCES producto(id) ON DELETE SET NULL;
CREATE UNIQUE INDEX ux_producto_publicado_como ON producto (publicado_como_id) WHERE publicado_como_id IS NOT NULL;
