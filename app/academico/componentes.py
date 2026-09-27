"""Piezas comunes de la sección Docencia."""
from fasthtml.common import A, Div

PESTANAS = (("planes", "Planes de estudio", "/docencia/planes"), ("oferta", "Oferta y docentes", "/docencia/oferta"),
            ("gestiones", "Gestiones", "/docencia/gestiones"))


def pestanas(activa: str):
    return Div(*[A(texto, href=url, cls="px-3 py-2 text-sm border-b-2 " + (
        "border-primary text-primary font-medium" if clave == activa else "border-transparent hover:text-primary"))
        for clave, texto, url in PESTANAS], cls="flex flex-wrap gap-2 border-b border-border mb-6")
