"""Cortes de seguimiento del plan de mejora (PLAN §72, etapa 5): lista, apertura, informe imprimible con los comentarios de
la Comisión, cierre (el informe queda como evidencia) y XLSX. Los ven quienes ven el plan; los abren, comentan y cierran
quienes registran juicios de la autoevaluación (Dirección de Carrera y Comisión de calidad)."""
from datetime import date

from fasthtml.common import (A, APIRouter, Div, H1, H2, Li, Option, P, Redirect, Select, Span, Table, Tbody, Td, Th,
                             Thead, Tr, Ul)
from fasthtml.toaster import add_toast
from monsterui.all import Button, ButtonT, Card, Form, LabelInput, LabelTextArea, TextPresets, UkIcon

from app.calidad import actividades_mejora as am
from app.calidad import cortes_mejora as cm
from app.calidad import evidencias, marco
from app.calidad.rutas.informes import ESTILO_IMPRESION, XLSX, _archivo, barra, descarga, hoja
from app.calidad.rutas.mejora import BASE, _botones_modal, _marco, _no_autorizado, _no_encontrado, _ve_todo, insignia_semaforo
from app.comun import formato
from app.comun.componentes.layout import ID_MODAL, campo, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()
URL = f"{BASE}/cortes"
TONO_ATENCION = {"vencida": "rojo", "en_riesgo": "ambar", "sin_avance": "gris"}


def _corte(auth, cid, registrar=False):
    c = cm.obtener(cid)
    if c is None:
        return None, None, _no_encontrado()
    m = marco.obtener(c["marco_id"])
    ok = cm.puede_registrar(auth, m) if registrar else _ve_todo(auth, m)
    return c, m, (None if ok else _no_autorizado())


def _titulo(c):
    return f"Corte {c['tipo']} al {formato.fecha(c['fecha'])}"


@rt(URL)
def get(auth):
    m = _marco()
    if not _ve_todo(auth, m):
        return _no_autorizado()
    registra = cm.puede_registrar(auth, m)
    cortes = cm.listar(m["id"])
    filas = [Tr(Td(A(_titulo(c), href=f"{URL}/{c['id']}", cls="text-primary hover:underline")),
                Td(insignia("Abierto", "ambar") if c["estado"] == "abierto" else insignia("Cerrado", "verde")),
                Td(str(c["actividades"]), cls="text-right tabular-nums"),
                Td(f"{c['atencion']}" + (f" ({c['sin_comentar']} sin comentar)" if c["estado"] == "abierto" and
                                         c["sin_comentar"] else ""), cls="tabular-nums"))
             for c in cortes]
    return pagina(
        "Cortes de seguimiento",
        A(UkIcon("arrow-left", height=14, width=14), "Plan de mejora", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary mb-4"),
        Div(Div(H2("Cortes de seguimiento"),
                P("Cada corte congela el estado del plan a su fecha; la Comisión comenta lo que pide atención y, al "
                  "cerrarlo, el informe queda como evidencia.", cls=TextPresets.muted_sm)),
            Button(UkIcon("flag", height=14, width=14), "Abrir un corte", cls=(ButtonT.primary, ButtonT.sm),
                   hx_get=f"{URL}/nuevo", hx_target=f"#{ID_MODAL}") if registra and not cm.abierto(m["id"]) else
            P("Hay un corte abierto: ciérrelo antes de abrir otro.", cls=TextPresets.muted_sm) if registra else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Card(Div(Table(Thead(Tr(Th("Corte"), Th("Estado"), Th("Actividades", cls="text-right"), Th("Piden atención"))),
                   Tbody(*filas), cls="uk-table uk-table-divider uk-table-small text-sm", data_tabla="cortes",
                   aria_label="Cortes de seguimiento"), cls="overflow-x-auto")) if filas else
        P("Aún no hay cortes.", cls=TextPresets.muted_sm),
        usuario=auth)


def _form_abrir(d=None, errores=()):
    d = d or {}
    return modal("Abrir un corte",
                 Form(mensaje_error(*errores),
                      campo("Tipo", Select(*[Option(t, value=k, selected=k == d.get("tipo", "trimestral"))
                                             for k, t in cm.TIPOS.items()], name="tipo", id="tipo", cls="uk-select")),
                      LabelInput("Fecha del corte", id="fecha", type="date", value=d.get("fecha") or date.today().isoformat(),
                                 required=True),
                      P("Se copia el estado de cada actividad a esa fecha. Primero aparecerán las vencidas, en riesgo y sin "
                        "avance desde el corte anterior, para comentarlas.", cls=TextPresets.muted_sm),
                      _botones_modal("Abrir el corte"), hx_post=URL, hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt(f"{URL}/nuevo")
def get(auth):
    return _form_abrir() if cm.puede_registrar(auth, _marco()) else _no_autorizado()


@rt(URL)
def post(auth, sess, tipo: str = "", fecha: str = ""):
    m = _marco()
    if not cm.puede_registrar(auth, m):
        return _no_autorizado()
    cid, errores = cm.abrir(m["id"], tipo, fecha, auth["id"])
    if errores:
        return _form_abrir({"tipo": tipo, "fecha": fecha}, errores)
    auditar(auth["id"], "abrir_corte_mejora", "corte_mejora", cid, f"{tipo} {formato.fecha(fecha)}")
    add_toast(sess, "Corte abierto.", "success")
    return Redirect(f"{URL}/{cid}")


# --- Informe del corte ------------------------------------------------------------------------------------------------------

def _comparar(actual, anterior):
    if anterior is None:
        return ""
    d = actual - anterior
    return Span(f" ({'+' if d > 0 else ''}{d})" if d else " (=)", cls="text-xs text-muted-foreground")


def _resumen(r):
    a, b = r["actual"], r["anterior"]
    celdas = [(am.SEMAFOROS[s], a["semaforo"][s], b["semaforo"][s] if b else None) for s in am.SEMAFOROS]
    celdas += [(f"Prioridad {am.PRIORIDAD_P[p]}", n, b["prioridad"][p] if b else None) for p, n in a["prioridad"].items()]
    celdas.append(("Avance promedio", a["avance"], b["avance"] if b else None))
    return Div(H2("Resumen", cls="text-lg font-semibold mb-1"),
               P(f"Entre paréntesis, la diferencia con el corte anterior ({formato.fecha(r['previo']['fecha'])})."
                 if r["previo"] else "Es el primer corte: no hay con qué comparar.", cls="apagado text-sm"),
               Div(*[Div(Div(Span(f"{n} %" if t == "Avance promedio" else str(n), cls="text-xl font-semibold tabular-nums"),
                             _comparar(n, ant)), Div(t, cls="text-xs text-muted-foreground"),
                         cls="rounded-md border border-border p-2 text-center") for t, n, ant in celdas],
                   cls="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2"), cls="mb-6")


def _form_comentario(c, x):
    return Form(LabelTextArea("Comentario de la Comisión", id=f"comentario-{x['id']}", name="texto",
                              value=x["comentario"] or "", rows=2),
                Div(Button("Guardar comentario", type="submit", cls=(ButtonT.default, ButtonT.xs)), cls="flex justify-end"),
                hx_post=f"{URL}/{c['id']}/comentarios/{x['id']}", hx_target=f"#item-{x['id']}", hx_swap="outerHTML",
                cls="no-imprimir space-y-2 mt-2")


def _item_atencion(c, x, comenta):
    return Li(Div(Div(Span(f"{x['accion_codigo'] or ''} {x['codigo'] or ''}".strip(), cls="font-mono text-muted-foreground mr-2"),
                      A(am.titulo(x["descripcion"]), href=f"{BASE}/actividades/{x['actividad_id']}", cls="hover:underline")
                      if x["actividad_id"] else am.titulo(x["descripcion"])),
                  insignia(cm.ATENCION[x["atencion"]], TONO_ATENCION[x["atencion"]]),
                  cls="flex flex-wrap items-start justify-between gap-2"),
              P(f"{x['responsable'] or '—'} · plazo {formato.fecha(x['plazo'])} · avance "
                f"{'—' if x['avance'] is None else str(round(x['avance'])) + ' %'} · último avance "
                f"{formato.fecha(x['ultimo_avance']) if x['ultimo_avance'] else 'ninguno'}", cls="apagado text-sm"),
              P(x["ultimo_texto"], cls="text-sm whitespace-pre-line") if x["ultimo_texto"] else "",
              (Div(P(x["comentario"], cls="text-sm whitespace-pre-line"),
                   P(f"{x['comento'] or ''}", cls="text-xs text-muted-foreground"),
                   cls="border-l-2 border-primary pl-3 mt-1") if x["comentario"] else "")
              if not (comenta and c["estado"] == "abierto") else _form_comentario(c, x),
              id=f"item-{x['id']}", cls="py-3 space-y-1")


def _tabla_resto(resto):
    return Div(Table(Thead(Tr(Th("Actividad"), Th("Responsable"), Th("Plazo"), Th("Avance", cls="text-right"), Th("Semáforo"))),
                 Tbody(*[Tr(Td(Span(f"{x['accion_codigo'] or ''} {x['codigo'] or ''}".strip(), cls="font-mono mr-1"),
                               am.titulo(x["descripcion"])),
                            Td(x["responsable"] or "—"), Td(formato.fecha(x["plazo"]), cls="whitespace-nowrap"),
                            Td("—" if x["avance"] is None else f"{round(x['avance'])} %", cls="text-right tabular-nums"),
                            Td(insignia_semaforo(x["semaforo"]))) for x in resto]),
                 cls="uk-table uk-table-divider uk-table-small text-sm", aria_label="Las demás actividades"),
               cls="overflow-x-auto")


def documento(c, comenta=False):
    todos = cm.items(c["id"])
    atencion = [x for x in todos if x["atencion"]]
    resto = [x for x in todos if not x["atencion"]]
    reps = cm.reprogramaciones_del_periodo(c)
    return hoja(
        H1(f"Plan de mejora: {_titulo(c).lower()}"),
        P(f"Abierto por {c['abrio'] or '—'} el {formato.fecha_hora(c['abierto_en'])}"
          + (f" · cerrado por {c['cerro'] or '—'} el {formato.fecha_hora(c['cerrado_en'])}" if c["cerrado_en"] else
             " · abierto: las cifras están congeladas a la fecha del corte, los comentarios se pueden cambiar"),
          cls="apagado text-sm mb-6"),
        _resumen(cm.resumen(c["id"])),
        Div(H2(f"Piden atención ({len(atencion)})", cls="text-lg font-semibold"),
            Ul(*[_item_atencion(c, x, comenta) for x in atencion], cls="divide-y divide-border") if atencion else
            P("Ninguna actividad vencida, en riesgo ni sin avance desde el corte anterior.", cls="apagado text-sm"),
            cls="mb-6"),
        Div(H2(f"Las demás actividades ({len(resto)})", cls="text-lg font-semibold mb-2"), _tabla_resto(resto),
            cls="mb-6") if resto else "",
        Div(H2(f"Reprogramaciones del periodo ({len(reps)})", cls="text-lg font-semibold mb-2"),
            Ul(*[Li(Span(f"{r['accion_codigo'] or ''} {r['codigo'] or ''}".strip(), cls="font-mono mr-1"),
                    f"{am.titulo(r['descripcion'])}: ", Span(formato.fecha(r["plazo_anterior"]), cls="line-through"), " → ",
                    formato.fecha(r["plazo_nuevo"]), f" ({am.ESTADOS_REPROGRAMACION[r['estado']].lower()}). ",
                    Span(r["causa"], cls="text-muted-foreground"), cls="text-sm py-1") for r in reps]),
            cls="mb-6") if reps else "",
        Div(H2("Conclusión", cls="text-lg font-semibold mb-1"), P(c["conclusion"], cls="text-sm whitespace-pre-line"))
        if c["conclusion"] else "",
        titulo=f"Plan de mejora · {_titulo(c)}")


@rt(f"{URL}/{{cid}}")
def get(auth, cid: int):
    c, m, error = _corte(auth, cid)
    if error:
        return error
    comenta = cm.puede_registrar(auth, m)
    pendientes = sum(1 for x in cm.items(cid) if x["atencion"] and not x["comentario"])
    acciones = []
    if comenta and c["estado"] == "abierto":
        acciones = [Button(UkIcon("lock", height=14, width=14), "Cerrar el corte", cls=(ButtonT.primary, ButtonT.sm),
                           hx_get=f"{URL}/{cid}/cerrar", hx_target=f"#{ID_MODAL}"),
                    Button(UkIcon("trash-2", height=14, width=14), "Descartar", cls=(ButtonT.ghost, ButtonT.sm),
                           hx_delete=f"{URL}/{cid}", hx_target="body",
                           hx_confirm="¿Descartar el corte? Se borran sus comentarios.")]
    evidencia = A(UkIcon("folder-open", height=14, width=14), "Ver la evidencia", href=f"/calidad/evidencias/{c['evidencia_id']}",
                  cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1") if c["evidencia_id"] else ""
    return pagina(
        _titulo(c), ESTILO_IMPRESION,
        A(UkIcon("arrow-left", height=14, width=14), "Cortes de seguimiento", href=URL,
          cls="no-imprimir inline-flex items-center gap-1 text-sm text-primary mb-4"),
        Div(P(f"{pendientes} actividad(es) que piden atención aún sin comentario.", cls="text-sm")
            if pendientes and c["estado"] == "abierto" else "",
            Div(*acciones, evidencia, cls="flex flex-wrap gap-2"),
            cls="no-imprimir flex flex-wrap items-center justify-between gap-3 mb-4") if acciones or evidencia or pendientes else "",
        barra((), [descarga("XLSX", f"{URL}/{cid}/xlsx")]), documento(c, comenta), usuario=auth)


@rt(f"{URL}/{{cid}}/xlsx")
def get(auth, cid: int):
    c, m, error = _corte(auth, cid)
    return error or _archivo(cm.a_xlsx(cid), f"corte-{c['tipo']}-{c['fecha']}.xlsx", XLSX)


@rt(f"{URL}/{{cid}}/comentarios/{{iid}}")
def post(auth, cid: int, iid: int, texto: str = ""):
    c, m, error = _corte(auth, cid, registrar=True)
    if error:
        return error
    if cm.comentar(c, iid, texto, auth["id"]):
        return _no_encontrado()
    auditar(auth["id"], "comentar_corte_mejora", "corte_mejora", cid, (texto or "").strip()[:80])
    x = next(x for x in cm.items(cid) if x["id"] == iid)
    return _item_atencion(c, x, True)


def _form_cerrar(c, m, d=None, errores=()):
    d = d or {}
    pendientes = sum(1 for x in cm.items(c["id"]) if x["atencion"] and not x["comentario"])
    crit = d.get("criterio_id") or cm.criterio_propuesto(m["id"])
    return modal("Cerrar el corte",
                 Form(mensaje_error(*errores),
                      P(f"Quedan {pendientes} actividad(es) que piden atención sin comentario: puede cerrar igual."
                        if pendientes else "Todas las actividades que piden atención tienen comentario.", cls="text-sm"),
                      LabelTextArea("Conclusión (opcional)", id="conclusion", value=d.get("conclusion") or "", rows=4),
                      campo("Criterio del marco al que se agrega el informe",
                            Select(*[Option(f"{x['codigo']} {x['nombre']}", value=str(x["id"]),
                                            selected=str(x["id"]) == str(crit))
                                     for x in evidencias.criterios_del_marco(m["id"])],
                                   name="criterio_id", id="criterio_id", cls="uk-select")),
                      P("Al cerrar, el corte ya no cambia y su informe en XLSX queda en el repositorio de evidencias.",
                        cls=TextPresets.muted_sm),
                      _botones_modal("Cerrar el corte"), hx_post=f"{URL}/{c['id']}/cerrar", hx_target=f"#{ID_MODAL}",
                      cls="space-y-4"))


@rt(f"{URL}/{{cid}}/cerrar")
def get(auth, cid: int):
    c, m, error = _corte(auth, cid, registrar=True)
    return error or _form_cerrar(c, m)


@rt(f"{URL}/{{cid}}/cerrar")
def post(auth, sess, cid: int, conclusion: str = "", criterio_id: str = ""):
    c, m, error = _corte(auth, cid, registrar=True)
    if error:
        return error
    errores = cm.cerrar(c, conclusion, criterio_id, auth["id"])
    if errores:
        return _form_cerrar(c, m, {"conclusion": conclusion, "criterio_id": criterio_id}, errores)
    auditar(auth["id"], "cerrar_corte_mejora", "corte_mejora", cid, _titulo(c))
    add_toast(sess, "Corte cerrado; su informe quedó como evidencia.", "success")
    return Redirect(f"{URL}/{cid}")


@rt(f"{URL}/{{cid}}")
def delete(auth, sess, cid: int):
    c, m, error = _corte(auth, cid, registrar=True)
    if error:
        return error
    if not cm.eliminar(c):
        return _no_autorizado()
    auditar(auth["id"], "descartar_corte_mejora", "corte_mejora", cid, _titulo(c))
    add_toast(sess, "Corte descartado.", "success")
    return Redirect(URL)
