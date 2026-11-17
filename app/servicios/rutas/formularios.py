"""Formularios imprimibles del reglamento de 2023 (PLAN §70, etapa 6): `/servicios/auxiliaturas/item/{iid}/formulario/{n}`. Los ven quienes ven
el ítem (quien gestiona la convocatoria y los docentes de su comisión); solo existen para convocatorias hechas con ese reglamento."""
import fasthtml.common as fh
from fasthtml.common import APIRouter, Div, Li, P, Span, Table, Tbody, Td, Th, Thead, Tr, Ul
from monsterui.all import H2, H3, TextPresets, UkIcon

from app.comun import config
from app.comun.componentes.layout import pagina
from app.servicios import auxiliaturas as aux
from app.servicios import formularios as frm
from app.servicios import rubricas
from app.servicios.rutas.auxiliaturas import _item_visible
from app.servicios.rutas.comun import no_autorizado, no_encontrado

rt = APIRouter()
BASE = "/servicios/auxiliaturas"
APROBADO = "Aprobado con Res. HCU N.º 424/2023 de fecha 18 de octubre de 2023 (modificada por la Res. HCU N.º 364/2025)"
TABLA = "uk-table uk-table-divider uk-table-small text-sm w-full"


def _n(v, dec: int = 1) -> str:
    if v is None:
        return "—"
    return f"{v:.{dec}f}".rstrip("0").rstrip(".").replace(".", ",") if dec else str(round(v))


def _cabecera(titulo: str, c: dict, it: dict, extra: str = ""):
    g = aux.gestiones_texto(c)
    return Div(
        Div(fh.Button(UkIcon("printer", height=14, width=14), "Imprimir", type="button", data_accion="imprimir",
                      cls="uk-btn uk-btn-default uk-btn-sm gap-1 no-imprimir"), cls="flex justify-end"),
        Div(P(config.UNIVERSIDAD, cls="font-semibold"), P("Vicerrectorado · Departamento de Bienestar Social", cls="text-xs"),
            P(f"{config.FACULTAD} · {config.NOMBRE_CARRERA}", cls="text-sm"), cls="text-center"),
        H2(titulo, cls="text-center mt-3 text-lg"),
        P(f"Gestión académica {g}" + (f" · {extra}" if extra else ""), cls="text-center text-sm"),
        P(f"({APROBADO})", cls="text-center text-xs text-muted-foreground mb-3"),
        Div(Span("Asignatura o proyecto: ", cls="font-medium"), it["titulo"], Span(" · Convocatoria: ", cls="font-medium"), c["titulo"],
            Span(" · Fecha: ", cls="font-medium"), "_" * 18, cls="text-sm mb-3"))


def _firmas(it: dict, con_director: bool = True):
    docentes = [m for m in it["tribunal"] if m["tipo"] == "docente"]
    estudiantes = [m for m in it["tribunal"] if m["tipo"] == "estudiante"]

    def firma(rotulo, m=None):
        return Div(Div(cls="h-12 border-b border-foreground"), P(rotulo, cls="text-xs font-semibold text-center mt-1"),
                   P(f"{m['nombres']} {m['apellidos']}" if m else "Nombre:", cls="text-xs text-center"))
    return Div(Div(*[firma("TRIBUNAL DOCENTE", m) for m in (docentes + [None, None])[:2]],
                   *[firma("TRIBUNAL ESTUDIANTIL", m) for m in (estudiantes + [None, None])[:2]], cls="grid grid-cols-2 sm:grid-cols-4 gap-6"),
               Div(firma("Vo. Bo. DIRECTOR DE CARRERA"), cls="w-64 mx-auto mt-6") if con_director else "", cls="mt-10")


def _nombre(p):
    return f"{p['apellidos']}, {p['nombres']}"


# --- 1: habilitación ------------------------------------------------------------------------------------------------------------

def _f1(c, it):
    filas = frm.habilitacion(it)
    reqs = aux.requisitos(c["id"])
    cab = [Th("N.º"), Th("Nombre completo")] + [Th(str(i), cls="text-center") for i in range(1, len(reqs) + 1)] + \
          [Th(str(len(reqs) + 1), cls="text-center"), Th("Habilitado", cls="text-center"), Th("Inhabilitado", cls="text-center")]
    marca = lambda ok: "✓" if ok else "—"  # noqa: E731
    cuerpo = [Tr(Td(str(n)), Td(_nombre(p)), *[Td(marca(cumplido) if not opcional or cumplido else "n/c", cls="text-center")
                                                for _t, cumplido, opcional in p["requisitos"]],
                 Td(marca(p["plan"]), cls="text-center"),
                 Td("✓" if p["habilitado"] else "", cls="text-center"), Td("✓" if p["habilitado"] is False else "", cls="text-center"))
              for n, p in enumerate(filas, 1)]
    return Div(Div(Table(Thead(Tr(*cab)), Tbody(*cuerpo), cls=TABLA + " min-w-[40rem]"), cls="overflow-x-auto") if cuerpo else
               P("Aún no hay postulaciones enviadas.", cls=TextPresets.muted_sm),
               H3("Requisitos que se verifican", cls="text-sm font-semibold mt-4"),
               Ul(*[Li(f"{i}. {r['texto']}" + (" (solo si corresponde: n/c)" if r["opcional"] else ""), cls="text-xs") for i, r in enumerate(reqs, 1)],
                  Li(f"{len(reqs) + 1}. Plan de trabajo de la materia, proyecto o programa que postula", cls="text-xs"), cls="space-y-0.5"),
               _firmas(it))


# --- 2: méritos (2-1, 2-2 o 2-3) ------------------------------------------------------------------------------------------------

def _f2(c, it):
    bloques = []
    for p in aux.en_concurso(it["id"]):
        acta = frm.acta_meritos(c, p["id"])
        if not acta:
            continue
        filas = []
        for s in acta["secciones"]:
            filas.append(Tr(Td(f"{s['numero']}. {s['titulo']}", colspan="3", cls="font-semibold"),
                            Td(f"máx. {s['maximo']}", cls="text-right font-semibold")))
            for clave, texto, pts, unidad, cantidad in s["lineas"]:
                filas.append(Tr(Td(f"{clave}. {texto}", cls="pl-4"), Td(f"{_n(pts)} p/{unidad}" if pts is not None else "51–59: 2 · 60–69: 4 · 70–79: 6 · 80–89: 8 · 90–100: 10",
                                                                       cls="text-xs"),
                                Td(_n(cantidad), cls="text-right"), Td("")))
            filas.append(Tr(Td("Subtotal", colspan="3", cls="text-right text-xs"), Td(_n(s["puntos"], 2), cls="text-right font-semibold")))
        filas.append(Tr(Td("TOTAL (máximo 30)", colspan="3", cls="text-right font-bold"), Td(_n(acta["total"], 2), cls="text-right font-bold")))
        bloques.append(Div(
            P(Span("Postulante: ", cls="font-medium"), _nombre(p), f" · promedio de {acta['miembros']} miembro(s) del tribunal", cls="text-sm mt-4"),
            Table(Thead(Tr(Th("Línea"), Th("Puntos por unidad"), Th("Cantidad", cls="text-right"), Th("Puntaje", cls="text-right"))), Tbody(*filas),
                  cls=TABLA), _firmas(it), cls="break-after-page"))
    return Div(*bloques) if bloques else P("Aún no se calificaron los méritos.", cls=TextPresets.muted_sm)


# --- 3: sorteo del tema ---------------------------------------------------------------------------------------------------------

def _f3(c, it):
    activos = sorted(aux.activos(it["id"]) if it["fase"] != "concluido" else [p for p in aux.en_concurso(it["id"]) if p["estado"] != "no_habilitada"],
                     key=lambda p: (p["orden_oral"] is None, p["orden_oral"] or 0, p["apellidos"]))
    temas = [t for t in (it["temas_oral"] or "").splitlines() if t]
    return Div(
        H3("Postulantes", cls="text-sm font-semibold"),
        Ul(*[Li(_nombre(p), cls="text-sm") for p in activos], cls="list-decimal pl-5 mb-3"),
        H3("Tribunal calificador", cls="text-sm font-semibold"),
        Table(Thead(Tr(Th("Docentes"), Th("Estudiantes"))),
              Tbody(Tr(Td(*[P(f"{m['nombres']} {m['apellidos']}") for m in it["tribunal"] if m["tipo"] == "docente"]),
                       Td(*[P(f"{m['nombres']} {m['apellidos']}") for m in it["tribunal"] if m["tipo"] == "estudiante"]))), cls=TABLA),
        H3("Temas propuestos por la comisión (cinco)", cls="text-sm font-semibold mt-3"),
        Ul(*[Li(t, cls="text-sm") for t in temas], cls="list-decimal pl-5") if temas else P("Aún no se propusieron.", cls=TextPresets.muted_sm),
        H3("Resultado del sorteo de tema", cls="text-sm font-semibold mt-3"),
        P(it["tema_oral"] or "—", cls="text-sm font-medium"),
        P(f"Cada postulante lo diserta dentro de las 24 horas siguientes al sorteo, con {rubricas.ORAL_TIEMPOS}.", cls="text-xs"),
        H3("Orden de participación de los postulantes", cls="text-sm font-semibold mt-3"),
        Table(Thead(Tr(Th("N.º"), Th("Hora"), Th("Postulante"))),
              Tbody(*[Tr(Td(str(p["orden_oral"] or n)), Td(p["hora_oral"] or ""), Td(_nombre(p))) for n, p in enumerate(activos, 1)]), cls=TABLA),
        _firmas(it))


# --- 4: examen oral ---------------------------------------------------------------------------------------------------------------

def _f4(c, it):
    filas = []
    for p in aux.en_concurso(it["id"]):
        acta = frm.acta_oral(p["id"])
        if acta:
            filas.append(Tr(Td(_nombre(p)), *[Td(_n(v, 2), cls="text-right") for *_, v in acta["criterios"]], Td(_n(acta["total"], 2), cls="text-right font-semibold")))
    cab = [Th("Postulante")] + [Th(f"{t} ({m} p)", cls="text-right") for _k, t, m in rubricas.ORAL] + [Th("Total (35 %)", cls="text-right")]
    return Div(P(f"Tema sorteado: {it['tema_oral'] or '—'} · {rubricas.ORAL_TIEMPOS}. Promedio de los miembros del tribunal.", cls="text-sm mb-2"),
               Div(Table(Thead(Tr(*cab)), Tbody(*filas), cls=TABLA + " min-w-[40rem]"), cls="overflow-x-auto") if filas else
               P("Aún no se calificó el examen oral.", cls=TextPresets.muted_sm), _firmas(it))


# --- 5: acta final ----------------------------------------------------------------------------------------------------------------

def _f5(c, it):
    filas = frm.final(it)
    return Div(
        P(f"En la ciudad de La Paz, a horas ______ del día ____ del mes de ____________ del 20____, el Tribunal Paritario conformado para la evaluación del "
          f"concurso de méritos, examen escrito y oral de los postulantes a la auxiliatura académica en {it['titulo']} y de acuerdo a la convocatoria "
          f"«{c['titulo']}», procedió a la calificación final, de acuerdo al Reglamento Específico de Auxiliares Académicos del Pregrado en vigencia de la "
          f"{config.UNIVERSIDAD}. De manera paritaria y en consenso, acuerdan la siguiente calificación a los postulantes:", cls="text-sm mb-3"),
        Table(Thead(Tr(Th("N.º"), Th("Nombre y apellidos"), Th("Méritos 30 %", cls="text-right"), Th("Examen escrito 35 %", cls="text-right"),
                       Th("Examen oral 35 %", cls="text-right"), Th("Total 100 %", cls="text-right"), Th("Resultado"))),
              Tbody(*[Tr(Td(str(n)), Td(_nombre(p)), *[Td(_n(p["notas"][f], 2), cls="text-right") for f in ("meritos", "escrito", "oral")],
                         Td(_n(p["total"], 2), cls="text-right font-semibold"),
                         Td(aux.ESTADOS_POST[p["estado"]], cls="text-xs")) for n, p in enumerate(filas, 1)]), cls=TABLA)
        if filas else P("Aún no hay postulantes calificados.", cls=TextPresets.muted_sm),
        P(f"Mínimos: méritos {_n(aux.minimo(it, 'meritos'))} de 30 y escrito {_n(aux.minimo(it, 'escrito'))} de 35. Titular con {aux.PUNTAJE_TITULAR} o más de 100.",
          cls="text-xs mt-2"),
        P("Resolución del Consejo de Carrera: " + (c["resolucion_resultados"] or "—") + " · Homologación del Consejo Facultativo: "
          + (c["resolucion_resultados_hcf"] or "—"), cls="text-xs"),
        _firmas(it))


_PAGINAS = {"1": _f1, "2": _f2, "3": _f3, "4": _f4, "5": _f5}


@rt(f"{BASE}/item/{{iid}}/formulario/{{n}}")
def get(auth, iid: int, n: str):
    it, c = _item_visible(auth, iid)
    if not it:
        return no_autorizado()
    if n not in _PAGINAS or not aux.usa_formularios(c):
        return no_encontrado()
    titulo = frm.FORMULARIOS[n]
    if n == "2":
        form = rubricas.formulario_de(c["modalidad"])
        titulo = rubricas.FORMULARIOS[form]["titulo"]
        extra = f"Formulario N.º {form}"
    else:
        extra = f"Formulario N.º {n}"
    return pagina(f"{titulo} · {it['titulo']}", _cabecera(titulo.upper(), c, it, extra), _PAGINAS[n](c, it), usuario=auth)

