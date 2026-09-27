"""Líneas de investigación institucionales (administración): alta, edición, vigencia y orden.
Todo /admin/* exige ser administrador (Beforeware)."""
from fasthtml.common import A, APIRouter, Div, Li, P, Redirect, Response, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, LabelInput, LabelTextArea, TextPresets, UkIcon

from app.investigacion import lineas
from app.comun.componentes.layout import ID_MODAL, JS_CERRAR, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()
BASE = "/admin/lineas"


def _fecha(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else None


def vigencia_texto(x):
    desde, hasta = _fecha(x["vigente_desde"]), _fecha(x["vigente_hasta"])
    if desde and hasta:
        return f"Del {desde} al {hasta}"
    if hasta:
        return f"Hasta el {hasta}"
    return f"Desde el {desde}" if desde else "Sin fecha de inicio registrada"


def insignia_estado(x):
    e = lineas.estado(x)
    return {"vigente": insignia("Vigente", "verde", icono="circle-check"),
            "proxima": insignia("Aún no rige", "azul", icono="clock"),
            "cerrada": insignia("Ya no rige", "gris", icono="circle-slash")}[e]


def _uso(x):
    partes = [f"{x['n_proyectos']} proyecto(s)", f"{x['n_propuestas']} propuesta(s)",
              f"{x['n_investigadores']} investigador(es)"]
    return " · ".join(partes)


def _boton(icono, etiqueta, **kw):
    return Button(UkIcon(icono, height=14, width=14), cls=(ButtonT.ghost, ButtonT.sm), type="button",
                  aria_label=etiqueta, title=etiqueta, **kw)


def fila(x, primera, ultima):
    cerrada = lineas.estado(x) == "cerrada"
    return Li(
        Div(Div(A(x["nombre"], href=f"{BASE}/{x['id']}", cls="font-medium hover:underline"), insignia_estado(x),
                cls="flex flex-wrap items-center gap-2"),
            P(x["descripcion"], cls="text-sm mt-1") if x["descripcion"] else "",
            P(vigencia_texto(x), " · ", _uso(x), cls=(TextPresets.muted_sm, "mt-1")), cls="flex-1"),
        Div(_boton("arrow-up", "Subir", hx_post=f"{BASE}/{x['id']}/subir", disabled=primera),
            _boton("arrow-down", "Bajar", hx_post=f"{BASE}/{x['id']}/bajar", disabled=ultima),
            _boton("pencil", "Editar", hx_get=f"{BASE}/{x['id']}/editar", hx_target=f"#{ID_MODAL}"),
            _boton("rotate-ccw", "Volver a hacerla vigente", hx_post=f"{BASE}/{x['id']}/reabrir",
                   hx_confirm="¿Quitar la fecha de término? La línea vuelve a poder elegirse.") if cerrada else
            _boton("circle-slash", "Poner fecha de término", hx_get=f"{BASE}/{x['id']}/cerrar",
                   hx_target=f"#{ID_MODAL}"),
            _boton("trash-2", "Eliminar", hx_delete=f"{BASE}/{x['id']}",
                   hx_confirm=f"¿Eliminar la línea «{x['nombre']}»?") if not lineas.en_uso(x["id"]) else
            _boton("trash-2", "En uso: no se puede eliminar (póngale fecha de término)", disabled=True),
            cls="flex shrink-0 items-start"),
        cls="flex flex-wrap sm:flex-nowrap gap-3 py-3")


@rt(BASE)
def get(auth):
    todas = lineas.todas()
    return pagina(
        "Líneas de investigación",
        Div(Div(H2("Líneas de investigación"),
                P("Líneas institucionales a las que se adscriben los proyectos y, de forma voluntaria, los "
                  "investigadores. Las propuestas institucionales deben elegir al menos una vigente.",
                  cls=TextPresets.muted_sm)),
            Button(UkIcon("plus", height=16, width=16), "Nueva línea", cls=ButtonT.primary,
                   hx_get=f"{BASE}/nueva", hx_target=f"#{ID_MODAL}"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Card(Ul(*[fila(x, i == 0, i == len(todas) - 1) for i, x in enumerate(todas)], cls="divide-y divide-border")
             if todas else P("Aún no hay líneas registradas.", cls=TextPresets.muted_sm)),
        Card(H3("Cuando las líneas cambian", cls="text-base font-semibold mb-2"),
             Ul(Li("Para corregir la redacción, edite la línea: el cambio se ve en todos los registros."),
                Li("Si una línea deja de regir, póngale fecha de término: no se podrá elegir en propuestas "
                   "posteriores, pero los proyectos, propuestas y perfiles que ya la usaban la conservan."),
                Li("Si una línea se reformula o se divide, póngale término y cree las nuevas; los investigadores "
                   "verán en su perfil que la anterior ya no rige."),
                Li("Solo se puede eliminar una línea que nadie ha usado."),
                cls="list-disc pl-5 space-y-1 text-sm"),
             cls="mt-6"),
        usuario=auth, seccion="lineas")


# --- Alta y edición -----------------------------------------------------------------------------------

def form_linea(d, errores=(), lid=None):
    def valor(k):
        return d.get(k) or ""
    return modal(
        "Editar línea" if lid else "Nueva línea de investigación",
        Form(mensaje_error(*errores),
             LabelInput("Nombre", id="nombre", value=valor("nombre"), required=True, maxlength=lineas.LARGO_NOMBRE),
             LabelTextArea("Descripción (opcional)", id="descripcion", value=valor("descripcion"), rows=3),
             Div(LabelInput("Vigente desde", id="vigente_desde", type="date", value=valor("vigente_desde")),
                 LabelInput("Vigente hasta", id="vigente_hasta", type="date", value=valor("vigente_hasta")),
                 cls="grid grid-cols-2 gap-4"),
             P("Deje «desde» en blanco si la línea ya regía antes del portal, y «hasta» en blanco mientras siga "
               "vigente. La vigencia la fija la resolución que aprueba las líneas.", cls=TextPresets.muted_sm),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
                 Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             **({"hx_put": f"{BASE}/{lid}"} if lid else {"hx_post": BASE}), hx_target=f"#{ID_MODAL}",
             cls="space-y-4"))


def _datos(nombre, descripcion, vigente_desde, vigente_hasta):
    return dict(nombre=nombre, descripcion=descripcion, vigente_desde=vigente_desde, vigente_hasta=vigente_hasta)


@rt(f"{BASE}/nueva")
def get(auth):
    return form_linea({})


@rt(BASE)
def post(auth, sess, nombre: str = "", descripcion: str = "", vigente_desde: str = "", vigente_hasta: str = ""):
    d, errores = lineas.validar(_datos(nombre, descripcion, vigente_desde, vigente_hasta))
    if errores:
        return form_linea(d, errores)
    lid = lineas.crear(d, auth["id"])
    auditar(auth["id"], "crear_linea", "linea_investigacion", lid, d["nombre"])
    add_toast(sess, "Línea creada.", "success")
    return Redirect(BASE)


def _linea_o_404(lid):
    x = lineas.obtener(lid)
    return x, (None if x else Response("No encontrado", status_code=404))


@rt(f"{BASE}/{{lid}}/editar")
def get(auth, lid: int):
    x, error = _linea_o_404(lid)
    return error or form_linea(x, lid=lid)


@rt(f"{BASE}/{{lid}}")
def put(auth, sess, lid: int, nombre: str = "", descripcion: str = "", vigente_desde: str = "",
        vigente_hasta: str = ""):
    x, error = _linea_o_404(lid)
    if error:
        return error
    d, errores = lineas.validar(_datos(nombre, descripcion, vigente_desde, vigente_hasta), lid)
    if errores:
        return form_linea(d, errores, lid)
    lineas.actualizar(lid, d)
    detalle = d["nombre"] if d["nombre"] == x["nombre"] else f"{x['nombre']} → {d['nombre']}"
    auditar(auth["id"], "editar_linea", "linea_investigacion", lid, detalle)
    add_toast(sess, "Línea guardada.", "success")
    return Redirect(BASE)


# --- Vigencia, orden y eliminación ------------------------------------------------------------------------

def form_cerrar(x, error=None, fecha=""):
    return modal(
        "Poner fecha de término",
        Form(mensaje_error(error) if error else "",
             P(f"«{x['nombre']}» dejará de poder elegirse en propuestas, proyectos y perfiles después de esta "
               "fecha. Quienes ya la usaban la conservan.", cls="text-sm"),
             LabelInput("Vigente hasta", id="fecha", type="date", value=fecha or lineas.hoy(), required=True),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
                 Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/{x['id']}/cerrar", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt(f"{BASE}/{{lid}}/cerrar")
def get(auth, lid: int):
    x, error = _linea_o_404(lid)
    return error or form_cerrar(x)


@rt(f"{BASE}/{{lid}}/cerrar")
def post(auth, sess, lid: int, fecha: str = ""):
    x, error = _linea_o_404(lid)
    if error:
        return error
    if (error := lineas.cerrar(lid, fecha)):
        return form_cerrar(x, error, fecha)
    auditar(auth["id"], "cerrar_linea", "linea_investigacion", lid, f"{x['nombre']} hasta {fecha}")
    add_toast(sess, "Fecha de término guardada.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/{{lid}}/reabrir")
def post(auth, sess, lid: int):
    x, error = _linea_o_404(lid)
    if error:
        return error
    lineas.reabrir(lid)
    auditar(auth["id"], "reabrir_linea", "linea_investigacion", lid, x["nombre"])
    add_toast(sess, "La línea vuelve a estar vigente.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/{{lid}}/subir")
def post(auth, lid: int):
    lineas.mover(lid, -1)
    return Redirect(BASE)


@rt(f"{BASE}/{{lid}}/bajar")
def post(auth, lid: int):
    lineas.mover(lid, 1)
    return Redirect(BASE)


@rt(f"{BASE}/{{lid}}")
def delete(auth, sess, lid: int):
    x, error = _linea_o_404(lid)
    if error:
        return error
    if (error := lineas.eliminar(lid)):
        add_toast(sess, error, "error")
    else:
        auditar(auth["id"], "eliminar_linea", "linea_investigacion", lid, x["nombre"])
        add_toast(sess, "Línea eliminada.", "success")
    return Redirect(BASE)


# --- Ficha: quiénes y qué proyectos la usan ------------------------------------------------------------------

@rt(f"{BASE}/{{lid}}")
def get(auth, lid: int):
    x, error = _linea_o_404(lid)
    if error:
        return pagina("No encontrado", P("La línea no existe."), usuario=auth)
    invs, proys = lineas.investigadores(lid), lineas.proyectos(lid)
    return pagina(
        x["nombre"],
        A(UkIcon("arrow-left", height=14, width=14), "Líneas de investigación", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(H2(x["nombre"]), insignia_estado(x), cls="flex flex-wrap items-center gap-3"),
        P(vigencia_texto(x), cls=(TextPresets.muted_sm, "mb-2")),
        P(x["descripcion"], cls="text-sm mb-6") if x["descripcion"] else "",
        Div(Card(H3(f"Proyectos ({len(proys)})", cls="text-base font-semibold mb-2"),
                 Ul(*[Li(A(p["nombre"], href=f"/proyectos/{p['id']}", cls="hover:underline"),
                         Span(f" · {p['tipo']} · {p['estado']}", cls=TextPresets.muted_sm), cls="py-1 text-sm")
                      for p in proys]) if proys else P("Ninguno.", cls=TextPresets.muted_sm)),
            Card(H3(f"Investigadores adscritos ({len(invs)})", cls="text-base font-semibold mb-2"),
                 Ul(*[Li(A(f"{i['nombres']} {i['apellidos']}", href=f"/investigadores/{i['id']}",
                           cls="hover:underline"), cls="py-1 text-sm") for i in invs])
                 if invs else P("Ninguno.", cls=TextPresets.muted_sm)),
            cls="grid grid-cols-1 md:grid-cols-2 gap-6"),
        usuario=auth, seccion="lineas")
