"""Tablero de indicadores del marco de calidad (PLAN §57, etapa 3): cifras por año de la ventana de evidencia, con su
meta y semáforo, exportación en XLSX y cierre de los años terminados. Lo ve quien ve el marco; cierra y reabre años
la Dirección de Carrera."""
from datetime import date

from fasthtml.common import A, APIRouter, Div, Option, P, Redirect, Response, Select, Span, Table, Tbody, Td, Th, \
    Thead, Tr
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, TextPresets, UkIcon

from app.calidad import indicadores, marco
from app.calidad.rutas.informes import XLSX, _archivo, descarga
from app.comun import unidades
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import fecha_local, insignia
from app.comun.db import auditar

rt = APIRouter()
BASE = "/calidad/indicadores"
BASE_MARCO = "/calidad/marco"

TONOS = {"cumple": ("verde", "check"), "no_cumple": ("rojo", "x"), "sin_meta": ("gris", None),
         "informativo": ("azul", None)}


def _no_autorizado():
    return Response("No autorizado", status_code=403)


def numero(v) -> str:
    """Cifra con coma decimal y a lo más un decimal (dos si es menor que 10 y no entera)."""
    if v is None:
        return "—"
    v = round(v, 2 if abs(v) < 10 else 1)
    return f"{v:g}".replace(".", ",")


def cifra(x: dict, unidad: str | None = None, detalle: bool = True):
    """La cifra de una celda con su semáforo; el detalle y la base (n) en la ayuda emergente."""
    if x["valor"] is None:
        return Span("—", cls=TextPresets.muted_sm, title=x["detalle"] or "Sin dato.")
    ayuda = " · ".join(t for t in (
        x["detalle"] if detalle else "", f"n = {x['n']}" if x["n"] is not None else "",
        f"Meta: {numero(x['meta'])}" if x["meta"] is not None else "", indicadores.ORIGENES.get(x["origen"], ""),
        indicadores.ESTADOS[x["estado"]]) if t)
    texto = numero(x["valor"]) + ("%" if unidad == "%" else f" {unidad}" if unidad else "")
    tono, icono = TONOS[x["estado"]]
    return insignia(texto, tono, titulo=ayuda, icono=icono)


def _marco_visible(auth):
    m = marco.de_unidad(unidades.id_de("CMAT"))
    return m if marco.puede(auth, "ver_marco_calidad", m) else None


def _anios(m, hasta: str):
    hoy = date.today().year
    h = int(hasta) if hasta.isdigit() and 2000 <= int(hasta) <= hoy else hoy
    return indicadores.anios_de(m, h), h


def _tabla(d, anios, cerrados):
    hoy = date.today().year
    filas = []
    for c in d["criterios"]:
        filas.append(Tr(Td(Span(c["codigo"], cls="font-mono mr-2"), c["nombre"], colspan=len(anios) + 2,
                           cls="bg-muted/40 text-xs font-medium")))
        for i in c["indicadores"]:
            meta = next((mt["valor"] for mt in i["metas"] if mt["anio"] == anios[-1]), None)
            filas.append(Tr(
                Td(A(i["codigo"], href=f"{BASE_MARCO}/indicadores/{i['id']}", cls="font-mono hover:underline"),
                   cls="align-top"),
                Td(i["nombre"], Div(marco.SENTIDOS[i["sentido"]], " · ", i["unidad_medida"] or "sin unidad",
                                    f" · meta {anios[-1]}: {numero(meta)}" if meta is not None else "",
                                    cls=TextPresets.muted_sm)),
                *[Td(cifra(i["celdas"][a], i["unidad_medida"]), cls="text-right align-top whitespace-nowrap")
                  for a in anios]))
    return Div(Table(
        Thead(Tr(Th("Código", cls="w-24"), Th("Indicador"),
                 *[Th(str(a), " ", UkIcon("lock", height=12, width=12) if a in cerrados else
                      Span("(parcial)", cls="font-normal") if a == hoy else "", cls="w-28 text-right") for a in anios])),
        Tbody(*filas), cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[48rem]"),
        cls="overflow-x-auto")


def _cierres(m, anios, cerrados, gestiona):
    hoy = date.today().year
    filas = []
    for a in anios:
        c = cerrados.get(a)
        if c:
            estado = Span(UkIcon("lock", height=12, width=12), f" Cerrado el {fecha_local(c['cerrado_en'])}",
                          f" por {c['por']}" if c["por"] else "",
                          f": {c['nota']}" if c["nota"] else "")
            boton = Button("Reabrir", cls=(ButtonT.ghost, ButtonT.sm), hx_delete=f"{BASE}/cierres/{a}",
                           hx_target="body", hx_confirm=f"¿Reabrir {a}? Las cifras volverán a calcularse con los datos "
                                                        "de hoy.")
        elif a < hoy:
            estado = Span("Abierto: las cifras se recalculan con los datos de hoy.", cls=TextPresets.muted_sm)
            boton = Form(Button("Cerrar el año", type="submit", cls=(ButtonT.default, ButtonT.sm)),
                         hx_post=f"{BASE}/cierres/{a}", hx_target="body",
                         hx_confirm=f"¿Cerrar {a}? Sus cifras y metas quedarán congeladas tal como están hoy.")
        else:
            estado = Span("En curso: no se puede cerrar hasta que termine.", cls=TextPresets.muted_sm)
            boton = ""
        filas.append(Tr(Td(str(a), cls="w-16"), Td(estado), Td(boton if gestiona else "", cls="text-right")))
    return Card(H3("Cierre de los años", cls="text-base font-semibold mb-1"),
                P("Cerrar un año congela sus cifras y metas, para que lo informado no cambie si después se corrigen "
                  "los datos. Reabrirlo vuelve a calcularlas.", cls=TextPresets.muted_sm),
                Table(Tbody(*filas), cls="uk-table uk-table-divider uk-table-small text-sm"), cls="mt-6")


@rt(BASE)
def get(auth, hasta: str = ""):
    m = _marco_visible(auth)
    if m is None:
        return _no_autorizado()
    anios, h = _anios(m, hasta)
    t = indicadores.tablero(m["id"], anios[0], anios[-1])
    gestiona = marco.puede(auth, "gestionar_marco_calidad", m)
    hoy = date.today().year
    resumen = [(t["conteo"]["cumple"], "cumplen la meta", "verde"), (t["conteo"]["no_cumple"], "no la cumplen", "rojo"),
               (t["conteo"]["sin_meta"], "sin meta", "gris"), (t["conteo"]["informativo"], "informativos", "azul"),
               (t["conteo"]["sin_dato"], "sin dato", "gris")]
    return pagina(
        "Indicadores de calidad",
        Div(Div(H2("Indicadores de calidad"),
                P(m["nombre"], " · versión ", m["version"], f" · {anios[0]}–{anios[-1]}", cls=TextPresets.muted_sm)),
            Div(Form(Select(*[Option(str(a), value=str(a), selected=a == h) for a in range(hoy, hoy - 15, -1)],
                            name="hasta", aria_label="Hasta el año", cls="uk-select uk-form-small w-28"),
                     Button("Ver", type="submit", cls=(ButtonT.default, ButtonT.sm)), method="get", action=BASE,
                     cls="flex gap-2"),
                descarga("XLSX", f"{BASE}/xlsx?hasta={h}"), cls="flex flex-wrap items-center gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-4"),
        P("Cifras del año calendario; la del año en curso es parcial. Cada cifra muestra al pasar el cursor cómo se "
          "obtuvo y su base (n). El semáforo compara la cifra con la meta del mismo año; la definición de cada indicador "
          "y sus metas están en el ", A("marco de calidad", href=BASE_MARCO, cls="text-primary hover:underline"), ".",
          cls="text-sm max-w-3xl mb-4"),
        Div(*[Card(Div(str(n), cls="text-2xl font-semibold"), Div(insignia(texto, tono), cls="mt-1"),
                   cls="text-center") for n, texto, tono in resumen],
            cls="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-2"),
        P("Según la cifra más reciente de cada indicador activo.", cls=(TextPresets.muted_sm, "mb-6")),
        Div(*[Card(H3(Span(d["codigo"], cls="font-mono mr-2"), d["nombre"], cls="text-base font-semibold mb-3"),
                   _tabla(d, anios, t["cierres"]), id=f"dimension-{d['codigo']}") for d in t["arbol"]],
            cls="space-y-6"),
        _cierres(m, anios, t["cierres"], gestiona),
        usuario=auth)


@rt(f"{BASE}/xlsx")
def get(auth, hasta: str = ""):
    m = _marco_visible(auth)
    if m is None:
        return _no_autorizado()
    anios, _ = _anios(m, hasta)
    t = indicadores.tablero(m["id"], anios[0], anios[-1])
    return _archivo(indicadores.a_xlsx(m["id"], t), f"indicadores-de-calidad-{anios[0]}-{anios[-1]}.xlsx", XLSX)


def _marco_gestionable(auth):
    m = marco.de_unidad(unidades.id_de("CMAT"))
    return m if marco.puede(auth, "gestionar_marco_calidad", m) else None


@rt(f"{BASE}/cierres/{{anio}}")
def post(auth, sess, anio: int, nota: str = ""):
    m = _marco_gestionable(auth)
    if m is None:
        return _no_autorizado()
    if indicadores.cerrar(m["id"], anio, auth["id"], nota) is None:
        add_toast(sess, "Solo se cierra un año ya terminado que no esté cerrado.", "error")
    else:
        auditar(auth["id"], "cerrar_anio_calidad", "marco_calidad", m["id"], str(anio))
        add_toast(sess, f"{anio} cerrado: sus cifras quedaron congeladas.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/cierres/{{anio}}")
def delete(auth, sess, anio: int):
    m = _marco_gestionable(auth)
    if m is None:
        return _no_autorizado()
    if indicadores.reabrir(m["id"], anio):
        auditar(auth["id"], "reabrir_anio_calidad", "marco_calidad", m["id"], str(anio))
        add_toast(sess, f"{anio} reabierto.", "success")
    return Redirect(BASE)
