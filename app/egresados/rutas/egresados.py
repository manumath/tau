"""Egresados (PLAN §50): titulación, seguimiento programado a los 6 meses, 1, 3 y 5 años, e indicadores. Ven los
indicadores (agregados, con su n) quienes ven el seguimiento estudiantil; la lista de egresados, el registro de la
titulación y el seguimiento los gestionan la Dirección de Carrera y la Coordinación académica."""
from fasthtml.common import A, APIRouter, Div, Option, P, Redirect, Response, Select, Span, Thead, Tr
from fasthtml.toaster import add_toast
from monsterui.all import (H2, H3, Button, ButtonT, Card, Form, FormLabel, LabelInput, Table, Tbody, Td, TextPresets, Th,
                           UkIcon)

from app.comun import permisos, vinculos
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.egresados import directorio, egresados
from app.estudiantil import cohortes

rt = APIRouter()
BASE = "/docencia/egresados"
directorio_base = f"{BASE}/directorio"
TONOS = {"respondido": "verde", "invitado": "azul", "omitido": "gris"}
ETIQUETAS = {"respondido": "Respondió", "invitado": "Invitado(a)", "omitido": "Omitido"}


def _ver(auth) -> bool:
    return permisos.puede(auth, "ver_seguimiento_estudiantil", vinculos.carrera())


def _gestiona(auth) -> bool:
    return permisos.puede(auth, "gestionar_egresados", vinculos.carrera())


def _no():
    return Response("No autorizado", status_code=403)


def _pct(x):
    return "—" if x is None else f"{x * 100:.0f} %"


def _num(x, dec=1):
    return "—" if x is None else f"{x:.{dec}f}".replace(".", ",")


def _boton(texto, url, *, confirmar=None, cls=ButtonT.default, icono=None):
    return Form(Button(UkIcon(icono, height=14, width=14) if icono else "", texto, type="submit", cls=cls),
                hx_post=url, hx_swap="none", **({"hx_confirm": confirmar} if confirmar else {}))


def _tabla_trienios(ind):
    filas = [Tr(Td(f"{t['desde']}–{t['hasta']}", cls="font-medium"), Td(t["titulados"]), Td(_num(t["anios_medios"])),
                Td(f"{t['respondieron']} ({_pct(t['tasa_respuesta'])})"),
                Td(f"{_pct(t['empleo'])} (n = {t['n_situacion']})"), Td(_pct(t["en_el_area"])),
                Td(f"{_pct(t['posgrado'])} (n = {t['n_posgrado']})"), Td(_num(t["utilidad"], 2)), Td(_num(t["satisfaccion"], 2)))
             for t in ind["trienios"]]
    return Div(Table(Thead(Tr(Th("Titulados en"), Th("Titulados"), Th("Años hasta titularse"), Th("Respondieron el seguimiento"),
                              Th("Con empleo"), Th("En su área"), Th("Posgrado"), Th("Utilidad (1 a 5)"), Th("Satisfacción (1 a 5)"))),
                     Tbody(*filas) if filas else Tbody(Tr(Td("Aún no hay egresados titulados cargados.", colspan=9,
                                                             cls=(TextPresets.muted_sm, "text-center py-6")))),
                     cls="uk-table-divider uk-table-middle", data_tabla="egresados", data_tabla_filtro="no"),
               cls="overflow-x-auto")


def _panel_seguimiento(auth):
    est = egresados.estado_seguimiento()
    filas = [Tr(Td(e["nombre"] + " después de titularse", cls="font-medium"),
                Td(A("Abierta", href=f"/docencia/encuestas/{e['encuesta']['id']}", cls="text-primary hover:underline")
                   if e["encuesta"] else Span("Sin activar", cls=TextPresets.muted_sm)),
                Td(e["invitados"]), Td(f"{e['respondidos']} ({_pct(e['respondidos'] / e['invitados'] if e['invitados'] else None)})"),
                Td(e["omitidos"]), Td(e["pendientes"])) for e in est]
    sin = egresados.hitos_sin_encuesta()
    pendientes = sum(e["pendientes"] for e in est)
    acciones = Div(
        _boton("Activar el seguimiento", f"{BASE}/seguimiento/activar", cls=ButtonT.primary, icono="play",
               confirmar="Se crearán y abrirán las encuestas de seguimiento que falten (6 meses, 1, 3 y 5 años). A partir de "
                         "entonces, cada egresado recibirá su invitación al cumplir cada hito. ¿Activar?") if sin else "",
        _boton(f"Invitar ahora a quienes corresponde ({pendientes})", f"{BASE}/seguimiento/invitar", icono="send",
               confirmar=f"Se enviará el correo de invitación a {min(pendientes, 50)} egresado(s). ¿Continuar?") if pendientes else "",
        cls="flex flex-wrap gap-2 mt-3") if _gestiona(auth) else ""
    return Card(
        H3("Seguimiento a los 6 meses, 1, 3 y 5 años", cls="text-base font-semibold"),
        P("Cada egresado titulado recibe por correo la encuesta del último hito que cumplió. Si al activar el seguimiento ya "
          "pasaron varios, se le invita solo al último (los anteriores quedan «omitidos»). Las invitaciones también salen solas, "
          "en la revisión horaria del sistema.", cls=(TextPresets.muted_sm, "mb-3")),
        Div(Table(Thead(Tr(Th("Encuesta"), Th("Estado"), Th("Invitados"), Th("Respondieron"), Th("Omitidos"), Th("Por invitar hoy"))),
                  Tbody(*filas), cls="uk-table-divider uk-table-middle"), cls="overflow-x-auto"), acciones)


def _chips(seguimiento: dict):
    if not seguimiento:
        return Span("—", cls=TextPresets.muted_sm)
    return Div(*[Span(Span(f"{egresados.HITOS[h][0]}: ", cls="text-xs"), insignia(ETIQUETAS[seguimiento[h]], TONOS[seguimiento[h]]),
                      cls="inline-flex items-center gap-1")
                 for h in egresados.HITOS if h in seguimiento], cls="flex flex-wrap items-center gap-2")


def _directorio(g):
    estado = directorio.estado_directorio(g["externo_id"])
    if estado == "visible":
        return insignia("Figura", "verde")
    if not (g["email"] or "").strip():
        return Span("Sin correo", cls=TextPresets.muted_sm)
    return Div(insignia("Invitado(a)", "azul") if estado == "invitado" else "",
               _boton("Reenviar" if estado == "invitado" else "Invitar", f"{directorio_base}/invitar/{g['externo_id']}",
                      cls=(ButtonT.ghost, ButtonT.sm)), cls="flex items-center gap-1")


def _lista(auth):
    gente = egresados.titulados()
    filas = [Tr(Td(f"{g['apellidos']}, {g['nombres']}", cls="font-medium"),
                Td(cohortes.texto(g["cohorte_anio"], g["cohorte_ciclo"]), cls="text-sm"), Td(g["fecha_titulacion"], cls="text-sm"),
                Td(cohortes.MODALIDADES.get(g["modalidad_titulacion"], "—"), cls="text-sm"),
                Td(_chips(g["seguimiento"])),
                Td(_directorio(g)))
             for g in gente]
    return Card(
        Div(H3(f"Egresados titulados ({len(gente)})", cls="text-base font-semibold"),
            Div(A(UkIcon("book-user", height=14, width=14), "Ver el directorio", href=directorio_base,
                  cls="uk-btn uk-btn-default uk-btn-small inline-flex items-center gap-1"),
                _boton("Invitar al directorio a quienes faltan", f"{directorio_base}/invitar-pendientes", icono="send",
                       cls=(ButtonT.default, ButtonT.sm),
                       confirmar="Se enviará la invitación al directorio (y se creará su cuenta) a los egresados con correo que aún no la "
                                 "recibieron, hasta 50. ¿Continuar?"),
                Button(UkIcon("graduation-cap", height=16, width=16), "Registrar titulación", cls=(ButtonT.primary, ButtonT.sm),
                       hx_get=f"{BASE}/titular", hx_target=f"#{ID_MODAL}"), cls="flex flex-wrap items-center gap-2"),
            cls="flex flex-wrap items-center justify-between gap-2 mb-3"),
        Div(Table(Thead(Tr(Th("Egresado"), Th("Cohorte"), Th("Titulación"), Th("Modalidad"), Th("Seguimiento"), Th("Directorio"))),
                  Tbody(*filas) if filas else Tbody(Tr(Td("Aún no hay egresados titulados.", colspan=6,
                                                          cls=(TextPresets.muted_sm, "text-center py-6")))),
                  cls="uk-table-divider uk-table-middle", data_tabla="lista-egresados", data_tabla_filtro="no"),
            cls="overflow-x-auto"))


@rt(BASE)
def get(auth):
    if not _ver(auth):
        return _no()
    ind = egresados.indicadores()
    resumen = Div(*[Div(Div(v, cls="text-2xl font-semibold"), Div(t, cls=TextPresets.muted_sm),
                        cls="rounded-md border border-border px-4 py-3")
                    for v, t in ((str(ind["total"]), "Egresados titulados"),
                                 (str(ind["respondieron"]), "Respondieron el seguimiento"),
                                 (_num(ind["anios_medios"]), "Años medios hasta titularse"))],
                   cls="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6")
    mod = P("Modalidad de titulación: " + " · ".join(f"{cohortes.MODALIDADES.get(k, k)}: {v}" for k, v in ind["modalidades"].items()),
            cls=(TextPresets.muted_sm, "mt-3")) if ind["modalidades"] else ""
    return pagina(
        "Egresados",
        H2("Egresados"),
        P("Titulación y seguimiento de los egresados de la licenciatura. Quien se titula entra solo al seguimiento. Los "
          "indicadores usan la última respuesta de cada egresado y siempre muestran cuántos respondieron (n): con pocos "
          "titulados por año se agrupan en trienios para no sacar tendencias de unos cuantos casos.",
          cls=(TextPresets.muted_sm, "max-w-3xl mb-6")),
        resumen,
        Card(H3("Indicadores por trienio de titulación", cls="text-base font-semibold mb-2"), _tabla_trienios(ind), mod),
        Div(cls="h-6"), _panel_seguimiento(auth),
        Div(cls="h-6"), _lista(auth) if _gestiona(auth) else "",
        usuario=auth, seccion="docencia")


# --- Acciones --------------------------------------------------------------------------------------------------

@rt(f"{BASE}/seguimiento/activar")
def post(auth, sess):
    if not _gestiona(auth):
        return _no()
    n = egresados.activar_seguimiento(auth["id"])
    add_toast(sess, f"Seguimiento activado: {n} encuesta(s) abierta(s)." if n else "El seguimiento ya estaba activo.", "success")
    return Redirect(BASE)


@rt(f"{BASE}/seguimiento/invitar")
def post(auth, sess):
    if not _gestiona(auth):
        return _no()
    r = egresados.programar(uid=auth["id"])
    texto = f"{r['invitados']} invitación(es) enviada(s)." if r["invitados"] else "No había invitaciones por enviar."
    if r["sin_correo"]:
        texto += f" {r['sin_correo']} egresado(s) sin correo."
    add_toast(sess, texto, "success" if r["invitados"] else "info")
    return Redirect(BASE)


def _form_titular(d=None, errores=()):
    d = d or {}
    return modal(
        "Registrar titulación",
        Form(mensaje_error(*errores),
             P("Pasa a «titulado» y entra al seguimiento de egresados. Si no indica la fecha de egreso, se toma la de titulación.",
               cls=TextPresets.muted_sm),
             Div(FormLabel("Estudiante"), Select(Option("— Elija —", value=""),
                                                *[Option(f"{c['apellidos']}, {c['nombres']} · cohorte {cohortes.texto(c['cohorte_anio'], c['cohorte_ciclo'])}",
                                                         value=str(c["id"]), selected=str(c["id"]) == str(d.get("estudiante_id")))
                                                  for c in egresados.candidatos_titulacion()],
                                                name="estudiante_id", cls="uk-select", required=True), cls="space-y-1"),
             Div(LabelInput("Fecha de egreso (opcional)", id="fecha_egreso", type="date", value=d.get("fecha_egreso") or ""),
                 LabelInput("Fecha de titulación", id="fecha_titulacion", type="date", value=d.get("fecha_titulacion") or "",
                            required=True), cls="grid grid-cols-2 gap-3"),
             Div(FormLabel("Modalidad de titulación"),
                 Select(Option("— Sin dato —", value=""), *[Option(t, value=k, selected=k == d.get("modalidad"))
                                                            for k, t in cohortes.MODALIDADES.items()],
                        name="modalidad", cls="uk-select"), cls="space-y-1"),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                 Button("Registrar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post=f"{BASE}/titular", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt(f"{BASE}/titular")
def get(auth):
    return _form_titular() if _gestiona(auth) else _no()


@rt(f"{BASE}/titular")
def post(auth, sess, estudiante_id: str = "", fecha_egreso: str = "", fecha_titulacion: str = "", modalidad: str = ""):
    if not _gestiona(auth):
        return _no()
    d = dict(estudiante_id=estudiante_id, fecha_egreso=fecha_egreso, fecha_titulacion=fecha_titulacion, modalidad=modalidad)
    errores = egresados.titular(int(estudiante_id), d, auth["id"]) if estudiante_id.isdigit() else ["Elija al estudiante."]
    if errores:
        return _form_titular(d, errores)
    add_toast(sess, "Titulación registrada: ya figura entre los egresados.", "success")
    return Redirect(BASE)
