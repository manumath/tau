"""Pantallas de los trámites de grado (PLAN §58, servicio 2): el estudiante arma su perfil o su documento final en
/estudiante/grado; el tutor, la Dirección o Coordinación y el tribunal lo atienden en /servicios/grado."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, P, Pre, Redirect, Span, Table, Tbody, Td, Th, Thead, Tr, Ul, UploadFile
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, ButtonT, LabelInput, TextPresets, UkIcon

from app.comun import config
from app.comun.componentes.etapas import etapas
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar
from app.investigacion import adjuntos
from app.servicios import grado, latex
from app.servicios.rutas.comun import (area, boton_post, descarga_bytes, descargar, enlace_adjunto, enviar, falta, fecha,
                                       formulario, le_toca, leer_archivo, no_autorizado, no_encontrado, seleccion, subir,
                                       tarjeta)

rt = APIRouter()
BASE = "/servicios/grado"
EST = "/estudiante/grado"
TONO = {"borrador": "gris", "con_tutor": "azul", "enviado": "azul", "en_revision": "azul", "observado": "ambar",
        "favorable": "verde", "aprobado": "verde", "rechazado": "rojo", "defendido": "verde", "reprobado": "rojo"}


def _estudiante(auth):
    from app.estudiantil.rutas.estudiante import _requiere
    return _requiere(auth)


def _pasos(t):
    orden = ["borrador", "con_tutor", "enviado", "en_revision", "favorable", "cierre"]
    e = t["estado"]
    pos = {"borrador": 0, "con_tutor": 1, "enviado": 2, "en_revision": 3, "observado": 3, "favorable": 4,
           "aprobado": 5, "defendido": 5, "rechazado": 3, "reprobado": 5}[e]
    final = t["tipo"] == "final"
    titulos = ["Documento" if final else "Borrador", "Visto bueno del tutor", "Designación del tribunal",
               "Revisión del tribunal" + (f" ({t['ronda']}.ª)" if t["ronda"] > 1 else ""), "Dictamen favorable",
               "Defensa" if final else "Resolución"]
    pasos = []
    for i, _ in enumerate(orden):
        estado = "hecho" if i < pos else "actual" if i == pos else "pendiente"
        if i == pos and e == "observado":
            estado = "alerta"
        if i == pos and e in ("rechazado", "reprobado"):
            estado = "error"
        if i == pos and e in ("aprobado", "defendido"):
            estado = "hecho"
        if e == "rechazado" and i > pos:
            estado = "omitido"
        detalle = None
        if i == 3 and t["plazo"] and e == "en_revision":
            detalle = f"hasta el {fecha(t['plazo'])}"
        if i == 5 and t["resolucion"]:
            detalle = t["resolucion"]
        if i == 5 and final and t["defensa_en"]:
            detalle = fecha(t["defensa_en"])
        pasos.append({"titulo": titulos[i], "estado": estado, "detalle": detalle})
    return etapas(pasos, etiqueta="Etapas del trámite")


def _contenido(t):
    """El perfil por secciones (solo lectura), o los PDF del documento final."""
    if t["tipo"] == "final":
        return Div(*[enlace_adjunto(d, f"{BASE}/{t['id']}/documento/{d['id']}") for d in grado.documentos(t)],
                   cls="flex flex-col gap-1") if grado.documentos(t) else P("Aún sin documento.", cls=TextPresets.muted_sm)
    return Div(*[Div(H3(grado.SECCIONES[k][0], cls="text-sm font-semibold"),
                     Pre(t["secciones"].get(k) or "—", cls="whitespace-pre-wrap text-sm font-sans bg-muted/40 rounded p-3"),
                     cls="space-y-1") for k in grado.seleccion(t)], cls="space-y-4")


def _historial(t, uid=None):
    """Informes del tribunal. Mientras una revisión está abierta, un miembro ve solo el suyo; el estudiante, nada."""
    bloques = []
    for ronda in range(1, t["ronda"] + 1):
        abierta = ronda == t["ronda"] and t["estado"] == "en_revision"
        infs = [i for i in grado.informes(t["id"], ronda) if not abierta or i["miembro_id"] == uid]
        if not infs:
            continue
        bloques.append(Div(H3(f"Revisión {ronda}", cls="text-sm font-semibold"),
                           *[Div(Div(Span(f"{i['nombres']} {i['apellidos']}", cls="font-medium"), " · ",
                                     insignia(grado.DICTAMENES[i["dictamen"]], {"aprobado": "verde", "observado": "ambar",
                                                                                "no_aprobado": "rojo"}[i["dictamen"]]),
                                     Span(f" · {fecha(i['enviado_en'])}", cls=TextPresets.muted_sm), cls="text-sm"),
                                 Ul(*[Li(f"{grado.ASPECTOS[a]}: {v}", cls="text-xs") for a, v in i["aspectos"].items()],
                                    cls="text-muted-foreground"),
                                 P(i["fundamento"], cls="text-sm") if i["fundamento"] else "",
                                 Ul(*[Li(Div(f"{o['numero']}. {o['texto']}", cls="text-sm"),
                                         Div(f"Respuesta: {o['respuesta']}", cls="text-sm text-primary") if o["respuesta"] else "",
                                         cls="py-1") for o in i["observaciones"]], cls="pl-2"),
                                 cls="rounded-md border border-border p-3 space-y-1") for i in infs],
                           cls="space-y-2"))
    if t["estado"] == "en_revision":
        recibidos, total = len(grado.informes(t["id"], t["ronda"])), len(grado.tribunal(t["id"]))
        bloques.append(P(f"Revisión {t['ronda']}: {recibidos} de {total} informes recibidos. Se muestran todos cuando "
                         "llega el último.", cls=TextPresets.muted_sm))
    return Div(*bloques, cls="space-y-4") if bloques else P("Aún no hay informes.", cls=TextPresets.muted_sm)


# --- Personal ---------------------------------------------------------------------------------------------------------

@rt(BASE)
def get(auth):
    gestor = grado.gestiona(auth)
    tutorados = grado.de_tutor(auth["id"])
    pendientes = grado.pendientes_de(auth["id"])
    miembro = grado.de_miembro(auth["id"])
    if not (gestor or tutorados or miembro):
        return no_autorizado()
    todos = grado.listar() if gestor else []
    toca = [le_toca(f"{t['que']}: {t['nombres']} {t['apellidos']}", f"{BASE}/{t['id']}",
                    f"{grado.TIPOS[t['tipo']]} «{t['titulo']}» · {'vence' if t['que'] == 'Su informe' else 'defensa'} el {fecha(t['cuando'])}")
            for t in pendientes]
    toca += [le_toca(f"Dar el visto bueno: {t['nombres']} {t['apellidos']}", f"{BASE}/{t['id']}", f"«{t['titulo']}»")
             for t in tutorados if t["estado"] == "con_tutor"]
    if gestor:
        toca += [le_toca(f"Designar el tribunal: {t['nombres']} {t['apellidos']}", f"{BASE}/{t['id']}", f"«{t['titulo']}»")
                 for t in todos if t["estado"] == "enviado"]
        toca += [le_toca(("Registrar la resolución" if t["tipo"] == "perfil" else "Programar la defensa") +
                         f": {t['nombres']} {t['apellidos']}", f"{BASE}/{t['id']}", f"«{t['titulo']}»")
                 for t in todos if t["estado"] == "favorable" and (t["tipo"] == "perfil" or not t["defensa_en"])]

    def tabla(filas):
        return Div(Table(Thead(Tr(Th("Estudiante"), Th("Trámite"), Th("Estado", cls="w-44"), Th("Plazo", cls="w-24"))),
                         Tbody(*[Tr(Td(A(f"{t['nombres']} {t['apellidos']}", href=f"{BASE}/{t['id']}", cls="font-medium hover:underline")),
                                    Td(grado.TIPOS[t["tipo"]], Div(t["titulo"], cls=TextPresets.muted_sm)),
                                    Td(insignia(grado.ESTADOS[t["estado"]], TONO[t["estado"]])),
                                    Td(fecha(t["plazo"]) if t["estado"] == "en_revision" else "")) for t in filas]),
                         cls="uk-table uk-table-divider uk-table-small text-sm min-w-[40rem]"), cls="overflow-x-auto")
    return pagina(
        "Proyectos de grado",
        H2("Proyectos de grado"),
        P("Perfiles y documentos finales: visto bueno del tutor, designación del tribunal, revisión en "
          f"{grado.DIAS_REVISION} días hábiles, resolución y defensa.", cls=(TextPresets.muted_sm, "mb-4")),
        tarjeta("Le toca a usted", Div(*toca, cls="space-y-2"), cls="mb-6") if toca else "",
        Div(tarjeta("Como tutor", tabla(tutorados)) if tutorados else "",
            tarjeta("Como tribunal", tabla(miembro)) if miembro else "", cls="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6"),
        tarjeta("Todos los trámites", tabla(todos) if todos else P("Aún no hay trámites enviados.", cls=TextPresets.muted_sm))
        if gestor else "",
        usuario=auth)


def _visible(auth, tid):
    t = grado.obtener(tid)
    return t if t and t["estado"] != "borrador" and grado.puede_ver(auth, t) else None


def _acciones(auth, t):
    url = f"{BASE}/{t['id']}"
    bloques = []
    if t["estado"] == "con_tutor" and t["tutor_id"] == auth["id"]:
        bloques.append(tarjeta("Su visto bueno como tutor",
                               formulario(f"{url}/tutor", area("Comentario (obligatorio si lo devuelve)", "comentario", "", 3),
                                          Div(_decision("Devolver al estudiante", "devolver"), _decision("Dar el visto bueno", "aprobar", True),
                                              cls="flex flex-wrap justify-end gap-2"))))
    if t["estado"] == "enviado" and grado.gestiona(auth):
        opciones = [u for u in grado.tutores() if u["id"] != t["tutor_id"]]
        bloques.append(tarjeta("Designar el tribunal",
                               formulario(f"{url}/tribunal",
                                          Div(*[fh.Label(fh.Input(type="checkbox", name="miembros", value=str(u["id"]), cls="uk-checkbox"),
                                                         f" {u['apellidos']}, {u['nombres']}", cls="flex items-center gap-2 text-sm")
                                                for u in opciones], cls="max-h-64 overflow-y-auto space-y-1 rounded border border-border p-2"),
                                          P(f"Al menos {grado.MIN_TRIBUNAL} docentes; el tutor no lo integra. Todos deben dictaminar en "
                                            f"{grado.DIAS_REVISION} días hábiles.", cls=TextPresets.muted_sm),
                                          Div(enviar("Designar y avisar"), cls="flex justify-end"))))
    if t["estado"] == "en_revision" and grado.es_miembro(t["id"], auth["id"]) and not grado.informe_de(t["id"], t["ronda"], auth["id"]):
        bloques.append(tarjeta(
            f"Su informe · vence el {fecha(t['plazo'])}",
            formulario(f"{url}/informe",
                       fh.Fieldset(fh.Legend("Aspectos que evalúa el tribunal (art. 35)", cls="text-sm font-medium mb-2"),
                                   *[Div(Span(n, cls="text-sm"),
                                         Div(*[fh.Label(fh.Input(type="radio", name=f"a_{k}", value=v, required=True, cls="uk-radio"),
                                                        f" {txt}", cls="flex items-center gap-1 text-sm")
                                               for v, txt in (("suficiente", "Suficiente"), ("observado", "Observado"))],
                                             cls="flex gap-4"),
                                         cls="flex flex-wrap items-center justify-between gap-2 py-1")
                                     for k, n in grado.ASPECTOS.items()], cls="space-y-1"),
                       area("Observaciones", "observaciones", "", 5,
                            "Una por párrafo (separe con una línea en blanco). El estudiante responde cada una."),
                       fh.Fieldset(fh.Legend("Su dictamen", cls="text-sm font-medium mb-2"),
                                   *[fh.Label(fh.Input(type="radio", name="dictamen", value=k, required=True, cls="uk-radio"),
                                              f" {txt}", cls="flex items-center gap-2 text-sm") for k, txt in grado.DICTAMENES.items()],
                                   cls="space-y-1"),
                       area("Fundamento (obligatorio si no aprueba)", "fundamento", "", 3),
                       P("El estudiante recibe los informes de todo el tribunal juntos, cuando el último miembro envía el suyo.",
                         cls=TextPresets.muted_sm),
                       Div(enviar("Firmar y enviar informe"), cls="flex justify-end"))))
    if t["estado"] == "favorable" and t["tipo"] == "perfil" and grado.gestiona(auth):
        bloques.append(tarjeta("Aprobar el perfil",
                               formulario(f"{url}/resolucion", LabelInput("Número de la resolución", id="numero", required=True,
                                                                          maxlength="120"),
                                          Div(enviar("Registrar y aprobar"), cls="flex justify-end")),
                               P("El PDF de la resolución es opcional:", cls=(TextPresets.muted_sm, "mt-3")),
                               subir(f"{url}/archivo", "Adjuntar PDF")))
    if t["estado"] == "favorable" and t["tipo"] == "final" and grado.gestiona(auth):
        bloques.append(tarjeta("Programar la defensa",
                               formulario(f"{url}/defensa",
                                          Div(LabelInput("Reunión del tribunal con el postulante y el tutor (art. 34)", id="reunion_en",
                                                         type="date", value=t["reunion_en"] or "", required=True),
                                              LabelInput("Defensa", id="defensa_en", type="date", value=t["defensa_en"] or "", required=True),
                                              cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
                                          Div(enviar("Guardar"), cls="flex justify-end"))))
    if t["estado"] == "favorable" and t["tipo"] == "final" and t["defensa_en"] and grado.es_miembro(t["id"], auth["id"]):
        mia = next((m for m in grado.tribunal(t["id"]) if m["usuario_id"] == auth["id"]), {})
        bloques.append(tarjeta("Su nota de la defensa",
                               formulario(f"{url}/nota", LabelInput("Nota (1 a 100)", id="nota", type="number", min="1", max="100",
                                                                    value=str(mia.get("nota_defensa") or ""), required=True),
                                          P("51–79 bueno, 80–89 sobresaliente, 90–100 excelente. La nota final es el promedio.",
                                            cls=TextPresets.muted_sm),
                                          Div(enviar("Guardar nota"), cls="flex justify-end"))))
    return bloques


def _decision(texto, valor, primario=False):
    return enviar(texto, cls=ButtonT.primary if primario else ButtonT.default, name="decision", value=valor)


@rt(f"{BASE}/{{tid}}")
def get(auth, tid: int):
    t = _visible(auth, tid)
    if not t:
        return no_autorizado()
    trib = grado.tribunal(tid)
    url = f"{BASE}/{tid}"
    nota = grado.nota_final(tid)
    return pagina(
        f"{grado.TIPOS[t['tipo']]} de {t['nombres']} {t['apellidos']}",
        A("← Proyectos de grado", href=BASE, cls="text-sm text-primary"),
        Div(Span(f"{grado.TIPOS[t['tipo']]} · {grado.MODALIDADES[t['modalidad']]}", cls="text-xs font-semibold uppercase text-primary"),
            H2(t["titulo"]),
            P(f"{t['nombres']} {t['apellidos']}" + (f" · RU {t['ru']}" if t["ru"] else "") +
              (f" · Tutor: {t['tutor_nombres']} {t['tutor_apellidos']}" if t["tutor_id"] else ""), cls=TextPresets.muted_sm),
            insignia(grado.ESTADOS[t["estado"]], TONO[t["estado"]]), cls="space-y-1 my-4"),
        Div(_pasos(t), cls="mb-6 overflow-x-auto"),
        Div(Div(*_acciones(auth, t),
                tarjeta("Contenido", _contenido(t),
                        accion=A(UkIcon("file-code", height=14, width=14), "LaTeX (ZIP)", href=f"{url}/latex.zip",
                                 cls="uk-btn uk-btn-default uk-btn-sm gap-1") if t["tipo"] == "perfil" else ""),
                cls="space-y-6 lg:col-span-2"),
            Div(tarjeta("Tribunal", Ul(*[Li(f"{m['nombres']} {m['apellidos']}",
                                            Span(f" · nota {m['nota_defensa']}" if m["nota_defensa"] else "", cls=TextPresets.muted_sm),
                                            cls="text-sm") for m in trib], cls="space-y-1")
                        if trib else P("Sin designar.", cls=TextPresets.muted_sm),
                        P(f"Nota final: {nota} ({grado.calificacion_literal(nota)})", cls="text-sm font-semibold mt-2")
                        if t["estado"] in ("defendido", "reprobado") and nota else "",
                        A(UkIcon("printer", height=14, width=14), "Acta de defensa", href=f"{url}/acta",
                          cls="uk-btn uk-btn-default uk-btn-sm gap-1 mt-2") if t["estado"] in ("defendido", "reprobado") else ""),
                tarjeta("Informes del tribunal", _historial(t, auth["id"])),
                tarjeta("Resolución", P(t["resolucion"], cls="text-sm"),
                        *[enlace_adjunto(d, f"{url}/documento/{d['id']}") for d in grado.documentos(t)])
                if t["resolucion"] else "",
                cls="space-y-6"),
            cls="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start"),
        usuario=auth)


@rt(f"{BASE}/{{tid}}/tutor")
def post(auth, sess, tid: int, decision: str = "", comentario: str = ""):
    t = _visible(auth, tid)
    if not t:
        return no_autorizado()
    errores = grado.responder_tutor(t, auth["id"], decision == "aprobar", comentario)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "visto_bueno_tutor" if decision == "aprobar" else "devolver_tramite_grado", "tramite_grado", tid)
        add_toast(sess, "Listo: se avisó al estudiante.", "success")
    return Redirect(f"{BASE}/{tid}")


@rt(f"{BASE}/{{tid}}/tribunal")
async def post(auth, sess, req, tid: int):
    t = _visible(auth, tid)
    if not t or not grado.gestiona(auth):
        return no_autorizado()
    f = await req.form()
    errores = grado.designar_tribunal(t, [int(x) for x in f.getlist("miembros") if str(x).isdigit()], auth["id"])
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "designar_tribunal_grado", "tramite_grado", tid)
        add_toast(sess, "Tribunal designado: se avisó a sus miembros y al estudiante.", "success")
    return Redirect(f"{BASE}/{tid}")


@rt(f"{BASE}/{{tid}}/informe")
async def post(auth, sess, req, tid: int):
    t = _visible(auth, tid)
    if not t:
        return no_autorizado()
    f = await req.form()
    aspectos = {k: f.get(f"a_{k}", "") for k in grado.ASPECTOS}
    obs = [x for x in str(f.get("observaciones", "")).replace("\r\n", "\n").split("\n\n")]
    errores = grado.enviar_informe(t, auth["id"], aspectos, f.get("dictamen", ""), f.get("fundamento", ""), obs)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "informe_tribunal_grado", "tramite_grado", tid, f.get("dictamen"))
        add_toast(sess, "Informe enviado.", "success")
    return Redirect(f"{BASE}/{tid}")


@rt(f"{BASE}/{{tid}}/resolucion")
def post(auth, sess, tid: int, numero: str = ""):
    t = _visible(auth, tid)
    if not t or not grado.gestiona(auth):
        return no_autorizado()
    errores = grado.registrar_resolucion(t, numero)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "aprobar_perfil_grado", "tramite_grado", tid, numero)
        add_toast(sess, "Perfil aprobado.", "success")
    return Redirect(f"{BASE}/{tid}")


@rt(f"{BASE}/{{tid}}/archivo")
async def post(auth, sess, tid: int, archivo: UploadFile = None):
    t = _visible(auth, tid)
    if not t or not grado.gestiona(auth):
        return no_autorizado()
    contenido, error = await leer_archivo(archivo)
    if not error:
        try:
            adjuntos.guardar("tramite_grado", tid, archivo.filename, contenido, auth["id"])
        except ValueError as e:
            error = str(e)
    add_toast(sess, error or "Archivo adjunto.", "error" if error else "success")
    return Redirect(f"{BASE}/{tid}")


@rt(f"{BASE}/{{tid}}/defensa")
def post(auth, sess, tid: int, reunion_en: str = "", defensa_en: str = ""):
    t = _visible(auth, tid)
    if not t or not grado.gestiona(auth):
        return no_autorizado()
    for e in grado.registrar_defensa(t, reunion_en, defensa_en):
        add_toast(sess, e, "error")
    return Redirect(f"{BASE}/{tid}")


@rt(f"{BASE}/{{tid}}/nota")
def post(auth, sess, tid: int, nota: str = ""):
    t = _visible(auth, tid)
    if not t:
        return no_autorizado()
    errores = grado.calificar_defensa(t, auth["id"], nota)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "nota_defensa_grado", "tramite_grado", tid)
        add_toast(sess, "Nota guardada.", "success")
    return Redirect(f"{BASE}/{tid}")


@rt(f"{BASE}/{{tid}}/latex.zip")
def get(auth, tid: int):
    t = _visible(auth, tid)
    return descarga_bytes(latex.zip_perfil(t), f"perfil-{tid}.zip", "application/zip") if t else no_autorizado()


@rt(f"{BASE}/{{tid}}/documento/{{adj_id}}")
def get(auth, tid: int, adj_id: int):
    t = _visible(auth, tid)
    adj = adjuntos.obtener(adj_id)
    if not t or not adj or adj["entidad"] != "tramite_grado" or adj["entidad_id"] != tid:
        return no_encontrado()
    return descargar(adj)


@rt(f"{BASE}/{{tid}}/acta")
def get(auth, tid: int):
    t = _visible(auth, tid)
    if not t or t["estado"] not in ("defendido", "reprobado"):
        return no_encontrado()
    nota = grado.nota_final(tid)
    return pagina(
        "Acta de defensa",
        Div(fh.Button(UkIcon("printer", height=14, width=14), "Imprimir", type="button", data_accion="imprimir",
                      cls="uk-btn uk-btn-default uk-btn-sm gap-1 no-imprimir"), cls="flex justify-end"),
        Div(P(config.UNIVERSIDAD, cls="font-semibold"), P(config.FACULTAD), P(config.NOMBRE_CARRERA), cls="text-center text-sm"),
        H2("Acta de defensa", cls="text-center mt-4"),
        P(f"{grado.MODALIDADES[t['modalidad']]}: «{t['titulo']}»", cls="text-center text-sm"),
        P(f"Postulante: {t['nombres']} {t['apellidos']}" + (f" · RU {t['ru']}" if t["ru"] else "") +
          f" · Tutor: {t['tutor_nombres']} {t['tutor_apellidos']}", cls="text-center text-sm"),
        P(f"Fecha de la defensa: {fecha(t['defensa_en'])}", cls="text-center text-sm mb-4"),
        Table(Thead(Tr(Th("Miembro del tribunal"), Th("Nota", cls="text-right"), Th("Firma"))),
              Tbody(*[Tr(Td(f"{m['nombres']} {m['apellidos']}"), Td(str(m["nota_defensa"]), cls="text-right"), Td(""))
                      for m in grado.tribunal(tid)]),
              cls="uk-table uk-table-divider text-sm"),
        P(f"Nota final: {nota} — {grado.calificacion_literal(nota)}", cls="text-center font-semibold mt-4"),
        P("Escala del Reglamento General de Tipos y Modalidades de Graduación: 51–79 bueno, 80–89 sobresaliente, 90–100 excelente.",
          cls=(TextPresets.muted_sm, "mt-6 text-center")),
        usuario=auth)


# --- Estudiante -----------------------------------------------------------------------------------------------------

@rt(EST)
def get(auth):
    externo, error = _estudiante(auth)
    if error:
        return error
    tramites = grado.de_estudiante(externo)
    perfil_abierto = any(t["tipo"] == "perfil" and t["estado"] in grado.ABIERTOS + ("aprobado",) for t in tramites)
    aprobado = next((t for t in tramites if t["tipo"] == "perfil" and t["estado"] == "aprobado"), None)
    con_final = aprobado and any(t["tipo"] == "final" and t["perfil_id"] == aprobado["id"] and t["estado"] != "reprobado"
                                 for t in tramites)
    return pagina(
        "Proyecto de grado",
        H2("Proyecto de grado"),
        P("Prepare aquí su perfil: el sistema le genera la nota de presentación y el perfil en LaTeX con la plantilla de la "
          "Carrera. Su tutor da el visto bueno, la Dirección designa el tribunal y usted responde sus observaciones aquí "
          "mismo.", cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Div(A(UkIcon("plus", height=14, width=14), "Empezar mi perfil", href=f"{EST}/nuevo", cls="uk-btn uk-btn-primary gap-1")
            if not perfil_abierto else "",
            boton_post("Presentar el documento final", f"{EST}/{aprobado['id']}/final", "file-up", cls=ButtonT.primary)
            if aprobado and not con_final else "", cls="flex flex-wrap gap-2 mb-6"),
        Div(*[tarjeta(f"{grado.TIPOS[t['tipo']]}: {t['titulo']}",
                      Div(insignia(grado.ESTADOS[t["estado"]], TONO[t["estado"]]),
                          A("Abrir", href=f"{EST}/{t['id']}", cls="uk-btn uk-btn-default uk-btn-sm"),
                          cls="flex items-center justify-between gap-2")) for t in tramites], cls="space-y-4")
        if tramites else P("Aún no tiene trámites de grado.", cls=TextPresets.muted_sm),
        usuario=auth)


def _form_nuevo():
    return formulario(
        EST,
        LabelInput("Título del trabajo", id="titulo", required=True, maxlength="300",
                   placeholder="Puede usar LaTeX: Existencia global para $iu_t + \\Delta u = 0$"),
        Div(seleccion("Modalidad", "modalidad", list(grado.MODALIDADES.items()), "proyecto_grado"),
            seleccion("Tutor(a)", "tutor_id", [(u["id"], f"{u['apellidos']}, {u['nombres']}") for u in grado.tutores()], vacio="— Elija —"),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
        Div(P("Secciones del perfil", cls="text-sm font-medium"),
            P("Las obligatorias de la Carrera ya están; agregue las que le sirvan (puede cambiarlas después).", cls=TextPresets.muted_sm),
            Div(*[fh.Label(fh.Input(type="checkbox", name="opcionales", value=k, checked=o or None, disabled=o or None, cls="uk-checkbox"),
                           f" {n}" + (" (obligatoria)" if o else ""), cls="flex items-center gap-2 text-sm")
                  for k, (n, o, _) in grado.SECCIONES.items()], cls="grid grid-cols-1 sm:grid-cols-2 gap-1"),
            cls="space-y-2 rounded-md border border-border p-4"),
        Div(A("Cancelar", href=EST, cls="uk-btn uk-btn-ghost"), enviar("Crear mi perfil"), cls="flex justify-end gap-2"))


@rt(f"{EST}/nuevo")
def get(auth):
    externo, error = _estudiante(auth)
    if error:
        return error
    return pagina("Nuevo perfil", A("← Proyecto de grado", href=EST, cls="text-sm text-primary"), H2("Nuevo perfil"),
                  Div(_form_nuevo(), cls="max-w-3xl mt-4"), usuario=auth)


@rt(EST)
async def post(auth, sess, req):
    externo, error = _estudiante(auth)
    if error:
        return error
    f = await req.form()
    tid, errores = grado.crear_perfil(externo, {k: f.get(k, "") for k in ("titulo", "modalidad", "tutor_id")},
                                      list(f.getlist("opcionales")))
    for e in errores:
        add_toast(sess, e, "error")
    if tid:
        auditar(auth["id"], "crear_perfil_grado", "tramite_grado", tid)
    return Redirect(f"{EST}/{tid}" if tid else f"{EST}/nuevo")


def _propio(auth, tid):
    externo, error = _estudiante(auth)
    if error:
        return None, error
    t = grado.obtener(tid)
    if not t or t["externo_id"] != externo:
        return None, no_encontrado()
    return t, None


def _observaciones(t):
    url = f"{EST}/{t['id']}"
    obs = [(i, o) for i in grado.informes(t["id"], t["ronda"]) for o in i["observaciones"]]
    if t["estado"] != "observado" or not obs:
        return ""
    return tarjeta(
        f"Observaciones del tribunal · {sum(1 for _, o in obs if (o['respuesta'] or '').strip())} de {len(obs)} respondidas",
        P("Responda cada una explicando qué cambió; corrija el texto y reenvíe.", cls=(TextPresets.muted_sm, "mb-2")),
        Ul(*[Li(Div(Span(f"{o['numero']} · {i['nombres']} {i['apellidos']}", cls="text-xs font-semibold"),
                    P(o["texto"], cls="text-sm"), cls="space-y-1"),
                formulario(f"{url}/observaciones/{o['id']}",
                           area("Su respuesta", f"r{o['id']}", o["respuesta"], 2, name="respuesta"),
                           Div(enviar("Guardar respuesta", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"), cls="space-y-1"),
                cls="py-3 space-y-2 " + ("" if (o["respuesta"] or "").strip() else "border-l-4 border-amber-500 pl-3"))
             for i, o in obs], cls="divide-y divide-border"))


@rt(f"{EST}/{{tid}}")
def get(auth, tid: int):
    t, error = _propio(auth, tid)
    if error:
        return error
    url = f"{EST}/{tid}"
    editable = grado.editable(t)
    faltan = grado.faltantes(t) if editable else []
    elegidas = grado.seleccion(t)
    aviso = {"borrador": "Complete su trabajo y pida el visto bueno de su tutor.",
             "con_tutor": "Su tutor lo está revisando.", "enviado": "La Dirección de Carrera designará el tribunal.",
             "en_revision": f"El tribunal lo revisa hasta el {fecha(t['plazo'])}.",
             "observado": "El tribunal envió observaciones: le toca a usted.",
             "favorable": "Dictamen favorable." + (" Falta la resolución de aprobación." if t["tipo"] == "perfil" else
                                                  (f" Defensa: {fecha(t['defensa_en'])}." if t["defensa_en"] else " La Dirección programará la defensa.")),
             "aprobado": f"Aprobado · {t['resolucion'] or ''}", "rechazado": "El tribunal no lo aprobó. Converse con su tutor.",
             "defendido": f"Defendido · nota {grado.nota_final(tid)}", "reprobado": f"Nota {grado.nota_final(tid)}."}[t["estado"]]
    if t["tipo"] == "perfil":
        secciones = [Div(Div(fh.Label(grado.SECCIONES[k][0], fr=f"s_{k}", cls="text-sm font-medium"),
                             P(grado.SECCIONES[k][2], cls=TextPresets.muted_sm), cls="space-y-0.5"),
                         fh.Textarea(t["secciones"].get(k) or "", id=f"s_{k}", name=f"s_{k}", cls="uk-textarea font-mono text-sm",
                                     rows="8" if k in ("bibliografia", "planteamiento", "metodologia") else "4",
                                     disabled=not editable or None), cls="space-y-1") for k in elegidas]
        opcionales = Div(P("Secciones opcionales", cls="text-sm font-medium"),
                         Div(*[fh.Label(fh.Input(type="checkbox", name="opcionales", value=k, checked=k in elegidas or None, cls="uk-checkbox"),
                                        f" {n}", cls="flex items-center gap-2 text-sm")
                               for k, (n, o, _) in grado.SECCIONES.items() if not o], cls="grid grid-cols-1 sm:grid-cols-2 gap-1"),
                         P("Al quitar una sección se borra lo escrito en ella.", cls=TextPresets.muted_sm),
                         cls="space-y-2 rounded-md border border-border p-3") if editable else ""
    else:
        secciones, opcionales = [], ""
    datos = Div(LabelInput("Título", id="titulo", value=t["titulo"], required=True, maxlength="300", disabled=not editable or None),
                Div(seleccion("Modalidad", "modalidad", list(grado.MODALIDADES.items()), t["modalidad"], disabled=not editable or None),
                    seleccion("Tutor(a)", "tutor_id", [(u["id"], f"{u['apellidos']}, {u['nombres']}") for u in grado.tutores()],
                              t["tutor_id"], "— Elija —", disabled=not editable or None),
                    cls="grid grid-cols-1 sm:grid-cols-2 gap-4"), cls="space-y-4")
    docs = grado.documentos(t)
    return pagina(
        grado.TIPOS[t["tipo"]],
        A("← Proyecto de grado", href=EST, cls="text-sm text-primary"),
        Div(H2(f"{grado.TIPOS[t['tipo']]} de {grado.MODALIDADES[t['modalidad']].lower()}"),
            P(f"{t['nombres']} {t['apellidos']}" + (f" · RU {t['ru']}" if t["ru"] else "") +
              (f" · Tutor: {t['tutor_nombres']} {t['tutor_apellidos']}" if t["tutor_id"] else ""), cls=TextPresets.muted_sm),
            cls="space-y-1 my-4"),
        Div(_pasos(t), cls="mb-4 overflow-x-auto"),
        Div(aviso, role="status", cls="rounded-md border p-3 text-sm mb-6 " + (
            "border-amber-400 bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-200" if t["estado"] == "observado"
            else "border-border bg-muted/40")),
        P(f"Comentario de su tutor: {t['comentario_tutor']}", cls="text-sm mb-4 text-amber-800 dark:text-amber-300")
        if t["comentario_tutor"] and t["estado"] == "borrador" else "",
        Div(Div(_observaciones(t),
                tarjeta("Su trabajo",
                        formulario(f"{url}", datos, opcionales, *secciones,
                                   Div(Span("Escriba en LaTeX: fórmulas entre $…$." if t["tipo"] == "perfil" else "", cls=TextPresets.muted_sm),
                                       enviar("Guardar"), cls="flex flex-wrap items-center justify-between gap-2") if editable else "")),
                tarjeta("Documento final (PDF)",
                        Div(*[Div(enlace_adjunto(d, f"{EST}/documento/{d['id']}"),
                                  boton_post("", f"{url}/documento/{d['id']}/quitar", "x", cls=(ButtonT.ghost, ButtonT.xs),
                                             aria_label=f"Quitar {d['nombre']}") if editable else "", cls="flex items-center gap-1")
                              for d in docs], cls="space-y-1 mb-2"),
                        subir(f"{url}/archivo", "Subir PDF") if editable else "") if t["tipo"] == "final" else "",
                cls="space-y-6 lg:col-span-2"),
            Div(tarjeta("Enviar",
                        falta(faltan, "Tiene todo lo que se pide.") if editable else P(grado.ESTADOS[t["estado"]], cls="text-sm"),
                        Div(boton_post("Pedir el visto bueno de mi tutor", f"{url}/visto-bueno", "send", cls=ButtonT.primary,
                                       disabled=bool(faltan) or None) if t["estado"] == "borrador" else "",
                            boton_post("Reenviar al tribunal", f"{url}/reenviar", "send", cls=ButtonT.primary,
                                       disabled=bool(faltan) or None) if t["estado"] == "observado" else "",
                            cls="flex flex-wrap gap-2 mt-3")),
                tarjeta("Documentos que genera el sistema",
                        A(Span("Nota de presentación (para imprimir)"), UkIcon("printer", height=14, width=14), href=f"{url}/nota",
                          cls="flex items-center justify-between rounded border border-border px-3 py-2 text-sm hover:bg-muted"),
                        A(Span("Perfil y nota en LaTeX (ZIP)"), UkIcon("file-code", height=14, width=14), href=f"{url}/latex.zip",
                          cls="flex items-center justify-between rounded border border-border px-3 py-2 text-sm hover:bg-muted mt-2")
                        if t["tipo"] == "perfil" else "",
                        P("Plantilla de la Carrera (clase perfil-cmat). Compile con pdfLaTeX o súbala a Overleaf; lo que cuenta "
                          "es lo que envía aquí.", cls=(TextPresets.muted_sm, "mt-2"))),
                tarjeta("Informes del tribunal", _historial(t, None)) if t["ronda"] else "",
                cls="space-y-6"),
            cls="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start"),
        usuario=auth)


@rt(f"{EST}/{{tid}}")
async def post(auth, sess, req, tid: int):
    t, error = _propio(auth, tid)
    if error:
        return error
    f = await req.form()
    textos = {k: f.get(f"s_{k}") for k in grado.SECCIONES if f.get(f"s_{k}") is not None}
    opcionales = list(f.getlist("opcionales")) if t["tipo"] == "perfil" else None
    errores = grado.guardar(t, {k: f.get(k, "") for k in ("titulo", "modalidad", "tutor_id")}, textos, opcionales)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        add_toast(sess, "Guardado.", "success")
    return Redirect(f"{EST}/{tid}")


@rt(f"{EST}/{{tid}}/visto-bueno")
def post(auth, sess, tid: int):
    t, error = _propio(auth, tid)
    if error:
        return error
    errores = grado.pedir_visto_bueno(t)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "pedir_visto_bueno", "tramite_grado", tid)
        add_toast(sess, "Se avisó a su tutor.", "success")
    return Redirect(f"{EST}/{tid}")


@rt(f"{EST}/{{tid}}/observaciones/{{oid}}")
def post(auth, sess, tid: int, oid: int, respuesta: str = ""):
    t, error = _propio(auth, tid)
    if error:
        return error
    for e in grado.responder_observacion(t, oid, respuesta):
        add_toast(sess, e, "error")
    return Redirect(f"{EST}/{tid}")


@rt(f"{EST}/{{tid}}/reenviar")
def post(auth, sess, tid: int):
    t, error = _propio(auth, tid)
    if error:
        return error
    errores = grado.reenviar(t)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "reenviar_tramite_grado", "tramite_grado", tid)
        add_toast(sess, "Reenviado: el tribunal tiene un nuevo plazo.", "success")
    return Redirect(f"{EST}/{tid}")


@rt(f"{EST}/{{tid}}/final")
def post(auth, sess, tid: int):
    t, error = _propio(auth, tid)
    if error:
        return error
    nuevo, errores = grado.iniciar_final(t)
    for e in errores:
        add_toast(sess, e, "error")
    return Redirect(f"{EST}/{nuevo}" if nuevo else EST)


@rt(f"{EST}/{{tid}}/archivo")
async def post(auth, sess, tid: int, archivo: UploadFile = None):
    t, error = _propio(auth, tid)
    if error:
        return error
    if t["tipo"] != "final" or not grado.editable(t):
        return no_autorizado()
    contenido, err = await leer_archivo(archivo)
    if not err and not contenido.startswith(b"%PDF-"):
        err = "El documento final debe ser un PDF."
    if not err:
        try:
            adjuntos.guardar("tramite_grado", tid, archivo.filename, contenido, auth["id"])
        except ValueError as e:
            err = str(e)
    add_toast(sess, err or "Documento subido.", "error" if err else "success")
    return Redirect(f"{EST}/{tid}")


def _documento_propio(auth, adj_id):
    externo, error = _estudiante(auth)
    adj = adjuntos.obtener(adj_id)
    if error or not adj or adj["entidad"] != "tramite_grado":
        return None
    t = grado.obtener(adj["entidad_id"])
    return adj if t and t["externo_id"] == externo else None


@rt(f"{EST}/documento/{{adj_id}}")
def get(auth, adj_id: int):
    adj = _documento_propio(auth, adj_id)
    return descargar(adj) if adj else no_encontrado()


@rt(f"{EST}/{{tid}}/documento/{{adj_id}}/quitar")
def post(auth, tid: int, adj_id: int):
    t, error = _propio(auth, tid)
    if error:
        return error
    adj = _documento_propio(auth, adj_id)
    if not adj or adj["entidad_id"] != tid or not grado.editable(t):
        return no_encontrado()
    adjuntos.eliminar(adj)
    return Redirect(f"{EST}/{tid}")


@rt(f"{EST}/{{tid}}/latex.zip")
def get(auth, tid: int):
    t, error = _propio(auth, tid)
    if error:
        return error
    return descarga_bytes(latex.zip_perfil(t), f"perfil-{tid}.zip", "application/zip")


@rt(f"{EST}/{{tid}}/nota")
def get(auth, tid: int):
    t, error = _propio(auth, tid)
    if error:
        return error
    que = "el perfil" if t["tipo"] == "perfil" else "el documento final"
    return pagina(
        "Nota de presentación",
        Div(A("← Volver", href=f"{EST}/{tid}", cls="text-sm text-primary no-imprimir"),
            fh.Button(UkIcon("printer", height=14, width=14), "Imprimir o guardar en PDF", type="button", data_accion="imprimir",
                      cls="uk-btn uk-btn-default uk-btn-sm gap-1 no-imprimir"), cls="flex justify-between mb-8"),
        Div(P(latex._fecha(), cls="text-right"),
            P("Señor(a)", fh.Br(), f"Director(a) de la {config.NOMBRE_CARRERA}", fh.Br(), config.FACULTAD, fh.Br(), config.UNIVERSIDAD,
              fh.Br(), Span("Presente", cls="underline")),
            P(Span(f"Ref.: Presentación de {que} de {grado.MODALIDADES[t['modalidad']].lower()}", cls="font-semibold"), cls="text-right"),
            P("De mi mayor consideración:"),
            P(f"Mediante la presente, me permito presentar a su autoridad {que} de {grado.MODALIDADES[t['modalidad']].lower()} "
              f"titulado «{t['titulo']}», bajo la tutoría de {t['tutor_nombres'] or ''} {t['tutor_apellidos'] or ''}, para su "
              "consideración y la designación del tribunal correspondiente."),
            P("Atentamente,"),
            Div(Div(cls="h-16"), P(f"{t['nombres']} {t['apellidos']}"), P(f"R. U. {t['ru'] or ''}"), cls="mt-8"),
            cls="max-w-2xl mx-auto space-y-4 text-sm leading-relaxed"),
        usuario=auth)


