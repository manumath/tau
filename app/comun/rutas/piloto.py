"""Piloto con usuarios reales (PLAN §72, etapa 9): «Comentar esta pantalla» para toda cuenta y, para la Administración del
sistema, la lista de comentarios y la adopción por rol y semana (`/admin/piloto`, regla en `auth.REGLAS_ADMIN`)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Li, P, Redirect, Response, Span, Table, Tbody, Td, Th, Thead, Tr, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, TextPresets

from app.comun import config, formato, permisos, piloto
from app.comun.componentes.layout import ID_MODAL, cerrar_modal, campo, mensaje_error, modal, pagina
from app.comun.db import auditar

rt = APIRouter()
ADMIN = "/admin/piloto"


def _form(ruta, texto="", errores=()):
    return modal(
        "Comentar esta pantalla",
        Form(mensaje_error(*errores),
             P("Cuéntenos qué le costó, qué no entendió o qué le faltó en esta pantalla. Se guarda su comentario con la "
               "pantalla y su rol, sin su nombre.", cls="text-sm"),
             P(f"Pantalla: {ruta}", cls=TextPresets.muted_sm),
             Input(type="hidden", name="ruta", value=ruta),
             campo("Comentario", fh.Textarea(texto, name="texto", rows=5, required=True, minlength="3",
                                             maxlength=str(piloto.MAX_TEXTO), cls="uk-textarea")),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Enviar comentario", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post="/piloto/comentar", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt("/piloto/comentar")
def get(auth, req):
    if not config.PILOTO:
        return Response("El piloto no está activo.", status_code=404)
    piloto.roles_de(auth["id"])                    # la cuenta de la sesión; nada de la dirección
    return _form(piloto.ruta_sin_parametros(req.headers.get("HX-Current-URL", "")))


@rt("/piloto/comentar")
def post(auth, sess, ruta: str = "", texto: str = ""):
    if not config.PILOTO:
        return Response("El piloto no está activo.", status_code=404)
    errores = piloto.comentar(auth["id"], ruta, texto)
    if errores:
        return _form(piloto.ruta_sin_parametros(ruta), texto, errores)
    add_toast(sess, "Gracias: su comentario llegó al equipo del sistema.", "success")
    return cerrar_modal()


# --- Administración -----------------------------------------------------------------------------------------------------

def _puede(auth):
    return permisos.puede(auth, "ver_auditoria")


def _comentario(c, atendido):
    return Li(
        Div(Div(Span(c["ruta"], cls="font-mono text-sm"), Span(f" · {c['rol']} · {formato.fecha(c['dia'])}",
                                                                cls=TextPresets.muted_sm), cls="min-w-0"),
            Form(Button("Reabrir", type="submit", cls=(ButtonT.ghost, ButtonT.xs)), hx_post=f"{ADMIN}/{c['id']}/reabrir",
                 hx_target="body") if atendido else "",
            cls="flex flex-wrap items-start justify-between gap-2"),
        P(c["texto"], cls="text-sm whitespace-pre-line mt-1"),
        P(f"Atendido el {formato.fecha(c['atendido_en'][:10])}" + (f": {c['nota']}" if c["nota"] else "."),
          cls=TextPresets.muted_sm) if atendido else
        Form(Div(Input(name="nota", maxlength="1000", placeholder="Qué se hizo (opcional)", cls="uk-input uk-form-small",
                       aria_label="Qué se hizo"),
                 Button("Marcar atendido", type="submit", cls=(ButtonT.default, ButtonT.sm)), cls="flex gap-2 mt-2"),
             hx_post=f"{ADMIN}/{c['id']}/atendido", hx_target="body"),
        cls="py-3")


def _adopcion(a):
    semanas = a["semanas"]
    if not a["filas"]:
        return P("Aún no hay actividad registrada en estas semanas.", cls=TextPresets.muted_sm)
    return Div(Table(
        Thead(Tr(Th("Rol"), *[Th(formato.fecha(s), cls="text-right whitespace-nowrap") for s in semanas])),
        Tbody(*[Tr(Td(f["rol"]), *[Td(f"{e} / {r}", cls="text-right tabular-nums") for e, r in zip(f["entraron"], f["registraron"])])
                for f in a["filas"]]),
        cls="uk-table uk-table-divider uk-table-small text-sm", aria_label="Adopción por rol y semana"),
        cls="overflow-x-auto")


@rt(ADMIN)
def get(auth, ver: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    atendidos = ver == "atendidos"
    lista = piloto.comentarios(pendientes=not atendidos)
    n = piloto.conteo()
    return pagina(
        "Piloto y adopción",
        H2("Piloto y adopción"),
        P("Comentarios que dejan los usuarios con «Comentar esta pantalla» (con TAU_PILOTO=1) y uso del sistema por rol, "
          "sacado de la auditoría. No se guarda quién comentó.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        P("El piloto no está activo en este servidor: los usuarios no ven el enlace para comentar.",
          cls="text-sm mb-4") if not config.PILOTO else "",
        Card(H3("Adopción por rol y semana", cls="text-base font-semibold mb-1"),
             P("En cada semana (desde el lunes indicado): personas que entraron / personas que registraron algo. Quien tiene "
               "dos roles cuenta en ambos.", cls=(TextPresets.muted_sm, "mb-2")),
             _adopcion(piloto.adopcion()), cls="mb-6"),
        Card(Div(H3(f"Comentarios {'atendidos' if atendidos else 'por atender'}", cls="text-base font-semibold"),
                 A(f"Ver por atender ({n['pendientes']})" if atendidos else f"Ver atendidos ({n['atendidos']})",
                   href=ADMIN if atendidos else f"{ADMIN}?ver=atendidos", cls="text-sm text-primary hover:underline"),
                 cls="flex flex-wrap items-center justify-between gap-2 mb-1"),
             Ul(*[_comentario(c, atendidos) for c in lista], cls="divide-y divide-border") if lista else
             P("No hay comentarios.", cls=TextPresets.muted_sm)),
        usuario=auth)


@rt(f"{ADMIN}/{{cid}}/atendido")
def post(auth, sess, cid: int, nota: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    if not piloto.atender(cid, auth["id"], nota):
        return Response("No encontrado", status_code=404)
    auditar(auth["id"], "atender_comentario_piloto", "comentario_piloto", cid, nota[:200])
    add_toast(sess, "Comentario marcado como atendido.", "success")
    return Redirect(ADMIN)


@rt(f"{ADMIN}/{{cid}}/reabrir")
def post(auth, sess, cid: int):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    if not piloto.reabrir(cid):
        return Response("No encontrado", status_code=404)
    auditar(auth["id"], "reabrir_comentario_piloto", "comentario_piloto", cid, "")
    return Redirect(f"{ADMIN}?ver=atendidos")
