"""Directorio de egresados y mentoría (PLAN §50). Lo ven los estudiantes y egresados con cuenta (en `/estudiante/…`) y el personal que
gestiona egresados (en `/docencia/egresados/directorio`). El egresado edita su perfil y responde las solicitudes desde su cuenta."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, FormLabel, LabelCheckboxX, LabelInput, TextPresets, UkIcon

from app.academico.componentes import pestanas
from app.comun import estudiantes, permisos, vinculos
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.egresados import directorio

rt = APIRouter()
BASE = "/estudiante"
STAFF = "/docencia/egresados/directorio"
TONOS = {"pendiente": "ambar", "aceptada": "verde", "rechazada": "gris"}


def _gestiona(auth) -> bool:
    return permisos.puede(auth, "gestionar_egresados", vinculos.carrera())


def _cuenta(auth):
    """Ficha de la cuenta de estudiante o egresado que ya aceptó el uso de sus datos; si no, (None, respuesta)."""
    externo = estudiantes.cuenta_de(auth["id"])
    if externo is None:
        return None, Response("Esta cuenta no es de estudiante ni de egresado.", status_code=403)
    if not estudiantes.consintio(externo):
        return None, Redirect(BASE)
    return externo, None


def _tarjeta(p, solicita: bool):
    return Card(
        Div(Div(Span(f"{p['nombres']} {p['apellidos']}", cls="font-medium"),
                Span(f" · titulado(a) en {p['fecha_titulacion'][:4]}", cls=TextPresets.muted_sm)),
            Button(UkIcon("send", height=14, width=14), "Pedir ayuda", cls=(ButtonT.primary, ButtonT.sm),
                   hx_get=f"{BASE}/directorio/{p['externo_id']}/solicitar", hx_target=f"#{ID_MODAL}") if solicita else "",
            cls="flex flex-wrap items-center justify-between gap-2"),
        P(" · ".join(x for x in (p["ocupacion"], p["institucion"], p["ciudad_pais"]) if x), cls="text-sm"),
        P(Span("Áreas: ", cls="font-medium"), p["areas"], cls="text-sm") if p["areas"] else "",
        Div(*[insignia(directorio.OFRECE[o], "azul") for o in p["ofrece"]], cls="flex flex-wrap gap-1") if p["ofrece"] else "",
        P(p["detalle"], cls=(TextPresets.muted_sm, "whitespace-pre-line")) if p["detalle"] else "", cls="space-y-1")


def _filtros(q, ofrece, destino):
    return fh.Form(fh.Input(type="search", name="q", value=q, placeholder="Buscar por nombre, ocupación, institución o área…",
                            cls="uk-input max-w-sm", aria_label="Buscar"),
                   Select(Option("Cualquier apoyo", value=""), *[Option(t, value=k, selected=k == ofrece) for k, t in directorio.OFRECE.items()],
                          name="ofrece", cls="uk-select w-64", aria_label="Apoyo que ofrece"),
                   Button("Buscar", type="submit", cls=(ButtonT.default, ButtonT.sm)), method="get", action=destino,
                   cls="flex flex-wrap gap-3 mb-4")


# --- Para estudiantes y egresados con cuenta ---------------------------------------------------------------------------

@rt(f"{BASE}/directorio")
def get(auth, q: str = "", ofrece: str = ""):
    externo, error = _cuenta(auth)
    if error:
        return error
    estudiante = not estudiantes.es_egresado(externo)
    enviadas = directorio.enviadas(externo)
    lista = [p for p in directorio.visibles(q, ofrece) if p["externo_id"] != externo]
    return pagina(
        "Directorio de egresados",
        A(UkIcon("arrow-left", height=14, width=14), "Mi seguimiento", href=BASE, cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2("Directorio de egresados"),
        P("Egresados de la Carrera que aceptaron figurar aquí y ofrecen apoyo: charlas, mentoría, pasantías, orientación sobre posgrados u "
          "ofertas de empleo. Solo lo ven estudiantes y personal de la Carrera. Su correo se comparte con la persona solo si acepta su pedido.",
          cls=(TextPresets.muted_sm, "max-w-3xl mb-4")),
        _filtros(q, ofrece, f"{BASE}/directorio"),
        Div(*[_tarjeta(p, estudiante) for p in lista], cls="grid grid-cols-1 lg:grid-cols-2 gap-4") if lista
        else P("No hay egresados en el directorio que coincidan.", cls=(TextPresets.muted_sm, "py-6")),
        Card(H3("Mis solicitudes", cls="text-base font-semibold mb-2"),
             Ul(*[Li(Div(Span(f"{s['nombres']} {s['apellidos']}", cls="font-medium"), insignia(s["estado"].capitalize(), TONOS[s["estado"]]),
                         Span(f" · {directorio.TIPOS_SOLICITUD[s['tipo']]}", cls=TextPresets.muted_sm), cls="flex flex-wrap items-center gap-2"),
                     P(f"Puede escribirle a {s['correo_egresado']}.", cls="text-sm") if s["estado"] == "aceptada" else "", cls="py-2")
                 for s in enviadas], cls="divide-y divide-border"), cls="mt-8") if estudiante and enviadas else "",
        usuario=auth, seccion="estudiante")


def _form_solicitud(a_externo, d=None, errores=()):
    d = d or {}
    return modal(
        "Pedir ayuda a un egresado",
        Form(mensaje_error(*errores),
             P("Cuéntele qué necesita. Su correo se le compartirá solo si acepta.", cls=TextPresets.muted_sm),
             Div(FormLabel("¿Qué necesita?"), Select(Option("— Elija —", value=""), *[Option(t, value=k, selected=k == d.get("tipo"))
                                                                                    for k, t in directorio.TIPOS_SOLICITUD.items()],
                                                    name="tipo", cls="uk-select", required=True), cls="space-y-1"),
             Div(FormLabel("Mensaje"), fh.Textarea(d.get("mensaje") or "", name="mensaje", rows="4", maxlength="1000", cls="uk-textarea",
                                                   required=True), cls="space-y-1"),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Enviar solicitud", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/directorio/{a_externo}/solicitar", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt(f"{BASE}/directorio/{{a_externo}}/solicitar")
def get(auth, a_externo: int):
    externo, error = _cuenta(auth)
    return error or _form_solicitud(a_externo)


@rt(f"{BASE}/directorio/{{a_externo}}/solicitar")
def post(auth, sess, a_externo: int, tipo: str = "", mensaje: str = ""):
    externo, error = _cuenta(auth)
    if error:
        return error
    errores = directorio.solicitar(externo, a_externo, tipo, mensaje)
    if errores:
        return _form_solicitud(a_externo, dict(tipo=tipo, mensaje=mensaje), errores)
    add_toast(sess, "Solicitud enviada. Le avisaremos cuando responda.", "success")
    return Redirect(f"{BASE}/directorio")


# --- Perfil del egresado y solicitudes recibidas ------------------------------------------------------------------

def _form_perfil(externo, d, errores=()):
    seleccion = set(d.get("ofrece") or [])
    return Form(
        mensaje_error(*errores),
        LabelInput("¿A qué se dedica hoy?", id="ocupacion", value=d.get("ocupacion") or "", maxlength="300",
                   placeholder="Docente de matemática, analista de datos…"),
        Div(LabelInput("Institución o empresa", id="institucion", value=d.get("institucion") or "", maxlength="300"),
            LabelInput("Ciudad y país", id="ciudad_pais", value=d.get("ciudad_pais") or "", maxlength="300"), cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
        LabelInput("Áreas de trabajo o interés", id="areas", value=d.get("areas") or "", maxlength="300",
                   placeholder="Estadística, criptografía, educación…"),
        Div(FormLabel("¿Qué puede ofrecer a los estudiantes?"),
            *[LabelCheckboxX(t, id=f"ofrece-{k}", name="ofrece", value=k, checked=k in seleccion) for k, t in directorio.OFRECE.items()],
            cls="space-y-1"),
        Div(FormLabel("Detalle (opcional)"), fh.Textarea(d.get("detalle") or "", name="detalle", rows="3", maxlength="1000", cls="uk-textarea"),
            cls="space-y-1"),
        Div(LabelCheckboxX("Quiero figurar en el directorio de egresados", id="visible", checked=bool(d.get("visible"))),
            LabelCheckboxX("Acepto que estos datos los vean los estudiantes y el personal de la Carrera dentro del sistema (mi correo solo "
                           "se comparte con quien yo acepte ayudar)", id="acepto", checked=bool(d.get("consentimiento_en"))), cls="space-y-1"),
        Button("Guardar mi perfil", type="submit", cls=ButtonT.primary), method="post", action=f"{BASE}/perfil-egresado", cls="space-y-4")


def _solicitud_recibida(s):
    return Li(
        Div(Div(Span(f"{s['nombres']} {s['apellidos']}", cls="font-medium"), insignia(s["estado"].capitalize(), TONOS[s["estado"]]),
                Span(f" · {directorio.TIPOS_SOLICITUD[s['tipo']]}", cls=TextPresets.muted_sm), cls="flex flex-wrap items-center gap-2"),
            P(s["mensaje"], cls="text-sm whitespace-pre-line"),
            P(f"Puede escribirle a {s['email']}.", cls="text-sm") if s["estado"] == "aceptada" else "", cls="space-y-1 min-w-0"),
        Div(Form(Button("Aceptar", type="submit", cls=(ButtonT.primary, ButtonT.sm)), hx_post=f"{BASE}/solicitudes/{s['id']}/aceptar", hx_swap="none"),
            Form(Button("No puedo", type="submit", cls=(ButtonT.default, ButtonT.sm)), hx_post=f"{BASE}/solicitudes/{s['id']}/rechazar",
                 hx_swap="none"), cls="flex gap-2 shrink-0") if s["estado"] == "pendiente" else "",
        cls="flex items-start justify-between gap-3 py-3")


@rt(f"{BASE}/perfil-egresado")
def get(auth):
    externo, error = _cuenta(auth)
    if error:
        return error
    if not estudiantes.es_egresado(externo):
        return Response("Solo los egresados titulados tienen perfil.", status_code=403)
    p = directorio.perfil(externo) or {}
    recibidas = directorio.recibidas(externo)
    return pagina(
        "Mi perfil de egresado",
        A(UkIcon("arrow-left", height=14, width=14), "Mi seguimiento", href=BASE, cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2("Mi perfil de egresado"),
        P("Figurar en el directorio es opcional. Puede cambiar de opinión cuando quiera: al desmarcar «Quiero figurar», deja de verse.",
          cls=(TextPresets.muted_sm, "max-w-3xl mb-6")),
        Div(Card(_form_perfil(externo, p)),
            Card(H3(f"Solicitudes de estudiantes ({len(recibidas)})", cls="text-base font-semibold mb-2"),
                 Ul(*[_solicitud_recibida(s) for s in recibidas], cls="divide-y divide-border") if recibidas
                 else P("Todavía nadie le pidió ayuda.", cls=TextPresets.muted_sm)),
            cls="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"),
        usuario=auth, seccion="estudiante")


@rt(f"{BASE}/perfil-egresado")
async def post(auth, req, sess):
    externo, error = _cuenta(auth)
    if error:
        return error
    f = await req.form()
    d = {k: str(f.get(k) or "") for k in ("ocupacion", "institucion", "ciudad_pais", "areas", "detalle", "visible", "acepto")}
    d["ofrece"] = [str(x) for x in f.getlist("ofrece")]
    errores = directorio.guardar_perfil(externo, d)
    if errores:
        return pagina("Mi perfil de egresado", H2("Mi perfil de egresado"), Card(_form_perfil(externo, d, errores)), usuario=auth, seccion="estudiante")
    add_toast(sess, "Perfil guardado.", "success")
    return Redirect(f"{BASE}/perfil-egresado")


def _responder(auth, sess, sid, aceptar):
    externo, error = _cuenta(auth)
    if error:
        return error
    ok = directorio.responder(sid, externo, aceptar)
    add_toast(sess, ("Aceptó la solicitud: el estudiante recibirá su correo." if aceptar else "Respondió que no puede ayudar.") if ok
              else "Esa solicitud ya no está pendiente.", "success" if ok else "error")
    return Redirect(f"{BASE}/perfil-egresado")


@rt(f"{BASE}/solicitudes/{{sid}}/aceptar")
def post(auth, sess, sid: int):
    return _responder(auth, sess, sid, True)


@rt(f"{BASE}/solicitudes/{{sid}}/rechazar")
def post(auth, sess, sid: int):
    return _responder(auth, sess, sid, False)


# --- Para el personal ----------------------------------------------------------------------------------------------

@rt(STAFF)
def get(auth, q: str = "", ofrece: str = ""):
    if not _gestiona(auth):
        return Response("No autorizado", status_code=403)
    ind = directorio.indicadores()
    lista = directorio.visibles(q, ofrece)
    return pagina(
        "Directorio de egresados", pestanas("egresados", auth),
        A(UkIcon("arrow-left", height=14, width=14), "Egresados", href="/docencia/egresados", cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2("Directorio de egresados"),
        P(f"{ind['visibles']} egresado(s) figuran de {ind['invitados']} invitado(s) · {ind['solicitudes']} solicitud(es) de estudiantes, "
          f"{ind['aceptadas']} aceptada(s).", cls=(TextPresets.muted_sm, "mb-4")),
        _filtros(q, ofrece, STAFF),
        Div(*[_tarjeta(p, False) for p in lista], cls="grid grid-cols-1 lg:grid-cols-2 gap-4") if lista
        else P("Aún no hay egresados en el directorio.", cls=(TextPresets.muted_sm, "py-6")), usuario=auth, seccion="docencia")


@rt(f"{STAFF}/invitar/{{externo_id}}")
def post(auth, sess, externo_id: int):
    if not _gestiona(auth):
        return Response("No autorizado", status_code=403)
    errores = directorio.invitar(externo_id, auth["id"])
    add_toast(sess, errores[0] if errores else "Invitación enviada.", "error" if errores else "success")
    return Redirect("/docencia/egresados")


@rt(f"{STAFF}/invitar-pendientes")
def post(auth, sess):
    if not _gestiona(auth):
        return Response("No autorizado", status_code=403)
    r = directorio.invitar_pendientes(auth["id"])
    texto = f"{r['invitados']} invitación(es) enviada(s)." if r["invitados"] else "No había egresados por invitar."
    if r["con_problemas"]:
        texto += f" {r['con_problemas']} con problemas (correo faltante o en uso)."
    add_toast(sess, texto, "success" if r["invitados"] else "info")
    return Redirect("/docencia/egresados")
