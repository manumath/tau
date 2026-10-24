"""Tutoría (PLAN §49): la vista del tutor («Mis tutorados», las reuniones de cada uno) y la de la Dirección de Carrera y la
Coordinación académica (asignar tutores y cifras). Las reuniones son confidenciales: las ve su autor y la Dirección de Carrera
(`ver_tutorias_detalle`; cada vez que la Dirección las abre queda en la auditoría)."""
from datetime import date

import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Thead, Tr, Ul
from fasthtml.toaster import add_toast
from monsterui.all import (H2, H3, Button, ButtonT, Card, Form, FormLabel, LabelInput, Table, Tbody, Td, TextPresets, Th,
                           UkIcon)

from app.comun import estudiantes, permisos, vinculos
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar, get_db
from app.estudiantil import cohortes, tutoria

rt = APIRouter()
BASE = "/tutoria"
DIR = "/docencia/tutoria"


def _no():
    return Response("No autorizado", status_code=403)


def _gestiona(auth) -> bool:
    return permisos.puede(auth, "gestionar_tutorias", vinculos.carrera())


def _ve_cifras(auth) -> bool:
    return permisos.puede(auth, "ver_seguimiento_estudiantil", vinculos.carrera())


def _detalle_direccion(auth) -> bool:
    return permisos.puede(auth, "ver_tutorias_detalle", vinculos.carrera())


def _estudiante(externo_id):
    filas = get_db().q("""SELECT pe.id, pe.nombres, pe.apellidos, es.cohorte_anio, es.cohorte_ciclo, es.registro_universitario,
                                 es.estado FROM persona_externa pe JOIN estudiante es ON es.externo_id = pe.id
                          WHERE pe.id = ? AND es.nivel = 'licenciatura' AND es.cohorte_anio IS NOT NULL
                          ORDER BY es.id DESC LIMIT 1""", [externo_id])
    return filas[0] if filas else None


# --- Vista del tutor -----------------------------------------------------------------------------------------

@rt(BASE)
def get(auth):
    if not estudiantes.es_tutor(auth["id"]):
        return _no()
    filas = [Tr(Td(A(f"{t['apellidos']}, {t['nombres']}", href=f"{BASE}/{t['externo_id']}", cls="font-medium hover:underline")),
                Td(cohortes.texto(t["cohorte_anio"], t["cohorte_ciclo"]), cls="text-sm"),
                Td(t["registro_universitario"] or "—", cls="text-sm"), Td(t["reuniones"]),
                Td(t["ultima"] or insignia("Sin reuniones", "ambar"), cls="text-sm whitespace-nowrap"))
             for t in tutoria.tutorados(auth["id"])]
    return pagina(
        "Mis tutorados",
        H2("Mis tutorados"),
        P("Estudiantes que la Carrera le asignó como tutor(a). Registre sus reuniones y derivaciones: son confidenciales (las ve "
          "usted y la Dirección de Carrera; el estudiante no las ve).", cls=(TextPresets.muted_sm, "max-w-3xl mb-6")),
        Card(Div(Table(Thead(Tr(Th("Estudiante"), Th("Cohorte"), Th("RU"), Th("Reuniones"), Th("Última"))), Tbody(*filas),
                       cls="uk-table-divider uk-table-middle"), cls="overflow-x-auto")),
        usuario=auth, seccion="tutoria")


def _acceso(auth, externo_id):
    """'tutor' si es su tutor(a) hoy, 'direccion' si puede ver todas las reuniones, None si no puede."""
    if tutoria.es_tutor_de(auth["id"], externo_id):
        return "tutor"
    return "direccion" if _detalle_direccion(auth) else None


def _reunion(r, propia):
    return Li(
        Div(Div(Span(r["fecha"], cls="font-medium text-sm"), insignia(tutoria.TEMAS[r["tema"]], "azul"),
                insignia(tutoria.MODALIDADES[r["modalidad"]], "gris"),
                insignia(tutoria.DERIVACIONES[r["derivacion"]], "ambar") if r["derivacion"] != "ninguna" else "",
                Span(f"{r['tutor_apellidos']}, {r['tutor_nombres']}", cls=TextPresets.muted_sm) if not propia else "",
                cls="flex flex-wrap items-center gap-2"),
            P(r["resumen"], cls="text-sm whitespace-pre-line") if r["resumen"] else "",
            P(Span("Acuerdos: ", cls="font-medium"), r["acuerdos"], cls="text-sm whitespace-pre-line") if r["acuerdos"] else "",
            cls="space-y-1 min-w-0"),
        Div(fh.Button(UkIcon("pencil", height=14, width=14), type="button", cls=(ButtonT.ghost, ButtonT.icon), aria_label="Corregir",
                      hx_get=f"{BASE}/reuniones/{r['id']}/editar", hx_target=f"#{ID_MODAL}"),
            fh.Form(fh.Button(UkIcon("trash-2", height=14, width=14), type="submit", cls=(ButtonT.ghost, ButtonT.icon),
                              aria_label="Eliminar"), hx_post=f"{BASE}/reuniones/{r['id']}/eliminar", hx_swap="none",
                    hx_confirm="¿Eliminar esta reunión?"), cls="flex shrink-0") if propia else "",
        cls="flex items-start justify-between gap-3 py-3")


@rt(f"{BASE}/{{externo_id}}")
def get(auth, externo_id: int):
    rol = _acceso(auth, externo_id)
    e = _estudiante(externo_id)
    if not rol or not e:
        return _no() if not rol else pagina("No encontrado", P("Esa persona no existe."), usuario=auth, seccion="tutoria")
    if rol == "direccion":
        auditar(auth["id"], "ver_tutorias", "persona_externa", externo_id)
    lista = tutoria.reuniones(externo_id, auth["id"] if rol == "tutor" else None)
    actividad = get_db().q("""SELECT titulo, tipo, fecha_inicio FROM actividad_estudiantil WHERE externo_id = ? AND estado = 'verificada'
                              ORDER BY fecha_inicio DESC LIMIT 8""", [externo_id])
    from app.estudiantil import actividad as act
    return pagina(
        f"{e['nombres']} {e['apellidos']}",
        A(UkIcon("arrow-left", height=14, width=14), "Tutoría", href=BASE if rol == "tutor" else DIR,
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(Div(H2(f"{e['nombres']} {e['apellidos']}"),
                P(f"RU {e['registro_universitario'] or '—'} · Cohorte {cohortes.texto(e['cohorte_anio'], e['cohorte_ciclo'])} · "
                  f"{cohortes.ESTADOS[e['estado']]}", cls=TextPresets.muted_sm)),
            Button(UkIcon("plus", height=16, width=16), "Registrar reunión", cls=ButtonT.primary, hx_get=f"{BASE}/{externo_id}/reuniones/nueva",
                   hx_target=f"#{ID_MODAL}") if rol == "tutor" else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Div(Div(Card(H3("Reuniones" + ("" if rol == "tutor" else " (de todos los tutores)"), cls="text-base font-semibold"),
                 P("Confidencial. " + ("Solo usted y la Dirección de Carrera ven estas notas." if rol == "tutor"
                                       else "Cada consulta suya queda en la auditoría."), cls=(TextPresets.muted_sm, "mb-2")),
                 Ul(*[_reunion(r, rol == "tutor" and r["tutor_id"] == auth["id"]) for r in lista], cls="divide-y divide-border")
                 if lista else P("Aún no hay reuniones registradas.", cls=(TextPresets.muted_sm, "py-4 text-center"))),
                cls="lg:col-span-2"),
            Card(H3("Actividad estudiantil verificada", cls="text-base font-semibold mb-2"),
                 Ul(*[Li(a["titulo"], Span(f" · {act.TIPOS[a['tipo']]} · {a['fecha_inicio']}", cls=TextPresets.muted_sm), cls="text-sm")
                      for a in actividad], cls="space-y-1") if actividad
                 else P("Aún no declaró actividades verificadas.", cls=TextPresets.muted_sm)),
            cls="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start"),
        usuario=auth, seccion="tutoria")


def _form(externo_id, d=None, errores=(), rid=None):
    d = d or {}
    return modal(
        "Corregir reunión" if rid else "Registrar reunión",
        Form(mensaje_error(*errores),
             Div(LabelInput("Fecha", id="fecha", type="date", value=d.get("fecha") or date.today().isoformat(), required=True),
                 Div(FormLabel("Modalidad"), Select(*[Option(t, value=k, selected=k == (d.get("modalidad") or "presencial"))
                                                      for k, t in tutoria.MODALIDADES.items()], name="modalidad", cls="uk-select"),
                     cls="space-y-1"), cls="grid grid-cols-2 gap-3"),
             Div(FormLabel("Tema"), Select(Option("— Elija —", value=""), *[Option(t, value=k, selected=k == d.get("tema"))
                                                                          for k, t in tutoria.TEMAS.items()],
                                          name="tema", cls="uk-select", required=True), cls="space-y-1"),
             Div(FormLabel("Resumen (confidencial)"), fh.Textarea(d.get("resumen") or "", name="resumen", rows="4", maxlength="3000",
                                                                  cls="uk-textarea"), cls="space-y-1"),
             Div(FormLabel("Derivación"), Select(*[Option(t, value=k, selected=k == (d.get("derivacion") or "ninguna"))
                                                   for k, t in tutoria.DERIVACIONES.items()], name="derivacion", cls="uk-select"),
                 cls="space-y-1"),
             Div(FormLabel("Acuerdos"), fh.Textarea(d.get("acuerdos") or "", name="acuerdos", rows="2", maxlength="2000",
                                                    cls="uk-textarea"), cls="space-y-1"),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/reuniones/{rid}" if rid else f"{BASE}/{externo_id}/reuniones", hx_target=f"#{ID_MODAL}", cls="space-y-4"),
        ancho="max-w-xl")


@rt(f"{BASE}/{{externo_id}}/reuniones/nueva")
def get(auth, externo_id: int):
    return _form(externo_id) if tutoria.es_tutor_de(auth["id"], externo_id) else _no()


def _campos(fecha, modalidad, tema, resumen, derivacion, acuerdos):
    return dict(fecha=fecha, modalidad=modalidad, tema=tema, resumen=resumen, derivacion=derivacion, acuerdos=acuerdos)


@rt(f"{BASE}/{{externo_id}}/reuniones")
def post(auth, sess, externo_id: int, fecha: str = "", modalidad: str = "", tema: str = "", resumen: str = "",
         derivacion: str = "", acuerdos: str = ""):
    if not tutoria.es_tutor_de(auth["id"], externo_id):
        return _no()
    d = _campos(fecha, modalidad, tema, resumen, derivacion, acuerdos)
    errores = tutoria.registrar(externo_id, auth["id"], d)
    if errores:
        return _form(externo_id, d, errores)
    add_toast(sess, "Reunión registrada.", "success")
    return Redirect(f"{BASE}/{externo_id}")


@rt(f"{BASE}/reuniones/{{rid}}/editar")
def get(auth, rid: int):
    r = tutoria.obtener(rid)
    return _form(r["externo_id"], r, rid=rid) if r and r["tutor_id"] == auth["id"] else _no()


@rt(f"{BASE}/reuniones/{{rid}}")
def post(auth, sess, rid: int, fecha: str = "", modalidad: str = "", tema: str = "", resumen: str = "", derivacion: str = "",
         acuerdos: str = ""):
    r = tutoria.obtener(rid)
    if not r or r["tutor_id"] != auth["id"]:
        return _no()
    d = _campos(fecha, modalidad, tema, resumen, derivacion, acuerdos)
    errores = tutoria.editar(rid, auth["id"], d)
    if errores:
        return _form(r["externo_id"], d, errores, rid)
    add_toast(sess, "Reunión corregida.", "success")
    return Redirect(f"{BASE}/{r['externo_id']}")


@rt(f"{BASE}/reuniones/{{rid}}/eliminar")
def post(auth, sess, rid: int):
    r = tutoria.obtener(rid)
    if not r or not tutoria.eliminar(rid, auth["id"]):
        return _no()
    add_toast(sess, "Reunión eliminada.", "success")
    return Redirect(f"{BASE}/{r['externo_id']}")


# --- Dirección: asignar tutores y cifras -------------------------------------------------------------------

def _pct(x):
    return "—" if x is None else f"{x * 100:.0f} %"


@rt(DIR)
def get(auth, cohorte: str = "", solo: str = ""):
    if not _ve_cifras(auth):
        return _no()
    ind = tutoria.indicadores()
    resumen = Div(*[Div(Div(v, cls="text-2xl font-semibold"), Div(t, cls=TextPresets.muted_sm),
                        cls="rounded-md border border-border px-4 py-3")
                    for v, t in ((_pct(ind["cobertura"]), f"Con tutor ({ind['con_tutor']} de {ind['cursando']})"),
                                 (str(ind["tutores"]), "Tutores con estudiantes"), (str(ind["reuniones"]), "Reuniones registradas"),
                                 (str(ind["sin_reunion_12m"]), "Con tutor y sin reunión en 12 meses"))],
                   cls="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6")
    detalle = Card(
        H3("Reuniones y derivaciones", cls="text-base font-semibold mb-2"),
        P("Por año: " + (" · ".join(f"{a}: {n}" for a, n in ind["por_anio"].items()) or "—"), cls="text-sm"),
        P("Por tema: " + " · ".join(f"{t}: {n}" for t, n in ind["temas"].items() if n) or "—", cls="text-sm"),
        P("Derivaciones: " + (" · ".join(f"{t}: {n}" for t, n in ind["derivaciones"].items() if n) or "ninguna"), cls="text-sm"))
    cuerpo = ""
    if _gestiona(auth):
        tutores = tutoria.tutores_elegibles()
        filas_est = [e for e in tutoria.cursando() if (not cohorte or cohortes.texto(e["cohorte_anio"], e["cohorte_ciclo"]) == cohorte)
                     and (solo != "sin_tutor" or e["tutor_id"] is None)]
        opciones_cohorte = sorted({cohortes.texto(e["cohorte_anio"], e["cohorte_ciclo"]) for e in tutoria.cursando()})

        def opciones(actual):
            return [Option("— Elija —", value=""), *[Option(f"{t['apellidos']}, {t['nombres']}", value=str(t["id"]),
                                                            selected=t["id"] == actual) for t in tutores]]
        filas = [Tr(Td(A(f"{e['apellidos']}, {e['nombres']}", href=f"{BASE}/{e['externo_id']}", cls="font-medium hover:underline")
                       if _detalle_direccion(auth) else Span(f"{e['apellidos']}, {e['nombres']}", cls="font-medium")),
                    Td(cohortes.texto(e["cohorte_anio"], e["cohorte_ciclo"]), cls="text-sm"),
                    Td(e["reuniones"], cls="text-sm"), Td(e["ultima"] or "—", cls="text-sm whitespace-nowrap"),
                    Td(Form(Div(Select(*opciones(e["tutor_id"]), name="tutor_id", cls="uk-select w-56", aria_label="Tutor", required=True),
                                Button("Asignar", type="submit", cls=(ButtonT.default, ButtonT.sm)), cls="flex gap-2"),
                            hx_post=f"{DIR}/{e['externo_id']}/asignar", hx_swap="none")))
                 for e in filas_est]
        cuerpo = Div(
            Card(H3("Asignar tutor a una cohorte", cls="text-base font-semibold mb-2"),
                 P("Asigna el tutor a los estudiantes de la cohorte que cursan y aún no tienen tutor.", cls=(TextPresets.muted_sm, "mb-2")),
                 Form(Div(Div(FormLabel("Cohorte"), Select(Option("— Elija —", value=""), *[Option(c, value=c) for c in opciones_cohorte],
                                                          name="cohorte", cls="uk-select", required=True), cls="space-y-1"),
                          Div(FormLabel("Tutor(a)"), Select(*opciones(None), name="tutor_id", cls="uk-select", required=True),
                              cls="space-y-1"), cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
                      Button("Asignar a la cohorte", type="submit", cls=ButtonT.primary), hx_post=f"{DIR}/asignar-cohorte",
                      hx_swap="none", cls="space-y-3")),
            Div(cls="h-4"),
            Card(Div(H3(f"Estudiantes que cursan ({len(filas_est)})", cls="text-base font-semibold"),
                     Form(Select(Option("Todas las cohortes", value=""), *[Option(c, value=c, selected=c == cohorte) for c in opciones_cohorte],
                                 name="cohorte", cls="uk-select w-44", aria_label="Cohorte"),
                          Select(Option("Con y sin tutor", value=""), Option("Solo sin tutor", value="sin_tutor", selected=solo == "sin_tutor"),
                                 name="solo", cls="uk-select w-44", aria_label="Tutor"),
                          Button("Filtrar", type="submit", cls=(ButtonT.default, ButtonT.sm)), method="get", action=DIR,
                          cls="flex flex-wrap gap-2"), cls="flex flex-wrap items-center justify-between gap-2 mb-3"),
                 Div(Table(Thead(Tr(Th("Estudiante"), Th("Cohorte"), Th("Reuniones"), Th("Última"), Th("Tutor(a)"))), Tbody(*filas),
                           cls="uk-table-divider uk-table-middle"), cls="overflow-x-auto")))
    return pagina(
        "Tutoría",
        H2("Tutoría"),
        P("Cada estudiante que cursa tiene un tutor (docente con vínculo vigente) que registra sus reuniones y derivaciones. Aquí "
          "se asignan los tutores y se ve la cobertura; las notas de las reuniones son confidenciales.",
          cls=(TextPresets.muted_sm, "max-w-3xl mb-6")),
        resumen, detalle, Div(cls="h-6"), cuerpo, usuario=auth, seccion="docencia")


@rt(f"{DIR}/{{externo_id}}/asignar")
def post(auth, sess, externo_id: int, tutor_id: str = ""):
    if not _gestiona(auth):
        return _no()
    errores = tutoria.asignar(externo_id, int(tutor_id), auth["id"]) if tutor_id.isdigit() else ["Elija al tutor."]
    add_toast(sess, errores[0] if errores else "Tutor asignado.", "error" if errores else "success")
    return Redirect(DIR)


@rt(f"{DIR}/asignar-cohorte")
def post(auth, sess, cohorte: str = "", tutor_id: str = ""):
    if not _gestiona(auth):
        return _no()
    try:
        anio, ciclo = int(cohorte[:4]), cohorte[5:]
        assert ciclo in ("I", "II") and tutor_id.isdigit()
    except (ValueError, AssertionError):
        add_toast(sess, "Elija la cohorte y el tutor.", "error")
        return Redirect(DIR)
    if not any(t["id"] == int(tutor_id) for t in tutoria.tutores_elegibles()):
        add_toast(sess, "Elija un docente con vínculo vigente.", "error")
        return Redirect(DIR)
    n = tutoria.asignar_cohorte(anio, ciclo, int(tutor_id), auth["id"])
    add_toast(sess, f"{n} estudiante(s) asignado(s)." if n else "No había estudiantes sin tutor en esa cohorte.", "success" if n else "info")
    return Redirect(DIR)
