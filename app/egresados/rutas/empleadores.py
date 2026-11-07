"""Registro de empleadores (PLAN §57, etapa 8): lo ven quienes ven el seguimiento estudiantil y lo mantiene quien gestiona
las encuestas."""
from fasthtml.common import APIRouter, Div, Option, P, Redirect, Response, Select, Span, Table, Tbody, Td, Th, Thead, Tr
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, Form, FormLabel, LabelInput, TextPresets, UkIcon

from app.comun import permisos, vinculos
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar
from app.egresados import empleadores

rt = APIRouter()
BASE = "/docencia/empleadores"


def _ver(auth) -> bool:
    return permisos.puede(auth, "ver_seguimiento_estudiantil", vinculos.carrera())


def _gestiona(auth) -> bool:
    return permisos.puede(auth, "gestionar_encuestas", vinculos.carrera())


def _no():
    return Response("No autorizado", status_code=403)


@rt(BASE)
def get(auth):
    if not _ver(auth):
        return _no()
    gestiona = _gestiona(auth)
    lista = empleadores.listar()
    return pagina(
        "Empleadores",
        Div(H2("Empleadores"),
            Button(UkIcon("plus", height=14, width=14), "Registrar empleador", cls=(ButtonT.primary, ButtonT.sm),
                   hx_get=f"{BASE}/nuevo", hx_target=f"#{ID_MODAL}") if gestiona else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-2"),
        P("Organizaciones donde trabajan o trabajaron los titulados de la Carrera, con la persona de contacto que responde la "
          "encuesta a empleadores (Encuestas → «Encuesta a empleadores», dirigida a «Empleadores registrados»). Solo los "
          "activos reciben encuestas.", cls=(TextPresets.muted_sm, "max-w-3xl mb-6")),
        Card(Div(Table(
            Thead(Tr(Th("Organización"), Th("Sector"), Th("Contacto"), Th("Correo"), Th("Estado"), Th(""))),
            Tbody(*[Tr(Td(m["organizacion"], cls="font-medium"), Td(empleadores.SECTORES[m["sector"]]),
                       Td(f"{m['nombres']} {m['apellidos']}", Div(m["cargo"] or "", cls=TextPresets.muted_sm)),
                       Td(m["email"], cls="text-sm"),
                       Td(insignia("Activo", "verde") if m["activo"] else insignia("Inactivo", "gris")),
                       Td(Div(Button("Editar", cls=(ButtonT.ghost, ButtonT.xs), hx_get=f"{BASE}/{m['id']}/editar",
                                     hx_target=f"#{ID_MODAL}"),
                              Button("Desactivar" if m["activo"] else "Activar", cls=(ButtonT.ghost, ButtonT.xs),
                                     hx_post=f"{BASE}/{m['id']}/activo", hx_target="body"),
                              cls="flex gap-1 justify-end") if gestiona else ""))
                    for m in lista]) if lista else
            Tbody(Tr(Td(Span("Aún no hay empleadores registrados.", cls=TextPresets.muted_sm), colspan=6,
                        cls="text-center py-6"))),
            cls="uk-table uk-table-divider uk-table-small text-sm"), cls="overflow-x-auto")),
        usuario=auth, seccion="docencia")


def _form(d, url, metodo, errores=()):
    def v(k):
        return d.get(k) or ""
    return modal(
        "Empleador",
        Form(mensaje_error(*errores),
             LabelInput("Organización", id="organizacion", value=v("organizacion"), required=True, maxlength=200),
             Div(FormLabel("Sector", fr="sector"),
                 Select(*[Option(t, value=k, selected=k == v("sector")) for k, t in empleadores.SECTORES.items()],
                        id="sector", name="sector", cls="uk-select"), cls="space-y-2"),
             Div(LabelInput("Nombres del contacto", id="nombres", value=v("nombres"), required=True, maxlength=100),
                 LabelInput("Apellidos", id="apellidos", value=v("apellidos"), required=True, maxlength=100),
                 cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
             Div(LabelInput("Correo", id="email", type="email", value=v("email"), required=True),
                 LabelInput("Cargo (opcional)", id="cargo", value=v("cargo"), maxlength=200),
                 cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             **{f"hx_{metodo}": url}, hx_target=f"#{ID_MODAL}", cls="space-y-4"))


def _datos(f):
    return {k: f.get(k, "") for k in ("nombres", "apellidos", "email", "organizacion", "cargo", "sector")}


@rt(f"{BASE}/nuevo")
def get(auth):
    return _form({"sector": "privado"}, BASE, "post") if _gestiona(auth) else _no()


@rt(BASE)
async def post(auth, sess, req):
    if not _gestiona(auth):
        return _no()
    x, errores = empleadores.validar(_datos(await req.form()))
    if errores:
        return _form(x, BASE, "post", errores)
    mid = empleadores.crear(x, auth["id"])
    auditar(auth["id"], "registrar_empleador", "empleador", mid, x["organizacion"])
    add_toast(sess, "Empleador registrado.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/{{mid}}/editar")
def get(auth, mid: int):
    m = empleadores.obtener(mid)
    if not _gestiona(auth):
        return _no()
    return _form(m, f"{BASE}/{mid}", "put") if m else Response("No encontrado", status_code=404)


@rt(f"{BASE}/{{mid}}")
async def put(auth, sess, req, mid: int):
    m = empleadores.obtener(mid)
    if not _gestiona(auth):
        return _no()
    if m is None:
        return Response("No encontrado", status_code=404)
    x, errores = empleadores.validar(_datos(await req.form()), mid)
    if errores:
        return _form(x, f"{BASE}/{mid}", "put", errores)
    empleadores.actualizar(m, x)
    auditar(auth["id"], "editar_empleador", "empleador", mid, x["organizacion"])
    add_toast(sess, "Empleador guardado.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/{{mid}}/activo")
def post(auth, sess, mid: int):
    m = empleadores.obtener(mid)
    if not _gestiona(auth):
        return _no()
    if m is None:
        return Response("No encontrado", status_code=404)
    activo = empleadores.cambiar_activo(m)
    auditar(auth["id"], "activar_empleador" if activo else "desactivar_empleador", "empleador", mid, m["organizacion"])
    add_toast(sess, "Empleador activado." if activo else "Empleador desactivado: ya no recibirá encuestas.", "success")
    return Redirect(BASE)
