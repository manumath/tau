"""Equivalencias de un plan en elaboración con el plan que reemplaza (PLAN §65, etapa 5): qué asignaturas del plan
anterior quedan iguales (misma sigla), equivalentes (un grupo registrado) o sin equivalente."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Option, P, Response, Select, Span
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import equivalencias, planes
from app.comun import permisos
from app.comun.componentes.layout import CERRAR, ID_MODAL, campo, cerrar_modal, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia

rt = APIRouter()
BASE = "/docencia/planes"


def _editable(auth, pid):
    if not permisos.puede(auth, "elaborar_planes"):
        return None, Response("No autorizado", status_code=403)
    p = planes.obtener(pid)
    if not p or p["estado"] != "elaboracion":
        return None, Response("No encontrado", status_code=404)
    return p, None


def _origen(pid, origen):
    """El plan anterior elegido (o el que este reemplaza por omisión)."""
    if origen and str(origen).isdigit():
        p = planes.obtener(int(origen))
        if p and p["estado"] != "elaboracion" and p["id"] != pid:
            return p
    return equivalencias.anterior(pid)


def _etiqueta(p):
    return f"{p['programa']} · {p['nombre']} ({planes.ESTADOS[p['estado']].lower()})"


def contenido(pid, origen, oob=False):
    """Resumen, brechas y grupos de equivalencia entre `origen` y el plan `pid`."""
    if not origen:
        return Div(P("Elija el plan que este reemplaza para ver cómo queda cada una de sus asignaturas.",
                     cls=TextPresets.muted_sm), id="equivalencias", hx_swap_oob="true" if oob else None)
    b = equivalencias.brechas(origen["id"], pid)
    n = {k: sum(r["estado"] == k for r in b["filas"]) for k in ("igual", "equivalente", "sin")}
    sin_oblig = b["sin_obligatorias"]
    estado = {"igual": insignia("Igual (misma sigla)", "verde", icono="check"),
              "equivalente": insignia("Equivalente", "azul", icono="arrow-left-right"),
              "sin": insignia("Sin equivalente", "ambar", icono="circle-alert")}
    filas = [fh.Tr(fh.Td(r["fila"]["sigla"], cls="font-mono text-sm whitespace-nowrap"),
                   fh.Td(r["fila"]["nombre"], Span(f" · {planes.TIPOS[r['fila']['tipo']]}", cls=TextPresets.muted_sm)
                         if r["fila"]["tipo"] != "obligatoria" else "", cls="text-sm"),
                   fh.Td(estado[r["estado"]]),
                   fh.Td(", ".join(r["destino"]) if r["estado"] == "equivalente" else "", cls="text-sm"))
             for r in sorted(b["filas"], key=lambda r: (r["estado"] != "sin", r["fila"]["semestre"] or 99))]
    grupos = [fh.Li(Div(Span(", ".join(a["sigla"] for a in g["origen"]), cls="font-mono text-sm"),
                        UkIcon("arrow-right", height=14, width=14), Span(", ".join(a["sigla"] for a in g["destino"]),
                                                                          cls="font-mono text-sm"),
                        Button(UkIcon("trash-2", height=14, width=14), hx_post=f"{BASE}/{pid}/equivalencias/{g['id']}/quitar",
                               hx_vals={"origen": origen["id"]}, hx_confirm="¿Quitar esta equivalencia?",
                               hx_target="#equivalencias", hx_swap="outerHTML",
                               cls=(ButtonT.ghost, ButtonT.xs, "text-destructive ml-auto"),
                               aria_label="Quitar la equivalencia"),
                        cls="flex flex-wrap items-center gap-2"),
                    P(g["nota"], cls=TextPresets.muted_sm) if g["nota"] else "", cls="py-2") for g in b["grupos"]]
    return Div(
        Div(insignia(f"{n['igual']} iguales", "verde"), insignia(f"{n['equivalente']} equivalentes", "azul"),
            insignia(f"{n['sin']} sin equivalente ({sin_oblig} obligatorias)", "ambar" if n["sin"] else "verde"),
            insignia(f"{len(b['nuevas'])} nuevas en este plan", "gris"), cls="flex flex-wrap gap-2 mb-4"),
        Card(Div(H3("Equivalencias registradas", cls="text-base font-semibold"),
                 Button(UkIcon("plus", height=14, width=14), "Agregar equivalencia",
                        hx_get=f"{BASE}/{pid}/equivalencias/nueva?origen={origen['id']}", hx_target=f"#{ID_MODAL}",
                        hx_swap="innerHTML", cls=(ButtonT.default, ButtonT.sm, "ml-auto")),
                 cls="flex items-center gap-2 mb-1"),
             P("Solo se registran las que cambian: una asignatura con la misma sigla en los dos planes ya es equivalente.",
               cls=(TextPresets.muted_sm, "mb-2")),
             fh.Ul(*grupos, cls="divide-y divide-border") if grupos else P("Todavía no hay equivalencias registradas.",
                                                                           cls="text-sm")),
        Card(H3("Asignaturas del plan anterior", cls="text-base font-semibold mb-2"),
             Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Sigla"), fh.Th("Asignatura"), fh.Th("En este plan"), fh.Th("Equivale a"))),
                          fh.Tbody(*filas), cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")),
        id="equivalencias", cls="space-y-4", hx_swap_oob="true" if oob else None)


@rt(f"{BASE}/{{pid}}/equivalencias")
def get(auth, pid: int, origen: str = ""):
    p, error = _editable(auth, pid)
    if error:
        return error
    o = _origen(pid, origen)
    opciones = equivalencias.origenes_posibles(pid)
    return pagina(
        f"Equivalencias · {p['programa']} · {p['nombre']}",
        A(UkIcon("arrow-left", height=14, width=14), "Volver al plan", href=f"{BASE}/{pid}",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2("Equivalencias con el plan anterior"),
        P(f"{p['programa']} · {p['nombre']}. Compare este plan con el que reemplaza (o con varios, si une programas: "
          "elija cada uno por separado).", cls=(TextPresets.muted_sm, "mb-4")),
        fh.Form(campo("Plan que reemplaza", Select(*[Option(_etiqueta(x), value=str(x["id"]),
                                                            selected=bool(o) and x["id"] == o["id"]) for x in opciones],
                                                   name="origen", cls="uk-select")),
                Button("Ver", type="submit", cls=(ButtonT.default, ButtonT.sm)), action=f"{BASE}/{pid}/equivalencias",
                method="get", cls="flex items-end gap-2 mb-6 max-w-xl"),
        contenido(pid, o), usuario=auth, seccion="docencia")


def _form(pid, origen, errores=(), marcadas=None):
    marcadas = marcadas or {"o": set(), "d": set()}
    b = equivalencias.brechas(origen["id"], pid)

    def caja(nombre, f):
        return fh.Label(Input(type="checkbox", name=nombre, value=str(f["asignatura_id"]),
                              checked=f["asignatura_id"] in marcadas["o" if nombre == "origen_ids" else "d"]),
                        Span(f"{f['sigla']} · {f['nombre']}", cls="text-sm"), cls="flex items-center gap-2")
    return fh.Form(
        mensaje_error(*errores),
        Input(type="hidden", name="origen", value=str(origen["id"])),
        Div(Div(H3("Del plan anterior (sin equivalente)", cls="text-sm font-semibold mb-1"),
                Div(*[caja("origen_ids", r["fila"]) for r in b["filas"] if r["estado"] == "sin"]
                    or [P("Todas tienen equivalente.", cls=TextPresets.muted_sm)],
                    cls="max-h-64 overflow-y-auto border border-border rounded-md p-2 space-y-1")),
            Div(H3("De este plan (nuevas)", cls="text-sm font-semibold mb-1"),
                Div(*[caja("destino_ids", f) for f in b["nuevas"]] or [P("No hay asignaturas nuevas.",
                                                                          cls=TextPresets.muted_sm)],
                    cls="max-h-64 overflow-y-auto border border-border rounded-md p-2 space-y-1")),
            cls="grid grid-cols-1 md:grid-cols-2 gap-3"),
        campo("Nota (opcional)", Input(name="nota", cls="uk-input"), cls="mt-3"),
        Div(Button("Guardar", type="submit", cls=ButtonT.primary),
            Button("Cancelar", type="button", cls=ButtonT.ghost, **CERRAR), cls="flex gap-2 justify-end mt-4"),
        hx_post=f"{BASE}/{pid}/equivalencias", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML",
        hx_disabled_elt="find button[type='submit']")


@rt(f"{BASE}/{{pid}}/equivalencias/nueva")
def get(auth, pid: int, origen: str = ""):
    p, error = _editable(auth, pid)
    if error:
        return error
    o = _origen(pid, origen)
    if not o:
        return Response("Elija el plan que este reemplaza.", status_code=400)
    return modal(f"Equivalencia con {o['programa']} · {o['nombre']}", _form(pid, o), ancho="max-w-3xl")


@rt(f"{BASE}/{{pid}}/equivalencias")
async def post(auth, pid: int, req):
    p, error = _editable(auth, pid)
    if error:
        return error
    f = await req.form()
    o = _origen(pid, f.get("origen", ""))
    if not o:
        return Response("Elija el plan que este reemplaza.", status_code=400)
    oi = [int(x) for x in f.getlist("origen_ids") if x.isdigit()]
    di = [int(x) for x in f.getlist("destino_ids") if x.isdigit()]
    errores = equivalencias.crear(o["id"], pid, oi, di, f.get("nota", ""), auth["id"])
    if errores:
        return modal(f"Equivalencia con {o['programa']} · {o['nombre']}",
                     _form(pid, o, errores, {"o": set(oi), "d": set(di)}), ancho="max-w-3xl")
    return cerrar_modal(), contenido(pid, o, oob=True)


@rt(f"{BASE}/{{pid}}/equivalencias/{{eid}}/quitar")
async def post(auth, pid: int, eid: int, req):
    p, error = _editable(auth, pid)
    if error:
        return error
    f = await req.form()
    if not equivalencias.eliminar(pid, eid, auth["id"]):
        return Response("No encontrado", status_code=404)
    return contenido(pid, _origen(pid, f.get("origen", "")))

