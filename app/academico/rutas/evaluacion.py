"""Evaluación docente (PLAN §68, etapa 5), lado del personal: el docente ve el instrumento, sus resultados y quién los consultó; la
Dirección de Carrera (`gestionar_evaluacion_docente`) la crea, anuncia, abre, cierra y publica el retorno. Reglas en
`app/academico/evaluacion.py`."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, Li, Option, P, Redirect, Response, Select, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import evaluacion, gestiones
from app.comun import formato, permisos
from app.comun.componentes.layout import campo, mensaje_error, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import get_db

rt = APIRouter()
BASE = "/docencia/evaluacion"
GESTION = f"{BASE}/gestion"
TONOS = {"borrador": "gris", "anunciada": "azul", "abierta": "verde", "cerrada": "gris"}


def _dirige(auth) -> bool:
    return permisos.puede(auth, "gestionar_evaluacion_docente")


def instrumento(e: dict):
    return Card(H3("Instrumento", cls="text-base font-semibold"),
                P("Cada estudiante inscrito responde, por paralelo, cuánto está de acuerdo con cada afirmación (de 1, «totalmente en "
                  "desacuerdo», a 5, «totalmente de acuerdo»). No hay respuestas abiertas.", cls=(TextPresets.muted_sm, "mb-2")),
             Ul(*[Li(f"{n}. {t}", cls="text-sm py-0.5") for n, (_, t) in enumerate(e["criterios"], start=1)]))


def reglas():
    return Card(H3("Cómo se usan los resultados", cls="text-base font-semibold"),
                Ul(Li("Las respuestas son anónimas: no se enlazan con quien las dio ni guardan la hora."),
                   Li(f"Los resultados de un docente se muestran desde {evaluacion.MIN_RESPUESTAS} respuestas; con menos, nadie los ve."),
                   Li("El docente ve los suyos, puede agregar su contexto y ve quién los consultó y cuándo."),
                   Li("La Dirección de Carrera los ve por docente, no en lista, y cada consulta queda registrada."),
                   Li("El instrumento y las fechas se anuncian con al menos "
                      f"{evaluacion.ANTICIPACION_DIAS} días de anticipación."),
                   Li("Los estudiantes reciben el retorno de lo que la Carrera hizo."), cls="text-sm space-y-1 list-disc pl-5"))


@rt(BASE)
def get(auth):
    evs = [e for e in evaluacion.listar() if e["estado"] != "borrador"]
    tarjetas = []
    for e in evs:
        g = evaluacion.gestion_de(e)
        est = evaluacion.estado(e)
        mias = evaluacion.paralelos_de(e["id"], auth["id"])
        tarjetas.append(Card(
            Div(H3(f"Evaluación docente de {gestiones.codigo(g)}", cls="text-base font-semibold"), insignia(evaluacion.ESTADOS[est], TONOS[est]),
                cls="flex items-center justify-between gap-2"),
            P(f"Del {formato.fecha(e['abre_el'])} al {formato.fecha(e['cierra_el'])}.", cls=TextPresets.muted_sm),
            A("Ver mis resultados", href=f"{BASE}/{e['id']}/docente/{auth['id']}", cls="text-sm text-primary hover:underline")
            if est == "cerrada" and mias else
            (P("Usted dicta paralelos evaluados.", cls=TextPresets.muted_sm) if mias and est != "cerrada" else ""),
            instrumento(e), cls="space-y-2"))
    return pagina(
        "Evaluación docente", H2("Evaluación docente"),
        P("El instrumento, las fechas y sus resultados. Mientras la evaluación está en curso no hay resultados para nadie.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Div(*tarjetas, cls="space-y-4") if tarjetas else Card(P("Aún no hay una evaluación anunciada.", cls="text-sm")),
        Div(reglas(), cls="mt-4"),
        P(A("Administrar la evaluación", href=GESTION, cls="text-sm text-primary hover:underline"), cls="mt-4") if _dirige(auth) else "",
        usuario=auth, seccion="docencia")


# --- Dirección de Carrera -----------------------------------------------------------------------------------------------------

def _form_crear(errores=()):
    ya = {e["gestion_id"] for e in evaluacion.listar()}
    candidatas = [g for g in gestiones.listar() if g["tipo"] in ("I", "II") and g["estado"] != "planificacion" and g["id"] not in ya]
    if not candidatas:
        return ""
    return Card(H3("Nueva evaluación", cls="text-base font-semibold"), mensaje_error(*errores), fh.Form(
        campo("Gestión", Select(*[Option(gestiones.codigo(g), value=str(g["id"])) for g in candidatas], name="gestion", cls="uk-select w-40")),
        campo("Abre el", Input(type="date", name="abre_el", required=True, cls="uk-input w-44")),
        campo("Cierra el", Input(type="date", name="cierra_el", required=True, cls="uk-input w-44")),
        Button("Crear", type="submit", cls=ButtonT.primary), method="post", action=GESTION, cls="flex flex-wrap items-end gap-3"))


def _acciones(e):
    est, base = evaluacion.estado(e), f"{BASE}/{e['id']}"

    def boton(texto, ruta, estilo=ButtonT.default, confirmar=None, icono=None):
        return fh.Form(Button(texto, type="submit", cls=(estilo, ButtonT.sm), **({"hx_confirm": confirmar} if confirmar else {})),
                       method="post", action=f"{base}/{ruta}")
    return Div(
        boton("Anunciar", "anunciar", ButtonT.primary, "¿Anunciar? Docentes y estudiantes verán el instrumento y las fechas; ya no cambiarán.")
        if e["estado"] == "borrador" else "",
        boton("Abrir", "abrir", ButtonT.primary, "¿Abrir la evaluación a los estudiantes?") if e["estado"] == "anunciada" else "",
        boton("Cerrar", "cerrar", ButtonT.default, "¿Cerrar la evaluación? Los estudiantes ya no podrán responder.")
        if est in ("abierta", "cerrada") and e["estado"] != "cerrada" else "",
        boton("Eliminar", "eliminar", ButtonT.ghost, "¿Eliminar el borrador?") if e["estado"] == "borrador" else "",
        cls="flex flex-wrap gap-2")


def _tarjeta_direccion(e, errores=()):
    g, est = evaluacion.gestion_de(e), evaluacion.estado(e)
    base = f"{BASE}/{e['id']}"
    cuerpo = [Div(H3(f"Evaluación de {gestiones.codigo(g)}", cls="text-base font-semibold"), insignia(evaluacion.ESTADOS[est], TONOS[est]),
                  cls="flex items-center justify-between gap-2"),
              P(f"Del {formato.fecha(e['abre_el'])} al {formato.fecha(e['cierra_el'])}"
                + (f" · anunciada el {formato.fecha_hora(e['anunciada_en'])}" if e["anunciada_en"] else "") + f" · "
                f"{evaluacion.n_respuestas(e['id'])} respuestas.", cls=TextPresets.muted_sm),
              mensaje_error(*errores), _acciones(e)]
    if e["estado"] in ("borrador", "anunciada"):
        cuerpo.append(fh.Form(
            Input(type="date", name="abre_el", value=e["abre_el"], cls="uk-input w-40", aria_label="Abre el"),
            Input(type="date", name="cierra_el", value=e["cierra_el"], cls="uk-input w-40", aria_label="Cierra el"),
            Button("Cambiar fechas", type="submit", cls=(ButtonT.default, ButtonT.sm)), method="post", action=f"{base}/fechas",
            cls="flex flex-wrap items-center gap-2"))
    if est == "cerrada":
        filas = [fh.Tr(fh.Td(A(f"{p['apellidos']}, {p['nombres']}", href=f"{BASE}/{e['id']}/docente/{p['id']}",
                                cls="text-sm text-primary hover:underline")), fh.Td(str(p["paralelos"]), cls="text-sm"),
                        fh.Td(f"{p['n']}" + (f" de {p['inscritos']}" if p["inscritos"] else ""), cls="text-sm"),
                        fh.Td("Sí" if p["suficiente"] else insignia(f"Menos de {evaluacion.MIN_RESPUESTAS}", "ambar"), cls="text-sm"))
                 for p in evaluacion.participacion(e["id"])]
        cuerpo += [H3("Participación por docente", cls="text-sm font-semibold mt-2"),
                   P("No se muestran resultados en lista: abra a cada docente (la consulta queda en su bitácora).", cls=TextPresets.muted_sm),
                   Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Docente"), fh.Th("Paralelos"), fh.Th("Respuestas"), fh.Th("Hay resultados"))),
                                fh.Tbody(*filas), cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto"),
                   fh.Form(campo("Retorno para los estudiantes: qué hará la Carrera con los resultados",
                                 fh.Textarea(e["retorno"] or "", name="retorno", rows=4, maxlength=evaluacion.MAX_TEXTO, cls="uk-textarea")),
                           Div(Button("Guardar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
                               Button("Guardar y publicar a los estudiantes", type="submit", cls=(ButtonT.primary, ButtonT.sm),
                                      formaction=f"{base}/retorno/publicar"),
                               Button("Retirar la publicación", type="submit", cls=(ButtonT.ghost, ButtonT.sm), formaction=f"{base}/retorno/retirar")
                               if e["retorno_publicado_en"] else "", cls="flex flex-wrap gap-2"),
                           method="post", action=f"{base}/retorno", cls="space-y-2")]
    return Card(*cuerpo, cls="space-y-3")


def _pagina_direccion(auth, errores=(), eid_error=None, errores_crear=()):
    evs = evaluacion.listar()
    return pagina("Administrar la evaluación docente",
                  A(UkIcon("arrow-left", height=14, width=14), "Evaluación docente", href=BASE,
                    cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
                  H2("Administrar la evaluación docente"),
                  P("Una evaluación por semestre: créela, anúnciela con anticipación, ábrala, ciérrela y publique el retorno.",
                    cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
                  _form_crear(errores_crear), *[_tarjeta_direccion(e, errores if e["id"] == eid_error else ()) for e in evs],
                  usuario=auth, seccion="docencia")


@rt(GESTION)
def get(auth, errores: str = "", eid: int = 0):
    if not _dirige(auth):
        return Response("No autorizado", status_code=403)
    return _pagina_direccion(auth, [x for x in errores.split("|") if x], eid)


@rt(GESTION)
def post(auth, sess, gestion: str = "", abre_el: str = "", cierra_el: str = ""):
    if not _dirige(auth):
        return Response("No autorizado", status_code=403)
    eid, errores = evaluacion.crear(int(gestion) if gestion.isdigit() else 0, abre_el, cierra_el, auth["id"])
    if errores:
        return _pagina_direccion(auth, errores_crear=errores)
    add_toast(sess, "Evaluación creada en borrador.", "success")
    return Redirect(GESTION)


def _accion(auth, sess, eid: int, hacer, ok: str):
    if not _dirige(auth):
        return Response("No autorizado", status_code=403)
    if not evaluacion.obtener(eid):
        return Response("No encontrado", status_code=404)
    errores = hacer()
    if errores:
        return Redirect(f"{GESTION}?eid={eid}&errores={'|'.join(errores)}")
    add_toast(sess, ok, "success")
    return Redirect(GESTION)


@rt(f"{BASE}/{{eid}}/anunciar")
def post(auth, sess, eid: int):
    return _accion(auth, sess, eid, lambda: evaluacion.anunciar(eid, auth["id"]), "Evaluación anunciada; se avisó a los docentes.")


@rt(f"{BASE}/{{eid}}/abrir")
def post(auth, sess, eid: int):
    return _accion(auth, sess, eid, lambda: evaluacion.abrir(eid, auth["id"]), "Evaluación abierta.")


@rt(f"{BASE}/{{eid}}/cerrar")
def post(auth, sess, eid: int):
    return _accion(auth, sess, eid, lambda: evaluacion.cerrar(eid, auth["id"]), "Evaluación cerrada.")


@rt(f"{BASE}/{{eid}}/eliminar")
def post(auth, sess, eid: int):
    return _accion(auth, sess, eid, lambda: evaluacion.eliminar(eid, auth["id"]), "Borrador eliminado.")


@rt(f"{BASE}/{{eid}}/fechas")
def post(auth, sess, eid: int, abre_el: str = "", cierra_el: str = ""):
    return _accion(auth, sess, eid, lambda: evaluacion.actualizar_fechas(eid, abre_el, cierra_el, auth["id"]), "Fechas actualizadas.")


@rt(f"{BASE}/{{eid}}/retorno")
def post(auth, sess, eid: int, retorno: str = ""):
    return _accion(auth, sess, eid, lambda: evaluacion.guardar_retorno(eid, retorno), "Retorno guardado.")


@rt(f"{BASE}/{{eid}}/retorno/publicar")
def post(auth, sess, eid: int, retorno: str = ""):
    return _accion(auth, sess, eid, lambda: evaluacion.guardar_retorno(eid, retorno) or evaluacion.publicar_retorno(eid, auth["id"]),
                   "Retorno publicado a los estudiantes.")


@rt(f"{BASE}/{{eid}}/retorno/retirar")
def post(auth, sess, eid: int):
    return _accion(auth, sess, eid, lambda: evaluacion.retirar_retorno(eid) or [], "Publicación retirada.")


# --- Resultados de un docente --------------------------------------------------------------------------------------------------

def _tabla(criterios):
    return Div(fh.Table(
        fh.Thead(fh.Tr(fh.Th("Afirmación"), fh.Th("Media"), *[fh.Th(str(v)) for v, _ in evaluacion.ESCALA])),
        fh.Tbody(*[fh.Tr(fh.Td(c["texto"], cls="text-sm"),
                         fh.Td(formato.numero(c["media"]) if c["media"] is not None else "—", cls="text-sm font-semibold tabular-nums"),
                         *[fh.Td(str(c["distribucion"][v]), cls="text-sm tabular-nums") for v, _ in evaluacion.ESCALA])
                   for c in criterios]), cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")


@rt(f"{BASE}/{{eid}}/docente/{{uid}}")
def get(auth, eid: int, uid: int, errores: str = ""):
    propio = uid == auth["id"]
    if not propio and not _dirige(auth):
        return Response("No autorizado", status_code=403)
    e = evaluacion.obtener(eid)
    persona = get_db().q("SELECT nombres, apellidos FROM usuario WHERE id = ?", [uid])
    if not e or not persona:
        return Response("No encontrado", status_code=404)
    r = evaluacion.resultados_de(eid, uid)
    if r is None:
        return Response("Los resultados se ven cuando la evaluación está cerrada.", status_code=404)
    evaluacion.registrar_consulta(eid, uid, auth["id"])          # no registra si es el propio docente
    g = evaluacion.gestion_de(e)
    nombre = f"{persona[0]['nombres']} {persona[0]['apellidos']}"
    ctx = evaluacion.contexto(eid, uid)
    cuerpo = [Card(P(f"{r['n']} respuesta(s) en sus paralelos de {gestiones.codigo(g)}.", cls="text-sm"),
                   P(f"Media global: {formato.numero(evaluacion.media_global(r))} de 5.", cls="text-sm font-semibold mt-1")
                   if r["suficiente"] else P(f"Aún no hay suficientes respuestas para mostrar resultados (mínimo {evaluacion.MIN_RESPUESTAS}): "
                                             "así nadie puede reconocer a quien respondió.", cls="text-sm"))]
    if r["suficiente"]:
        cuerpo.append(Card(H3("Resultados", cls="text-base font-semibold mb-2"), _tabla(r["criterios"])))
        cuerpo += [Card(H3(f"{p['sigla']} · paralelo {p['paralelo']} ({p['n']} respuestas)", cls="text-base font-semibold mb-2"),
                        _tabla(p["criterios"])) for p in r["paralelos"]]
    cuerpo.append(Card(H3("Contexto del docente", cls="text-base font-semibold"),
                       fh.Form(mensaje_error(*[x for x in errores.split("|") if x]),
                               fh.Textarea(ctx, name="contexto", rows=4, maxlength=evaluacion.MAX_TEXTO, cls="uk-textarea",
                                           aria_label="Su contexto"),
                               P("Lo que quiera que quien consulte sus resultados tenga en cuenta (curso numeroso, primera vez, cambios).",
                                 cls=TextPresets.muted_sm),
                               Button("Guardar mi contexto", type="submit", cls=(ButtonT.default, ButtonT.sm)),
                               method="post", action=f"{BASE}/{eid}/contexto", cls="space-y-2") if propio
                       else P(ctx or "El docente no agregó contexto.", cls="text-sm")))
    if propio:
        cs = evaluacion.consultas(eid, uid)
        cuerpo.append(Card(H3("Quién consultó sus resultados", cls="text-base font-semibold"),
                           Ul(*[Li(f"{c['nombres']} {c['apellidos']} · {formato.fecha_hora(c['consultada_en'])}", cls="text-sm py-0.5")
                                for c in cs]) if cs else P("Nadie más los ha consultado.", cls=TextPresets.muted_sm)))
    return pagina(f"Resultados de {nombre}",
                  A(UkIcon("arrow-left", height=14, width=14), "Evaluación docente", href=BASE if propio else GESTION,
                    cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
                  H2(f"Resultados de {nombre}" if not propio else "Mis resultados"), P(f"Evaluación de {gestiones.codigo(g)}.",
                                                                                    cls=(TextPresets.muted_sm, "mb-4")),
                  Div(*cuerpo, cls="space-y-4"), usuario=auth, seccion="docencia")


@rt(f"{BASE}/{{eid}}/contexto")
def post(auth, sess, eid: int, contexto: str = ""):
    errores = evaluacion.guardar_contexto(eid, auth["id"], contexto)
    if errores:
        return Redirect(f"{BASE}/{eid}/docente/{auth['id']}?errores={'|'.join(errores)}")
    add_toast(sess, "Contexto guardado.", "success")
    return Redirect(f"{BASE}/{eid}/docente/{auth['id']}")
