"""Programa analítico (PLAN §68, etapa 3): el titular lo escribe y publica por versiones; cualquiera del personal lee lo publicado
y quien arma la oferta (`gestionar_oferta`) ve la cobertura. El estudiante lo ve desde su plan (`rutas/mi_plan.py`)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Option, P, Redirect, Response, Select, Span
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import gestiones, programas
from app.comun import formato, permisos
from app.comun.componentes.layout import campo, mensaje_error, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import get_db

rt = APIRouter()
BASE = "/docencia/programas"


def _asignatura(aid: int) -> dict | None:
    f = get_db().q("SELECT * FROM asignatura WHERE id = ?", [aid])
    return f[0] if f else None


def lectura(p: dict):
    """Un programa publicado, para leer (lo usan el personal y el estudiante)."""
    return Div(*[Card(H3(t, cls="text-base font-semibold"),
                      *[P(linea, cls="text-sm mt-1") for linea in p[k].splitlines() if linea.strip()])
                 for k, t in programas.CAMPOS.items() if p.get(k)], cls="space-y-4")


@rt(BASE)
def get(auth):
    mias = programas.materias_de(auth["id"])
    filas = [fh.Tr(fh.Td(m["gestion"], cls="text-sm whitespace-nowrap"),
                   fh.Td(Span(m["sigla"], cls="font-mono text-sm"), Span(f" {m['nombre']}", cls="text-sm")),
                   fh.Td(insignia(f"Publicado · versión {m['version']}", "verde") if m["version"]
                         else insignia("Sin publicar", "ambar", icono="circle-alert"),
                         insignia("Borrador", "gris") if m["borrador"] else ""),
                   fh.Td(A("Escribir" if not m["version"] else "Editar", href=f"{BASE}/{m['asignatura_id']}/{m['gestion_id']}",
                           cls="text-sm text-primary hover:underline"))) for m in mias]
    return pagina(
        "Mis programas analíticos", H2("Mis programas analíticos"),
        P("El programa de cada materia que dicta como titular: objetivos, contenido, metodología, evaluación y bibliografía. Al "
          "publicarlo, sus estudiantes lo ven en su plan de estudios. Cada publicación es una versión que no se edita.",
          cls=(TextPresets.muted_sm, "mb-4 max-w-3xl")),
        Card(Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Gestión"), fh.Th("Materia"), fh.Th("Estado"), fh.Th(""))), fh.Tbody(*filas),
                          cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")) if filas
        else Card(P("No es titular de ninguna materia en una gestión vigente o en planificación.", cls="text-sm")),
        P(A("Cobertura de la oferta", href=f"{BASE}/cobertura", cls="text-sm text-primary hover:underline"), cls="mt-4")
        if permisos.puede(auth, "gestionar_oferta") else "", usuario=auth, seccion="docencia")


@rt(f"{BASE}/cobertura")
def get(auth, gestion: str = ""):
    if not permisos.puede(auth, "gestionar_oferta"):
        return Response("No autorizado", status_code=403)
    lista = [g for g in gestiones.listar() if g["estado"] != "concluida"][::-1] or gestiones.listar()
    g = next((x for x in lista if str(x["id"]) == gestion), None) or (lista[0] if lista else None)
    if not g:
        return pagina("Programas analíticos", Card(P("Aún no hay gestiones.", cls="text-sm")), usuario=auth, seccion="docencia")
    filas = programas.cobertura(g["id"])
    con = sum(1 for f in filas if f["version"])
    selector = Select(*[Option(gestiones.codigo(x), value=str(x["id"]), selected=x["id"] == g["id"]) for x in lista],
                      aria_label="Gestión", cls="uk-select w-40", data_navegar=f"{BASE}/cobertura?gestion=")
    return pagina(
        "Programas analíticos",
        Div(Div(H2("Programas analíticos"), P(f"{con} de {len(filas)} asignaturas de {gestiones.codigo(g)} tienen su programa "
                                              "publicado.", cls=TextPresets.muted_sm)),
            selector, cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Card(Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Asignatura"), fh.Th("Titular"), fh.Th("Programa"))), fh.Tbody(*[
            fh.Tr(fh.Td(Span(f["sigla"], cls="font-mono text-sm"), Span(f" {f['nombre']}", cls="text-sm")),
                  fh.Td(f["titulares"] or "—", cls="text-sm"),
                  fh.Td(A(f"Versión {f['version']} · {formato.fecha_hora(f['publicado_en'])}",
                          href=f"{BASE}/{f['asignatura_id']}/{g['id']}", cls="text-sm text-primary hover:underline")
                        if f["version"] else insignia("Sin publicar", "ambar", icono="circle-alert"))) for f in filas]),
            cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")) if filas
        else Card(P("Esta gestión aún no tiene oferta.", cls="text-sm")), usuario=auth, seccion="docencia")


def _formulario(a: dict, g: dict, b: dict | None, errores=()):
    datos = b or {}
    base = f"{BASE}/{a['id']}/{g['id']}"
    return fh.Form(
        mensaje_error(*errores),
        *[Div(campo(t + (" *" if k in programas.OBLIGATORIOS else ""),
                    fh.Textarea(datos.get(k) or "", name=k, rows=6 if k in ("contenido", "bibliografia") else 4,
                                maxlength=programas.MAX, cls="uk-textarea")),
              P(programas.AYUDAS[k], cls=TextPresets.muted_sm)) for k, t in programas.CAMPOS.items()],
        Div(Button(UkIcon("save", height=14, width=14), "Guardar borrador", type="submit", cls=ButtonT.default,
                   formaction=base),
            Button(UkIcon("send", height=14, width=14), "Guardar y publicar", type="submit", cls=ButtonT.primary,
                   formaction=f"{base}/publicar"),
            Button("Descartar el borrador", type="submit", cls=ButtonT.ghost, formaction=f"{base}/descartar",
                   hx_confirm="¿Descartar el borrador? No se puede deshacer.") if b else "",
            cls="flex flex-wrap gap-2"),
        method="post", action=base, cls="space-y-4")


@rt(f"{BASE}/{{aid}}/{{gid}}")
def get(auth, aid: int, gid: int, errores: str = ""):
    a, g = _asignatura(aid), gestiones.obtener(gid)
    if not a or not g:
        return Response("No encontrado", status_code=404)
    puede = programas.puede_editar(auth["id"], aid, gid) is None
    titulo = f"{a['sigla']} · {a['nombre']} · {gestiones.codigo(g)}"
    pub = programas.publicado(aid, gid)
    if puede:
        b = programas.borrador(aid, gid)
        v = programas.vigente(aid)
        avisos = [P("Es una versión nueva: lo que publicó antes se conserva.", cls=(TextPresets.muted_sm, "mb-3"))] if pub else []
        partir = fh.Form(Button(UkIcon("copy", height=14, width=14), "Partir del último programa publicado de la materia",
                                type="submit", cls=(ButtonT.default, ButtonT.sm)), method="post", action=f"{BASE}/{aid}/{gid}/partir",
                         cls="mb-4") if not b and v else ""
        return pagina(titulo, A(UkIcon("arrow-left", height=14, width=14), "Mis programas", href=BASE,
                                cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
                      H2("Programa analítico"), P(titulo, cls=(TextPresets.muted_sm, "mb-2")), *avisos, partir,
                      _formulario(a, g, b, [e for e in errores.split("|") if e]), usuario=auth, seccion="docencia")
    if not pub:
        return Response("Esta materia aún no tiene un programa publicado.", status_code=404)
    return pagina(titulo, A(UkIcon("arrow-left", height=14, width=14), "Programas", href=BASE,
                            cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
                  H2("Programa analítico"),
                  P(f"{titulo} · versión {pub['version']}, publicada el {formato.fecha_hora(pub['publicado_en'])} por "
                    f"{pub['nombres']} {pub['apellidos']}.", cls=(TextPresets.muted_sm, "mb-4")), lectura(pub),
                  usuario=auth, seccion="docencia")


def _volver(g_id, aid, errores, sess, ok, quedarse=True):
    if errores:
        return Redirect(f"{BASE}/{aid}/{g_id}?errores={'|'.join(errores)}")
    add_toast(sess, ok, "success")
    return Redirect(f"{BASE}/{aid}/{g_id}" if quedarse else BASE)


@rt(f"{BASE}/{{aid}}/{{gid}}")
async def post(auth, sess, aid: int, gid: int, req):
    f = await req.form()
    return _volver(gid, aid, programas.guardar(aid, gid, auth["id"], dict(f)), sess, "Borrador guardado.")


@rt(f"{BASE}/{{aid}}/{{gid}}/publicar")
async def post(auth, sess, aid: int, gid: int, req):
    f = await req.form()
    errores = programas.guardar(aid, gid, auth["id"], dict(f)) or programas.publicar(aid, gid, auth["id"])
    return _volver(gid, aid, errores, sess, "Programa publicado.", quedarse=False)


@rt(f"{BASE}/{{aid}}/{{gid}}/partir")
def post(auth, sess, aid: int, gid: int):
    return _volver(gid, aid, programas.partir_de_la_vigente(aid, gid, auth["id"]), sess, "Borrador creado.")


@rt(f"{BASE}/{{aid}}/{{gid}}/descartar")
def post(auth, sess, aid: int, gid: int):
    return _volver(gid, aid, programas.descartar(aid, gid, auth["id"]), sess, "Borrador descartado.")
