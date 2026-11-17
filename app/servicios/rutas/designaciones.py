"""Resultado y designación de las auxiliaturas (PLAN §70, etapa 5): invitaciones, designaciones con sus documentos y memorándum,
informe final con las resoluciones y documentación para Bienestar Social. Las gestiona quien gestiona la convocatoria; el estudiante
responde sus invitaciones desde /estudiante/auxiliaturas."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, P, Redirect, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, ButtonT, LabelInput, TextPresets

from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar
from app.servicios import auxiliaturas as aux
from app.servicios import designaciones as des
from app.servicios.rutas.comun import boton_post, enviar, fecha, formulario, no_autorizado, no_encontrado, tarjeta

rt = APIRouter()
BASE = "/servicios/auxiliaturas"
EST = "/estudiante/auxiliaturas"
TONO_INVITACION = {"pendiente": "ambar", "aceptada": "verde", "rechazada": "gris"}


def _gestionable(auth, cid):
    c = aux.obtener(cid)
    return c if c and aux.puede_gestionar(auth, c["modalidad"]) and des.aplica(c) else None


def _alerta(texto: str, bien: bool):
    return P(texto, cls="text-sm " + ("text-green-700 dark:text-green-300" if bien else "text-amber-700 dark:text-amber-300"))


def _form_designado(d, url):
    campos = Div(*[LabelInput(texto, id=f"{k}_{d['id']}", name=k, type="date", value=d[k] or "")
                   for k, texto in (("cert_deudas", "Certificado de no tener deudas"), ("cert_procesos", "Certificado de la sala de procesos"),
                                    ("sigep", "Registro en el SIGEP"))],
                  cls="grid grid-cols-1 sm:grid-cols-3 gap-3")
    memo = Div(LabelInput("Memorándum (número)", id=f"memorandum_{d['id']}", name="memorandum", value=d["memorandum"] or "", maxlength="120"),
               LabelInput("Fecha del memorándum", id=f"memorandum_fecha_{d['id']}", name="memorandum_fecha", type="date",
                          value=d["memorandum_fecha"] or ""),
               LabelInput("Rige desde (1 o 15)", id=f"inicio_{d['id']}", name="inicio", type="date", value=d["inicio"] or ""),
               LabelInput("Hasta", id=f"fin_{d['id']}", name="fin", type="date", value=d["fin"] or ""),
               cls="grid grid-cols-1 sm:grid-cols-4 gap-3")
    return formulario(f"{url}/designaciones/{d['id']}", campos, memo,
                      Div(enviar("Guardar", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"), cls="space-y-3 mt-2")


@rt(f"{BASE}/{{cid}}/designacion")
def get(auth, cid: int):
    c = _gestionable(auth, cid)
    if not c:
        return no_autorizado()
    url = f"{BASE}/{cid}"
    lista = des.designaciones(cid)
    informe = des.aviso_informe(c)
    limite = des.limite_documentos(cid)
    entregada = des.documentacion(cid)
    limite_doc = des.limite_documentacion(cid)
    bloques = []
    for it in aux.items(cid):
        propios = [d for d in lista if d["item_id"] == it["id"]]
        invs = des.invitaciones(it["id"])
        cubiertas = des.cubiertas(it)
        por_invitar = des._por_invitar(it) if des.puede_invitar(it) else []
        pendientes_postulantes = any(v["estado"] == "pendiente" and v["origen"] == "postulante" for v in invs)
        bloques.append(tarjeta(
            it["titulo"],
            P(f"{it['plazas']} plaza(s) · {it['horas']} h/mes · {cubiertas} cubierta(s)" + (f" · {it['plazas'] - cubiertas} sin cubrir" if cubiertas < it["plazas"] else ""),
              cls=(TextPresets.muted_sm, "mb-2")),
            P("El concurso de este ítem aún no concluyó.", cls=TextPresets.muted_sm) if it["fase"] != "concluido" else "",
            Ul(*[Li(fh.Details(
                fh.Summary(Span(f"{d['nombres']} {d['apellidos']}", cls="font-medium"), " ", insignia(des.CATEGORIAS[d["categoria"]], "verde"),
                           Span(f" · faltan {len(d['faltan'])} documento(s)" if d["faltan"] else " · documentos completos",
                                cls="text-xs " + ("text-amber-700 dark:text-amber-300" if d["faltan"] else "text-green-700 dark:text-green-300")),
                           Span(f" · memorándum {d['memorandum']}" if d["memorandum"] else "", cls=TextPresets.muted_sm),
                           cls="text-sm cursor-pointer"),
                _form_designado(d, BASE)), cls="py-2") for d in propios], cls="divide-y divide-border") if propios else
            (P("Aún no hay designados.", cls=TextPresets.muted_sm) if it["fase"] == "concluido" else ""),
            Div(P("Invitaciones (arts. 6 y 13)", cls="text-sm font-semibold mt-4"),
                Ul(*[Li(Div(Span(f"{v['orden']}. {v['nombres']} {v['apellidos']}", cls="font-medium"),
                            Span(f" · {des.ORIGENES[v['origen']]}" + (f" · {v['puntaje']:g} puntos" if v["puntaje"] is not None else "")
                                 + (f" · {v['nota']}" if v["nota"] else ""), cls=TextPresets.muted_sm), cls="text-sm"),
                         insignia(des.ESTADOS_INVITACION[v["estado"]], TONO_INVITACION[v["estado"]]),
                         Div(boton_post("Aceptó", f"{BASE}/invitaciones/{v['id']}/responder?acepta=1", cls=(ButtonT.default, ButtonT.xs)),
                             boton_post("No aceptó", f"{BASE}/invitaciones/{v['id']}/responder?acepta=0", cls=(ButtonT.ghost, ButtonT.xs)),
                             cls="flex gap-1") if v["estado"] == "pendiente" else "",
                         cls="flex flex-wrap items-center justify-between gap-2 py-1") for v in invs], cls="divide-y divide-border") if invs else "",
                boton_post(f"Invitar a los {len(por_invitar)} postulante(s) con 51 a 55 puntos", f"{BASE}/item/{it['id']}/invitaciones",
                           "mail", cls=(ButtonT.default, ButtonT.sm), confirmar="Se avisará a cada uno. ¿Invitar?") if por_invitar else "",
                formulario(f"{BASE}/item/{it['id']}/invitaciones/estudiante",
                           P("Si nadie de ellos acepta, se invita a los mejores estudiantes de la materia (los certifica Kardex).",
                             cls=TextPresets.muted_sm),
                           Div(LabelInput("Registro universitario (RU)", id=f"ru_{it['id']}", name="ru", maxlength="30"),
                               LabelInput("De dónde sale (p. ej. promedio de las dos últimas gestiones)", id=f"nota_{it['id']}", name="nota",
                                          maxlength="300"), cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
                           Div(enviar("Invitar", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"), cls="space-y-2 mt-2")
                if des.puede_invitar(it) and not por_invitar and not pendientes_postulantes else "",
                cls="space-y-2") if des.puede_invitar(it) or invs else "",
            cls="mb-4"))
    return pagina(
        f"Resultado y designación · {c['titulo']}",
        A("← " + c["titulo"], href=url, cls="text-sm text-primary"),
        H2("Resultado y designación", cls="mt-2"),
        P(f"{c['titulo']} · según el {aux.reglamento_texto(c)}.", cls=(TextPresets.muted_sm, "mb-4")),
        _alerta(f"Los documentos de los ganadores se reciben hasta el {fecha(limite.strftime('%Y-%m-%dT%H:%M'))} (72 horas de concluido el proceso; "
                "art. 23)." + (" El plazo pasó." if des.documentos_vencidos(cid) else ""), not des.documentos_vencidos(cid))
        if limite else P("El proceso aún no concluyó: los plazos de los arts. 22 y 23 corren desde entonces.", cls=TextPresets.muted_sm),
        Div(tarjeta("Informe final y resoluciones (art. 22)",
                    _alerta(informe[1], informe[0]) if informe else "",
                    formulario(f"{url}/informe",
                               Div(LabelInput("Informe entregado el", id="informe_final_en", name="informe_final_en", type="date",
                                              value=c["informe_final_en"] or ""),
                                   LabelInput("Resolución del Consejo de Carrera que aprueba los resultados", id="resolucion_resultados",
                                              name="resolucion_resultados", value=c["resolucion_resultados"] or "", maxlength="120"),
                                   LabelInput("Homologación del Consejo Facultativo", id="resolucion_resultados_hcf", name="resolucion_resultados_hcf",
                                              value=c["resolucion_resultados_hcf"] or "", maxlength="120"),
                                   cls="grid grid-cols-1 sm:grid-cols-3 gap-3"),
                               Div(enviar("Guardar", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"), cls="space-y-2"),
                    cls="mb-6"),
            *bloques,
            tarjeta("Documentación para Bienestar Social (art. 27)",
                    P("La Dirección de Carrera la entrega a la Sección de Becas Académicas" + (
                        f" hasta el {fecha(limite_doc.isoformat())} (15 días del último memorándum)." if limite_doc else ", 15 días después de emitidos los memorándums."),
                      cls=(TextPresets.muted_sm, "mb-2")),
                    formulario(f"{url}/documentacion",
                               Div(*[LabelInput(texto, id=f"doc_{k}", name=k, type="date", value=entregada.get(k, ""))
                                     for k, texto in des.DOCUMENTACION.items()], cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
                               P("La fecha en que se entregó cada documento; en blanco, aún no.", cls=TextPresets.muted_sm),
                               Div(enviar("Guardar", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"), cls="space-y-2")),
            cls="max-w-4xl space-y-0"),
        usuario=auth)


@rt(f"{BASE}/{{cid}}/informe")
def post(auth, sess, cid: int, informe_final_en: str = "", resolucion_resultados: str = "", resolucion_resultados_hcf: str = ""):
    c = _gestionable(auth, cid)
    if not c:
        return no_autorizado()
    errores = des.guardar_informe(cid, informe_final_en, resolucion_resultados, resolucion_resultados_hcf)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "informe_final_auxiliatura", "convocatoria_auxiliatura", cid, resolucion_resultados[:120])
        add_toast(sess, "Informe y resoluciones guardados.", "success")
    return Redirect(f"{BASE}/{cid}/designacion")


@rt(f"{BASE}/{{cid}}/documentacion")
async def post(auth, sess, req, cid: int):
    c = _gestionable(auth, cid)
    if not c:
        return no_autorizado()
    f = await req.form()
    errores = des.guardar_documentacion(cid, {k: f.get(k, "") for k in des.DOCUMENTACION}, auth["id"])
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "documentacion_auxiliatura", "convocatoria_auxiliatura", cid)
        add_toast(sess, "Documentación guardada.", "success")
    return Redirect(f"{BASE}/{cid}/designacion")


@rt(f"{BASE}/designaciones/{{did}}")
async def post(auth, sess, req, did: int):
    d = des.designacion(did)
    c = _gestionable(auth, d["convocatoria_id"]) if d else None
    if not c:
        return no_autorizado()
    f = await req.form()
    errores = des.guardar_designacion(did, {k: f.get(k, "") for k in ("cert_deudas", "cert_procesos", "sigep", "memorandum",
                                                                       "memorandum_fecha", "inicio", "fin")})
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "designacion_auxiliatura", "designacion_auxiliatura", did)
        add_toast(sess, "Designación guardada.", "success")
    return Redirect(f"{BASE}/{c['id']}/designacion")


def _item_gestionable(auth, iid):
    it = aux.item(iid)
    c = _gestionable(auth, it["convocatoria_id"]) if it else None
    return (it, c) if c else (None, None)


@rt(f"{BASE}/item/{{iid}}/invitaciones")
def post(auth, sess, iid: int):
    it, c = _item_gestionable(auth, iid)
    if not it:
        return no_autorizado()
    errores = des.generar_invitaciones(it, auth["id"])
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "invitar_auxiliares", "item_auxiliatura", iid)
        add_toast(sess, "Se invitó a los postulantes y se les avisó.", "success")
    return Redirect(f"{BASE}/{c['id']}/designacion")


@rt(f"{BASE}/item/{{iid}}/invitaciones/estudiante")
def post(auth, sess, iid: int, ru: str = "", nota: str = ""):
    it, c = _item_gestionable(auth, iid)
    if not it:
        return no_autorizado()
    errores = des.invitar_mejor_estudiante(it, ru, nota, auth["id"])
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "invitar_mejor_estudiante", "item_auxiliatura", iid, ru)
        add_toast(sess, "Se invitó al estudiante y se le avisó.", "success")
    return Redirect(f"{BASE}/{c['id']}/designacion")


@rt(f"{BASE}/invitaciones/{{vid}}/responder")
def post(auth, sess, vid: int, acepta: int = 0):
    v = des.invitacion(vid)
    it, c = _item_gestionable(auth, v["item_id"]) if v else (None, None)
    if not it:
        return no_autorizado()
    errores = des.responder_invitacion(vid, bool(acepta))
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "responder_invitacion_auxiliatura", "invitacion_auxiliatura", vid, "acepta" if acepta else "no acepta")
    return Redirect(f"{BASE}/{c['id']}/designacion")


# --- Estudiante: responde sus invitaciones -----------------------------------------------------------------------------------

@rt(f"{EST}/invitaciones/{{vid}}/responder")
def post(auth, sess, vid: int, acepta: int = 0):
    from app.comun.estudiantes import requiere as _requiere
    externo, error = _requiere(auth)
    if error:
        return error
    v = des.invitacion(vid)
    if not v or v["externo_id"] != externo:
        return no_encontrado()
    errores = des.responder_invitacion(vid, bool(acepta))
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "responder_invitacion_auxiliatura", "invitacion_auxiliatura", vid, "acepta" if acepta else "no acepta")
        add_toast(sess, "Gracias: registramos su respuesta." if acepta else "Registramos que no acepta la invitación.", "success")
    return Redirect(EST)

