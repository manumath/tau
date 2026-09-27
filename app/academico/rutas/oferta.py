"""Oferta por gestión y asignación docente; gestiones académicas. La consultan todos; la editan la
Dirección de Carrera y la Coordinación académica (acción `gestionar_oferta`)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Datalist, Div, Input, Li, Option, P, Response, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, TextPresets, UkIcon

from app.academico import gestiones, oferta
from app.academico.componentes import pestanas
from app.comun import permisos
from app.comun.componentes.layout import mensaje_error, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar

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
    return Li(Span(f"{d['nombres']} {d['apellidos']}", cls="text-sm"),
              Span(f" · {oferta.ROLES[d['rol']].lower()} · {d['horas_semanales']} h/sem", cls=TextPresets.muted_sm),
              aviso, quitar, cls="flex items-center gap-1")


def _form_docente(o, g):
    sugeridas = oferta.horas_sugeridas(o["asignatura_id"])
    return fh.Details(fh.Summary("+ Asignar docente", cls="cursor-pointer text-xs text-primary mt-1"), fh.Form(
        Select(Option("Docente…", value=""),
               *[Option(f"{p['apellidos']}, {p['nombres']}" + ("" if p["con_vinculo"] else " (sin vínculo con la Carrera)"),
                        value=str(p["id"])) for p in oferta.docentes_posibles(g)],
               name="usuario", cls="uk-select h-8 text-sm w-64", aria_label="Docente", required=True),
        Select(*[Option(t, value=k) for k, t in oferta.ROLES.items()], name="rol", cls="uk-select h-8 text-sm w-28",
               aria_label="Rol"),
        Input(name="horas", value=str(sugeridas or ""), cls="uk-input h-8 text-sm w-20", aria_label="Horas semanales",
              placeholder="h/sem", inputmode="numeric", title="Horas semanales (sugeridas: las del plan)"),
        Button("Asignar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
        hx_post=f"{BASE}/{o['id']}/docentes", hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML",
        cls="flex flex-wrap gap-2 mt-2"))


def seccion_oferta(g, auth, errores=()):
    puede = _puede(auth)
    filas = []
    for o in oferta.listar(g["id"]):
        quitar = fh.Button(UkIcon("trash-2", height=14, width=14), type="button", aria_label="Quitar de la oferta",
                           cls="p-1 rounded hover:bg-muted hover:text-red-600", hx_delete=f"{BASE}/{o['id']}",
                           hx_target=f"#{ID_OFERTA}", hx_swap="outerHTML",
                           hx_confirm=f"¿Quitar {o['sigla']} paralelo {o['paralelo']} de la oferta?") if puede else ""
        filas.append(fh.Tr(
            fh.Td(o["sigla"], cls="font-mono text-sm whitespace-nowrap"),
            fh.Td(Div(o["nombre"], cls="text-sm"),
                  Div(", ".join(oferta.programas_de(o["asignatura_id"])), cls=TextPresets.muted_sm)),
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
                     cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")
        if filas else P("Aún no hay asignaturas en la oferta de esta gestión.", cls=TextPresets.muted_sm),
        id=ID_OFERTA)


@rt(BASE)
def get(auth, gestion: str = ""):
    g = gestiones.obtener(int(gestion)) if gestion.isdigit() else gestiones.actual()
    if not g:
        return pagina("Oferta y docentes", pestanas("oferta"),
                      P("Todavía no hay gestiones registradas. ", A("Crear las gestiones de un año", href="/docencia/gestiones",
                                                                    cls="text-primary hover:underline"),
                        cls="text-sm"), usuario=auth, seccion="docencia")
    return pagina(
        "Oferta y docentes",
        pestanas("oferta"),
        Div(Div(H2(gestiones.codigo(g)), P(f"{gestiones.nombre(g)} · del {g['fecha_inicio']} al {g['fecha_fin']}",
                                           cls=TextPresets.muted_sm)),
            _selector(g), cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
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
def post(auth, sess, oid: int, usuario: str = "", rol: str = "titular", horas: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    o = oferta.obtener(oid)
    if not o:
        return Response("No encontrado", status_code=404)
    g = gestiones.obtener(o["gestion_id"])
    errores = oferta.asignar(oid, int(usuario) if usuario.isdigit() else 0, rol, horas)
    if not errores:
        auditar(auth["id"], "asignar_docente", "oferta", oid, f"{gestiones.codigo(g)} {o['sigla']} {o['paralelo']}: "
                                                              f"usuario {usuario}, {horas} h")
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
    return pagina("Gestiones académicas", pestanas("gestiones"), H2("Gestiones académicas"),
                  P("Semestres (I, II) y cursos de temporada (INV en julio; VER en enero del año siguiente, que se "
                    "cuenta con la gestión anterior). Las fechas propuestas se ajustan al calendario aprobado.",
                    cls=(TextPresets.muted_sm, "mb-6")),
                  seccion_gestiones(auth), usuario=auth, seccion="docencia")


@rt("/docencia/gestiones")
def post(auth, anio: str = ""):
    if not _puede(auth):
        return Response("No autorizado", status_code=403)
    if not anio.isdigit() or not 2000 <= int(anio) <= 2100:
        return seccion_gestiones(auth, ["Indique un año entre 2000 y 2100."])
    gestiones.crear_anio(int(anio))
    auditar(auth["id"], "crear_gestiones", "gestion_academica", None, anio)
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
