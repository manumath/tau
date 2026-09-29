"""Pestaña «Participantes»: agregar, cambiar rol, carga horaria en el proyecto, dar de baja y reincorporar."""
import json

import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, H3, Input, Li, Option, P, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Card, TextPresets, UkIcon

from app.investigacion import carga_proyectos, proyectos
from app.comun import personas, vinculos
from app.investigacion.componentes import personas as ui_personas
from app.comun.componentes.registros import enlace_persona
from app.comun.db import auditar
from app.investigacion.rutas.proyectos.base import ID_TAB, _proyecto_o_error

rt = APIRouter()


# --- Pestaña: participantes --------------------------------------------------------------------------------

def _celda_carga(p, x, gestiona):
    """Carga del participante en el proyecto: la vigente (editable por el responsable) y la anterior."""
    if not x["interno"]:
        return Span("—", cls=TextPresets.muted_sm)
    pid, part_id = p["id"], x["participante_id"]
    actual = carga_proyectos.actual(part_id)
    vig = vinculos.vigente(x["id"])
    hoy = carga_proyectos._hoy()
    act = vinculos.ACTIVIDADES[carga_proyectos.actividad(p)].lower()
    d = carga_proyectos.disponible(x["id"], p) if vig else None
    if gestiona and x["vigente"] and d and (d["contratadas"] or actual) and p["estado"] != "finalizado":
        control = Select(*[Option("Sin carga" if h == 0 else f"{h} h/mes", value=str(h),
                                  selected=h == (actual["horas"] if actual else 0))
                           for h in carga_proyectos.opciones(x["id"], p, part_id)],
                         name="horas", cls="uk-select h-8 w-32 text-sm", aria_label="Carga en el proyecto",
                         hx_post=f"/proyectos/{pid}/participantes/{part_id}/carga", hx_trigger="change",
                         hx_target=f"#{ID_TAB}")
    else:
        control = Span(f"{actual['horas']} h/mes" if actual else "Sin carga", cls="text-sm")
    notas = []
    if not vig:
        notas.append("sin vínculo vigente: figura sin carga")
    elif not d["contratadas"]:
        notas.append(f"su vínculo no tiene carga de {act}")
    elif gestiona and x["vigente"]:
        notas.append(f"{d['libres']} h/mes de {act} libres de {d['contratadas']}")
    notas += [f"antes: {h['horas']} h/mes ({h['desde']} a {h['hasta']})"
              for h in carga_proyectos.historial(part_id) if h["hasta"] and h["hasta"] < hoy]
    return Div(control, *[P(n, cls="text-xs text-muted-foreground") for n in notas])


def tab_participantes(p, auth):
    pid = p["id"]
    gestiona = proyectos.puede_gestionar(pid, auth)
    con_carga = carga_proyectos.admite(p)
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
            fh.Td(_celda_carga(p, x, gestiona)) if con_carga else "",
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
    nota = P(f"La carga en el proyecto sale de la carga de "
             f"{vinculos.ACTIVIDADES[carga_proyectos.actividad(p)].lower()} que la Dirección de Carrera registró en "
             "el vínculo de cada persona y rige mientras ese vínculo esté vigente. Se puede participar sin carga.",
             cls=(TextPresets.muted_sm, "mb-3")) if con_carga else ""
    return Card(nota,
                fh.Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Persona"), fh.Th("Rol"),
                                               fh.Th("Carga (h/mes)") if con_carga else "",
                                               fh.Th("Periodo"), fh.Th(""))),
                                fh.Tbody(*filas), cls="uk-table uk-table-divider uk-table-middle",
                                data_tabla=f"participantes-{pid}"),
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
    con_carga = carga_proyectos.admite(p)

    def accion(x):
        # En los institucionales, a los del instituto se les indica la carga antes de agregarlos.
        if con_carga and x["interno"]:
            return {"hx_get": f"/proyectos/{pid}/participantes/nuevo", "hx_vals": json.dumps({"ref": x["ref"]}),
                    "hx_target": "#resultados-miembro"}
        return {"hx_post": f"/proyectos/{pid}/participantes", "hx_vals": json.dumps({"ref": x["ref"]}),
                "hx_target": f"#{ID_TAB}"}
    opciones = [Li(fh.Button(
        Span(f"{x['nombres']} {x['apellidos']}", cls="font-medium"),
        Span(("Instituto" if x["interno"] else "Externo") + (f" · {x['afiliacion']}" if x.get("afiliacion") else ""),
             cls=TextPresets.muted_sm),
        type="button", cls="w-full text-left flex flex-col px-3 py-2 hover:bg-muted", **accion(x)))
        for x in encontradas]
    opciones.append(Li(fh.Button(
        UkIcon("user-plus", height=14, width=14), f"Registrar a «{q.strip()}» como persona externa",
        type="button", cls="w-full text-left flex items-center gap-2 px-3 py-2 text-primary hover:bg-muted",
        hx_get=f"/proyectos/{pid}/participantes/externo", hx_vals=json.dumps({"q": q.strip()}),
        hx_target="#resultados-miembro")))
    return Ul(*opciones, cls="absolute z-30 w-full mt-1 max-h-72 overflow-y-auto rounded-md border "
                             "border-border bg-background shadow-lg divide-y divide-border")


@rt("/proyectos/{pid}/participantes/nuevo")
def get(auth, pid: int, ref: str = ""):
    """Formulario para agregar a alguien del instituto con su carga en el proyecto."""
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    persona = personas.por_ref(ref)
    cols = personas.columnas(ref) if persona else {}
    if not persona or not cols.get("investigador_id"):
        return P("Persona no válida.", cls="text-sm text-red-600")
    uid = cols["investigador_id"]
    d = carga_proyectos.disponible(uid, p)
    act = vinculos.ACTIVIDADES[d["actividad"]].lower()
    ayuda = (f"Tiene {d['libres']} h/mes de {act} libres (contratadas en su vínculo: {d['contratadas']})."
             if d["vinculo"] else "No tiene un vínculo vigente: puede participar, pero sin carga horaria.")
    return fh.Form(
        P(Span(f"{persona['nombres']} {persona['apellidos']}", cls="font-medium"), cls="text-sm"),
        Div(Select(*[Option("Sin carga" if h == 0 else f"{h} h/mes", value=str(h))
                     for h in carga_proyectos.opciones(uid, p)],
                   name="carga", cls="uk-select h-9 w-40", aria_label="Carga en el proyecto"),
            Button("Agregar", type="submit", cls=(ButtonT.primary, ButtonT.sm)),
            Button("Cancelar", type="button", cls=(ButtonT.ghost, ButtonT.sm),
                   onclick="document.getElementById('resultados-miembro').innerHTML=''"),
            cls="flex flex-wrap items-center gap-2"),
        P(ayuda, cls=TextPresets.muted_sm),
        Input(type="hidden", name="ref", value=ref),
        hx_post=f"/proyectos/{pid}/participantes", hx_target=f"#{ID_TAB}",
        cls="mt-2 space-y-2 rounded-md border border-border p-3")


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
def post(auth, sess, pid: int, ref: str = "", rol: str = "co_investigador", carga: str = "0"):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if ref.startswith("e:") and rol == "co_investigador":
        rol = "colaborador"
    cols = personas.columnas(ref) if personas.parsear_ref(ref) else {}
    horas = 0
    if cols.get("investigador_id") and carga not in ("", "0"):
        horas, error = carga_proyectos.validar(cols["investigador_id"], p, carga)
        if error:
            return _con_error(sess, error, p, auth)
    error = proyectos.agregar_participante(pid, ref, rol, False)
    if not error:
        auditar(auth["id"], "agregar_participante", "proyecto", pid, ref + (f" ({horas} h/mes)" if horas else ""))
        if horas:
            nuevo = next(x for x in proyectos.participantes(pid) if x["ref"] == ref)
            error = carga_proyectos.asignar(pid, nuevo["participante_id"], horas, auth["id"])
    return _con_error(sess, error, p, auth)


@rt("/proyectos/{pid}/participantes/{part_id}/carga")
def post(auth, sess, pid: int, part_id: int, horas: str = "0"):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    error = carga_proyectos.asignar(pid, part_id, horas, auth["id"])
    if not error:
        auditar(auth["id"], "carga_participante", "proyecto", pid, f"{part_id}: {horas} h/mes")
        add_toast(sess, "Carga horaria actualizada.", "success")
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
