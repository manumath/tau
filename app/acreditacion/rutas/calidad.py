"""Tablero de calidad de datos (`ver_calidad_datos`): qué falta o no cuadra, quién lo corrige y dónde."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, P, Response, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, TextPresets, UkIcon

from app.acreditacion import calidad
from app.comun import permisos
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()


def _boton_avisar(c, auth):
    """«Avisar a N persona(s)»: en las revisiones que corrigen las personas o los responsables de proyecto."""
    n = len(c["destinatarios"])
    if not n or c["clave"] not in calidad.AVISABLES or not permisos.puede(auth, "avisar_calidad"):
        return ""
    return Div(Button(UkIcon("bell-ring", height=14, width=14), f"Avisar a {n} persona{'s' if n != 1 else ''}",
                      type="button", cls=(ButtonT.default, ButtonT.sm), hx_post=f"/informes/calidad/{c['clave']}/avisar",
                      hx_target="this", hx_swap="outerHTML",
                      hx_confirm=f"¿Avisar a {n} persona{'s' if n != 1 else ''}? Cada una recibe un aviso con sus "
                                 "registros por completar (no se repite a quien ya se avisó en los últimos "
                                 f"{calidad.DIAS_ENTRE_AVISOS} días)."),
               cls="pl-7 mt-2")


def _chequeo(c, auth):
    ok = not c["n"]
    cabecera = Div(
        UkIcon("circle-check" if ok else "circle-alert", height=18, width=18,
               cls="shrink-0 mt-0.5 " + ("text-green-600" if ok else "text-amber-600")),
        Div(Div(Span(c["titulo"], cls="font-medium"), Span(f" · {c['n']}" if c["n"] else "", cls="font-semibold tabular-nums"),
                cls="text-sm"),
            P(c["explicacion"], cls=TextPresets.muted_sm) if c["explicacion"] else "",
            Div(insignia(f"Corrige: {calidad.QUIEN[c['quien']]}", "gris"), insignia(f"Afecta: {c['afecta']}", "azul"),
                cls="flex flex-wrap gap-1 mt-1") if not ok else "",
            cls="min-w-0"),
        "" if ok else Span(UkIcon("chevron-down", height=16, width=16), Span("Ver registros", cls="text-xs"),
                           cls="ml-auto shrink-0 inline-flex items-center gap-1 text-primary"),
        cls="flex items-start gap-2")
    if ok:
        return Div(cabecera, cls="py-3")
    lista = Ul(*[Li(A(i["texto"], href=i["href"], cls="text-sm text-primary hover:underline"),
                    Span(f" · {i['detalle']}", cls=TextPresets.muted_sm) if i["detalle"] else "", cls="py-0.5")
                 for i in c["items"]],
               P(f"… y {c['n'] - len(c['items'])} más.", cls=TextPresets.muted_sm) if c["n"] > len(c["items"]) else "",
               cls="pl-7 mt-2")
    return fh.Details(fh.Summary(cabecera, cls="cursor-pointer list-none"), lista, _boton_avisar(c, auth), cls="py-3",
                      id=f"chequeo-{c['clave']}")


@rt("/informes/calidad")
def get(auth):
    if not permisos.puede(auth, "ver_calidad_datos"):
        return Response("No autorizado", status_code=403)
    chequeos = calidad.revisar()
    r = calidad.resumen(chequeos)
    grupos = {}
    for c in chequeos:
        grupos.setdefault(c["grupo"], []).append(c)
    return pagina(
        "Calidad de datos",
        Div(H2("Calidad de datos"),
            P("Lo que falta o no cuadra antes de generar la memoria, el anexo o los informes de docencia. Cada "
              "revisión dice a qué afecta y quién lo corrige; abra una para ver los registros, con enlace para "
              "corregirlos. Esta página no cambia datos; en lo que corrigen las personas o los responsables de proyecto, "
              "«Avisar» les envía un aviso con sus registros por completar.", cls=TextPresets.muted_sm),
            cls="mb-6 space-y-1"),
        Div(Card(Div(Span(str(r["con_observaciones"]), cls="text-3xl font-semibold tabular-nums"),
                     Span(f" de {r['chequeos']} revisiones con observaciones", cls="text-sm"))),
            Card(Div(Span(str(r["registros"]), cls="text-3xl font-semibold tabular-nums"),
                     Span(" registros por completar", cls="text-sm"))),
            Card(Ul(*[Li(Span(f"{calidad.QUIEN[q]}: ", cls="text-sm"), Span(str(n), cls="text-sm font-semibold"))
                      for q, n in r["por_quien"].items() if n], cls="space-y-0.5")
                 if r["registros"] else P("Todo en orden.", cls="text-sm text-green-700")),
            cls="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6"),
        *[Card(fh.H3(g, cls="text-base font-semibold mb-1"),
               Div(*[_chequeo(c, auth) for c in lista], cls="divide-y divide-border"), cls="mb-4")
          for g, lista in grupos.items()],
        usuario=auth, seccion="informes")


@rt("/informes/calidad/{clave}/avisar")
def post(auth, sess, clave: str):
    if not permisos.puede(auth, "avisar_calidad"):
        return Response("No autorizado", status_code=403)
    if clave not in calidad.AVISABLES:
        return Response("No encontrado", status_code=404)
    r = calidad.avisar(clave, auth["id"])
    auditar(auth["id"], "avisar_calidad", "calidad", None, f"{clave}: {r['avisadas']} avisada(s), "
                                                           f"{r['ya_avisadas']} ya avisada(s)")
    texto = f"Se avisó a {r['avisadas']} persona(s)." + (
        f" {r['ya_avisadas']} ya tenía(n) un aviso de esta revisión de los últimos {calidad.DIAS_ENTRE_AVISOS} días."
        if r["ya_avisadas"] else "")
    add_toast(sess, texto, "success")
    return P(UkIcon("check", height=14, width=14, cls="inline mr-1"), texto, cls="pl-7 mt-2 text-sm text-green-700")
