"""Centro de avisos: la campana de la barra, la página «Avisos» y la preferencia de correo."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, P, Redirect, Response, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, TextPresets, UkIcon

from app.comun import notificaciones, usuarios
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import fecha_local

rt = APIRouter()
ID_CAMPANA = "campana-avisos"


def _item(n, compacto=False):
    nueva = not n["leida_en"]
    return Li(A(Div(Span("", cls="mt-1.5 h-2 w-2 shrink-0 rounded-full " + ("bg-primary" if nueva else "bg-transparent")),
                    Div(Span(n["asunto"], cls="text-sm " + ("font-medium" if nueva else "")),
                        P(n["texto"], cls=TextPresets.muted_sm + (" line-clamp-2" if compacto else "")) if n["texto"] else "",
                        Span(fecha_local(n["creada_en"]), cls="text-xs text-muted-foreground"),
                        cls="min-w-0"),
                    cls="flex items-start gap-2"),
                href=f"/avisos/{n['id']}", cls="block rounded px-2 py-2 hover:bg-muted"))


def campana(uid: int):
    n = notificaciones.no_leidas(uid)
    recientes = notificaciones.recientes(uid, 8)
    return Div(
        fh.Button(UkIcon("bell", height=18, width=18),
                  Span(str(n) if n < 100 else "99+", cls="absolute -top-1 -right-1 rounded-full bg-amber-500 px-1.5 "
                                                          "text-[10px] font-bold text-white") if n else "",
                  type="button", aria_label=f"Avisos ({n} sin leer)" if n else "Avisos",
                  cls="relative inline-flex items-center rounded p-2 hover:bg-muted"),
        Div(Div(Span("Avisos", cls="text-sm font-semibold"),
                fh.Button("Marcar todo como leído", type="button", cls="text-xs text-primary hover:underline",
                          hx_post="/avisos/leidas", hx_target=f"#{ID_CAMPANA}", hx_swap="outerHTML") if n else "",
                cls="flex items-center justify-between px-2 py-1"),
            Ul(*[_item(x, compacto=True) for x in recientes], cls="max-h-96 overflow-y-auto")
            if recientes else P("No tiene avisos.", cls=(TextPresets.muted_sm, "px-2 py-3")),
            A("Ver todos los avisos y elegir cómo recibirlos", href="/avisos",
              cls="block border-t border-border px-2 py-2 text-xs text-primary hover:underline"),
            uk_dropdown="mode: click; pos: bottom-right", cls="uk-drop uk-dropdown w-80 p-1"),
        id=ID_CAMPANA)


@rt("/avisos/campana")
def get(auth):
    return campana(auth["id"])


@rt("/avisos/leidas")
def post(auth, sess, htmx: fh.HtmxHeaders = None):
    n = notificaciones.marcar_todas(auth["id"])
    if htmx and htmx.target == ID_CAMPANA:
        return campana(auth["id"])
    add_toast(sess, f"{n} aviso(s) marcado(s) como leído(s).", "success")
    return Redirect("/avisos")


@rt("/avisos/preferencia")
def post(auth, sess, frecuencia: str = ""):
    if not notificaciones.fijar_frecuencia(auth["id"], frecuencia):
        return Response("Preferencia no válida", status_code=400)
    add_toast(sess, f"Avisos: {notificaciones.FRECUENCIAS[frecuencia].lower()}.", "success")
    return Redirect("/avisos")


@rt("/avisos/{nid}")
def get(auth, nid: int):
    """Abre un aviso: lo marca como leído y lleva a donde se atiende."""
    n = notificaciones.abrir(nid, auth["id"])
    if not n:
        return Response("No encontrado", status_code=404)
    return Redirect(n["url"] or "/avisos")


@rt("/avisos")
def get(auth):
    uid = auth["id"]
    lista = notificaciones.todas(uid)
    actual = usuarios.por_id(uid)["frecuencia_avisos"]
    preferencia = Card(
        fh.H3("Cómo recibir los avisos", cls="text-base font-semibold mb-2"),
        fh.Form(*[fh.Label(fh.Input(type="radio", name="frecuencia", value=k, checked=k == actual, cls="uk-radio"),
                           Span(t, cls="text-sm"), cls="flex items-center gap-2") for k, t in notificaciones.FRECUENCIAS.items()],
                P("Siempre quedan aquí y en la campana. El resumen semanal reúne los avisos que aún no leyó.",
                  cls=TextPresets.muted_sm),
                Button("Guardar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
                method="post", action="/avisos/preferencia", cls="space-y-2"))
    return pagina(
        "Avisos",
        Div(Div(H2("Avisos"), P("Lo que el sistema le avisó: propuestas por revisar, decisiones, carga en proyectos, "
                                "plazos. Abra uno para ir a atenderlo.", cls=TextPresets.muted_sm)),
            fh.Form(Button(UkIcon("check-check", height=14, width=14), "Marcar todo como leído", type="submit",
                           cls=(ButtonT.default, ButtonT.sm)), method="post", action="/avisos/leidas")
            if notificaciones.no_leidas(uid) else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Div(Card(Ul(*[_item(n) for n in lista], cls="divide-y divide-border") if lista
                 else P("No tiene avisos.", cls=TextPresets.muted_sm), cls="lg:col-span-2 min-w-0"),
            preferencia, cls="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start"),
        usuario=auth)
