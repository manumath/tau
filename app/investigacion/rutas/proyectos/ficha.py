"""Ficha del proyecto: navegación entre pestañas y página completa."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, HtmxResponseHeaders, Li, P, Span
from monsterui.all import H2, TextPresets, UkIcon

from app.investigacion import proyectos
from app.comun.componentes.layout import ID_MODAL, pagina
from app.investigacion.rutas.proyectos.base import (ID_TAB, PESTANAS, _proyecto_o_error, contador_pestana,
                                                    insignia_estado, insignia_tipo)
from app.investigacion.rutas.proyectos.registros import tab_actividades, tab_productos
from app.investigacion.rutas.proyectos.participantes import tab_participantes
from app.investigacion.rutas.proyectos.pendientes import tab_pendientes
from app.investigacion.rutas.proyectos.plan import tab_plan
from app.investigacion.rutas.proyectos.resumen import tab_resumen

rt = APIRouter()


def _contenido_pestana(p, auth, tab):
    return {"resumen": tab_resumen, "participantes": tab_participantes, "actividades": tab_actividades,
            "productos": tab_productos, "plan": tab_plan, "pendientes": tab_pendientes}[tab](p, auth)


def _pestanas_visibles(pid, auth):
    tipo = proyectos.obtener(pid)["tipo"]
    return [t for t in PESTANAS if (t != "pendientes" or proyectos.puede_gestionar(pid, auth))
            and (t != "plan" or tipo == "institucional")]


def nav_pestanas(p, auth, activa):
    enlaces = []
    for t in _pestanas_visibles(p["id"], auth):
        enlaces.append(Li(A(PESTANAS[t], contador_pestana(p["id"]) if t == "pendientes" else "",
                            href=f"/proyectos/{p['id']}?tab={t}",
                            hx_get=f"/proyectos/{p['id']}/tab/{t}", hx_target=f"#{ID_TAB}",
                            # Marca la pestaña activa en el navegador, sin volver a pedir la barra.
                            hx_on__before_request="this.closest('ul').querySelectorAll('li')"
                                                  ".forEach(li=>li.classList.remove('uk-active'));"
                                                  "this.parentElement.classList.add('uk-active')"),
                          cls="uk-active" if t == activa else ""))
    return fh.Ul(*enlaces, cls="uk-tab mb-6")


@rt("/proyectos/{pid}/tab/{tab}")
def get(auth, pid: int, tab: str):
    p, error = _proyecto_o_error(pid, auth)
    if error:
        return error
    if tab not in _pestanas_visibles(pid, auth):
        tab = "resumen"
    return _contenido_pestana(p, auth, tab), HtmxResponseHeaders(replace_url=f"/proyectos/{pid}?tab={tab}")


@rt("/proyectos/{pid}")
def get(auth, pid: int, tab: str = "resumen"):
    p, error = _proyecto_o_error(pid, auth)
    if error:
        return pagina("No encontrado", P("El proyecto no existe o no participa en él."), usuario=auth)
    if tab not in _pestanas_visibles(pid, auth):
        tab = "resumen"
    responsables = proyectos.responsables(pid)
    return pagina(
        p["nombre"],
        A(UkIcon("arrow-left", height=14, width=14), "Proyectos", href="/proyectos",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(Div(Div(insignia_tipo(p), insignia_estado(p),
                    Span(p["codigo"] or "", cls="font-mono text-sm text-muted-foreground"),
                    cls="flex items-center gap-2"),
                Div(A(UkIcon("file-text", height=14, width=14), "Informe", href=f"/proyectos/{pid}/informe",
                      cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1"),
                    fh.Button(UkIcon("trash-2", height=14, width=14), "Eliminar", type="button",
                              cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1 text-red-600",
                              hx_delete=f"/proyectos/{pid}",
                              hx_confirm=f"¿Eliminar el proyecto «{p['nombre']}»? Se borran sus participantes, "
                                         "objetivos y contrapartes. Los productos y actividades enlazados no se "
                                         "borran: siguen en el registro de sus autores, sin este proyecto.")
                    if proyectos.puede_eliminar(p, auth) else "",
                    cls="flex items-center gap-2"),
                cls="flex items-center justify-between gap-2"),
            H2(p["nombre"], cls="mt-2"),
            Div(P("Responsable: " + ", ".join(f"{r['nombres']} {r['apellidos']}" for r in responsables)
                  if responsables else "Sin responsable vigente.", cls=TextPresets.muted_sm),
                fh.Button(UkIcon("user-cog", height=14, width=14), "Reasignar responsable", type="button",
                          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline",
                          hx_get=f"/proyectos/{pid}/responsable", hx_target=f"#{ID_MODAL}")
                if proyectos.puede_reasignar(auth) else "",
                cls="flex flex-wrap items-center gap-x-4 gap-y-1"),
            cls="mb-6"),
        nav_pestanas(p, auth, tab),
        # Las pestañas de actividades/productos se refrescan si se registra algo desde el modal.
        Div(_contenido_pestana(p, auth, tab), id=ID_TAB),
        usuario=auth, seccion="proyectos")
