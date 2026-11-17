"""Piezas de interfaz comunes a los servicios (PLAN §58): formularios simples que envían y vuelven a la página (con un
aviso), botones de acción y descargas de adjuntos."""
from urllib.parse import quote

import fasthtml.common as fh
from fasthtml.common import A, Div, FileResponse, Option, P, Response, Select
from monsterui.all import H3, Button, ButtonT, Card, FormLabel, TextPresets, UkIcon

from app.comun.componentes.bandeja import le_toca  # noqa: F401  (lo usan las pantallas de servicios)
from app.comun import formato
from app.comun import adjuntos

ACEPTA = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"


def no_autorizado():
    return Response("No autorizado", status_code=403)


def no_encontrado():
    return Response("No encontrado", status_code=404)


def fecha(iso: str | None) -> str:
    """'2026-11-12T14:30' → '12 nov 2026, 14:30' (PLAN §62: una sola forma de escribir fechas)."""
    return formato.momento(iso)


def formulario(url: str, *contenido, archivos: bool = False, cls: str = "space-y-4", **kw):
    """Formulario normal (sin HTMX): envía, el servidor guarda y vuelve a la página con un aviso."""
    return fh.Form(*contenido, method="post", action=url, cls=cls,
                   **({"enctype": "multipart/form-data"} if archivos else {}), **kw)


def boton_post(texto, url: str, icono: str | None = None, cls=ButtonT.default, confirmar: str | None = None, **kw):
    """Botón que hace una acción por POST (con confirmación opcional) y vuelve a la página."""
    return Button(UkIcon(icono, height=14, width=14) if icono else "", texto, type="button", cls=cls,
                  hx_post=url, hx_confirm=confirmar, **kw)


def enviar(texto: str = "Guardar", cls=ButtonT.primary, deshabilitado: bool = False, **kw):
    return Button(texto, type="submit", cls=cls, disabled=deshabilitado or None, **kw)


def seleccion(etiqueta, nombre, opciones, actual=None, vacio=None, **kw):
    actual = "" if actual is None else str(actual)
    return Div(FormLabel(etiqueta, fr=nombre),
               Select(*([Option(vacio, value="")] if vacio is not None else []),
                      *[Option(t, value=str(v), selected=str(v) == actual) for v, t in opciones],
                      id=nombre, name=nombre, cls="uk-select", **kw), cls="space-y-1")


def area(etiqueta, nombre, valor="", filas=4, ayuda=None, **kw):
    kw.setdefault("name", nombre)
    return Div(FormLabel(etiqueta, fr=nombre),
               fh.Textarea(valor or "", id=nombre, rows=str(filas), cls="uk-textarea", **kw),
               P(ayuda, cls=TextPresets.muted_sm) if ayuda else "", cls="space-y-1")


def tarjeta(titulo, *contenido, accion=None, id=None, cls=""):
    return Card(Div(H3(titulo, cls="text-base font-semibold"), accion or "",
                    cls="flex flex-wrap items-center justify-between gap-2 mb-3"),
                *contenido, id=id, cls=cls)


def falta(lista: list[str], texto_ok: str | None = None):
    """Lista de lo que falta para poder enviar (o un mensaje de que está todo)."""
    if not lista:
        return P(UkIcon("circle-check", height=14, width=14, cls="shrink-0"), texto_ok or "Está todo listo.",
                 cls="flex items-center gap-1 text-sm text-green-700 dark:text-green-300") if texto_ok else ""
    return Div(P("Antes de enviar, falta:", cls="text-sm font-medium"),
               fh.Ul(*[fh.Li(x) for x in lista], cls="list-disc pl-5 text-sm"),
               cls="rounded-md border border-amber-300 bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-200 "
                   "dark:border-amber-800 p-3 space-y-1")


def subir(url: str, etiqueta: str = "Subir PDF o imagen", nombre: str = "archivo"):
    return formulario(url, fh.Input(type="file", name=nombre, accept=ACEPTA, required=True, aria_label=etiqueta,
                                    cls="text-sm w-full min-w-0 max-w-full"),
                      enviar(etiqueta, cls=(ButtonT.default, ButtonT.sm)), archivos=True,
                      cls="flex flex-wrap items-center gap-2")


async def leer_archivo(archivo) -> tuple[bytes, str | None]:
    """→ (contenido, error)."""
    if archivo is None or not getattr(archivo, "filename", ""):
        return b"", "Elija un archivo."
    contenido = await archivo.read(adjuntos.MAX_BYTES + 1)
    if len(contenido) > adjuntos.MAX_BYTES:
        return b"", "El archivo supera los 20 MB."
    if not adjuntos.detectar_tipo(contenido):
        return b"", "Solo se admiten archivos PDF, PNG o JPG."
    return contenido, None


def descargar(adj: dict, adjunto: bool = False):
    modo = "attachment" if adjunto else "inline"
    return FileResponse(adjuntos.ruta(adj), media_type=adj["mime"], headers={
        "Content-Disposition": f"{modo}; filename*=UTF-8''{quote(adj['nombre'])}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


def enlace_adjunto(adj: dict, url: str):
    return A(UkIcon("paperclip", height=12, width=12), adj["nombre"], href=url, target="_blank",
             cls="inline-flex items-center gap-1 text-sm text-primary hover:underline")


def descarga_bytes(contenido: bytes, nombre: str, mime: str):
    return Response(contenido, media_type=mime, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(nombre)}", "Cache-Control": "private, no-store"})
