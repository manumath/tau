"""Actividades del plan de mejora (PLAN §72, etapa 3): alta y edición (Dirección de Carrera), ficha con avances y
reprogramaciones, y la resolución de las reprogramaciones.

La ven quienes tienen `ver_plan_mejora`, el responsable de la actividad y el de su acción. Registran avances y piden
reprogramaciones el responsable de la actividad y quien gestiona el plan; lo demás es de `gestionar_plan_mejora`."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, P, Redirect, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, LabelInput, LabelTextArea, TextPresets, UkIcon

from app.calidad import actividades_mejora as am
from app.calidad import evidencias, marco, mejora
from app.calidad.rutas.indicadores import numero
from app.calidad.rutas.mejora import (BASE, _botones_modal, _dato, _gestiona, _no_autorizado, _no_encontrado, _select,
                                      _ve_todo, barra_avance, insignia_semaforo)
from app.comun import formato
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

rt = APIRouter()


def _url(tid):
    return f"{BASE}/actividades/{tid}"


def _visible(auth, tid):
    """(actividad, marco, error): la ven quienes ven el plan, su responsable y el de su acción."""
    t = am.obtener(tid)
    if t is None:
        return None, None, _no_encontrado()
    m = marco.obtener(t["marco_id"])
    a = mejora.obtener(t["accion_id"])
    if _ve_todo(auth, m) or am.es_responsable(auth, t) or a["responsable_id"] == auth["id"]:
        return t, m, None
    return t, m, _no_autorizado()


def _gestionable(auth, tid):
    t = am.obtener(tid)
    if t is None:
        return None, None, _no_encontrado()
    m = marco.obtener(t["marco_id"])
    return t, m, (None if _gestiona(auth, m) else _no_autorizado())


# --- Formulario -----------------------------------------------------------------------------------------------------------

def form_actividad(m, d, url, metodo, errores=(), actual=None):
    def v(k):
        return "" if d.get(k) is None else d.get(k)
    gente = [(u["id"], f"{u['apellidos']}, {u['nombres']}") for u in mejora.responsables()]
    inds = [(i["id"], f"{i['codigo']} {i['nombre']}") for i in mejora.indicadores_del_marco(m["id"])]
    plazo_fijo = actual is not None and am.aprobado(m)
    num = lambda x: numero(x) if isinstance(x, (int, float)) else x  # noqa: E731
    return modal(
        "Actividad del plan de mejora",
        Form(mensaje_error(*errores),
             Div(LabelInput("Código (opcional)", id="codigo", value=v("codigo"), maxlength=20, placeholder="4.2"),
                 Div(LabelTextArea("Actividad", id="descripcion", value=v("descripcion"), rows=2, required=True),
                     cls="sm:col-span-3"), cls="grid grid-cols-1 sm:grid-cols-4 gap-4"),
             Div(_select("Responsable (persona del sistema)", "responsable_id", gente, v("responsable_id"), "—"),
                 LabelInput("Unidad responsable (si no es una persona del sistema, o además)", id="unidad_responsable",
                            value=v("unidad_responsable"), maxlength=200, placeholder="DEAGEC, DTIC…"),
                 cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
             Div(LabelInput("Inicio (opcional)", id="inicio", type="date", value=v("inicio")),
                 LabelInput("Plazo", id="plazo", type="date", value=v("plazo"), required=True, readonly=plazo_fijo),
                 cls="grid grid-cols-2 gap-4"),
             P("El plan está aprobado: el plazo cambia solo por reprogramación, desde la ficha de la actividad.",
               cls=TextPresets.muted_sm) if plazo_fijo else "",
             Div(LabelInput("Línea base", id="linea_base", value=v("linea_base"), maxlength=500,
                            placeholder="Tasa de deserción 2025: 31 %"),
                 LabelInput("Meta", id="meta", value=v("meta"), maxlength=500, placeholder="Bajar a 25 % en 2028"),
                 cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
             fh.Details(fh.Summary("Medir con un indicador del sistema", cls="cursor-pointer text-sm font-medium"),
                        P("Con un indicador y la línea base y la meta en números, el avance se calcula solo con la última "
                          "cifra del indicador; si no, el avance es el último porcentaje registrado.",
                          cls=(TextPresets.muted_sm, "mt-2")),
                        Div(Div(_select("Indicador", "indicador_id", inds, v("indicador_id"), "—"), cls="sm:col-span-2"),
                            LabelInput("Línea base (número)", id="linea_base_valor", value=num(v("linea_base_valor")),
                                       inputmode="decimal"),
                            LabelInput("Meta (número)", id="meta_valor", value=num(v("meta_valor")), inputmode="decimal"),
                            cls="grid grid-cols-1 sm:grid-cols-4 gap-4 mt-2"),
                        open=bool(v("indicador_id")), cls="rounded-md border border-border p-3"),
             Div(LabelInput("Presupuesto en Bs (opcional)", id="presupuesto", value=num(v("presupuesto")), inputmode="decimal"),
                 LabelInput("Fuente del presupuesto", id="fuente", value=v("fuente"), maxlength=200,
                            placeholder="Recursos propios, IDH…"),
                 cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
             Div(LabelTextArea("Medio de verificación", id="verificacion", value=v("verificacion"), rows=2),
                 LabelTextArea("Medio de difusión", id="difusion", value=v("difusion"), rows=2),
                 cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
             _botones_modal(), **{f"hx_{metodo}": url}, hx_target=f"#{ID_MODAL}", cls="space-y-4"),
        ancho="max-w-3xl")


def _datos(f):
    return {k: f.get(k, "") for k in am.CAMPOS}


@rt(f"{BASE}/acciones/{{aid}}/actividades/nueva")
def get(auth, aid: int):
    a = mejora.obtener(aid)
    if a is None:
        return _no_encontrado()
    m = marco.obtener(a["marco_id"])
    if not _gestiona(auth, m) or a["estado"] not in mejora.ABIERTAS:
        return _no_autorizado()
    return form_actividad(m, {"responsable_id": a["responsable_id"]}, f"{BASE}/acciones/{aid}/actividades", "post")


@rt(f"{BASE}/acciones/{{aid}}/actividades")
async def post(auth, sess, req, aid: int):
    a = mejora.obtener(aid)
    if a is None:
        return _no_encontrado()
    m = marco.obtener(a["marco_id"])
    if not _gestiona(auth, m) or a["estado"] not in mejora.ABIERTAS:
        return _no_autorizado()
    x, errores = am.validar(_datos(await req.form()), m["id"])
    if errores:
        return form_actividad(m, x, f"{BASE}/acciones/{aid}/actividades", "post", errores)
    tid = am.crear(aid, x, auth["id"])
    auditar(auth["id"], "crear_actividad_mejora", "actividad_mejora", tid, x["descripcion"][:120])
    add_toast(sess, "Actividad agregada.", "success")
    return Redirect(f"{BASE}/acciones/{aid}")


@rt(f"{BASE}/actividades/{{tid}}/editar")
def get(auth, tid: int):
    t, m, error = _gestionable(auth, tid)
    return error or form_actividad(m, t, _url(tid), "put", actual=t)


@rt(f"{BASE}/actividades/{{tid}}")
async def put(auth, sess, req, tid: int):
    t, m, error = _gestionable(auth, tid)
    if error:
        return error
    x, errores = am.validar(_datos(await req.form()), m["id"], actual=t)
    if errores:
        return form_actividad(m, x, _url(tid), "put", errores, actual=t)
    am.actualizar(t, x)
    auditar(auth["id"], "editar_actividad_mejora", "actividad_mejora", tid, x["descripcion"][:120])
    add_toast(sess, "Actividad guardada.", "success")
    return Redirect(_url(tid))


# --- Ficha ---------------------------------------------------------------------------------------------------------------------

def _texto_dinero(v):
    return f"Bs {numero(v)}" if v is not None else "—"


def _volver_seguro(volver: str) -> str | None:
    """Solo direcciones de este sitio («/docencia/pendientes»), nunca «//otro.sitio»."""
    return volver if volver.startswith("/") and not volver.startswith("//") else None


def form_avance(t, m, d=None, errores=(), volver=None):
    """Con `volver`, es el formulario del modal de «Mi parte del plan»: al guardar vuelve a esa pantalla."""
    d = d or {}
    evs = [(e["id"], e["titulo"]) for e in evidencias.listar(m["id"])]
    con_indicador = t["indicador_id"] and t["linea_base_valor"] is not None and t["meta_valor"] is not None
    return Form(mensaje_error(*errores),
                LabelTextArea("¿Qué se hizo?", id="texto", value=d.get("texto") or "", rows=3, required=True),
                Div(LabelInput("Fecha (hoy, si la deja vacía)", id="fecha", type="date", value=d.get("fecha") or ""),
                    LabelInput("Porcentaje logrado (opcional)", id="porcentaje", type="number", min=0, max=100,
                               value=d.get("porcentaje") if d.get("porcentaje") is not None else "")
                    if not con_indicador else "",
                    _select("Evidencia (opcional)", "evidencia_id", evs, d.get("evidencia_id"), "—"),
                    cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                P("El avance de esta actividad lo calcula el indicador; describa lo hecho y adjunte la evidencia."
                  if con_indicador else "La evidencia se elige del repositorio de evidencias; súbala allí primero.",
                  cls=TextPresets.muted_sm),
                fh.Input(type="hidden", name="volver", value=volver) if volver else "",
                (_botones_modal("Registrar avance") if volver else
                 Div(Button("Registrar avance", type="submit", cls=(ButtonT.primary, ButtonT.sm)), cls="flex justify-end")),
                **({"hx_post": f"{_url(t['id'])}/avances", "hx_target": f"#{ID_MODAL}"} if volver else
                   {"hx_post": f"{_url(t['id'])}/avances", "hx_target": "#form-avance", "hx_select": "#form-avance",
                    "hx_swap": "outerHTML", "id": "form-avance"}),
                cls="space-y-3 mt-4")


def _modal_avance(t, m, volver, d=None, errores=()):
    return modal(f"Registrar avance: {t['codigo'] + ' ' if t['codigo'] else ''}{am.titulo(t['descripcion'])[:70]}",
                 P(f"Plazo: {formato.fecha(t['plazo'])} · avance actual: "
                   f"{'—' if t['avance'] is None else str(round(t['avance'])) + ' %'}", cls=TextPresets.muted_sm),
                 form_avance(t, m, d, errores, volver=volver), ancho="max-w-2xl")


@rt(f"{BASE}/actividades/{{tid}}/avance")
def get(auth, tid: int, volver: str = ""):
    t, m, error = _visible(auth, tid)
    if error:
        return error
    if t["estado"] not in am.ABIERTAS or not am.puede_avanzar(auth, t):
        return _no_autorizado()
    return _modal_avance(t, m, _volver_seguro(volver) or _url(tid))


def mi_parte(auth, volver: str):
    """«Mi parte del plan de mejora» (PLAN §72, etapa 6): las actividades abiertas a cargo de la persona, la más urgente
    primero, con un botón que registra el avance en un modal sin salir de la pantalla. Vacío si no tiene ninguna."""
    acts = am.de_responsable(auth["id"])
    if not acts:
        return ""
    return Card(Div(H3("Mi parte del plan de mejora", cls="text-base font-semibold"),
                    A("Ver el plan", href=BASE, cls="text-sm text-primary hover:underline"),
                    cls="flex items-center justify-between gap-2 mb-1"),
                Ul(*[Li(Div(Div(A(Span(t["codigo"] or "", cls="font-mono text-muted-foreground mr-1"),
                                   am.titulo(t["descripcion"]), href=_url(t["id"]), cls="text-sm font-medium hover:underline"),
                                 Div(f"{t['accion_codigo'] + ' · ' if t['accion_codigo'] else ''}vence el "
                                     f"{formato.fecha(t['plazo'])} · avance "
                                     f"{'—' if t['avance'] is None else str(round(t['avance'])) + ' %'}",
                                     cls=TextPresets.muted_sm), cls="min-w-0 flex-1"),
                             insignia_semaforo(t["semaforo"]),
                             Button("Registrar avance", type="button", cls=(ButtonT.default, ButtonT.xs),
                                    hx_get=f"{_url(t['id'])}/avance?volver={volver}", hx_target=f"#{ID_MODAL}"),
                             cls="flex flex-wrap items-center gap-3 py-2")) for t in acts],
                   cls="divide-y divide-border"), cls="mb-4")


def _cifra_indicador(t):
    if not t["indicador_id"]:
        return "—"
    actual, anio = am.valor_indicador(t, __import__("datetime").date.today())
    return Span(A(f"{t['indicador_codigo']} {t['indicador_nombre']}", href=f"/calidad/marco/indicadores/{t['indicador_id']}",
                  cls="hover:underline"),
                Span(f" · última cifra: {numero(actual)} ({anio})" if actual is not None else " · aún sin cifra",
                     cls=TextPresets.muted_sm))


def _reprogramaciones(auth, t, m):
    gestiona = _gestiona(auth, m)
    filas = []
    for r in t["reprogramaciones"]:
        tono = {"pendiente": "ambar", "aprobada": "verde", "rechazada": "gris"}[r["estado"]]
        resolver = Div(Button("Aprobar", type="button", cls=(ButtonT.primary, ButtonT.xs),
                              hx_post=f"{BASE}/reprogramaciones/{r['id']}/aprobar", hx_target="body",
                              hx_confirm=f"¿Aprobar el plazo nuevo ({formato.fecha(r['plazo_nuevo'])})?"),
                       Button("Rechazar", type="button", cls=(ButtonT.ghost, ButtonT.xs),
                              hx_get=f"{BASE}/reprogramaciones/{r['id']}/rechazar", hx_target=f"#{ID_MODAL}"),
                       cls="flex gap-2 mt-1") if gestiona and r["estado"] == "pendiente" else ""
        filas.append(Li(
            Div(Span(Span(formato.fecha(r["plazo_anterior"]), cls="line-through text-muted-foreground"), " → ",
                     Span(formato.fecha(r["plazo_nuevo"]), cls="font-medium")),
                insignia(am.ESTADOS_REPROGRAMACION[r["estado"]], tono), cls="flex flex-wrap items-center gap-2"),
            P(r["causa"], cls="text-sm whitespace-pre-line"),
            P(f"Pedida por {r['solicitante'] or '—'} el {formato.fecha_hora(r['solicitada_en'])}"
              + (f" · {am.ESTADOS_REPROGRAMACION[r['estado']].lower()} por {r['resolvio'] or '—'} el "
                 f"{formato.fecha_hora(r['resuelta_en'])}" if r["resuelta_en"] else ""), cls=TextPresets.muted_sm),
            P(r["respuesta"], cls="text-sm italic") if r["respuesta"] else "",
            A(UkIcon("folder-open", height=12, width=12), f" {r['evidencia_titulo']}",
              href=f"/calidad/evidencias/{r['evidencia_id']}", cls="text-xs text-primary hover:underline")
            if r["evidencia_id"] else "",
            resolver, cls="py-2 space-y-1"))
    abierta = t["estado"] in am.ABIERTAS
    boton = Button(UkIcon("calendar-clock", height=14, width=14),
                   "Reprogramar" if gestiona else "Pedir reprogramación", type="button", cls=(ButtonT.default, ButtonT.sm),
                   hx_get=f"{_url(t['id'])}/reprogramar", hx_target=f"#{ID_MODAL}") \
        if abierta and am.aprobado(m) and am.puede_avanzar(auth, t) and not t["reprogramacion_pendiente"] else ""
    if not filas and not boton:
        return ""
    return Card(Div(H3("Reprogramaciones", cls="text-base font-semibold"), boton,
                    cls="flex items-center justify-between gap-2 mb-1"),
                Ul(*filas, cls="divide-y divide-border") if filas else P("Sin reprogramaciones.", cls=TextPresets.muted_sm),
                cls="mt-6")


@rt(f"{BASE}/actividades/{{tid}}")
def get(auth, tid: int):
    t, m, error = _visible(auth, tid)
    if error:
        return error
    gestiona = _gestiona(auth, m)
    abierta = t["estado"] in am.ABIERTAS
    url = _url(tid)
    botones = []
    if gestiona and abierta:
        botones = [Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.default, ButtonT.sm),
                          hx_get=f"{url}/editar", hx_target=f"#{ID_MODAL}"),
                   Button(UkIcon("check", height=14, width=14), "Cumplida", cls=(ButtonT.default, ButtonT.sm),
                          hx_get=f"{url}/cumplir", hx_target=f"#{ID_MODAL}"),
                   Button("Cancelar la actividad", cls=(ButtonT.ghost, ButtonT.sm), hx_get=f"{url}/cancelar",
                          hx_target=f"#{ID_MODAL}")]
        if not t["avances"] and not t["reprogramaciones"]:
            botones.append(Button(UkIcon("trash-2", height=14, width=14), "Eliminar", cls=(ButtonT.ghost, ButtonT.sm),
                                  hx_delete=url, hx_target="body", hx_confirm="¿Eliminar la actividad?"))
    elif gestiona:
        botones = [Button("Reabrir", cls=(ButtonT.ghost, ButtonT.sm), hx_post=f"{url}/reabrir", hx_target="body",
                          hx_confirm="¿Reabrir la actividad?")]
    estado = (f"{am.ESTADOS[t['estado']]} el {formato.fecha(t['cumplida_en'])}" if t["cumplida_en"] else
              f"{am.ESTADOS[t['estado']]}: {t['motivo_cancelacion']}" if t["motivo_cancelacion"] else am.ESTADOS[t["estado"]])
    titulo = f"{t['codigo']} · {am.titulo(t['descripcion'])}" if t["codigo"] else am.titulo(t["descripcion"])
    return pagina(
        titulo[:80],
        A(UkIcon("arrow-left", height=14, width=14), f"{t['accion_codigo'] + ' · ' if t['accion_codigo'] else ''}{t['accion_titulo']}",
          href=f"{BASE}/acciones/{t['accion_id']}", cls="inline-flex items-center gap-1 text-sm text-primary mb-4"),
        Div(Div(H2(Span(t["codigo"], cls="font-mono text-muted-foreground mr-2") if t["codigo"] else "", am.titulo(t["descripcion"])),
                Div(insignia_semaforo(t["semaforo"]), insignia(t["prioridad_p"], "gris", titulo="Prioridad de la acción"),
                    insignia("Reprogramación por resolver", "ambar") if t["reprogramacion_pendiente"] else "",
                    cls="flex flex-wrap gap-2 mt-2"),
                Div(barra_avance(t["avance"], "Avance de la actividad"), cls="mt-3 max-w-md")),
            Div(*botones, cls="flex flex-wrap gap-2"), cls="flex flex-wrap items-start justify-between gap-4 mb-6"),
        Card(Div(Div(_dato("Responsable", t["responsable"] or "—"), _dato("Unidad responsable", t["unidad_responsable"] or "—"),
                     _dato("Estado", estado), cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                 Div(_dato("Inicio", formato.fecha(t["inicio"]) if t["inicio"] else "—"), _dato("Plazo", formato.fecha(t["plazo"])),
                     _dato("Último avance", formato.fecha(t["ultimo_avance"]) if t["ultimo_avance"] else "—"),
                     cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                 Div(_dato("Línea base", t["linea_base"] or "—"), _dato("Meta", t["meta"] or "—"),
                     _dato("Indicador", _cifra_indicador(t)), cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                 Div(_dato("Presupuesto", _texto_dinero(t["presupuesto"]), Span(f" · {t['fuente']}", cls=TextPresets.muted_sm)
                           if t["fuente"] else ""),
                     _dato("Medio de verificación", t["verificacion"] or "—"), _dato("Medio de difusión", t["difusion"] or "—"),
                     cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
                 _dato("Recursos", Span(am.detalle(t["descripcion"]), cls="whitespace-pre-line"))
                 if am.detalle(t["descripcion"]) else "",
                 cls="space-y-4")),
        _reprogramaciones(auth, t, m),
        Card(H3("Avances", cls="text-base font-semibold mb-2"),
             Ul(*[Li(Div(Span(formato.fecha(v["fecha"]), cls="font-medium"),
                         Span(f" · {v['porcentaje']} %", cls="font-medium") if v["porcentaje"] is not None else "",
                         Span(f" · {v['por']}", cls=TextPresets.muted_sm) if v["por"] else "",
                         _boton_quitar(auth, t, m, v)),
                     P(v["texto"], cls="text-sm whitespace-pre-line"),
                     A(UkIcon("folder-open", height=12, width=12), f" {v['evidencia_titulo']}",
                       href=f"/calidad/evidencias/{v['evidencia_id']}", cls="text-xs text-primary hover:underline")
                     if v["evidencia_id"] else "", cls="space-y-1 py-2") for v in t["lista_avances"]],
                cls="divide-y divide-border") if t["lista_avances"] else P("Aún sin avances.", cls=TextPresets.muted_sm),
             form_avance(t, m) if abierta and am.puede_avanzar(auth, t) else "", cls="mt-6"),
        usuario=auth)


def _boton_quitar(auth, t, m, v):
    if t["estado"] not in am.ABIERTAS or not (_gestiona(auth, m) or v["registrado_por"] == auth["id"]):
        return ""
    return Button(UkIcon("trash-2", height=12, width=12), cls=(ButtonT.ghost, ButtonT.xs), type="button",
                  aria_label="Quitar el avance", title="Quitar el avance",
                  hx_delete=f"{_url(t['id'])}/avances/{v['id']}", hx_target="body", hx_confirm="¿Quitar este avance?")


# --- Avances -------------------------------------------------------------------------------------------------------------------

@rt(f"{BASE}/actividades/{{tid}}/avances")
def post(auth, sess, tid: int, texto: str = "", fecha: str = "", porcentaje: str = "", evidencia_id: str = "",
         volver: str = ""):
    t, m, error = _visible(auth, tid)
    if error:
        return error
    if t["estado"] not in am.ABIERTAS or not am.puede_avanzar(auth, t):
        return _no_autorizado()
    volver = _volver_seguro(volver)
    x, errores = mejora.validar_avance({"texto": texto, "fecha": fecha, "porcentaje": porcentaje,
                                        "evidencia_id": evidencia_id}, m["id"])
    if errores:
        return _modal_avance(t, m, volver, x, errores) if volver else form_avance(t, m, x, errores)
    am.registrar_avance(t, x, auth["id"])
    auditar(auth["id"], "avance_actividad_mejora", "actividad_mejora", tid, x["texto"][:80])
    add_toast(sess, "Avance registrado.", "success")
    return Redirect(volver or _url(tid))


@rt(f"{BASE}/actividades/{{tid}}/avances/{{vid}}")
def delete(auth, sess, tid: int, vid: int):
    t, m, error = _visible(auth, tid)
    v = mejora.avance(vid)
    if error or v is None or v["actividad_id"] != tid:
        return error or _no_encontrado()
    if t["estado"] not in am.ABIERTAS or not (_gestiona(auth, m) or v["registrado_por"] == auth["id"]):
        return _no_autorizado()
    mejora.eliminar_avance(vid)
    auditar(auth["id"], "quitar_avance_actividad_mejora", "actividad_mejora", tid, v["texto"][:80])
    add_toast(sess, "Avance quitado.", "success")
    return Redirect(_url(tid))


# --- Estados ---------------------------------------------------------------------------------------------------------------------

@rt(f"{BASE}/actividades/{{tid}}/cumplir")
def get(auth, tid: int):
    t, m, error = _gestionable(auth, tid)
    if error:
        return error
    return modal("Marcar como cumplida",
                 Form(LabelInput("Fecha en que se cumplió", id="fecha", type="date", required=True),
                      P(f"Plazo: {formato.fecha(t['plazo'])}. Conviene registrar antes el último avance con su evidencia.",
                        cls=TextPresets.muted_sm),
                      _botones_modal("Marcar cumplida"), hx_post=f"{_url(tid)}/cumplir", hx_target="body", cls="space-y-4"))


@rt(f"{BASE}/actividades/{{tid}}/cumplir")
def post(auth, sess, tid: int, fecha: str = ""):
    t, m, error = _gestionable(auth, tid)
    if error:
        return error
    errores = am.cumplir(t, fecha)
    if errores:
        add_toast(sess, " ".join(errores), "error")
    else:
        auditar(auth["id"], "cumplir_actividad_mejora", "actividad_mejora", tid, formato.fecha(fecha))
        add_toast(sess, "Actividad cumplida.", "success")
    return Redirect(_url(tid))


@rt(f"{BASE}/actividades/{{tid}}/cancelar")
def get(auth, tid: int):
    t, m, error = _gestionable(auth, tid)
    if error:
        return error
    return modal("Cancelar la actividad",
                 Form(LabelTextArea("Motivo", id="motivo", rows=3, required=True),
                      _botones_modal("Cancelar la actividad"), hx_post=f"{_url(tid)}/cancelar", hx_target="body",
                      cls="space-y-4"))


@rt(f"{BASE}/actividades/{{tid}}/cancelar")
def post(auth, sess, tid: int, motivo: str = ""):
    t, m, error = _gestionable(auth, tid)
    if error:
        return error
    errores = am.cancelar(t, motivo)
    if errores:
        add_toast(sess, " ".join(errores), "error")
    else:
        auditar(auth["id"], "cancelar_actividad_mejora", "actividad_mejora", tid, motivo.strip()[:200])
        add_toast(sess, "Actividad cancelada.", "success")
    return Redirect(_url(tid))


@rt(f"{BASE}/actividades/{{tid}}/reabrir")
def post(auth, sess, tid: int):
    t, m, error = _gestionable(auth, tid)
    if error:
        return error
    am.reabrir(t)
    auditar(auth["id"], "reabrir_actividad_mejora", "actividad_mejora", tid, t["descripcion"][:120])
    add_toast(sess, "Actividad reabierta.", "success")
    return Redirect(_url(tid))


@rt(f"{BASE}/actividades/{{tid}}")
def delete(auth, sess, tid: int):
    t, m, error = _gestionable(auth, tid)
    if error:
        return error
    if not am.eliminar(t):
        add_toast(sess, "La actividad tiene avances o reprogramaciones: cancélela, con su motivo.", "error")
        return Redirect(_url(tid))
    auditar(auth["id"], "eliminar_actividad_mejora", "actividad_mejora", tid, t["descripcion"][:120])
    add_toast(sess, "Actividad eliminada.", "success")
    return Redirect(f"{BASE}/acciones/{t['accion_id']}")


# --- Reprogramaciones --------------------------------------------------------------------------------------------------------------

def _form_reprogramar(auth, t, m, d=None, errores=()):
    d = d or {}
    evs = [(e["id"], e["titulo"]) for e in evidencias.listar(m["id"])]
    directo = _gestiona(auth, m)
    return modal(
        "Reprogramar la actividad" if directo else "Pedir una reprogramación",
        Form(mensaje_error(*errores),
             P(f"Plazo actual: {formato.fecha(t['plazo'])}. "
               + ("Como gestiona el plan, la reprogramación queda aprobada al guardarla." if directo else
                  "La Dirección de Carrera recibirá su pedido y lo aprobará o rechazará; se le avisará."), cls="text-sm"),
             LabelInput("Plazo nuevo", id="plazo_nuevo", type="date", value=d.get("plazo_nuevo") or "", required=True),
             LabelTextArea("Causa", id="causa", value=d.get("causa") or "", rows=3, required=True,
                           placeholder="Qué impidió cumplir en el plazo y qué se hará para cumplir en el nuevo."),
             _select("Evidencia de la causa (opcional)", "evidencia_id", evs, d.get("evidencia_id"), "—"),
             _botones_modal("Reprogramar" if directo else "Enviar el pedido"),
             hx_post=f"{_url(t['id'])}/reprogramar", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt(f"{BASE}/actividades/{{tid}}/reprogramar")
def get(auth, tid: int):
    t, m, error = _visible(auth, tid)
    if error:
        return error
    if not am.puede_avanzar(auth, t):
        return _no_autorizado()
    return _form_reprogramar(auth, t, m)


@rt(f"{BASE}/actividades/{{tid}}/reprogramar")
def post(auth, sess, tid: int, plazo_nuevo: str = "", causa: str = "", evidencia_id: str = ""):
    t, m, error = _visible(auth, tid)
    if error:
        return error
    if not am.puede_avanzar(auth, t):
        return _no_autorizado()
    d = {"plazo_nuevo": plazo_nuevo, "causa": causa, "evidencia_id": evidencia_id}
    rid, errores = am.solicitar_reprogramacion(auth, t, d)
    if errores:
        return _form_reprogramar(auth, t, m, d, errores)
    auditar(auth["id"], "reprogramar_actividad_mejora", "actividad_mejora", tid,
            f"{formato.fecha(t['plazo'])} → {formato.fecha(plazo_nuevo)}")
    add_toast(sess, "Plazo reprogramado." if _gestiona(auth, m) else "Pedido enviado a la Dirección de Carrera.", "success")
    return Redirect(_url(tid))


def _reprogramacion_gestionable(auth, rid):
    r = am.reprogramacion(rid)
    if r is None:
        return None, _no_encontrado()
    return r, (None if _gestiona(auth, marco.obtener(r["marco_id"])) else _no_autorizado())


@rt(f"{BASE}/reprogramaciones/{{rid}}/aprobar")
def post(auth, sess, rid: int):
    r, error = _reprogramacion_gestionable(auth, rid)
    if error:
        return error
    errores = am.resolver_reprogramacion(r, True, auth["id"])
    if errores:
        add_toast(sess, " ".join(errores), "error")
    else:
        auditar(auth["id"], "aprobar_reprogramacion_mejora", "actividad_mejora", r["actividad_id"],
                f"{formato.fecha(r['plazo_anterior'])} → {formato.fecha(r['plazo_nuevo'])}")
        add_toast(sess, "Reprogramación aprobada: el plazo cambió.", "success")
    return Redirect(_url(r["actividad_id"]))


@rt(f"{BASE}/reprogramaciones/{{rid}}/rechazar")
def get(auth, rid: int):
    r, error = _reprogramacion_gestionable(auth, rid)
    if error:
        return error
    return modal("Rechazar la reprogramación",
                 Form(P(f"Se pedía mover el plazo del {formato.fecha(r['plazo_anterior'])} al {formato.fecha(r['plazo_nuevo'])}.",
                        cls="text-sm"),
                      LabelTextArea("Motivo del rechazo", id="respuesta", rows=3, required=True),
                      P("Se avisará a quien la pidió.", cls=TextPresets.muted_sm),
                      _botones_modal("Rechazar"), hx_post=f"{BASE}/reprogramaciones/{rid}/rechazar", hx_target="body",
                      cls="space-y-4"))


@rt(f"{BASE}/reprogramaciones/{{rid}}/rechazar")
def post(auth, sess, rid: int, respuesta: str = ""):
    r, error = _reprogramacion_gestionable(auth, rid)
    if error:
        return error
    errores = am.resolver_reprogramacion(r, False, auth["id"], respuesta)
    if errores:
        add_toast(sess, " ".join(errores), "error")
    else:
        auditar(auth["id"], "rechazar_reprogramacion_mejora", "actividad_mejora", r["actividad_id"], respuesta.strip()[:200])
        add_toast(sess, "Reprogramación rechazada.", "success")
    return Redirect(_url(r["actividad_id"]))


__all__ = ["H2", "Card"]
