"""Piezas comunes de la sección Docencia."""

from app.comun import permisos, vinculos
from app.comun.db import get_db


def tiene_docencia(auth: dict | None) -> bool:
    """¿Tiene vínculo con la Carrera o materias asignadas? (para mostrar «Mi docencia»)."""
    if not auth:
        return False
    return bool(get_db().q("""SELECT 1 FROM vinculo WHERE usuario_id = :u
                              UNION SELECT 1 FROM oferta_docente WHERE usuario_id = :u LIMIT 1""", {"u": auth["id"]}))


def prepara_semestres(auth: dict | None) -> bool:
    """Dirección de Carrera y Coordinación académica (preparación del semestre)."""
    return bool(auth) and (permisos.puede(auth, "gestionar_oferta")
                           or permisos.puede(auth, "gestionar_vinculos", vinculos.carrera()))


# Secciones de Docencia y Estudiantes en el menú lateral (app/navegacion.py, PLAN.md §53).
# (clave, texto, url, condición): la condición es una acción de permisos o una función de auth.
PESTANAS = (("mia", "Mi docencia", "/docencia/mia", tiene_docencia),
            ("preparacion", "Preparación del semestre", "/docencia/preparacion", prepara_semestres),
            ("planes", "Planes de estudio", "/docencia/planes", None),
            ("oferta", "Oferta y docentes", "/docencia/oferta", None),
            ("carga", "Carga horaria", "/docencia/carga", "ver_carga"),
            ("cohortes", "Cohortes estudiantiles", "/docencia/cohortes", "ver_seguimiento_estudiantil"),
            ("encuestas", "Encuestas", "/docencia/encuestas", "ver_seguimiento_estudiantil"),
            ("tutoria", "Tutoría", "/docencia/tutoria", "ver_seguimiento_estudiantil"),
            ("egresados", "Egresados", "/docencia/egresados", "ver_seguimiento_estudiantil"),
            # Para los demás es una lista de fechas de solo lectura (la oferta ya elige la gestión): PLAN.md §54.
            ("gestiones", "Gestiones", "/docencia/gestiones", "gestionar_oferta"))


def visible(condicion, auth) -> bool:
    """¿Ve la persona una pestaña? `condicion`: None (todos), una acción de permisos o una función de auth."""
    if condicion is None:
        return True
    return condicion(auth) if callable(condicion) else permisos.puede(auth, condicion)
