"""Encuestas a estudiantes y egresados (PLAN §49 y §50): armarlas, abrirlas, enviar las invitaciones y ver los
resultados agregados. Arman, abren y envían la Dirección de Carrera y la Coordinación académica
(`gestionar_encuestas`); ven los resultados quienes ven el seguimiento estudiantil (`ver_seguimiento_estudiantil`,
incluido el Comité de acreditación, que solo ve agregados). Las respuestas individuales solo existen en las
encuestas nominales y solo las ve quien las gestiona."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Thead, Tr, Ul
from fasthtml.toaster import add_toast
from monsterui.all import (H2, H3, Button, ButtonT, Card, Form, FormLabel, LabelCheckboxX, LabelInput, Table, Tbody, Td,
                           TextPresets, Th, UkIcon)

from app.comun import permisos, vinculos
from app.comun.componentes.layout import mensaje_error, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import get_db
from app.estudiantil import encuestas
from app.estudiantil.plantillas_encuesta import PLANTILLAS

rt = APIRouter()
BASE = "/docencia/encuestas"
TONOS = {"borrador": "gris", "abierta": "verde", "cerrada": "azul"}


def _ver(auth) -> bool:
    return permisos.puede(auth, "ver_seguimiento_estudiantil", vinculos.carrera())


def _gestiona(auth) -> bool:
    return permisos.puede(auth, "gestionar_encuestas", vinculos.carrera())


def _no():
    return Response("No autorizado", status_code=403)


def _pct(x):
    return "—" if x is None else f"{x * 100:.0f} %"


def _boton(texto, url, *, confirmar=None, cls=ButtonT.default, icono=None, **extra):
    """Formulario de un solo botón que envía un POST y vuelve a la página (la ruta responde con Redirect)."""
    return Form(Button(UkIcon(icono, height=14, width=14) if icono else "", texto, type="submit", cls=cls),
                hx_post=url, hx_swap="none", **({"hx_confirm": confirmar} if confirmar else {}), **extra)


# --- Lista -----------------------------------------------------------------------------------------------------

@rt(BASE)
def get(auth):
    if not _ver(auth):
        return _no()
    filas = [Tr(Td(A(e["titulo"], href=f"{BASE}/{e['id']}", cls="font-medium hover:underline"),
                   Div(encuestas.TIPOS[e["tipo"]], cls=TextPresets.muted_sm)),
                Td(encuestas.PUBLICOS[e["publico"]], cls="text-sm"),
                Td("Anónima" if e["anonima"] else "Nominal", cls="text-sm"),
                Td(insignia(encuestas.ESTADOS[e["estado"]], TONOS[e["estado"]])),
                Td(f"{e['respondidas']} de {e['invitadas']}" if e["invitadas"] else "—", cls="text-sm"),
                Td(_pct(e["respondidas"] / e["invitadas"]) if e["invitadas"] else "—", cls="text-sm"))
             for e in encuestas.listar()]
    nueva = Card(
        H3("Nueva encuesta", cls="text-base font-semibold"),
        Form(Div(Div(FormLabel("Partir de"), Select(Option("Una encuesta en blanco", value=""),
                                                     *[Option(p["titulo"], value=k) for k, p in PLANTILLAS.items()],
                                                     name="plantilla", cls="uk-select"), cls="space-y-1"),
                 LabelInput("Título (solo si parte en blanco)", id="titulo"), cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
             Button("Crear borrador", type="submit", cls=ButtonT.primary), hx_post=BASE, hx_swap="none",
             cls="space-y-3")) if _gestiona(auth) else ""
    return pagina(
        "Encuestas",
        H2("Encuestas"),
        P("Encuestas a estudiantes y egresados (satisfacción, clima, bienestar, abandono, seguimiento de egresados). Cada "
          "persona responde con un enlace personal que recibe por correo, sin necesidad de cuenta. Las anónimas no "
          f"asocian la respuesta con la persona y no muestran resultados hasta tener {encuestas.MIN_ANONIMO} respuestas.",
          cls=(TextPresets.muted_sm, "max-w-3xl mb-6")),
        nueva, Div(cls="h-4"),
        Card(Div(Table(Thead(Tr(Th("Encuesta"), Th("Público"), Th("Modalidad"), Th("Estado"), Th("Respondieron"), Th("Tasa"))),
                       Tbody(*filas) if filas else Tbody(Tr(Td("Aún no hay encuestas.", colspan=6,
                                                               cls=(TextPresets.muted_sm, "text-center py-6")))),
                       cls="uk-table-divider uk-table-middle"), cls="overflow-x-auto")),
        usuario=auth, seccion="docencia")


@rt(BASE)
def post(auth, sess, plantilla: str = "", titulo: str = ""):
    if not _gestiona(auth):
        return _no()
    if plantilla in PLANTILLAS:
        eid = encuestas.crear_desde_plantilla(plantilla, auth["id"])
    else:
        eid, errores = encuestas.crear({"titulo": titulo, "tipo": "otra", "publico": "estudiantes", "anonima": "1"}, auth["id"])
        if errores:
            add_toast(sess, errores[0], "error")
            return Redirect(BASE)
    add_toast(sess, "Borrador creado. Revise las preguntas y los datos antes de abrirlo.", "success")
    return Redirect(f"{BASE}/{eid}")


# --- Detalle y edición -----------------------------------------------------------------------------------------

def _datos(e, editable, errores=()):
    if not editable:
        filtro = (f"Ingreso entre {e['cohorte_desde'] or '…'} y {e['cohorte_hasta'] or '…'}"
                  if e["cohorte_desde"] or e["cohorte_hasta"] else "Todas las cohortes")
        return Div(P(e["descripcion"] or "", cls="text-sm"),
                   P(f"{encuestas.TIPOS[e['tipo']]} · {encuestas.PUBLICOS[e['publico']]} · {filtro} · "
                     f"{'Anónima' if e['anonima'] else 'Nominal'}" + (f" · hasta el {e['cierra_el']}" if e["cierra_el"] else ""),
                     cls=TextPresets.muted_sm))
    return Form(
        mensaje_error(*errores),
        LabelInput("Título", id="titulo", value=e["titulo"], required=True, maxlength="200"),
        Div(FormLabel("Descripción (se muestra a quien responde)"),
            fh.Textarea(e["descripcion"] or "", name="descripcion", rows="2", maxlength="2000", cls="uk-textarea"),
            cls="space-y-1"),
        Div(Div(FormLabel("Tipo"), Select(*[Option(t, value=k, selected=k == e["tipo"]) for k, t in encuestas.TIPOS.items()],
                                         name="tipo", cls="uk-select"), cls="space-y-1"),
            Div(FormLabel("Dirigida a"), Select(*[Option(t, value=k, selected=k == e["publico"])
                                                  for k, t in encuestas.PUBLICOS.items()], name="publico", cls="uk-select"),
                cls="space-y-1"),
            LabelInput("Ingreso desde (año, opcional)", id="cohorte_desde", type="number", value=e["cohorte_desde"] or "",
                       min="1990", max="2100"),
            LabelInput("Ingreso hasta (año, opcional)", id="cohorte_hasta", type="number", value=e["cohorte_hasta"] or "",
                       min="1990", max="2100"),
            LabelInput("Se puede responder hasta (opcional)", id="cierra_el", type="date", value=e["cierra_el"] or ""),
            cls="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"),
        LabelCheckboxX("Anónima: la respuesta no se asocia con la persona (recomendado en bienestar, clima y abandono)",
                       id="anonima", checked=bool(e["anonima"])),
        Button("Guardar datos", type="submit", cls=ButtonT.primary), method="post", action=f"{BASE}/{e['id']}/datos",
        cls="space-y-3")


def _pregunta(e, q, i, n, editable):
    detalle = encuestas.TIPOS_PREGUNTA[q["tipo"]] + (" · obligatoria" if q["obligatoria"] else " · opcional")
    if q["opciones"]:
        detalle += " · " + " / ".join(q["opciones"])
    acciones = Div(
        _boton("", f"{BASE}/preguntas/{q['id']}/subir", cls=(ButtonT.ghost, ButtonT.icon), icono="arrow-up",
               aria_label="Subir") if i > 0 else "",
        _boton("", f"{BASE}/preguntas/{q['id']}/bajar", cls=(ButtonT.ghost, ButtonT.icon), icono="arrow-down",
               aria_label="Bajar") if i < n - 1 else "",
        _boton("", f"{BASE}/preguntas/{q['id']}/eliminar", cls=(ButtonT.ghost, ButtonT.icon), icono="trash-2",
               aria_label="Eliminar pregunta", confirmar="¿Eliminar esta pregunta?"),
        cls="flex shrink-0") if editable else ""
    return Li(Div(Div(f"{i + 1}. {q['texto']}", cls="text-sm font-medium"), Div(detalle, cls=TextPresets.muted_sm),
                  cls="min-w-0"), acciones, cls="flex items-start justify-between gap-3 py-2")


def _form_pregunta(eid, errores=()):
    return fh.Details(
        fh.Summary("Agregar una pregunta", cls="cursor-pointer text-sm text-primary"),
        Form(mensaje_error(*errores),
             LabelInput("Pregunta", id="texto", required=True, maxlength="500"),
             Div(Div(FormLabel("Tipo de respuesta"), Select(*[Option(t, value=k) for k, t in encuestas.TIPOS_PREGUNTA.items()],
                                                          name="tipo", cls="uk-select"), cls="space-y-1"),
                 Div(FormLabel("Opciones (una por línea; solo para «Una opción» y «Varias opciones»)"),
                     fh.Textarea(name="opciones", rows="3", cls="uk-textarea"), cls="space-y-1"),
                 cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
             LabelCheckboxX("Respuesta obligatoria", id="obligatoria", checked=True),
             Button("Agregar", type="submit", cls=ButtonT.default), method="post", action=f"{BASE}/{eid}/preguntas",
             cls="space-y-3 mt-3"),
        open=bool(errores), cls="rounded-md border border-border p-3 mt-3")


def _envio(e, auth):
    inv = encuestas.resumen_invitaciones(e["id"])
    if e["estado"] == "borrador":
        gente, sin_correo = encuestas.destinatarios(e)
        return Div(
            P(f"Al abrirla se invitará a {len(gente)} persona(s)" + (f"; {sin_correo} no tienen correo registrado y no se "
                                                                     "invitarán." if sin_correo else "."),
              cls="text-sm"),
            P("Una vez abierta ya no se pueden cambiar las preguntas ni los datos.", cls=TextPresets.muted_sm),
            _boton("Abrir la encuesta", f"{BASE}/{e['id']}/abrir", cls=ButtonT.primary, icono="play",
                   confirmar=f"Se abrirá la encuesta a {len(gente)} persona(s). Después no podrá cambiar las preguntas. "
                             "¿Abrirla?") if _gestiona(auth) else "", cls="space-y-2")
    estado = P(f"{inv['respondidas']} respuesta(s) de {inv['invitadas']} invitada(s) · {inv['enviadas']} correo(s) enviado(s)"
               f" · {_pct(inv['respondidas'] / inv['invitadas'] if inv['invitadas'] else None)} de respuesta", cls="text-sm")
    if e["estado"] == "cerrada" or not _gestiona(auth):
        return Div(estado)
    return Div(
        estado,
        Div(_boton(f"Enviar invitaciones pendientes ({min(inv['por_enviar'], encuestas.LOTE_CORREOS)} de {inv['por_enviar']})",
                   f"{BASE}/{e['id']}/enviar", cls=ButtonT.primary, icono="send") if inv["por_enviar"] else "",
            _boton("Enviar recordatorio a quienes no respondieron", f"{BASE}/{e['id']}/recordar", icono="bell-ring",
                   confirmar="Se enviará un recordatorio a quienes no respondieron (y no recibieron otro en la última "
                             "semana). ¿Continuar?") if inv["enviadas"] > inv["respondidas"] else "",
            _boton("Cerrar la encuesta", f"{BASE}/{e['id']}/cerrar", icono="lock",
                   confirmar="Los enlaces dejarán de servir. ¿Cerrar la encuesta?"),
            cls="flex flex-wrap gap-2 mt-3"),
        P(f"Los correos salen en lotes de {encuestas.LOTE_CORREOS}: repita el envío hasta que no queden pendientes.",
          cls=(TextPresets.muted_sm, "mt-2")), cls="space-y-1")


def _detalle(auth, e, errores_datos=(), errores_pregunta=()):
    editable = e["estado"] == "borrador" and _gestiona(auth)
    qs = encuestas.preguntas(e["id"])
    return pagina(
        e["titulo"],
        A(UkIcon("arrow-left", height=14, width=14), "Encuestas", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(Div(H2(e["titulo"]), Div(insignia(encuestas.ESTADOS[e["estado"]], TONOS[e["estado"]]),
                                      insignia("Anónima" if e["anonima"] else "Nominal", "gris"), cls="flex gap-2 mt-1")),
            A(UkIcon("bar-chart-3", height=16, width=16), "Ver resultados", href=f"{BASE}/{e['id']}/resultados",
              cls="uk-btn uk-btn-default inline-flex items-center gap-1") if e["estado"] != "borrador" else "",
            cls="flex flex-wrap items-start justify-between gap-4 mb-6"),
        Div(Card(H3("Datos", cls="text-base font-semibold mb-2"), _datos(e, editable, errores_datos)),
            Card(H3("Envío", cls="text-base font-semibold mb-2"), _envio(e, auth)),
            Card(H3(f"Preguntas ({len(qs)})", cls="text-base font-semibold"),
                 Ul(*[_pregunta(e, q, i, len(qs), editable) for i, q in enumerate(qs)], cls="divide-y divide-border")
                 if qs else P("Aún no hay preguntas.", cls=(TextPresets.muted_sm, "py-3")),
                 _form_pregunta(e["id"], errores_pregunta) if editable else ""),
            _boton("Eliminar el borrador", f"{BASE}/{e['id']}/eliminar", icono="trash-2",
                   confirmar="¿Eliminar este borrador con sus preguntas?") if editable else "",
            cls="space-y-6"),
        usuario=auth, seccion="docencia")


def _encuesta(eid):
    return encuestas.obtener(eid)


@rt(f"{BASE}/{{eid}}")
def get(auth, eid: int):
    e = _encuesta(eid)
    if not _ver(auth):
        return _no()
    return _detalle(auth, e) if e else pagina("No encontrada", P("Esa encuesta no existe."), usuario=auth, seccion="docencia")


def _accion(auth, sess, eid, hacer, ok):
    """Ejecuta `hacer(e)` (→ errores) sobre una encuesta y vuelve al detalle con un aviso."""
    e = _encuesta(eid)
    if not _gestiona(auth):
        return _no()
    if not e:
        return Redirect(BASE)
    errores = hacer(e)
    add_toast(sess, errores[0] if errores else ok, "error" if errores else "success")
    return Redirect(f"{BASE}/{eid}")


@rt(f"{BASE}/{{eid}}/datos")
def post(auth, sess, eid: int, titulo: str = "", descripcion: str = "", tipo: str = "", publico: str = "",
         cohorte_desde: str = "", cohorte_hasta: str = "", cierra_el: str = "", anonima: str = ""):
    e = _encuesta(eid)
    if not _gestiona(auth):
        return _no()
    if not e:
        return Redirect(BASE)
    d = dict(titulo=titulo, descripcion=descripcion, tipo=tipo, publico=publico, cohorte_desde=cohorte_desde,
             cohorte_hasta=cohorte_hasta, cierra_el=cierra_el, anonima=anonima)
    errores = encuestas.actualizar(eid, d)
    if errores:
        return _detalle(auth, {**e, **d, "anonima": int(anonima == "on")}, errores_datos=errores)
    add_toast(sess, "Datos guardados.", "success")
    return Redirect(f"{BASE}/{eid}")


@rt(f"{BASE}/{{eid}}/preguntas")
def post(auth, sess, eid: int, texto: str = "", tipo: str = "", opciones: str = "", obligatoria: str = ""):
    e = _encuesta(eid)
    if not _gestiona(auth):
        return _no()
    if not e:
        return Redirect(BASE)
    errores = encuestas.agregar_pregunta(eid, dict(texto=texto, tipo=tipo, opciones=opciones, obligatoria=obligatoria))
    if errores:
        return _detalle(auth, e, errores_pregunta=errores)
    return Redirect(f"{BASE}/{eid}")


def _de_pregunta(auth, pid, hacer):
    if not _gestiona(auth):
        return _no()
    filas = get_db().q("SELECT encuesta_id FROM pregunta WHERE id = ?", [pid])
    if filas:
        hacer(pid)
    return Redirect(f"{BASE}/{filas[0]['encuesta_id']}" if filas else BASE)


@rt(f"{BASE}/preguntas/{{pid}}/eliminar")
def post(auth, pid: int):
    return _de_pregunta(auth, pid, encuestas.eliminar_pregunta)


@rt(f"{BASE}/preguntas/{{pid}}/subir")
def post(auth, pid: int):
    return _de_pregunta(auth, pid, lambda p: encuestas.mover_pregunta(p, -1))


@rt(f"{BASE}/preguntas/{{pid}}/bajar")
def post(auth, pid: int):
    return _de_pregunta(auth, pid, lambda p: encuestas.mover_pregunta(p, 1))


@rt(f"{BASE}/{{eid}}/abrir")
def post(auth, sess, eid: int):
    def hacer(e):
        _, _, errores = encuestas.abrir(eid, auth["id"])
        return errores
    return _accion(auth, sess, eid, hacer, "Encuesta abierta. Ahora envíe las invitaciones.")


def _envio_correos(auth, sess, eid, recordatorio):
    e = _encuesta(eid)
    if not _gestiona(auth):
        return _no()
    r = encuestas.enviar(eid, auth["id"], recordatorio=recordatorio) if e else {"enviados": 0, "quedan": 0}
    texto = f"{r['enviados']} correo(s) enviado(s)." + (f" Quedan {r['quedan']} por enviar: repita el envío." if r["quedan"] else "")
    add_toast(sess, texto if r["enviados"] else "No hay correos por enviar.", "success" if r["enviados"] else "info")
    return Redirect(f"{BASE}/{eid}" if e else BASE)


@rt(f"{BASE}/{{eid}}/enviar")
def post(auth, sess, eid: int):
    return _envio_correos(auth, sess, eid, False)


@rt(f"{BASE}/{{eid}}/recordar")
def post(auth, sess, eid: int):
    return _envio_correos(auth, sess, eid, True)


@rt(f"{BASE}/{{eid}}/cerrar")
def post(auth, sess, eid: int):
    return _accion(auth, sess, eid, lambda e: [] if encuestas.cerrar(eid, auth["id"]) else ["No se pudo cerrar la encuesta."],
                   "Encuesta cerrada.")


@rt(f"{BASE}/{{eid}}/eliminar")
def post(auth, sess, eid: int):
    if not _gestiona(auth):
        return _no()
    ok = encuestas.eliminar(eid)
    add_toast(sess, "Borrador eliminado." if ok else "Solo se puede eliminar un borrador.", "success" if ok else "error")
    return Redirect(BASE)


# --- Resultados ------------------------------------------------------------------------------------------------

def _barras(p):
    q, conteo = p["pregunta"], p["conteo"]
    total = max(sum(conteo.values()), 1)
    filas = [Div(Span(encuestas.texto_valor(q, str(k)), cls="text-sm w-64 shrink-0"),
                 fh.Progress(value=str(n), max=str(total), cls="uk-progress flex-1", aria_label=str(k)),
                 Span(f"{n} ({_pct(n / total)})", cls="text-sm w-24 text-right"), cls="flex items-center gap-3")
             for k, n in conteo.items()]
    return Div(*filas, cls="space-y-1")


def _resultado_pregunta(p):
    q = p["pregunta"]
    cuerpo = []
    if q["tipo"] == "texto":
        cuerpo.append(Ul(*[Li(t, cls="text-sm py-1") for t in p["textos"]], cls="divide-y divide-border")
                      if p["textos"] else P("Sin comentarios.", cls=TextPresets.muted_sm))
    else:
        if q["tipo"] == "escala" and p["promedio"] is not None:
            cuerpo.append(P(f"Promedio: {p['promedio']:.2f}".replace(".", ",") + " de 5", cls="text-sm font-semibold"))
        cuerpo.append(_barras(p))
        if q["tipo"] == "escala" and p["por_grupo"]:
            cuerpo.append(P("Promedio por año de ingreso: " + " · ".join(f"{g}: {v:.2f}".replace(".", ",")
                                                                       for g, v in p["por_grupo"].items()),
                            cls=TextPresets.muted_sm))
    return Card(H3(q["texto"], cls="text-base font-medium"), P(f"{p['n']} respuesta(s)", cls=TextPresets.muted_sm), *cuerpo,
                cls="space-y-2")


@rt(f"{BASE}/{{eid}}/resultados")
def get(auth, eid: int):
    if not _ver(auth):
        return _no()
    e = _encuesta(eid)
    if not e or e["estado"] == "borrador":
        return pagina("Resultados", P("Esa encuesta no existe o aún no se abrió."), usuario=auth, seccion="docencia")
    r = encuestas.resultados(eid)
    individuales = encuestas.individuales(eid) if _gestiona(auth) else []
    return pagina(
        f"Resultados: {e['titulo']}",
        A(UkIcon("arrow-left", height=14, width=14), e["titulo"], href=f"{BASE}/{eid}",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(Div(H2("Resultados"), P(f"{e['titulo']} · {r['n']} respuesta(s) de {r['invitadas']} invitada(s) "
                                    f"({_pct(r['tasa'])})", cls=TextPresets.muted_sm)),
            A(UkIcon("download", height=16, width=16), "Descargar CSV", href=f"{BASE}/{eid}/resultados.csv",
              cls="uk-btn uk-btn-default inline-flex items-center gap-1") if not r["oculto"] else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Card(P(f"Por ser anónima, los resultados se muestran desde {r['minimo']} respuestas, para que nadie pueda saber "
               f"quién respondió qué. Hay {r['n']}.", cls="text-sm")) if r["oculto"]
        else Div(*[_resultado_pregunta(p) for p in r["preguntas"]], cls="space-y-4"),
        Div(H3("Respuestas individuales", cls="text-base font-semibold mt-8 mb-2"),
            *[Card(Div(f"{x['apellidos']}, {x['nombres']}", cls="font-medium"),
                   Ul(*[Li(Span(q["texto"], cls=TextPresets.muted_sm), Div(" · ".join(encuestas.texto_valor(q, v) for v in vals)
                                                                          or "—", cls="text-sm"))
                         for q, vals in x["respuestas"]], cls="space-y-1 mt-1"), cls="mb-3")
              for x in individuales]) if individuales else "",
        usuario=auth, seccion="docencia")


@rt(f"{BASE}/{{eid}}/resultados.csv")
def get(auth, eid: int):
    if not _ver(auth):
        return _no()
    contenido = encuestas.csv_resultados(eid) if _encuesta(eid) else None
    if contenido is None:
        return Response("Aún no hay resultados que mostrar.", status_code=404)
    return Response(contenido.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="encuesta-{eid}.csv"'})
