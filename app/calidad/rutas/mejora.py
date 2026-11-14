"""Plan de mejora y evaluación externa (PLAN §57, etapa 6): acciones con responsable, plazo, indicador y meta; avances con
evidencia; acciones creadas desde las debilidades de la autoevaluación o las recomendaciones de una evaluación externa.

Lo gestiona la Dirección de Carrera (`gestionar_plan_mejora`); lo ven quienes tienen `ver_plan_mejora`; el responsable de
una acción ve sus acciones y registra sus avances aunque no tenga rol."""
from datetime import date
from urllib.parse import urlencode

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Table, Tbody, Td, Th,
                             Thead, Tr, Ul)
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, FormLabel, LabelInput, LabelTextArea, Progress, \
    TextPresets, UkIcon

from app.calidad import autoevaluacion as ae
from app.calidad import actividades_mejora as am
from app.calidad import evidencias, marco, mejora
from app.calidad.rutas.indicadores import numero
from app.calidad.rutas.informes import XLSX, _archivo, descarga
from app.comun import formato, unidades
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()
BASE = "/calidad/mejora"
TONO_ESTADO = {"pendiente": "gris", "en_curso": "azul", "cumplida": "verde", "cancelada": "gris"}
TONO_PRIORIDAD = {"alta": "rojo", "media": "ambar", "baja": "gris"}


def _no_autorizado():
    return Response("No autorizado", status_code=403)


def _no_encontrado():
    return Response("No encontrado", status_code=404)


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def _fecha(iso):
    return formato.fecha(iso) if iso else "—"


def _gestiona(auth, m):
    return marco.puede(auth, "gestionar_plan_mejora", m)


def _ve_todo(auth, m):
    return marco.puede(auth, "ver_plan_mejora", m)


def _estado(a):
    if a["vencida"]:
        return insignia("Vencida", "rojo", icono="clock")
    return insignia(mejora.ESTADOS[a["estado"]], TONO_ESTADO[a["estado"]],
                    icono="check" if a["estado"] == "cumplida" else None)


def _select(etiqueta, nombre, opciones, actual, vacio=None):
    actual = "" if actual is None else str(actual)
    return Div(FormLabel(etiqueta, fr=nombre),
               Select(*([Option(vacio, value="")] if vacio is not None else []),
                      *[Option(t, value=str(v), selected=str(v) == actual) for v, t in opciones],
                      id=nombre, name=nombre, cls="uk-select"), cls="space-y-2")


def _botones_modal(texto="Guardar"):
    return Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
               Button(texto, type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2")


# --- Tablero ----------------------------------------------------------------------------------------------------

TONO_SEMAFORO = {"vencida": "rojo", "en_riesgo": "ambar", "al_dia": "azul", "cumplida": "verde", "cancelada": "gris"}
ICONO_SEMAFORO = {"vencida": "clock", "en_riesgo": "triangle-alert", "al_dia": None, "cumplida": "check", "cancelada": None}
CIFRAS = (("al_dia", "al día"), ("en_riesgo", "en riesgo"), ("vencida", "vencidas"), ("cumplida", "cumplidas"))


def insignia_semaforo(s):
    return insignia(am.SEMAFOROS[s], TONO_SEMAFORO[s], icono=ICONO_SEMAFORO[s]) if s else ""


def barra_avance(pct, etiqueta):
    """Barra de avance con su cifra; sin cifra, «sin avance medido»."""
    if pct is None:
        return Span("Sin avance medido", cls=TextPresets.muted_sm)
    return Div(Progress(value=pct, max=100, aria_label=etiqueta, cls="flex-1 !mb-0"),
               Span(f"{pct} %", cls="text-sm tabular-nums w-12 text-right"), cls="flex items-center gap-2")


def _tarjeta_accion(a):
    n = len(a["actividades"])
    detalle = [f"{n} actividad{'es' if n != 1 else ''}"] + [f"{c} {t}" for s, t in CIFRAS if (c := a["conteo"].get(s))] \
        if n else []
    return Card(
        Div(Div(Span(a["codigo"], cls="font-mono text-sm text-muted-foreground mr-2") if a["codigo"] else "",
                A(a["titulo"], href=f"{BASE}/acciones/{a['id']}", cls="font-medium hover:underline"), cls="min-w-0"),
            Div(insignia(a["prioridad_p"], TONO_PRIORIDAD[a["prioridad"]], titulo=f"Prioridad {mejora.PRIORIDADES[a['prioridad']].lower()}"),
                insignia_semaforo(a["semaforo"]), cls="flex flex-wrap gap-1.5 shrink-0"),
            cls="flex flex-wrap items-start justify-between gap-2"),
        Div(barra_avance(a["avance"], f"Avance de {a['titulo']}"), cls="mt-3"),
        P(" · ".join(detalle + [f"plazo {formato.fecha(a['plazo'])}"] + ([a["responsable"]] if a["responsable"] else [])),
          cls=(TextPresets.muted_sm, "mt-2")),
        cls="p-4")


FILTROS_PRIORIDAD = (("", "Todas las prioridades"), ("alta", "P1 (alta)"), ("media", "P2 (media)"), ("baja", "P3 (baja)"))


def _url(**params):
    return f"{BASE}?{urlencode({k: v for k, v in params.items() if v})}" if any(params.values()) else BASE


@rt(BASE)
def get(auth, ver: str = "", prioridad: str = "", responsable: str = "", anio: str = ""):
    m = _marco()
    ve, gestiona = _ve_todo(auth, m), _gestiona(auth, m)
    if not ve and not mejora.tiene_acciones(auth["id"]):
        return _no_autorizado()
    todas = am.tablero(m["id"])
    if not ve:      # el responsable sin rol ve solo lo suyo
        todas = [a for a in todas if auth["id"] in a["responsables"]]
    ver = ver if ver in am.SEMAFOROS else ""
    prioridad = prioridad if prioridad in mejora.PRIORIDADES else ""
    rid = int(responsable) if responsable.isdigit() else None
    lista = [a for a in todas if (not ver or a["semaforo"] == ver) and (not prioridad or a["prioridad"] == prioridad)
             and (not rid or rid in a["responsables"]) and (not anio or anio in a["anios"])]
    cifras = {s: sum(a["semaforo"] == s for a in todas) for s, _ in CIFRAS}
    gente = {u["id"]: f"{u['apellidos']}, {u['nombres']}" for u in mejora.responsables()}
    con_resp = sorted({r for a in todas for r in a["responsables"] if r in gente}, key=lambda r: gente[r])
    anios = sorted({x for a in todas for x in a["anios"]})
    aev = (ae.listar(m["id"]) or [None])[0]
    pendientes = am.pendientes_de_marco(m["id"]) if gestiona else []
    filtros = {"ver": ver, "prioridad": prioridad, "responsable": responsable if rid else "", "anio": anio}
    return pagina(
        "Plan de mejora",
        Div(Div(H2("Plan de mejora"), P(m["nombre"], " · versión ", m["version"], cls=TextPresets.muted_sm)),
            Div(A(UkIcon("calendar-range", height=14, width=14), "Cronograma", href=f"{BASE}/cronograma",
                  cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1"),
                A(UkIcon("flag", height=14, width=14), "Cortes", href=f"{BASE}/cortes",
                  cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1") if ve else "",
                A(UkIcon("award", height=14, width=14), "Evaluaciones externas", href=f"{BASE}/externas",
                  cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1") if ve else "",
                A(UkIcon("list-checks", height=14, width=14), "Debilidades de la autoevaluación",
                  href=f"{BASE}/debilidades", cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1")
                if ve and aev else "",
                Button(UkIcon("upload", height=14, width=14), "Cargar CSV", cls=(ButtonT.default, ButtonT.sm),
                       hx_get=f"{BASE}/importar", hx_target=f"#{ID_MODAL}") if gestiona else "",
                Button(UkIcon("plus", height=14, width=14), "Nueva acción", cls=(ButtonT.primary, ButtonT.sm),
                       hx_get=f"{BASE}/acciones/nueva", hx_target=f"#{ID_MODAL}") if gestiona else "",
                descarga("XLSX", f"{BASE}/xlsx") if ve else "", cls="flex flex-wrap gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-4"),
        _aprobacion(m, gestiona) if ve else
        P("Las acciones y actividades del plan de mejora a su cargo: registre sus avances en cada una.", cls="text-sm mb-4"),
        _reprogramaciones_pendientes(pendientes),
        Div(*[A(Card(Div(str(cifras[s]), cls="text-2xl font-semibold"), Div(t, cls=TextPresets.muted_sm),
                     cls="text-center p-3" + (" ring-2 ring-primary" if ver == s else "")),
                href=_url(**{**filtros, "ver": "" if ver == s else s}), aria_current="true" if ver == s else None,
                title=f"Ver solo las acciones {t}")
              for s, t in CIFRAS], cls="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4"),
        Form(Select(*[Option(t, value=v, selected=v == prioridad) for v, t in FILTROS_PRIORIDAD], name="prioridad",
                    aria_label="Prioridad", cls="uk-select uk-form-small w-44"),
             Select(Option("Todos los responsables", value=""),
                    *[Option(gente[r], value=str(r), selected=r == rid) for r in con_resp],
                    name="responsable", aria_label="Responsable", cls="uk-select uk-form-small max-w-xs") if ve else "",
             Select(Option("Todos los años", value=""), *[Option(x, selected=x == anio) for x in anios],
                    name="anio", aria_label="Año del plazo", cls="uk-select uk-form-small w-36"),
             fh.Input(type="hidden", name="ver", value=ver) if ver else "",
             Button("Filtrar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
             A("Quitar filtros", href=BASE, cls="text-sm text-primary hover:underline") if any(filtros.values()) else "",
             method="get", action=BASE, cls="flex flex-wrap items-center gap-2 mb-4"),
        P(f"{len(lista)} de {len(todas)} acciones", cls=(TextPresets.muted_sm, "mb-2")) if len(lista) != len(todas) else "",
        Div(*[_tarjeta_accion(a) for a in lista], cls="grid grid-cols-1 lg:grid-cols-2 gap-3") if lista else
        P("No hay acciones con ese filtro." if todas else
          "El plan aún no tiene acciones: cree la primera o cárguelo completo desde un CSV." if gestiona else
          "El plan aún no tiene acciones.", cls=TextPresets.muted_sm),
        usuario=auth)


def _aprobacion(m, gestiona):
    if am.aprobado(m):
        return P(UkIcon("badge-check", height=14, width=14, cls="inline mr-1"),
                 f"Plan aprobado con {m['plan_resolucion']} el {formato.fecha(m['plan_aprobado_en'])}. Desde entonces el plazo "
                 "de una actividad cambia solo por reprogramación, con su causa.",
                 Button("Corregir", type="button", cls=(ButtonT.ghost, ButtonT.xs, "ml-1"), hx_get=f"{BASE}/aprobacion",
                        hx_target=f"#{ID_MODAL}") if gestiona else "", cls="text-sm mb-4")
    return Div(P("El plan aún no está aprobado: los plazos se pueden editar libremente. Al registrar la resolución que lo "
                 "aprueba, cada cambio de plazo pasará a ser una reprogramación con su causa.", cls="text-sm"),
               Button("Registrar la aprobación", type="button", cls=(ButtonT.default, ButtonT.sm), hx_get=f"{BASE}/aprobacion",
                      hx_target=f"#{ID_MODAL}") if gestiona else "",
               cls="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3 mb-4")


def _reprogramaciones_pendientes(pendientes):
    if not pendientes:
        return ""
    return Card(H3(f"Reprogramaciones por resolver ({len(pendientes)})", cls="text-base font-semibold mb-2"),
                Ul(*[Li(A(f"{r['codigo'] + ' · ' if r['codigo'] else ''}{am.titulo(r['descripcion'])[:90]}",
                          href=f"{BASE}/actividades/{r['actividad_id']}", cls="font-medium hover:underline"),
                        Div(f"{r['solicitante'] or '—'} pide mover el plazo del {formato.fecha(r['plazo_anterior'])} al "
                            f"{formato.fecha(r['plazo_nuevo'])}", cls=TextPresets.muted_sm),
                        P(r["causa"], cls="text-sm line-clamp-2"), cls="py-2")
                     for r in pendientes], cls="divide-y divide-border"),
                cls="mb-4 border-amber-300")


@rt(f"{BASE}/aprobacion")
def get(auth):
    m, error = _gestionable(auth)
    if error:
        return error
    return _form_aprobacion(m, {"resolucion": m["plan_resolucion"] or "", "fecha": m["plan_aprobado_en"] or ""})


def _form_aprobacion(m, d, errores=()):
    return modal("Aprobación del plan de mejora",
                 Form(mensaje_error(*errores),
                      P("Registre la resolución con que se aprobó el plan. Desde la fecha de aprobación, el plazo de cada "
                        "actividad cambia solo por reprogramación: el responsable la pide con su causa y la Dirección de "
                        "Carrera la aprueba o la rechaza.", cls="text-sm"),
                      LabelInput("Resolución", id="resolucion", value=d["resolucion"], required=True, maxlength=200,
                                 placeholder="Res. HCC N.º …"),
                      LabelInput("Fecha de aprobación", id="fecha", type="date", value=d["fecha"], required=True),
                      _botones_modal(), hx_post=f"{BASE}/aprobacion", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt(f"{BASE}/aprobacion")
def post(auth, sess, resolucion: str = "", fecha: str = ""):
    m, error = _gestionable(auth)
    if error:
        return error
    errores = am.aprobar_plan(m["id"], resolucion, fecha)
    if errores:
        return _form_aprobacion(m, {"resolucion": resolucion, "fecha": fecha}, errores)
    auditar(auth["id"], "aprobar_plan_mejora", "marco_calidad", m["id"], f"{resolucion.strip()} · {fecha}")
    add_toast(sess, "Aprobación del plan registrada.", "success")
    return Redirect(BASE)


# --- Cronograma ---------------------------------------------------------------------------------------------------

def _trimestre(iso):
    return (int(iso[5:7]) - 1) // 3 + 1


@rt(f"{BASE}/cronograma")
def get(auth, anio: str = ""):
    m = _marco()
    ve = _ve_todo(auth, m)
    if not ve and not mejora.tiene_acciones(auth["id"]):
        return _no_autorizado()
    acts = am.de_marco(m["id"])
    if not ve:
        acts = [t for t in acts if t["responsable_id"] == auth["id"]]
    anios = sorted({t["plazo"][:4] for t in acts})
    este = str(date.today().year)
    anio = anio if anio in anios else (este if este in anios else (anios[0] if anios else ""))
    del_anio = [t for t in acts if t["plazo"][:4] == anio]
    bloques = []
    for q in (1, 2, 3, 4):
        filas = sorted([t for t in del_anio if _trimestre(t["plazo"]) == q], key=lambda t: t["plazo"])
        if not filas:
            continue
        bloques.append(Div(
            H3(f"{q}.º trimestre", Span(f" · {len(filas)}", cls=TextPresets.muted_sm), cls="text-base font-semibold mb-2"),
            Div(Table(Thead(Tr(Th("Actividad"), Th("Responsable", cls="w-48"), Th("Plazo", cls="w-28"), Th("Avance", cls="w-20"),
                               Th("Estado", cls="w-28"))),
                      Tbody(*[Tr(Td(Span(t["codigo"], cls="font-mono text-xs text-muted-foreground mr-1") if t["codigo"] else "",
                                    A(am.titulo(t["descripcion"]), href=f"{BASE}/actividades/{t['id']}", cls="hover:underline")),
                                 Td(t["responsable"] or t["unidad_responsable"] or "—"),
                                 Td(formato.fecha(t["plazo"]), cls="whitespace-nowrap"),
                                 Td("—" if t["avance"] is None else f"{t['avance']} %", cls="tabular-nums"),
                                 Td(insignia_semaforo(t["semaforo"]))) for t in filas]),
                      cls="uk-table uk-table-divider uk-table-small text-sm", data_tabla=f"cronograma-{anio}-t{q}"),
                cls="overflow-x-auto"), cls="mb-6"))
    return pagina(
        "Cronograma del plan de mejora",
        A(UkIcon("arrow-left", height=14, width=14), "Plan de mejora", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary mb-4"),
        H2("Cronograma del plan de mejora"),
        P("Las actividades por el trimestre en que vence su plazo." + ("" if ve else " Solo las suyas."),
          cls=(TextPresets.muted_sm, "mb-4")),
        Div(*[A(x, href=f"{BASE}/cronograma?anio={x}", aria_current="page" if x == anio else None,
                cls="uk-btn uk-btn-sm " + ("uk-btn-primary" if x == anio else "uk-btn-default")) for x in anios],
            cls="flex flex-wrap gap-2 mb-6", role="navigation", aria_label="Años del plan") if anios else "",
        Card(*bloques) if bloques else P("No hay actividades en el plan." if not anios else "No hay actividades con plazo en ese año.",
                                         cls=TextPresets.muted_sm),
        usuario=auth)


@rt(f"{BASE}/xlsx")
def get(auth):
    m = _marco()
    if not _ve_todo(auth, m):
        return _no_autorizado()
    return _archivo(mejora.a_xlsx(m["id"]), "plan-de-mejora.xlsx", XLSX)


# --- Alta y edición de acciones ---------------------------------------------------------------------------------

def form_accion(m, d, url, metodo, errores=()):
    def v(k):
        return d.get(k) if d.get(k) is not None else ""
    crit = [(c["id"], f"{c['codigo']} {c['nombre']}") for c in evidencias.criterios_del_marco(m["id"])]
    inds = [(i["id"], f"{i['codigo']} {i['nombre']}") for i in mejora.indicadores_del_marco(m["id"])]
    gente = [(u["id"], f"{u['apellidos']}, {u['nombres']}") for u in mejora.responsables()]
    ocultos = [fh.Input(type="hidden", name=k, value=str(v(k))) for k in ("origen", "autoevaluacion_id",
                                                                         "recomendacion_id") if v(k) != ""]
    origen = v("origen") or "otro"
    return modal(
        "Acción de mejora",
        Form(mensaje_error(*errores), *ocultos,
             Div(Div("Origen: ", mejora.ORIGENES[origen], cls="text-sm font-medium"),
                 Div(v("debilidad"), cls="text-sm whitespace-pre-line") if v("debilidad") else "",
                 cls="rounded bg-muted p-3 space-y-1") if origen != "otro" else
             _select("Origen", "origen", list(mejora.ORIGENES.items()), origen),
             fh.Input(type="hidden", name="debilidad", value=v("debilidad")) if origen != "otro" else
             LabelTextArea("Problema que atiende (opcional)", id="debilidad", value=v("debilidad"), rows=2),
             Div(LabelInput("Código (opcional)", id="codigo", value=v("codigo"), maxlength=20, placeholder="A4"),
                 Div(LabelInput("Acción", id="titulo", value=v("titulo"), required=True, maxlength=200), cls="sm:col-span-3"),
                 cls="grid grid-cols-1 sm:grid-cols-4 gap-4"),
             LabelTextArea("Objetivo (opcional)", id="objetivo", value=v("objetivo"), rows=2),
             LabelTextArea("Descripción (opcional)", id="descripcion", value=v("descripcion"), rows=3),
             LabelInput("Eje o dimensión (opcional)", id="eje", value=v("eje"), maxlength=200),
             Div(_select("Criterio", "criterio_id", crit, v("criterio_id"), "—"),
                 _select("Responsable", "responsable_id", gente, v("responsable_id"), "—"),
                 cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
             Div(LabelInput("Plazo", id="plazo", type="date", value=v("plazo"), required=True),
                 _select("Prioridad", "prioridad", [(k, f"{am.PRIORIDAD_P[k]} ({t.lower()})") for k, t in mejora.PRIORIDADES.items()],
                         v("prioridad") or "media"),
                 cls="grid grid-cols-2 gap-4"),
             P("Si la acción tiene actividades, su plazo es el último de ellas y se ajusta solo.", cls=TextPresets.muted_sm)
             if d.get("id") else "",
             Div(Div(_select("Indicador con que se mide (opcional)", "indicador_id", inds, v("indicador_id"), "—"),
                     cls="sm:col-span-2"),
                 LabelInput("Meta (opcional)", id="meta", value=v("meta"), inputmode="decimal"),
                 cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
             _botones_modal(), **{f"hx_{metodo}": url}, hx_target=f"#{ID_MODAL}", cls="space-y-4"),
        ancho="max-w-2xl")


def _datos_accion(f):
    return {k: f.get(k, "") for k in mejora.CAMPOS}


def _gestionable(auth):
    m = _marco()
    return m, (None if _gestiona(auth, m) else _no_autorizado())


@rt(f"{BASE}/acciones/nueva")
def get(auth, criterio: str = "", autoevaluacion: str = "", debilidad: str = "", recomendacion: str = ""):
    m, error = _gestionable(auth)
    if error:
        return error
    d = {"criterio_id": criterio, "prioridad": "media"}
    if autoevaluacion.isdigit():
        d |= {"origen": "autoevaluacion", "autoevaluacion_id": autoevaluacion, "debilidad": debilidad}
    elif recomendacion.isdigit() and (r := mejora.recomendacion(int(recomendacion))) and r["marco_id"] == m["id"]:
        d |= {"origen": "externa", "recomendacion_id": r["id"], "debilidad": r["texto"],
              "criterio_id": r["criterio_id"] or ""}
    return form_accion(m, d, f"{BASE}/acciones", "post")


@rt(f"{BASE}/acciones")
async def post(auth, sess, req):
    m, error = _gestionable(auth)
    if error:
        return error
    x, errores = mejora.validar(_datos_accion(await req.form()), m["id"])
    if errores:
        return form_accion(m, x, f"{BASE}/acciones", "post", errores)
    aid = mejora.crear(m["id"], x, auth["id"])
    auditar(auth["id"], "crear_accion_mejora", "accion_mejora", aid, x["titulo"])
    add_toast(sess, "Acción creada.", "success")
    return Redirect(f"{BASE}/acciones/{aid}")


# --- Ficha de la acción --------------------------------------------------------------------------------------------

def _accion_visible(auth, aid):
    a = mejora.obtener(aid)
    if a is None:
        return None, None, _no_encontrado()
    m = marco.obtener(a["marco_id"])
    if _ve_todo(auth, m) or a["responsable_id"] == auth["id"]:
        return a, m, None
    return a, m, _no_autorizado()


def _puede_avanzar(auth, a, m):
    return a["estado"] in mejora.ABIERTAS and (_gestiona(auth, m) or a["responsable_id"] == auth["id"])


def _meta(a):
    if a["meta"] is None:
        return "—"
    unidad = a["unidad_medida"] if a["unidad_medida"] not in (None, "número", "sí/no") else ""
    return f"{numero(a['meta'])} {unidad}".strip()


def _dato(titulo, *valor):
    return Div(Div(titulo, cls=TextPresets.muted_sm), Div(*valor, cls="text-sm"), cls="space-y-1")


def form_avance(a, m, d=None, errores=()):
    d = d or {}
    evs = [(e["id"], e["titulo"]) for e in evidencias.listar(m["id"])]
    return Form(mensaje_error(*errores),
                LabelTextArea("Avance", id="texto", value=d.get("texto") or "", rows=3, required=True),
                Div(LabelInput("Fecha (hoy, si la deja vacía)", id="fecha", type="date", value=d.get("fecha") or ""),
                    LabelInput("Porcentaje logrado (opcional)", id="porcentaje", type="number", min=0, max=100,
                               value=d.get("porcentaje") if d.get("porcentaje") is not None else ""),
                    _select("Evidencia (opcional)", "evidencia_id", evs, d.get("evidencia_id"), "—"),
                    cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                P("La evidencia se elige del repositorio de evidencias; súbala allí primero.", cls=TextPresets.muted_sm),
                Div(Button("Registrar avance", type="submit", cls=(ButtonT.primary, ButtonT.sm)), cls="flex justify-end"),
                hx_post=f"{BASE}/acciones/{a['id']}/avances", hx_target="#form-avance", hx_select="#form-avance",
                hx_swap="outerHTML", id="form-avance", cls="space-y-3 mt-4")


@rt(f"{BASE}/acciones/{{aid}}")
def get(auth, aid: int):
    a, m, error = _accion_visible(auth, aid)
    if error:
        return error
    gestiona = _gestiona(auth, m)
    abierta = a["estado"] in mejora.ABIERTAS
    url = f"{BASE}/acciones/{aid}"
    acts = am.de_accion(aid)
    resumen = am.resumen_accion(acts) if acts else None
    botones = []
    if gestiona and abierta:
        botones = [Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.default, ButtonT.sm),
                          hx_get=f"{url}/editar", hx_target=f"#{ID_MODAL}"),
                   Button(UkIcon("check", height=14, width=14), "Cumplida", cls=(ButtonT.default, ButtonT.sm),
                          hx_get=f"{url}/cumplir", hx_target=f"#{ID_MODAL}"),
                   Button("Cancelar la acción", cls=(ButtonT.ghost, ButtonT.sm), hx_get=f"{url}/cancelar",
                          hx_target=f"#{ID_MODAL}")]
        if not a["avances"] and not acts:
            botones.append(Button(UkIcon("trash-2", height=14, width=14), "Eliminar", cls=(ButtonT.ghost, ButtonT.sm),
                                  hx_delete=url, hx_target="body", hx_confirm="¿Eliminar la acción?"))
    elif gestiona:
        botones = [Button("Reabrir", cls=(ButtonT.ghost, ButtonT.sm), hx_post=f"{url}/reabrir", hx_target="body",
                          hx_confirm="¿Reabrir la acción?")]
    origen = a["debilidad"]
    if a["recomendacion"]:
        origen = Span(a["recomendacion"]["texto"], " (", A(a["recomendacion"]["organismo"],
                      href=f"{BASE}/externas/{a['recomendacion']['evaluacion_id']}", cls="text-primary hover:underline"),
                      ")")
    return pagina(
        a["titulo"],
        A(UkIcon("arrow-left", height=14, width=14), "Plan de mejora", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary mb-4"),
        Div(Div(H2(Span(a["codigo"], cls="font-mono text-muted-foreground mr-2") if a["codigo"] else "", a["titulo"]),
                Div(insignia_semaforo(resumen["semaforo"]) if resumen and abierta and resumen["semaforo"] else _estado(a),
                    insignia(f"{am.PRIORIDAD_P[a['prioridad']]} · prioridad {mejora.PRIORIDADES[a['prioridad']].lower()}",
                             TONO_PRIORIDAD[a["prioridad"]]), cls="flex flex-wrap gap-2 mt-2"),
                Div(barra_avance(100 if a["estado"] == "cumplida" else resumen["avance"], f"Avance de {a['titulo']}"),
                    cls="mt-3 max-w-md") if resumen else ""),
            Div(*botones, cls="flex flex-wrap gap-2"), cls="flex flex-wrap items-start justify-between gap-4 mb-6"),
        Card(Div(_dato("Objetivo", a["objetivo"]) if a["objetivo"] else "",
                 _dato("Descripción", a["descripcion"] or "—"),
                 _dato("Eje", a["eje"]) if a["eje"] else "",
                 _dato(f"Origen: {mejora.ORIGENES[a['origen']]}", origen or "—"),
                 Div(_dato("Criterio", f"{a['criterio_codigo']} {a['criterio_nombre']}" if a["criterio_codigo"] else "—"),
                     _dato("Responsable", a["responsable"] or "—"), _dato("Plazo", _fecha(a["plazo"])),
                     cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                 Div(_dato("Indicador", A(f"{a['indicador_codigo']} {a['indicador_nombre']}",
                                          href=f"/calidad/marco/indicadores/{a['indicador_id']}",
                                          cls="hover:underline") if a["indicador_id"] else "—"),
                     _dato("Meta", _meta(a)),
                     _dato("Estado", mejora.ESTADOS[a["estado"]],
                           f" el {_fecha(a['cumplida_en'])}" if a["cumplida_en"] else "",
                           " (en plazo)" if a["en_plazo"] else " (fuera de plazo)" if a["estado"] == "cumplida" else "",
                           f": {a['motivo_cancelacion']}" if a["motivo_cancelacion"] else ""),
                     cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                 cls="space-y-4")),
        _actividades(a, acts, gestiona and abierta),
        Card(H3("Avances", cls="text-base font-semibold mb-2"),
             P("Los avances se registran en cada actividad; aquí se ven todos juntos.", cls=(TextPresets.muted_sm, "mb-2"))
             if acts else "",
             Ul(*[Li(Div(Span(_fecha(v["fecha"]), cls="font-medium"),
                         Span(f" · {v['porcentaje']}%", cls="font-medium") if v["porcentaje"] is not None else "",
                         Span(f" · {v['por']}", cls=TextPresets.muted_sm) if v["por"] else "",
                         _boton_quitar(auth, a, m, v)),
                     P(v["texto"], cls="text-sm whitespace-pre-line"),
                     A(UkIcon("folder-open", height=12, width=12), f" {v['evidencia_titulo']}",
                       href=f"/calidad/evidencias/{v['evidencia_id']}", cls="text-xs text-primary hover:underline")
                     if v["evidencia_id"] else "", cls="space-y-1") for v in a["lista_avances"]],
                cls="divide-y divide-border space-y-3") if a["lista_avances"] else
             P("Aún sin avances.", cls=TextPresets.muted_sm),
             form_avance(a, m) if _puede_avanzar(auth, a, m) and not acts else "", cls="mt-6"),
        usuario=auth)


def _actividades(a, acts, puede_agregar):
    nueva = Button(UkIcon("plus", height=14, width=14), "Nueva actividad", cls=(ButtonT.default, ButtonT.sm),
                   hx_get=f"{BASE}/acciones/{a['id']}/actividades/nueva", hx_target=f"#{ID_MODAL}") if puede_agregar else ""
    if not acts:
        return Card(Div(H3("Actividades", cls="text-base font-semibold"), nueva, cls="flex items-center justify-between gap-2"),
                    P("Sin actividades: la acción se sigue con sus propios avances. Agregue actividades si el plan las detalla "
                      "(cada una con su responsable, plazo y meta).", cls=(TextPresets.muted_sm, "mt-2")),
                    cls="mt-6") if puede_agregar else ""
    return Card(
        Div(H3("Actividades", Span(f" · {len(acts)}", cls=TextPresets.muted_sm), cls="text-base font-semibold"), nueva,
            cls="flex items-center justify-between gap-2 mb-2"),
        Div(Table(Thead(Tr(Th("Actividad"), Th("Responsable", cls="w-44"), Th("Plazo", cls="w-28"), Th("Avance", cls="w-20"),
                           Th("Estado", cls="w-28"))),
                  Tbody(*[Tr(Td(Span(t["codigo"], cls="font-mono text-xs text-muted-foreground mr-1") if t["codigo"] else "",
                                A(am.titulo(t["descripcion"]), href=f"{BASE}/actividades/{t['id']}", cls="hover:underline"),
                                insignia("Reprogramación por resolver", "ambar") if t["reprogramacion_pendiente"] else ""),
                             Td(t["responsable"] or t["unidad_responsable"] or "—"),
                             Td(formato.fecha(t["plazo"]), cls="whitespace-nowrap"),
                             Td("—" if t["avance"] is None else f"{t['avance']} %", cls="tabular-nums"),
                             Td(insignia_semaforo(t["semaforo"]))) for t in acts]),
                  cls="uk-table uk-table-divider uk-table-small text-sm", data_tabla=f"actividades-{a['codigo'] or a['id']}"),
            cls="overflow-x-auto"),
        cls="mt-6")


def _boton_quitar(auth, a, m, v):
    if a["estado"] not in mejora.ABIERTAS or not (_gestiona(auth, m) or v["registrado_por"] == auth["id"]):
        return ""
    return Button(UkIcon("trash-2", height=12, width=12), cls=(ButtonT.ghost, ButtonT.xs), type="button",
                  aria_label="Quitar el avance", title="Quitar el avance",
                  hx_delete=f"{BASE}/acciones/{a['id']}/avances/{v['id']}", hx_target="body",
                  hx_confirm="¿Quitar este avance?")


@rt(f"{BASE}/acciones/{{aid}}/avances")
def post(auth, sess, aid: int, texto: str = "", fecha: str = "", porcentaje: str = "", evidencia_id: str = ""):
    a, m, error = _accion_visible(auth, aid)
    if error:
        return error
    if not _puede_avanzar(auth, a, m):
        return _no_autorizado()
    x, errores = mejora.validar_avance({"texto": texto, "fecha": fecha, "porcentaje": porcentaje,
                                        "evidencia_id": evidencia_id}, m["id"])
    if errores:
        return form_avance(a, m, x, errores)
    mejora.registrar_avance(a, x, auth["id"])
    auditar(auth["id"], "avance_accion_mejora", "accion_mejora", aid, x["texto"][:80])
    add_toast(sess, "Avance registrado.", "success")
    return Redirect(f"{BASE}/acciones/{aid}")


@rt(f"{BASE}/acciones/{{aid}}/avances/{{vid}}")
def delete(auth, sess, aid: int, vid: int):
    a, m, error = _accion_visible(auth, aid)
    v = mejora.avance(vid)
    if error or v is None or v["accion_id"] != aid:
        return error or _no_encontrado()
    if a["estado"] not in mejora.ABIERTAS or not (_gestiona(auth, m) or v["registrado_por"] == auth["id"]):
        return _no_autorizado()
    mejora.eliminar_avance(vid)
    auditar(auth["id"], "quitar_avance_accion_mejora", "accion_mejora", aid, v["texto"][:80])
    add_toast(sess, "Avance quitado.", "success")
    return Redirect(f"{BASE}/acciones/{aid}")


def _accion_gestionable(auth, aid):
    a = mejora.obtener(aid)
    if a is None:
        return None, None, _no_encontrado()
    m = marco.obtener(a["marco_id"])
    return a, m, (None if _gestiona(auth, m) else _no_autorizado())


@rt(f"{BASE}/acciones/{{aid}}/editar")
def get(auth, aid: int):
    a, m, error = _accion_gestionable(auth, aid)
    return error or form_accion(m, a, f"{BASE}/acciones/{aid}", "put")


@rt(f"{BASE}/acciones/{{aid}}")
async def put(auth, sess, req, aid: int):
    a, m, error = _accion_gestionable(auth, aid)
    if error:
        return error
    x, errores = mejora.validar(_datos_accion(await req.form()), m["id"])
    if errores:
        return form_accion(m, x, f"{BASE}/acciones/{aid}", "put", errores)
    mejora.actualizar(aid, x)
    auditar(auth["id"], "editar_accion_mejora", "accion_mejora", aid, x["titulo"])
    add_toast(sess, "Acción guardada.", "success")
    return Redirect(f"{BASE}/acciones/{aid}")


@rt(f"{BASE}/acciones/{{aid}}/cumplir")
def get(auth, aid: int):
    a, m, error = _accion_gestionable(auth, aid)
    if error:
        return error
    return modal("Marcar como cumplida",
                 Form(LabelInput("Fecha en que se cumplió", id="fecha", type="date", required=True),
                      P(f"Plazo: {_fecha(a['plazo'])}. Conviene registrar antes el último avance con su evidencia.",
                        cls=TextPresets.muted_sm),
                      _botones_modal("Marcar cumplida"), hx_post=f"{BASE}/acciones/{aid}/cumplir", hx_target="body",
                      cls="space-y-4"))


@rt(f"{BASE}/acciones/{{aid}}/cumplir")
def post(auth, sess, aid: int, fecha: str = ""):
    a, m, error = _accion_gestionable(auth, aid)
    if error:
        return error
    errores = mejora.cumplir(a, fecha)
    if errores:
        add_toast(sess, " ".join(errores), "error")
    else:
        auditar(auth["id"], "cumplir_accion_mejora", "accion_mejora", aid, fecha)
        add_toast(sess, "Acción cumplida.", "success")
    return Redirect(f"{BASE}/acciones/{aid}")


@rt(f"{BASE}/acciones/{{aid}}/cancelar")
def get(auth, aid: int):
    a, m, error = _accion_gestionable(auth, aid)
    if error:
        return error
    return modal("Cancelar la acción",
                 Form(LabelTextArea("Motivo", id="motivo", rows=3, required=True),
                      _botones_modal("Cancelar la acción"), hx_post=f"{BASE}/acciones/{aid}/cancelar", hx_target="body",
                      cls="space-y-4"))


@rt(f"{BASE}/acciones/{{aid}}/cancelar")
def post(auth, sess, aid: int, motivo: str = ""):
    a, m, error = _accion_gestionable(auth, aid)
    if error:
        return error
    errores = mejora.cancelar(a, motivo)
    if errores:
        add_toast(sess, " ".join(errores), "error")
    else:
        auditar(auth["id"], "cancelar_accion_mejora", "accion_mejora", aid, motivo.strip()[:200])
        add_toast(sess, "Acción cancelada.", "success")
    return Redirect(f"{BASE}/acciones/{aid}")


@rt(f"{BASE}/acciones/{{aid}}/reabrir")
def post(auth, sess, aid: int):
    a, m, error = _accion_gestionable(auth, aid)
    if error:
        return error
    mejora.reabrir(a)
    auditar(auth["id"], "reabrir_accion_mejora", "accion_mejora", aid, a["titulo"])
    add_toast(sess, "Acción reabierta.", "success")
    return Redirect(f"{BASE}/acciones/{aid}")


@rt(f"{BASE}/acciones/{{aid}}")
def delete(auth, sess, aid: int):
    a, m, error = _accion_gestionable(auth, aid)
    if error:
        return error
    if not mejora.eliminar(a):
        add_toast(sess, "La acción tiene avances o actividades: cancélela, con su motivo, en lugar de eliminarla.", "error")
        return Redirect(f"{BASE}/acciones/{aid}")
    auditar(auth["id"], "eliminar_accion_mejora", "accion_mejora", aid, a["titulo"])
    add_toast(sess, "Acción eliminada.", "success")
    return Redirect(BASE)


# --- Debilidades de la autoevaluación ----------------------------------------------------------------------------

@rt(f"{BASE}/debilidades")
def get(auth, autoevaluacion: str = ""):
    m = _marco()
    if not _ve_todo(auth, m):
        return _no_autorizado()
    lista = ae.listar(m["id"])
    aev = next((x for x in lista if str(x["id"]) == autoevaluacion), lista[0] if lista else None)
    gestiona = _gestiona(auth, m)
    debs = mejora.debilidades(aev) if aev else []
    return pagina(
        "Debilidades de la autoevaluación",
        A(UkIcon("arrow-left", height=14, width=14), "Plan de mejora", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary mb-4"),
        H2("Debilidades de la autoevaluación"),
        Form(Select(*[Option(f"{x['nombre']} ({ae.ESTADOS[x['estado']].lower()})", value=str(x["id"]),
                             selected=aev and x["id"] == aev["id"]) for x in lista],
                    name="autoevaluacion", aria_label="Autoevaluación", cls="uk-select uk-form-small max-w-sm"),
             Button("Ver", type="submit", cls=(ButtonT.default, ButtonT.sm)), method="get",
             cls="flex items-center gap-2 my-4") if len(lista) > 1 else "",
        P("Cada línea de «debilidades» de los juicios de la autoevaluación. Cree una acción para cada una que se vaya a "
          "atender; las que ya tienen acción lo indican.", cls="text-sm max-w-3xl mb-4"),
        Div(Table(Thead(Tr(Th("Criterio", cls="w-20"), Th("Debilidad"), Th("Nivel", cls="w-40"),
                           Th("Acciones", cls="w-56"))),
                  Tbody(*[Tr(Td(Span(x["criterio"]["codigo"], cls="font-mono"), title=x["criterio"]["nombre"]),
                             Td(x["texto"]), Td(x["nivel"] or "—"),
                             Td(*[Div(A(y["titulo"], href=f"{BASE}/acciones/{y['id']}", cls="text-xs hover:underline"))
                                  for y in x["acciones"]],
                                Button(UkIcon("plus", height=12, width=12), "Crear acción",
                                       cls=(ButtonT.ghost, ButtonT.xs), hx_target=f"#{ID_MODAL}",
                                       hx_get=f"{BASE}/acciones/nueva?" + urlencode(
                                           {"criterio": x["criterio"]["id"], "autoevaluacion": aev["id"],
                                            "debilidad": x["texto"]})) if gestiona else ""))
                          for x in debs]),
                  cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[44rem]"),
            cls="overflow-x-auto") if debs else P("La autoevaluación no tiene debilidades registradas.",
                                                  cls=TextPresets.muted_sm),
        usuario=auth)


# --- Evaluaciones externas --------------------------------------------------------------------------------------

def form_externa(m, d, url, metodo, errores=()):
    def v(k):
        return d.get(k) or ""
    evs = [(e["id"], e["titulo"]) for e in evidencias.listar(m["id"])]
    return modal(
        "Evaluación externa",
        Form(mensaje_error(*errores),
             Div(Div(LabelInput("Organismo evaluador", id="organismo", value=v("organismo"), required=True,
                                maxlength=200), cls="sm:col-span-2"),
                 _select("Tipo", "tipo", list(mejora.TIPOS_EXTERNA.items()), v("tipo") or "acreditacion"),
                 cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
             Div(LabelInput("Visita", id="fecha_visita", type="date", value=v("fecha_visita")),
                 LabelInput("Dictamen", id="fecha_dictamen", type="date", value=v("fecha_dictamen")),
                 LabelInput("Vigente hasta", id="vigente_hasta", type="date", value=v("vigente_hasta")),
                 cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
             LabelInput("Resultado del dictamen", id="resultado", value=v("resultado"), maxlength=500,
                        placeholder="Por ejemplo: acreditada por cinco años, con observaciones"),
             _select("Informe del organismo (evidencia del repositorio, opcional)", "evidencia_id", evs,
                     v("evidencia_id"), "—"),
             LabelTextArea("Nota (opcional)", id="nota", value=v("nota"), rows=2),
             _botones_modal(), **{f"hx_{metodo}": url}, hx_target=f"#{ID_MODAL}", cls="space-y-4"),
        ancho="max-w-2xl")


def _datos_externa(f):
    return {k: f.get(k, "") for k in ("organismo", "tipo", "fecha_visita", "fecha_dictamen", "resultado",
                                      "vigente_hasta", "evidencia_id", "nota")}


@rt(f"{BASE}/externas")
def get(auth):
    m = _marco()
    if not _ve_todo(auth, m):
        return _no_autorizado()
    lista = mejora.externas(m["id"])
    return pagina(
        "Evaluaciones externas",
        A(UkIcon("arrow-left", height=14, width=14), "Plan de mejora", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary mb-4"),
        Div(H2("Evaluaciones externas"),
            Button(UkIcon("plus", height=14, width=14), "Nueva evaluación", cls=(ButtonT.primary, ButtonT.sm),
                   hx_get=f"{BASE}/externas/nueva", hx_target=f"#{ID_MODAL}") if _gestiona(auth, m) else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-4"),
        P("Evaluaciones por pares y acreditaciones de la Carrera: su dictamen, su vigencia y sus recomendaciones, que pasan "
          "al plan de mejora como acciones.", cls="text-sm max-w-3xl mb-4"),
        Div(Table(Thead(Tr(Th("Organismo"), Th("Tipo", cls="w-40"), Th("Dictamen", cls="w-28"),
                           Th("Vigente hasta", cls="w-28"), Th("Recomendaciones", cls="w-36 text-right"))),
                  Tbody(*[Tr(Td(A(x["organismo"], href=f"{BASE}/externas/{x['id']}", cls="font-medium hover:underline"),
                                Div(x["resultado"] or "", cls=TextPresets.muted_sm)),
                             Td(mejora.TIPOS_EXTERNA[x["tipo"]]), Td(_fecha(x["fecha_dictamen"])),
                             Td(_fecha(x["vigente_hasta"])), Td(str(x["recomendaciones"]), cls="text-right"))
                          for x in lista]),
                  cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[44rem]"),
            cls="overflow-x-auto") if lista else P("Aún no hay evaluaciones externas registradas.",
                                                   cls=TextPresets.muted_sm),
        usuario=auth)


@rt(f"{BASE}/externas/nueva")
def get(auth):
    m, error = _gestionable(auth)
    return error or form_externa(m, {}, f"{BASE}/externas", "post")


@rt(f"{BASE}/externas")
async def post(auth, sess, req):
    m, error = _gestionable(auth)
    if error:
        return error
    x, errores = mejora.validar_externa(_datos_externa(await req.form()), m["id"])
    if errores:
        return form_externa(m, x, f"{BASE}/externas", "post", errores)
    xid = mejora.crear_externa(m["id"], x, auth["id"])
    auditar(auth["id"], "crear_evaluacion_externa", "evaluacion_externa", xid, x["organismo"])
    add_toast(sess, "Evaluación externa registrada.", "success")
    return Redirect(f"{BASE}/externas/{xid}")


def _externa(auth, xid, gestionar=False):
    x = mejora.externa(xid)
    if x is None:
        return None, None, _no_encontrado()
    m = marco.obtener(x["marco_id"])
    ok = _gestiona(auth, m) if gestionar else _ve_todo(auth, m)
    return x, m, (None if ok else _no_autorizado())


@rt(f"{BASE}/externas/{{xid}}")
def get(auth, xid: int):
    x, m, error = _externa(auth, xid)
    if error:
        return error
    gestiona = _gestiona(auth, m)
    url = f"{BASE}/externas/{xid}"
    crit = [(c["id"], f"{c['codigo']} {c['nombre']}") for c in evidencias.criterios_del_marco(m["id"])]
    return pagina(
        x["organismo"],
        A(UkIcon("arrow-left", height=14, width=14), "Evaluaciones externas", href=f"{BASE}/externas",
          cls="inline-flex items-center gap-1 text-sm text-primary mb-4"),
        Div(Div(H2(x["organismo"]), P(mejora.TIPOS_EXTERNA[x["tipo"]], cls=TextPresets.muted_sm)),
            Div(Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.default, ButtonT.sm),
                       hx_get=f"{url}/editar", hx_target=f"#{ID_MODAL}"),
                Button(UkIcon("trash-2", height=14, width=14), "Eliminar", cls=(ButtonT.ghost, ButtonT.sm),
                       hx_delete=url, hx_target="body", hx_confirm="¿Eliminar la evaluación externa?"),
                cls="flex gap-2") if gestiona else "",
            cls="flex flex-wrap items-start justify-between gap-4 mb-6"),
        Card(Div(Div(_dato("Visita", _fecha(x["fecha_visita"])), _dato("Dictamen", _fecha(x["fecha_dictamen"])),
                     _dato("Vigente hasta", _fecha(x["vigente_hasta"])), cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                 _dato("Resultado", x["resultado"] or "—"),
                 _dato("Informe del organismo", A(x["evidencia_titulo"], href=f"/calidad/evidencias/{x['evidencia_id']}",
                                                  cls="text-primary hover:underline") if x["evidencia_id"] else "—"),
                 _dato("Nota", x["nota"]) if x["nota"] else "", cls="space-y-4")),
        Card(H3("Recomendaciones", cls="text-base font-semibold mb-2"),
             Div(Table(Tbody(*[Tr(
                 Td(Span(r["criterio_codigo"] or "—", cls="font-mono"), cls="w-20", title=r["criterio_nombre"] or ""),
                 Td(r["texto"]),
                 Td(Span(f"{r['acciones']} acción" + ("es" if r["acciones"] != 1 else ""), cls=TextPresets.muted_sm),
                    Button(UkIcon("plus", height=12, width=12), "Crear acción", cls=(ButtonT.ghost, ButtonT.xs),
                           hx_get=f"{BASE}/acciones/nueva?recomendacion={r['id']}", hx_target=f"#{ID_MODAL}")
                    if gestiona else "",
                    Button(UkIcon("trash-2", height=12, width=12), cls=(ButtonT.ghost, ButtonT.xs), type="button",
                           aria_label="Quitar la recomendación", title="Quitar la recomendación",
                           hx_delete=f"{url}/recomendaciones/{r['id']}", hx_target="body",
                           hx_confirm="¿Quitar la recomendación?") if gestiona and not r["acciones"] else "",
                    cls="w-56")) for r in x["lista_recomendaciones"]]),
                       cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[40rem]"),
                 cls="overflow-x-auto") if x["lista_recomendaciones"] else
             P("Sin recomendaciones registradas.", cls=TextPresets.muted_sm),
             Form(LabelTextArea("Agregar recomendaciones (una por línea)", id="texto", rows=3, required=True),
                  Div(Div(_select("Criterio (opcional)", "criterio_id", crit, "", "—"), cls="flex-1"),
                      Button("Agregar", type="submit", cls=(ButtonT.primary, ButtonT.sm)),
                      cls="flex flex-wrap items-end gap-4"),
                  hx_post=f"{url}/recomendaciones", hx_target="body", cls="space-y-3 mt-4") if gestiona else "",
             cls="mt-6"),
        usuario=auth)


@rt(f"{BASE}/externas/{{xid}}/editar")
def get(auth, xid: int):
    x, m, error = _externa(auth, xid, gestionar=True)
    return error or form_externa(m, x, f"{BASE}/externas/{xid}", "put")


@rt(f"{BASE}/externas/{{xid}}")
async def put(auth, sess, req, xid: int):
    x, m, error = _externa(auth, xid, gestionar=True)
    if error:
        return error
    d, errores = mejora.validar_externa(_datos_externa(await req.form()), m["id"])
    if errores:
        return form_externa(m, d, f"{BASE}/externas/{xid}", "put", errores)
    mejora.actualizar_externa(xid, d)
    auditar(auth["id"], "editar_evaluacion_externa", "evaluacion_externa", xid, d["organismo"])
    add_toast(sess, "Evaluación externa guardada.", "success")
    return Redirect(f"{BASE}/externas/{xid}")


@rt(f"{BASE}/externas/{{xid}}")
def delete(auth, sess, xid: int):
    x, m, error = _externa(auth, xid, gestionar=True)
    if error:
        return error
    if not mejora.eliminar_externa(x):
        add_toast(sess, "Sus recomendaciones ya originaron acciones: no se puede eliminar.", "error")
        return Redirect(f"{BASE}/externas/{xid}")
    auditar(auth["id"], "eliminar_evaluacion_externa", "evaluacion_externa", xid, x["organismo"])
    add_toast(sess, "Evaluación externa eliminada.", "success")
    return Redirect(f"{BASE}/externas")


@rt(f"{BASE}/externas/{{xid}}/recomendaciones")
def post(auth, sess, xid: int, texto: str = "", criterio_id: str = ""):
    x, m, error = _externa(auth, xid, gestionar=True)
    if error:
        return error
    validos = {c["id"] for c in evidencias.criterios_del_marco(m["id"])}
    cid = int(criterio_id) if criterio_id.isdigit() and int(criterio_id) in validos else None
    n = mejora.agregar_recomendaciones(xid, texto, cid)
    if n:
        auditar(auth["id"], "recomendaciones_externas", "evaluacion_externa", xid, f"{n} agregadas")
    add_toast(sess, f"{n} recomendación(es) agregada(s)." if n else "Escriba al menos una recomendación.",
              "success" if n else "error")
    return Redirect(f"{BASE}/externas/{xid}")


@rt(f"{BASE}/externas/{{xid}}/recomendaciones/{{rid}}")
def delete(auth, sess, xid: int, rid: int):
    x, m, error = _externa(auth, xid, gestionar=True)
    r = mejora.recomendacion(rid)
    if error or r is None or r["evaluacion_id"] != xid:
        return error or _no_encontrado()
    if not mejora.eliminar_recomendacion(r):
        add_toast(sess, "La recomendación ya originó acciones.", "error")
    else:
        auditar(auth["id"], "quitar_recomendacion_externa", "evaluacion_externa", xid, r["texto"][:80])
        add_toast(sess, "Recomendación quitada.", "success")
    return Redirect(f"{BASE}/externas/{xid}")

