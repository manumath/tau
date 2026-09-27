"""Carga horaria semestral: resumen por persona y distribución de actividades. La ven la Dirección
de Carrera, la Coordinación académica, la Dirección del Instituto y el Comité (`ver_carga`); la
registra la Dirección de Carrera (`asignar_carga`)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Ul
from fasthtml.toaster import add_toast
from monsterui.all import H2, H3, Button, ButtonT, TextPresets, UkIcon

from app.academico import carga, gestiones, oferta
from app.academico.componentes import pestanas
from app.comun import permisos
from app.comun.componentes.layout import ID_MODAL, JS_CERRAR, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import auditar, get_db

rt = APIRouter()
BASE = "/docencia/carga"


def _semestres():
    return [g for g in gestiones.listar() if g["tipo"] in carga.SEMESTRES]


def _semestre_actual():
    g = gestiones.actual()
    if g and g["tipo"] in carga.SEMESTRES:
        return g
    return next(iter(_semestres()), None)


def _h(valor):
    return f"{valor}" if valor else "—"


def _estado(r):
    if r["avisos"]:
        return Div(*[insignia(a, "ambar", icono="circle-alert") for a in r["avisos"]], cls="flex flex-col gap-1")
    return insignia("Completa", "verde", icono="check")


@rt(BASE)
def get(auth, gestion: str = ""):
    if not permisos.puede(auth, "ver_carga"):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(int(gestion)) if gestion.isdigit() else _semestre_actual()
    if not g or g["tipo"] not in carga.SEMESTRES:
        return pagina("Carga horaria", pestanas("carga", auth),
                      P("La carga se asigna por semestre. Cree primero las gestiones del año en «Gestiones».",
                        cls="text-sm"), usuario=auth, seccion="docencia")
    edita = permisos.puede(auth, "asignar_carga")
    filas = [fh.Tr(
        fh.Td(A(f"{r['apellidos']}, {r['nombres']}", href="#", hx_get=f"{BASE}/{g['id']}/{r['id']}",
                hx_target=f"#{ID_MODAL}", cls="font-medium hover:underline")),
        fh.Td(_h(r["contratada"]), cls="tabular-nums"),
        fh.Td(f"{r['docencia']} ({len(r['materias'])})" if r["materias"] else "—", cls="tabular-nums"),
        *[fh.Td(_h(r["por_tipo"][t]), cls="tabular-nums") for t in carga.TIPOS],
        fh.Td(str(r["total"]), cls="tabular-nums font-medium"),
        fh.Td(_estado(r))) for r in carga.personas(g)]
    registrar = fh.Form(
        Select(Option("Persona…", value=""),
               *[Option(f"{p['apellidos']}, {p['nombres']}" + ("" if p["con_vinculo"] else " (sin vínculo con la Carrera)"),
                        value=str(p["id"])) for p in oferta.docentes_posibles(g)],
               name="usuario", cls="uk-select w-72", aria_label="Persona", required=True),
        Select(*[Option(f"{h} h/mes", value=str(h), selected=h == carga.TIEMPO_COMPLETO) for h in carga.CARGAS],
               name="horas", cls="uk-select w-36", aria_label="Carga contratada"),
        Button(UkIcon("plus", height=14, width=14), "Registrar carga contratada", type="submit", cls=ButtonT.primary),
        hx_post=f"{BASE}/{g['id']}", hx_target=f"#{ID_MODAL}", cls="flex flex-wrap gap-2") if edita else _SOLO_CONSULTA
    copiar = Button(UkIcon("copy", height=14, width=14), "Copiar del semestre anterior", cls=ButtonT.default,
                    hx_post=f"{BASE}/{g['id']}/copiar",
                    hx_confirm="Copia la carga contratada y las actividades (no la docencia, que sale de la oferta) "
                               "de quienes aún no tienen carga en este semestre. ¿Continuar?") \
        if edita and carga.anterior(g) else ""
    return pagina(
        "Carga horaria",
        pestanas("carga", auth),
        Div(Div(H2(f"Carga horaria {gestiones.codigo(g)}"),
                P("En h/mes (unidades de 32). Docencia: 32 h/mes por materia como titular (grado o maestría), según "
                  "la oferta. No suman los auxiliares ni los cursos de verano e invierno.", cls=TextPresets.muted_sm)),
            Select(*[Option(gestiones.codigo(x), value=str(x["id"]), selected=x["id"] == g["id"]) for x in _semestres()],
                   aria_label="Semestre", cls="uk-select w-40", onchange=f"location.href='{BASE}?gestion='+this.value"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Div(registrar, copiar, cls="flex flex-wrap items-center justify-between gap-2 mb-4"),
        Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Persona"), fh.Th("Contratada"), fh.Th("Docencia (materias)"),
                                    *[fh.Th(t) for t in carga.TIPOS.values()], fh.Th("Total"), fh.Th("Estado"))),
                     fh.Tbody(*filas), cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")
        if filas else P("Aún no hay cargas en este semestre.", cls=TextPresets.muted_sm),
        usuario=auth, seccion="docencia")


def _gestion_semestre(gid):
    g = gestiones.obtener(gid)
    if not g:
        return None, Response("No encontrado", status_code=404)
    return g, None


_SOLO_CONSULTA = P(UkIcon("info", height=14, width=14, cls="inline mr-1"),
                   "La carga horaria la registra la Dirección de Carrera; usted puede consultarla.",
                   cls=(TextPresets.muted_sm, "flex items-center"))


def modal_persona(g, uid, auth, errores=()):
    persona = get_db().q("SELECT id, nombres, apellidos FROM usuario WHERE id = ?", [uid])[0]
    r = carga.resumen(uid, g)
    edita = permisos.puede(auth, "asignar_carga")
    base = f"{BASE}/{g['id']}/{uid}"
    contratada = fh.Form(
        Select(*[Option(f"{h} h/mes", value=str(h), selected=h == r["contratada"]) for h in carga.CARGAS],
               name="horas", cls="uk-select w-36", aria_label="Carga contratada"),
        Button("Guardar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
        hx_post=f"{BASE}/{g['id']}", hx_vals=f'{{"usuario": "{uid}"}}', hx_target=f"#{ID_MODAL}",
        cls="flex gap-2") if edita else Span(f"{_h(r['contratada'])} h/mes", cls="text-sm")
    acts = [Li(Span(f"{carga.TIPOS[a['tipo']]} · {a['horas']} h/mes", cls="text-sm font-medium"),
               Span(f" · {a['detalle']}", cls=TextPresets.muted_sm) if a["detalle"] else "",
               fh.Button(UkIcon("x", height=12, width=12), type="button", aria_label="Quitar actividad",
                         cls="p-0.5 rounded hover:text-red-600", hx_delete=f"{BASE}/actividades/{a['id']}",
                         hx_target=f"#{ID_MODAL}") if edita else "",
               cls="flex items-center gap-1 py-1") for a in r["actividades"]]
    agregar = fh.Form(
        Select(*[Option(t, value=k) for k, t in carga.TIPOS.items()], name="tipo", cls="uk-select w-48",
               aria_label="Tipo de actividad"),
        Select(*[Option(f"{h} h/mes", value=str(h)) for h in carga.CARGAS], name="horas", cls="uk-select w-32",
               aria_label="Horas"),
        fh.Input(name="detalle", cls="uk-input", placeholder="Detalle (proyecto, cargo, programa…)", aria_label="Detalle"),
        Button("Agregar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
        hx_post=f"{base}/actividades", hx_target=f"#{ID_MODAL}", cls="grid grid-cols-1 sm:grid-cols-4 gap-2") \
        if edita and r["carga"] else \
        P("Registre primero la carga contratada para agregar actividades.", cls=TextPresets.muted_sm) if edita else ""
    return modal(
        f"{persona['nombres']} {persona['apellidos']} · {gestiones.codigo(g)}",
        mensaje_error(*errores),
        "" if edita else Div(_SOLO_CONSULTA, cls="mb-3"),
        Div(Div(Span("Carga contratada", cls=(TextPresets.muted_sm, "w-40 shrink-0")), contratada,
                cls="flex flex-wrap items-center gap-2"),
            H3("Docencia", cls="text-base font-semibold mt-4"),
            Ul(*[Li(f"{m['sigla']} {m['nombre']} · paralelo {m['paralelo']} · {oferta.HORAS_POR_MATERIA} h/mes",
                    cls="text-sm py-0.5") for m in r["materias"]]) if r["materias"]
            else P("Sin materias como titular en la oferta de este semestre.", cls=TextPresets.muted_sm),
            P("Se cambia en «Oferta y docentes».", cls=TextPresets.muted_sm),
            H3("Otras actividades", cls="text-base font-semibold mt-4"),
            Ul(*acts) if acts else P("Sin otras actividades.", cls=TextPresets.muted_sm),
            agregar,
            Div(Span(f"Total: {r['total']} h/mes", cls="font-medium"),
                *[insignia(a, "ambar", icono="circle-alert") for a in r["avisos"]]
                or [insignia("Completa", "verde", icono="check")] if r["contratada"] else [],
                cls="flex flex-wrap items-center gap-2 mt-4"),
            cls="space-y-2"),
        Div(Button("Listo", type="button", cls=ButtonT.default, onclick="location.reload()"),
            cls="flex justify-end mt-4"),
        ancho="max-w-3xl")


@rt(f"{BASE}/{{gid}}/{{uid}}")
def get(auth, gid: int, uid: int):
    if not permisos.puede(auth, "ver_carga"):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_semestre(gid)
    return error or modal_persona(g, uid, auth)


@rt(f"{BASE}/{{gid}}")
def post(auth, gid: int, usuario: str = "", horas: str = ""):
    if not permisos.puede(auth, "asignar_carga"):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_semestre(gid)
    if error:
        return error
    if not usuario.isdigit() or not get_db().q("SELECT 1 FROM usuario WHERE id = ?", [int(usuario)]):
        return modal("Carga horaria", mensaje_error("Elija una persona."),
                     Div(Button("Cerrar", type="button", cls=ButtonT.default, onclick=JS_CERRAR), cls="flex justify-end"))
    uid = int(usuario)
    e = carga.fijar_contratada(uid, g, horas, auth["id"])
    if not e:
        auditar(auth["id"], "carga_contratada", "usuario", uid, f"{gestiones.codigo(g)}: {horas} h/mes")
    return modal_persona(g, uid, auth, [e] if e else [])


@rt(f"{BASE}/{{gid}}/{{uid}}/actividades")
def post(auth, gid: int, uid: int, tipo: str = "", horas: str = "", detalle: str = ""):
    if not permisos.puede(auth, "asignar_carga"):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_semestre(gid)
    if error:
        return error
    e = carga.agregar_actividad(uid, g, tipo, horas, detalle)
    if not e:
        auditar(auth["id"], "carga_actividad", "usuario", uid,
                f"{gestiones.codigo(g)}: {carga.TIPOS.get(tipo, tipo)} {horas} h/mes")
    return modal_persona(g, uid, auth, [e] if e else [])


@rt(f"{BASE}/actividades/{{aid}}")
def delete(auth, aid: int):
    if not permisos.puede(auth, "asignar_carga"):
        return Response("No autorizado", status_code=403)
    a = carga.quitar_actividad(aid)
    if not a:
        return Response("No encontrado", status_code=404)
    g = gestiones.obtener(a["gestion_id"])
    auditar(auth["id"], "quitar_carga_actividad", "usuario", a["usuario_id"],
            f"{gestiones.codigo(g)}: {carga.TIPOS[a['tipo']]} {a['horas']} h/mes")
    return modal_persona(g, a["usuario_id"], auth)


@rt(f"{BASE}/{{gid}}/copiar")
def post(auth, sess, gid: int):
    if not permisos.puede(auth, "asignar_carga"):
        return Response("No autorizado", status_code=403)
    g, error = _gestion_semestre(gid)
    if error:
        return error
    n = carga.copiar_del_anterior(g, auth["id"])
    auditar(auth["id"], "copiar_carga", "gestion_academica", gid, f"{gestiones.codigo(g)}: {n} persona(s)")
    add_toast(sess, f"Se copió la carga de {n} persona(s) del semestre anterior.", "success")
    return Redirect(f"{BASE}?gestion={gid}")
