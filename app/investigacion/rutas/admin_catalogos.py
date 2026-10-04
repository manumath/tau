"""Catálogos (Dirección del Instituto, PLAN.md §47): tipos de actividad, tipos de producto e índices. Los del
sistema se reordenan y se activan o desactivan (en los índices, además, su política de indexado y
arbitrado); los agregados aquí se renombran y, si nadie los usó, se eliminan. Todo /admin/* pasa por
REGLAS_ADMIN (permiso «gestionar_catalogos»)."""
from fasthtml.common import APIRouter, Div, H3, Li, P, Redirect, Response, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, Form, LabelCheckboxX, LabelInput, TextPresets, UkIcon

from app.investigacion import catalogos
from app.investigacion.catalogos import CATALOGOS, POLITICA
from app.comun.componentes.avisos_emergentes import aviso_con_deshacer
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()
BASE = "/admin/catalogos"
AYUDA = {
    "actividades": "Se ofrecen al registrar una actividad. Un tipo nuevo cuenta en la memoria y el CV, pero no en "
                   "las categorías del anexo de I+D+i ni de la Guía de Antecedentes.",
    "productos": "Se ofrecen al registrar un producto. Un tipo nuevo que pueda ser indexado o arbitrado cuenta en la "
                 "memoria según su nivel de revisión; no entra en las categorías del anexo ni de la Guía.",
    "indices": "Bases en que figuran las revistas. Si un índice cuenta como «indexado», un producto que figura en él "
               "es indexado; si cuenta como «arbitrado», sus revistas se consideran arbitradas.",
}


def _boton(icono, etiqueta, **kw):
    return Button(UkIcon(icono, height=14, width=14), cls=(ButtonT.ghost, ButtonT.sm), type="button",
                  aria_label=etiqueta, title=etiqueta, **kw)


def _insignias(cat, x):
    res = [insignia("Del sistema", "gris", titulo="Lo reconocen el anexo, la Guía, el CV o las importaciones: "
                                                 "su nombre no cambia") if x["del_sistema"] else
           insignia("Agregado", "azul")]
    if not x["activo"]:
        res.append(insignia("Inactivo", "ambar", titulo="No se ofrece en los formularios; lo registrado lo conserva"))
    for col, texto in CATALOGOS[cat]["opciones"].items():
        if x[col]:
            res.append(insignia(texto.split(" (")[0], "verde"))
    return res


def fila(cat, x, primera, ultima):
    url = f"{BASE}/{cat}/{x['id']}"
    editable = not x["del_sistema"] or (cat == "indices")
    return Li(
        Div(Div(Span(x["nombre"], cls="font-medium"), *_insignias(cat, x), cls="flex flex-wrap items-center gap-2"),
            P(f"Usado en {x['uso']} registro(s)" if x["uso"] else "Sin uso", cls=(TextPresets.muted_sm, "mt-1")),
            cls="flex-1 min-w-0"),
        Div(_boton("arrow-up", "Subir", hx_post=f"{url}/subir", disabled=primera),
            _boton("arrow-down", "Bajar", hx_post=f"{url}/bajar", disabled=ultima),
            _boton("pencil", "Editar", hx_get=f"{url}/editar", hx_target=f"#{ID_MODAL}") if editable else "",
            _boton("eye-off", "Desactivar (deja de ofrecerse)", hx_post=f"{url}/activo", hx_vals='{"activo": "0"}')
            if x["activo"] else _boton("eye", "Activar", hx_post=f"{url}/activo", hx_vals='{"activo": "1"}'),
            _boton("trash-2", "Eliminar", hx_delete=url, hx_confirm=f"¿Eliminar «{x['nombre']}»?")
            if not x["del_sistema"] and not x["uso"] else "",
            cls="flex shrink-0 items-start"),
        cls="flex flex-wrap sm:flex-nowrap gap-3 py-3")


def seccion(cat):
    c, filas = CATALOGOS[cat], catalogos.listar(cat)
    return Card(
        Div(Div(H3(c["titulo"], cls="text-base font-semibold"), P(AYUDA[cat], cls=TextPresets.muted_sm)),
            Button(UkIcon("plus", height=14, width=14), f"Nuevo {c['singular']}", cls=(ButtonT.default, ButtonT.sm),
                   hx_get=f"{BASE}/{cat}/nuevo", hx_target=f"#{ID_MODAL}"),
            cls="flex flex-wrap items-start justify-between gap-3 mb-2"),
        Ul(*[fila(cat, x, i == 0, i == len(filas) - 1) for i, x in enumerate(filas)], cls="divide-y divide-border"),
        id=f"catalogo-{cat}")


@rt(BASE)
def get(auth):
    return pagina(
        "Catálogos",
        Div(H2("Catálogos"),
            P("Tipos de actividad, tipos de producto e índices. Los del sistema se pueden reordenar y desactivar (los "
              "reconocen por su nombre el anexo, la Guía de Antecedentes, el CV y las importaciones); los agregados "
              "aquí, además, renombrar y, si nadie los usó, eliminar.", cls=TextPresets.muted_sm),
            cls="mb-6"),
        Div(*[seccion(cat) for cat in CATALOGOS], cls="space-y-6"),
        usuario=auth, seccion="catalogos")


# --- Alta y edición -------------------------------------------------------------------------------------

def form_catalogo(cat, d, errores=(), xid=None, del_sistema=False):
    c = CATALOGOS[cat]
    politica = cat == "indices" and xid
    return modal(
        f"Editar {c['singular']}" if xid else f"Nuevo {c['singular']}",
        Form(mensaje_error(*errores),
             P(Span(d["nombre"], cls="font-medium"), " · del sistema: su nombre no cambia.", cls="text-sm")
             if del_sistema else
             LabelInput("Nombre", id="nombre", value=d.get("nombre") or "", required=True,
                        maxlength=catalogos.LARGO_NOMBRE),
             *[LabelCheckboxX(texto, id=col, checked=bool(d.get(col))) for col, texto in c["opciones"].items()],
             Div(UkIcon("triangle-alert", height=14, width=14, cls="shrink-0 mt-0.5"),
                 Span("Cambiar si cuenta como indexado o arbitrado cambia la clasificación de lo ya registrado: los "
                      "artículos de revistas verificadas que figuran en este índice se reclasifican (y con ellos la "
                      "memoria, el anexo y los CV); los de revistas sin verificar conservan lo que declararon sus "
                      "autores. Queda en la auditoría."),
                 cls="flex gap-1.5 text-sm text-amber-700 dark:text-amber-400") if politica else "",
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             **({"hx_put": f"{BASE}/{cat}/{xid}"} if xid else {"hx_post": f"{BASE}/{cat}"}),
             hx_target=f"#{ID_MODAL}", cls="space-y-4"))


def _catalogo_o_404(cat, xid=None):
    if cat not in CATALOGOS:
        return None, Response("No encontrado", status_code=404)
    if xid is None:
        return None, None
    x = catalogos.obtener(cat, xid)
    return x, (None if x else Response("No encontrado", status_code=404))


def _opciones(req_form, cat):
    return {k: req_form.get(k) for k in ("nombre", *CATALOGOS[cat]["opciones"])}


@rt(f"{BASE}/{{cat}}/nuevo")
def get(auth, cat: str):
    _, error = _catalogo_o_404(cat)
    return error or form_catalogo(cat, {"admite_revision": 1, "cuenta_como_indexado": 1})


@rt(f"{BASE}/{{cat}}")
async def post(auth, sess, req, cat: str):
    _, error = _catalogo_o_404(cat)
    if error:
        return error
    d, errores = catalogos.validar(cat, _opciones(await req.form(), cat))
    if errores:
        return form_catalogo(cat, d, errores)
    xid = catalogos.crear(cat, d)
    auditar(auth["id"], "crear_catalogo", CATALOGOS[cat]["tabla"], xid, d["nombre"])
    add_toast(sess, f"«{d['nombre']}» agregado.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/{{cat}}/{{xid}}/editar")
def get(auth, cat: str, xid: int):
    x, error = _catalogo_o_404(cat, xid)
    if error:
        return error
    if x["del_sistema"] and cat != "indices":
        return Response("Un tipo del sistema solo se reordena o se desactiva.", status_code=403)
    return form_catalogo(cat, x, xid=xid, del_sistema=bool(x["del_sistema"]))


@rt(f"{BASE}/{{cat}}/{{xid}}")
async def put(auth, sess, req, cat: str, xid: int):
    x, error = _catalogo_o_404(cat, xid)
    if error:
        return error
    if x["del_sistema"] and cat != "indices":
        return Response("Un tipo del sistema solo se reordena o se desactiva.", status_code=403)
    d, errores = catalogos.validar(cat, _opciones(await req.form(), cat), xid)
    if errores:
        return form_catalogo(cat, {**x, **d}, errores, xid, bool(x["del_sistema"]))
    catalogos.actualizar(cat, xid, d)
    cambios = [f"{x['nombre']} → {d['nombre']}"] if d["nombre"] != x["nombre"] else []
    cambios += [f"{col}: {x[col]} → {d[col]}" for col in CATALOGOS[cat]["opciones"] if d[col] != x[col]]
    politica = any(c.split(":")[0] in POLITICA for c in cambios)
    n = catalogos.reclasificar_indice(xid) if politica else 0
    auditar(auth["id"], "politica_indice" if politica else "editar_catalogo", CATALOGOS[cat]["tabla"], xid,
            "; ".join(cambios + ([f"{n} artículo(s) reclasificado(s)"] if politica else [])) or d["nombre"])
    add_toast(sess, f"Cambios guardados: se reclasificaron {n} artículo(s)." if politica else "Cambios guardados.",
              "success")
    return Redirect(BASE)


# --- Orden, activación y eliminación ---------------------------------------------------------------------

def _mover(cat, xid, delta):
    _, error = _catalogo_o_404(cat, xid)
    if error:
        return error
    catalogos.mover(cat, xid, delta)
    return Redirect(BASE)


@rt(f"{BASE}/{{cat}}/{{xid}}/subir")
def post(auth, cat: str, xid: int):
    return _mover(cat, xid, -1)


@rt(f"{BASE}/{{cat}}/{{xid}}/bajar")
def post(auth, cat: str, xid: int):
    return _mover(cat, xid, 1)


@rt(f"{BASE}/{{cat}}/{{xid}}/activo")
def post(auth, sess, cat: str, xid: int, activo: str = ""):
    """Activa (activo=1) o desactiva (activo=0). Desactivar no pide confirmación: el aviso ofrece «Deshacer»."""
    x, error = _catalogo_o_404(cat, xid)
    if error:
        return error
    nuevo = activo == "1" if activo in ("0", "1") else not x["activo"]
    if nuevo == bool(x["activo"]):
        return Redirect(BASE)
    catalogos.activar(cat, xid, nuevo)
    auditar(auth["id"], "activar_catalogo" if nuevo else "desactivar_catalogo", CATALOGOS[cat]["tabla"], xid,
            x["nombre"])
    if nuevo:
        add_toast(sess, f"«{x['nombre']}» activado.", "success")
    else:
        aviso_con_deshacer(sess, f"«{x['nombre']}» desactivado: ya no se ofrece en los formularios.",
                           hx_post=f"{BASE}/{cat}/{xid}/activo", hx_vals='{"activo": "1"}')
    return Redirect(BASE)


@rt(f"{BASE}/{{cat}}/{{xid}}")
def delete(auth, sess, cat: str, xid: int):
    x, error = _catalogo_o_404(cat, xid)
    if error:
        return error
    if (problema := catalogos.eliminar(cat, xid)):
        add_toast(sess, problema, "error")
    else:
        auditar(auth["id"], "eliminar_catalogo", CATALOGOS[cat]["tabla"], xid, x["nombre"])
        add_toast(sess, f"«{x['nombre']}» eliminado.", "success")
    return Redirect(BASE)
