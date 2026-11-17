"""Administración → Módulos (PLAN §73, etapa 1): la Administración del sistema activa y apaga las funciones de esta
instalación (`gestionar_modulos`; regla en `auth.REGLAS_ADMIN`). Apagar oculta las pantallas y no borra datos."""
from fasthtml.common import APIRouter, Div, Li, P, Redirect, Response, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, TextPresets

from app.comun import formato, modulos, permisos
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import insignia

rt = APIRouter()
URL = "/admin/modulos"


def _puede(auth) -> bool:
    return permisos.puede(auth, "gestionar_modulos")


def _boton(e):
    m = e["modulo"]
    if e["activo"]:
        if e["dependen"]:   # no se puede apagar mientras otro activo lo necesite: la fila dice cuáles
            return ""
        en_curso = e["en_curso"]
        aviso = f" Ahora tiene en curso: {'; '.join(en_curso)}." if en_curso else ""
        return Form(Button("Apagar", type="submit", cls=(ButtonT.default, ButtonT.sm), aria_label=f"Apagar {m.nombre}"),
                    hx_post=f"{URL}/{m.clave}/apagar", hx_target="body",
                    hx_confirm=f"¿Apagar «{m.nombre}»?{aviso} Sus pantallas dejan de verse y no se borra ningún dato.")
    faltan = modulos.faltan_para(m.clave)
    return Form(Button("Activar", type="submit", cls=(ButtonT.primary, ButtonT.sm), aria_label=f"Activar {m.nombre}"),
                hx_post=f"{URL}/{m.clave}/activar", hx_target="body",
                **({"hx_confirm": f"Para activar «{m.nombre}» se activará también: "
                                  f"{', '.join(f.nombre for f in faltan)}. ¿Continuar?"} if faltan else {}))


def _fila(e):
    m = e["modulo"]
    requiere = [modulos.obtener(c).nombre for c in m.requiere]
    e["dependen"] = [d.nombre for d in modulos.dependientes_activos(m.clave)] if e["activo"] else []
    e["en_curso"] = modulos.en_curso(m.clave) if e["activo"] else []
    return Li(Div(Div(Span(m.nombre, cls="font-medium"),
                      insignia("Activo", "verde") if e["activo"] else insignia("Apagado"),
                      cls="flex flex-wrap items-center gap-2"),
                  P(m.descripcion, cls="text-sm"),
                  P(f"Requiere: {', '.join(requiere)}.", cls=TextPresets.muted_sm) if requiere else "",
                  P(f"No se puede apagar mientras lo usen: {', '.join(e['dependen'])}.",
                    cls=TextPresets.muted_sm) if e["dependen"] else "",
                  P(f"En curso: {'; '.join(e['en_curso'])}.", cls=TextPresets.muted_sm) if e["en_curso"] else "",
                  P(f"Último cambio: {formato.fecha_hora(e['cambiado_en'])}"
                    + (f", por {e['cambiado_por']}" if e["cambiado_por"] else "") + ".",
                    cls=TextPresets.muted_sm) if e["cambiado_en"] else "",
                  cls="min-w-0 space-y-1"),
              Div(_boton(e), cls="shrink-0"),
              cls="flex flex-wrap items-start justify-between gap-3 py-3")


@rt(URL)
def get(auth):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    estado = modulos.estado()
    activos = sum(e["activo"] for e in estado)
    return pagina(
        "Módulos",
        H2("Módulos"),
        P("Las funciones de este sistema que su unidad usa. Al activar un módulo aparecen sus pantallas para quienes "
          "tienen el permiso; al apagarlo dejan de verse, no se envían sus avisos y sus datos se conservan: si lo vuelve "
          "a activar, todo queda como estaba. Las cuentas, los roles, los vínculos, los avisos y la auditoría están "
          "siempre activos.", cls=(TextPresets.muted_sm, "mb-2 max-w-3xl")),
        P(f"{activos} de {len(estado)} módulos activos.", cls="text-sm mb-4"),
        *[Card(H3(area, cls="text-base font-semibold"),
               Ul(*[_fila(e) for e in estado if e["modulo"].area == area], cls="divide-y divide-border"), cls="mb-4")
          for area in modulos.AREAS if any(e["modulo"].area == area for e in estado)],
        usuario=auth)


def _cambiar(auth, sess, clave: str, activar: bool):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    if not modulos.obtener(clave):
        return Response("No encontrado", status_code=404)
    errores, cambiaron = modulos.cambiar(clave, activar, auth["id"])
    if errores:
        add_toast(sess, " ".join(errores), "error")
    elif cambiaron:
        add_toast(sess, f"{'Se activó' if activar else 'Se apagó'}: {', '.join(cambiaron)}.", "success")
    return Redirect(URL)


@rt(URL + "/{clave}/activar")
def post(auth, sess, clave: str):
    return _cambiar(auth, sess, clave, True)


@rt(URL + "/{clave}/apagar")
def post(auth, sess, clave: str):
    return _cambiar(auth, sess, clave, False)
