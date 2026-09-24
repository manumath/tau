"""Piezas comunes a actividades y productos: insignias, filtros, adjuntos y confirmaciones."""
import fasthtml.common as fh
from fasthtml.common import A, Div, Input, Li, Option, P, Select, Span, Ul
from monsterui.all import Button, ButtonT, TextPresets, UkIcon

from app import adjuntos
from app.components.layout import mensaje_error


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


def seccion_adjuntos(entidad: str, entidad_id: int, editable: bool, error: str | None = None):
    lista = adjuntos.listar(entidad, entidad_id)
    seccion_id = f"adjuntos-{entidad}-{entidad_id}"
    filas = [Li(
        UkIcon("file-text" if a["mime"] == "application/pdf" else "image", height=16, width=16,
               cls="shrink-0 text-muted-foreground"),
        A(a["nombre"], href=f"/adjuntos/{a['id']}", cls="text-primary hover:underline truncate"),
        Span(adjuntos.tamano_texto(a["tamano"]), cls=(TextPresets.muted_sm, "shrink-0")),
        fh.Button(UkIcon("trash-2", height=14, width=14), type="button",
                  cls="ml-auto p-1 rounded hover:bg-muted hover:text-red-600",
                  hx_delete=f"/adjuntos/{a['id']}", hx_target=f"#{seccion_id}",
                  hx_swap="outerHTML", hx_confirm=f"¿Eliminar «{a['nombre']}»?",
                  title="Eliminar", aria_label=f"Eliminar {a['nombre']}") if editable else "",
        cls="flex items-center gap-2 py-2") for a in lista]
    subir = fh.Form(
        Button(UkIcon("paperclip", height=14, width=14), "Adjuntar archivo", type="button",
               cls=(ButtonT.default, ButtonT.sm),
               onclick="this.closest('form').querySelector('input[type=file]').click()"),
        Input(type="file", name="archivo", accept="application/pdf,image/png,image/jpeg",
              cls="hidden", aria_label="Archivo adjunto"),
        Span("PDF, PNG o JPG hasta 20 MB.", cls=TextPresets.muted_sm),
        Span(UkIcon("loader-circle", height=14, width=14, cls="animate-spin"), " Subiendo…",
             cls="htmx-indicator text-sm"),
        hx_post=f"/adjuntos/{entidad}/{entidad_id}", hx_trigger="change",
        hx_encoding="multipart/form-data", hx_target=f"#{seccion_id}", hx_swap="outerHTML",
        cls="flex flex-wrap items-center gap-3 mt-3") if editable else ""
    return Div(
        mensaje_error(error) if error else "",
        Ul(*filas, cls="divide-y divide-border") if filas
        else P("Sin archivos adjuntos.", cls=TextPresets.muted_sm),
        subir, id=seccion_id)


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


# --- Vínculos con proyectos ------------------------------------------------------------------------

TONO_VINCULO = {"pendiente": "ambar", "aprobado": "azul", "rechazado": "rojo"}
ICONO_VINCULO = {"pendiente": "clock", "aprobado": "folder-check", "rechazado": "circle-x"}


def insignias_proyectos(vinculos: list[dict]):
    """Una insignia por proyecto: «Proyecto X · pendiente». El motivo de rechazo va en el title."""
    from app.proyectos import ESTADOS_VINCULO
    return [insignia(f"{v['proyecto']} · {ESTADOS_VINCULO[v['estado']].lower()}",
                     TONO_VINCULO[v["estado"]], icono=ICONO_VINCULO[v["estado"]],
                     titulo=f"Motivo: {v['comentario']}" if v.get("comentario") else None)
            for v in vinculos]


def casillas_proyectos(tipo: str, registro_id: int | None, usuario: dict,
                       marcados_form: list[int] | None = None, preseleccion: int | None = None):
    """Casillas «Vincular a proyectos» para el formulario de una actividad o un producto."""
    from app import proyectos
    disponibles = {p["id"]: p for p in proyectos.para_proponer(usuario["id"])}
    vinculos = {v["proyecto_id"]: v for v in proyectos.vinculos_de(tipo, registro_id)} \
        if registro_id else {}
    ids = list(dict.fromkeys([*disponibles, *vinculos]))
    if not ids:
        return ""
    filas = []
    for pid in ids:
        p = disponibles.get(pid)
        v = vinculos.get(pid)
        nombre = p["nombre"] if p else v["proyecto"]
        if marcados_form is not None:
            marcado = pid in marcados_form or (v and v["estado"] == "aprobado")
        else:
            marcado = bool(v) or pid == preseleccion
        directo = p and p["mi_rol"] in proyectos.ROLES_RESPONSABLES
        if v and v["estado"] == "aprobado":
            nota = Span("aprobado · solo un responsable puede desvincularlo", cls=TextPresets.muted_sm)
        elif v and v["estado"] == "pendiente":
            nota = Span("propuesta pendiente de aprobación", cls="text-sm text-amber-600")
        elif v and v["estado"] == "rechazado":
            nota = Span(f"rechazado: «{v['comentario']}». Si lo deja marcado, se vuelve a proponer.",
                        cls="text-sm text-red-600")
        elif directo:
            nota = Span("usted es responsable: se vincula directamente", cls=TextPresets.muted_sm)
        else:
            nota = Span("quedará pendiente hasta que un responsable lo apruebe", cls=TextPresets.muted_sm)
        bloqueado = (v and v["estado"] == "aprobado") or not p
        filas.append(fh.Label(
            Input(type="checkbox", name="proyecto", value=str(pid), checked=marcado,
                  disabled=bloqueado, cls="uk-checkbox mt-0.5"),
            Div(Span(nombre, cls="font-medium text-sm"), nota, cls="flex flex-col"),
            cls="flex items-start gap-2"))
    return Div(Span("Vincular a proyectos", cls="uk-form-label"),
               Div(*filas, cls="space-y-2 rounded-md border border-border p-3"),
               cls="space-y-2")
