"""Guía de Antecedentes de IAC-CINDA (`ver_informes_institucionales`): elegir programa, último
ciclo y tipo de cambio, ver qué llena el sistema y descargar la plantilla oficial llenada."""
from datetime import date
import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, Li, Option, P, Response, Select, Span, Ul
from monsterui.all import H2, Button, ButtonT, Card, TextPresets, UkIcon

from app.acreditacion import guia_antecedentes as guia
from app.acreditacion.rutas.informes import XLSX, _archivo
from app.comun import permisos
from app.comun.componentes.layout import mensaje_error, pagina

rt = APIRouter()
BASE = "/informes/guia-antecedentes"


def _puede(auth):
    return permisos.puede(auth, "ver_informes_institucionales")


def _ultimo(ciclo: str) -> tuple[int, str]:
    """«2026-II» → (2026, 'II'); si no es válido, el último semestre que empezó."""
    anio, _, tipo = (ciclo or "").partition("-")
    if anio.isdigit() and tipo in ("I", "II") and 2000 <= int(anio) <= date.today().year + 1:
        return int(anio), tipo
    return guia.ultimo_ciclo_por_omision()


def _tipo_cambio(texto: str) -> tuple[float | None, str | None]:
    t = (texto or "").strip().replace(",", ".")
    if not t:
        return None, None
    try:
        v = float(t)
    except ValueError:
        return None, "Indique el tipo de cambio como número (p. ej., 6,96)."
    return (v, None) if 0 < v < 1000 else (None, "El tipo de cambio debe ser un número positivo de bolivianos por dólar.")


def _ciclos_elegibles() -> list[tuple[int, str]]:
    a, t = guia.ultimo_ciclo_por_omision()
    return list(reversed(guia.ciclos_hasta(a, t, 12)))


def pantalla(auth, plan: str = "", ciclo: str = "", cambio: str = ""):
    vigentes = guia.planes_vigentes()
    pid = int(plan) if plan.isdigit() else (vigentes[0]["id"] if vigentes else None)
    ultimo = _ultimo(ciclo)
    ciclos = guia.ciclos_hasta(*ultimo)
    _, error = _tipo_cambio(cambio)
    formulario = fh.Form(
        fh.Label(Span("Programa", cls="text-sm"),
                 Select(*[Option(f"{p['programa']} ({p['nombre']})", value=str(p["id"]), selected=p["id"] == pid)
                          for p in vigentes], name="plan", cls="uk-select"), cls="space-y-1 block"),
        fh.Label(Span("Último ciclo de referencia (ciclo 10)", cls="text-sm"),
                 Select(*[Option(guia.texto_ciclo(a, t), value=guia.texto_ciclo(a, t), selected=(a, t) == ultimo)
                          for a, t in _ciclos_elegibles()], name="ciclo", cls="uk-select"), cls="space-y-1 block"),
        fh.Label(Span("Tipo de cambio (bolivianos por dólar)", cls="text-sm"),
                 fh.Input(name="cambio", value=cambio, placeholder="p. ej., 6,96", inputmode="decimal", cls="uk-input"),
                 P("Para expresar en USD los montos de los proyectos, como pide la Guía. Sin él, los montos en "
                   "bolivianos quedan en blanco.", cls=TextPresets.muted_sm), cls="space-y-1 block"),
        Div(Button("Ver los ciclos", type="submit", cls=(ButtonT.default, ButtonT.sm)),
            # La descarga envía lo elegido en el formulario (aunque no se haya pulsado «Ver los ciclos»).
            Button(UkIcon("download", height=14, width=14), "Descargar la Guía (XLSX)", type="submit",
                   formaction=f"{BASE}/xlsx", cls=(ButtonT.primary, ButtonT.sm)) if pid else "",
            cls="flex flex-wrap gap-2"),
        method="get", cls="space-y-4")
    return pagina(
        "Guía de Antecedentes",
        Div(H2("Guía de Antecedentes IAC-CINDA"),
            P(f"La planilla oficial de IAC-CINDA para carreras de pregrado (2025), llenada con lo que registra el "
              f"sistema para los ciclos {guia.texto_ciclo(*ciclos[0])} a {guia.texto_ciclo(*ciclos[-1])} (años "
              f"{ciclos[0][0]}–{ciclos[-1][0]}). La estructura, las fórmulas y los gráficos del resumen estadístico "
              "quedan como los entrega IAC-CINDA: complete a mano lo que el sistema no registra y revise el archivo "
              "antes de enviarlo.", cls=TextPresets.muted_sm),
            cls="mb-6 space-y-1"),
        mensaje_error(error) if error else "",
        Div(Card(formulario, cls="lg:col-span-1"),
            Card(fh.H3("Qué llena el sistema", cls="text-base font-semibold mb-2"),
                 Ul(*[Li(Span(h, cls="font-medium"), Span(f" — {t}", cls="text-muted-foreground"), cls="text-sm")
                      for h, t in guia.COBERTURA], cls="space-y-1.5"),
                 P("Criterios: horas en h/semana (la carga mensual ÷ 4); jornada completa desde 160 h/mes, media "
                   "de 80 a 159, por horas bajo 80; académicos del programa: titulares, contratados, interinos e "
                   "invitados con vínculo vigente. Además se corrigen tres fórmulas de la plantilla (tasas de "
                   "egreso y titulación, deserción al tercer año de la cohorte de la fila 18 y costo total de los "
                   "proyectos).", cls=(TextPresets.muted_sm, "mt-3")),
                 cls="lg:col-span-2"),
            cls="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start"),
        usuario=auth, seccion="informes")


@rt(BASE)
def get(auth, plan: str = "", ciclo: str = "", cambio: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    return pantalla(auth, plan, ciclo, cambio)


@rt(f"{BASE}/xlsx")
def get(auth, plan: str = "", ciclo: str = "", cambio: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    tipo_cambio, error = _tipo_cambio(cambio)
    if error:
        return pantalla(auth, plan, ciclo, cambio)
    ultimo = _ultimo(ciclo)
    contenido = guia.generar(int(plan) if plan.isdigit() else None, ultimo, tipo_cambio)
    return _archivo(contenido, f"guia-antecedentes-{guia.texto_ciclo(*ultimo)}.xlsx", XLSX)
