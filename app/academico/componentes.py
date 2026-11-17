"""Piezas comunes de la sección Docencia."""

from app.comun import permisos, vinculos
from app.comun.db import get_db


def tiene_docencia(auth: dict | None) -> bool:
    """¿Tiene vínculo con la Carrera o materias asignadas? (para mostrar «Mi docencia»)."""
    if not auth:
        return False
    return bool(get_db().q("""SELECT 1 FROM vinculo WHERE usuario_id = :u
                              UNION SELECT 1 FROM oferta_docente WHERE usuario_id = :u LIMIT 1""", {"u": auth["id"]}))


def es_docente(auth: dict | None) -> bool:
    """Vínculo, materias, tutorías, temas, tribunales o trámites de grado (para «Mis pendientes» y «Mi calendario»)."""
    from app.academico import docente
    return docente.es_docente(auth)


def ve_evaluacion(auth: dict | None) -> bool:
    """Docentes (ven su instrumento y resultados) y la Dirección de Carrera (la administra)."""
    return es_docente(auth) or bool(auth) and permisos.puede(auth, "gestionar_evaluacion_docente")


def prepara_semestres(auth: dict | None) -> bool:
    """Dirección de Carrera y Coordinación académica (preparación del semestre)."""
    return bool(auth) and (permisos.puede(auth, "gestionar_oferta")
                           or permisos.puede(auth, "gestionar_vinculos", vinculos.carrera()))


# Secciones de Docencia en el menú lateral (PLAN.md §53), en su orden. (clave, texto, url, condición): la condición es
# una acción de permisos o una función de auth. `app/academico/aportes.py` las reparte entre los módulos de docencia; las
# de Estudiantes las aporta cada módulo en su `aportes.py` (PLAN §73).
PESTANAS = (("mia", "Mi docencia", "/docencia/mia", tiene_docencia),
            ("historial", "Mi historial", "/docencia/historial", es_docente),
            ("evaluacion", "Evaluación docente", "/docencia/evaluacion", ve_evaluacion),
            ("listas", "Listas de cursos", "/docencia/listas", es_docente),
            ("programas", "Mis programas", "/docencia/programas", es_docente),
            ("preferencias", "Mis preferencias", "/docencia/preferencias", es_docente),
            ("preferencias_todas", "Preferencias de docentes", "/docencia/preferencias/todas", "gestionar_oferta"),
            ("preparacion", "Preparación del semestre", "/docencia/preparacion", prepara_semestres),
            ("planes", "Planes de estudio", "/docencia/planes", None),
            ("oferta", "Oferta y docentes", "/docencia/oferta", None),
            ("carga", "Carga horaria", "/docencia/carga", "ver_carga"),
            # Para los demás es una lista de fechas de solo lectura (la oferta ya elige la gestión): PLAN.md §54.
            ("gestiones", "Gestiones", "/docencia/gestiones", "gestionar_oferta"))


def visible(condicion, auth) -> bool:
    """¿Ve la persona una pestaña? `condicion`: None (todos), una acción de permisos o una función de auth."""
    if condicion is None:
        return True
    return condicion(auth) if callable(condicion) else permisos.puede(auth, condicion)
