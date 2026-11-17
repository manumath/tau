"""Enlace entre un preprint y su versión publicada (PLAN.md §46), desde la ficha del preprint: elegir la
versión entre los productos ya registrados o importarla por DOI (queda enlazada), y desenlazar."""
from fasthtml.common import APIRouter, Div, HtmxResponseHeaders, Input, Label, P, Response, Span
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Form, TextPresets

from app.investigacion import productos
from app.comun.componentes.avisos_emergentes import aviso_con_deshacer
from app.comun.componentes.layout import ID_MODAL, cerrar_modal, mensaje_error, modal
from app.comun.db import auditar
from app.investigacion.rutas.productos.formulario import caja_importar
from app.investigacion.rutas.productos.lista import EVENTO

rt = APIRouter()


def _preprint(pid, uid):
    """(preprint, None) si existe, es un preprint y quien pide puede editarlo; si no, (None, respuesta)."""
    p = productos.obtener(pid)
    if not p or not productos.es_preprint(p):
        return None, Response("No encontrado", status_code=404)
    if not productos.puede_editar(p, uid):
        return None, Response("No autorizado", status_code=403)
    return p, None


def modal_version(pre, uid, errores=()):
    candidatos = productos.candidatos_version(pre, uid)
    opciones = [Label(Input(type="radio", name="publicada", value=str(c["id"]), cls="uk-radio mt-1",
                            checked=i == 0 and productos.parecido(c["titulo"], pre["titulo"]) >= 0.85),
                      Div(Span(c["titulo"], cls="font-medium"),
                          Span(f" · {c['tipo']} · {c['anio']}" + (f" · doi:{c['doi']}" if c["doi"] else ""),
                               cls=TextPresets.muted_sm)),
                      cls="flex items-start gap-2 px-3 py-2 hover:bg-muted cursor-pointer")
                for i, c in enumerate(candidatos)]
    return modal(
        "Versión publicada del preprint",
        mensaje_error(*errores),
        P(f"«{pre['titulo']}»" + (f" (arXiv:{pre['arxiv_id']})" if pre["arxiv_id"] else ""), cls="font-medium mb-1"),
        P("Al enlazarlo, el CV, el perfil público y la exportación BibTeX listan solo la versión publicada, con el "
          "arXiv del preprint. El preprint sigue en «Mis productos».", cls=(TextPresets.muted_sm, "mb-4")),
        Form(P("Elija la versión publicada entre sus productos (los de título más parecido, primero):",
               cls="text-sm font-medium"),
             Div(*opciones, cls="max-h-64 overflow-y-auto rounded-md border border-border divide-y divide-border")
             if opciones else P("No tiene otros productos registrados que puedan serlo.", cls=TextPresets.muted_sm),
             Div(Button("Enlazar", type="submit", cls=(ButtonT.primary, ButtonT.sm), disabled=not opciones),
                 cls="flex justify-end"),
             hx_post=f"/productos/{pre['id']}/version", hx_target=f"#{ID_MODAL}", cls="space-y-2"),
        P("¿Aún no la registró? Impórtela por su DOI: quedará enlazada a este preprint.",
          cls="text-sm font-medium mt-6 mb-2"),
        caja_importar(preprint=pre["id"]),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
            cls="flex justify-end mt-4"),
        ancho="max-w-2xl")


@rt("/productos/{pid}/version")
def get(auth, pid: int):
    pre, error = _preprint(pid, auth["id"])
    return error or modal_version(pre, auth["id"])


@rt("/productos/{pid}/version")
def post(auth, sess, pid: int, publicada: int = None):
    pre, error = _preprint(pid, auth["id"])
    if error:
        return error
    pub = productos.obtener(publicada) if publicada else None
    if not pub or not productos.puede_editar(pub, auth["id"]):
        return modal_version(pre, auth["id"], ["Elija la versión publicada entre sus productos."])
    if (problema := productos.enlazar_version(pid, pub["id"])):
        return modal_version(pre, auth["id"], [problema])
    auditar(auth["id"], "enlazar_version", "producto", pid, f"versión publicada: producto {pub['id']}")
    add_toast(sess, f"Enlazado con su versión publicada, «{pub['titulo']}».", "success")
    return cerrar_modal(), HtmxResponseHeaders(trigger=EVENTO)


@rt("/productos/{pid}/version")
def delete(auth, sess, pid: int):
    pre, error = _preprint(pid, auth["id"])
    if error:
        return error
    publicada = pre["publicado_como"]
    productos.desenlazar_version(pid)
    auditar(auth["id"], "desenlazar_version", "producto", pid)
    if publicada:
        aviso_con_deshacer(sess, "El preprint ya no está enlazado con su versión publicada.",
                           hx_post=f"/productos/{pid}/version", hx_vals=f'{{"publicada": "{publicada["id"]}"}}')
    return "", HtmxResponseHeaders(trigger=EVENTO)
