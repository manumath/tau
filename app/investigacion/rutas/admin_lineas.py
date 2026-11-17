"""Líneas de investigación institucionales: áreas, alta, edición, vigencia, orden y proyectos de cada línea.
Las mantiene la Dirección del Instituto (`gestionar_catalogos`, regla de /admin/lineas en auth.REGLAS_ADMIN)."""
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, FormLabel, LabelInput, LabelTextArea, TextPresets, UkIcon

from app.investigacion import lineas
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
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


def _grupos(todas):
    """[(área o None, líneas)] en el orden del catálogo; las líneas sin área van al final."""
    grupos = [(a, [x for x in todas if x["area_id"] == a["id"]]) for a in lineas.areas()]
    sin_area = [x for x in todas if x["area_id"] is None]
    return grupos + ([(None, sin_area)] if sin_area else [])


def _bloque(a, filas):
    titulo = a["nombre"] if a else "Sin área"
    return Div(H3(titulo, cls="text-sm font-semibold uppercase tracking-wide text-muted-foreground"),
               P("Líneas anteriores al catálogo por áreas: asígneles un área (Editar) o póngales fecha de término si "
                 "ya no rigen.", cls=(TextPresets.muted_sm, "mt-1")) if a is None else "",
               Ul(*[fila(x, i == 0, i == len(filas) - 1) for i, x in enumerate(filas)], cls="divide-y divide-border")
               if filas else P("Sin líneas.", cls=(TextPresets.muted_sm, "py-2")),
               cls="space-y-1")


def _tarjeta_areas(areas):
    return Card(
        Div(H3("Áreas", cls="text-base font-semibold"),
            Button(UkIcon("plus", height=14, width=14), "Nueva área", cls=(ButtonT.default, ButtonT.sm),
                   hx_get=f"{BASE}/areas/nueva", hx_target=f"#{ID_MODAL}"),
            cls="flex flex-wrap items-center justify-between gap-2 mb-2"),
        Ul(*[Li(Div(Div(a["nombre"], cls="font-medium"), Div(f"{a['n_lineas']} línea(s)", cls=TextPresets.muted_sm),
                    cls="flex-1 min-w-0 text-sm"),
                Div(_boton("arrow-up", "Subir", hx_post=f"{BASE}/areas/{a['id']}/subir", disabled=i == 0),
                    _boton("arrow-down", "Bajar", hx_post=f"{BASE}/areas/{a['id']}/bajar", disabled=i == len(areas) - 1),
                    _boton("pencil", "Cambiar el nombre", hx_get=f"{BASE}/areas/{a['id']}/editar", hx_target=f"#{ID_MODAL}"),
                    _boton("trash-2", "Eliminar", hx_delete=f"{BASE}/areas/{a['id']}",
                           hx_confirm=f"¿Eliminar el área «{a['nombre']}»?") if not a["n_lineas"] else
                    _boton("trash-2", "Tiene líneas: no se puede eliminar", disabled=True),
                    cls="flex shrink-0"),
                cls="flex items-center gap-2 py-1") for i, a in enumerate(areas)], cls="divide-y divide-border")
        if areas else P("Aún no hay áreas.", cls=TextPresets.muted_sm))


@rt(BASE)
def get(auth):
    todas = lineas.todas()
    return pagina(
        "Líneas de investigación",
        Div(Div(H2("Líneas de investigación"),
                P("Líneas institucionales, agrupadas por área, a las que se adscriben los proyectos y, de forma "
                  "voluntaria, los investigadores. Las propuestas institucionales deben elegir al menos una vigente.",
                  cls=TextPresets.muted_sm)),
            Button(UkIcon("plus", height=16, width=16), "Nueva línea", cls=ButtonT.primary,
                   hx_get=f"{BASE}/nueva", hx_target=f"#{ID_MODAL}"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Div(Card(Div(*[_bloque(a, filas) for a, filas in _grupos(todas)], cls="space-y-6")
                 if todas else P("Aún no hay líneas registradas.", cls=TextPresets.muted_sm), cls="lg:col-span-2"),
            Div(_tarjeta_areas(lineas.areas()),
                Card(H3("Cuando las líneas cambian", cls="text-base font-semibold mb-2"),
                     Ul(Li("Para corregir la redacción o cambiar el área, edite la línea: el cambio se ve en todos los "
                           "registros."),
                        Li("Si una línea deja de regir, póngale fecha de término: no se podrá elegir en propuestas "
                           "posteriores, pero los proyectos, propuestas y perfiles que ya la usaban la conservan."),
                        Li("Si una línea se reformula o se divide, póngale término y cree las nuevas."),
                        Li("En la ficha de cada línea puede agregar o quitar los proyectos vigentes que la trabajan."),
                        Li("Solo se puede eliminar una línea que nadie ha usado, y un área sin líneas."),
                        cls="list-disc pl-5 space-y-1 text-sm")),
                cls="space-y-6"),
            cls="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start"),
        usuario=auth, seccion="lineas")


# --- Alta y edición -----------------------------------------------------------------------------------

def form_linea(d, errores=(), lid=None):
    def valor(k):
        return d.get(k) or ""
    return modal(
        "Editar línea" if lid else "Nueva línea de investigación",
        Form(mensaje_error(*errores),
             LabelInput("Nombre", id="nombre", value=valor("nombre"), required=True, maxlength=lineas.LARGO_NOMBRE),
             Div(FormLabel("Área", fr="area_id"),
                 Select(Option("Elija el área", value=""),
                        *[Option(a["nombre"], value=str(a["id"]), selected=str(a["id"]) == str(valor("area_id")))
                          for a in lineas.areas()], id="area_id", name="area_id", cls="uk-select"),
                 cls="space-y-1"),
             LabelTextArea("Descripción (opcional)", id="descripcion", value=valor("descripcion"), rows=3),
             Div(LabelInput("Vigente desde", id="vigente_desde", type="date", value=valor("vigente_desde")),
                 LabelInput("Vigente hasta", id="vigente_hasta", type="date", value=valor("vigente_hasta")),
                 cls="grid grid-cols-2 gap-4"),
             P("Deje «desde» en blanco si la línea ya regía antes del sistema, y «hasta» en blanco mientras siga "
               "vigente. La vigencia la fija la resolución que aprueba las líneas.", cls=TextPresets.muted_sm),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             **({"hx_put": f"{BASE}/{lid}"} if lid else {"hx_post": BASE}), hx_target=f"#{ID_MODAL}",
             cls="space-y-4"))


def _datos(nombre, descripcion, vigente_desde, vigente_hasta, area_id):
    return dict(nombre=nombre, area_id=area_id, descripcion=descripcion, vigente_desde=vigente_desde,
                vigente_hasta=vigente_hasta)


@rt(f"{BASE}/nueva")
def get(auth):
    return form_linea({})


@rt(BASE)
def post(auth, sess, nombre: str = "", descripcion: str = "", vigente_desde: str = "", vigente_hasta: str = "",
         area_id: str = ""):
    d, errores = lineas.validar(_datos(nombre, descripcion, vigente_desde, vigente_hasta, area_id))
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
        vigente_hasta: str = "", area_id: str = ""):
    x, error = _linea_o_404(lid)
    if error:
        return error
    d, errores = lineas.validar(_datos(nombre, descripcion, vigente_desde, vigente_hasta, area_id), lid)
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
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
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


# --- Ficha: quiénes y qué proyectos la usan

def _agregar_proyecto(x):
    if not lineas.vigente(x):
        return P("La línea ya no rige: no se le pueden agregar proyectos.", cls=(TextPresets.muted_sm, "mt-3"))
    disponibles = lineas.proyectos_para_agregar(x["id"])
    if not disponibles:
        return P("Todos los proyectos vigentes ya están en esta línea.", cls=(TextPresets.muted_sm, "mt-3"))
    return Form(Select(Option("Agregar un proyecto vigente…", value=""),
                       *[Option(p["nombre"], value=str(p["id"])) for p in disponibles],
                       name="proyecto_id", cls="uk-select", aria_label="Proyecto vigente"),
                Button("Agregar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
                hx_post=f"{BASE}/{x['id']}/proyectos", cls="flex flex-wrap sm:flex-nowrap items-center gap-2 mt-3")


@rt(f"{BASE}/{{lid}}/proyectos")
def post(auth, sess, lid: int, proyecto_id: str = ""):
    x, error = _linea_o_404(lid)
    if error:
        return error
    pid = int(proyecto_id) if proyecto_id.isdigit() else 0
    if (error := lineas.agregar_proyecto(lid, pid)):
        add_toast(sess, error, "error")
    else:
        auditar(auth["id"], "adscribir_proyecto_linea", "linea_investigacion", lid, f"proyecto {pid}")
        add_toast(sess, "Proyecto agregado a la línea.", "success")
    return Redirect(f"{BASE}/{lid}")


@rt(f"{BASE}/{{lid}}/proyectos/{{pid}}/quitar")
def post(auth, sess, lid: int, pid: int):
    x, error = _linea_o_404(lid)
    if error:
        return error
    lineas.quitar_proyecto(lid, pid)
    auditar(auth["id"], "quitar_proyecto_linea", "linea_investigacion", lid, f"proyecto {pid}")
    add_toast(sess, "Proyecto quitado de la línea.", "success")
    return Redirect(f"{BASE}/{lid}")


# --- Áreas -------------------------------------------------------------------------------------------------

def form_area(nombre="", errores=(), aid=None):
    return modal(
        "Cambiar el nombre del área" if aid else "Nueva área",
        Form(mensaje_error(*errores),
             LabelInput("Nombre", id="nombre", value=nombre, required=True, maxlength=lineas.LARGO_AREA),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/areas/{aid}" if aid else f"{BASE}/areas", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt(f"{BASE}/areas/nueva")
def get(auth):
    return form_area()


@rt(f"{BASE}/areas")
def post(auth, sess, nombre: str = ""):
    nombre, errores = lineas.validar_area(nombre)
    if errores:
        return form_area(nombre, errores)
    aid = lineas.crear_area(nombre)
    auditar(auth["id"], "crear_area_investigacion", "area_investigacion", aid, nombre)
    add_toast(sess, "Área creada.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/areas/{{aid}}/editar")
def get(auth, aid: int):
    a = lineas.area(aid)
    return form_area(a["nombre"], aid=aid) if a else Response("No encontrado", status_code=404)


@rt(f"{BASE}/areas/{{aid}}")
def post(auth, sess, aid: int, nombre: str = ""):
    a = lineas.area(aid)
    if not a:
        return Response("No encontrado", status_code=404)
    nombre, errores = lineas.validar_area(nombre, aid)
    if errores:
        return form_area(nombre, errores, aid)
    lineas.renombrar_area(aid, nombre)
    auditar(auth["id"], "editar_area_investigacion", "area_investigacion", aid, f"{a['nombre']} → {nombre}")
    add_toast(sess, "Área guardada.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/areas/{{aid}}")
def delete(auth, sess, aid: int):
    a = lineas.area(aid)
    if not a:
        return Response("No encontrado", status_code=404)
    if (error := lineas.eliminar_area(aid)):
        add_toast(sess, error, "error")
    else:
        auditar(auth["id"], "eliminar_area_investigacion", "area_investigacion", aid, a["nombre"])
        add_toast(sess, "Área eliminada.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/areas/{{aid}}/subir")
def post(auth, aid: int):
    lineas.mover_area(aid, -1)
    return Redirect(BASE)


@rt(f"{BASE}/areas/{{aid}}/bajar")
def post(auth, aid: int):
    lineas.mover_area(aid, 1)
    return Redirect(BASE)


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
                 Ul(*[Li(Div(A(p["nombre"], href=f"/proyectos/{p['id']}", cls="hover:underline"),
                             Span(f" · {p['tipo']} · {p['estado']}", cls=TextPresets.muted_sm), cls="flex-1"),
                         _boton("x", f"Quitar «{p['nombre']}» de la línea", hx_post=f"{BASE}/{lid}/proyectos/{p['id']}/quitar",
                                hx_confirm=f"¿Quitar «{p['nombre']}» de esta línea?"),
                         cls="flex items-center gap-2 py-1 text-sm") for p in proys], cls="divide-y divide-border")
                 if proys else P("Ninguno.", cls=TextPresets.muted_sm),
                 _agregar_proyecto(x)),
            Card(H3(f"Investigadores adscritos ({len(invs)})", cls="text-base font-semibold mb-2"),
                 Ul(*[Li(A(f"{i['nombres']} {i['apellidos']}", href=f"/investigadores/{i['id']}",
                           cls="hover:underline"), cls="py-1 text-sm") for i in invs])
                 if invs else P("Ninguno.", cls=TextPresets.muted_sm)),
            cls="grid grid-cols-1 md:grid-cols-2 gap-6"),
        usuario=auth, seccion="lineas")
