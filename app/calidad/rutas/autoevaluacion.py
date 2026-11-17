"""Autoevaluación con el marco de calidad (PLAN §57, etapa 5): lista, proceso con avance por dimensión, juicio de cada
criterio con sus indicadores y evidencias a la vista, síntesis por dimensión, análisis global, conclusión, e informe
imprimible y en XLSX."""
import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Div, H1, Li, P, Redirect, Response, Span, Table, Tbody, Td, Th, Thead, Tr,
                             Ul)
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, Form, LabelInput, LabelTextArea, TextPresets, \
    UkIcon

from app.calidad import autoevaluacion as ae
from app.calidad import evidencias, indicadores, marco
from app.calidad.rutas.indicadores import cifra, numero
from app.comun.componentes.informe import ESTILO_IMPRESION, XLSX, _archivo, barra, descarga, hoja
from app.comun import unidades
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina, campo
from app.comun.componentes.registros import fecha_local, insignia
from app.comun.db import auditar
from app.ia import catalogo as ia_catalogo, servicio as ia
from app.ia.rutas.panel import bloque as bloque_ia, respuesta_pedido

rt = APIRouter()
BASE = "/calidad/autoevaluaciones"
TONOS_NIVEL = ("rojo", "ambar", "azul", "verde")   # del más bajo al más alto (se reparten si la escala tiene otro largo)


def _no_autorizado():
    return Response("No autorizado", status_code=403)


def _no_encontrado():
    return Response("No encontrado", status_code=404)


def _marco():
    return marco.de_unidad(unidades.carrera())


def _tono(nivel, escala):
    if nivel is None or not escala:
        return "gris"
    pos = [n["valor"] for n in escala].index(nivel) if nivel in [n["valor"] for n in escala] else 0
    return TONOS_NIVEL[round(pos * (len(TONOS_NIVEL) - 1) / max(1, len(escala) - 1))]


def insignia_nivel(j, escala):
    if not j or j["nivel"] is None:
        return insignia("Sin juzgar", "gris")
    return insignia(f"{j['nivel']}. {j['nivel_nombre']}", _tono(j["nivel"], escala))


def _lineas(texto):
    items = [x.strip(" -•\t") for x in (texto or "").splitlines() if x.strip(" -•\t")]
    return Ul(*[Li(x) for x in items], cls="list-disc pl-5 space-y-1") if items else P("—", cls=TextPresets.muted_sm)


def _estado(a):
    return insignia(ae.ESTADOS[a["estado"]], "verde" if a["estado"] == "concluida" else "azul",
                    icono="lock" if a["estado"] == "concluida" else None)


def _visible(auth, aid, accion="ver_autoevaluacion"):
    a = ae.obtener(aid)
    if a is None:
        return None, _no_encontrado()
    return a, (None if marco.puede(auth, accion, marco.obtener(a["marco_id"])) else _no_autorizado())


def _editable(auth, aid, accion="registrar_juicios_calidad"):
    """La autoevaluación, si la cuenta puede la acción y aún está en curso."""
    a, error = _visible(auth, aid, accion)
    if error:
        return a, error
    return a, (None if a["estado"] == "en_curso" else Response("La autoevaluación está concluida.", status_code=409))


def _botones_modal():
    return Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
               Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2")


# --- Lista y alta ---------------------------------------------------------------------------------------------

@rt(BASE)
def get(auth):
    m = _marco()
    if not marco.puede(auth, "ver_autoevaluacion", m):
        return _no_autorizado()
    gestiona = marco.puede(auth, "gestionar_autoevaluacion", m)
    lista = ae.listar(m["id"])
    return pagina(
        "Autoevaluación",
        Div(Div(H2("Autoevaluación"), P(m["nombre"], " · versión ", m["version"], cls=TextPresets.muted_sm)),
            Button(UkIcon("plus", height=14, width=14), "Nueva autoevaluación", cls=(ButtonT.primary, ButtonT.sm),
                   hx_get=f"{BASE}/nueva", hx_target=f"#{ID_MODAL}")
            if gestiona and not ae.en_curso(m["id"]) else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-4"),
        P("En la autoevaluación, la Comisión de calidad juzga cada criterio del marco en su escala, con los indicadores y "
          "las evidencias a la vista, y anota fortalezas y debilidades; después sintetiza cada dimensión y hace el análisis "
          "global. Las debilidades son el punto de partida del plan de mejora.", cls="text-sm max-w-3xl mb-6"),
        Div(Table(Thead(Tr(Th("Autoevaluación"), Th("Periodo", cls="w-28"), Th("Estado", cls="w-32"),
                           Th("Criterios juzgados", cls="w-40"))),
                  Tbody(*[Tr(Td(A(a["nombre"], href=f"{BASE}/{a['id']}", cls="font-medium hover:underline")),
                             Td(f"{a['desde_anio']}–{a['hasta_anio']}"), Td(_estado(a)),
                             Td(f"{a['juzgados']} de {a['criterios']}")) for a in lista]),
                  cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[36rem]"),
            cls="overflow-x-auto")
        if lista else P("Aún no hay autoevaluaciones.", cls=TextPresets.muted_sm),
        usuario=auth)


def form_datos(d, url, metodo, errores=()):
    return modal(
        "Autoevaluación",
        Form(mensaje_error(*errores),
             LabelInput("Nombre", id="nombre", value=d.get("nombre") or "", required=True, maxlength=200,
                        placeholder="Autoevaluación 2026"),
             Div(LabelInput("Periodo evaluado: desde el año", id="desde_anio", type="number", min=2000,
                            value=d.get("desde_anio") or ""),
                 LabelInput("hasta el año", id="hasta_anio", type="number", min=2000, value=d.get("hasta_anio") or ""),
                 cls="grid grid-cols-2 gap-4"),
             P("Los indicadores se muestran en los años del periodo. Conviene cerrar antes esos años en el tablero de "
               "indicadores, para que sus cifras no cambien durante la autoevaluación.", cls=TextPresets.muted_sm),
             _botones_modal(), **{f"hx_{metodo}": url}, hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt(f"{BASE}/nueva")
def get(auth):
    m = _marco()
    if not marco.puede(auth, "gestionar_autoevaluacion", m):
        return _no_autorizado()
    anios = indicadores.anios_de(m, max(2000, indicadores.anios_de(m)[-1] - 1))
    return form_datos({"nombre": f"Autoevaluación {anios[-1] + 1}", "desde_anio": anios[0], "hasta_anio": anios[-1]},
                      BASE, "post")


@rt(BASE)
def post(auth, sess, nombre: str = "", desde_anio: str = "", hasta_anio: str = ""):
    m = _marco()
    if not marco.puede(auth, "gestionar_autoevaluacion", m):
        return _no_autorizado()
    x, errores = ae.validar({"nombre": nombre, "desde_anio": desde_anio, "hasta_anio": hasta_anio})
    aid = None if errores else ae.crear(m["id"], x, auth["id"])
    if not errores and aid is None:
        errores = ["Ya hay una autoevaluación en curso: concluya o elimine esa primero."]
    if errores:
        return form_datos(x, BASE, "post", errores)
    auditar(auth["id"], "crear_autoevaluacion", "autoevaluacion", aid, x["nombre"])
    add_toast(sess, "Autoevaluación creada.", "success")
    return Redirect(f"{BASE}/{aid}")


# --- La autoevaluación ------------------------------------------------------------------------------------------

def _dimension(a, d, escala, registra):
    url = f"{BASE}/{a['id']}"
    return Card(
        Div(H3(Span(d["codigo"], cls="font-mono mr-2"), d["nombre"], cls="text-base font-semibold flex-1"),
            Button(UkIcon("pencil", height=14, width=14), "Síntesis", cls=(ButtonT.ghost, ButtonT.sm),
                   hx_get=f"{url}/dimensiones/{d['id']}/sintesis", hx_target=f"#{ID_MODAL}") if registra else "",
            cls="flex items-start gap-3 mb-2"),
        Div(Table(Tbody(*[Tr(
            Td(A(Span(c["codigo"], cls="font-mono mr-2"), c["nombre"], href=f"{url}/criterios/{c['id']}",
                 cls="hover:underline")),
            Td(insignia_nivel(c["juicio"], escala), cls="w-48"),
            Td(Span(UkIcon("folder-open", height=12, width=12), f" {len(c['evidencias'])}",
                    cls="inline-flex items-center gap-1", title="Evidencias del criterio"),
               Span(UkIcon("gauge", height=12, width=12), f" {len(c['indicadores'])}",
                    cls="inline-flex items-center gap-1 ml-3", title="Indicadores activos"),
               cls="w-28 text-xs text-muted-foreground")) for c in d["criterios"]]),
            cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[36rem]"), cls="overflow-x-auto"),
        Div(Div("Síntesis de la dimensión", cls="text-xs font-medium mt-3"),
            P(d["sintesis"], cls="text-sm whitespace-pre-line")) if d["sintesis"] else "",
        id=f"dimension-{d['id']}")


@rt(f"{BASE}/{{aid}}")
def get(auth, aid: int):
    a, error = _visible(auth, aid)
    if error:
        return error
    m = marco.obtener(a["marco_id"])
    en_curso = a["estado"] == "en_curso"
    gestiona = marco.puede(auth, "gestionar_autoevaluacion", m)
    registra = en_curso and marco.puede(auth, "registrar_juicios_calidad", m)
    escala = marco.escala(m["id"])
    ar = ae.arbol(a)
    hechos, total = ae.avance(a)
    dist = ae.distribucion(ar, escala)[-1]["niveles"]
    url = f"{BASE}/{aid}"
    acciones = []
    if gestiona and en_curso:
        acciones += [Button(UkIcon("pencil", height=14, width=14), "Datos", cls=(ButtonT.default, ButtonT.sm),
                            hx_get=f"{url}/editar", hx_target=f"#{ID_MODAL}"),
                     Button(UkIcon("lock", height=14, width=14), "Concluir", cls=(ButtonT.default, ButtonT.sm),
                            hx_post=f"{url}/concluir", hx_target="body",
                            hx_confirm="¿Concluir la autoevaluación? Sus juicios y síntesis quedarán fijos."),
                     Button(UkIcon("trash-2", height=14, width=14), "Eliminar", cls=(ButtonT.ghost, ButtonT.sm),
                            hx_delete=url, hx_target="body",
                            hx_confirm="¿Eliminar la autoevaluación en curso con todos sus juicios?")]
    elif gestiona:
        acciones.append(Button("Reabrir", cls=(ButtonT.ghost, ButtonT.sm), hx_post=f"{url}/reabrir", hx_target="body",
                               hx_confirm="¿Reabrir la autoevaluación? Se podrán volver a cambiar sus juicios."))
    return pagina(
        a["nombre"],
        A(UkIcon("arrow-left", height=14, width=14), "Autoevaluaciones", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary mb-4"),
        Div(Div(H2(a["nombre"]),
                P(f"Periodo evaluado {a['desde_anio']}–{a['hasta_anio']} · {m['nombre']}, versión {m['version']}",
                  cls=TextPresets.muted_sm),
                Div(_estado(a), Span(f"Concluida el {fecha_local(a['concluida_en'])}"
                                     + (f" por {a['concluida_por_nombre']}" if a["concluida_por_nombre"] else ""),
                                     cls=TextPresets.muted_sm) if a["concluida_en"] else "",
                    cls="flex flex-wrap items-center gap-2 mt-2")),
            Div(*acciones, A(UkIcon("file-text", height=14, width=14), "Informe", href=f"{url}/informe",
                             cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1"),
                descarga("XLSX", f"{url}/xlsx"), cls="flex flex-wrap gap-2"),
            cls="flex flex-wrap items-start justify-between gap-4 mb-6"),
        Card(Div(Div(f"{hechos} de {total}", cls="text-2xl font-semibold"),
                 Div("criterios juzgados", cls=TextPresets.muted_sm), cls="text-center"),
             Div(*[insignia(f"{n['nombre']}: {dist[n['valor']]}", _tono(n["valor"], escala)) for n in escala],
                 insignia(f"Sin juzgar: {dist[None]}", "gris"), cls="flex flex-wrap justify-center gap-2"),
             fh.Progress(value=str(hechos), max=str(max(total, 1)), cls="uk-progress w-full",
                         aria_label="Criterios juzgados"),
             cls="space-y-3 mb-6"),
        Div(*[_dimension(a, d, escala, registra) for d in ar if d["criterios"]], cls="space-y-6"),
        Card(Div(H3("Análisis global", cls="text-base font-semibold flex-1"),
                 Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.ghost, ButtonT.sm),
                        hx_get=f"{url}/analisis", hx_target=f"#{ID_MODAL}") if registra else "",
                 cls="flex items-start gap-3 mb-2"),
             P(a["analisis_global"], cls="text-sm whitespace-pre-line") if a["analisis_global"] else
             P("Aún sin análisis global.", cls=TextPresets.muted_sm), cls="mt-6"),
        usuario=auth)


@rt(f"{BASE}/{{aid}}/editar")
def get(auth, aid: int):
    a, error = _editable(auth, aid, "gestionar_autoevaluacion")
    return error or form_datos(a, f"{BASE}/{aid}", "put")


@rt(f"{BASE}/{{aid}}")
def put(auth, sess, aid: int, nombre: str = "", desde_anio: str = "", hasta_anio: str = ""):
    a, error = _editable(auth, aid, "gestionar_autoevaluacion")
    if error:
        return error
    x, errores = ae.validar({"nombre": nombre, "desde_anio": desde_anio, "hasta_anio": hasta_anio})
    if errores:
        return form_datos(x, f"{BASE}/{aid}", "put", errores)
    ae.actualizar(aid, x)
    auditar(auth["id"], "editar_autoevaluacion", "autoevaluacion", aid, x["nombre"])
    add_toast(sess, "Datos guardados.", "success")
    return Redirect(f"{BASE}/{aid}")


@rt(f"{BASE}/{{aid}}/concluir")
def post(auth, sess, aid: int):
    a, error = _visible(auth, aid, "gestionar_autoevaluacion")
    if error:
        return error
    errores = ae.concluir(a, auth["id"])
    if errores:
        add_toast(sess, " ".join(errores), "error")
    else:
        auditar(auth["id"], "concluir_autoevaluacion", "autoevaluacion", aid, a["nombre"])
        add_toast(sess, "Autoevaluación concluida.", "success")
    return Redirect(f"{BASE}/{aid}")


@rt(f"{BASE}/{{aid}}/reabrir")
def post(auth, sess, aid: int):
    a, error = _visible(auth, aid, "gestionar_autoevaluacion")
    if error:
        return error
    errores = ae.reabrir(a)
    if errores:
        add_toast(sess, " ".join(errores), "error")
    else:
        auditar(auth["id"], "reabrir_autoevaluacion", "autoevaluacion", aid, a["nombre"])
        add_toast(sess, "Autoevaluación reabierta.", "success")
    return Redirect(f"{BASE}/{aid}")


@rt(f"{BASE}/{{aid}}")
def delete(auth, sess, aid: int):
    a, error = _visible(auth, aid, "gestionar_autoevaluacion")
    if error:
        return error
    if not ae.eliminar(a):
        add_toast(sess, "Una autoevaluación concluida no se elimina.", "error")
        return Redirect(f"{BASE}/{aid}")
    auditar(auth["id"], "eliminar_autoevaluacion", "autoevaluacion", aid, a["nombre"])
    add_toast(sess, "Autoevaluación eliminada.", "success")
    return Redirect(BASE)


# --- Juicio de un criterio -----------------------------------------------------------------------------------------

def _criterio_de(a, cid):
    c = marco.criterio(cid)
    return c if c and c["marco_id"] == a["marco_id"] else None


def _vecinos(a, cid):
    ids = [c["id"] for c in evidencias.criterios_del_marco(a["marco_id"])]
    i = ids.index(cid)
    return (ids[i - 1] if i > 0 else None), (ids[i + 1] if i + 1 < len(ids) else None)


def _indicadores_del_criterio(a, c):
    anios = ae.anios(a)
    inds = [i for d in marco.arbol(a["marco_id"], inactivos=False) for x in d["criterios"] if x["id"] == c["id"]
            for i in x["indicadores"]]
    if not inds:
        return P("El criterio no tiene indicadores activos.", cls=TextPresets.muted_sm)
    filas = []
    for i in inds:
        serie = indicadores.serie({**i, "marco_id": a["marco_id"]}, anios)
        filas.append(Tr(Td(A(i["codigo"], href=f"/calidad/marco/indicadores/{i['id']}", cls="font-mono hover:underline"),
                           title=i["nombre"]), Td(i["nombre"]),
                        *[Td(cifra(serie[y], i["unidad_medida"]), cls="text-right whitespace-nowrap") for y in anios]))
    return Div(Table(Thead(Tr(Th("Código", cls="w-20"), Th("Indicador"),
                              *[Th(str(y), cls="w-20 text-right") for y in anios])), Tbody(*filas),
                     cls="uk-table uk-table-divider uk-table-small text-sm table-fixed min-w-[36rem]"),
               cls="overflow-x-auto")


def _evidencias_del_criterio(a, c):
    evs = evidencias.listar(a["marco_id"], c["id"])
    if not evs:
        return P("El criterio aún no tiene evidencias.", cls=TextPresets.muted_sm)
    return Ul(*[Li(A(e["titulo"], href=f"/calidad/evidencias/{e['id']}", cls="hover:underline"), " ",
                   insignia("Vencida", "ambar") if e["vencida"] else "", cls="text-sm") for e in evs],
              cls="space-y-1")


def servicio_activo():
    return ia.activa(ia_catalogo.NARRATIVA.clave)


def form_juicio(a, c, j, escala, errores=()):
    actual = str(j.get("nivel")) if j.get("nivel") is not None else ""
    return Form(
        mensaje_error(*errores),
        campo("Nivel", *[fh.Label(fh.Input(type="radio", name="nivel", value=str(n["valor"]), checked=str(n["valor"]) == actual,
                                cls="uk-radio mt-1"),
                       Span(Span(f"{n['valor']}. {n['nombre']}", cls="font-medium"),
                            Span(f": {n['descripcion']}", cls=TextPresets.muted_sm) if n["descripcion"] else ""),
                       cls="flex items-start gap-2 text-sm") for n in escala],
            fh.Label(fh.Input(type="radio", name="nivel", value="", checked=actual == "", cls="uk-radio mt-1"),
                     Span("Aún sin juzgar", cls=TextPresets.muted_sm), cls="flex items-start gap-2 text-sm"),
            cls="space-y-2"),
        LabelTextArea("Juicio fundado (por qué ese nivel, con referencia a indicadores y evidencias)", id="juicio",
                      value=j.get("juicio") or "", rows=5),
        LabelTextArea("Fortalezas (una por línea)", id="fortalezas", value=j.get("fortalezas") or "", rows=3),
        LabelTextArea("Debilidades (una por línea; el plan de mejora partirá de ellas)", id="debilidades",
                      value=j.get("debilidades") or "", rows=3),
        Div(Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end"),
        hx_post=f"{BASE}/{a['id']}/criterios/{c['id']}", hx_target="#juicio", hx_select="#juicio", hx_swap="outerHTML",
        cls="space-y-4", id="juicio")


def _juicio_leido(j, escala):
    if not j:
        return P("Sin juicio.", cls=TextPresets.muted_sm)
    return Div(insignia_nivel(j, escala),
               Div(Div("Juicio", cls="text-xs font-medium"), P(j["juicio"] or "—", cls="text-sm whitespace-pre-line")),
               Div(Div("Fortalezas", cls="text-xs font-medium"), _lineas(j["fortalezas"]), cls="text-sm"),
               Div(Div("Debilidades", cls="text-xs font-medium"), _lineas(j["debilidades"]), cls="text-sm"),
               cls="space-y-3", id="juicio")


@rt(f"{BASE}/{{aid}}/criterios/{{cid}}")
def get(auth, aid: int, cid: int):
    a, error = _visible(auth, aid)
    if error:
        return error
    c = _criterio_de(a, cid)
    if c is None:
        return _no_encontrado()
    m = marco.obtener(a["marco_id"])
    escala = marco.escala(m["id"])
    registra = a["estado"] == "en_curso" and marco.puede(auth, "registrar_juicios_calidad", m)
    j = ae.juicios(aid).get(cid) or {}
    antes, despues = _vecinos(a, cid)
    url = f"{BASE}/{aid}"
    return pagina(
        f"{c['codigo']} {c['nombre']}",
        Div(A(UkIcon("arrow-left", height=14, width=14), a["nombre"], href=f"{url}#dimension-{c['dimension_id']}",
              cls="inline-flex items-center gap-1 text-sm text-primary"),
            Div(A("← Anterior", href=f"{url}/criterios/{antes}", cls="text-sm text-primary") if antes else "",
                A("Siguiente →", href=f"{url}/criterios/{despues}", cls="text-sm text-primary") if despues else "",
                cls="flex gap-4"),
            cls="flex flex-wrap justify-between gap-2 mb-4"),
        H2(Span(c["codigo"], cls="font-mono mr-2"), c["nombre"]),
        P(f"{c['dimension_codigo']} {c['dimension_nombre']}", cls=TextPresets.muted_sm),
        P(c["descripcion"], cls="text-sm mt-2 max-w-3xl") if c["descripcion"] else "",
        Card(H3("Indicadores", cls="text-base font-semibold mb-2"), _indicadores_del_criterio(a, c), cls="mt-6"),
        Div(Card(H3("Evidencias", cls="text-base font-semibold mb-2"), _evidencias_del_criterio(a, c),
                 Div(bloque_ia(ia_catalogo.EVIDENCIAS.clave, f"evidencias:{aid}:{cid}", auth,
                               f"{BASE}/{aid}/criterios/{cid}/ia/evidencias", f"{BASE}/{aid}/criterios/{cid}",
                               "Sugerir evidencias con IA"), cls="mt-3") if registra else "",
                 cls="min-w-0"),
            Card(H3("Juicio", cls="text-base font-semibold mb-3"),
                 Div(bloque_ia(ia_catalogo.NARRATIVA.clave, f"juicio:{aid}:{cid}", auth,
                               f"{BASE}/{aid}/criterios/{cid}/ia/juicio", f"{BASE}/{aid}/criterios/{cid}",
                               "Borrador del juicio con IA"),
                     P("Al aprobarlo reemplaza el texto del juicio; el nivel lo asigna la Comisión.",
                       cls="text-xs text-muted-foreground mt-1 no-imprimir") if servicio_activo() else "",
                     cls="mb-4") if registra else "",
                 form_juicio(a, c, j, escala) if registra else _juicio_leido(j or None, escala),
                 P(f"Última modificación: {fecha_local(j['actualizado_en'])}"
                   + (f" por {j['por']}" if j.get("por") else ""), cls=(TextPresets.muted_sm, "mt-3"))
                 if j.get("actualizado_en") else "", cls="lg:col-span-2"),
            cls="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6 items-start"),
        usuario=auth)


@rt(f"{BASE}/{{aid}}/criterios/{{cid}}")
def post(auth, sess, aid: int, cid: int, nivel: str = "", juicio: str = "", fortalezas: str = "",
         debilidades: str = ""):
    a, error = _editable(auth, aid)
    if error:
        return error
    c = _criterio_de(a, cid)
    if c is None:
        return _no_encontrado()
    escala = marco.escala(a["marco_id"])
    x, errores = ae.validar_juicio({"nivel": nivel, "juicio": juicio, "fortalezas": fortalezas,
                                    "debilidades": debilidades}, escala)
    if errores:
        return form_juicio(a, c, x, escala, errores)
    ae.guardar_juicio(aid, cid, x, auth["id"])
    auditar(auth["id"], "juicio_criterio_calidad", "autoevaluacion", aid,
            f"{c['codigo']}: {x['nivel_nombre'] or 'sin nivel'}")
    add_toast(sess, f"Juicio de {c['codigo']} guardado.", "success")
    return Redirect(f"{BASE}/{aid}/criterios/{cid}")


# --- Síntesis y análisis global ------------------------------------------------------------------------------------

def _form_texto(titulo, etiqueta, valor, url, ayuda=""):
    return modal(titulo, Form(LabelTextArea(etiqueta, id="texto", value=valor or "", rows=10),
                              P(ayuda, cls=TextPresets.muted_sm) if ayuda else "", _botones_modal(),
                              hx_put=url, hx_target=f"#{ID_MODAL}", cls="space-y-4"), ancho="max-w-2xl")


@rt(f"{BASE}/{{aid}}/dimensiones/{{did}}/sintesis")
def get(auth, aid: int, did: int):
    a, error = _editable(auth, aid)
    if error:
        return error
    d = marco.dimension(did)
    if d is None or d["marco_id"] != a["marco_id"]:
        return _no_encontrado()
    return _form_texto(f"Síntesis de {d['codigo']}", f"{d['codigo']} {d['nombre']}", ae.sintesis(aid).get(did),
                       f"{BASE}/{aid}/dimensiones/{did}/sintesis",
                       "Principales fortalezas y debilidades de la dimensión y el juicio de conjunto.")


@rt(f"{BASE}/{{aid}}/dimensiones/{{did}}/sintesis")
def put(auth, sess, aid: int, did: int, texto: str = ""):
    a, error = _editable(auth, aid)
    if error:
        return error
    d = marco.dimension(did)
    if d is None or d["marco_id"] != a["marco_id"]:
        return _no_encontrado()
    ae.guardar_sintesis(aid, did, texto, auth["id"])
    auditar(auth["id"], "sintesis_dimension_calidad", "autoevaluacion", aid, d["codigo"])
    add_toast(sess, f"Síntesis de {d['codigo']} guardada.", "success")
    return Redirect(f"{BASE}/{aid}#dimension-{did}")


@rt(f"{BASE}/{{aid}}/analisis")
def get(auth, aid: int):
    a, error = _editable(auth, aid)
    return error or _form_texto("Análisis global", "Análisis global", a["analisis_global"], f"{BASE}/{aid}/analisis",
                                "Balance de la Carrera en su conjunto: logros, problemas principales y prioridades.")


@rt(f"{BASE}/{{aid}}/analisis")
def put(auth, sess, aid: int, texto: str = ""):
    a, error = _editable(auth, aid)
    if error:
        return error
    ae.guardar_analisis(aid, texto)
    auditar(auth["id"], "analisis_global_calidad", "autoevaluacion", aid, a["nombre"])
    add_toast(sess, "Análisis global guardado.", "success")
    return Redirect(f"{BASE}/{aid}")


# --- Informe --------------------------------------------------------------------------------------------------

def documento(a, m):
    escala = marco.escala(m["id"])
    ar = ae.arbol(a, cifras=True)
    anios = ae.anios(a)
    dist = ae.distribucion(ar, escala)
    borrador = a["estado"] != "concluida"
    cab_dist = Thead(Tr(Th("Dimensión"), *[Th(n["nombre"], cls="text-right") for n in escala],
                        Th("Sin juzgar", cls="text-right")))
    partes = [
        H1(f"Informe de autoevaluación: {a['nombre']}"),
        P(f"SIAC de la Carrera · periodo evaluado {a['desde_anio']}–{a['hasta_anio']} · {m['nombre']}, versión "
          f"{m['version']}", cls="apagado text-sm"),
        P("Borrador: la autoevaluación aún está en curso." if borrador else
          f"Concluida el {fecha_local(a['concluida_en'])}.", cls="text-sm font-medium mt-1"),
        fh.H2("Escala de valoración"),
        Ul(*[Li(Span(f"{n['valor']}. {n['nombre']}", cls="font-medium"),
                f": {n['descripcion']}" if n["descripcion"] else "") for n in escala], cls="text-sm space-y-1"),
        fh.H2("Resumen"),
        Div(Table(cab_dist, Tbody(*[Tr(Td(f"{x['codigo']} {x['nombre']}".strip(),
                                          cls="font-medium" if not x["codigo"] else ""),
                                       *[Td(str(x["niveles"][n["valor"]]), cls="text-right") for n in escala],
                                       Td(str(x["niveles"][None]), cls="text-right")) for x in dist])),
            cls="overflow-x-auto"),
    ]
    for d in ar:
        if not d["criterios"]:
            continue
        partes += [fh.H2(f"{d['codigo']} {d['nombre']}"),
                   P(d["sintesis"], cls="text-sm whitespace-pre-line") if d["sintesis"] else
                   P("Sin síntesis de la dimensión.", cls="apagado text-sm")]
        for c in d["criterios"]:
            j = c["juicio"]
            partes += [
                fh.H3(f"{c['codigo']} {c['nombre']}", cls="mt-4"),
                P("Nivel: ", Span(f"{j['nivel']}. {j['nivel_nombre']}" if j and j["nivel"] is not None
                                  else "sin juzgar", cls="font-medium"), cls="text-sm"),
                P(j["juicio"], cls="text-sm whitespace-pre-line") if j and j["juicio"] else "",
                Div(Div(Div("Fortalezas", cls="text-xs font-medium"), _lineas(j and j["fortalezas"])),
                    Div(Div("Debilidades", cls="text-xs font-medium"), _lineas(j and j["debilidades"])),
                    cls="grid grid-cols-2 gap-4 text-sm"),
                Div(Table(Thead(Tr(Th("Indicador"), *[Th(str(y), cls="text-right") for y in anios])),
                          Tbody(*[Tr(Td(f"{i['codigo']} {i['nombre']}"),
                                     *[Td(numero((i["celdas"].get(y) or {}).get("valor")), cls="text-right")
                                       for y in anios]) for i in c["indicadores"]])),
                    cls="overflow-x-auto") if c["indicadores"] else "",
                P("Evidencias: ", "; ".join(e["titulo"] + (" (vencida)" if e["vencida"] else "")
                                            for e in c["evidencias"]) or "ninguna.", cls="text-xs apagado"),
            ]
    partes += [fh.H2("Análisis global"),
               P(a["analisis_global"], cls="text-sm whitespace-pre-line") if a["analisis_global"] else
               P("Sin análisis global.", cls="apagado text-sm"),
               P("Cifras de los indicadores: las de los años cerrados en el tablero están congeladas; las de los demás se "
                 "calculan con los datos del día en que se genera este informe.", cls="apagado text-xs mt-4")]
    return hoja(*partes, titulo=f"Informe de autoevaluación {a['nombre']}")


@rt(f"{BASE}/{{aid}}/informe")
def get(auth, aid: int):
    a, error = _visible(auth, aid)
    if error:
        return error
    m = marco.obtener(a["marco_id"])
    return pagina(f"Informe de autoevaluación: {a['nombre']}", ESTILO_IMPRESION,
                  A(UkIcon("arrow-left", height=14, width=14), a["nombre"], href=f"{BASE}/{aid}",
                    cls="no-imprimir inline-flex items-center gap-1 text-sm text-primary mb-4"),
                  barra((), [descarga("XLSX", f"{BASE}/{aid}/xlsx")]), documento(a, m), usuario=auth)


@rt(f"{BASE}/{{aid}}/xlsx")
def get(auth, aid: int):
    a, error = _visible(auth, aid)
    if error:
        return error
    return _archivo(ae.a_xlsx(a), f"autoevaluacion-{a['desde_anio']}-{a['hasta_anio']}.xlsx", XLSX)


# --- IA (PLAN §59, etapa 3b): sugerencias de evidencias y borrador de la narrativa del juicio ---------------------

@rt(f"{BASE}/{{aid}}/criterios/{{cid}}/ia/evidencias")
def post(auth, aid: int, cid: int, volver: str = ""):
    a, error = _editable(auth, aid)
    if error:
        return error
    c = _criterio_de(a, cid)
    if c is None:
        return _no_encontrado()
    entidad = f"evidencias:{aid}:{cid}"
    datos, elegir = ia_catalogo.datos_evidencias(a, c)
    return respuesta_pedido(ia_catalogo.EVIDENCIAS.clave, entidad, auth, f"{BASE}/{aid}/criterios/{cid}",
                            lambda: ia.generar(ia_catalogo.EVIDENCIAS.clave, datos, auth, entidad_tipo=entidad,
                                               entidad_id=cid, en_fondo=True, posproceso=elegir))


@rt(f"{BASE}/{{aid}}/criterios/{{cid}}/ia/juicio")
def post(auth, aid: int, cid: int, volver: str = ""):
    a, error = _editable(auth, aid)
    if error:
        return error
    c = _criterio_de(a, cid)
    if c is None:
        return _no_encontrado()
    entidad = f"juicio:{aid}:{cid}"
    datos, posproceso = ia_catalogo.datos_narrativa(c, evidencias.listar(a["marco_id"], cid),
                                                    ae.juicios(aid).get(cid))
    return respuesta_pedido(ia_catalogo.NARRATIVA.clave, entidad, auth, f"{BASE}/{aid}/criterios/{cid}",
                            lambda: ia.generar(ia_catalogo.NARRATIVA.clave, datos, auth, entidad_tipo=entidad,
                                               entidad_id=cid, en_fondo=True, posproceso=posproceso))
