"""Oportunidades (PLAN §67, etapa 4): quien publica las arma, las publica y decide sobre las postulaciones; el estudiante (o el
egresado, si es empleo) las ve y postula desde /estudiante/oportunidades."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Li, Option, P, Redirect, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.comun import formato, permisos
from app.comun.componentes.layout import campo, mensaje_error, pagina
from app.comun.componentes.registros import insignia
from app.egresados import empleadores
from app.estudiantil.rutas.estudiante import _requiere
from app.servicios import oportunidades as op
from app.servicios.rutas.comun import no_autorizado, no_encontrado

rt = APIRouter()
BASE = "/servicios/oportunidades"
EST = "/estudiante/oportunidades"
TONO_ESTADO = {"borrador": "gris", "publicada": "verde", "cerrada": "azul"}
TONO_POST = {"postulada": "azul", "preseleccionada": "ambar", "seleccionada": "verde", "no_seleccionada": "gris",
             "retirada": "gris"}


# --- Quien publica ------------------------------------------------------------------------------------------------------

@rt(BASE)
def get(auth):
    if not op.puede_publicar(auth):
        return no_autorizado()
    filas = [Li(Div(A(o["titulo"], href=f"{BASE}/{o['id']}", cls="font-medium hover:underline"),
                    insignia(op.TIPOS[o["tipo"]], "azul"), insignia(op.ESTADOS[o["estado"]], TONO_ESTADO[o["estado"]]),
                    insignia(f"{o['n_postulaciones']} postulación(es)", "gris") if o["n_postulaciones"] else "",
                    cls="flex flex-wrap items-center gap-2"),
                P(f"Para {op.PARA[o['para']].lower()}" + (f" · cierra el {formato.fecha(o['cierre'])}" if o["cierre"] else ""),
                  cls=TextPresets.muted_sm), cls="py-3") for o in op.listar(auth)]
    return pagina("Oportunidades", H2("Oportunidades"),
                  P("Becas, movilidad, pasantías, ayudantías de investigación y empleo para estudiantes y egresados. Quien "
                    "publica decide sobre las postulaciones y cada postulante recibe un aviso.",
                    cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
                  A(UkIcon("plus", height=14, width=14), "Nueva oportunidad", href=f"{BASE}/nueva",
                    cls="uk-btn uk-btn-primary gap-1 mb-4"),
                  Card(Ul(*filas, cls="divide-y divide-border")) if filas else
                  P("Todavía no hay oportunidades.", cls=TextPresets.muted_sm), usuario=auth)


def _form(auth, o=None, errores=()):
    o = o or {}
    es_nueva = "id" not in o
    pueden_todo = permisos.puede(auth, "gestionar_oportunidades")
    tipos = [(k, t) for k, t in op.TIPOS.items() if pueden_todo or k == "ayudantia"]
    proyectos = op.proyectos_que_dirige(auth) if not pueden_todo else _todos_los_proyectos()
    return fh.Form(
        mensaje_error(*errores),
        Div(campo("Tipo", Select(*[Option(t, value=k, selected=o.get("tipo") == k) for k, t in tipos], name="tipo",
                                 cls="uk-select", disabled=None if es_nueva else True)),
            campo("Para", Select(*[Option(t, value=k, selected=o.get("para") == k) for k, t in op.PARA.items()], name="para",
                                 cls="uk-select")), cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
        campo("Título", Input(name="titulo", value=o.get("titulo", ""), required=True, maxlength="200", cls="uk-input")),
        campo("Descripción", fh.Textarea(o.get("descripcion") or "", name="descripcion", rows=5, cls="uk-textarea")),
        campo("Requisitos", fh.Textarea(o.get("requisitos") or "", name="requisitos", rows=3, cls="uk-textarea")),
        Div(campo("Quién la ofrece", Input(name="organizacion", value=o.get("organizacion") or "", cls="uk-input")),
            campo("Cierre de postulaciones", Input(type="date", name="cierre", value=o.get("cierre") or "", cls="uk-input")),
            campo("Plazas", Input(name="plazas", value=str(o.get("plazas") or ""), inputmode="numeric", cls="uk-input")),
            campo("Enlace (opcional)", Input(name="enlace", value=o.get("enlace") or "", placeholder="https://", cls="uk-input")),
            campo("Contacto (opcional)", Input(name="contacto", value=o.get("contacto") or "", cls="uk-input")),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
        Div(campo("Proyecto (para ayudantías de investigación)",
                  Select(Option("—", value=""), *[Option(p["nombre"], value=str(p["id"]), selected=o.get("proyecto_id") == p["id"])
                                                  for p in proyectos], name="proyecto_id", cls="uk-select")),
            campo("Empleador (para empleo)",
                  Select(Option("—", value=""), *[Option(f"{e['organizacion']}", value=str(e["id"]),
                                                         selected=o.get("empleador_id") == e["id"])
                                                  for e in empleadores.listar(activos=True)], name="empleador_id",
                         cls="uk-select")), cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
        Div(Button("Guardar", type="submit", cls=ButtonT.primary), A("Cancelar", href=BASE, cls="uk-btn uk-btn-ghost"),
            cls="flex gap-2"), method="post", action=BASE if es_nueva else f"{BASE}/{o['id']}", cls="space-y-3")


def _todos_los_proyectos():
    from app.comun.db import get_db
    return get_db().q("SELECT id, nombre FROM proyecto WHERE estado <> 'finalizado' ORDER BY nombre")


@rt(f"{BASE}/nueva")
def get(auth):
    if not op.puede_publicar(auth):
        return no_autorizado()
    return pagina("Nueva oportunidad", A(UkIcon("arrow-left", height=14, width=14), "Oportunidades", href=BASE,
                                         cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
                  H2("Nueva oportunidad"), Card(_form(auth)), usuario=auth)


@rt(BASE)
async def post(auth, sess, req):
    if not op.puede_publicar(auth):
        return no_autorizado()
    d = dict(await req.form())
    oid, errores = op.crear(d, auth)
    if errores:
        return pagina("Nueva oportunidad", H2("Nueva oportunidad"), Card(_form(auth, d, errores)), usuario=auth)
    add_toast(sess, "Oportunidad creada como borrador: revísela y publíquela.", "success")
    return Redirect(f"{BASE}/{oid}")


def _postulante(x, o, auth):
    decidir = fh.Form(
        Input(name="nota", placeholder="Comentario para la persona (opcional)", maxlength="500", cls="uk-input h-8 text-sm"),
        Div(*[Button(op.ESTADOS_POSTULACION[e], type="submit", formaction=f"{BASE}/{o['id']}/postulaciones/{x['id']}/{e}",
                     cls=(ButtonT.default, ButtonT.xs)) for e in op.DECISIONES], cls="flex flex-wrap gap-1 mt-1"),
        method="post", cls="mt-2")
    return Li(Div(Span(f"{x['apellidos']}, {x['nombres']}", cls="font-medium text-sm"),
                  Span(f"RU {x['registro_universitario']}" if x["registro_universitario"] else "", cls=TextPresets.muted_sm),
                  Span(x["email"] or "", cls=TextPresets.muted_sm), insignia(op.ESTADOS_POSTULACION[x["estado"]], TONO_POST[x["estado"]]),
                  cls="flex flex-wrap items-center gap-2"),
              P(x["mensaje"], cls="text-sm whitespace-pre-line") if x["mensaje"] else "",
              P(f"Comentario: {x['nota']}", cls=TextPresets.muted_sm) if x["nota"] else "", decidir, cls="py-3")


@rt(f"{BASE}/{{oid}}")
def get(auth, oid: int):
    o = op.obtener(oid)
    if not o:
        return no_encontrado()
    if not op.puede_gestionar(auth, o):
        return no_autorizado()
    post_ = op.postulaciones(oid)
    acciones = Div(
        fh.Form(Button(UkIcon("rocket", height=14, width=14), "Publicar", type="submit", cls=ButtonT.primary), method="post",
                action=f"{BASE}/{oid}/publicar") if o["estado"] == "borrador" else "",
        fh.Form(Button("Cerrar las postulaciones", type="submit", cls=ButtonT.default), method="post",
                action=f"{BASE}/{oid}/cerrar") if o["estado"] == "publicada" else "", cls="flex gap-2 mb-4")
    return pagina(
        o["titulo"], A(UkIcon("arrow-left", height=14, width=14), "Oportunidades", href=BASE,
                       cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(o["titulo"]), Div(insignia(op.TIPOS[o["tipo"]], "azul"), insignia(op.ESTADOS[o["estado"]], TONO_ESTADO[o["estado"]]),
                             cls="flex gap-2 mb-4"), acciones,
        Div(Card(H3("Datos", cls="text-base font-semibold mb-2"), _form(auth, o)) if o["estado"] != "cerrada" else
            Card(P("Cerrada: ya no se edita.", cls="text-sm")),
            Card(H3(f"Postulaciones ({len(post_)})", cls="text-base font-semibold mb-1"),
                 Ul(*[_postulante(x, o, auth) for x in post_], cls="divide-y divide-border") if post_
                 else P("Todavía nadie postuló.", cls=TextPresets.muted_sm)),
            cls="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start"), usuario=auth)


@rt(f"{BASE}/{{oid}}")
async def post(auth, sess, oid: int, req):
    o = op.obtener(oid)
    if not o:
        return no_encontrado()
    if not op.puede_gestionar(auth, o):
        return no_autorizado()
    d = dict(await req.form())
    errores = op.actualizar(oid, d, auth)
    add_toast(sess, errores[0] if errores else "Guardado.", "error" if errores else "success")
    return Redirect(f"{BASE}/{oid}")


@rt(f"{BASE}/{{oid}}/publicar")
def post(auth, sess, oid: int):
    errores = op.cambiar_estado(oid, "publicada", auth)
    add_toast(sess, errores[0] if errores else "Publicada: los estudiantes ya la ven.", "error" if errores else "success")
    return Redirect(f"{BASE}/{oid}")


@rt(f"{BASE}/{{oid}}/cerrar")
def post(auth, sess, oid: int):
    errores = op.cambiar_estado(oid, "cerrada", auth)
    add_toast(sess, errores[0] if errores else "Cerrada.", "error" if errores else "success")
    return Redirect(f"{BASE}/{oid}")


@rt(f"{BASE}/{{oid}}/postulaciones/{{pid}}/{{estado}}")
async def post(auth, sess, oid: int, pid: int, estado: str, req):
    o = op.obtener(oid)
    if not o or not op.puede_gestionar(auth, o):
        return no_autorizado()
    nota = (await req.form()).get("nota", "")
    errores = op.decidir(pid, estado, nota, auth)
    add_toast(sess, errores[0] if errores else "Decisión registrada: se avisó a la persona.", "error" if errores else "success")
    return Redirect(f"{BASE}/{oid}")


# --- Estudiantes y egresados -----------------------------------------------------------------------------------------------

@rt(EST)
def get(auth, tipo: str = ""):
    externo, error = _requiere(auth)
    if error:
        return error
    tipo = tipo if tipo in op.TIPOS else ""
    lista = op.para_estudiante(externo, tipo)
    mias = op.mis_postulaciones(externo)
    filtros = Div(*[A(t, href=f"{EST}?tipo={k}" if k else EST, aria_current="true" if k == tipo else None,
                      cls="text-sm rounded-full border px-3 py-1 " + ("bg-primary text-primary-foreground border-primary"
                                                                        if k == tipo else "hover:bg-muted"))
                    for k, t in (("", "Todas"), *op.TIPOS.items())], cls="flex flex-wrap gap-2 mb-4")
    return pagina(
        "Oportunidades", H2("Oportunidades"),
        P("Becas, movilidad, pasantías, ayudantías de investigación y empleo que publica la Carrera. Postule desde aquí y reciba "
          "la respuesta en sus avisos.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")), filtros,
        Div(*[Card(Div(insignia(op.TIPOS[o["tipo"]], "azul"),
                       Span(f"Cierra el {formato.fecha(o['cierre'])}" if o["cierre"] else "Sin fecha de cierre",
                            cls=TextPresets.muted_sm), cls="flex flex-wrap items-center gap-2"),
                   A(o["titulo"], href=f"{EST}/{o['id']}", cls="font-medium hover:underline block mt-1"),
                   P(o["organizacion"] or "", cls=TextPresets.muted_sm)) for o in lista], cls="grid grid-cols-1 md:grid-cols-2 gap-3")
        if lista else Card(P("No hay oportunidades abiertas en este momento.", cls="text-sm")),
        Card(H3("Mis postulaciones", cls="text-base font-semibold mb-1"),
             Ul(*[Li(A(x["titulo"], href=f"{EST}/{x['oportunidad_id']}", cls="hover:underline text-sm"),
                     insignia(op.ESTADOS_POSTULACION[x["estado"]], TONO_POST[x["estado"]]), cls="flex items-center gap-2 py-1.5")
                  for x in mias], cls="divide-y divide-border"), cls="mt-6") if mias else "", usuario=auth)


@rt(f"{EST}/{{oid}}")
def get(auth, oid: int):
    externo, error = _requiere(auth)
    if error:
        return error
    o = op.obtener(oid)
    if not o or not op.visible_para(externo, o):
        return no_encontrado()
    mia = op.postulacion_de(oid, externo)
    activa = mia and mia["estado"] != "retirada"
    return pagina(
        o["titulo"], A(UkIcon("arrow-left", height=14, width=14), "Oportunidades", href=EST,
                       cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(o["titulo"]),
        Div(insignia(op.TIPOS[o["tipo"]], "azul"), Span(o["organizacion"] or o["empleador"] or "", cls=TextPresets.muted_sm),
            insignia("Cerrada", "gris") if not op.abierta(o) else "", cls="flex flex-wrap items-center gap-2 mb-4"),
        Card(*[Div(H3(t, cls="text-sm font-semibold"), P(v, cls="text-sm whitespace-pre-line"), cls="mb-3")
               for t, v in (("Descripción", o["descripcion"]), ("Requisitos", o["requisitos"]),
                            ("Plazas", str(o["plazas"]) if o["plazas"] else None),
                            ("Cierre de postulaciones", formato.fecha(o["cierre"]) if o["cierre"] else None),
                            ("Proyecto", o["proyecto"]), ("Contacto", o["contacto"])) if v],
             A("Más información", href=o["enlace"], target="_blank", rel="noopener noreferrer",
               cls="text-sm text-primary hover:underline") if o["enlace"] else ""),
        Card(H3("Mi postulación", cls="text-base font-semibold mb-1"),
             Div(insignia(op.ESTADOS_POSTULACION[mia["estado"]], TONO_POST[mia["estado"]]),
                 P(mia["nota"], cls="text-sm mt-1") if mia["nota"] else "",
                 fh.Form(Button("Retirar mi postulación", type="submit", cls=(ButtonT.ghost, ButtonT.sm)), method="post",
                         action=f"{EST}/{oid}/retirar") if mia["estado"] in ("postulada", "preseleccionada") else "")
             if activa else (fh.Form(
                 campo("Mensaje (por qué le interesa, opcional)",
                       fh.Textarea("", name="mensaje", rows=4, maxlength="1000", cls="uk-textarea")),
                 Button("Postular", type="submit", cls=ButtonT.primary), method="post", action=f"{EST}/{oid}/postular",
                 cls="space-y-2") if op.abierta(o) else P("La convocatoria ya cerró.", cls="text-sm")), cls="mt-4"),
        usuario=auth)


@rt(f"{EST}/{{oid}}/postular")
def post(auth, sess, oid: int, mensaje: str = ""):
    externo, error = _requiere(auth)
    if error:
        return error
    errores = op.postular(oid, externo, mensaje)
    add_toast(sess, errores[0] if errores else "Postulación enviada.", "error" if errores else "success")
    return Redirect(f"{EST}/{oid}")


@rt(f"{EST}/{{oid}}/retirar")
def post(auth, sess, oid: int):
    externo, error = _requiere(auth)
    if error:
        return error
    errores = op.retirar(oid, externo)
    add_toast(sess, errores[0] if errores else "Postulación retirada.", "error" if errores else "info")
    return Redirect(f"{EST}/{oid}")

