"""Piezas del menú lateral que usan los aportes de cada módulo (PLAN §73, etapa 2): cada módulo entrega sus ítems con
`item` y `app/navegacion.py` los ordena en grupos."""
from fasthtml.common import Span


def item(clave, texto, href, icono, insignia=None) -> dict:
    return {"clave": clave, "texto": texto, "href": href, "icono": icono, "insignia": insignia}


def contador(id_, url):
    """Insignia que se carga aparte y se refresca sola (para no consultar la base en cada página)."""
    return Span(id=id_, cls="hidden", hx_get=url, hx_trigger="load", hx_swap="outerHTML")


def agenda_en_el_menu() -> list[tuple]:
    """«Mis pendientes» y «Mi calendario» de toda la persona, bajo «Inicio». Los aporta cada módulo que le da algo que
    hacer (docencia, investigación, plan de mejora); el menú los muestra una sola vez."""
    return [(None, 5, item("pendientes", "Mis pendientes", "/pendientes", "list-checks")),
            (None, 6, item("calendario", "Mi calendario", "/calendario", "calendar-days"))]

