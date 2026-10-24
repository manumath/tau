"""«Mi docencia»: lo que la persona dicta y su carga horaria, en una sola página (solo lo propio)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, Li, Option, P, Redirect, Response, Select, Span, Ul
from monsterui.all import H2, H3, Button, ButtonT, Card, Progress, TextPresets, UkIcon

from app.academico import carga, gestiones, oferta
from app.academico.componentes import tiene_docencia
from app.comun import adscripcion, permisos, vinculos
from app.comun.componentes.layout import ID_MODAL, pagina
from app.comun.db import get_db
from app.comun.componentes.registros import insignia

rt = APIRouter()
BASE = "/docencia/mia"


def _tarjeta_vinculo(v):
    if not v:
        return Card(H3("Vínculo y carga horaria", cls="text-base font-semibold"),
                    P("No tiene un vínculo vigente con la Carrera. Si cree que es un error, consulte a la "
                      "Dirección de Carrera.", cls=TextPresets.muted_sm))
    c = vinculos.carga_de(v)
    return Card(
        H3("Vínculo y carga horaria", cls="text-base font-semibold"),
        P(Span(vinculos.CATEGORIAS[v["categoria"]], cls="font-medium"), f" · {vinculos.texto_periodo(v)}",
          cls="text-sm"),
        Div(Span(f"{c['horas']}", cls="text-3xl font-semibold tabular-nums"), Span(" h/mes contratadas", cls="text-sm"),
            cls="mt-3") if c else P("Sin carga contratada registrada.", cls=TextPresets.muted_sm),
        Ul(*[Li(Span(f"{t}: ", cls="text-sm"), Span(f"{c['actividades'][k]} h/mes", cls="text-sm font-medium"),
                Span(f" · {c['detalles'][k]}", cls=TextPresets.muted_sm) if c["detalles"].get(k) else "",
                cls="py-0.5")
             for k, t in vinculos.ACTIVIDADES.items() if c["actividades"][k]], cls="mt-2") if c else "",
        P("La registra la Dirección de Carrera.", cls=(TextPresets.muted_sm, "mt-2")))


def _barra(valor, maximo, etiqueta):
    """Avance de horas (si se pasa del máximo, la barra queda llena y el aviso lo explica)."""
    return Progress(value=min(valor, maximo), max=maximo, aria_label=etiqueta, title=etiqueta, cls="mt-1")


def _tarjeta_materias(uid, g):
    materias = carga.materias_con_detalle(uid, g["id"])
    temporada = g["tipo"] in oferta.TEMPORADA
    r = carga.resumen(uid, g) if not temporada else None
    filas = [fh.Tr(fh.Td(m["sigla"], cls="font-mono text-sm whitespace-nowrap"), fh.Td(m["nombre"], cls="text-sm"),
                   fh.Td(m["paralelo"], cls="text-sm"),
                   fh.Td(str(m["inscritos"]) if m["inscritos"] is not None else "—", cls="text-sm tabular-nums"),
                   fh.Td(oferta.ROLES[m["rol"]], cls="text-sm")) for m in materias]
    return Card(
        H3(f"Materias · {gestiones.codigo(g)}", cls="text-base font-semibold"),
        P(gestiones.nombre(g), cls=TextPresets.muted_sm),
        Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Sigla"), fh.Th("Asignatura"), fh.Th("Paralelo"), fh.Th("Inscritos"),
                                    fh.Th("Rol"))), fh.Tbody(*filas), cls="uk-table uk-table-divider uk-table-small"),
            cls="overflow-x-auto mt-2") if filas else P("No tiene materias en esta gestión.", cls=(TextPresets.muted_sm, "mt-2")),
        P("Curso de temporada: cuenta como docencia dictada, no como carga del semestre.",
          cls="text-sm text-amber-700 mt-2") if temporada else "",
        Div(P(f"Docencia prevista: {r['prevista'] if r['prevista'] is not None else '—'} h/mes · asignada: "
              f"{r['asignada']} h/mes (32 por materia como titular).", cls="text-sm"),
            _barra(r["asignada"], r["prevista"], "Docencia asignada respecto de la prevista") if r["prevista"] else "",
            *[insignia(a, "ambar", icono="circle-alert") for a in r["avisos"]],
            cls="mt-3 space-y-1") if r else "")


def _tarjeta_proyectos(uid, v):
    c = vinculos.carga_de(v)
    en = carga.proyectos_con_carga(uid)
    usadas = {a: sum(x["horas"] for x in en if vinculos.ACTIVIDAD_DE_CLASE.get(x["clase"]) == a)
              for a in ("investigacion", "extension")}
    resumen = [(a, f"{vinculos.ACTIVIDADES[a]}: {usadas[a]} de {c['actividades'][a]} h/mes asignadas en proyectos")
               for a in ("investigacion", "extension") if c and c["actividades"][a]]
    return Card(
        H3("Carga en proyectos", cls="text-base font-semibold"),
        Ul(*[Li(fh.A(x["nombre"], href=f"/proyectos/{x['id']}", cls="text-sm hover:underline"),
                Span(f" · {'investigación' if x['clase'] == 'investigacion' else 'interacción social'} · {x['horas']} h/mes",
                     cls=TextPresets.muted_sm), cls="py-0.5") for x in en], cls="mt-2")
        if en else P("Ningún proyecto le tiene carga asignada en su vínculo vigente.", cls=(TextPresets.muted_sm, "mt-2")),
        *[Div(P(t, cls=TextPresets.muted_sm), _barra(usadas[a], c["actividades"][a], t))
          for a, t in resumen],
        P("La asigna el responsable de cada proyecto institucional.", cls=(TextPresets.muted_sm, "mt-2")))


def _tarjeta_historial(uid):
    periodos = list(reversed(vinculos.listar(uid)))
    return Card(
        H3("Historial de vínculo", cls="text-base font-semibold"),
        Ul(*[Li(Span(vinculos.CATEGORIAS[v["categoria"]], cls="text-sm font-medium"),
                Span(f" · {vinculos.texto_periodo(v)}", cls="text-sm"),
                Span(f" · {vinculos.texto_carga(v)}", cls=TextPresets.muted_sm) if vinculos.carga_de(v) else "",
                Span(f" · {vinculos.MOTIVOS_TERMINO[v['motivo_termino']].lower()}", cls=TextPresets.muted_sm)
                if v["motivo_termino"] else "", cls="py-0.5") for v in periodos], cls="mt-2")
        if periodos else P("Sin periodos registrados.", cls=(TextPresets.muted_sm, "mt-2")))


def _gestion_y_selector(uid, gestion, base):
    lista = carga.gestiones_de(uid)
    g = next((x for x in lista if str(x["id"]) == gestion), None) or carga.semestre_de_referencia() \
        or (lista[0] if lista else None)
    selector = Select(*[Option(gestiones.codigo(x), value=str(x["id"]), selected=g and x["id"] == g["id"]) for x in lista],
                      aria_label="Gestión", cls="uk-select w-40",
                      data_navegar=f"{base}?gestion=") if len(lista) > 1 else ""
    return g, selector


def cuerpo(uid, g):
    """Materias, carga en proyectos, vínculo e historial de una persona (lo usan «Mi docencia» y la ficha)."""
    v = vinculos.vigente(uid)
    return Div(Div(_tarjeta_materias(uid, g) if g else Card(P("Aún no hay gestiones registradas.", cls=TextPresets.muted_sm)),
                   _tarjeta_proyectos(uid, v), cls="space-y-4 lg:col-span-2 min-w-0"),
               Div(_tarjeta_vinculo(v), _tarjeta_historial(uid), cls="space-y-4 min-w-0"),
               cls="grid grid-cols-1 lg:grid-cols-3 gap-4")


@rt(BASE)
def get(auth, gestion: str = ""):
    uid = auth["id"]
    g, selector = _gestion_y_selector(uid, gestion, BASE)
    return pagina(
        "Mi docencia",
        Div(Div(H2("Mi docencia"),
                P("Sus materias, su carga horaria y su vínculo con la Carrera. Solo usted y las direcciones ven esta "
                  "información.", cls=TextPresets.muted_sm)),
            selector, cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        cuerpo(uid, g),
        P(UkIcon("info", height=14, width=14, cls="shrink-0 mt-0.5"),
          Span("¿Algo no coincide? La carga y el vínculo los corrige la Dirección de Carrera; las materias, la "
               "Dirección de Carrera o la Coordinación académica en «Oferta y docentes»."),
          cls=(TextPresets.muted_sm, "flex items-start gap-1 mt-6")),
        usuario=auth, seccion="docencia")


@rt("/docencia/docentes/{uid}")
def get(auth, uid: int, gestion: str = ""):
    """Ficha de un docente para las direcciones: lo mismo que ve en «Mi docencia», con acceso a editar."""
    if uid == auth["id"]:
        return Redirect(BASE + (f"?gestion={gestion}" if gestion else ""))
    if not permisos.puede(auth, "ver_carga"):
        return Response("No autorizado", status_code=403)
    persona = get_db().q("SELECT id, nombres, apellidos, email FROM usuario WHERE id = ?", [uid])
    if not persona:
        return Response("No encontrado", status_code=404)
    p = persona[0]
    g, selector = _gestion_y_selector(uid, gestion, f"/docencia/docentes/{uid}")
    v = vinculos.vigente(uid)
    edita_vinculo = permisos.puede(auth, "gestionar_vinculos", vinculos.carrera())
    return pagina(
        f"{p['nombres']} {p['apellidos']}",
        A(UkIcon("arrow-left", height=14, width=14), "Carga horaria",
          href="/docencia/carga" + (f"?gestion={g['id']}" if g and g["tipo"] in carga.SEMESTRES else ""),
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(Div(H2(f"{p['nombres']} {p['apellidos']}"),
                P(" · ".join(x for x in (vinculos.CATEGORIAS[v["categoria"]] if v else "Sin vínculo vigente",
                                         adscripcion.cargo(uid), p["email"]) if x), cls=TextPresets.muted_sm)),
            Div(selector,
                Button(UkIcon("pencil", height=14, width=14), "Vínculo y carga", cls=(ButtonT.default, ButtonT.sm),
                       hx_get=f"/admin/usuarios/{uid}/vinculo", hx_target=f"#{ID_MODAL}") if edita_vinculo else "",
                A(UkIcon("user-round", height=14, width=14), "Perfil", href=f"/investigadores/{uid}",
                  cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1")
                if get_db().q("SELECT 1 FROM investigador WHERE usuario_id = ?", [uid]) else "",
                cls="flex flex-wrap items-center gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        cuerpo(uid, g),
        usuario=auth, seccion="docencia")


@rt("/docencia")
def get(auth):
    """Entrada de la sección: «Mi docencia» para quien dicta o tiene vínculo; si no, los planes."""
    return Redirect(BASE if tiene_docencia(auth) else "/docencia/planes")
