"""Pantallas de comunicados y eventos (PLAN §58, servicio 1): quien publica los arma y elige a los convocados; quien los
recibe los lee y confirma su asistencia. Los estudiantes los ven en /estudiante/comunicados (su cuenta solo llega ahí)."""
from datetime import datetime

import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, P, Redirect, Span, Table, Tbody, Td, Th, Thead, Tr, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, ButtonT, LabelInput, TextPresets, UkIcon

from app.comun import usuarios
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar
from app.servicios import comunicados as com
from app.servicios.rutas.comun import (area, boton_post, enviar, fecha, formulario, no_autorizado, no_encontrado,
                                       seleccion, tarjeta)

rt = APIRouter()
BASE = "/servicios/comunicados"
EST = "/estudiante/comunicados"
TONO = {"borrador": "gris", "publicado": "verde", "cancelado": "rojo"}


def _cuando(c):
    return Span(UkIcon("calendar", height=14, width=14), com.fecha_hora(c["inicio"]) + (f" · {c['lugar']}" if c["lugar"] else ""),
                cls="inline-flex items-center gap-1 text-sm") if c["inicio"] else ""


def lista_recibidos(uid, base):
    filas = com.recibidos(uid)
    pendientes = {c["id"] for c in com.por_confirmar(uid)}
    items = []
    for c in filas:
        marca = insignia("Confirme su asistencia", "ambar") if c["id"] in pendientes else \
            insignia(com.RESPUESTAS[c["respuesta"]], "verde" if c["respuesta"] == "asistire" else "gris") if c["respuesta"] else \
            insignia("Cancelado", "rojo") if c["estado"] == "cancelado" else ""
        items.append(Li(A(Div(Span(com.TIPOS[c["tipo"]], cls="text-xs font-semibold uppercase text-primary"),
                              Div(c["titulo"], cls="font-medium"),
                              Div(com.autor(c), " · ", fecha(c["publicado_en"]), cls=TextPresets.muted_sm), _cuando(c),
                              cls="space-y-0.5 min-w-0"), marca, href=f"{base}/{c['id']}",
                            cls="flex items-start justify-between gap-3 py-3 px-2 rounded hover:bg-muted/50")))
    return Ul(*items, cls="divide-y divide-border") if items else P("Aún no recibió comunicados.", cls=TextPresets.muted_sm)


def detalle_recibido(c, base):
    """Lo que ve quien lo recibe, con los botones Asistiré / No podré si corresponde."""
    pide = c["estado"] == "publicado" and c["confirmar"] and (c["inicio"] or "") >= datetime.now().strftime("%Y-%m-%dT%H:%M")
    respuesta = Div(
        P("¿Asistirá?" if not c["respuesta"] else f"Su respuesta: {com.RESPUESTAS[c['respuesta']]}. Puede cambiarla.",
          cls="text-sm font-medium"),
        Div(*[formulario(f"{base}/{c['id']}/respuesta", fh.Input(type="hidden", name="respuesta", value=k),
                         enviar(t, cls=ButtonT.primary if k == "asistire" else ButtonT.default), cls="")
              for k, t in com.RESPUESTAS.items()], cls="flex gap-2"),
        cls="space-y-2 rounded-md border border-border p-4") if pide else ""
    return Div(
        Span(com.TIPOS[c["tipo"]], cls="text-xs font-semibold uppercase text-primary"),
        H2(c["titulo"]),
        Div(com.autor(c), " · publicado el ", fecha(c["publicado_en"]), cls=TextPresets.muted_sm),
        insignia("Cancelado", "rojo") if c["estado"] == "cancelado" else "",
        _cuando(c),
        Div(*[P(x) for x in (c["texto"] or "").split("\n\n") if x.strip()], cls="space-y-3 text-sm max-w-3xl whitespace-pre-line"),
        A(UkIcon("arrow-right", height=14, width=14), "Ir a la convocatoria", href=c["enlace"],
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline") if c["enlace"] else "",
        respuesta, cls="space-y-3")


# --- Personal: lista ---------------------------------------------------------------------------------------------------

@rt(BASE)
def get(auth):
    mios = com.mios(auth) if com.puede_publicar(auth) else []
    return pagina(
        "Comunicados y eventos",
        Div(H2("Comunicados y eventos"),
            A(UkIcon("plus", height=14, width=14), "Nuevo", href=f"{BASE}/nuevo", cls="uk-btn uk-btn-primary uk-btn-sm gap-1")
            if com.puede_publicar(auth) else "", cls="flex flex-wrap items-end justify-between gap-4 mb-4"),
        Div(tarjeta("Recibidos", lista_recibidos(auth["id"], BASE)),
            tarjeta("Publicados por usted o su cargo", Table(
                Thead(Tr(Th("Título"), Th("Estado", cls="w-28"), Th("Convocados", cls="w-28 text-right"))),
                Tbody(*[Tr(Td(A(c["titulo"], href=f"{BASE}/{c['id']}", cls="font-medium hover:underline"),
                              Div(com.TIPOS[c["tipo"]], " · ", com.autor(c), cls=TextPresets.muted_sm)),
                           Td(insignia(com.ESTADOS[c["estado"]], TONO[c["estado"]])),
                           Td("todos" if c["para_todos"] and c["estado"] == "borrador" else str(c["n"]),
                              Div(f"{c['asistiran']} asistirán", cls=TextPresets.muted_sm) if c["confirmar"] else "",
                              cls="text-right")) for c in mios]),
                cls="uk-table uk-table-divider uk-table-small text-sm") if mios else
                P("Aún no publicó nada.", cls=TextPresets.muted_sm)) if com.puede_publicar(auth) else "",
            cls="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"),
        usuario=auth)


# --- Personal: armar ------------------------------------------------------------------------------------------------------

def _form(auth, c=None):
    c = c or {}
    opciones = com.como_puede_publicar(auth)
    como = f"proyecto:{c['proyecto_id']}" if c.get("publica_como") == "proyecto" else c.get("publica_como")
    url = f"{BASE}/{c['id']}" if c.get("id") else BASE
    return formulario(
        url,
        Div(seleccion("Tipo", "tipo", list(com.TIPOS.items()), c.get("tipo") or "comunicado"),
            seleccion("Publica como", "publica_como", opciones, como or (opciones[0][0] if opciones else None)),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
        LabelInput("Título", id="titulo", value=c.get("titulo") or "", required=True, maxlength="200",
                   placeholder="Convocatoria a auxiliaturas I-2027, Seminario de Análisis, reunión de tesistas…"),
        area("Texto", "texto", c.get("texto"), 6, "Separe los párrafos con una línea en blanco."),
        Div(P("Si es un evento", cls="text-sm font-semibold"),
            Div(LabelInput("Fecha y hora", id="inicio", type="datetime-local", value=c.get("inicio") or ""),
                LabelInput("Lugar o enlace de la reunión", id="lugar", value=c.get("lugar") or "", maxlength="200"),
                cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
            fh.Label(fh.Input(type="checkbox", name="confirmar", value="1", checked=bool(c.get("confirmar")), cls="uk-checkbox"),
                     " Pedir que confirmen su asistencia", cls="flex items-center gap-2 text-sm"),
            cls="space-y-3 rounded-md border border-border p-4"),
        LabelInput("Enlace dentro del sistema (opcional)", id="enlace", value=c.get("enlace") or "",
                   placeholder="/estudiante/auxiliaturas"),
        Div(A("Cancelar", href=f"{BASE}/{c['id']}" if c.get("id") else BASE, cls="uk-btn uk-btn-ghost"),
            enviar("Guardar y elegir a quién llega" if not c.get("id") else "Guardar"), cls="flex justify-end gap-2"))


@rt(f"{BASE}/nuevo")
def get(auth):
    if not com.puede_publicar(auth):
        return no_autorizado()
    return pagina("Nuevo comunicado", A("← Comunicados", href=BASE, cls="text-sm text-primary"), H2("Nuevo comunicado o evento"),
                  Div(_form(auth), cls="max-w-3xl mt-4"), usuario=auth)


async def _datos(req):
    f = await req.form()
    return {k: f.get(k, "") for k in ("tipo", "titulo", "texto", "publica_como", "inicio", "lugar", "confirmar", "enlace")}


@rt(BASE)
async def post(auth, sess, req):
    opciones = com.como_puede_publicar(auth)
    if not opciones:
        return no_autorizado()
    x, errores = com.validar(await _datos(req), opciones)
    if errores:
        for e in errores:
            add_toast(sess, e, "error")
        return Redirect(f"{BASE}/nuevo")
    cid = com.crear(x, auth["id"])
    auditar(auth["id"], "crear_comunicado", "comunicado", cid, x["titulo"])
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}")
async def post(auth, sess, req, cid: int):
    c = com.obtener(cid)
    if not c or c["estado"] != "borrador":
        return no_encontrado()
    if not com.puede_editar(auth, c):
        return no_autorizado()
    x, errores = com.validar(await _datos(req), com.como_puede_publicar(auth))
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        com.editar(cid, x)
        add_toast(sess, "Guardado.", "success")
    return Redirect(f"{BASE}/{cid}" + ("/editar" if errores else ""))


@rt(f"{BASE}/{{cid}}/editar")
def get(auth, cid: int):
    c = com.obtener(cid)
    if not c or c["estado"] != "borrador":
        return no_encontrado()
    if not com.puede_editar(auth, c):
        return no_autorizado()
    return pagina("Editar comunicado", A("← Volver", href=f"{BASE}/{cid}", cls="text-sm text-primary"), H2("Editar"),
                  Div(_form(auth, c), cls="max-w-3xl mt-4"), usuario=auth)


def _convocados(auth, c):
    url = f"{BASE}/{c['id']}"
    ds = com.convocados(c["id"])
    borrador = c["estado"] == "borrador"
    chips = [Li(Span(f"{d['nombres']} {d['apellidos']}", cls="text-sm"),
                Span(" · estudiante" if d["estudiante"] else "", cls=TextPresets.muted_sm),
                boton_post("", f"{url}/convocados/{d['usuario_id']}/quitar", "x", cls=(ButtonT.ghost, ButtonT.xs),
                           aria_label=f"Quitar a {d['nombres']} {d['apellidos']}") if borrador else "",
                cls="inline-flex items-center gap-1 rounded-full border border-border pl-3 pr-1 py-0.5")
             for d in ds]
    if not borrador:
        return tarjeta(f"Llegó a {len(ds)} personas", Ul(*chips, cls="flex flex-wrap gap-2") if chips else "")
    para_todos = Div(
        formulario(f"{url}/para-todos", fh.Input(type="hidden", name="valor", value="0" if c["para_todos"] else "1"),
                   enviar("Elegir convocados" if c["para_todos"] else "Enviar a todas las cuentas", cls=(ButtonT.default, ButtonT.sm)),
                   cls=""),
        P("Para todos: llega a todas las cuentas activas (personal y estudiantes)." if not c["para_todos"] else
          "Está marcado para todos.", cls=TextPresets.muted_sm), cls="flex flex-wrap items-center gap-3")
    if c["para_todos"]:
        return tarjeta(f"Llegará a {com.alcance(c)} personas", para_todos)
    return tarjeta(
        f"Convocados · llegará a {len(ds)} personas",
        para_todos,
        Div(formulario(f"{url}/convocados/grupo",
                       Div(seleccion("Agregar un grupo", "grupo", com.grupos(auth, c), vacio="— Elija un grupo —"),
                           cls="flex-1 min-w-0"),
                       enviar("Agregar", cls=(ButtonT.default, ButtonT.sm)), cls="flex items-end gap-2"),
            Div(LabelInput("Agregar una persona", id="q", placeholder="Nombre o correo", hx_get=f"{url}/buscar",
                           hx_trigger="input changed delay:300ms, search", hx_target="#resultados", autocomplete="off",
                           type="search"),
                Div(id="resultados"), cls="space-y-1"),
            cls="grid grid-cols-1 md:grid-cols-2 gap-4 my-4"),
        Ul(*chips, cls="flex flex-wrap gap-2") if chips else P("Aún no hay convocados.", cls=TextPresets.muted_sm),
        boton_post("Quitar a todos", f"{url}/convocados/vaciar", "trash-2", cls=(ButtonT.ghost, ButtonT.sm),
                   confirmar="¿Quitar a todos los convocados?") if chips else "")


def _asistencia(c):
    url = f"{BASE}/{c['id']}"
    ds = com.convocados(c["id"])
    k = com.cifras(c["id"])
    resumen = Div(*[Div(Div(str(v), cls="text-2xl font-semibold"), Div(t, cls=TextPresets.muted_sm))
                    for v, t in ((k["asistire"], "asistirán"), (k["no_podre"], "no podrán"), (k["sin_respuesta"], "sin respuesta"))],
                  cls="grid grid-cols-3 gap-3 mb-3") if c["confirmar"] else ""
    tabla = Table(Thead(Tr(Th("Persona"), Th("Respuesta", cls="w-28"), Th("Asistió", cls="w-20 text-center")
                           if com.puede_registrar_asistencia(c) or k["registrada"] else "")),
                  Tbody(*[Tr(Td(f"{d['nombres']} {d['apellidos']}", Div(d["email"], cls=TextPresets.muted_sm)),
                             Td(com.RESPUESTAS.get(d["respuesta"], "—")),
                             Td(fh.Input(type="checkbox", name="presentes", value=str(d["usuario_id"]), cls="uk-checkbox",
                                         checked=d["asistio"] == 1, aria_label=f"Asistió {d['nombres']} {d['apellidos']}"),
                                cls="text-center") if com.puede_registrar_asistencia(c) else
                             Td("sí" if d["asistio"] == 1 else "no" if d["asistio"] == 0 else "", cls="text-center")
                             if k["registrada"] else "") for d in ds]),
                  cls="uk-table uk-table-divider uk-table-small text-sm")
    if com.puede_registrar_asistencia(c):
        cuerpo = formulario(f"{url}/asistencia", tabla, Div(enviar("Guardar asistencia"), cls="flex justify-end"))
    else:
        cuerpo = tabla
    nota = P("La asistencia se registra después de que empieza el evento." if c["tipo"] == "evento" and not c["para_todos"]
             and not com.puede_registrar_asistencia(c) else "", cls=TextPresets.muted_sm)
    return tarjeta(f"Respuestas · {k['asistieron']} asistieron" if k["registrada"] else "Respuestas", resumen, nota, cuerpo)


@rt(f"{BASE}/{{cid}}")
def get(auth, cid: int):
    c = com.obtener(cid)
    if not c:
        return no_encontrado()
    if not com.puede_editar(auth, c):
        r = com.recibido(auth["id"], cid)
        if not r:
            return no_autorizado()
        r["_uid"] = auth["id"]
        return pagina(c["titulo"], A("← Comunicados", href=BASE, cls="text-sm text-primary"),
                      Div(detalle_recibido(r, BASE), cls="mt-4"), usuario=auth)
    url = f"{BASE}/{cid}"
    borrador = c["estado"] == "borrador"
    acciones = Div(
        A(UkIcon("pencil", height=14, width=14), "Editar", href=f"{url}/editar", cls="uk-btn uk-btn-default uk-btn-sm gap-1")
        if borrador else "",
        boton_post("Publicar y avisar", f"{url}/publicar", "send", cls=(ButtonT.primary, ButtonT.sm),
                   confirmar=f"Se avisará a {com.alcance(c)} personas. ¿Publicar?") if borrador else "",
        boton_post("Eliminar borrador", f"{url}/eliminar", "trash-2", cls=(ButtonT.ghost, ButtonT.sm),
                   confirmar="¿Eliminar el borrador?") if borrador else "",
        boton_post("Cancelar y avisar", f"{url}/cancelar", "ban", cls=(ButtonT.ghost, ButtonT.sm),
                   confirmar="Se avisará a los convocados que se canceló. ¿Seguir?") if c["estado"] == "publicado" else "",
        cls="flex flex-wrap gap-2")
    vista = dict(c, respuesta=None, _uid=0)
    vista["confirmar"] = 0
    return pagina(
        c["titulo"],
        A("← Comunicados", href=BASE, cls="text-sm text-primary"),
        Div(insignia(com.ESTADOS[c["estado"]], TONO[c["estado"]]), acciones, cls="flex flex-wrap items-center justify-between gap-3 my-4"),
        Div(Div(tarjeta("Así lo verán", detalle_recibido(vista, BASE),
                        P("Pedirá confirmar asistencia." if c["confirmar"] else "", cls=TextPresets.muted_sm)),
                cls="space-y-6"),
            Div(_convocados(auth, c), _asistencia(c) if not borrador else "", cls="space-y-6"),
            cls="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"),
        usuario=auth)


def _editable(auth, cid):
    c = com.obtener(cid)
    if not c or c["estado"] != "borrador" or not com.puede_editar(auth, c):
        return None
    return c


@rt(f"{BASE}/{{cid}}/buscar")
def get(auth, cid: int, q: str = ""):
    c = _editable(auth, cid)
    if not c:
        return no_autorizado()
    personas = com.buscar_personas(q)
    if not personas:
        return P("Sin resultados." if len(q.strip()) >= 2 else "", cls=TextPresets.muted_sm)
    return Ul(*[Li(Span(f"{p['nombres']} {p['apellidos']}", cls="text-sm"),
                   Span(f" · {'estudiante' if p['estudiante'] else p['email']}", cls=TextPresets.muted_sm),
                   boton_post("Agregar", f"{BASE}/{cid}/convocados/{p['id']}", "plus", cls=(ButtonT.ghost, ButtonT.xs)),
                   cls="flex items-center justify-between gap-2 py-1") for p in personas],
              cls="divide-y divide-border rounded-md border border-border px-2")


@rt(f"{BASE}/{{cid}}/convocados/grupo")
def post(auth, sess, cid: int, grupo: str = ""):
    c = _editable(auth, cid)
    if not c:
        return no_autorizado()
    if grupo not in dict(com.grupos(auth, c)):
        add_toast(sess, "Elija un grupo.", "error")
    else:
        n = com.agregar_convocados(cid, com.miembros_de(grupo), excluir=auth["id"])
        add_toast(sess, f"Se agregaron {n} personas.", "success")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/convocados/vaciar")
def post(auth, cid: int):
    if not _editable(auth, cid):
        return no_autorizado()
    com.vaciar_convocados(cid)
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/convocados/{{uid}}")
def post(auth, cid: int, uid: int):
    c = _editable(auth, cid)
    if not c:
        return no_autorizado()
    # El responsable de un proyecto convoca personas sueltas además de su proyecto; todas deben tener cuenta activa.
    u = usuarios.por_id(uid)
    if u and u["activo"] and uid != auth["id"]:
        com.agregar_convocados(cid, [uid])
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/convocados/{{uid}}/quitar")
def post(auth, cid: int, uid: int):
    if not _editable(auth, cid):
        return no_autorizado()
    com.quitar_convocado(cid, uid)
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/para-todos")
def post(auth, cid: int, valor: str = "0"):
    c = _editable(auth, cid)
    if not c:
        return no_autorizado()
    if c["publica_como"] == "proyecto":
        return no_autorizado()   # el responsable de un proyecto convoca a su gente, no a todos
    com.fijar_para_todos(cid, valor == "1")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/publicar")
def post(auth, sess, cid: int):
    c = _editable(auth, cid)
    if not c:
        return no_autorizado()
    errores = com.publicar(cid)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "publicar_comunicado", "comunicado", cid, c["titulo"])
        add_toast(sess, "Publicado: se avisó a los convocados.", "success")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/eliminar")
def post(auth, cid: int):
    c = _editable(auth, cid)
    if not c:
        return no_autorizado()
    com.eliminar(cid)
    return Redirect(BASE)


@rt(f"{BASE}/{{cid}}/cancelar")
def post(auth, sess, cid: int):
    c = com.obtener(cid)
    if not c or not com.puede_editar(auth, c):
        return no_autorizado()
    errores = com.cancelar(cid)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "cancelar_comunicado", "comunicado", cid, c["titulo"])
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/asistencia")
async def post(auth, sess, req, cid: int):
    c = com.obtener(cid)
    if not c or not com.puede_editar(auth, c):
        return no_autorizado()
    if not com.puede_registrar_asistencia(c):
        add_toast(sess, "La asistencia se registra después de que empieza un evento que no es para todos.", "error")
        return Redirect(f"{BASE}/{cid}")
    f = await req.form()
    com.registrar_asistencia(cid, {int(x) for x in f.getlist("presentes") if str(x).isdigit()})
    auditar(auth["id"], "registrar_asistencia", "comunicado", cid)
    add_toast(sess, "Asistencia guardada.", "success")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/respuesta")
def post(auth, sess, cid: int, respuesta: str = ""):
    for e in com.responder(auth["id"], cid, respuesta):
        add_toast(sess, e, "error")
    return Redirect(f"{BASE}/{cid}")


# --- Estudiantes -----------------------------------------------------------------------------------------------------

def _estudiante(auth):
    from app.estudiantil.rutas.estudiante import _requiere
    return _requiere(auth)


@rt(EST)
def get(auth):
    externo, error = _estudiante(auth)
    if error:
        return error
    return pagina("Comunicados", H2("Comunicados y eventos"),
                  P("Convocatorias, avisos y eventos de la Dirección de Carrera, del Instituto, de la Coordinación académica "
                    "y de los proyectos en que participa.", cls=(TextPresets.muted_sm, "mb-4")),
                  tarjeta("Recibidos", lista_recibidos(auth["id"], EST)), usuario=auth)


@rt(f"{EST}/{{cid}}")
def get(auth, cid: int):
    externo, error = _estudiante(auth)
    if error:
        return error
    c = com.recibido(auth["id"], cid)
    if not c:
        return no_encontrado()
    c["_uid"] = auth["id"]
    return pagina(c["titulo"], A("← Comunicados", href=EST, cls="text-sm text-primary"),
                  Div(detalle_recibido(c, EST), cls="mt-4"), usuario=auth)


@rt(f"{EST}/{{cid}}/respuesta")
def post(auth, sess, cid: int, respuesta: str = ""):
    externo, error = _estudiante(auth)
    if error:
        return error
    errores = com.responder(auth["id"], cid, respuesta)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        add_toast(sess, "Gracias: se registró su respuesta.", "success")
    return Redirect(f"{EST}/{cid}")


def pendientes_estudiante(uid: int) -> list:
    """Eventos por confirmar (para «Le toca a usted» en el inicio del estudiante)."""
    return com.por_confirmar(uid)

