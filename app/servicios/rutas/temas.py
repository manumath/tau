"""Banco de temas de grado (PLAN §67, etapa 5): el docente publica temas y responde a quienes los piden; el estudiante los
explora en /estudiante/temas, pide tutor y, si lo aceptan, empieza su perfil con ese título y ese tutor."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Li, Option, P, Redirect, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.comun.componentes.layout import campo, mensaje_error, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import get_db
from app.comun.estudiantes import requiere as _requiere
from app.servicios import temas
from app.servicios.rutas.comun import no_autorizado, no_encontrado

rt = APIRouter()
BASE = "/servicios/temas"
EST = "/estudiante/temas"
TONO = {"borrador": "gris", "publicado": "verde", "retirado": "gris"}
TONO_SOL = {"pendiente": "ambar", "aceptada": "verde", "rechazada": "gris", "retirada": "gris"}


def _lineas():
    return get_db().q("SELECT id, nombre FROM linea_investigacion ORDER BY nombre")


# --- Docente -----------------------------------------------------------------------------------------------------------------

@rt(BASE)
def get(auth):
    if not temas.puede_publicar(auth):
        return no_autorizado()
    filas = [Li(Div(A(t["titulo"], href=f"{BASE}/{t['id']}", cls="font-medium hover:underline"),
                    insignia(temas.ESTADOS[t["estado"]], TONO[t["estado"]]),
                    insignia(f"{t['pendientes']} pedido(s)", "ambar") if t["pendientes"] else "",
                    insignia(f"{t['aceptadas']} de {t['cupos']} cupos", "gris"), cls="flex flex-wrap items-center gap-2"),
                P(f"{t['nombres']} {t['apellidos']} · {temas.MODALIDADES[t['modalidad']]}", cls=TextPresets.muted_sm),
                cls="py-3") for t in temas.listar(auth)]
    return pagina("Temas de grado", H2("Temas de grado"),
                  P("Publique temas de tesis o proyecto de grado para que los estudiantes los conozcan y le pidan ser su tutor(a). "
                    "Usted decide a quién acepta.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
                  A(UkIcon("plus", height=14, width=14), "Nuevo tema", href=f"{BASE}/nuevo", cls="uk-btn uk-btn-primary gap-1 mb-4"),
                  Card(Ul(*filas, cls="divide-y divide-border")) if filas else
                  P("Todavía no publicó temas.", cls=TextPresets.muted_sm), usuario=auth)


def _form(t=None, errores=()):
    t = t or {}
    nuevo = "id" not in t
    return fh.Form(
        mensaje_error(*errores),
        campo("Título del tema", Input(name="titulo", value=t.get("titulo", ""), required=True, maxlength="300", cls="uk-input")),
        campo("Descripción", fh.Textarea(t.get("descripcion") or "", name="descripcion", rows=6, cls="uk-textarea")),
        campo("Conocimientos previos que conviene tener", fh.Textarea(t.get("requisitos") or "", name="requisitos", rows=3,
                                                                       cls="uk-textarea")),
        Div(campo("Línea de investigación", Select(Option("—", value=""), *[Option(x["nombre"], value=str(x["id"]),
                                                                                  selected=t.get("linea_id") == x["id"])
                                                                           for x in _lineas()], name="linea_id", cls="uk-select")),
            campo("Modalidad", Select(*[Option(n, value=k, selected=t.get("modalidad") == k) for k, n in temas.MODALIDADES.items()],
                                      name="modalidad", cls="uk-select")),
            campo("Cupos", Input(name="cupos", value=str(t.get("cupos", 1)), inputmode="numeric", cls="uk-input")),
            cls="grid grid-cols-1 sm:grid-cols-3 gap-3"),
        Div(Button("Guardar", type="submit", cls=ButtonT.primary), A("Cancelar", href=BASE, cls="uk-btn uk-btn-ghost"),
            cls="flex gap-2"), method="post", action=BASE if nuevo else f"{BASE}/{t['id']}", cls="space-y-3")


@rt(f"{BASE}/nuevo")
def get(auth):
    if not temas.puede_publicar(auth):
        return no_autorizado()
    return pagina("Nuevo tema", H2("Nuevo tema"), Card(_form()), usuario=auth)


@rt(BASE)
async def post(auth, sess, req):
    if not temas.puede_publicar(auth):
        return no_autorizado()
    d = dict(await req.form())
    tid, errores = temas.crear(d, auth)
    if errores:
        return pagina("Nuevo tema", H2("Nuevo tema"), Card(_form(d, errores)), usuario=auth)
    add_toast(sess, "Tema creado como borrador: publíquelo para que lo vean los estudiantes.", "success")
    return Redirect(f"{BASE}/{tid}")


def _solicitud(s, t):
    pendiente = s["estado"] == "pendiente"
    return Li(Div(Span(f"{s['apellidos']}, {s['nombres']}", cls="font-medium text-sm"),
                  Span(f"RU {s['registro_universitario']}" if s["registro_universitario"] else "", cls=TextPresets.muted_sm),
                  Span(s["email"] or "", cls=TextPresets.muted_sm), insignia(temas.ESTADOS_SOLICITUD[s["estado"]], TONO_SOL[s["estado"]]),
                  cls="flex flex-wrap items-center gap-2"),
              P(s["mensaje"], cls="text-sm whitespace-pre-line") if s["mensaje"] else "",
              P(f"Su respuesta: {s['respuesta']}", cls=TextPresets.muted_sm) if s["respuesta"] else "",
              fh.Form(Input(name="respuesta", placeholder="Mensaje para el estudiante (opcional)", maxlength="500",
                            cls="uk-input h-8 text-sm"),
                      Div(Button("Aceptar", type="submit", formaction=f"{BASE}/{t['id']}/solicitudes/{s['id']}/aceptar",
                                 cls=(ButtonT.primary, ButtonT.xs)),
                          Button("No aceptar", type="submit", formaction=f"{BASE}/{t['id']}/solicitudes/{s['id']}/rechazar",
                                 cls=(ButtonT.default, ButtonT.xs)), cls="flex gap-1 mt-1"), method="post", cls="mt-2")
              if pendiente else "", cls="py-3")


@rt(f"{BASE}/{{tid}}")
def get(auth, tid: int):
    t = temas.obtener(tid)
    if not t:
        return no_encontrado()
    if not temas.puede_gestionar(auth, t):
        return no_autorizado()
    sols = temas.solicitudes(tid)
    return pagina(
        t["titulo"], A(UkIcon("arrow-left", height=14, width=14), "Temas de grado", href=BASE,
                       cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(t["titulo"]), Div(insignia(temas.ESTADOS[t["estado"]], TONO[t["estado"]]),
                             insignia(f"{t['aceptadas']} de {t['cupos']} cupos", "gris"), cls="flex gap-2 mb-4"),
        Div(fh.Form(Button("Publicar", type="submit", cls=ButtonT.primary), method="post", action=f"{BASE}/{tid}/publicar")
            if t["estado"] == "borrador" else "",
            fh.Form(Button("Retirar el tema", type="submit", cls=ButtonT.default), method="post", action=f"{BASE}/{tid}/retirar")
            if t["estado"] != "retirado" else "", cls="flex gap-2 mb-4"),
        Div(Card(H3("Datos", cls="text-base font-semibold mb-2"), _form(t)) if t["estado"] != "retirado" else
            Card(P("Retirado: ya no se edita.", cls="text-sm")),
            Card(H3(f"Pedidos de tutoría ({len(sols)})", cls="text-base font-semibold mb-1"),
                 Ul(*[_solicitud(s, t) for s in sols], cls="divide-y divide-border") if sols
                 else P("Todavía nadie lo pidió.", cls=TextPresets.muted_sm)),
            cls="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start"), usuario=auth)


@rt(f"{BASE}/{{tid}}")
async def post(auth, sess, tid: int, req):
    t = temas.obtener(tid)
    if not t:
        return no_encontrado()
    if not temas.puede_gestionar(auth, t):
        return no_autorizado()
    errores = temas.actualizar(tid, dict(await req.form()), auth)
    add_toast(sess, errores[0] if errores else "Guardado.", "error" if errores else "success")
    return Redirect(f"{BASE}/{tid}")


def _estado(auth, sess, tid, estado, mensaje):
    t = temas.obtener(tid)
    if not t:
        return no_encontrado()
    errores = temas.cambiar_estado(tid, estado, auth)
    add_toast(sess, errores[0] if errores else mensaje, "error" if errores else "success")
    return Redirect(f"{BASE}/{tid}")


@rt(f"{BASE}/{{tid}}/publicar")
def post(auth, sess, tid: int):
    return _estado(auth, sess, tid, "publicado", "Publicado: los estudiantes ya lo ven.")


@rt(f"{BASE}/{{tid}}/retirar")
def post(auth, sess, tid: int):
    return _estado(auth, sess, tid, "retirado", "Tema retirado.")


async def _responder(auth, sess, tid, sid, acepta, req):
    t = temas.obtener(tid)
    if not t or not temas.puede_gestionar(auth, t):
        return no_autorizado()
    errores = temas.responder(sid, acepta, (await req.form()).get("respuesta", ""), auth)
    add_toast(sess, errores[0] if errores else "Respuesta enviada: se avisó al estudiante.", "error" if errores else "success")
    return Redirect(f"{BASE}/{tid}")


@rt(f"{BASE}/{{tid}}/solicitudes/{{sid}}/aceptar")
async def post(auth, sess, tid: int, sid: int, req):
    return await _responder(auth, sess, tid, sid, True, req)


@rt(f"{BASE}/{{tid}}/solicitudes/{{sid}}/rechazar")
async def post(auth, sess, tid: int, sid: int, req):
    return await _responder(auth, sess, tid, sid, False, req)


# --- Estudiante ---------------------------------------------------------------------------------------------------------------

@rt(EST)
def get(auth, q: str = "", linea: str = "", modalidad: str = ""):
    externo, error = _requiere(auth)
    if error:
        return error
    lista = temas.disponibles(q, linea, modalidad)
    mias = temas.mis_solicitudes(externo)
    return pagina(
        "Temas de grado", H2("Temas de grado"),
        P("Temas que los docentes proponen para tesis o proyecto de grado. Pida a quien le interese que sea su tutor(a): si lo "
          "acepta, empiece su perfil con ese tema desde «Grado».", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        fh.Form(Input(name="q", value=q, placeholder="Buscar por título, tema o docente", aria_label="Buscar", cls="uk-input"),
                Select(Option("Todas las líneas", value=""), *[Option(x["nombre"], value=str(x["id"]), selected=str(x["id"]) == linea)
                                                               for x in _lineas()], name="linea", aria_label="Línea",
                       cls="uk-select"),
                Select(Option("Cualquier modalidad", value=""), *[Option(n, value=k, selected=k == modalidad)
                                                                  for k, n in temas.MODALIDADES.items() if k != "cualquiera"],
                       name="modalidad", aria_label="Modalidad", cls="uk-select"),
                Button("Buscar", type="submit", cls=ButtonT.default), method="get", cls="grid grid-cols-1 sm:grid-cols-4 gap-2 mb-4"),
        Div(*[Card(A(t["titulo"], href=f"{EST}/{t['id']}", cls="font-medium hover:underline"),
                   P(f"{t['nombres']} {t['apellidos']} · {temas.MODALIDADES[t['modalidad']]}"
                     + (f" · {t['linea']}" if t["linea"] else ""), cls=TextPresets.muted_sm),
                   P((t["descripcion"] or "")[:200] + ("…" if len(t["descripcion"] or "") > 200 else ""), cls="text-sm"))
              for t in lista], cls="grid grid-cols-1 md:grid-cols-2 gap-3")
        if lista else Card(P("No hay temas con esos criterios.", cls="text-sm")),
        Card(H3("Mis pedidos", cls="text-base font-semibold mb-1"),
             Ul(*[Li(Div(A(s["titulo"], href=f"{EST}/{s['tema_id']}", cls="text-sm hover:underline"),
                         insignia(temas.ESTADOS_SOLICITUD[s["estado"]], TONO_SOL[s["estado"]]), cls="flex items-center gap-2"),
                     A("Empezar mi perfil con este tema", href=f"/estudiante/grado/nuevo?tema={s['tema_id']}",
                       cls="text-sm text-primary hover:underline") if s["estado"] == "aceptada" else "", cls="py-2")
                  for s in mias], cls="divide-y divide-border"), cls="mt-6") if mias else "", usuario=auth)


@rt(f"{EST}/{{tid}}")
def get(auth, tid: int):
    externo, error = _requiere(auth)
    if error:
        return error
    t = temas.obtener(tid)
    mia = temas.solicitud_de(tid, externo) if t else None
    if not t or (t["estado"] != "publicado" and not mia):
        return no_encontrado()
    activa = mia and mia["estado"] != "retirada"
    return pagina(
        t["titulo"], A(UkIcon("arrow-left", height=14, width=14), "Temas de grado", href=EST,
                       cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(t["titulo"]), P(f"Propone: {t['nombres']} {t['apellidos']} · {temas.MODALIDADES[t['modalidad']]}"
                           + (f" · {t['linea']}" if t["linea"] else ""), cls=(TextPresets.muted_sm, "mb-4")),
        Card(*[Div(H3(n, cls="text-sm font-semibold"), P(v, cls="text-sm whitespace-pre-line"), cls="mb-3")
               for n, v in (("Descripción", t["descripcion"]), ("Conocimientos previos", t["requisitos"])) if v],
             P(f"Cupos: {t['cupos'] - t['aceptadas']} de {t['cupos']} disponibles.", cls=TextPresets.muted_sm)),
        Card(H3("Mi pedido", cls="text-base font-semibold mb-1"),
             Div(insignia(temas.ESTADOS_SOLICITUD[mia["estado"]], TONO_SOL[mia["estado"]]),
                 P(mia["respuesta"], cls="text-sm mt-1") if mia["respuesta"] else "",
                 A("Empezar mi perfil con este tema", href=f"/estudiante/grado/nuevo?tema={tid}",
                   cls="uk-btn uk-btn-primary mt-2") if mia["estado"] == "aceptada" else "",
                 fh.Form(Button("Retirar mi pedido", type="submit", cls=(ButtonT.ghost, ButtonT.sm)), method="post",
                         action=f"{EST}/{tid}/retirar") if mia["estado"] == "pendiente" else "")
             if activa else fh.Form(
                 campo("Mensaje para el docente (por qué le interesa, opcional)",
                       fh.Textarea("", name="mensaje", rows=4, maxlength="1000", cls="uk-textarea")),
                 Button("Pedirle ser mi tutor(a) en este tema", type="submit", cls=ButtonT.primary), method="post",
                 action=f"{EST}/{tid}/pedir", cls="space-y-2"), cls="mt-4"), usuario=auth)


@rt(f"{EST}/{{tid}}/pedir")
def post(auth, sess, tid: int, mensaje: str = ""):
    externo, error = _requiere(auth)
    if error:
        return error
    errores = temas.solicitar(tid, externo, mensaje)
    add_toast(sess, errores[0] if errores else "Se avisó al docente.", "error" if errores else "success")
    return Redirect(f"{EST}/{tid}")


@rt(f"{EST}/{{tid}}/retirar")
def post(auth, sess, tid: int):
    externo, error = _requiere(auth)
    if error:
        return error
    errores = temas.retirar(tid, externo)
    add_toast(sess, errores[0] if errores else "Pedido retirado.", "error" if errores else "info")
    return Redirect(f"{EST}/{tid}")
