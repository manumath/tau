"""Pestaña «Resumen»: datos, propuestas institucionales, líneas, contrapartes y objetivos."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, H3, Input, Li, Option, P, Response, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Card, TextPresets, UkIcon

from app.investigacion import actividades, institucionales, lineas, productos, proyectos
from app.comun import paises
from app.investigacion.componentes.lineas import casillas_lineas, insignias_lineas
from app.comun.componentes.layout import mensaje_error
from app.comun.componentes.registros import dato
from app.investigacion.rutas import propuestas as ui_propuestas
from app.comun.db import auditar
from app.investigacion.rutas.proyectos.base import ID_TAB, _monto, _periodo, _proyecto_o_error

rt = APIRouter()


# --- Pestaña: resumen y objetivos -----------------------------------------------------------------------

def tarjeta_propuestas(p, auth):
    """Proyectos institucionales: propuestas por periodo, continuidad y aviso de término."""
    pid = p["id"]
    props = institucionales.de_proyecto(pid)
    periodo = institucionales.periodo_de_continuidad(p)
    es_responsable = proyectos.rol_de(pid, auth["id"]) == "responsable"
    siguiente = institucionales.de_proyecto_y_periodo(pid, periodo) if periodo is not None else None
    pendiente = institucionales.pendiente_de_continuidad(p)
    aviso = ""
    if pendiente is not None and proyectos.puede_gestionar(pid, auth):
        cierre = institucionales.plazo(pendiente)["cierra"]
        aviso = Div(UkIcon("alarm-clock", height=16, width=16, cls="shrink-0"),
                    Span(f"El proyecto termina el {institucionales.fecha_texto(p['fecha_fin'])}. Si no envía la "
                         f"propuesta de continuidad antes del {institucionales.fecha_texto(cierre)}, concluye en esa fecha."),
                    cls="flex gap-2 rounded-md border border-amber-300 bg-amber-50 text-amber-900 "
                        "dark:bg-amber-950 dark:text-amber-200 p-3 text-sm mb-3")
    boton = ""
    if periodo is not None and p["estado"] != "finalizado" and es_responsable:
        if siguiente:
            boton = A(UkIcon("file-pen", height=14, width=14),
                      f"Propuesta de continuidad {institucionales.periodo_texto(periodo)}",
                      href=f"/propuestas/{siguiente['id']}", cls="uk-btn uk-btn-default uk-btn-sm inline-flex gap-1")
        elif institucionales.puede_proponer(auth):
            boton = Button(UkIcon("refresh-cw", height=14, width=14),
                           f"Proponer continuidad {institucionales.periodo_texto(periodo)}",
                           cls=(ButtonT.primary, ButtonT.sm), hx_post=f"/proyectos/{pid}/continuidad")
    return Card(Div(H3("Propuestas institucionales", cls="text-base font-semibold"), boton,
                    cls="flex flex-wrap justify-between items-center gap-2 mb-2"),
                aviso,
                ui_propuestas.lista_propuestas(props) if props
                else P("Este proyecto no tiene propuestas registradas en el sistema.", cls=TextPresets.muted_sm))


def tarjeta_contrapartes(p, auth):
    pid = p["id"]
    gestiona = proyectos.puede_gestionar(pid, auth)
    filas = [Li(Div(Span(c["institucion"], cls="font-medium"), Span(f" · {c['pais'] or 'país sin indicar'}",
                                                                   cls=TextPresets.muted_sm)),
                fh.Button(UkIcon("x", height=14, width=14), type="button", aria_label="Quitar contraparte",
                          cls="p-1 rounded hover:bg-muted hover:text-red-600",
                          hx_delete=f"/proyectos/{pid}/contrapartes/{c['id']}", hx_target=f"#{ID_TAB}")
                if gestiona else "", cls="flex justify-between items-center py-1")
             for c in proyectos.contrapartes(pid)]
    agregar = fh.Form(Input(name="institucion", placeholder="Institución (p. ej., Universidad de Chile)", cls="uk-input",
                            required=True, aria_label="Institución contraparte"),
                      Input(name="pais", placeholder="País", cls="uk-input w-40", list="lista-paises", aria_label="País"),
                      fh.Datalist(*[Option(value=x) for x in paises.nombres()], id="lista-paises"),
                      Button("Agregar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
                      hx_post=f"/proyectos/{pid}/contrapartes", hx_target=f"#{ID_TAB}",
                      cls="flex flex-wrap gap-2 mt-3")
    agregar = fh.Details(fh.Summary("+ Agregar contraparte", cls="cursor-pointer text-sm font-medium text-primary mt-2"),
                         agregar) if gestiona else ""
    return Card(H3("Instituciones contraparte", cls="text-base font-semibold mb-1"),
                P("Instituciones con las que se colabora o que cofinancian (con su país): definen si el proyecto es "
                  "internacional.", cls=(TextPresets.muted_sm, "mb-2")),
                Ul(*filas, cls="divide-y divide-border") if filas else P("Sin contrapartes registradas.",
                                                                         cls=TextPresets.muted_sm),
                agregar)


def lineas_editables(p) -> bool:
    """En un proyecto institucional con propuesta aceptada, las líneas vienen de ella."""
    return p["tipo"] != "institucional" or not any(x["estado"] == "aceptada"
                                                   for x in institucionales.de_proyecto(p["id"]))


def tarjeta_lineas(p, auth, editar=False, error=None):
    pid = p["id"]
    actuales = lineas.de_proyecto(pid)
    puede = proyectos.puede_gestionar(pid, auth) and lineas_editables(p)
    if editar and puede:
        cuerpo = fh.Form(mensaje_error(error) if error else "",
                         casillas_lineas([x["id"] for x in actuales], actuales=actuales),
                         Div(Button("Cancelar", type="button", cls=ButtonT.ghost, hx_get=f"/proyectos/{pid}/lineas",
                                    hx_target="#tarjeta-lineas", hx_swap="outerHTML"),
                             Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
                         hx_put=f"/proyectos/{pid}/lineas", hx_target="#tarjeta-lineas", hx_swap="outerHTML",
                         cls="space-y-3")
    else:
        cuerpo = insignias_lineas(actuales, vacio="Sin líneas de investigación registradas.")
    ayuda = ("Vienen de la propuesta aceptada: se cambian en la propuesta de continuidad."
             if not lineas_editables(p) else "Líneas institucionales vigentes a las que se adscribe el proyecto.")
    return Card(Div(H3("Líneas de investigación", cls="text-base font-semibold"),
                    Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.ghost, ButtonT.sm),
                           hx_get=f"/proyectos/{pid}/lineas?editar=1", hx_target="#tarjeta-lineas",
                           hx_swap="outerHTML") if puede and not editar else "",
                    cls="flex justify-between items-center mb-1"),
                P(ayuda, cls=(TextPresets.muted_sm, "mb-2")), cuerpo, id="tarjeta-lineas")


@rt("/proyectos/{pid}/lineas")
def get(auth, pid: int, editar: bool = False):
    p, error = _proyecto_o_error(pid, auth)
    return error or tarjeta_lineas(p, auth, editar)


@rt("/proyectos/{pid}/lineas")
def put(auth, sess, pid: int, linea: list[str] = None):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if not lineas_editables(p):
        return Response("Las líneas de este proyecto vienen de su propuesta aceptada.", status_code=403)
    ids = lineas.ids_validos(linea)
    if (error := lineas.adscribir_proyecto(pid, ids)):
        return tarjeta_lineas(p, auth, editar=True, error=error)
    auditar(auth["id"], "lineas_proyecto", "proyecto", pid, lineas.nombres(lineas.de_proyecto(pid)))
    add_toast(sess, "Líneas de investigación guardadas.", "success")
    return tarjeta_lineas(p, auth)


@rt("/proyectos/{pid}/contrapartes")
def post(auth, sess, pid: int, institucion: str = "", pais: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if (error := proyectos.agregar_contraparte(pid, institucion, pais)):
        add_toast(sess, error, "error")
    else:
        auditar(auth["id"], "agregar_contraparte", "proyecto", pid, institucion)
    return tab_resumen(proyectos.obtener(pid), auth)


@rt("/proyectos/{pid}/contrapartes/{cid}")
def delete(auth, pid: int, cid: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    proyectos.quitar_contraparte(pid, cid)
    return tab_resumen(p, auth)


def tab_resumen(p, auth):
    pid = p["id"]
    gestiona = proyectos.puede_gestionar(pid, auth)
    institucional = p["tipo"] == "institucional"
    objetivos = proyectos.objetivos(pid)
    editados = [r for r in proyectos.registros(pid, "producto") + proyectos.registros(pid, "actividad")
                if r["editado_despues"]]
    lista_obj = fh.Ol(*[Li(Div(Span(o["texto"], cls="flex-1"),
                            fh.Button(UkIcon("x", height=14, width=14), type="button",
                                      cls="p-1 rounded hover:bg-muted hover:text-red-600",
                                      hx_delete=f"/proyectos/{pid}/objetivos/{o['id']}",
                                      hx_target=f"#{ID_TAB}", hx_confirm="¿Quitar este objetivo?",
                                      aria_label="Quitar objetivo") if gestiona and not institucional else "",
                            cls="flex gap-2 items-start")) for o in objetivos],
                   cls="list-decimal pl-5 space-y-1") if objetivos \
        else P("Sin objetivos específicos registrados.", cls=TextPresets.muted_sm)
    agregar_obj = fh.Form(
        Input(name="texto", placeholder="Nuevo objetivo específico…", cls="uk-input", required=True,
              aria_label="Nuevo objetivo específico"),
        Button("Agregar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
        hx_post=f"/proyectos/{pid}/objetivos", hx_target=f"#{ID_TAB}",
        cls="flex gap-2 mt-3") if gestiona and not institucional else ""
    return Div(
        tarjeta_propuestas(p, auth) if institucional else "",
        Card(Div(H3("Datos", cls="text-base font-semibold"),
                 Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.ghost, ButtonT.sm),
                        hx_get=f"/proyectos/{pid}/datos/editar", hx_target=f"#{ID_TAB}")
                 if gestiona else "", cls="flex justify-between items-center mb-2"),
             dato("Código", p["codigo"]), dato("Periodo", _periodo(p)),
             dato("Financiamiento", p["fuente_financiamiento"]), dato("Monto", _monto(p)),
             dato("Ámbito", (proyectos.AMBITOS[amb] + ("" if p.get("ambito") else " (según sus contrapartes)"))
                  if (amb := proyectos.ambito_efectivo(p)) else None),
             dato("Descripción", P(p["descripcion"], cls="whitespace-pre-line") if p["descripcion"] else None),
             dato("Objetivo general", p["objetivo_general"])),
        tarjeta_lineas(p, auth),
        tarjeta_contrapartes(p, auth),
        Card(H3("Objetivos específicos", cls="text-base font-semibold mb-2"), lista_obj, agregar_obj),
        Card(H3("Editados después de aprobados", cls="text-base font-semibold mb-2"),
             P("Registros ya aprobados que sus autores modificaron después. Revíselos si corresponde.",
               cls=(TextPresets.muted_sm, "mb-2")),
             Ul(*[Li(_enlace_registro("producto" if "producto_id" in r else "actividad", r["registro_id"]),
                     cls="py-1") for r in editados])) if gestiona and editados else "",
        cls="space-y-6")


def _enlace_registro(tipo, rid):
    if tipo == "producto":
        x = productos.obtener(rid)
        return A(x["titulo"], href=f"/productos/{rid}", cls="text-primary hover:underline") if x else ""
    x = actividades.obtener(rid)
    return A(x["titulo"], href=f"/actividades/{rid}", cls="text-primary hover:underline") if x else ""


@rt("/proyectos/{pid}/objetivos")
def post(auth, pid: int, texto: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if p["tipo"] == "institucional":
        return Response("Los objetivos de un proyecto institucional se cambian en su propuesta.", status_code=403)
    if texto.strip():
        proyectos.agregar_objetivo(pid, texto)
    return tab_resumen(p, auth)


@rt("/proyectos/{pid}/objetivos/{oid}")
def delete(auth, pid: int, oid: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if p["tipo"] == "institucional":
        return Response("Los objetivos de un proyecto institucional se cambian en su propuesta.", status_code=403)
    proyectos.quitar_objetivo(pid, oid)
    return tab_resumen(p, auth)
