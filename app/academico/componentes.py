"""Piezas comunes de la sección Docencia."""
from fasthtml.common import A, Div

from app.comun import permisos
from app.comun.db import get_db


def tiene_docencia(auth: dict | None) -> bool:
    """¿Tiene vínculo con la Carrera o materias asignadas? (para mostrar «Mi docencia»)."""
    if not auth:
        return False
    return bool(get_db().q("""SELECT 1 FROM vinculo WHERE usuario_id = :u
                              UNION SELECT 1 FROM oferta_docente WHERE usuario_id = :u LIMIT 1""", {"u": auth["id"]}))


# (clave, texto, url, condición): la condición es una acción de permisos o una función de auth.
PESTANAS = (("mia", "Mi docencia", "/docencia/mia", tiene_docencia),
            ("planes", "Planes de estudio", "/docencia/planes", None),
            ("oferta", "Oferta y docentes", "/docencia/oferta", None),
            ("carga", "Carga horaria", "/docencia/carga", "ver_carga"),
            ("gestiones", "Gestiones", "/docencia/gestiones", None))


def _visible(condicion, auth) -> bool:
    if condicion is None:
        return True
    return condicion(auth) if callable(condicion) else permisos.puede(auth, condicion)


def pestanas(activa: str, auth: dict | None = None):
    visibles = [(c, t, u) for c, t, u, condicion in PESTANAS if _visible(condicion, auth)]
    return Div(*[A(texto, href=url, cls="px-3 py-2 text-sm border-b-2 " + (
        "border-primary text-primary font-medium" if clave == activa else "border-transparent hover:text-primary"))
        for clave, texto, url in visibles], cls="flex flex-wrap gap-2 border-b border-border mb-6")
