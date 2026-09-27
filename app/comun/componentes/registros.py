"""Piezas genéricas de fichas y listas: insignias, enlaces a personas, filtros y datos."""
import fasthtml.common as fh
from fasthtml.common import A, Div, Input, Option, Select, Span
from monsterui.all import TextPresets, UkIcon


def insignia(texto, tono="gris", titulo=None, icono=None):
    tonos = {
        "gris": "bg-muted text-foreground",
        "azul": "bg-primary/15 text-primary",
        "verde": "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300",
        "ambar": "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
        "rojo": "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
    }
    return Span(UkIcon(icono, height=12, width=12) if icono else "", texto, title=titulo,
                cls=f"inline-flex items-center gap-1 text-xs rounded px-2 py-0.5 {tonos[tono]}")


def enlace_persona(p, clase=""):
    """Nombre enlazado al perfil si es del instituto; texto plano si es externo."""
    nombre = f"{p['nombres']} {p['apellidos']}"
    if p["interno"]:
        return A(nombre, href=f"/investigadores/{p['id']}", cls=f"text-primary hover:underline {clase}")
    return Span(nombre, title=p.get("afiliacion") or "", cls=clase)


def filtros(id_form: str, url_lista: str, id_destino: str, texto: str, anio: str, anios,
            tipo_id: str, tipos, extra=()):
    """Barra de filtros: cada cambio pide la lista a `url_lista` y la reemplaza (sin recargar)."""
    return fh.Form(
        Input(type="search", name="q", value=texto, placeholder="Buscar por título…",
              cls="uk-input max-w-xs", aria_label="Buscar"),
        Select(Option("Todos los años", value=""),
               *[Option(str(a), value=str(a), selected=str(a) == anio) for a in anios],
               name="anio", cls="uk-select w-40", aria_label="Año"),
        Select(Option("Todos los tipos", value=""),
               *[Option(t["nombre"], value=str(t["id"]), selected=str(t["id"]) == tipo_id)
                 for t in tipos],
               name="tipo", cls="uk-select w-56", aria_label="Tipo"),
        *extra,
        # La URL de la página la actualiza el servidor (cabecera HX-Replace-Url): así se puede
        # recargar o compartir la vista filtrada.
        id=id_form, hx_get=url_lista, hx_target=f"#{id_destino}", hx_swap="outerHTML",
        hx_trigger="input delay:300ms, search", onsubmit="return false",
        cls="flex flex-wrap gap-3 items-center mb-6")


def url_filtrada(ruta: str, **params) -> str:
    """'/productos', q='x', anio='' → '/productos?q=x' (omite los vacíos)."""
    from urllib.parse import urlencode
    limpios = {k: v for k, v in params.items() if v not in ("", None, False)}
    return f"{ruta}?{urlencode(limpios)}" if limpios else ruta


def dato(etiqueta, valor):
    """Fila etiqueta/valor para fichas de detalle; se omite si no hay valor."""
    if not valor:
        return ""
    return Div(Span(etiqueta, cls=(TextPresets.muted_sm, "w-40 shrink-0")), Div(valor),
               cls="flex flex-col sm:flex-row gap-1 py-1.5")


