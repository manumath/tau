"""Pestañas «Actividades» y «Productos»: lo aprobado en el proyecto."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Option, P, Response, Select, Span
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Card, TextPresets, UkIcon

from app.investigacion import actividades, filiacion, productos, proyectos
from app.comun.componentes.layout import ID_MODAL
from app.comun.componentes.registros import insignia
from app.comun.db import auditar
from app.investigacion.rutas.proyectos.base import ID_TAB, _proyecto_o_error
from app.investigacion.rutas.proyectos.pendientes import _requisitos, _selector_agradece

rt = APIRouter()


# --- Pestañas: actividades y productos aprobados ---------------------------------------------------------------

def _boton_registrar(p, auth, tipo):
    if not proyectos.rol_de(p["id"], auth["id"]) or p["estado"] == "finalizado":
        return ""
    ruta = "/actividades/nueva" if tipo == "actividad" else "/productos/nuevo"
    texto = "Registrar actividad del proyecto" if tipo == "actividad" else "Registrar producto del proyecto"
    return Button(UkIcon("plus", height=14, width=14), texto, cls=(ButtonT.default, ButtonT.sm),
                  hx_get=f"{ruta}?proyecto={p['id']}", hx_target=f"#{ID_MODAL}")


def _desvincular(p, tipo, rid, gestiona):
    if not gestiona:
        return ""
    return fh.Button(UkIcon("unlink", height=14, width=14), type="button", title="Desvincular del proyecto",
                     aria_label="Desvincular del proyecto",
                     cls="p-1 rounded hover:bg-muted hover:text-destructive",
                     hx_post=f"/proyectos/{p['id']}/{tipo}/{rid}/desvincular", hx_target=f"#{ID_TAB}",
                     hx_confirm="¿Desvincular del proyecto? El registro sigue en el perfil de sus autores.")


def _escuchar(pid, tab, evento):
    """Recarga la pestaña si se registra algo desde el modal (p. ej. «Registrar … del proyecto»)."""
    return Div(hx_get=f"/proyectos/{pid}/tab/{tab}", hx_trigger=f"{evento} from:body",
               hx_target=f"#{ID_TAB}", cls="hidden")


def tab_actividades(p, auth):
    pid = p["id"]
    gestiona = proyectos.puede_gestionar(pid, auth)
    vigentes = proyectos.participantes(pid, solo_vigentes=True)
    filas = []
    for v in proyectos.registros(pid, "actividad"):
        a = actividades.obtener(v["registro_id"])
        if gestiona:
            responsable = Select(Option("— Sin responsable —", value=""),
                                 *[Option(f"{x['nombres']} {x['apellidos']}", value=str(x["participante_id"]),
                                          selected=x["participante_id"] == v["responsable_participante_id"])
                                   for x in vigentes],
                                 name="responsable", cls="uk-select h-8 text-sm w-56",
                                 aria_label="Responsable de la actividad",
                                 hx_post=f"/proyectos/{pid}/actividad/{a['id']}/responsable",
                                 hx_trigger="change", hx_target=f"#{ID_TAB}")
        else:
            r = next((x for x in proyectos.participantes(pid)
                      if x["participante_id"] == v["responsable_participante_id"]), None)
            responsable = Span(f"Responsable: {r['nombres']} {r['apellidos']}" if r else "",
                               cls=TextPresets.muted_sm)
        filas.append(Div(
            Div(actividades.fechas_texto(a), cls="text-sm text-muted-foreground w-28 shrink-0"),
            Div(A(a["titulo"], href=f"/actividades/{a['id']}", cls="block font-medium hover:underline"),
                Div(insignia(a["tipo"]), insignia(actividades.AMBITOS[a["ambito"]], "azul"),
                    insignia("editada después de aprobada", "ambar", icono="pencil") if v["editado_despues"] else "",
                    cls="flex flex-wrap gap-1.5"),
                cls="flex-1 min-w-0 space-y-1"),
            responsable, _desvincular(p, "actividad", a["id"], gestiona),
            cls="flex flex-wrap items-center gap-3 py-3"))
    return Card(_escuchar(pid, "actividades", "actividades-cambiadas"),
                Div(P(f"{len(filas)} actividad{'es' if len(filas) != 1 else ''} aprobada"
                      f"{'s' if len(filas) != 1 else ''}", cls=TextPresets.muted_sm),
                    _boton_registrar(p, auth, "actividad"), cls="flex justify-between items-center mb-2"),
                Div(*filas, cls="divide-y divide-border") if filas
                else P("Aún no hay actividades aprobadas.", cls=(TextPresets.muted_sm, "py-4")))


def tab_productos(p, auth):
    pid = p["id"]
    gestiona = proyectos.puede_gestionar(pid, auth)
    from app.investigacion.rutas.productos.lista import insignias as insignias_producto
    filas, n_informe = [], 0
    for v in proyectos.registros(pid, "producto"):
        x = productos.obtener(v["registro_id"])
        n_informe += productos.cuenta_para_informe(x)
        filas.append(Div(
            Div(str(x["anio"]), cls="font-mono text-sm text-muted-foreground w-12 shrink-0"),
            Div(A(x["titulo"], href=f"/productos/{x['id']}", cls="block font-medium hover:underline"),
                P(", ".join(f"{a['nombres']} {a['apellidos']}" for a in x["autores"]), cls="text-sm"),
                Div(insignias_producto(x),
                    insignia("editado después de aprobado", "ambar", icono="pencil") if v["editado_despues"] else "",
                    cls="flex flex-wrap gap-1.5"),
                Div(*_requisitos(x, v),
                    _selector_agradece(v["agradece"], hx_post=f"/proyectos/{pid}/producto/{x['id']}/agradece",
                                       hx_trigger="change", hx_target=f"#{ID_TAB}") if gestiona else "",
                    cls="flex flex-wrap items-center gap-1.5"),
                cls="flex-1 min-w-0 space-y-1"),
            _desvincular(p, "producto", x["id"], gestiona),
            cls="flex items-start gap-3 py-3"))
    return Card(_escuchar(pid, "productos", "productos-cambiados"),
                Div(P(f"{len(filas)} producto{'s' if len(filas) != 1 else ''} aprobado"
                      f"{'s' if len(filas) != 1 else ''} · {n_informe} para el informe",
                      cls=TextPresets.muted_sm),
                    _boton_registrar(p, auth, "producto"), cls="flex justify-between items-center mb-2"),
                Div(*filas, cls="divide-y divide-border") if filas
                else P("Aún no hay productos aprobados.", cls=(TextPresets.muted_sm, "py-4")))


@rt("/proyectos/{pid}/producto/{rid}/agradece")
def post(auth, pid: int, rid: int, agradece: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if proyectos.vinculo("producto", rid, pid):
        proyectos.marcar_agradece(rid, pid, filiacion.normalizar(agradece))
        auditar(auth["id"], "marcar_agradecimiento", "producto", rid, f"proyecto {pid}: {agradece or 'sin declarar'}")
    return tab_productos(p, auth)


@rt("/proyectos/{pid}/actividad/{rid}/responsable")
def post(auth, sess, pid: int, rid: int, responsable: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    error = proyectos.asignar_responsable_actividad(rid, pid, int(responsable) if responsable.isdigit() else None)
    if error:
        add_toast(sess, error, "error")
    return tab_actividades(p, auth)


@rt("/proyectos/{pid}/{tipo}/{rid}/desvincular")
def post(auth, sess, pid: int, tipo: str, rid: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error or tipo not in proyectos.TABLAS:
        return error or Response(status_code=404)
    proyectos.desvincular(tipo, rid, pid)
    auditar(auth["id"], "desvincular", tipo, rid, f"proyecto {pid}")
    add_toast(sess, "Registro desvinculado del proyecto.", "success")
    return tab_actividades(p, auth) if tipo == "actividad" else tab_productos(p, auth)
