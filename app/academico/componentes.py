"""Piezas comunes de la sección Docencia."""
from fasthtml.common import A, Div

from app.comun import permisos

PESTANAS = (("planes", "Planes de estudio", "/docencia/planes", None),
            ("oferta", "Oferta y docentes", "/docencia/oferta", None),
            ("carga", "Carga horaria", "/docencia/carga", "ver_carga"),
            ("gestiones", "Gestiones", "/docencia/gestiones", None))


def pestanas(activa: str, auth: dict | None = None):
    visibles = [(c, t, u) for c, t, u, accion in PESTANAS if accion is None or permisos.puede(auth, accion)]
    return Div(*[A(texto, href=url, cls="px-3 py-2 text-sm border-b-2 " + (
        "border-primary text-primary font-medium" if clave == activa else "border-transparent hover:text-primary"))
        for clave, texto, url in visibles], cls="flex flex-wrap gap-2 border-b border-border mb-6")
