"""Pestaña «Participantes»: agregar, cambiar rol, dar de baja y reincorporar."""
import json

import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, H3, Input, Li, Option, P, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import Card, TextPresets, UkIcon

from app.investigacion import proyectos
from app.comun import personas
from app.investigacion.componentes import personas as ui_personas
from app.comun.componentes.registros import enlace_persona
from app.comun.db import auditar
from app.investigacion.rutas.proyectos.base import ID_TAB, _proyecto_o_error

rt = APIRouter()


# --- Pestaña: participantes --------------------------------------------------------------------------------

def tab_participantes(p, auth):
    pid = p["id"]
    gestiona = proyectos.puede_gestionar(pid, auth)
    filas = []
    for x in proyectos.participantes(pid):
        # El rol «responsable» no se asigna ni se quita aquí: lo reasigna la administración.
        roles_permitidos = {k: v for k, v in proyectos.ROLES.items()
                            if k != "responsable" and x["rol"] != "responsable"}
        if not x["interno"]:
            roles_permitidos = {k: v for k, v in roles_permitidos.items()
                                if k not in proyectos.ROLES_RESPONSABLES}
        editable_rol = gestiona and x["vigente"] and (x["rol"] in roles_permitidos)
        rol = Select(*[Option(t, value=k, selected=k == x["rol"]) for k, t in roles_permitidos.items()],
                     name="rol", cls="uk-select h-8 w-48 text-sm", aria_label="Rol",
                     hx_post=f"/proyectos/{pid}/participantes/{x['participante_id']}/rol",
                     hx_trigger="change", hx_target=f"#{ID_TAB}") if editable_rol \
            else Span(proyectos.ROLES[x["rol"]], cls="text-sm")
        accion = ""
        if gestiona and x["rol"] != "responsable":
            accion = fh.Button(
                "Dar de baja" if x["vigente"] else "Reincorporar", type="button",
                cls="text-sm text-primary hover:underline",
                hx_post=f"/proyectos/{pid}/participantes/{x['participante_id']}/"
                        f"{'baja' if x['vigente'] else 'reincorporar'}",
                hx_target=f"#{ID_TAB}",
                hx_confirm=f"¿Dar de baja a {x['nombres']} {x['apellidos']}? Sus registros ya aprobados "
                           "seguirán en el proyecto." if x["vigente"] else None)
        filas.append(fh.Tr(
            fh.Td(enlace_persona(x), Span(" · externo", cls=TextPresets.muted_sm) if not x["interno"] else "",
                  P(x["afiliacion"] or "", cls=TextPresets.muted_sm) if x.get("afiliacion") else ""),
            fh.Td(rol),
            fh.Td(Span(f"desde {x['fecha_desde'] or '—'}" + (f" · hasta {x['fecha_hasta']}" if x["fecha_hasta"] else ""),
                       cls=TextPresets.muted_sm)),
            fh.Td(accion, cls="text-right"),
            cls="" if x["vigente"] else "opacity-60"))
    agregar = Div(
        H3("Agregar participante", cls="text-base font-semibold mb-2"),
        Div(Input(type="search", id="buscar-miembro", name="q", autocomplete="off", cls="uk-input",
                  placeholder="Buscar investigador o persona externa…", aria_label="Buscar participante",
                  hx_get=f"/proyectos/{pid}/participantes/buscar", hx_target="#resultados-miembro",
                  hx_trigger="input changed delay:250ms, search"),
            Div(id="resultados-miembro"), cls="relative max-w-xl"),
        cls="mt-6") if gestiona else ""
    return Card(fh.Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Persona"), fh.Th("Rol"), fh.Th("Periodo"), fh.Th(""))),
                                fh.Tbody(*filas), cls="uk-table uk-table-divider uk-table-middle"),
                       cls="overflow-x-auto"),
                agregar)


def _con_error(sess, error, p, auth):
    if error:
        add_toast(sess, error, "error")
    return tab_participantes(p, auth)


@rt("/proyectos/{pid}/participantes/buscar")
def get(auth, pid: int, q: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if len(q.strip()) < 2:
        return ""
    ya = {x["ref"] for x in proyectos.participantes(pid)}
    encontradas = personas.buscar(q, excluir=ya)
    opciones = [Li(fh.Button(
        Span(f"{x['nombres']} {x['apellidos']}", cls="font-medium"),
        Span(("Instituto" if x["interno"] else "Externo") + (f" · {x['afiliacion']}" if x.get("afiliacion") else ""),
             cls=TextPresets.muted_sm),
        type="button", cls="w-full text-left flex flex-col px-3 py-2 hover:bg-muted",
        hx_post=f"/proyectos/{pid}/participantes", hx_vals=json.dumps({"ref": x["ref"]}),
        hx_target=f"#{ID_TAB}")) for x in encontradas]
    opciones.append(Li(fh.Button(
        UkIcon("user-plus", height=14, width=14), f"Registrar a «{q.strip()}» como persona externa",
        type="button", cls="w-full text-left flex items-center gap-2 px-3 py-2 text-primary hover:bg-muted",
        hx_get=f"/proyectos/{pid}/participantes/externo", hx_vals=json.dumps({"q": q.strip()}),
        hx_target="#resultados-miembro")))
    return Ul(*opciones, cls="absolute z-30 w-full mt-1 max-h-72 overflow-y-auto rounded-md border "
                             "border-border bg-background shadow-lg divide-y divide-border")


@rt("/proyectos/{pid}/participantes/externo")
def get(auth, pid: int, q: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    return ui_personas.form_externo("miembro", q, url=f"/proyectos/{pid}/participantes/externo",
                                    destino=f"#{ID_TAB}")


@rt("/proyectos/{pid}/participantes/externo")
def post(auth, sess, pid: int, ext_nombres: str = "", ext_apellidos: str = "", ext_institucion: str = "",
         ext_pais: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if not ext_nombres.strip() or not ext_apellidos.strip():
        return _con_error(sess, "Nombres y apellidos son obligatorios.", p, auth)
    externo = personas.externo_similar(ext_nombres, ext_apellidos) or personas.crear_externo(
        ext_nombres, ext_apellidos, ext_institucion, ext_pais, auth["id"])
    error = proyectos.agregar_participante(pid, f"e:{externo['id']}", "colaborador", False)
    return _con_error(sess, error, p, auth)


@rt("/proyectos/{pid}/participantes")
def post(auth, sess, pid: int, ref: str = "", rol: str = "co_investigador"):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if ref.startswith("e:") and rol == "co_investigador":
        rol = "colaborador"
    error = proyectos.agregar_participante(pid, ref, rol, False)
    if not error:
        auditar(auth["id"], "agregar_participante", "proyecto", pid, ref)
    return _con_error(sess, error, p, auth)


@rt("/proyectos/{pid}/participantes/{part_id}/rol")
def post(auth, sess, pid: int, part_id: int, rol: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    error = proyectos.cambiar_rol(pid, part_id, rol, False)
    if not error:
        auditar(auth["id"], "cambiar_rol", "proyecto", pid, f"{part_id}:{rol}")
    return _con_error(sess, error, p, auth)


@rt("/proyectos/{pid}/participantes/{part_id}/baja")
def post(auth, sess, pid: int, part_id: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    error = proyectos.dar_de_baja(pid, part_id, False)
    if not error:
        auditar(auth["id"], "baja_participante", "proyecto", pid, str(part_id))
    return _con_error(sess, error, p, auth)


@rt("/proyectos/{pid}/participantes/{part_id}/reincorporar")
def post(auth, sess, pid: int, part_id: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    proyectos.reincorporar(pid, part_id)
    return tab_participantes(p, auth)
