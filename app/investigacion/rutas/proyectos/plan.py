"""Pestaña «Plan»: actividades previstas frente a realizadas (proyectos institucionales)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, H3, Option, P, Select, Span
from fasthtml.toaster import add_toast
from monsterui.all import Card, TextPresets

from app.investigacion import institucionales, proyectos
from app.comun.componentes.registros import insignia
from app.investigacion.rutas.proyectos.base import ID_TAB, _proyecto_o_error

rt = APIRouter()


# --- Pestaña: plan de actividades (proyectos institucionales) ------------------------------------------------

TONO_PLAN = {"realizada": ("Realizada", "verde"), "pendiente": ("Pendiente", "gris"), "atrasada": ("Atrasada", "ambar")}


def tab_plan(p, auth):
    pid = p["id"]
    gestiona = proyectos.puede_gestionar(pid, auth)
    bloques = []
    for periodo in institucionales.plan(pid):
        opciones = institucionales.actividades_para_enlazar(pid, periodo["periodo"]) if gestiona else []
        filas = []
        for f in periodo["previstas"]:
            texto, tono = TONO_PLAN[f["estado"]]
            if gestiona:
                enlace = Select(Option("— Sin registrar —", value=""),
                                *[Option(f"{a['fecha_inicio']} · {a['titulo']}", value=str(a["id"]),
                                         selected=a["id"] == f["actividad_id"]) for a in opciones],
                                name="actividad_id", cls="uk-select h-8 text-sm", aria_label="Actividad realizada",
                                hx_post=f"/proyectos/{pid}/plan/{f['id']}", hx_trigger="change",
                                hx_target=f"#{ID_TAB}")
            else:
                enlace = A(f["realizada_titulo"], href=f"/actividades/{f['actividad_id']}",
                           cls="text-sm text-primary hover:underline") if f["actividad_id"] else Span("—")
            filas.append(fh.Tr(fh.Td(institucionales.mes_texto(f["mes_previsto"]), cls="whitespace-nowrap text-sm"),
                               fh.Td(f["descripcion"], cls="text-sm"), fh.Td(insignia(texto, tono)), fh.Td(enlace)))
        total = len(periodo["previstas"])
        bloques.append(Card(
            Div(H3(f"Periodo {institucionales.periodo_texto(periodo['periodo'])}", cls="text-base font-semibold"),
                Span(f"{periodo['realizadas']} de {total} realizadas", cls=TextPresets.muted_sm),
                cls="flex justify-between items-center mb-2"),
            fh.Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Mes"), fh.Th("Actividad prevista"), fh.Th("Estado"),
                                           fh.Th("Actividad registrada"))), fh.Tbody(*filas),
                            cls="uk-table uk-table-divider uk-table-middle"), cls="overflow-x-auto")
            if filas else P("La propuesta no tiene actividades previstas.", cls=TextPresets.muted_sm)))
    if not bloques:
        return Card(P("El plan aparece cuando la propuesta del proyecto es aceptada.", cls=TextPresets.muted_sm))
    ayuda = P("Para marcar una actividad prevista como realizada, elija la actividad registrada que la cumple. "
              "Deben estar aprobadas en el proyecto (pestaña Actividades).", cls=(TextPresets.muted_sm, "mb-4")) \
        if gestiona else ""
    return Div(ayuda, *bloques, cls="space-y-6")


@rt("/proyectos/{pid}/plan/{prevista_id}")
def post(auth, sess, pid: int, prevista_id: int, actividad_id: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    error = institucionales.enlazar_prevista(prevista_id, int(actividad_id) if actividad_id.isdigit() else None, auth)
    if error:
        add_toast(sess, error, "error")
    return tab_plan(p, auth)
