"""Oferta por gestión y asignación docente; gestiones académicas. La consultan todos; la editan la
Dirección de Carrera y la Coordinación académica (acción `gestionar_oferta`)."""
import base64

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Code, Datalist, Div, Input, Li, Option, P, Redirect, Response, Select, Span,
                             Ul, UploadFile)
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, TextPresets, UkIcon

from app.academico import gestiones, importar_oferta, oferta
from app.academico.componentes import pestanas
from app.comun import permisos
from app.comun.componentes.layout import ID_MODAL, JS_CERRAR, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar, transaccion

rt = APIRouter()
BASE = "/docencia/oferta"
ID_OFERTA = "oferta-gestion"


def _puede(auth):
    return permisos.puede(auth, "gestionar_oferta")


def _selector(g):
    return Select(*[Option(f"{gestiones.codigo(x)} · {gestiones.TIPOS[x['tipo']]}", value=str(x["id"]),
                           selected=x["id"] == g["id"]) for x in gestiones.listar()],
                  name="gestion", aria_label="Gestión", cls="uk-select w-72",
                  onchange=f"location.href='{BASE}?gestion='+this.value")


def _docente(d, g, puede):
    aviso = Span(" · sin vínculo con la Carrera", cls="text-xs text-amber-700",
                 title="No tiene vínculo vigente con la Carrera al inicio de la gestión") \
        if oferta.sin_vinculo_con_la_carrera(d["usuario_id"], g) else ""
    quitar = fh.Button(UkIcon("x", height=12, width=12), type="button", aria_label="Quitar docente",
                       cls="p-0.5 rounded hover:text-red-600", hx_delete=f"{BASE}/docentes/{d['id']}",
                       hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML",
                       hx_confirm=f"¿Quitar a {d['nombres']} {d['apellidos']} de este paralelo?") if puede else ""
    carga = (f" · {oferta.HORAS_POR_MATERIA} h/mes" if d["rol"] == "titular" and g["tipo"] not in oferta.TEMPORADA
             else "")
    return Li(Span(f"{d['nombres']} {d['apellidos']}", cls="text-sm"),
              Span(f" · {oferta.ROLES[d['rol']].lower()}{carga}", cls=TextPresets.muted_sm),
              aviso, quitar, cls="flex items-center gap-1")


def _form_docente(o, g):
    return fh.Details(fh.Summary("+ Asignar docente", cls="cursor-pointer text-xs text-primary mt-1"), fh.Form(
        Select(Option("Docente…", value=""),
               *[Option(f"{p['apellidos']}, {p['nombres']}" + ("" if p["con_vinculo"] else " (sin vínculo con la Carrera)"),
                        value=str(p["id"])) for p in oferta.docentes_posibles(g)],
               name="usuario", cls="uk-select h-8 text-sm w-64", aria_label="Docente", required=True),
        Select(*[Option(t, value=k) for k, t in oferta.ROLES.items()], name="rol", cls="uk-select h-8 text-sm w-28",
               aria_label="Rol"),
        Button("Asignar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
        hx_post=f"{BASE}/{o['id']}/docentes", hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML",
        cls="flex flex-wrap gap-2 mt-2"))


def seccion_oferta(g, auth, errores=()):
    puede = _puede(auth)
    troncales = {a["id"] for a in oferta.troncales(g["anio"])}
    filas = []
    for o in oferta.listar(g["id"]):
        quitar = fh.Button(UkIcon("trash-2", height=14, width=14), type="button", aria_label="Quitar de la oferta",
                           cls="p-1 rounded hover:bg-muted hover:text-red-600", hx_delete=f"{BASE}/{o['id']}",
                           hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML",
                           hx_confirm=f"¿Quitar {o['sigla']} paralelo {o['paralelo']} de la oferta?") if puede else ""
        filas.append(fh.Tr(
            fh.Td(o["sigla"], cls="font-mono text-sm whitespace-nowrap"),
            fh.Td(Div(o["nombre"], cls="text-sm"),
                  Div(", ".join(oferta.programas_de(o["asignatura_id"]))
                      + (" · troncal" if o["asignatura_id"] in troncales else ""), cls=TextPresets.muted_sm)),
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
        cls="space-y-2 mb-4") if puede else ""
    total = sum(len(o["docentes"]) == 0 for o in oferta.listar(g["id"]))
    return Div(
        agregar,
        P(f"{len(filas)} paralelo(s)" + (f" · {total} sin docente" if total else ""), cls=(TextPresets.muted_sm, "mb-2")),
        Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Sigla"), fh.Th("Asignatura"), fh.Th("Paralelo"), fh.Th("Inscritos"),
                                    fh.Th("Docentes"), fh.Th(""))), fh.Tbody(*filas),
                     cls="uk-table uk-table-divider uk-table-small", data_tabla=f"oferta-{gestiones.codigo(g)}"),
            cls="overflow-x-auto")
        if filas else P("Aún no hay asignaturas en la oferta de esta gestión.", cls=TextPresets.muted_sm),
        id=ID_OFERTA)


@rt(BASE)
def get(auth, gestion: str = ""):
    g = gestiones.obtener(int(gestion)) if gestion.isdigit() else gestiones.actual()
    if not g:
        return pagina("Oferta y docentes", pestanas("oferta", auth),
                      P("Todavía no hay gestiones registradas. ", A("Crear las gestiones de un año", href="/docencia/gestiones",
                                                                    cls="text-primary hover:underline"),
                        cls="text-sm"), usuario=auth, seccion="docencia")
    temporada = P("Curso de temporada: solo lo dictan docentes titulares y no suma a la carga horaria del semestre "
                  "(cuenta como docencia dictada).", cls="text-sm text-amber-700 mb-4") \
        if g["tipo"] in oferta.TEMPORADA else ""
    return pagina(
        "Oferta y docentes",
        pestanas("oferta", auth),
        Div(Div(H2(gestiones.codigo(g)), P(f"{gestiones.nombre(g)} · del {g['fecha_inicio']} al {g['fecha_fin']}",
                                           cls=TextPresets.muted_sm)),
            Div(_selector(g),
                Button(UkIcon("list-plus", height=16, width=16), "Agregar las troncales", cls=ButtonT.default,
                       hx_post=f"{BASE}/{g['id']}/troncales", hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML",
                       hx_confirm="¿Agregar a la oferta las troncales de las licenciaturas que aún no están "
                                  "(paralelo A)?") if _puede(auth) and g["tipo"] not in oferta.TEMPORADA else "",
                Button(UkIcon("file-up", height=16, width=16), "Importar CSV", cls=ButtonT.default,
                       hx_get=f"{BASE}/importar", hx_target=f"#{ID_MODAL}") if _puede(auth) else "",
                cls="flex flex-wrap gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        temporada,
        seccion_oferta(g, auth),
        usuario=auth, seccion="docencia")


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
    oferta.quitar(oid)
    g = gestiones.obtener(o["gestion_id"])
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
    d = oferta.quitar_docente(did)
    if not d:
        return Response("No encontrado", status_code=404)
    o = oferta.obtener(d["oferta_id"])
    g = gestiones.obtener(o["gestion_id"])
    auditar(auth["id"], "quitar_docente", "oferta", o["id"], f"{gestiones.codigo(g)} {o['sigla']}: usuario {d['usuario_id']}")
    return seccion_oferta(g, auth)


# --- Gestiones ---------------------------------------------------------------------------------------------

def seccion_gestiones(auth, errores=()):
    puede = _puede(auth)
    filas = []
    for g in gestiones.listar():
        fechas = fh.Form(Input(type="date", name="inicio", value=g["fecha_inicio"], cls="uk-input h-8 w-40",
                               aria_label="Inicio"),
                         Input(type="date", name="fin", value=g["fecha_fin"], cls="uk-input h-8 w-40", aria_label="Término"),
                         Button("Guardar", type="submit", cls=(ButtonT.ghost, ButtonT.sm)),
                         hx_put=f"/docencia/gestiones/{g['id']}", hx_target="#gestiones", hx_swap="outerHTML",
                         cls="flex flex-wrap gap-2") if puede else Span(f"{g['fecha_inicio']} a {g['fecha_fin']}",
                                                                        cls="text-sm")
        filas.append(fh.Tr(fh.Td(A(gestiones.codigo(g), href=f"{BASE}?gestion={g['id']}",
                                   cls="font-mono hover:underline")),
                           fh.Td(gestiones.nombre(g), cls="text-sm"), fh.Td(fechas)))
    crear = fh.Form(Input(name="anio", placeholder="Año", cls="uk-input w-28", inputmode="numeric", aria_label="Año"),
                    Button(UkIcon("plus", height=14, width=14), "Crear las gestiones del año", type="submit",
                           cls=ButtonT.primary),
                    hx_post="/docencia/gestiones", hx_target="#gestiones", hx_swap="outerHTML",
                    cls="flex gap-2 mb-4") if puede else ""
    return Div(mensaje_error(*errores), crear,
               Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Código"), fh.Th("Gestión"), fh.Th("Fechas"))), fh.Tbody(*filas),
                            cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")
               if filas else P("Sin gestiones registradas.", cls=TextPresets.muted_sm),
               id="gestiones")


@rt("/docencia/gestiones")
def get(auth):
    return pagina("Gestiones académicas", pestanas("gestiones", auth), H2("Gestiones académicas"),
                  P("Semestres (I, II) y cursos de temporada (INV en julio; VER en enero del año siguiente, que se "
                    "cuenta con la gestión anterior). Las fechas propuestas se ajustan al calendario aprobado. Al "
                    "crear las gestiones, los semestres se ofertan con las troncales de las licenciaturas "
                    "(paralelo A); las electivas y los docentes se agregan en «Oferta y docentes».",
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
                Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
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
                            *[P(a, cls="text-sm text-amber-700") for a in g["avisos"]])
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
                Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
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
