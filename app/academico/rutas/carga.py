"""Carga horaria por semestre: lo contratado y su distribución (del vínculo con la Carrera) frente a
la docencia asignada en la oferta. La ven la Dirección de Carrera, la Coordinación académica, la
Dirección del Instituto y el Comité (`ver_carga`). La carga se registra en Usuarios → Vínculo,
pestaña de la Carrera (`gestionar_vinculos` en la Carrera: la Dirección de Carrera)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Response, Select, Span, Ul
from monsterui.all import H2, H3, Button, ButtonT, TextPresets, UkIcon

from app.academico import carga, gestiones, oferta
from app.academico.componentes import pestanas
from app.comun import permisos, vinculos
from app.comun.componentes.layout import ID_MODAL, JS_CERRAR, modal, pagina
from app.comun.componentes.registros import insignia
from app.comun.db import get_db

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


def _edita(auth) -> bool:
    return permisos.puede(auth, "gestionar_vinculos", vinculos.carrera())


def _url_vinculo(uid):
    return f"/admin/usuarios/{uid}/vinculo"


@rt(BASE)
def get(auth, gestion: str = ""):
    if not permisos.puede(auth, "ver_carga"):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(int(gestion)) if gestion.isdigit() else _semestre_actual()
    if not g or g["tipo"] not in carga.SEMESTRES:
        return pagina("Carga horaria", pestanas("carga", auth),
                      P("La carga se consulta por semestre. Cree primero las gestiones del año en «Gestiones».",
                        cls="text-sm"), usuario=auth, seccion="docencia")
    filas = []
    for r in carga.personas(g):
        c = r["carga"]
        filas.append(fh.Tr(
            fh.Td(A(f"{r['apellidos']}, {r['nombres']}", href="#", hx_get=f"{BASE}/{g['id']}/{r['id']}",
                    hx_target=f"#{ID_MODAL}", cls="font-medium hover:underline"),
                  Div(vinculos.CATEGORIAS[r["vinculo"]["categoria"]], cls=TextPresets.muted_sm) if r["vinculo"] else ""),
            fh.Td(_h(r["contratada"]), cls="tabular-nums"),
            fh.Td(f"{_h(r['prevista'])} / {r['asignada']}" + (f" ({len(r['materias'])})" if r["materias"] else ""),
                  cls="tabular-nums whitespace-nowrap"),
            *[fh.Td(_h(c["actividades"][k]) if c else "—", cls="tabular-nums")
              for k in carga.ACTIVIDADES if k != "docencia"],
            fh.Td(_estado(r))))
    nota = P(UkIcon("info", height=14, width=14, cls="shrink-0 mt-0.5"),
             Span("La carga contratada y su distribución se registran en el vínculo con la Carrera (Usuarios → Vínculo). "
             + ("Haga clic en una persona para verla o cambiarla." if _edita(auth)
                else "La registra la Dirección de Carrera; usted puede consultarla.")),
             cls=(TextPresets.muted_sm, "flex items-start gap-1 mb-4"))
    return pagina(
        "Carga horaria",
        pestanas("carga", auth),
        Div(Div(H2(f"Carga horaria {gestiones.codigo(g)}"),
                P("En h/mes (unidades de 32), según el vínculo con la Carrera al inicio del semestre. Docencia: "
                  "prevista / asignada en la oferta (32 h/mes por materia como titular, de grado o maestría); no suman "
                  "los auxiliares ni los cursos de verano e invierno.", cls=TextPresets.muted_sm)),
            Div(Select(*[Option(gestiones.codigo(x), value=str(x["id"]), selected=x["id"] == g["id"]) for x in _semestres()],
                       aria_label="Semestre", cls="uk-select w-40", onchange=f"location.href='{BASE}?gestion='+this.value"),
                A(UkIcon("file-text", height=14, width=14), "Informe imprimible y XLSX",
                  href=f"/informes/carga-docente?gestion={g['id']}",
                  cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1"),
                cls="flex flex-wrap items-center gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-4"),
        nota,
        Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Persona"), fh.Th("Contratada"), fh.Th("Docencia (materias)"),
                                    *[fh.Th(t) for k, t in carga.ACTIVIDADES.items() if k != "docencia"],
                                    fh.Th("Estado"))),
                     fh.Tbody(*filas), cls="uk-table uk-table-divider uk-table-small"), cls="overflow-x-auto")
        if filas else P("Nadie tiene vínculo con la Carrera ni materias asignadas en este semestre.",
                        cls=TextPresets.muted_sm),
        usuario=auth, seccion="docencia")


@rt(f"{BASE}/{{gid}}/{{uid}}")
def get(auth, gid: int, uid: int):
    if not permisos.puede(auth, "ver_carga"):
        return Response("No autorizado", status_code=403)
    g = gestiones.obtener(gid)
    filas = get_db().q("SELECT id, nombres, apellidos FROM usuario WHERE id = ?", [uid])
    if not g or g["tipo"] not in carga.SEMESTRES or not filas:
        return Response("No encontrado", status_code=404)
    persona, r = filas[0], carga.resumen(uid, g)
    c, v = r["carga"], r["vinculo"]
    distribucion = Ul(*[Li(Span(f"{t}: ", cls="text-sm"), Span(f"{c['actividades'][k]} h/mes", cls="text-sm font-medium"),
                           Span(f" · {c['detalles'][k]}", cls=TextPresets.muted_sm) if c["detalles"].get(k) else "",
                           cls="py-0.5") for k, t in carga.ACTIVIDADES.items() if c["actividades"][k]]) if c else ""
    return modal(
        f"{persona['nombres']} {persona['apellidos']} · {gestiones.codigo(g)}",
        Div(P(f"Vínculo con la Carrera: {vinculos.CATEGORIAS[v['categoria']]} ({vinculos.texto_periodo(v)})"
              if v else "Sin vínculo con la Carrera al inicio del semestre.", cls="text-sm"),
            H3("Carga contratada", cls="text-base font-semibold mt-4"),
            P(f"{c['horas']} h/mes", cls="text-sm font-medium")
            if c else P("Sin carga registrada.", cls=TextPresets.muted_sm),
            distribucion,
            *([H3("En proyectos", cls="text-base font-semibold mt-4"),
               Ul(*[Li(f"{x['nombre']} · {'investigación' if x['clase'] == 'investigacion' else 'extensión'} · "
                       f"{x['horas']} h/mes", cls="text-sm py-0.5") for x in carga.en_proyectos(v["id"])])]
              if v and carga.en_proyectos(v["id"]) else []),
            H3("Docencia asignada", cls="text-base font-semibold mt-4"),
            Ul(*[Li(f"{m['sigla']} {m['nombre']} · paralelo {m['paralelo']} · {oferta.HORAS_POR_MATERIA} h/mes",
                    cls="text-sm py-0.5") for m in r["materias"]]) if r["materias"]
            else P("Sin materias como titular en la oferta de este semestre.", cls=TextPresets.muted_sm),
            P("Se cambia en «Oferta y docentes».", cls=TextPresets.muted_sm),
            Div(*[insignia(a, "ambar", icono="circle-alert") for a in r["avisos"]]
                or [insignia("Completa", "verde", icono="check")], cls="flex flex-wrap gap-2 mt-4"),
            cls="space-y-2"),
        Div(Button(UkIcon("pencil", height=14, width=14), "Registrar o cambiar la carga en el vínculo",
                   cls=ButtonT.primary, hx_get=_url_vinculo(uid), hx_target=f"#{ID_MODAL}") if _edita(auth) else "",
            Button("Cerrar", type="button", cls=ButtonT.default, onclick=JS_CERRAR),
            cls="flex justify-end gap-2 mt-4"),
        ancho="max-w-2xl")
