"""Piezas compartidas por las páginas de proyectos: pestañas, insignias, permisos y contadores."""
from datetime import date

from fasthtml.common import Response, Span

from app.investigacion import institucionales, proyectos
from app.comun import config
from app.comun.componentes.registros import insignia


PESTANAS = {"resumen": "Resumen", "participantes": "Participantes", "actividades": "Actividades",
            "productos": "Productos", "plan": "Plan", "pendientes": "Pendientes"}
ID_TAB = "tab-contenido"
EVENTO_PENDIENTES = "pendientes-cambiados"
TONO_ESTADO = {"formulacion": "ambar", "vigente": "verde", "finalizado": "gris"}


def insignia_estado(p):
    if institucionales.en_renovacion(p):
        return insignia("En renovación", "ambar", icono="refresh-cw",
                        titulo="Su continuidad está en revisión: sigue vigente hasta la decisión.")
    return insignia(proyectos.ESTADOS[p["estado"]], TONO_ESTADO[p["estado"]])


def insignia_tipo(p):
    if p["tipo"] == "institucional":
        return insignia("Institucional", "azul", icono="landmark")
    return insignia("Individual", "gris", icono="user-round")


def _proyecto_o_error(pid, auth, gestionar=False):
    """(proyecto, None) si el usuario puede verlo (o gestionarlo); (None, respuesta) si no."""
    p = proyectos.obtener(pid)
    if not p or not proyectos.puede_ver(pid, auth):
        return None, Response("No encontrado", status_code=404)
    if gestionar and not proyectos.puede_gestionar(pid, auth):
        return None, Response("No autorizado", status_code=403)
    return p, None


def _monto(p):
    if p["monto"] is None:
        return None
    return f"{config.SIMBOLOS_MONEDA.get(p['moneda'], p['moneda'])} {p['monto']:,}".replace(",", ".")


def _periodo(p):
    if not p["fecha_inicio"]:
        return None
    ini = date.fromisoformat(p["fecha_inicio"]).strftime("%m/%Y")
    fin = date.fromisoformat(p["fecha_fin"]).strftime("%m/%Y") if p["fecha_fin"] else "…"
    return f"{ini} – {fin}"


def insignia_contador(n):
    return Span(str(n) if n else "", id="badge-pendientes",
                title=f"{n} propuesta(s) por revisar" if n else None,
                cls="ml-1 rounded-full bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5"
                    if n else "hidden",
                hx_get="/proyectos/pendientes/contador", hx_swap="outerHTML",
                hx_trigger=f"every 60s, {EVENTO_PENDIENTES} from:body")


# --- Página del proyecto -----------------------------------------------------------------------------------------

def contador_pestana(pid, oob=False):
    n = proyectos.n_pendientes(pid)
    return Span(str(n) if n else "", id="contador-pestana-pendientes",
                cls="ml-1 rounded-full bg-amber-500 text-white text-[10px] font-bold px-1.5" if n else "hidden",
                hx_swap_oob="true" if oob else None)
