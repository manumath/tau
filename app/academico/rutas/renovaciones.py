"""Renovación de contratos del semestre (Dirección de Carrera, `gestionar_vinculos`): abre en bloque
el periodo nuevo de contratados, interinos e invitados con la misma categoría y carga."""
import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, Input, Option, P, Redirect, Response, Select, Span
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import carga, gestiones
from app.comun import permisos, vinculos
from app.comun.componentes.layout import mensaje_error, pagina
from app.comun.db import auditar

rt = APIRouter()
BASE = "/docencia/renovaciones"


def _puede(auth):
    return permisos.puede(auth, "gestionar_vinculos", vinculos.carrera())


def _semestres():
    return [g for g in gestiones.listar() if g["tipo"] in carga.SEMESTRES]


def _objetivo(gestion: str):
    """El semestre elegido o, por omisión, el próximo que aún no empezó (si no, el de referencia)."""
    if gestion.isdigit():
        g = gestiones.obtener(int(gestion))
        if g and g["tipo"] in carga.SEMESTRES:
            return g
    hoy = vinculos.hoy().isoformat()
    futuros = [g for g in reversed(_semestres()) if g["fecha_inicio"] > hoy]
    return futuros[0] if futuros else carga.semestre_de_referencia()


def pagina_renovaciones(auth, g, errores=()):
    candidatos = carga.candidatos_renovacion(g)
    filas = [fh.Tr(fh.Td(fh.Input(type="checkbox", name="vinculo", value=str(v["id"]), checked=True, cls="uk-checkbox",
                                  aria_label=f"Renovar a {v['nombres']} {v['apellidos']}")),
                   fh.Td(f"{v['apellidos']}, {v['nombres']}"),
                   fh.Td(vinculos.CATEGORIAS[v["categoria"]], cls="text-sm"),
                   fh.Td(vinculos.texto_periodo(v), cls="text-sm whitespace-nowrap"),
                   fh.Td(vinculos.texto_carga(v) or "Sin carga", cls="text-sm")) for v in candidatos]
    selector = Select(*[Option(gestiones.codigo(x), value=str(x["id"]), selected=x["id"] == g["id"]) for x in _semestres()],
                      aria_label="Semestre", cls="uk-select w-40", data_navegar=f"{BASE}?gestion=")
    return pagina(
        "Renovar contratos",
        Div(Div(H2(f"Renovar contratos para {gestiones.codigo(g)}"),
                P("Contratados, interinos e invitados cuyo periodo terminó en los meses previos al semestre y que aún no "
                  "tienen uno nuevo. Se abre un periodo con la misma categoría y la misma carga contratada; la carga en "
                  "proyectos no pasa sola (los responsables reciben el aviso). Desmarque a quien no se renueva.",
                  cls=TextPresets.muted_sm)),
            selector, cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        mensaje_error(*errores),
        Card(fh.Form(
            Div(fh.Table(fh.Thead(fh.Tr(fh.Th(""), fh.Th("Persona"), fh.Th("Categoría"), fh.Th("Periodo anterior"),
                                        fh.Th("Carga contratada"))), fh.Tbody(*filas),
                         cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto"),
            Div(Div(fh.Label(Span("Desde", cls="text-sm"), Input(type="date", name="desde", value=g["fecha_inicio"],
                                                                 cls="uk-input w-44"), cls="flex items-center gap-2"),
                    fh.Label(Span("Hasta", cls="text-sm"), Input(type="date", name="hasta", value=g["fecha_fin"],
                                                                 cls="uk-input w-44"), cls="flex items-center gap-2"),
                    cls="flex flex-wrap gap-4"),
                Button(UkIcon("refresh-cw", height=14, width=14), "Renovar los marcados", type="submit",
                       cls=ButtonT.primary),
                cls="flex flex-wrap items-center justify-between gap-4 mt-4"),
            method="post", action=f"{BASE}/{g['id']}")
             if filas else P("No hay contratos por renovar para este semestre.", cls=TextPresets.muted_sm)),
        usuario=auth, seccion="docencia")


@rt(BASE)
def get(auth, gestion: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    g = _objetivo(gestion)
    if not g:
        return pagina("Renovar contratos", P("Cree primero las gestiones del año.", cls="text-sm"),
                      usuario=auth, seccion="docencia")
    return pagina_renovaciones(auth, g)


@rt(f"{BASE}/{{gid}}")
async def post(auth, sess, req, gid: int, desde: str = "", hasta: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(gid)
    if not g or g["tipo"] not in carga.SEMESTRES:
        return Response("No encontrado", status_code=404)
    elegidos = [int(x) for x in (await req.form()).getlist("vinculo") if str(x).isdigit()]
    validos = {v["id"] for v in carga.candidatos_renovacion(g)}
    n, errores = carga.renovar([x for x in elegidos if x in validos], desde, hasta, auth["id"])
    if n:
        auditar(auth["id"], "renovar_contratos", "gestion_academica", gid, f"{gestiones.codigo(g)}: {n} persona(s)")
        add_toast(sess, f"{n} contrato(s) renovado(s) para {gestiones.codigo(g)}.", "success")
    if errores:
        return pagina_renovaciones(auth, g, errores)
    return Redirect(f"{BASE}?gestion={gid}")
