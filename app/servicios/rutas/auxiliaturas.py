"""Pantallas de auxiliaturas (PLAN §58, servicio 3): la Dirección o la Coordinación arma y publica la convocatoria, el
estudiante postula desde su teléfono y el tribunal califica cada fase. Los miembros estudiantes del tribunal califican en
/estudiante/tribunal (su cuenta solo llega a /estudiante)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, P, Redirect, Span, Table, Tbody, Td, Th, Thead, Tr, Ul, UploadFile
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, ButtonT, LabelInput, TextPresets, UkIcon

from app.comun.componentes.etapas import etapas
from app.comun.componentes.layout import pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar, get_db
from app.investigacion import adjuntos
from app.servicios import auxiliaturas as aux
from app.servicios.rutas.comun import (area, boton_post, descargar, enlace_adjunto, enviar, falta, fecha, formulario,
                                       leer_archivo, no_autorizado, no_encontrado, seleccion, subir, tarjeta)

rt = APIRouter()
BASE = "/servicios/auxiliaturas"
EST = "/estudiante/auxiliaturas"
TRIB = "/estudiante/tribunal"
TONO_POST = {"borrador": "gris", "enviada": "azul", "no_habilitada": "rojo", "eliminada": "rojo", "titular": "verde",
             "no_seleccionada": "gris", "empate": "ambar"}
TONO_CONV = {"borrador": "gris", "publicada": "verde", "concluida": "azul"}


def _num(v):
    return "—" if v is None else f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _estudiante(auth):
    from app.estudiantil.rutas.estudiante import _requiere
    return _requiere(auth)


# --- Calificación (la comparten el personal y los estudiantes del tribunal) --------------------------------------------

def _docs_postulante(p, base_doc):
    """Requisitos del postulante, uno por línea: si se cumple, el requisito y sus documentos o la declaración."""
    filas = []
    for r in aux.requisitos_de(aux.postulacion(p["id"])):
        docs = [enlace_adjunto(d, f"{base_doc}/{d['id']}") for d in r["documentos"]]
        filas.append(Li(UkIcon("circle-check" if r["cumplido"] else "circle", height=12, width=12,
                               cls="mt-0.5 shrink-0 " + ("text-primary" if r["cumplido"] else "text-muted-foreground")),
                        Div(Span(r["texto"], cls="text-muted-foreground"),
                            Div(*docs, cls="flex flex-wrap gap-x-3") if docs else
                            ("" if r["acredita"] == "documento" else Span(f" · {r['detalle']}", cls="text-muted-foreground"))),
                        cls="flex items-start gap-1 text-xs"))
    return Ul(*filas, cls="space-y-1 mt-1") if filas else ""


def panel_calificar(auth, it, post_url, base_doc):
    """Formulario del miembro: su calificación de la fase en curso para cada postulante (una ficha por postulante, que
    se lee igual en el teléfono)."""
    fase = it["fase"]
    if fase not in aux.FASES:
        return ""
    activos = aux.activos(it["id"])
    if not activos:
        return tarjeta(f"Su calificación · {aux.NOMBRE_FASE[fase]}", P("No hay postulantes en esta fase.", cls=TextPresets.muted_sm))
    propias = {c["postulacion_id"]: c for c in get_db().q(
        "SELECT * FROM calificacion_auxiliatura WHERE fase = ? AND miembro_id = ?", [fase, auth["id"]])}
    fichas = []
    for p in activos:
        mia, nombre = propias.get(p["id"]), f"{p['nombres']} {p['apellidos']}"
        if fase == "habilitacion":
            campo = fh.Select(fh.Option("—", value=""), fh.Option("Cumple: habilitado", value="1", selected=mia and mia["valor"] == 1),
                              fh.Option("No cumple", value="0", selected=mia and mia["valor"] == 0),
                              id=f"v_{p['id']}", name=f"v_{p['id']}", cls="uk-select")
        else:
            campo = fh.Input(type="number", step="0.5", min="0", max=str(aux.MAXIMO[fase]), id=f"v_{p['id']}", name=f"v_{p['id']}",
                             value=_num(mia["valor"]).replace(",", ".") if mia else "", cls="uk-input", inputmode="decimal")
        fichas.append(Div(
            Div(Span(nombre, cls="font-medium"),
                Span(f"{len(aux.calificaciones(p['id'], fase))} de {aux.QUORUM} calificaciones", cls=TextPresets.muted_sm),
                cls="flex flex-wrap items-baseline justify-between gap-x-3"),
            _docs_postulante(p, base_doc) if fase in ("habilitacion", "meritos") else "",
            P((p["propuesta"] or "")[:400], cls=(TextPresets.muted_sm, "mt-1")) if fase == "meritos" and p["propuesta"] else "",
            Div(Div(fh.Label("Calificación", fr=f"v_{p['id']}", cls="text-xs font-medium"), campo, cls="space-y-1"),
                Div(fh.Label("Observación (opcional)", fr=f"o_{p['id']}", cls="text-xs font-medium"),
                    fh.Input(id=f"o_{p['id']}", name=f"o_{p['id']}", value=(mia or {}).get("observacion") or "", cls="uk-input",
                             maxlength="1000"), cls="space-y-1"),
                cls="grid gap-2 sm:grid-cols-[12rem_1fr] mt-2"),
            role="group", aria_label=nombre, cls="py-3"))
    minimo = aux.minimo(it, fase)
    maximo = "" if fase == "habilitacion" else f" (0 a {aux.MAXIMO[fase]}" + (f", mínimo {_num(minimo)})" if minimo is not None else ")")
    return tarjeta(
        f"Su calificación · {aux.NOMBRE_FASE[fase]}{maximo}",
        P("Cada miembro califica por su cuenta; la nota de la fase es el promedio de al menos tres miembros. Puede corregir "
          "su calificación hasta que se cierre la fase.", cls=(TextPresets.muted_sm, "mb-1")),
        P(f"Tema sorteado para el examen oral: {it['tema_oral']}", cls="text-sm font-medium mb-2") if fase == "oral" and it["tema_oral"] else "",
        formulario(post_url, Div(*fichas, cls="divide-y divide-border"),
                   Div(enviar("Guardar mi calificación"), cls="flex justify-end")))


async def _guardar_calificacion(auth, sess, req, it):
    f = await req.form()
    errores, n = [], 0
    for p in aux.activos(it["id"]):
        v = str(f.get(f"v_{p['id']}", "")).strip()
        if v == "":
            continue
        e = aux.calificar(it, auth["id"], p["id"], v, f.get(f"o_{p['id']}", ""))
        errores += [f"{p['nombres']} {p['apellidos']}: {x}" for x in e]
        n += not e
    for e in errores:
        add_toast(sess, e, "error")
    if n:
        add_toast(sess, f"Se guardaron {n} calificaciones.", "success")


def tabla_resultados(it, base_doc=None, detalle=True):
    filas = aux.tabla(it)
    publicadas = aux.fases_publicadas(it["id"])
    cab = [Th("Postulante")] + [Th(aux.NOMBRE_FASE[f], cls="text-right") for f in aux.FASES] + [Th("Total", cls="text-right"), Th("Estado")]
    cuerpo = []
    for r in filas:
        celdas = [Td(Div(f"{r['nombres']} {r['apellidos']}", cls="font-medium"),
                     Div(*[enlace_adjunto(d, f"{base_doc}/{d['id']}") for q in aux.requisitos_de(aux.postulacion(r["id"]))
                           for d in q["documentos"]], cls="flex flex-wrap gap-x-3") if base_doc and detalle else "")]
        for f in aux.FASES:
            v = r["notas"][f]
            texto = ("sí" if v > 0.5 else "no") if f == "habilitacion" and v is not None else _num(v)
            celdas.append(Td(texto, Div(f"{r['n'][f]} cal.", cls=TextPresets.muted_sm) if f not in publicadas and r["n"][f] else "",
                             cls="text-right"))
        celdas += [Td(_num(r["total"]), cls="text-right font-semibold"),
                   Td(insignia(aux.ESTADOS_POST[r["estado"]], TONO_POST[r["estado"]]))]
        cuerpo.append(Tr(*celdas))
    return Div(Table(Thead(Tr(*cab)), Tbody(*cuerpo), cls="uk-table uk-table-divider uk-table-small text-sm min-w-[44rem]"),
               cls="overflow-x-auto") if cuerpo else P("Aún no hay postulaciones enviadas.", cls=TextPresets.muted_sm)


def _pasos_item(it):
    orden = ("postulacion", *aux.FASES, "concluido")
    actual = orden.index(it["fase"])
    return etapas([{"titulo": aux.NOMBRE_FASE[f], "estado": "hecho" if i < actual else "actual" if i == actual else "pendiente",
                    "detalle": fecha(c["cerrada_en"]) if (c := aux.cierre_de(it["id"], f)) else None}
                   for i, f in enumerate(orden)], etiqueta="Fases del concurso")


# --- Personal: convocatorias ---------------------------------------------------------------------------------------------

@rt(BASE)
def get(auth):
    gestor = aux.puede_gestionar(auth)
    mios = aux.items_de_miembro(auth["id"])
    if not gestor and not mios:
        return no_autorizado()
    convs = aux.listar(auth) if gestor else []
    return pagina(
        "Auxiliaturas",
        Div(H2("Auxiliaturas"), A(UkIcon("plus", height=14, width=14), "Nueva convocatoria", href=f"{BASE}/nueva",
                                  cls="uk-btn uk-btn-primary uk-btn-sm gap-1") if gestor else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-2"),
        P("Convocatorias a auxiliaturas de los semestres regulares (I y II), de docencia y de investigación, según el Reglamento "
          "Específico de Auxiliares Académicos del Pregrado de la UMSA (Res. HCU 424/2023, modificada por la 364/2025): requisitos, "
          "tribunal por ítem, calificación por fases y resultado.", cls="text-sm max-w-3xl mb-4"),
        tarjeta("Tribunales que integra", Ul(*[Li(A(Div(i["titulo"], cls="font-medium"),
                                                     Div(i["convocatoria"], " · ", aux.NOMBRE_FASE[i["fase"]], cls=TextPresets.muted_sm),
                                                     href=f"{BASE}/item/{i['id']}", cls="hover:underline"),
                                                   insignia(f"{i['por_calificar']} por calificar", "ambar") if i["por_calificar"] else "",
                                                   cls="flex items-center justify-between gap-3 py-2") for i in mios],
                                             cls="divide-y divide-border"), cls="mb-6") if mios else "",
        Div(Table(Thead(Tr(Th("Convocatoria"), Th("Gestión", cls="w-24"), Th("Ítems", cls="w-16 text-right"),
                           Th("Postulaciones", cls="w-28 text-right"), Th("Estado", cls="w-28"))),
                  Tbody(*[Tr(Td(A(c["titulo"], href=f"{BASE}/{c['id']}", cls="font-medium hover:underline"),
                                Div(aux.MODALIDADES[c["modalidad"]], " · ", "primera" if c["numero"] == 1 else "segunda",
                                    " convocatoria", cls=TextPresets.muted_sm)),
                             Td(f"{c['gestion_tipo']}-{c['anio']}"), Td(str(c["n_items"]), cls="text-right"),
                             Td(str(c["n_post"]), cls="text-right"),
                             Td(insignia(aux.ESTADOS_CONV[c["estado"]], TONO_CONV[c["estado"]]))) for c in convs]),
                  cls="uk-table uk-table-divider uk-table-small text-sm min-w-[40rem]"), cls="overflow-x-auto")
        if convs else (P("Aún no hay convocatorias.", cls=TextPresets.muted_sm) if gestor else ""),
        usuario=auth)


def _form_conv(auth, c=None):
    c = c or {}
    url = f"{BASE}/{c['id']}" if c.get("id") else BASE
    return formulario(
        url,
        Div(seleccion("Modalidad", "modalidad", [(m, aux.MODALIDADES[m]) for m in aux.modalidades_de(auth)], c.get("modalidad")),
            seleccion("Gestión", "gestion_id", [(g["id"], aux.texto_gestion(g)) for g in aux.gestiones()], c.get("gestion_id")),
            seleccion("Convocatoria", "numero", [(1, "Primera"), (2, "Segunda (si la primera quedó desierta)")], c.get("numero") or 1),
            cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
        LabelInput("Título", id="titulo", value=c.get("titulo") or "", required=True, maxlength="200",
                   placeholder="Auxiliaturas de docencia I-2027, primera convocatoria"),
        Div(LabelInput("Publicación", id="publicacion", type="date", value=c.get("publicacion") or ""),
            LabelInput("Cierre de la recepción", id="cierre", type="datetime-local", value=c.get("cierre") or ""),
            LabelInput("Examen escrito", id="examen", type="datetime-local", value=c.get("examen") or ""),
            LabelInput("Lugar de los exámenes", id="lugar", value=c.get("lugar") or "", maxlength="200"),
            cls="grid grid-cols-1 sm:grid-cols-4 gap-4"),
        Div(LabelInput("Lugar de recepción de los documentos", id="recepcion_lugar", value=c.get("recepcion_lugar") or "",
                       maxlength="200", placeholder="Secretaría de la Carrera"),
            LabelInput("Horario de atención", id="recepcion_horario", value=c.get("recepcion_horario") or "", maxlength="120",
                       placeholder="Lunes a viernes, de 9:00 a 12:00 y de 15:00 a 17:00"),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
        Div(LabelInput("Resolución del Consejo de Carrera (número y fecha)", id="resolucion", value=c.get("resolucion") or "",
                       maxlength="120", placeholder="Res. CC 123/2026, 30/09/2026"),
            LabelInput("Resolución del Consejo Facultativo (opcional)", id="resolucion_hcf", value=c.get("resolucion_hcf") or "",
                       maxlength="120", placeholder="Res. CF 45/2026"),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
        P("La convocatoria la aprueba el Consejo de Carrera con visto bueno del Vicedecano (art. 11): sin el número de su resolución "
          "no se puede publicar. El PDF se adjunta aparte y es opcional. La recepción de documentos dura 10 días hábiles desde la "
          "publicación en la primera convocatoria y 5 en la segunda (art. 24).", cls=TextPresets.muted_sm),
        Div(A("Cancelar", href=url if c.get("id") else BASE, cls="uk-btn uk-btn-ghost"), enviar(), cls="flex justify-end gap-2"))


async def _datos_conv(req):
    f = await req.form()
    return {k: f.get(k, "") for k in ("modalidad", "gestion_id", "numero", "titulo", "publicacion", "cierre", "examen", "lugar",
                                      "resolucion", "resolucion_hcf", "recepcion_lugar", "recepcion_horario")}


@rt(f"{BASE}/nueva")
def get(auth):
    if not aux.puede_gestionar(auth):
        return no_autorizado()
    if not aux.gestiones():
        return pagina("Nueva convocatoria", P("Primero registre la gestión en Docencia › Gestiones."), usuario=auth)
    return pagina("Nueva convocatoria", A("← Auxiliaturas", href=BASE, cls="text-sm text-primary"),
                  H2("Nueva convocatoria a auxiliaturas"),
                  P("Solo de los semestres I y II. Se crea con los requisitos del reglamento; después agrega los ítems, sus tribunales y "
                    "los requisitos propios de la Carrera.", cls=(TextPresets.muted_sm, "mb-4")),
                  Div(_form_conv(auth), cls="max-w-4xl"), usuario=auth)


@rt(BASE)
async def post(auth, sess, req):
    if not aux.puede_gestionar(auth):
        return no_autorizado()
    x, errores = aux.validar(await _datos_conv(req), aux.modalidades_de(auth))
    if errores:
        for e in errores:
            add_toast(sess, e, "error")
        return Redirect(f"{BASE}/nueva")
    cid = aux.crear(x, auth["id"])
    auditar(auth["id"], "crear_convocatoria_auxiliatura", "convocatoria_auxiliatura", cid, x["titulo"])
    return Redirect(f"{BASE}/{cid}")


def _gestionable(auth, cid):
    c = aux.obtener(cid)
    return c if c and aux.puede_gestionar(auth, c["modalidad"]) else None


@rt(f"{BASE}/{{cid}}")
def get(auth, cid: int, editar: int = 0):
    c = _gestionable(auth, cid)
    if not c:
        return no_autorizado()
    url = f"{BASE}/{cid}"
    borrador = c["estado"] == "borrador"
    its = aux.items(cid)
    reqs = aux.requisitos(cid)
    chequeo = aux.chequeo_fechas(c)
    calendario = aux.chequeo_calendario(c) if borrador else None
    segunda_plazo = aux.chequeo_segunda(c) if borrador else None
    primera = aux.obtener(c["primera_id"]) if c.get("primera_id") else None
    siguiente = aux.segunda_de(cid)
    falta_pub = aux.faltantes_publicar(c) if borrador else []
    pdfs = adjuntos.listar("convocatoria_auxiliatura", cid)
    if borrador and c["modalidad"] == "docencia":
        opciones_item = seleccion("Materia de la oferta", "asignatura_id",
                                  [(a["id"], f"{a['sigla']} {a['nombre']}") for a in aux.asignaturas_de_la_oferta(c["gestion_id"])],
                                  vacio="— Elija —")
    else:
        opciones_item = Div(seleccion("Proyecto (opcional)", "proyecto_id",
                                      [(p["id"], p["nombre"]) for p in aux.proyectos_vigentes(c["modalidad"])],
                                      vacio="— Sin proyecto —"),
                            LabelInput("Nombre de la auxiliatura", id="titulo", maxlength="200"), cls="space-y-2")
    datos = Div(_form_conv(auth, c), cls="max-w-4xl") if borrador and editar else Div(
        Div(Span("Gestión: ", cls="font-medium"), f"{c['gestion_tipo']}-{c['anio']} · {aux.MODALIDADES[c['modalidad']]} · "
            f"{'primera' if c['numero'] == 1 else 'segunda'} convocatoria"),
        Div(Span("Publicación: ", cls="font-medium"), fecha(c["publicacion"]), Span(" · Cierre: ", cls="font-medium"),
            fecha(c["cierre"]), Span(" · Examen escrito: ", cls="font-medium"), fecha(c["examen"]),
            f" · Exámenes en {c['lugar']}" if c["lugar"] else ""),
        Div(Span("Recepción de documentos: ", cls="font-medium"),
            " · ".join(x for x in (c["recepcion_lugar"], c["recepcion_horario"]) if x) or Span("falta", cls="text-amber-700 dark:text-amber-300")
            ) if c["reglamento"] == aux.REGLAMENTO_VIGENTE else "",
        Div(Span("Resolución: ", cls="font-medium"), c["resolucion"] or Span("falta", cls="text-amber-700 dark:text-amber-300"),
            *[Span(" · ", enlace_adjunto(a, f"{BASE}/{cid}/resolucion/{a['id']}")) for a in pdfs],
            Span(" · Consejo Facultativo: ", cls="font-medium") if c["resolucion_hcf"] else "", c["resolucion_hcf"] or ""),
        *[P(x[1], cls="text-sm " + ("text-green-700 dark:text-green-300" if x[0] else "text-amber-700 dark:text-amber-300"))
          for x in (chequeo, calendario, segunda_plazo) if x],
        Div("Es la segunda convocatoria de ", A(primera["titulo"], href=f"{BASE}/{primera['id']}", cls="text-primary hover:underline"),
            ", con las plazas que esa no cubrió (arts. 13 y 14).", cls="text-sm") if primera else "",
        Div("Segunda convocatoria: ", A(siguiente["titulo"], href=f"{BASE}/{siguiente['id']}", cls="text-primary hover:underline"),
            cls="text-sm") if siguiente else "",
        Div(Span("Comisión: ", cls="font-medium"),
            f"designada por {c['comision_resolucion']}" if c["comision_resolucion"] else
            Span("falta la resolución del Consejo de Carrera que la designa", cls="text-amber-700 dark:text-amber-300"),
            f" · aprobada por {c['comision_resolucion_hcf']}" if c["comision_resolucion_hcf"] else ""
            ) if c["reglamento"] == aux.REGLAMENTO_VIGENTE else "",
        P(f"Según el {aux.reglamento_texto(c)}.", cls=TextPresets.muted_sm),
        A(UkIcon("pencil", height=14, width=14), "Editar datos", href=f"{url}?editar=1", cls="uk-btn uk-btn-default uk-btn-sm gap-1")
        if borrador else "",
        cls="space-y-2 text-sm")
    return pagina(
        c["titulo"],
        A("← Auxiliaturas", href=BASE, cls="text-sm text-primary"),
        Div(Div(H2(c["titulo"]), insignia(aux.ESTADOS_CONV[c["estado"]], TONO_CONV[c["estado"]])),
            Div(boton_post("Publicar y avisar a los estudiantes", f"{url}/publicar", "send", cls=(ButtonT.primary, ButtonT.sm),
                           confirmar="Se avisará a todos los estudiantes con cuenta y a los tribunales. ¿Publicar?",
                           disabled=bool(falta_pub) or None) if borrador else "",
                boton_post("Eliminar", f"{url}/eliminar", "trash-2", cls=(ButtonT.ghost, ButtonT.sm),
                           confirmar="¿Eliminar el borrador de la convocatoria?") if borrador else "",
                boton_post("Generar la segunda convocatoria", f"{url}/segunda", "copy-plus", cls=(ButtonT.primary, ButtonT.sm),
                           confirmar="Se arma un borrador con las plazas que esta convocatoria no cubrió, los mismos requisitos y "
                                     "tribunales. ¿Generarlo?") if aux.puede_generar_segunda(c) else "",
                cls="flex flex-wrap gap-2"),
            cls="flex flex-wrap items-start justify-between gap-4 my-4"),
        falta(["Falta " + x for x in falta_pub]) if falta_pub else "",
        Div(Div(tarjeta("Datos", datos),
                tarjeta("Ítems y tribunales", Div(Table(
                    Thead(Tr(Th("Ítem"), Th("Plazas", cls="w-16 text-right"), Th("h/mes", cls="w-16 text-right"),
                             Th("Tribunal"), Th("Fase", cls="w-32"), Th("", cls="w-10"))),
                    Tbody(*[Tr(Td(A(i["titulo"], href=f"{BASE}/item/{i['id']}", cls="font-medium hover:underline")),
                               Td(str(i["plazas"]), cls="text-right"), Td(str(i["horas"]), cls="text-right"),
                               Td(Span("Completo (4)", cls="text-green-700 dark:text-green-300") if len(i["tribunal"]) == 4 else
                                  A("Designar", href=f"{BASE}/item/{i['id']}", cls="text-amber-700 dark:text-amber-300 hover:underline")),
                               Td(aux.NOMBRE_FASE[i["fase"]], Div(f"{i['n_post']} postulantes", cls=TextPresets.muted_sm)),
                               Td(boton_post("", f"{url}/items/{i['id']}/quitar", "x", cls=(ButtonT.ghost, ButtonT.xs),
                                             aria_label=f"Quitar {i['titulo']}", confirmar="¿Quitar el ítem?") if borrador else ""))
                            for i in its]),
                    cls="uk-table uk-table-divider uk-table-small text-sm min-w-[40rem]"), cls="overflow-x-auto")
                    if its else P("Agregue los ítems que se convocan.", cls=TextPresets.muted_sm),
                    formulario(f"{url}/items", Div(Div(opciones_item, cls="sm:col-span-2"),
                                                   LabelInput("Plazas", id="plazas", type="number", min="1", max="20", value="1"),
                                                   seleccion("Horas al mes", "horas", [(40, "40"), (20, "20")], 40),
                                                   cls="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end"),
                               Div(enviar("Agregar ítem", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"),
                               cls="space-y-2 mt-4 border-t border-border pt-4") if borrador else "",
                    P("Tribunal por ítem: dos docentes y dos estudiantes. Lo designa la Dirección de Carrera o la "
                      "Coordinación académica.", cls=(TextPresets.muted_sm, "mt-2"))),
                cls="space-y-6 lg:col-span-2"),
            Div(tarjeta("Calificación (fija)",
                        *[Div(Span(n), Span(t, cls="font-semibold"), cls="flex justify-between text-sm")
                          for n, t in (("Habilitación", "requisitos"), ("Méritos", f"30 · mín. {_num(aux.reglas(c)['minimo']['meritos'])}"),
                                       ("Examen escrito", f"35 · mín. {_num(aux.reglas(c)['minimo']['escrito'])}"),
                                       ("Examen oral", "35"), ("Para ser titular", f"{aux.PUNTAJE_TITULAR} de 100"))],
                        P(f"Cada fase la califican al menos {aux.QUORUM} miembros del tribunal; la nota es el promedio.",
                          cls=(TextPresets.muted_sm, "mt-2"))),
                tarjeta("Requisitos", Ul(*[Li(Div(Span(r["texto"], cls="text-sm"),
                                                  Div(aux.ACREDITA[r["acredita"]] + (" · solo si corresponde" if r["opcional"] else ""), cls=TextPresets.muted_sm)),
                                              boton_post("", f"{url}/requisitos/{r['id']}/quitar", "x", cls=(ButtonT.ghost, ButtonT.xs),
                                                         aria_label="Quitar requisito") if borrador else "",
                                              cls="flex items-start justify-between gap-2 py-2") for r in reqs],
                                         cls="divide-y divide-border"),
                        formulario(f"{url}/requisitos", LabelInput("Requisito de la Carrera", id="texto", maxlength="400"),
                                   seleccion("Se acredita con", "acredita", [("documento", "Documento"), ("declaracion", "Declaración jurada")]),
                                   Div(enviar("Agregar", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"),
                                   cls="space-y-2 mt-3") if borrador else ""),
                tarjeta("Resolución de la comisión (art. 15)",
                        formulario(f"{url}/comision",
                                   LabelInput("Consejo de Carrera (número y fecha)", id="comision_resolucion",
                                              value=c["comision_resolucion"] or "", maxlength="120", placeholder="Res. CC 130/2026"),
                                   LabelInput("Aprobación del Consejo Facultativo (opcional)", id="comision_resolucion_hcf",
                                              value=c["comision_resolucion_hcf"] or "", maxlength="120", placeholder="Res. CF 52/2026"),
                                   P("Sin la resolución del Consejo de Carrera no se cierra la recepción para empezar a evaluar.",
                                     cls=TextPresets.muted_sm),
                                   Div(enviar("Guardar", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"), cls="space-y-2"))
                if c["reglamento"] == aux.REGLAMENTO_VIGENTE and c["estado"] != "concluida" else "",
                tarjeta("Resolución (PDF, opcional)", Div(*[enlace_adjunto(a, f"{BASE}/{cid}/resolucion/{a['id']}") for a in pdfs],
                                                         cls="flex flex-col gap-1 mb-2"),
                        subir(f"{url}/resolucion", "Adjuntar PDF")),
                cls="space-y-6"),
            cls="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start"),
        usuario=auth)


@rt(f"{BASE}/{{cid}}")
async def post(auth, sess, req, cid: int):
    c = _gestionable(auth, cid)
    if not c or c["estado"] != "borrador":
        return no_autorizado()
    x, errores = aux.validar(await _datos_conv(req), aux.modalidades_de(auth))
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        aux.editar(cid, x)
        add_toast(sess, "Guardado.", "success")
    return Redirect(f"{BASE}/{cid}" + ("?editar=1" if errores else ""))


@rt(f"{BASE}/{{cid}}/items")
async def post(auth, sess, req, cid: int):
    c = _gestionable(auth, cid)
    if not c or c["estado"] != "borrador":
        return no_autorizado()
    for e in aux.agregar_item(c, dict(await req.form())):
        add_toast(sess, e, "error")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/items/{{iid}}/quitar")
def post(auth, cid: int, iid: int):
    c = _gestionable(auth, cid)
    if not c or c["estado"] != "borrador":
        return no_autorizado()
    aux.quitar_item(cid, iid)
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/requisitos")
def post(auth, sess, cid: int, texto: str = "", acredita: str = ""):
    c = _gestionable(auth, cid)
    if not c or c["estado"] != "borrador":
        return no_autorizado()
    for e in aux.agregar_requisito(cid, texto, acredita):
        add_toast(sess, e, "error")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/requisitos/{{rid}}/quitar")
def post(auth, cid: int, rid: int):
    c = _gestionable(auth, cid)
    if not c or c["estado"] != "borrador":
        return no_autorizado()
    aux.quitar_requisito(cid, rid)
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/resolucion")
async def post(auth, sess, cid: int, archivo: UploadFile = None):
    c = _gestionable(auth, cid)
    if not c:
        return no_autorizado()
    contenido, error = await leer_archivo(archivo)
    if not error:
        try:
            adjuntos.guardar("convocatoria_auxiliatura", cid, archivo.filename, contenido, auth["id"])
        except ValueError as e:
            error = str(e)
    add_toast(sess, error or "Resolución adjunta.", "error" if error else "success")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/resolucion/{{adj_id}}")
def get(auth, cid: int, adj_id: int):
    adj = adjuntos.obtener(adj_id)
    if not _gestionable(auth, cid) or not adj or adj["entidad"] != "convocatoria_auxiliatura" or adj["entidad_id"] != cid:
        return no_encontrado()
    return descargar(adj)


@rt(f"{BASE}/{{cid}}/publicar")
def post(auth, sess, cid: int):
    c = _gestionable(auth, cid)
    if not c:
        return no_autorizado()
    errores = aux.publicar(cid)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "publicar_convocatoria_auxiliatura", "convocatoria_auxiliatura", cid, c["titulo"])
        add_toast(sess, "Convocatoria publicada: se avisó a los estudiantes y a los tribunales.", "success")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/comision")
def post(auth, sess, cid: int, comision_resolucion: str = "", comision_resolucion_hcf: str = ""):
    c = _gestionable(auth, cid)
    if not c or c["reglamento"] != aux.REGLAMENTO_VIGENTE or c["estado"] == "concluida":
        return no_autorizado()
    aux.guardar_resolucion_comision(cid, comision_resolucion, comision_resolucion_hcf)
    auditar(auth["id"], "resolucion_comision_auxiliatura", "convocatoria_auxiliatura", cid, comision_resolucion[:120])
    add_toast(sess, "Resolución de la comisión guardada.", "success")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/segunda")
def post(auth, sess, cid: int):
    c = _gestionable(auth, cid)
    if not c:
        return no_autorizado()
    nuevo, errores = aux.generar_segunda(cid, auth["id"])
    for e in errores:
        add_toast(sess, e, "error")
    if nuevo:
        auditar(auth["id"], "generar_segunda_convocatoria_auxiliatura", "convocatoria_auxiliatura", nuevo, f"de la convocatoria {cid}")
        add_toast(sess, "Borrador de la segunda convocatoria: póngale fechas y la resolución del Consejo de Carrera.", "success")
        return Redirect(f"{BASE}/{nuevo}")
    return Redirect(f"{BASE}/{cid}")


@rt(f"{BASE}/{{cid}}/eliminar")
def post(auth, cid: int):
    c = _gestionable(auth, cid)
    if not c or c["estado"] != "borrador":
        return no_autorizado()
    aux.eliminar(cid)
    auditar(auth["id"], "eliminar_convocatoria_auxiliatura", "convocatoria_auxiliatura", cid, c["titulo"])
    return Redirect(BASE)


# --- Personal: un ítem (tribunal, fases, impugnaciones, resultado) -------------------------------------------------------

def _item_visible(auth, iid):
    it = aux.item(iid)
    if not it:
        return None, None
    c = aux.obtener(it["convocatoria_id"])
    if aux.puede_gestionar(auth, c["modalidad"]) or aux.es_miembro(iid, auth["id"]):
        return it, c
    return None, None


@rt(f"{BASE}/item/{{iid}}")
def get(auth, iid: int):
    it, c = _item_visible(auth, iid)
    if not it:
        return no_autorizado()
    url = f"{BASE}/item/{iid}"
    gestor = aux.puede_gestionar(auth, c["modalidad"])
    conduce = aux.puede_conducir(auth, it)
    miembro = aux.es_miembro(iid, auth["id"])
    docentes = {m["usuario_id"] for m in it["tribunal"] if m["tipo"] == "docente"}
    est = {m["usuario_id"] for m in it["tribunal"] if m["tipo"] == "estudiante"}
    d_ops = [(u["id"], f"{u['apellidos']}, {u['nombres']}") for u in aux.docentes_elegibles()]
    e_ops = [(u["id"], f"{u['apellidos']}, {u['nombres']}") for u in aux.estudiantes_elegibles()]
    d_sel, e_sel = (sorted(docentes) + [None, None])[:2], (sorted(est) + [None, None])[:2]
    tribunal = tarjeta(
        "Tribunal",
        Ul(*[Li(f"{m['nombres']} {m['apellidos']}", Span(f" · {m['tipo']}", cls=TextPresets.muted_sm), cls="text-sm")
             for m in it["tribunal"]], cls="space-y-1 mb-3") if it["tribunal"] else P("Sin designar.", cls=TextPresets.muted_sm),
        *[P(UkIcon("triangle-alert", height=12, width=12, cls="inline mr-1"), a,
            cls="text-xs text-amber-700 dark:text-amber-300 mb-2") for a in aux.avisos_comision(it)],
        formulario(f"{url}/tribunal",
                   Div(seleccion("Docente 1", "docente1", d_ops, d_sel[0], "—"), seleccion("Docente 2", "docente2", d_ops, d_sel[1], "—"),
                       seleccion("Estudiante 1", "estudiante1", e_ops, e_sel[0], "—"),
                       seleccion("Estudiante 2", "estudiante2", e_ops, e_sel[1], "—"), cls="grid grid-cols-1 sm:grid-cols-2 gap-3"),
                   P((aux.COMISION_TEXTO[c["modalidad"]] + " " if c["reglamento"] == aux.REGLAMENTO_VIGENTE else
                      "El docente responsable de la materia, un docente de una materia afín y dos estudiantes que la aprobaron con "
                      "notas sobresalientes. ") + "Los estudiantes necesitan cuenta en el sistema. La comisión la designa el Consejo "
                     "de Carrera y la aprueba el Consejo Facultativo: registre sus resoluciones en la convocatoria.",
                     cls=TextPresets.muted_sm),
                   Div(enviar("Guardar tribunal", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"))
        if gestor and it["fase"] in ("postulacion", "habilitacion") else "")
    fase = it["fase"]
    faltan = aux.faltantes_cierre(it)
    previo = aux.cierre_de(iid, aux.anterior(fase)) if fase in aux.FASES else None
    control = tarjeta(
        f"Fase en curso: {aux.NOMBRE_FASE[fase]}",
        P("Al cerrar la fase, cada postulante ve su resultado y tiene 24 horas para impugnar por escrito; la fase siguiente "
          "no se cierra mientras haya impugnaciones sin resolver (art. 21).", cls=(TextPresets.muted_sm, "mb-2")),
        P(f"Fase anterior cerrada el {fecha(previo['cerrada_en'])} (hora UTC).", cls=TextPresets.muted_sm) if previo else "",
        falta(faltan) if faltan and fase != "concluido" else "",
        Div(boton_post("Cerrar la recepción" if fase == "postulacion" else f"Cerrar {aux.NOMBRE_FASE[fase].lower()} y publicar notas",
                       f"{url}/cerrar", "lock", cls=(ButtonT.primary, ButtonT.sm), disabled=bool(faltan) or None,
                       confirmar="¿Cerrar la fase? Las notas ya no se podrán cambiar.") if fase != "concluido" else "",
            A(UkIcon("printer", height=14, width=14), "Acta de calificaciones", href=f"{url}/acta",
              cls="uk-btn uk-btn-default uk-btn-sm gap-1"),
            cls="flex flex-wrap gap-2 mt-3")) if conduce else ""
    tema = tarjeta("Sorteo del tema del examen oral",
                   P(f"Tema sorteado: {it['tema_oral']}", cls="text-sm font-medium") if it["tema_oral"] else "",
                   formulario(f"{url}/tema", area("Temas (uno por línea)", "temas", "", 4),
                              Div(enviar("Sortear", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"))
                   if fase in ("escrito", "oral") else P("Se sortea antes del examen oral.", cls=TextPresets.muted_sm)) \
        if conduce and fase not in ("postulacion", "concluido") else ""
    imps = aux.impugnaciones(iid)
    postul = aux.en_concurso(iid)
    cerradas = [f for f in aux.FASES if aux.cierre_de(iid, f)]
    impug = tarjeta(
        "Impugnaciones",
        P("Se presentan por escrito ante la Dirección de Carrera; aquí solo se registran y se anota su resolución.",
          cls=(TextPresets.muted_sm, "mb-2")),
        Ul(*[Li(Div(Span(f"{m['nombres']} {m['apellidos']}", cls="font-medium"), f" · {aux.NOMBRE_FASE[m['fase']]} · {fecha(m['presentada_en'])}",
                    cls="text-sm"),
                P(m["texto"], cls="text-sm"),
                P(f"Resolución: {m['resolucion']}", cls="text-sm text-green-700 dark:text-green-300") if m["resolucion"] else
                formulario(f"{url}/impugnaciones/{m['id']}", Div(LabelInput("Resolución", id=f"r{m['id']}", name="resolucion",
                                                                             maxlength="2000"), cls="flex-1"),
                           enviar("Registrar", cls=(ButtonT.default, ButtonT.sm)), cls="flex items-end gap-2"),
                cls="py-2 space-y-1") for m in imps], cls="divide-y divide-border"),
        formulario(f"{url}/impugnaciones",
                   Div(seleccion("Postulante", "postulacion_id", [(p["id"], f"{p['nombres']} {p['apellidos']}") for p in postul]),
                       seleccion("Fase", "fase", [(f, aux.NOMBRE_FASE[f]) for f in cerradas]),
                       LabelInput("Presentada el", id="presentada_en", type="date"), cls="grid grid-cols-1 sm:grid-cols-3 gap-3"),
                   area("Motivo", "texto", "", 2),
                   Div(enviar("Registrar impugnación", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"),
                   cls="space-y-2 mt-3 border-t border-border pt-3") if cerradas and postul else "") if conduce else ""
    empatados = [p for p in postul if p["estado"] == "empate"]
    empate = tarjeta(
        "Empate: examen de desempate",
        formulario(f"{url}/desempate",
                   *[fh.Label(fh.Input(type="checkbox", name="ganadores", value=str(p["id"]), cls="uk-checkbox"),
                              f" {p['nombres']} {p['apellidos']}", cls="flex items-center gap-2 text-sm") for p in empatados],
                   P("Marque a quien ganó el examen de desempate.", cls=TextPresets.muted_sm),
                   Div(enviar("Registrar resultado", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"))) \
        if conduce and empatados else ""
    return pagina(
        it["titulo"],
        A(f"← {c['titulo']}", href=f"{BASE}/{c['id']}" if aux.puede_gestionar(auth, c["modalidad"]) else BASE, cls="text-sm text-primary"),
        H2(it["titulo"], cls="mt-2"),
        P(f"{it['plazas']} plaza(s) · {it['horas']} h/mes · {c['titulo']}", cls=(TextPresets.muted_sm, "mb-4")),
        Div(_pasos_item(it), cls="mb-6"),
        panel_calificar(auth, it, f"{url}/calificar", f"{BASE}/documento") if miembro else "",
        Div(tarjeta("Postulantes y notas", tabla_resultados(it, f"{BASE}/documento")), cls="my-6"),
        Div(Div(control, tema, empate, cls="space-y-6"), Div(tribunal, impug, cls="space-y-6"),
            cls="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"),
        usuario=auth)


@rt(f"{BASE}/item/{{iid}}/tribunal")
def post(auth, sess, iid: int, docente1: str = "", docente2: str = "", estudiante1: str = "", estudiante2: str = ""):
    it, c = _item_visible(auth, iid)
    if not it or not aux.puede_gestionar(auth, c["modalidad"]):
        return no_autorizado()
    if it["fase"] not in ("postulacion", "habilitacion"):
        add_toast(sess, "El tribunal ya no se cambia: el concurso está en curso.", "error")
        return Redirect(f"{BASE}/item/{iid}")
    num = [int(x) if str(x).isdigit() else None for x in (docente1, docente2, estudiante1, estudiante2)]
    errores = aux.fijar_tribunal(it, num[:2], num[2:])
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "designar_tribunal_auxiliatura", "item_auxiliatura", iid)
        add_toast(sess, "Tribunal guardado.", "success")
    return Redirect(f"{BASE}/item/{iid}")


@rt(f"{BASE}/item/{{iid}}/calificar")
async def post(auth, sess, req, iid: int):
    it, _ = _item_visible(auth, iid)
    if not it or not aux.es_miembro(iid, auth["id"]):
        return no_autorizado()
    await _guardar_calificacion(auth, sess, req, it)
    return Redirect(f"{BASE}/item/{iid}")


def _conducible(auth, iid):
    it, c = _item_visible(auth, iid)
    return it if it and aux.puede_conducir(auth, it) else None


@rt(f"{BASE}/item/{{iid}}/cerrar")
def post(auth, sess, iid: int):
    it = _conducible(auth, iid)
    if not it:
        return no_autorizado()
    fase = it["fase"]
    errores = aux.cerrar_fase(it, auth["id"])
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "cerrar_fase_auxiliatura", "item_auxiliatura", iid, fase)
        add_toast(sess, f"Se cerró «{aux.NOMBRE_FASE[fase]}».", "success")
    return Redirect(f"{BASE}/item/{iid}")


@rt(f"{BASE}/item/{{iid}}/tema")
def post(auth, sess, iid: int, temas: str = ""):
    it = _conducible(auth, iid)
    if not it:
        return no_autorizado()
    for e in aux.sortear_tema(it, temas):
        add_toast(sess, e, "error")
    return Redirect(f"{BASE}/item/{iid}")


@rt(f"{BASE}/item/{{iid}}/impugnaciones")
def post(auth, sess, iid: int, postulacion_id: int = 0, fase: str = "", presentada_en: str = "", texto: str = ""):
    it = _conducible(auth, iid)
    if not it:
        return no_autorizado()
    errores = aux.registrar_impugnacion(it, postulacion_id, fase, presentada_en, texto, auth["id"])
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "registrar_impugnacion", "item_auxiliatura", iid)
    return Redirect(f"{BASE}/item/{iid}")


@rt(f"{BASE}/item/{{iid}}/impugnaciones/{{mid}}")
def post(auth, sess, iid: int, mid: int, resolucion: str = ""):
    it = _conducible(auth, iid)
    if not it:
        return no_autorizado()
    for e in aux.resolver_impugnacion(iid, mid, resolucion):
        add_toast(sess, e, "error")
    return Redirect(f"{BASE}/item/{iid}")


@rt(f"{BASE}/item/{{iid}}/desempate")
async def post(auth, sess, req, iid: int):
    it = _conducible(auth, iid)
    if not it:
        return no_autorizado()
    f = await req.form()
    errores = aux.resolver_empate(it, [int(x) for x in f.getlist("ganadores") if str(x).isdigit()])
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "resolver_empate_auxiliatura", "item_auxiliatura", iid)
    return Redirect(f"{BASE}/item/{iid}")


@rt(f"{BASE}/item/{{iid}}/acta")
def get(auth, iid: int):
    it, c = _item_visible(auth, iid)
    if not it:
        return no_autorizado()
    from app.comun import config
    return pagina(
        f"Acta · {it['titulo']}",
        Div(fh.Button(UkIcon("printer", height=14, width=14), "Imprimir", type="button", data_accion="imprimir",
                      cls="uk-btn uk-btn-default uk-btn-sm gap-1 no-imprimir"), cls="flex justify-end"),
        Div(P(config.UNIVERSIDAD, cls="font-semibold"), P(config.FACULTAD), P(config.NOMBRE_CARRERA), cls="text-center text-sm"),
        H2("Acta de calificaciones", cls="text-center mt-4"),
        P(f"{c['titulo']} · {it['titulo']} · {it['plazas']} plaza(s) de {it['horas']} h/mes", cls="text-center text-sm mb-1"),
        P(f"Resolución del Consejo de Carrera: {c['resolucion'] or '—'}", cls="text-center text-sm mb-4"),
        tabla_resultados(it, detalle=False),
        H3("Tribunal", cls="mt-8 text-base font-semibold"),
        Div(*[Div(Div(cls="h-12 border-b border-foreground"), P(f"{m['nombres']} {m['apellidos']} ({m['tipo']})", cls="text-sm text-center"))
              for m in it["tribunal"]], cls="grid grid-cols-2 gap-8 mt-4"),
        P(f"Mínimos: méritos {_num(aux.minimo(it, 'meritos'))} de 30, escrito {_num(aux.minimo(it, 'escrito'))} de 35. "
          f"Titular con {aux.PUNTAJE_TITULAR} de 100 ({aux.reglamento_texto(c)}).",
          cls=(TextPresets.muted_sm, "mt-6")),
        usuario=auth)


def _documento_permitido(auth, adj_id):
    """Documento de un requisito de una postulación: lo ven el tribunal del ítem y quien gestiona la convocatoria."""
    adj = adjuntos.obtener(adj_id)
    if not adj or adj["entidad"] != "requisito_postulacion":
        return None
    f = get_db().q("""SELECT p.item_id FROM postulacion_requisito r JOIN postulacion_auxiliatura p ON p.id = r.postulacion_id
                      WHERE r.id = ?""", [adj["entidad_id"]])
    if not f:
        return None
    it, _ = _item_visible(auth, f[0]["item_id"])
    return adj if it else None


@rt(f"{BASE}/documento/{{adj_id}}")
def get(auth, adj_id: int):
    adj = _documento_permitido(auth, adj_id)
    return descargar(adj) if adj else no_encontrado()


# --- Estudiantes: postular -------------------------------------------------------------------------------------------------

@rt(EST)
def get(auth):
    externo, error = _estudiante(auth)
    if error:
        return error
    mias = aux.de_estudiante(externo)
    ya = {p["item_id"]: p for p in mias}
    tribunales = aux.items_de_miembro(auth["id"])
    abiertas = aux.abiertas()
    return pagina(
        "Auxiliaturas",
        H2("Auxiliaturas"),
        P("Postule desde aquí: cada materia o proyecto es una postulación. Suba los documentos que se piden y envíe antes del "
          "cierre.", cls=(TextPresets.muted_sm, "mb-4")),
        Div(*[tarjeta(f"Tribunal: {i['titulo']}", P(i["convocatoria"], " · ", aux.NOMBRE_FASE[i["fase"]], cls=TextPresets.muted_sm),
                      A(f"Calificar ({i['por_calificar']} pendientes)" if i["por_calificar"] else "Ver el concurso",
                        href=f"{TRIB}/{i['id']}", cls="uk-btn uk-btn-primary uk-btn-sm mt-2")) for i in tribunales],
            cls="space-y-4 mb-6") if tribunales else "",
        tarjeta("Mis postulaciones", Ul(*[Li(A(Div(p["item_titulo"], cls="font-medium"), Div(p["convocatoria"], cls=TextPresets.muted_sm),
                                               href=f"{EST}/{p['id']}", cls="min-w-0 hover:underline"),
                                             insignia(aux.ESTADOS_POST[p["estado"]], TONO_POST[p["estado"]]),
                                             cls="flex items-center justify-between gap-3 py-2") for p in mias],
                                        cls="divide-y divide-border"), cls="mb-6") if mias else "",
        Div(*[tarjeta(c["titulo"],
                      P(f"{aux.MODALIDADES[c['modalidad']]} · {c['gestion_tipo']}-{c['anio']} · recepción hasta el "
                        f"{fecha(c['cierre'])} · examen escrito {fecha(c['examen'])}" + (f", {c['lugar']}" if c["lugar"] else ""),
                        cls=(TextPresets.muted_sm, "mb-2")),
                      Ul(*[Li(Div(Div(i["titulo"], cls="font-medium"), Div(f"{i['plazas']} plaza(s) · {i['horas']} h/mes",
                                                                           cls=TextPresets.muted_sm)),
                              A("Continuar", href=f"{EST}/{ya[i['id']]['id']}", cls="uk-btn uk-btn-default uk-btn-sm")
                              if i["id"] in ya else
                              boton_post("Postular", f"{EST}/item/{i['id']}/postular", cls=(ButtonT.primary, ButtonT.sm)),
                              cls="flex items-center justify-between gap-3 py-2") for i in c["items"]],
                         cls="divide-y divide-border")) for c in abiertas], cls="space-y-4")
        if abiertas else P("No hay convocatorias abiertas por ahora.", cls=TextPresets.muted_sm),
        usuario=auth)


def _propia(externo, pid):
    p = aux.postulacion(pid)
    return p if p and p["externo_id"] == externo else None


@rt(f"{EST}/item/{{iid}}/postular")
def post(auth, sess, iid: int):
    externo, error = _estudiante(auth)
    if error:
        return error
    pid, errores = aux.postular(iid, externo)
    for e in errores:
        add_toast(sess, e, "error")
    return Redirect(f"{EST}/{pid}" if pid else EST)


def _pasos_postulacion(p):
    orden = ("postulacion", *aux.FASES, "concluido")
    actual = orden.index(p["fase"])
    fuera = p["fase_fin"]
    pasos = []
    for i, f in enumerate(orden):
        if p["estado"] == "borrador":
            estado = "actual" if f == "postulacion" else "pendiente"
        elif fuera and orden.index(f) > orden.index(fuera):
            estado = "omitido"
        elif fuera == f:
            estado = "error"
        elif f == "concluido" and p["fase"] == "concluido":
            estado = "hecho" if p["estado"] == "titular" else "alerta" if p["estado"] == "empate" else "error"
        else:
            estado = "hecho" if i < actual else "actual" if i == actual else "pendiente"
        pasos.append({"titulo": aux.NOMBRE_FASE[f], "estado": estado})
    return etapas(pasos, etiqueta="Fases de su postulación")


@rt(f"{EST}/{{pid}}")
def get(auth, pid: int):
    externo, error = _estudiante(auth)
    if error:
        return error
    p = _propia(externo, pid)
    if not p:
        return no_encontrado()
    url = f"{EST}/{pid}"
    borrador = p["estado"] == "borrador"
    abierta = aux.abierta(p)
    reqs = aux.requisitos_de(p)
    exigidos = [r for r in reqs if not r["opcional"]]
    cumplidos = sum(r["cumplido"] for r in exigidos)
    faltan = aux.faltantes_envio(p) if borrador else []

    def requisito(r):
        cab = Div(UkIcon("circle-check" if r["cumplido"] else "circle", height=16, width=16,
                         cls="shrink-0 " + ("text-primary" if r["cumplido"] else "text-muted-foreground")),
                  Div(Div(r["texto"], cls="text-sm font-medium"),
                      Div(("Solo si corresponde · " if r["opcional"] else "") + r["detalle"], cls=TextPresets.muted_sm)),
                  cls="flex items-start gap-2")
        acciones = ""
        if borrador and abierta and r["acredita"] == "documento":
            acciones = Div(*[Div(enlace_adjunto(d, f"{EST}/documento/{d['id']}"),
                                 boton_post("", f"{url}/documento/{d['id']}/quitar", "x", cls=(ButtonT.ghost, ButtonT.xs),
                                            aria_label=f"Quitar {d['nombre']}"), cls="flex items-center gap-1")
                             for d in r["documentos"]],
                           subir(f"{url}/requisitos/{r['id']}/archivo", "Subir PDF o foto"), cls="space-y-1 pl-6 mt-1")
        elif borrador and abierta and r["acredita"] == "declaracion":
            acciones = formulario(f"{url}/requisitos/{r['id']}/declarar",
                                  fh.Input(type="hidden", name="valor", value="0" if r["cumplido"] else "1"),
                                  enviar("Retirar mi declaración" if r["cumplido"] else "Declaro que es así",
                                         cls=(ButtonT.default, ButtonT.sm)), cls="pl-6 mt-1")
        return Li(cab, acciones, cls="py-3")

    resultados = [(f, aux.nota(p["id"], f)) for f in aux.FASES if aux.cierre_de(p["item_id"], f)]
    return pagina(
        "Mi postulación",
        A("← Auxiliaturas", href=EST, cls="text-sm text-primary"),
        Div(Span(p["convocatoria"], cls="text-xs font-semibold uppercase text-primary"), H2(p["item_titulo"]),
            P(f"{p['plazas']} plaza(s) · {p['horas']} h/mes · recepción hasta el {fecha(p['cierre'])} · examen escrito "
              f"{fecha(p['examen'])}" + (f", {p['lugar']}" if p["lugar"] else ""), cls=TextPresets.muted_sm),
            insignia(aux.ESTADOS_POST[p["estado"]], TONO_POST[p["estado"]]), cls="space-y-1 my-4"),
        Div(_pasos_postulacion(p), cls="mb-6 overflow-x-auto"),
        Div(Div(
            tarjeta(f"Requisitos · {cumplidos} de {len(exigidos)}",
                    fh.Progress(value=str(cumplidos), max=str(max(1, len(exigidos))), cls="uk-progress",
                                aria_label=f"{cumplidos} de {len(exigidos)} requisitos"),
                    Ul(*[requisito(r) for r in reqs], cls="divide-y divide-border")),
            tarjeta("Plan de trabajo de la materia, proyecto o programa que postula",
                    formulario(f"{url}/propuesta", area("Qué haría en las prácticas y cómo apoyaría al docente", "propuesta",
                                                        p["propuesta"], 5, maxlength="4000"),
                               Div(enviar("Guardar", cls=(ButtonT.default, ButtonT.sm)), cls="flex justify-end"))
                    if borrador and abierta else P(p["propuesta"] or "—", cls="text-sm whitespace-pre-line")),
            cls="space-y-6 lg:col-span-2"),
            Div(tarjeta("Enviar",
                        falta(faltan, "Tiene todo lo que se pide.") if borrador else
                        P(f"Enviada el {fecha(p['enviada_en'])}.", cls="text-sm"),
                        Div(boton_post("Enviar postulación", f"{url}/enviar", "send", cls=ButtonT.primary,
                                       disabled=bool(faltan) or not abierta or None) if borrador else
                            boton_post("Retirar el envío para corregir", f"{url}/retirar", cls=(ButtonT.ghost, ButtonT.sm),
                                       confirmar="¿Retirar el envío? Deberá enviarla de nuevo antes del cierre.") if abierta and
                            p["estado"] == "enviada" else "",
                            boton_post("Descartar", f"{url}/eliminar", "trash-2", cls=(ButtonT.ghost, ButtonT.sm),
                                       confirmar="¿Descartar esta postulación y sus documentos?") if borrador else "",
                            cls="flex flex-wrap gap-2 mt-3"),
                        P("Puede postular a varias materias; cada una es una postulación.", cls=(TextPresets.muted_sm, "mt-2"))),
                tarjeta("Sus resultados",
                        Ul(*[Li(Span(aux.NOMBRE_FASE[f]), Span(("habilitado" if v and v > 0.5 else "no habilitado")
                                                               if f == "habilitacion" else f"{_num(v)} de {aux.MAXIMO[f]}",
                                                               cls="font-semibold"),
                                cls="flex justify-between text-sm py-1") for f, v in resultados], cls="divide-y divide-border"),
                        P(f"Total: {_num(aux.total(p['id']))} de 100" if p["fase"] == "concluido" and p["estado"] in
                          ("titular", "no_seleccionada", "empate") else "", cls="text-sm font-semibold mt-2"),
                        P("Después de cada fase tiene 24 horas para impugnar por escrito ante la Dirección de Carrera.",
                          cls=(TextPresets.muted_sm, "mt-2"))) if resultados else
                tarjeta("Después de enviar", P("Verá aquí su resultado al cerrar cada fase y tendrá 24 horas para impugnar. "
                                               "Si gana, se le pedirán el certificado de no tener deudas, el de la Comisión de "
                                               "Procesos y el formulario SIGEP.", cls="text-sm")),
                cls="space-y-6"),
            cls="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start"),
        usuario=auth)


def _borrador_propio(auth, pid):
    externo, error = _estudiante(auth)
    if error:
        return None, error
    p = _propia(externo, pid)
    if not p:
        return None, no_encontrado()
    if p["estado"] != "borrador" or not aux.abierta(p):
        return None, no_autorizado()
    return p, None


@rt(f"{EST}/{{pid}}/requisitos/{{rid}}/archivo")
async def post(auth, sess, pid: int, rid: int, archivo: UploadFile = None):
    p, error = _borrador_propio(auth, pid)
    if error:
        return error
    r = next((x for x in aux.requisitos_de(p) if x["id"] == rid and x["acredita"] == "documento"), None)
    if not r:
        return no_encontrado()
    contenido, err = await leer_archivo(archivo)
    if not err:
        try:
            adjuntos.guardar("requisito_postulacion", r["fila"], archivo.filename, contenido, auth["id"])
        except ValueError as e:
            err = str(e)
    add_toast(sess, err or "Documento subido.", "error" if err else "success")
    return Redirect(f"{EST}/{pid}")


@rt(f"{EST}/{{pid}}/requisitos/{{rid}}/declarar")
def post(auth, pid: int, rid: int, valor: str = "1"):
    p, error = _borrador_propio(auth, pid)
    if error:
        return error
    if not any(x["id"] == rid and x["acredita"] == "declaracion" for x in aux.requisitos_de(p)):
        return no_encontrado()
    aux.declarar(pid, rid, valor == "1")
    return Redirect(f"{EST}/{pid}")


def _documento_propio(auth, adj_id):
    externo, error = _estudiante(auth)
    if error:
        return None
    adj = adjuntos.obtener(adj_id)
    if not adj or adj["entidad"] != "requisito_postulacion":
        return None
    f = get_db().q("""SELECT p.externo_id, p.id FROM postulacion_requisito r JOIN postulacion_auxiliatura p ON p.id = r.postulacion_id
                      WHERE r.id = ?""", [adj["entidad_id"]])
    return (adj, f[0]["id"]) if f and f[0]["externo_id"] == externo else None


@rt(f"{EST}/documento/{{adj_id}}")
def get(auth, adj_id: int):
    r = _documento_propio(auth, adj_id)
    return descargar(r[0]) if r else no_encontrado()


@rt(f"{EST}/{{pid}}/documento/{{adj_id}}/quitar")
def post(auth, pid: int, adj_id: int):
    p, error = _borrador_propio(auth, pid)
    if error:
        return error
    r = _documento_propio(auth, adj_id)
    if not r or r[1] != pid:
        return no_encontrado()
    adjuntos.eliminar(r[0])
    return Redirect(f"{EST}/{pid}")


@rt(f"{EST}/{{pid}}/propuesta")
def post(auth, sess, pid: int, propuesta: str = ""):
    p, error = _borrador_propio(auth, pid)
    if error:
        return error
    aux.guardar_propuesta(pid, propuesta)
    add_toast(sess, "Plan de trabajo guardado.", "success")
    return Redirect(f"{EST}/{pid}")


@rt(f"{EST}/{{pid}}/enviar")
def post(auth, sess, pid: int):
    externo, error = _estudiante(auth)
    if error:
        return error
    if not _propia(externo, pid):
        return no_encontrado()
    errores = aux.enviar(pid)
    for e in errores:
        add_toast(sess, e, "error")
    if not errores:
        auditar(auth["id"], "enviar_postulacion_auxiliatura", "postulacion_auxiliatura", pid)
        add_toast(sess, "Postulación enviada. Le avisaremos el resultado de cada fase.", "success")
    return Redirect(f"{EST}/{pid}")


@rt(f"{EST}/{{pid}}/retirar")
def post(auth, sess, pid: int):
    externo, error = _estudiante(auth)
    if error:
        return error
    if not _propia(externo, pid):
        return no_encontrado()
    for e in aux.retirar(pid):
        add_toast(sess, e, "error")
    return Redirect(f"{EST}/{pid}")


@rt(f"{EST}/{{pid}}/eliminar")
def post(auth, pid: int):
    p, error = _borrador_propio(auth, pid)
    if error:
        return error
    aux.eliminar_borrador(pid)
    return Redirect(EST)


# --- Estudiantes del tribunal ----------------------------------------------------------------------------------------------

def _miembro_estudiante(auth, iid):
    externo, error = _estudiante(auth)
    if error:
        return None, error
    it = aux.item(iid)
    if not it or not aux.es_miembro(iid, auth["id"]):
        return None, no_encontrado()
    return it, None


@rt(f"{TRIB}/{{iid}}")
def get(auth, iid: int):
    it, error = _miembro_estudiante(auth, iid)
    if error:
        return error
    c = aux.obtener(it["convocatoria_id"])
    return pagina(
        f"Tribunal · {it['titulo']}",
        A("← Auxiliaturas", href=EST, cls="text-sm text-primary"),
        H2(f"Tribunal: {it['titulo']}", cls="mt-2"),
        P(f"{c['titulo']} · Usted integra el tribunal como estudiante.", cls=(TextPresets.muted_sm, "mb-4")),
        Div(_pasos_item(it), cls="mb-6 overflow-x-auto"),
        panel_calificar(auth, it, f"{TRIB}/{iid}/calificar", f"{TRIB}/documento"),
        Div(tarjeta("Postulantes y notas", tabla_resultados(it, f"{TRIB}/documento")), cls="mt-6"),
        usuario=auth)


@rt(f"{TRIB}/{{iid}}/calificar")
async def post(auth, sess, req, iid: int):
    it, error = _miembro_estudiante(auth, iid)
    if error:
        return error
    await _guardar_calificacion(auth, sess, req, it)
    return Redirect(f"{TRIB}/{iid}")


@rt(f"{TRIB}/documento/{{adj_id}}")
def get(auth, adj_id: int):
    externo, error = _estudiante(auth)
    if error:
        return error
    adj = adjuntos.obtener(adj_id)
    if not adj or adj["entidad"] != "requisito_postulacion":
        return no_encontrado()
    f = get_db().q("""SELECT p.item_id FROM postulacion_requisito r JOIN postulacion_auxiliatura p ON p.id = r.postulacion_id
                      WHERE r.id = ?""", [adj["entidad_id"]])
    return descargar(adj) if f and aux.es_miembro(f[0]["item_id"], auth["id"]) else no_encontrado()
