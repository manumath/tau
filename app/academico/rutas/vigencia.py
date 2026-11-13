"""Poner en vigencia, iniciar el cierre y cerrar un plan; y la página de una reforma (PLAN §65, etapa 5).
Decide solo la Dirección de Carrera (`decidir_planes`); la Coordinación académica puede ver la reforma."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Input, P, Redirect, Response, Span
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, Card, TextPresets, UkIcon

from app.academico import planes, vigencia
from app.academico.rutas.planes import BASE, estado_insignia
from app.comun import permisos
from app.comun.componentes.layout import CERRAR, ID_MODAL, campo, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import get_db

rt = APIRouter()


def _decide(auth):
    return None if permisos.puede(auth, "decidir_planes") else Response("No autorizado", status_code=403)


def _plan(pid, estado):
    p = planes.obtener(pid)
    return p if p and p["estado"] == estado else None


@rt(f"{BASE}/{{pid}}/vigencia")
def post(auth, sess, pid: int):
    if (no := _decide(auth)):
        return no
    if not _plan(pid, "elaboracion"):
        return Response("No encontrado", status_code=404)
    errores = vigencia.poner_en_vigencia(pid, auth["id"])
    if errores:
        add_toast(sess, errores[0], "error")
        return Redirect(f"{BASE}/{pid}")
    add_toast(sess, "El plan está en vigencia.", "success")
    return Redirect(f"{BASE}/{pid}")


def _form_inicio(p, errores=(), v=None):
    v = v or {}
    return fh.Form(
        mensaje_error(*errores),
        P(f"{p['programa']} · {p['nombre']}. Un plan en proceso de cierre ya no admite nuevos ingresos; sigue en la "
          "oferta mientras egresan quienes lo cursan.", cls=(TextPresets.muted_sm, "mb-3")),
        campo("Año del último ingreso", Input(name="anio", value=v.get("anio", str(p["vigente_desde"])),
                                              inputmode="numeric", required=True, cls="uk-input")),
        campo("Resolución o motivo", fh.Textarea(v.get("motivo", ""), name="motivo", rows=3, required=True,
                                                 cls="uk-textarea")),
        Div(Button("Iniciar el cierre", type="submit", cls=ButtonT.primary),
            Button("Cancelar", type="button", cls=ButtonT.ghost, **CERRAR), cls="flex gap-2 justify-end mt-4"),
        hx_post=f"{BASE}/{p['id']}/cierre/iniciar", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML",
        hx_confirm="Este plan dejará de admitir nuevos ingresos. ¿Continuar?",
        hx_disabled_elt="find button[type='submit']", cls="space-y-3")


@rt(f"{BASE}/{{pid}}/cierre/iniciar")
def get(auth, pid: int):
    if (no := _decide(auth)):
        return no
    p = _plan(pid, "vigente")
    if not p:
        return Response("No encontrado", status_code=404)
    return modal("Iniciar el cierre del plan", _form_inicio(p), ancho="max-w-lg")


@rt(f"{BASE}/{{pid}}/cierre/iniciar")
async def post(auth, sess, pid: int, req):
    if (no := _decide(auth)):
        return no
    p = _plan(pid, "vigente")
    if not p:
        return Response("No encontrado", status_code=404)
    f = await req.form()
    errores = vigencia.iniciar_cierre(pid, f.get("anio", ""), f.get("motivo", ""), auth["id"])
    if errores:
        return modal("Iniciar el cierre del plan", _form_inicio(p, errores, dict(f)), ancho="max-w-lg")
    add_toast(sess, "El plan está en proceso de cierre.", "success")
    return Redirect(f"{BASE}/{pid}")


def _form_cierre(p, errores=(), v=None):
    v = v or {}
    quedan = vigencia.estudiantes_en(p["id"])
    return fh.Form(
        mensaje_error(*errores),
        P(f"{p['programa']} · {p['nombre']}. Un plan cerrado queda solo como historial y sale de la oferta.",
          cls=(TextPresets.muted_sm, "mb-3")),
        Div(insignia(f"{quedan} estudiante{'s' if quedan != 1 else ''} cursando", "ambar" if quedan else "verde",
                     icono="users"), cls="mb-3"),
        fh.Label(Input(type="checkbox", name="forzar", value="1", checked=bool(v.get("forzar"))),
                 Span("Cerrar aunque queden estudiantes cursando", cls="text-sm"), cls="flex items-center gap-2 mb-3")
        if quedan else "",
        campo("Motivo del cierre" + (" (obligatorio si quedan estudiantes)" if quedan else " (opcional)"),
              fh.Textarea(v.get("motivo", ""), name="motivo", rows=3, cls="uk-textarea")),
        Div(Button("Cerrar el plan", type="submit", cls=ButtonT.primary),
            Button("Cancelar", type="button", cls=ButtonT.ghost, **CERRAR), cls="flex gap-2 justify-end mt-4"),
        hx_post=f"{BASE}/{p['id']}/cierre/cerrar", hx_target=f"#{ID_MODAL}", hx_swap="innerHTML",
        hx_confirm="Un plan cerrado no se vuelve a abrir. ¿Continuar?", hx_disabled_elt="find button[type='submit']",
        cls="space-y-3")


@rt(f"{BASE}/{{pid}}/cierre/cerrar")
def get(auth, pid: int):
    if (no := _decide(auth)):
        return no
    p = _plan(pid, "cierre")
    if not p:
        return Response("No encontrado", status_code=404)
    return modal("Cerrar el plan", _form_cierre(p), ancho="max-w-lg")


@rt(f"{BASE}/{{pid}}/cierre/cerrar")
async def post(auth, sess, pid: int, req):
    if (no := _decide(auth)):
        return no
    p = _plan(pid, "cierre")
    if not p:
        return Response("No encontrado", status_code=404)
    f = await req.form()
    errores = vigencia.cerrar(pid, f.get("motivo", ""), bool(f.get("forzar")), auth["id"])
    if errores:
        return modal("Cerrar el plan", _form_cierre(p, errores, dict(f)), ancho="max-w-lg")
    add_toast(sess, "El plan está cerrado.", "success")
    return Redirect(f"{BASE}/{pid}")


# --- Una reforma ------------------------------------------------------------------------------------------------------

def _reforma(rid):
    f = get_db().q("SELECT * FROM reforma_curricular WHERE id = ?", [rid])
    return f[0] if f else None


@rt(f"{BASE}/reforma/{{rid}}")
def get(auth, rid: int):
    if not permisos.puede(auth, "elaborar_planes"):
        return Response("No autorizado", status_code=403)
    r = _reforma(rid)
    if not r:
        return pagina("No encontrado", P("La reforma no existe."), usuario=auth)
    lista = [p for p in planes.listar(auth) if p["reforma_id"] == rid]
    filas, borradores, listos = [], 0, 0
    for p in lista:
        if p["estado"] == "elaboracion":
            borradores += 1
            falta = vigencia.faltantes(p["id"])
            listos += not falta
            estado_verif = insignia("Lista", "verde", icono="check") if not falta else \
                insignia(f"Faltan {len(falta)}", "rojo", icono="circle-x")
        else:
            estado_verif = ""
        filas.append(fh.Tr(fh.Td(A(p["programa"], href=f"{BASE}/{p['id']}", cls="font-medium hover:underline"),
                                 Div(planes.NIVELES[p["nivel"]], cls=TextPresets.muted_sm)),
                           fh.Td(p["nombre"]), fh.Td(estado_insignia(p)), fh.Td(str(p["n_asignaturas"]), cls="tabular-nums"),
                           fh.Td(estado_verif)))
    anio = r["vigente_desde"]
    boton = Div(
        Button(UkIcon("rocket", height=14, width=14), "Poner en vigencia la reforma", hx_post=f"{BASE}/reforma/{rid}/vigencia",
               hx_confirm=f"¿Poner en vigencia los {borradores} planes de la reforma {r['nombre']}? Los planes vigentes "
                          f"de los mismos programas pasarán a «en proceso de cierre» (último ingreso en {anio - 1}). "
                          "Los planes nuevos dejarán de poder editarse.", hx_swap="none",
               disabled=listos != borradores, cls=ButtonT.primary),
        P("Se ponen en vigencia todos los planes juntos, o ninguno." if listos == borradores else
          f"Aún no: {borradores - listos} plan(es) tienen puntos por resolver en su lista de verificación.",
          cls=(TextPresets.muted_sm, "mt-1")), cls="mt-4") if borradores and permisos.puede(auth, "decidir_planes") else ""
    return pagina(
        f"Reforma {r['nombre']}",
        A(UkIcon("arrow-left", height=14, width=14), "Planes de estudio", href=BASE,
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(f"Reforma {r['nombre']}"),
        P(" · ".join(x for x in (r["resolucion"], f"rige desde {anio}") if x), cls=(TextPresets.muted_sm, "mb-4")),
        Card(H3("Planes de la reforma", cls="text-base font-semibold mb-2"),
             Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Programa"), fh.Th("Plan"), fh.Th("Estado"), fh.Th("Asignaturas"),
                                         fh.Th("Para poner en vigencia"))), fh.Tbody(*filas),
                          cls="uk-table uk-table-divider uk-table-middle"), cls="overflow-x-auto")),
        boton, usuario=auth, seccion="docencia")


@rt(f"{BASE}/reforma/{{rid}}/vigencia")
def post(auth, sess, rid: int):
    if (no := _decide(auth)):
        return no
    if not _reforma(rid):
        return Response("No encontrado", status_code=404)
    errores = vigencia.poner_reforma_en_vigencia(rid, auth["id"])
    if errores:
        add_toast(sess, errores[0], "error")
        return Redirect(f"{BASE}/reforma/{rid}")
    add_toast(sess, "La reforma está en vigencia.", "success")
    return Redirect(f"{BASE}/reforma/{rid}")

