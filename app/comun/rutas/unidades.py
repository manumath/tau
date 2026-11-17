"""Administración → Unidades (PLAN §73): la sigla y el nombre de la universidad, la facultad, la carrera y el instituto
de esta instalación. Solo la Administración del sistema (`configurar_unidades`; regla en `auth.REGLAS_ADMIN`). De aquí
salen los nombres de los membretes, las páginas públicas y los correos."""
from fasthtml.common import APIRouter, Div, Input, P, Redirect, Response
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, TextPresets

from app.comun import permisos, unidades
from app.comun.componentes.layout import campo, pagina
from app.comun.db import auditar

rt = APIRouter()
URL = "/admin/unidades"


def _puede(auth) -> bool:
    return permisos.puede(auth, "configurar_unidades")


def _formulario(u):
    return Card(H3(unidades.TIPOS[u["tipo"]], cls="text-base font-semibold mb-2"),
                Form(Div(campo("Sigla", Input(name="sigla", value=u["sigla"], required=True, maxlength="20",
                                              cls="uk-input w-full"), cls="w-32"),
                         campo("Nombre", Input(name="nombre", value=u["nombre"], required=True, maxlength="200",
                                               cls="uk-input w-full"), cls="flex-1 min-w-0"),
                         cls="flex flex-wrap items-end gap-3"),
                     Div(Button("Guardar", type="submit", cls=(ButtonT.primary, ButtonT.sm)), cls="flex justify-end mt-3"),
                     hx_post=f"{URL}/{u['tipo']}", hx_target="body"), cls="mb-4")


@rt(URL)
def get(auth):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    return pagina(
        "Unidades",
        H2("Unidades"),
        P("Los nombres y las siglas de su universidad, su facultad, su carrera y su instituto. Aparecen en los membretes de "
          "los informes, en las páginas públicas, en los correos y donde se asignan los roles. Una instalación es de una "
          "carrera; si no tiene instituto, deje el que viene y no le asigne roles.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Div(*[_formulario(u) for u in unidades.todas()], cls="max-w-3xl"),
        usuario=auth)


@rt(URL + "/{tipo}")
def post(auth, sess, tipo: str, sigla: str = "", nombre: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    if tipo not in unidades.TIPOS:
        return Response("No encontrado", status_code=404)
    errores = unidades.configurar(tipo, sigla, nombre)
    if errores:
        add_toast(sess, " ".join(errores), "error")
    else:
        auditar(auth["id"], "configurar_unidad", "unidad", unidades.de_tipo(tipo), f"{tipo}: {sigla.strip()} · {nombre.strip()}")
        add_toast(sess, f"{unidades.TIPOS[tipo]} actualizada.", "success")
    return Redirect(URL)
