"""Oferta por gestión y asignación docente; gestiones académicas. La consultan todos; la editan la
Dirección de Carrera y la Coordinación académica (acción `gestionar_oferta`)."""
from collections import Counter
from datetime import date
import base64

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Code, Datalist, Div, Input, Li, Option, P, Redirect, Response, Select, Span,
                             Ul, UploadFile)
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import cambios, gestiones, importar_oferta, oferta, preferencias
from app.comun import permisos
from app.comun import formato
from app.comun.componentes.layout import CERRAR, ID_MODAL, campo, cerrar_modal, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar, get_db, transaccion

rt = APIRouter()
BASE = "/docencia/oferta"
ID_OFERTA = "oferta-gestion"


def _puede(auth):
    return permisos.puede(auth, "gestionar_oferta")


def _selector(g):
    return Select(*[Option(f"{gestiones.codigo(x)} · {gestiones.TIPOS[x['tipo']]}", value=str(x["id"]),
                           selected=x["id"] == g["id"]) for x in gestiones.listar()],
                  name="gestion", aria_label="Gestión", cls="uk-select w-72",
                  data_navegar=f"{BASE}?gestion=")


def _docente(d, g, puede):
    aviso = Span(" · sin vínculo con la Carrera", cls="text-xs text-amber-700 dark:text-amber-400",
                 title="No tiene vínculo vigente con la Carrera al inicio de la gestión") \
        if oferta.sin_vinculo_con_la_carrera(d["usuario_id"], g) else ""
    quitar = fh.Button(UkIcon("x", height=12, width=12), type="button", aria_label="Quitar docente",
                       cls="p-0.5 rounded hover:text-destructive", hx_delete=f"{BASE}/docentes/{d['id']}",
                       hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML",
                       hx_confirm=f"¿Quitar a {d['nombres']} {d['apellidos']} de este paralelo?") if puede else ""
    carga = (f" · {oferta.HORAS_POR_MATERIA} h/mes" if d["rol"] == "titular" and g["tipo"] not in oferta.TEMPORADA
             else "")
    return Li(Span(f"{d['nombres']} {d['apellidos']}", cls="text-sm"),
              Span(f" · {oferta.ROLES[d['rol']].lower()}{carga}", cls=TextPresets.muted_sm),
              aviso, quitar, cls="flex items-center gap-1")


def _form_docente(o, g):
    pref = preferencias.por_asignatura(g["id"], o["asignatura_id"])
    marca = {"prefiere": " (la prefiere)", "no_puede": " (indicó que no puede dictarla)"}
    posibles = sorted(oferta.docentes_posibles(g), key=lambda p: pref.get(p["id"]) != "prefiere")   # primero quien la prefiere
    return fh.Details(fh.Summary("+ Asignar docente", cls="cursor-pointer text-xs text-primary mt-1"), fh.Form(
        Select(Option("Docente…", value=""),
               *[Option(f"{p['apellidos']}, {p['nombres']}" + ("" if p["con_vinculo"] else " (sin vínculo con la Carrera)")
                        + marca.get(pref.get(p["id"]), ""), value=str(p["id"])) for p in posibles],
               name="usuario", cls="uk-select h-8 text-sm w-64", aria_label="Docente", required=True),
        Select(*[Option(t, value=k) for k, t in oferta.ROLES.items()], name="rol", cls="uk-select h-8 text-sm w-28",
               aria_label="Rol"),
        Button("Asignar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
        hx_post=f"{BASE}/{o['id']}/docentes", hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML",
        cls="flex flex-wrap gap-2 mt-2"))


def seccion_oferta(g, auth, errores=(), oob=False):
    puede = _puede(auth)
    activa = g["estado"] == "activa"
    troncales = {a["id"] for a in oferta.troncales(g["anio"])}
    paralelos = oferta.listar(g["id"], historial=g["estado"] != "planificacion")
    # Los programas se muestran solo donde difieren de los de la mayoría (PLAN §62, UX-02): repetidos en cada fila
    # no dicen nada.
    programas = {o["asignatura_id"]: ", ".join(oferta.programas_de(o["asignatura_id"])) for o in paralelos}
    comunes = Counter(programas.values()).most_common(1)[0][0] if programas else ""
    filas = []
    for o in paralelos:
        if g["estado"] != "planificacion":
            filas.append(_fila_activa(o, g, puede and activa, programas, comunes, troncales))
            continue
        quitar = fh.Button(UkIcon("trash-2", height=14, width=14), type="button", aria_label="Quitar de la oferta",
                           cls="p-1 rounded hover:bg-muted hover:text-destructive", hx_delete=f"{BASE}/{o['id']}",
                           hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML",
                           hx_confirm=f"¿Quitar {o['sigla']} paralelo {o['paralelo']} de la oferta?") if puede else ""
        filas.append(fh.Tr(
            fh.Td(o["sigla"], cls="font-mono text-sm whitespace-nowrap"),
            fh.Td(Div(o["nombre"], cls="text-sm"),
                  Div(" · ".join(x for x in (programas[o["asignatura_id"]] if programas[o["asignatura_id"]] != comunes
                                              else "", "troncal" if o["asignatura_id"] in troncales else "") if x),
                      cls=TextPresets.muted_sm)),
            fh.Td(o["paralelo"], cls="text-sm"),
            fh.Td(str(o["inscritos"]) if o["inscritos"] is not None else "—", cls="text-sm tabular-nums"),
            fh.Td(Ul(*[_docente(d, g, puede) for d in o["docentes"]]) if o["docentes"]
                  else insignia("Sin docente", "ambar", icono="circle-alert"),
                  _form_docente(o, g) if puede else ""),
            fh.Td(quitar)))
    lista = Datalist(*[Option(value=f"{a['sigla']} · {a['nombre']}") for a in oferta.asignaturas_ofertables()],
                     id="asignaturas-ofertables")
    agregar = fh.Form(
        mensaje_error(*errores),
        Div(Input(name="asignatura", list="asignaturas-ofertables", cls="uk-input w-96", required=True,
                  placeholder="Asignatura (sigla o nombre)", aria_label="Asignatura"),
            Input(name="paralelo", value="A", cls="uk-input w-20", aria_label="Paralelo"),
            Input(name="inscritos", cls="uk-input w-28", placeholder="Inscritos", aria_label="Inscritos",
                  inputmode="numeric"),
            Button(UkIcon("plus", height=14, width=14), "Agregar a la oferta", type="submit", cls=ButtonT.primary),
            cls="flex flex-wrap gap-2"),
        lista, hx_post=f"{BASE}/{g['id']}", hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML",
        cls="space-y-2 mb-4") if puede and g["estado"] == "planificacion" else (
        Div(Button(UkIcon("plus", height=14, width=14), "Agregar una materia", cls=ButtonT.primary,
                   hx_get=f"{BASE}/cambio/{g['id']}/materia", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML"), cls="mb-4")
        if puede and activa else "")
    total = sum(len(o["docentes"]) == 0 and not o["retirada_en"] for o in paralelos)
    return Div(
        agregar,
        Div(P(f"{len(filas)} paralelo(s)", f" · programas (salvo indicación): {comunes}" if comunes else "", cls=TextPresets.muted_sm),
            Button(UkIcon("circle-alert", height=14, width=14), f"Ver los {total} sin docente" if total > 1 else
                   "Ver el que no tiene docente", type="button", cls=(ButtonT.default, ButtonT.sm, "gap-1"),
                   data_accion="filtrar-tabla", data_filtro="Sin docente", aria_pressed="false") if total else "",
            cls="flex flex-wrap items-center gap-3 mb-2"),
        Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Sigla"), fh.Th("Asignatura"), fh.Th("Paralelo"), fh.Th("Inscritos"),
                                    fh.Th("Docentes"), fh.Th(""))), fh.Tbody(*filas),
                     cls="uk-table uk-table-divider uk-table-small", data_tabla=f"oferta-{gestiones.codigo(g)}"),
            cls="overflow-x-auto")
        if filas else P("Aún no hay asignaturas en la oferta de esta gestión.", cls=TextPresets.muted_sm),
        id=ID_OFERTA, hx_swap_oob="true" if oob else None)


@rt(BASE)
def get(auth, gestion: str = ""):
    g = gestiones.obtener(int(gestion)) if gestion.isdigit() else gestiones.actual()
    if not g:
        return pagina("Oferta y docentes",
                      P("Todavía no hay gestiones registradas. ", A("Crear las gestiones de un año", href="/docencia/gestiones",
                                                                    cls="text-primary hover:underline"),
                        cls="text-sm"), usuario=auth, seccion="docencia")
    anterior = oferta.mismo_semestre_anio_anterior(g)
    anterior = anterior if anterior and oferta.listar(anterior["id"]) else None
    temporada = P("Curso de temporada: solo lo dictan docentes titulares y no suma a la carga horaria del semestre "
                  "(cuenta como docencia dictada).", cls="text-sm text-amber-700 dark:text-amber-400 mb-4") \
        if g["tipo"] in oferta.TEMPORADA else ""
    libre = gestiones.edicion_libre(g)
    n_cambios = len(cambios.listar(g["id"])) if g["estado"] != "planificacion" else 0
    estado = Div(estado_insignia(g),
                 P("Los cambios en la oferta y en los docentes piden motivo y fecha de efecto, y quedan registrados."
                   if g["estado"] == "activa" else "Es historial, de solo lectura. La Dirección de Carrera puede reabrirla "
                   "para corregirla; la oferta de un semestre pasado también se carga por CSV.",
                   cls=TextPresets.muted_sm) if not libre else "",
                 A(UkIcon("history", height=14, width=14), f"Cambios del semestre ({n_cambios})",
                   href=f"{BASE}/{g['id']}/cambios",
                   cls="inline-flex items-center gap-1 text-sm text-primary hover:underline") if n_cambios or not libre
                 else "", cls="flex flex-wrap items-center gap-3 mb-4")
    return pagina(
        "Oferta y docentes",
        Div(Div(H2(gestiones.codigo(g)), P(f"{gestiones.nombre(g)} · {formato.periodo(g['fecha_inicio'], g['fecha_fin'])}",
                                           cls=TextPresets.muted_sm)),
            Div(_selector(g),
                Button(UkIcon("list-plus", height=16, width=16), "Agregar las troncales", cls=ButtonT.default,
                       hx_post=f"{BASE}/{g['id']}/troncales", hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML",
                       hx_confirm="¿Agregar a la oferta las troncales de las licenciaturas que aún no están "
                                  "(paralelo A)?") if _puede(auth) and libre and g["tipo"] not in oferta.TEMPORADA else "",
                Button(UkIcon("copy", height=16, width=16), f"Copiar de {gestiones.codigo(anterior)}", cls=ButtonT.default,
                       hx_get=f"{BASE}/{g['id']}/copiar", hx_target=f"#{ID_MODAL}") if _puede(auth) and libre and anterior else "",
                A(UkIcon("grid-3x3", height=16, width=16), "Asignar en grilla", href=f"{BASE}/{g['id']}/grilla",
                  cls="uk-btn uk-btn-default inline-flex items-center gap-1") if _puede(auth) and libre else "",
                Button(UkIcon("file-up", height=16, width=16), "Importar CSV", cls=ButtonT.default,
                       hx_get=f"{BASE}/importar", hx_target=f"#{ID_MODAL}") if _puede(auth) and g["estado"] != "activa" else "",
                cls="flex flex-wrap gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        estado, temporada,
        seccion_oferta(g, auth),
        usuario=auth, seccion="docencia")


# --- Con el semestre activo: cambios con motivo y fecha (PLAN §66) ----------------------------------------------

def _fecha(f):
    return formato.fecha(f) if f else ""


def _docente_activa(d, g, puede):
    """Un docente con sus fechas, y —si sigue— los botones para reasignarlo o retirarlo."""
    nombre = f"{d['nombres']} {d['apellidos']}"
    if d["hasta"]:
        return Li(Span(nombre, cls="text-sm line-through text-muted-foreground"),
                  Span(f" · {oferta.ROLES[d['rol']].lower()} · {'del ' + _fecha(d['desde']) + ' ' if d['desde'] else ''}"
                       f"hasta el {_fecha(d['hasta'])}", cls=TextPresets.muted_sm), cls="flex items-center gap-1")
    desde = f" · desde el {_fecha(d['desde'])}" if d["desde"] else ""
    botones = [fh.Button(UkIcon("arrow-left-right", height=12, width=12), type="button", aria_label=f"Reasignar a {nombre}",
                         title="Reasignar a otra persona", cls="p-0.5 rounded hover:text-primary",
                         hx_get=f"{BASE}/cambio/docente/{d['id']}/reasignar", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML"),
               fh.Button(UkIcon("user-minus", height=12, width=12), type="button", aria_label=f"Retirar a {nombre}",
                         title="Retirar del paralelo", cls="p-0.5 rounded hover:text-destructive",
                         hx_get=f"{BASE}/cambio/docente/{d['id']}/retirar", hx_target=f"#{ID_MODAL}",
                         hx_swap="innerHTML")] if puede else []
    carga = (f" · {oferta.HORAS_POR_MATERIA} h/mes" if d["rol"] == "titular" and g["tipo"] not in oferta.TEMPORADA else "")
    return Li(Span(nombre, cls="text-sm"), Span(f" · {oferta.ROLES[d['rol']].lower()}{carga}{desde}", cls=TextPresets.muted_sm),
              *botones, cls="flex items-center gap-1")


def _fila_activa(o, g, puede, programas, comunes, troncales):
    retirada = bool(o["retirada_en"])
    boton = fh.Button(UkIcon("circle-x", height=14, width=14), type="button", aria_label=f"Retirar {o['sigla']} {o['paralelo']}",
                      title="Retirar la materia del semestre", cls="p-1 rounded hover:bg-muted hover:text-destructive",
                      hx_get=f"{BASE}/cambio/{o['id']}/retirar", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML") \
        if puede and not retirada else ""
    nota = " · ".join(x for x in (programas[o["asignatura_id"]] if programas[o["asignatura_id"]] != comunes else "",
                                  "troncal" if o["asignatura_id"] in troncales else "",
                                  f"agregada el {_fecha(o['agregada_en'])}" if o["agregada_en"] else "") if x)
    docentes = Ul(*[_docente_activa(d, g, puede and not retirada) for d in o["docentes"]]) if o["docentes"] else (
        "" if retirada else insignia("Sin docente", "ambar", icono="circle-alert"))
    agregar = fh.Button("+ Asignar docente", type="button", cls="cursor-pointer text-xs text-primary mt-1",
                        hx_get=f"{BASE}/cambio/{o['id']}/docente", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML") \
        if puede and not retirada else ""
    return fh.Tr(
        fh.Td(o["sigla"], cls="font-mono text-sm whitespace-nowrap"),
        fh.Td(Div(o["nombre"], cls="text-sm" + (" line-through text-muted-foreground" if retirada else "")),
              Div(nota, cls=TextPresets.muted_sm) if nota else "",
              Div(insignia(f"Retirada desde el {_fecha(o['retirada_en'])}", "gris", icono="circle-x"),
                  Span(f" {o['motivo_retiro']}", cls=TextPresets.muted_sm)) if retirada else ""),
        fh.Td(o["paralelo"], cls="text-sm"),
        fh.Td(str(o["inscritos"]) if o["inscritos"] is not None else "—", cls="text-sm tabular-nums"),
        fh.Td(docentes, agregar), fh.Td(boton))


def _campos_cambio(g, v=None):
    v = v or {}
    hoy = date.today().isoformat()
    por_omision = v.get("fecha") or (hoy if g["fecha_inicio"] <= hoy <= g["fecha_fin"] else g["fecha_inicio"])
    return Div(
        campo("Fecha de efecto (primer día en que rige el cambio)",
              Input(type="date", name="fecha", value=por_omision, min=g["fecha_inicio"], max=g["fecha_fin"], required=True,
                    cls="uk-input")),
        campo("Motivo", Select(Option("Elija el motivo…", value=""),
                               *[Option(t, value=k, selected=v.get("motivo") == k) for k, t in cambios.MOTIVOS.items()],
                               name="motivo", required=True, cls="uk-select")),
        campo("Detalle (obligatorio si el motivo es «Otro»)",
              fh.Textarea(v.get("detalle", ""), name="detalle", rows=3, cls="uk-textarea")),
        cls="space-y-3")


def _modal_cambio(titulo, g, url, *extra, errores=(), v=None, boton="Registrar el cambio"):
    return modal(titulo, fh.Form(
        mensaje_error(*errores), P(f"{gestiones.codigo(g)} está activa: el cambio queda registrado con su fecha y su motivo.",
                                    cls=(TextPresets.muted_sm, "mb-3")),
        *extra, _campos_cambio(g, v),
        Div(Button(boton, type="submit", cls=ButtonT.primary),
            Button("Cancelar", type="button", cls=ButtonT.ghost, **CERRAR), cls="flex gap-2 justify-end mt-4"),
        hx_post=url, hx_target=f"#{ID_MODAL}", hx_swap="innerHTML", hx_disabled_elt="find button[type='submit']",
        cls="space-y-3"), ancho="max-w-xl")


def _datos_cambio(form):
    return {k: form.get(k, "") for k in ("fecha", "motivo", "detalle")}


def _exito(g, auth):
    """Cierra el modal y actualiza la oferta de la página (fuera de banda)."""
    return cerrar_modal(), seccion_oferta(g, auth, oob=True)


def _autoriza_cambio(auth):
    return None if _puede(auth) else Response("No autorizado", status_code=403)


def _paralelo_o_404(oid):
    o = oferta.obtener(oid)
    return o, (None if o else Response("No encontrado", status_code=404))


def _docentes_para(g, excluir=()):
    return [Option(f"{p['apellidos']}, {p['nombres']}" + ("" if p["con_vinculo"] else " (sin vínculo con la Carrera)"),
                   value=str(p["id"])) for p in oferta.docentes_posibles(g) if p["id"] not in excluir]


@rt(f"{BASE}/cambio/{{gid}}/materia")
def get(auth, gid: int):
    if (no := _autoriza_cambio(auth)):
        return no
    g, error = _gestion_o_404(gid)
    if error:
        return error
    if not cambios.exige_motivo(g):
        return Response("Los cambios con motivo solo se hacen con la gestión activa.", status_code=409)
    return _modal_cambio("Agregar una materia al semestre", g, f"{BASE}/cambio/{gid}/materia", _campos_materia(),
                         boton="Agregar la materia")


def _campos_materia(v=None):
    v = v or {}
    return Div(Div(Input(name="asignatura", list="asignaturas-ofertables", value=v.get("asignatura", ""), required=True,
                         cls="uk-input", placeholder="Asignatura (sigla o nombre)", aria_label="Asignatura"),
                   Datalist(*[Option(value=f"{a['sigla']} · {a['nombre']}") for a in oferta.asignaturas_ofertables()],
                            id="asignaturas-ofertables"), cls="mb-2"),
               Div(campo("Paralelo", Input(name="paralelo", value=v.get("paralelo", "A"), cls="uk-input")),
                   campo("Inscritos (opcional)", Input(name="inscritos", value=v.get("inscritos", ""),
                                                       inputmode="numeric", cls="uk-input")),
                   cls="grid grid-cols-2 gap-3"))


@rt(f"{BASE}/cambio/{{gid}}/materia")
async def post(auth, sess, gid: int, req):
    if (no := _autoriza_cambio(auth)):
        return no
    g, error = _gestion_o_404(gid)
    if error:
        return error
    f = await req.form()
    v = {**_datos_cambio(f), "asignatura": f.get("asignatura", ""), "paralelo": f.get("paralelo", "A"),
         "inscritos": f.get("inscritos", "")}
    errores = cambios.agregar_materia(gid, v["asignatura"], v["paralelo"], v["inscritos"], v, auth["id"])
    if errores:
        return _modal_cambio("Agregar una materia al semestre", g, f"{BASE}/cambio/{gid}/materia", _campos_materia(v),
                             errores=errores, v=v, boton="Agregar la materia")
    add_toast(sess, "Materia agregada al semestre.", "success")
    return _exito(g, auth)


@rt(f"{BASE}/cambio/{{oid}}/retirar")
def get(auth, oid: int):
    if (no := _autoriza_cambio(auth)):
        return no
    o, error = _paralelo_o_404(oid)
    if error:
        return error
    g = gestiones.obtener(o["gestion_id"])
    return _modal_cambio(f"Retirar {o['sigla']} {o['paralelo']}", g, f"{BASE}/cambio/{oid}/retirar",
                         P(f"{o['nombre']}. La materia queda en el registro, marcada como retirada; sus docentes dejan "
                           "el paralelo desde la fecha de efecto.", cls="text-sm"), boton="Retirar la materia")


@rt(f"{BASE}/cambio/{{oid}}/retirar")
async def post(auth, sess, oid: int, req):
    if (no := _autoriza_cambio(auth)):
        return no
    o, error = _paralelo_o_404(oid)
    if error:
        return error
    g = gestiones.obtener(o["gestion_id"])
    v = _datos_cambio(await req.form())
    errores = cambios.retirar_materia(oid, v, auth["id"])
    if errores:
        return _modal_cambio(f"Retirar {o['sigla']} {o['paralelo']}", g, f"{BASE}/cambio/{oid}/retirar", errores=errores,
                             v=v, boton="Retirar la materia")
    add_toast(sess, f"{o['sigla']} retirada del semestre.", "success")
    return _exito(g, auth)


@rt(f"{BASE}/cambio/{{oid}}/docente")
def get(auth, oid: int):
    if (no := _autoriza_cambio(auth)):
        return no
    o, error = _paralelo_o_404(oid)
    if error:
        return error
    g = gestiones.obtener(o["gestion_id"])
    return _modal_cambio(f"Asignar un docente a {o['sigla']} {o['paralelo']}", g, f"{BASE}/cambio/{oid}/docente",
                         _campos_docente(g), boton="Asignar")


def _campos_docente(g, v=None, etiqueta="Docente"):
    v = v or {}
    return Div(campo(etiqueta, Select(Option("Elija a la persona…", value=""), *_docentes_para(g), name="usuario",
                                      required=True, cls="uk-select")),
               campo("Rol", Select(*[Option(t, value=k, selected=v.get("rol") == k) for k, t in oferta.ROLES.items()],
                                   name="rol", cls="uk-select")), cls="grid grid-cols-2 gap-3 mb-3")


@rt(f"{BASE}/cambio/{{oid}}/docente")
async def post(auth, sess, oid: int, req):
    if (no := _autoriza_cambio(auth)):
        return no
    o, error = _paralelo_o_404(oid)
    if error:
        return error
    g = gestiones.obtener(o["gestion_id"])
    f = await req.form()
    v = {**_datos_cambio(f), "rol": f.get("rol", "titular")}
    usuario = f.get("usuario", "")
    errores = cambios.agregar_docente(oid, int(usuario) if usuario.isdigit() else 0, v["rol"], v, auth["id"])
    if errores:
        return _modal_cambio(f"Asignar un docente a {o['sigla']} {o['paralelo']}", g, f"{BASE}/cambio/{oid}/docente",
                             _campos_docente(g, v), errores=errores, v=v, boton="Asignar")
    add_toast(sess, "Docente asignado.", "success")
    return _exito(g, auth)


def _docente_o_404(did):
    filas = get_db().q("SELECT * FROM oferta_docente WHERE id = ?", [did])
    if not filas:
        return None, None, Response("No encontrado", status_code=404)
    o = oferta.obtener(filas[0]["oferta_id"])
    return filas[0], o, None


@rt(f"{BASE}/cambio/docente/{{did}}/reasignar")
def get(auth, did: int):
    if (no := _autoriza_cambio(auth)):
        return no
    d, o, error = _docente_o_404(did)
    if error:
        return error
    g = gestiones.obtener(o["gestion_id"])
    return _modal_cambio(f"Reasignar {o['sigla']} {o['paralelo']}", g, f"{BASE}/cambio/docente/{did}/reasignar",
                         Div(P("La persona que dicta hoy deja el paralelo desde la fecha de efecto y entra la nueva, con "
                               "el mismo rol. Los dos reciben un aviso.", cls=(TextPresets.muted_sm, "mb-2")),
                             campo("Nueva persona", Select(Option("Elija a la persona…", value=""),
                                                           *_docentes_para(g), name="usuario", required=True,
                                                           cls="uk-select")), cls="mb-3"), boton="Reasignar")


@rt(f"{BASE}/cambio/docente/{{did}}/reasignar")
async def post(auth, sess, did: int, req):
    if (no := _autoriza_cambio(auth)):
        return no
    d, o, error = _docente_o_404(did)
    if error:
        return error
    g = gestiones.obtener(o["gestion_id"])
    f = await req.form()
    v = _datos_cambio(f)
    usuario = f.get("usuario", "")
    errores = cambios.reasignar_docente(did, int(usuario) if usuario.isdigit() else 0, v, auth["id"])
    if errores:
        return _modal_cambio(f"Reasignar {o['sigla']} {o['paralelo']}", g, f"{BASE}/cambio/docente/{did}/reasignar",
                             Div(campo("Nueva persona", Select(Option("Elija a la persona…", value=""),
                                                               *_docentes_para(g), name="usuario", required=True,
                                                               cls="uk-select")), cls="mb-3"),
                             errores=errores, v=v, boton="Reasignar")
    add_toast(sess, "Docente reasignado.", "success")
    return _exito(g, auth)


@rt(f"{BASE}/cambio/docente/{{did}}/retirar")
def get(auth, did: int):
    if (no := _autoriza_cambio(auth)):
        return no
    d, o, error = _docente_o_404(did)
    if error:
        return error
    g = gestiones.obtener(o["gestion_id"])
    return _modal_cambio(f"Retirar a un docente de {o['sigla']} {o['paralelo']}", g,
                         f"{BASE}/cambio/docente/{did}/retirar",
                         P("La persona deja el paralelo desde la fecha de efecto y recibe un aviso. Si era la titular, el "
                           "paralelo queda sin titular.", cls="text-sm"), boton="Retirar")


@rt(f"{BASE}/cambio/docente/{{did}}/retirar")
async def post(auth, sess, did: int, req):
    if (no := _autoriza_cambio(auth)):
        return no
    d, o, error = _docente_o_404(did)
    if error:
        return error
    g = gestiones.obtener(o["gestion_id"])
    v = _datos_cambio(await req.form())
    errores = cambios.retirar_docente(did, v, auth["id"])
    if errores:
        return _modal_cambio(f"Retirar a un docente de {o['sigla']} {o['paralelo']}", g,
                             f"{BASE}/cambio/docente/{did}/retirar", errores=errores, v=v, boton="Retirar")
    add_toast(sess, "Docente retirado del paralelo.", "success")
    return _exito(g, auth)


@rt(f"{BASE}/{{gid}}/cambios")
def get(auth, gid: int):
    if not (_puede(auth) or permisos.puede(auth, "ver_carga")):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_o_404(gid)
    if error:
        return error
    filas = []
    for c in cambios.listar(gid):
        quien = " → ".join(x for x in (c["anterior"], c["nuevo"]) if x)
        filas.append(fh.Tr(fh.Td(_fecha(c["fecha_efecto"]), cls="text-sm whitespace-nowrap"),
                           fh.Td(cambios.TIPOS[c["tipo"]], cls="text-sm"),
                           fh.Td(f"{c['sigla']} {c['paralelo']}" if c["sigla"] else "", cls="font-mono text-sm"),
                           fh.Td(quien, cls="text-sm"),
                           fh.Td(Div(cambios.MOTIVOS[c["motivo"]], cls="text-sm"),
                                 Div(c["detalle"] or "", cls=TextPresets.muted_sm)),
                           fh.Td(Div(c["por"] or "", cls="text-sm"), Div(formato.fecha_hora(c["registrado_en"]),
                                                                         cls=TextPresets.muted_sm))))
    return pagina(
        f"Cambios de {gestiones.codigo(g)}",
        A(UkIcon("arrow-left", height=14, width=14), "Oferta y docentes", href=f"{BASE}?gestion={gid}",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(f"Cambios de {gestiones.codigo(g)}"),
        P("Lo que cambió con el semestre en marcha: materias agregadas o retiradas y docentes agregados, reasignados o "
          "retirados, con su fecha de efecto, su motivo y quién lo registró.", cls=(TextPresets.muted_sm, "mb-4")),
        Card(Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Desde"), fh.Th("Cambio"), fh.Th("Materia"), fh.Th("Docente"),
                                         fh.Th("Motivo"), fh.Th("Registró"))), fh.Tbody(*filas),
                          cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")
             if filas else P("Todavía no hay cambios registrados.", cls="text-sm")),
        usuario=auth, seccion="docencia")


# --- Copiar del año anterior y grilla ----------------------------------------------------------------------

@rt(f"{BASE}/{{gid}}/copiar")
def get(auth, gid: int):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_o_404(gid)
    if error:
        return error
    if not gestiones.edicion_libre(g):
        return _con_motivo(g)
    origen = oferta.mismo_semestre_anio_anterior(g)
    if not origen:
        return Response("No hay gestión del año anterior", status_code=404)
    n = len(oferta.listar(origen["id"]))
    return modal(
        f"Copiar la oferta de {gestiones.codigo(origen)}",
        fh.Form(
            P(f"Se agregan a {gestiones.codigo(g)} los {n} paralelos de {gestiones.codigo(origen)} que aún no están, sin "
              "inscritos. Lo que ya está en la oferta no cambia.", cls="text-sm"),
            fh.Label(fh.Input(type="checkbox", name="con_docentes", value="1", checked=True, cls="uk-checkbox"),
                     Span("Con sus docentes (titulares y auxiliares). Se aplican las mismas reglas que al asignar a mano: "
                          "en verano e invierno, solo titulares.", cls="text-sm"), cls="flex items-start gap-2"),
            Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                Button(UkIcon("copy", height=14, width=14), "Copiar", type="submit", cls=ButtonT.primary),
                cls="flex justify-end gap-2"),
            hx_post=f"{BASE}/{gid}/copiar", hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML", cls="space-y-4"))


@rt(f"{BASE}/{{gid}}/copiar")
def post(auth, sess, gid: int, con_docentes: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_o_404(gid)
    if error:
        return error
    if not gestiones.edicion_libre(g):
        return _con_motivo(g)
    origen = oferta.mismo_semestre_anio_anterior(g)
    if not origen:
        return Response("No hay gestión del año anterior", status_code=404)
    with transaccion():
        r = oferta.copiar(origen, g, con_docentes == "1", auth["id"])
    auditar(auth["id"], "copiar_oferta", "gestion_academica", gid,
            f"de {gestiones.codigo(origen)}: {r['paralelos']} paralelo(s), {r['docentes']} docente(s)")
    add_toast(sess, f"Se copiaron {r['paralelos']} paralelo(s) y {r['docentes']} asignación(es) de docente.", "success")
    for aviso in r["avisos"][:5]:
        add_toast(sess, aviso, "warning")
    return seccion_oferta(g, auth), Div(id=ID_MODAL, hx_swap_oob="true")


def _pagina_grilla(g, auth, errores=()):
    posibles = oferta.docentes_posibles(g)
    opciones = lambda actual: [Option("— Sin titular —", value="")] + [  # noqa: E731
        Option(f"{p['apellidos']}, {p['nombres']}" + ("" if p["con_vinculo"] else " (sin vínculo)"),
               value=str(p["id"]), selected=p["id"] == actual) for p in posibles]
    filas = []
    for o in oferta.listar(g["id"]):
        t = oferta.titular_de(o["id"])
        auxiliares = [f"{d['nombres']} {d['apellidos']}" for d in o["docentes"] if d["rol"] == "auxiliar"]
        filas.append(fh.Tr(fh.Td(o["sigla"], cls="font-mono text-sm whitespace-nowrap"), fh.Td(o["nombre"], cls="text-sm"),
                           fh.Td(o["paralelo"], cls="text-sm"),
                           fh.Td(Select(*opciones(t["usuario_id"] if t else None), name=f"titular_{o['id']}",
                                        cls="uk-select h-8 text-sm w-72 max-w-full", aria_label=f"Titular de {o['sigla']} {o['paralelo']}")),
                           fh.Td(", ".join(auxiliares) or "—", cls="text-xs text-muted-foreground")))
    return pagina(
        f"Grilla de docentes {gestiones.codigo(g)}",
        A(UkIcon("arrow-left", height=14, width=14), "Oferta y docentes", href=f"{BASE}?gestion={g['id']}",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(H2(f"Docentes titulares de {gestiones.codigo(g)}"),
            P("Elija el titular de cada paralelo y guarde una sola vez. Cambiar el titular reemplaza al anterior; los "
              "auxiliares se gestionan en «Oferta y docentes».", cls=TextPresets.muted_sm), cls="mb-4"),
        mensaje_error(*errores),
        Card(fh.Form(
            Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Sigla"), fh.Th("Asignatura"), fh.Th("Paralelo"), fh.Th("Titular"),
                                        fh.Th("Auxiliares"))), fh.Tbody(*filas),
                         cls="uk-table uk-table-divider uk-table-small", data_tabla=f"grilla-{gestiones.codigo(g)}"),
                cls="overflow-x-auto"),
            Div(Button(UkIcon("save", height=14, width=14), "Guardar la grilla", type="submit", cls=ButtonT.primary),
                cls="flex justify-end mt-4 sticky bottom-0 bg-background py-3"),
            method="post", action=f"{BASE}/{g['id']}/grilla") if filas
            else P("Aún no hay paralelos en esta gestión.", cls=TextPresets.muted_sm)),
        usuario=auth, seccion="docencia")


@rt(f"{BASE}/{{gid}}/grilla")
def get(auth, gid: int):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_o_404(gid)
    if error:
        return error
    if not gestiones.edicion_libre(g):
        return _con_motivo(g)
    return _pagina_grilla(g, auth)


@rt(f"{BASE}/{{gid}}/grilla")
async def post(auth, sess, req, gid: int):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_o_404(gid)
    if error:
        return error
    if not gestiones.edicion_libre(g):
        return _con_motivo(g)
    form = await req.form()
    cambios, errores = 0, []
    with transaccion():
        for o in oferta.listar(g["id"]):
            valor = form.get(f"titular_{o['id']}")
            if valor is None:
                continue
            nuevo = int(valor) if str(valor).isdigit() else None
            actual = oferta.titular_de(o["id"])
            if (actual["usuario_id"] if actual else None) == nuevo:
                continue
            e = oferta.fijar_titular(o["id"], nuevo)
            if e:
                errores.append(f"{o['sigla']} {o['paralelo']}: {e[0]}")
            else:
                cambios += 1
    if cambios:
        auditar(auth["id"], "grilla_docentes", "gestion_academica", gid, f"{gestiones.codigo(g)}: {cambios} cambio(s)")
        add_toast(sess, f"{cambios} paralelo(s) actualizado(s).", "success")
    if errores:
        return _pagina_grilla(g, auth, errores)
    return Redirect(f"{BASE}?gestion={gid}")


def _con_motivo(g):
    """Respuesta cuando se intenta editar libremente una gestión que ya no está en planificación."""
    return Response("La gestión está activa: los cambios en la oferta y en los docentes piden motivo y fecha de efecto."
                    if g["estado"] == "activa" else
                    "La gestión está concluida: es historial. Para corregirla, la Dirección de Carrera puede reabrirla.",
                    status_code=409)


def _gestion_o_404(gid):
    g = gestiones.obtener(gid)
    return g, (None if g else Response("No encontrado", status_code=404))


@rt(f"{BASE}/{{gid}}")
def post(auth, gid: int, asignatura: str = "", paralelo: str = "A", inscritos: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_o_404(gid)
    if error:
        return error
    if not gestiones.edicion_libre(g):
        return _con_motivo(g)
    oid, errores = oferta.agregar(gid, asignatura, paralelo, inscritos, auth["id"])
    if not errores:
        o = oferta.obtener(oid)
        auditar(auth["id"], "agregar_oferta", "oferta", oid, f"{gestiones.codigo(g)} {o['sigla']} {o['paralelo']}")
    return seccion_oferta(g, auth, errores)


@rt(f"{BASE}/{{gid}}/troncales")
def post(auth, sess, gid: int):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_o_404(gid)
    if error:
        return error
    if not gestiones.edicion_libre(g):
        return _con_motivo(g)
    n = oferta.ofertar_troncales(g, auth["id"])
    auditar(auth["id"], "ofertar_troncales", "gestion_academica", gid, f"{gestiones.codigo(g)}: {n}")
    add_toast(sess, f"{n} troncal(es) agregada(s)." if n else "Todas las troncales ya estaban en la oferta.",
              "success" if n else "info")
    return seccion_oferta(g, auth)


@rt(f"{BASE}/{{oid}}")
def delete(auth, oid: int):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    o = oferta.obtener(oid)
    if not o:
        return Response("No encontrado", status_code=404)
    g = gestiones.obtener(o["gestion_id"])
    if not gestiones.edicion_libre(g):
        return _con_motivo(g)
    oferta.quitar(oid)
    auditar(auth["id"], "quitar_oferta", "oferta", oid, f"{gestiones.codigo(g)} {o['sigla']} {o['paralelo']}")
    return seccion_oferta(g, auth)


@rt(f"{BASE}/{{oid}}/docentes")
def post(auth, sess, oid: int, usuario: str = "", rol: str = "titular"):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    o = oferta.obtener(oid)
    if not o:
        return Response("No encontrado", status_code=404)
    g = gestiones.obtener(o["gestion_id"])
    if not gestiones.edicion_libre(g):
        return _con_motivo(g)
    errores = oferta.asignar(oid, int(usuario) if usuario.isdigit() else 0, rol)
    if not errores:
        auditar(auth["id"], "asignar_docente", "oferta", oid, f"{gestiones.codigo(g)} {o['sigla']} {o['paralelo']}: "
                                                              f"usuario {usuario} ({rol})")
        add_toast(sess, "Docente asignado.", "success")
    return seccion_oferta(g, auth, errores)


@rt(f"{BASE}/docentes/{{did}}")
def delete(auth, did: int):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    d0 = get_db().q("SELECT * FROM oferta_docente WHERE id = ?", [did])
    if not d0:
        return Response("No encontrado", status_code=404)
    o = oferta.obtener(d0[0]["oferta_id"])
    g = gestiones.obtener(o["gestion_id"])
    if not gestiones.edicion_libre(g):
        return _con_motivo(g)
    d = oferta.quitar_docente(did)
    auditar(auth["id"], "quitar_docente", "oferta", o["id"], f"{gestiones.codigo(g)} {o['sigla']}: usuario {d['usuario_id']}")
    return seccion_oferta(g, auth)


# --- Gestiones ---------------------------------------------------------------------------------------------

def estado_insignia(g):
    return insignia(gestiones.ESTADOS[g["estado"]], gestiones.TONOS[g["estado"]], icono=gestiones.ICONOS[g["estado"]])


def seccion_gestiones(auth, errores=()):
    puede = _puede(auth)
    filas = []
    for g in gestiones.listar():
        editable = puede and g["estado"] != "concluida"
        fechas = fh.Form(Input(type="date", name="inicio", value=g["fecha_inicio"], cls="uk-input h-8 w-40",
                               aria_label="Inicio"),
                         Input(type="date", name="fin", value=g["fecha_fin"], cls="uk-input h-8 w-40", aria_label="Término"),
                         Button("Guardar", type="submit", cls=(ButtonT.ghost, ButtonT.sm)),
                         hx_put=f"/docencia/gestiones/{g['id']}", hx_target="#gestiones", hx_swap="outerHTML",
                         cls="flex flex-wrap gap-2") if editable else Span(formato.periodo(g["fecha_inicio"], g["fecha_fin"]),
                                                                           cls="text-sm")
        planificar = A(UkIcon("clipboard-check", height=14, width=14),
                       "Planificar" if g["estado"] == "planificacion" else "Ver la planificación",
                       href=f"/docencia/preparacion?semestre={gestiones.codigo(g)}",
                       cls="inline-flex items-center gap-1 text-sm text-primary hover:underline whitespace-nowrap")
        borrar = Button(UkIcon("trash-2", height=14, width=14), hx_delete=f"/docencia/gestiones/{g['id']}",
                        hx_confirm=f"¿Borrar la gestión {gestiones.codigo(g)} con toda su oferta y docentes? No se puede "
                                   "deshacer.", hx_target="#gestiones", hx_swap="outerHTML",
                        cls=(ButtonT.ghost, ButtonT.xs, "text-destructive"),
                        aria_label=f"Borrar la gestión {gestiones.codigo(g)}") \
            if puede and g["estado"] == "planificacion" else ""
        filas.append(fh.Tr(fh.Td(A(gestiones.codigo(g), href=f"{BASE}?gestion={g['id']}",
                                   cls="font-mono hover:underline")),
                           fh.Td(gestiones.nombre(g), cls="text-sm"), fh.Td(estado_insignia(g)), fh.Td(fechas),
                           fh.Td(planificar, borrar, cls="flex items-center gap-2")))
    crear = Div(
        fh.Form(Input(name="anio", placeholder="Año", cls="uk-input w-28", inputmode="numeric", aria_label="Año"),
                Button(UkIcon("plus", height=14, width=14), "Crear las gestiones del año", type="submit",
                       cls=ButtonT.primary),
                hx_post="/docencia/gestiones", hx_target="#gestiones", hx_swap="outerHTML", cls="flex gap-2"),
        fh.Details(fh.Summary("Crear una sola gestión", cls="text-sm cursor-pointer text-primary"),
                   fh.Form(Input(name="anio", placeholder="Año", cls="uk-input w-28", inputmode="numeric",
                                 aria_label="Año de la gestión"),
                           Select(*[Option(f"{t} · {n}", value=t) for t, n in gestiones.TIPOS.items()], name="tipo",
                                  aria_label="Tipo de gestión", cls="uk-select w-56"),
                           fh.Label(Input(type="checkbox", name="concluida", value="1"),
                                    Span("Ya terminó: crearla como concluida, para cargar su historial", cls="text-sm"),
                                    cls="flex items-center gap-2"),
                           Button("Crear", type="submit", cls=ButtonT.default),
                           hx_post="/docencia/gestiones/una", hx_target="#gestiones", hx_swap="outerHTML",
                           cls="flex flex-wrap items-center gap-3 mt-2"), cls="mt-3"),
        cls="mb-4") if puede else ""
    return Div(mensaje_error(*errores), crear,
               Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Código"), fh.Th("Gestión"), fh.Th("Estado"), fh.Th("Fechas"),
                                           fh.Th(Span("Acciones", cls="sr-only")))), fh.Tbody(*filas),
                            cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")
               if filas else P("Sin gestiones registradas.", cls=TextPresets.muted_sm),
               id="gestiones")


@rt("/docencia/gestiones")
def get(auth):
    return pagina("Gestiones académicas", H2("Gestiones académicas"),
                  P("Semestres (I, II) y cursos de temporada (INV en julio; VER en enero del año siguiente, que se "
                    "cuenta con la gestión anterior). Una gestión nace en planificación: se arma su oferta y se asignan "
                    "los docentes (en «Planificar») hasta que la Dirección de Carrera la active; mientras está en "
                    "planificación se puede borrar. Las fechas propuestas se ajustan al calendario aprobado. Al crear "
                    "las gestiones, los semestres se ofertan con las troncales de las licenciaturas (paralelo A).",
                    cls=(TextPresets.muted_sm, "mb-6")),
                  seccion_gestiones(auth), usuario=auth, seccion="docencia")


@rt("/docencia/gestiones")
def post(auth, sess, anio: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    if not anio.isdigit() or not 2000 <= int(anio) <= 2100:
        return seccion_gestiones(auth, ["Indique un año entre 2000 y 2100."])
    with transaccion():
        creadas = gestiones.crear_anio_con_nuevas(int(anio))
        n = sum(oferta.ofertar_troncales(g, auth["id"]) for g, nueva in creadas if nueva)
    auditar(auth["id"], "crear_gestiones", "gestion_academica", None, f"{anio}: {n} troncal(es) ofertada(s)")
    if n:
        add_toast(sess, f"Gestiones {anio} creadas; los semestres se ofertaron con las troncales de las "
                        "licenciaturas. Agregue las electivas y asigne los docentes.", "success")
    return seccion_gestiones(auth)


@rt("/docencia/gestiones/una")
def post(auth, sess, anio: str = "", tipo: str = "", concluida: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    if not anio.isdigit():
        return seccion_gestiones(auth, ["Indique el año de la gestión."])
    g, error = gestiones.crear(int(anio), tipo, auth["id"], concluida=bool(concluida))
    if error:
        return seccion_gestiones(auth, [error])
    n = 0
    if g["estado"] == "planificacion" and g["tipo"] not in oferta.TEMPORADA:
        n = oferta.ofertar_troncales(g, auth["id"])
    add_toast(sess, f"Gestión {gestiones.codigo(g)} creada" + (" como concluida (historial)." if concluida else
              (f" con {n} troncales ofertadas." if n else ".")), "success")
    return seccion_gestiones(auth)


@rt("/docencia/gestiones/{gid}")
def delete(auth, sess, gid: int):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_o_404(gid)
    if error:
        return error
    e = gestiones.eliminar(gid, auth["id"])
    if not e:
        add_toast(sess, f"Gestión {gestiones.codigo(g)} borrada.", "success")
    return seccion_gestiones(auth, [e] if e else [])


@rt("/docencia/gestiones/{gid}")
def put(auth, gid: int, inicio: str = "", fin: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_o_404(gid)
    if error:
        return error
    e = gestiones.actualizar_fechas(gid, inicio, fin)
    if not e:
        auditar(auth["id"], "fechas_gestion", "gestion_academica", gid, f"{gestiones.codigo(g)}: {inicio} a {fin}")
    return seccion_gestiones(auth, [e] if e else [])


# --- Importación de la oferta de gestiones pasadas ------------------------------------------------------

def _form_importar(errores=()):
    return Div(
        mensaje_error(*errores),
        P("Una fila por docente de cada paralelo: ", Code("gestion"), " (I-2021, INV-2021, II-2021, VER-2021), ",
          Code("sigla"), " y, si quiere, ", Code("paralelo"), " (vacío = A), ", Code("inscritos"), ", ",
          Code("email"), " del docente (vacío si no tuvo) y ", Code("rol"), " (titular o auxiliar; vacío = titular). "
          "Cada materia de un titular en un semestre cuenta 32 h/mes de carga.", cls="text-sm"),
        P("La oferta de cada gestión del archivo se reemplaza por la del archivo; las demás no cambian. Una gestión "
          "con errores no se importa. Los docentes deben estar registrados (aunque sea sin acceso). Primero verá una "
          "vista previa.", cls=TextPresets.muted_sm),
        A(UkIcon("download", height=14, width=14), "Descargar plantilla", href=f"{BASE}/plantilla",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline"),
        fh.Form(Input(type="file", name="archivo", accept=".csv,text/csv", required=True, aria_label="Archivo CSV"),
                Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                    Button("Revisar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
                hx_post=f"{BASE}/importar/revisar", hx_encoding="multipart/form-data", hx_target=f"#{ID_MODAL}",
                cls="space-y-4"),
        cls="space-y-4")


@rt(f"{BASE}/importar")
def get(auth):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    return modal("Importar oferta", _form_importar(), ancho="max-w-2xl")


@rt(f"{BASE}/plantilla")
def get(auth):
    return Response(importar_oferta.PLANTILLA.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-oferta.csv"'})


@rt(f"{BASE}/importar/revisar")
async def post(auth, archivo: UploadFile = None):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    if archivo is None or not archivo.filename:
        return modal("Importar oferta", _form_importar(["Seleccione un archivo."]), ancho="max-w-2xl")
    contenido = await archivo.read(importar_oferta.MAX_BYTES + 1)
    lista, errores = importar_oferta.leer(contenido)
    if not lista:
        return modal("Importar oferta", _form_importar(errores), ancho="max-w-2xl")
    listas = [g for g in lista if not g["errores"] and g["anio"] is not None]
    filas = []
    for g in lista:
        paralelos = len(g["paralelos"])
        docentes = sum(len(p["docentes"]) for p in g["paralelos"].values())
        sin_doc = sum(not p["docentes"] for p in g["paralelos"].values())
        if g["errores"]:
            resultado = Div(insignia("No se importa", "rojo", icono="circle-x"),
                            *[P(e, cls="text-sm") for e in g["errores"][:8]],
                            P(f"… y {len(g['errores']) - 8} más.", cls=TextPresets.muted_sm) if len(g["errores"]) > 8
                            else "")
        else:
            resultado = Div(Span(("Reemplaza " + str(g["actuales"]) + " paralelo(s) actual(es)") if g["actuales"] else
                                 ("Gestión nueva: se crearán las del año" if not g["existe"] else "Sin oferta previa"),
                                 cls="text-sm"),
                            *[P(a, cls="text-sm text-amber-700 dark:text-amber-400") for a in g["avisos"]])
        filas.append(fh.Tr(fh.Td(g["codigo"], cls="font-mono whitespace-nowrap"),
                           fh.Td(f"{paralelos} paralelo(s), {docentes} docente(s)" +
                                 (f", {sin_doc} sin docente" if sin_doc else ""), cls="text-sm"),
                           fh.Td(resultado)))
    return modal(
        "Vista previa de la oferta",
        P(f"{len(listas)} gestión(es) se importarán · {len(lista) - len(listas)} con errores, se omiten.",
          cls="text-sm font-medium mb-3"),
        Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Gestión"), fh.Th("Contenido"), fh.Th("Resultado"))), fh.Tbody(*filas),
                     cls="uk-table uk-table-divider uk-table-small"),
            cls="max-h-96 overflow-y-auto border border-border rounded-md mb-4"),
        fh.Form(Input(type="hidden", name="contenido", value=base64.b64encode(contenido).decode()),
                Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
                    Button(f"Importar {len(listas)} gestión(es)", type="submit", cls=ButtonT.primary,
                           disabled=not listas), cls="flex justify-end gap-2"),
                hx_post=f"{BASE}/importar/confirmar", hx_target=f"#{ID_MODAL}"),
        ancho="max-w-4xl")


@rt(f"{BASE}/importar/confirmar")
def post(auth, sess, contenido: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    try:
        datos = base64.b64decode(contenido, validate=True)
    except ValueError:
        return modal("Importar oferta", _form_importar(["No se pudo leer el archivo. Súbalo otra vez."]))
    lista, _ = importar_oferta.leer(datos)
    n = importar_oferta.aplicar(lista, auth["id"])
    add_toast(sess, f"Oferta importada: {n} gestión(es).", "success")
    ultima = next((gestiones.por_codigo(g["codigo"]) for g in reversed(lista) if not g["errores"] and g["anio"]), None)
    return Redirect(f"{BASE}?gestion={ultima['id']}" if ultima else BASE)
