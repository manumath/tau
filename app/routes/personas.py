"""Endpoints del selector de personas (autocompletar, filas y alta rápida de externos)."""
from fasthtml.common import APIRouter, HtmxResponseHeaders

from app import personas
from app.components import personas as ui

rt = APIRouter()
CAMPOS = {"autor", "participante"}


def _rol_inicial(campo):
    return "expositor" if campo == "participante" else None


@rt("/personas/buscar")
def get(campo: str = "autor", q: str = "", autor: list[str] = None, participante: list[str] = None):
    if campo not in CAMPOS:
        return ""
    elegidas = set((autor if campo == "autor" else participante) or [])
    return ui.resultados(campo, q, personas.buscar(q, excluir=elegidas))


@rt("/personas/fila")
def get(campo: str = "autor", ref: str = ""):
    p = personas.por_ref(ref)
    if campo not in CAMPOS or not p:
        return ""
    return ui.fila(p, campo, _rol_inicial(campo))


@rt("/personas/externo/nuevo")
def get(campo: str = "autor", q: str = ""):
    return ui.form_externo(campo, q) if campo in CAMPOS else ""


@rt("/personas/externo")
def post(auth, campo: str = "autor", ext_nombres: str = "", ext_apellidos: str = "",
         ext_institucion: str = "", ext_pais: str = ""):
    if campo not in CAMPOS:
        return ""
    if not ext_nombres.strip() or not ext_apellidos.strip():
        # El botón apunta a la lista; el error vuelve al recuadro del formulario.
        _, resultados_id, _ = ui.ids(campo)
        return (ui.form_externo(campo, f"{ext_nombres} {ext_apellidos}",
                                ["Nombres y apellidos son obligatorios."]),
                HtmxResponseHeaders(retarget=f"#{resultados_id}", reswap="innerHTML"))
    # Si ya existe alguien con el mismo nombre se reutiliza, en lugar de duplicarlo.
    externo = personas.externo_similar(ext_nombres, ext_apellidos) or personas.crear_externo(
        ext_nombres, ext_apellidos, ext_institucion, ext_pais, auth["id"])
    return ui.fila(personas.por_ref(f"e:{externo['id']}"), campo, _rol_inicial(campo))
