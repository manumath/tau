"""Bienestar y orientación (PLAN §67, etapa 9): el estudiante consulta las preguntas frecuentes y el directorio de servicios de apoyo
y escribe al buzón (identificado o anónimo); la Dirección de Carrera y la Coordinación académica lo atienden y mantienen el
contenido. Un envío anónimo no se vincula con la cuenta (ni siquiera en el registro de peticiones)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Li, Option, P, Redirect, Response, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.comun import formato
from app.comun.componentes.layout import campo, pagina
from app.comun.componentes.registros import insignia
from app.estudiantil import orientacion as ori
from app.estudiantil.rutas.estudiante import _requiere

rt = APIRouter()
EST = "/estudiante"
BASE = "/servicios"
TONO = {"recibida": "ambar", "en_atencion": "azul", "respondida": "verde", "cerrada": "gris"}


def _no():
    return Response("No autorizado", status_code=403)


# --- Estudiante: orientación y buzón ---------------------------------------------------------------------------------------------

@rt(f"{EST}/orientacion")
def get(auth):
    externo, error = _requiere(auth)
    if error:
        return error
    faqs: dict = {}
    for q in ori.preguntas():
        faqs.setdefault(q["categoria"], []).append(q)
    servicios = ori.servicios()
    return pagina(
        "Orientación", H2("Bienestar y orientación"),
        P("Dónde pedir ayuda y respuestas a lo que más se pregunta. Si no encuentra lo que busca, escriba al ",
          A("buzón", href=f"{EST}/buzon", cls="text-primary hover:underline"), ".", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Card(H3("Servicios de apoyo", cls="text-base font-semibold mb-2"),
             Ul(*[Li(Div(Span(s["nombre"], cls="font-medium text-sm"), insignia(ori.TIPOS_SERVICIO[s["tipo"]], "azul"),
                         cls="flex flex-wrap items-center gap-2"),
                     P(s["descripcion"], cls="text-sm") if s["descripcion"] else "",
                     P(" · ".join(x for x in (s["contacto"], s["horario"]) if x), cls=TextPresets.muted_sm),
                     A("Más información", href=s["enlace"], target="_blank", rel="noopener noreferrer",
                       cls="text-sm text-primary hover:underline") if s["enlace"] else "", cls="py-3") for s in servicios],
                cls="divide-y divide-border")) if servicios else "",
        *[Card(H3(cat, cls="text-base font-semibold mb-1"),
               *[fh.Details(fh.Summary(q["pregunta"], cls="cursor-pointer text-sm font-medium py-1.5"),
                            P(q["respuesta"], cls="text-sm whitespace-pre-line pb-2 pl-4"), cls="border-b border-border")
                 for q in qs], cls="mt-4") for cat, qs in faqs.items()],
        P("Todavía no hay preguntas frecuentes ni servicios publicados.", cls=TextPresets.muted_sm) if not (faqs or servicios) else "",
        usuario=auth)


@rt(f"{EST}/buzon")
def get(auth):
    externo, error = _requiere(auth)
    if error:
        return error
    mias = ori.mias(externo)
    return pagina(
        "Buzón", H2("Buzón de consultas, reclamos y sugerencias"),
        P("Lo atienden la Dirección de Carrera y la Coordinación académica. Si lo envía con su nombre, la respuesta le llega aquí y en "
          "sus avisos. Si marca «Anónimo», nadie sabrá quién lo envió (no se guarda su cuenta ni la hora), pero tampoco podrán "
          "responderle personalmente: la respuesta se publica en las preguntas frecuentes.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Card(fh.Form(
            Div(campo("Tipo", Select(*[Option(t, value=k) for k, t in ori.TIPOS.items()], name="tipo", cls="uk-select")),
                campo("Asunto", Input(name="asunto", required=True, maxlength="150", cls="uk-input")),
                cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
            campo("Mensaje", fh.Textarea("", name="texto", rows=6, required=True, minlength="10", maxlength="4000", cls="uk-textarea")),
            Div(Button("Enviar con mi nombre", type="submit", cls=ButtonT.primary),
                Button("Enviar como anónimo", type="submit", formaction=f"{EST}/buzon/anonima", cls=ButtonT.default),
                cls="flex flex-wrap gap-2"), method="post", action=f"{EST}/buzon", cls="space-y-3")),
        Card(H3("Mis envíos", cls="text-base font-semibold mb-1"),
             Ul(*[Li(Div(Span(c["asunto"], cls="font-medium text-sm"), insignia(ori.TIPOS[c["tipo"]], "azul"),
                         insignia(ori.ESTADOS[c["estado"]], TONO[c["estado"]]), cls="flex flex-wrap items-center gap-2"),
                     P(c["texto"], cls="text-sm whitespace-pre-line"),
                     P(f"Respuesta: {c['respuesta']}", cls="text-sm font-medium mt-1") if c["respuesta"] else "", cls="py-3")
                  for c in mias], cls="divide-y divide-border"), cls="mt-4") if mias else "",
        P("Los envíos anónimos no aparecen aquí: no se guardan con su nombre.", cls=(TextPresets.muted_sm, "mt-2")), usuario=auth)


def _enviar(auth, sess, anonima, tipo, asunto, texto):
    externo, error = _requiere(auth)
    if error:
        return error
    errores = ori.enviar(externo, tipo, asunto, texto, anonima)
    add_toast(sess, errores[0] if errores else "Enviado. Gracias." + ("" if anonima else " Le responderán aquí."),
              "error" if errores else "success")
    return Redirect(f"{EST}/buzon")


@rt(f"{EST}/buzon")
def post(auth, sess, tipo: str = "", asunto: str = "", texto: str = ""):
    return _enviar(auth, sess, False, tipo, asunto, texto)


@rt(f"{EST}/buzon/anonima")
def post(auth, sess, tipo: str = "", asunto: str = "", texto: str = ""):
    return _enviar(auth, sess, True, tipo, asunto, texto)


# --- Personal: buzón ---------------------------------------------------------------------------------------------------------------

@rt(f"{BASE}/buzon")
def get(auth, estado: str = ""):
    if not ori.puede_gestionar(auth):
        return _no()
    estado = estado if estado in ori.ESTADOS else ""
    lista = ori.listar(estado)
    filtros = Div(*[A(t, href=f"{BASE}/buzon?estado={k}" if k else f"{BASE}/buzon", aria_current="true" if k == estado else None,
                      cls="text-sm rounded-full border px-3 py-1 " + ("bg-primary text-primary-foreground border-primary"
                                                                        if k == estado else "hover:bg-muted"))
                    for k, t in (("", "Todas"), *ori.ESTADOS.items())], cls="flex flex-wrap gap-2 mb-4")
    return pagina(
        "Buzón", H2("Buzón de consultas, reclamos y sugerencias"),
        A(UkIcon("settings", height=14, width=14), "Preguntas frecuentes y servicios de apoyo", href=f"{BASE}/orientacion",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"), filtros,
        Card(Ul(*[Li(Div(A(c["asunto"], href=f"{BASE}/buzon/{c['id']}", cls="font-medium hover:underline"),
                         insignia(ori.TIPOS[c["tipo"]], "azul"), insignia(ori.ESTADOS[c["estado"]], TONO[c["estado"]]),
                         insignia("Anónima", "gris") if c["anonima"] else "", cls="flex flex-wrap items-center gap-2"),
                     P((f"{c['nombres']} {c['apellidos']} · " if c["nombres"] else "") + formato.fecha(c["creada_en"][:10]),
                       cls=TextPresets.muted_sm), cls="py-3") for c in lista], cls="divide-y divide-border"))
        if lista else Card(P("No hay consultas.", cls="text-sm")), usuario=auth)


@rt(f"{BASE}/buzon/{{cid}}")
def get(auth, cid: int):
    c = ori.obtener(cid)
    if not c:
        return Response("No encontrado", status_code=404)
    if not ori.puede_gestionar(auth):
        return _no()
    abierta = c["estado"] in ("recibida", "en_atencion")
    return pagina(
        c["asunto"], A(UkIcon("arrow-left", height=14, width=14), "Buzón", href=f"{BASE}/buzon",
                       cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(c["asunto"]),
        Div(insignia(ori.TIPOS[c["tipo"]], "azul"), insignia(ori.ESTADOS[c["estado"]], TONO[c["estado"]]),
            insignia("Anónima: no se sabe quién la envió", "gris") if c["anonima"] else
            Span(f"{c['nombres']} {c['apellidos']} · {c['email'] or ''}", cls=TextPresets.muted_sm), cls="flex flex-wrap items-center gap-2 mb-4"),
        Card(P(c["texto"], cls="text-sm whitespace-pre-line")),
        Card(H3("Respuesta", cls="text-base font-semibold mb-1"), P(c["respuesta"], cls="text-sm whitespace-pre-line"), cls="mt-4")
        if c["respuesta"] else (Card(
            H3("Responder", cls="text-base font-semibold mb-1"),
            P("Una consulta anónima no tiene a quién responder: se publica la respuesta en las preguntas frecuentes."
              if c["anonima"] else "La persona recibe la respuesta en su portal y en sus avisos. Puede publicarla también en las "
                                   "preguntas frecuentes (sin su nombre).", cls=(TextPresets.muted_sm, "mb-2")),
            fh.Form(campo("Respuesta", fh.Textarea("", name="respuesta", rows=5, required=True, cls="uk-textarea")),
                    Div(campo("Categoría en las preguntas frecuentes", Input(name="categoria", value="Consultas", cls="uk-input")),
                        fh.Label(fh.Input(type="checkbox", name="faq", value="1", checked=bool(c["anonima"]) or None,
                                          disabled=bool(c["anonima"]) or None, cls="uk-checkbox"),
                                 Span(" Publicar también en las preguntas frecuentes" if not c["anonima"] else
                                      " Se publica en las preguntas frecuentes", cls="text-sm"), cls="flex items-center gap-2"),
                        cls="grid grid-cols-1 sm:grid-cols-2 gap-3 items-end"),
                    Div(Button("Responder", type="submit", cls=ButtonT.primary),
                        Button("Marcar en atención", type="submit", formaction=f"{BASE}/buzon/{cid}/estado/en_atencion",
                               formnovalidate=True, cls=ButtonT.default),
                        Button("Cerrar sin responder", type="submit", formaction=f"{BASE}/buzon/{cid}/estado/cerrada",
                               formnovalidate=True, cls=ButtonT.ghost), cls="flex flex-wrap gap-2"),
                    method="post", action=f"{BASE}/buzon/{cid}/responder", cls="space-y-3"), cls="mt-4") if abierta else ""),
        usuario=auth)


@rt(f"{BASE}/buzon/{{cid}}/responder")
def post(auth, sess, cid: int, respuesta: str = "", categoria: str = "", faq: str = ""):
    if not ori.puede_gestionar(auth):
        return _no()
    c = ori.obtener(cid)
    errores = ori.responder(cid, respuesta, auth, faq == "1" or bool(c and c["anonima"]), categoria)
    add_toast(sess, errores[0] if errores else "Respondida.", "error" if errores else "success")
    return Redirect(f"{BASE}/buzon/{cid}")


@rt(f"{BASE}/buzon/{{cid}}/estado/{{estado}}")
def post(auth, sess, cid: int, estado: str):
    if not ori.puede_gestionar(auth):
        return _no()
    errores = ori.cambiar_estado(cid, estado, auth)
    add_toast(sess, errores[0] if errores else "Guardado.", "error" if errores else "success")
    return Redirect(f"{BASE}/buzon/{cid}")


# --- Personal: preguntas frecuentes y servicios de apoyo --------------------------------------------------------------------------

@rt(f"{BASE}/orientacion")
def get(auth):
    if not ori.puede_gestionar(auth):
        return _no()
    return pagina(
        "Orientación", A(UkIcon("arrow-left", height=14, width=14), "Buzón", href=f"{BASE}/buzon",
                         cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2("Preguntas frecuentes y servicios de apoyo"),
        P("Lo que ven los estudiantes en «Orientación». Los cambios se muestran al instante.", cls=(TextPresets.muted_sm, "mb-4")),
        Card(H3("Preguntas frecuentes", cls="text-base font-semibold mb-2"),
             *[fh.Form(Div(Input(name="categoria", value=q["categoria"], aria_label="Categoría", cls="uk-input"),
                           Input(name="pregunta", value=q["pregunta"], aria_label="Pregunta", cls="uk-input"), cls="grid grid-cols-2 gap-2"),
                       fh.Textarea(q["respuesta"], name="respuesta", rows=2, aria_label="Respuesta", cls="uk-textarea mt-1"),
                       Div(fh.Label(Input(type="checkbox", name="publicada", value="1", checked=bool(q["publicada"]) or None,
                                          cls="uk-checkbox"), Span(" Publicada", cls="text-sm"), cls="flex items-center gap-2"),
                           Button("Guardar", type="submit", cls=(ButtonT.default, ButtonT.xs)),
                           Button("Eliminar", type="button", hx_post=f"{BASE}/orientacion/preguntas/{q['id']}/eliminar",
                                  hx_swap="none", hx_confirm="¿Eliminar esta pregunta?", cls=(ButtonT.ghost, ButtonT.xs)),
                           cls="flex items-center gap-3 mt-1"),
                       method="post", action=f"{BASE}/orientacion/preguntas/{q['id']}", cls="border-b border-border py-3")
               for q in ori.preguntas(solo_publicadas=False)],
             fh.Form(H3("Nueva pregunta", cls="text-sm font-semibold mt-4"),
                     Div(Input(name="categoria", placeholder="Categoría (Trámites, Becas…)", required=True, aria_label="Categoría",
                               cls="uk-input"), Input(name="pregunta", placeholder="Pregunta", required=True, aria_label="Pregunta",
                                                      cls="uk-input"), cls="grid grid-cols-2 gap-2"),
                     fh.Textarea("", name="respuesta", rows=3, placeholder="Respuesta", required=True, aria_label="Respuesta",
                                 cls="uk-textarea mt-1"),
                     Button("Agregar", type="submit", cls=(ButtonT.primary, ButtonT.sm)), method="post",
                     action=f"{BASE}/orientacion/preguntas", cls="space-y-1")),
        Card(H3("Servicios de apoyo", cls="text-base font-semibold mb-2"),
             *[_form_servicio(s) for s in ori.servicios(solo_activos=False)], _form_servicio(None), cls="mt-4"), usuario=auth)


def _form_servicio(s):
    s = s or {}
    nuevo = "id" not in s
    return fh.Form(
        H3("Nuevo servicio", cls="text-sm font-semibold mt-4") if nuevo else "",
        Div(Select(*[Option(t, value=k, selected=s.get("tipo") == k) for k, t in ori.TIPOS_SERVICIO.items()], name="tipo",
                   aria_label="Tipo", cls="uk-select"),
            Input(name="nombre", value=s.get("nombre", ""), placeholder="Nombre", required=True, aria_label="Nombre", cls="uk-input"),
            Input(name="contacto", value=s.get("contacto") or "", placeholder="Contacto", aria_label="Contacto", cls="uk-input"),
            Input(name="horario", value=s.get("horario") or "", placeholder="Horario", aria_label="Horario", cls="uk-input"),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-2"),
        fh.Textarea(s.get("descripcion") or "", name="descripcion", rows=2, placeholder="Descripción", aria_label="Descripción",
                    cls="uk-textarea mt-1"),
        Input(name="enlace", value=s.get("enlace") or "", placeholder="Enlace (https://…)", aria_label="Enlace", cls="uk-input mt-1"),
        Div(fh.Label(Input(type="checkbox", name="activo", value="1", checked=bool(s.get("activo", 1)) or None, cls="uk-checkbox"),
                     Span(" Visible", cls="text-sm"), cls="flex items-center gap-2"),
            Button("Agregar" if nuevo else "Guardar", type="submit", cls=(ButtonT.primary if nuevo else ButtonT.default, ButtonT.xs)),
            Button("Eliminar", type="button", hx_post=f"{BASE}/orientacion/servicios/{s['id']}/eliminar", hx_swap="none",
                   hx_confirm="¿Eliminar este servicio?", cls=(ButtonT.ghost, ButtonT.xs)) if not nuevo else "",
            cls="flex items-center gap-3 mt-1"),
        method="post", action=f"{BASE}/orientacion/servicios" + ("" if nuevo else f"/{s['id']}"),
        cls="py-3" + ("" if nuevo else " border-b border-border"))


def _hecho(sess, errores, ok):
    add_toast(sess, errores[0] if errores else ok, "error" if errores else "success")
    return Redirect(f"{BASE}/orientacion")


@rt(f"{BASE}/orientacion/preguntas")
async def post(auth, sess, req):
    if not ori.puede_gestionar(auth):
        return _no()
    return _hecho(sess, ori.guardar_pregunta(dict(await req.form()), auth["id"]), "Pregunta agregada.")


@rt(f"{BASE}/orientacion/preguntas/{{pid}}")
async def post(auth, sess, pid: int, req):
    if not ori.puede_gestionar(auth):
        return _no()
    d = dict(await req.form())
    d.setdefault("publicada", "0")
    return _hecho(sess, ori.guardar_pregunta(d, auth["id"], pid), "Guardado.")


@rt(f"{BASE}/orientacion/preguntas/{{pid}}/eliminar")
def post(auth, sess, pid: int):
    if not ori.puede_gestionar(auth):
        return _no()
    ori.eliminar_pregunta(pid, auth["id"])
    return _hecho(sess, [], "Pregunta eliminada.")


@rt(f"{BASE}/orientacion/servicios")
async def post(auth, sess, req):
    if not ori.puede_gestionar(auth):
        return _no()
    return _hecho(sess, ori.guardar_servicio(dict(await req.form()), auth["id"]), "Servicio agregado.")


@rt(f"{BASE}/orientacion/servicios/{{sid}}")
async def post(auth, sess, sid: int, req):
    if not ori.puede_gestionar(auth):
        return _no()
    d = dict(await req.form())
    d.setdefault("activo", "0")
    return _hecho(sess, ori.guardar_servicio(d, auth["id"], sid), "Guardado.")


@rt(f"{BASE}/orientacion/servicios/{{sid}}/eliminar")
def post(auth, sess, sid: int):
    if not ori.puede_gestionar(auth):
        return _no()
    ori.eliminar_servicio(sid, auth["id"])
    return _hecho(sess, [], "Servicio eliminado.")
