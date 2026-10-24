"""Planes de estudio: lista y ficha por semestre con electivas, requisitos, totales y las
observaciones marcadas para revisión. Los consulta cualquier persona con sesión; las observaciones
las resuelven la Dirección de Carrera y la Coordinación académica."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, P, Response, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import planes
from app.comun import permisos
from app.comun.componentes.layout import mensaje_error, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()
BASE = "/docencia/planes"


def _vigencia(p):
    return f"Vigente desde {p['vigente_desde']}" + (f" (último ingreso: {p['vigente_hasta']})" if p["vigente_hasta"] else "")


def _medida(p):
    if p["sistema"] == "creditos":
        return f"Créditos (1 crédito = {p['horas_por_credito']} horas académicas)"
    return f"Horas semanales · semestres de {p['semanas_semestre']} semanas"


@rt(BASE)
def get(auth):
    filas = [fh.Tr(fh.Td(A(p["programa"], href=f"{BASE}/{p['id']}", cls="font-medium hover:underline"),
                         Div(planes.NIVELES[p["nivel"]], cls=TextPresets.muted_sm)),
                   fh.Td(p["nombre"], Div(p["resolucion"] or "", cls=TextPresets.muted_sm)),
                   fh.Td(_vigencia(p), cls="text-sm"),
                   fh.Td(str(p["n_asignaturas"]), cls="text-sm tabular-nums"),
                   fh.Td(insignia(f"{p['n_pendientes']} por revisar", "ambar", icono="circle-alert")
                         if p["n_pendientes"] else insignia("Sin observaciones", "verde", icono="check")))
             for p in planes.listar()]
    return pagina(
        "Planes de estudio",
        H2("Planes de estudio"),
        P("Programas de la Carrera de Matemática y sus planes vigentes. Las inconsistencias de los documentos "
          "quedan marcadas para revisión de la Dirección Académica.", cls=(TextPresets.muted_sm, "mb-6")),
        Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Programa"), fh.Th("Plan"), fh.Th("Vigencia"), fh.Th("Asignaturas"),
                                    fh.Th("Revisión"))), fh.Tbody(*filas),
                     cls="uk-table uk-table-divider uk-table-middle"), cls="overflow-x-auto"),
        usuario=auth, seccion="docencia")


def _horas(f, sistema):
    if sistema == "creditos":
        return [fh.Td(f"{f['creditos']}" if f["creditos"] else "—", cls="tabular-nums w-14")]
    return [fh.Td(str(f[c]) if f[c] else "—", cls="tabular-nums w-14")
            for c in ("horas_teoricas", "horas_practicas", "horas_laboratorio")]


def _fila(f, sistema):
    if f["asignatura_id"] is None:
        nombre = Span(planes.TIPOS[f["tipo"]], cls="italic")
        sigla = ""
    else:
        nombre = Div(f["nombre"], Span(" · la dicta otra unidad", cls=TextPresets.muted_sm)
                     if not f["de_la_carrera"] else "")
        sigla = f["sigla"]
    tipo = "" if f["tipo"] == "obligatoria" else insignia(planes.TIPOS[f["tipo"]],
                                                         "azul" if "electiva" in f["tipo"] else "gris")
    return fh.Tr(fh.Td(sigla, cls="font-mono text-sm whitespace-nowrap"), fh.Td(nombre, tipo, cls="text-sm"),
                 *_horas(f, sistema), fh.Td(", ".join(f["requisitos"]) or "—", cls="text-sm whitespace-nowrap"),
                 id=f"asignatura-{sigla}" if sigla else None,  # destino de la búsqueda global
                 cls="target:bg-amber-50 dark:target:bg-amber-950")


def _encabezado(sistema):
    horas = [fh.Th("Créditos", cls="w-14")] if sistema == "creditos" else \
        [fh.Th("T", title="Horas teóricas semanales", cls="w-14"),
         fh.Th("P", title="Horas prácticas semanales", cls="w-14"),
         fh.Th("L", title="Horas de laboratorio semanales", cls="w-14")]
    return fh.Thead(fh.Tr(fh.Th("Sigla"), fh.Th("Asignatura"), *horas, fh.Th("Requisitos")))


def _tabla(filas, sistema):
    return Div(fh.Table(_encabezado(sistema), fh.Tbody(*[_fila(f, sistema) for f in filas]),
                        cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")


def tarjeta_observaciones(p, auth, errores=(), abierta=None):
    obs = planes.observaciones(p["id"])
    if not obs:
        return ""
    revisa = permisos.puede(auth, "revisar_planes")
    items = []
    for o in obs:
        if o["estado"] == "resuelta":
            items.append(Li(Div(insignia("Resuelta", "verde", icono="check"), Span(o["detalle"], cls="text-sm"),
                                cls="flex flex-wrap gap-2 items-start"),
                            P(f"{o['resolucion']} ({o['resuelta_por_nombre']})", cls=(TextPresets.muted_sm, "mt-1")),
                            cls="py-2"))
            continue
        formulario = fh.Form(
            mensaje_error(*(errores if abierta == o["id"] else ())),
            Div(fh.Input(name="resolucion", cls="uk-input", placeholder="Cómo se resolvió…",
                         aria_label="Resolución"),
                Button("Marcar resuelta", type="submit", cls=(ButtonT.default, ButtonT.sm)), cls="flex gap-2"),
            hx_post=f"{BASE}/observaciones/{o['id']}/resolver", hx_target="#observaciones-plan", hx_swap="outerHTML",
            cls="mt-2 space-y-1") if revisa else ""
        items.append(Li(Div(insignia("Por revisar", "ambar", icono="circle-alert"), Span(o["detalle"], cls="text-sm"),
                            cls="flex flex-wrap gap-2 items-start"), formulario, cls="py-2"))
    return Card(H3("Observaciones del documento", cls="text-base font-semibold mb-1"),
                P("Se cargó el plan tal como está en el documento; esto no cuadra y la Dirección Académica debe "
                  "confirmarlo.", cls=(TextPresets.muted_sm, "mb-2")),
                Ul(*items, cls="divide-y divide-border"), id="observaciones-plan")


@rt(f"{BASE}/{{pid}}")
def get(auth, pid: int):
    p = planes.obtener(pid)
    if not p:
        return pagina("No encontrado", P("El plan no existe."), usuario=auth)
    sistema = p["sistema"]
    bloques, ciclo_actual = [], None
    for semestre, ciclo, filas in planes.por_semestre(pid):
        if ciclo and ciclo != ciclo_actual:
            bloques.append(H3(f"Ciclo {ciclo}", cls="text-sm font-semibold uppercase tracking-wide text-muted-foreground mt-4"))
            ciclo_actual = ciclo
        bloques.append(Card(H3(f"{planes.ORDINALES[semestre]} semestre", cls="text-base font-semibold mb-2"),
                            _tabla(filas, sistema)))
    electivas = [Card(H3(f"{planes.GRUPOS_ELECTIVAS[g]} ({len(fs)})", cls="text-base font-semibold mb-2"),
                      _tabla(fs, sistema)) for g, fs in planes.electivas(pid).items()]
    tot = planes.totales(pid)
    filas_tot = [fh.Tr(fh.Td(f"Total {k}"), fh.Td(f"{d:,}".replace(",", ".") if d is not None else "—",
                                                  cls="tabular-nums w-14"),
                       fh.Td(f"{c:,}".replace(",", "."), cls="tabular-nums w-14"),
                       fh.Td(insignia("Coincide", "verde", icono="check") if d == c else
                             insignia("No coincide", "ambar", icono="circle-alert") if d is not None else ""))
                 for k, (d, c) in tot.items()]
    return pagina(
        f"{p['programa']} · {p['nombre']}",
        A(UkIcon("arrow-left", height=14, width=14), "Planes de estudio", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(f"{p['programa']}"),
        P(" · ".join(x for x in (p["nombre"], p["resolucion"], _vigencia(p), _medida(p),
                                 f"Nota mínima de aprobación: {p['nota_minima']} %" if p["nota_minima"] else None) if x),
          cls=(TextPresets.muted_sm, "mb-6")),
        Div(tarjeta_observaciones(p, auth),
            Card(H3("Totales", cls="text-base font-semibold mb-2"),
                 fh.Table(fh.Thead(fh.Tr(fh.Th(""), fh.Th("Documento"), fh.Th("Suma del plan"),
                                        fh.Th(""))), fh.Tbody(*filas_tot), cls="uk-table uk-table-small"),
                 P("Horas: suma de las horas semanales de cada semestre (con las casillas de electiva) por las "
                   "semanas del semestre.", cls=TextPresets.muted_sm) if sistema == "horas" else ""),
            *bloques,
            H3("Asignaturas electivas", cls="text-lg font-semibold mt-8") if electivas else "",
            *electivas,
            cls="space-y-4"),
        usuario=auth, seccion="docencia")


@rt(f"{BASE}/observaciones/{{oid}}/resolver")
def post(auth, sess, oid: int, resolucion: str = ""):
    if not permisos.puede(auth, "revisar_planes"):
        return Response("No autorizado", status_code=403)
    o = planes.observacion(oid)
    if not o:
        return Response("No encontrado", status_code=404)
    p = planes.obtener(o["plan_id"])
    error = planes.resolver(oid, resolucion, auth["id"])
    if error:
        return tarjeta_observaciones(p, auth, [error], oid)
    auditar(auth["id"], "resolver_observacion_plan", "plan_estudios", p["id"], o["detalle"][:120])
    add_toast(sess, "Observación marcada como resuelta.", "success")
    return tarjeta_observaciones(p, auth)
