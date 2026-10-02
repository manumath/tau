"""Endpoints del selector de personas (autocompletar, filas y alta rápida de externos)."""
import fasthtml.common as fh
from fasthtml.common import A, APIRouter, Div, HtmxResponseHeaders, Input, P, Response, Span, Thead, Tr
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, Table, Tbody, Td, TextPresets, Th, UkIcon

from app.comun import paises, permisos, personas
from app.investigacion.componentes import personas as ui
from app.comun.componentes.layout import ID_MODAL, JS_CERRAR, boton_espera, modal, pagina
from app.comun.db import auditar, get_db

rt = APIRouter()
CAMPOS = {"autor", "participante"}


def _rol_inicial(campo):
    return "expositor" if campo == "participante" else None


@rt("/personas/buscar")
def get(campo: str = "autor", q: str = "", autor: list[str] = None, participante: list[str] = None):
    if campo not in CAMPOS:
        return ""
    elegidas = set((autor if campo == "autor" else participante) or [])
    return ui.resultados(campo, q, personas.buscar(q, excluir=elegidas))


@rt("/personas/fila")
def get(campo: str = "autor", ref: str = ""):
    p = personas.por_ref(ref)
    if campo not in CAMPOS or not p:
        return ""
    return ui.fila(p, campo, _rol_inicial(campo))


@rt("/personas/externo/nuevo")
def get(campo: str = "autor", q: str = ""):
    return ui.form_externo(campo, q) if campo in CAMPOS else ""


@rt("/personas/externo")
def post(auth, campo: str = "autor", ext_nombres: str = "", ext_apellidos: str = "",
         ext_institucion: str = "", ext_pais: str = ""):
    if campo not in CAMPOS:
        return ""
    if not ext_nombres.strip() or not ext_apellidos.strip():
        # El botón apunta a la lista; el error vuelve al recuadro del formulario.
        _, resultados_id, _ = ui.ids(campo)
        return (ui.form_externo(campo, f"{ext_nombres} {ext_apellidos}",
                                ["Nombres y apellidos son obligatorios."]),
                HtmxResponseHeaders(retarget=f"#{resultados_id}", reswap="innerHTML"))
    # Si ya existe alguien con el mismo nombre se reutiliza, en lugar de duplicarlo.
    externo = personas.externo_similar(ext_nombres, ext_apellidos) or personas.crear_externo(
        ext_nombres, ext_apellidos, ext_institucion, ext_pais, auth["id"])
    return ui.fila(personas.por_ref(f"e:{externo['id']}"), campo, _rol_inicial(campo))


# --- Coautores externos: completar país e institución ------------------------------------------------------------

def _permitido(auth):
    return auth["es_investigador"] or permisos.puede(auth, "gestionar_personas_externas")


def fila_externo(e, vincula=False):
    return Tr(
        Td(Div(f"{e['apellidos']}, {e['nombres']}", cls="font-medium"),
           Div(f"{e['n_productos']} productos · {e['n_actividades']} actividades · {e['n_proyectos']} proyectos",
               cls=TextPresets.muted_sm)),
        Td(fh.Form(Input(name="institucion", value=e["institucion"] or "", cls="uk-input h-8 text-sm",
                         placeholder="Institución", aria_label=f"Institución de {e['nombres']} {e['apellidos']}"),
                   Input(name="pais", value=e["pais"] or "", list="lista-paises", placeholder="País",
                         cls="uk-input h-8 text-sm w-40" + ("" if e["pais"] else " border-amber-400"),
                         aria_label=f"País de {e['nombres']} {e['apellidos']}"),
                   Button("Guardar", type="submit", cls=(ButtonT.ghost, ButtonT.sm)),
                   hx_put=f"/personas/externos/{e['id']}", hx_target=f"#externo-{e['id']}", hx_swap="outerHTML",
                   cls="flex flex-wrap gap-2 items-center"),
           Button(UkIcon("link", height=14, width=14), "Vincular a una cuenta", type="button",
                  cls=(ButtonT.ghost, ButtonT.sm), hx_get=f"/personas/externos/{e['id']}/vincular",
                  hx_target=f"#{ID_MODAL}") if vincula else ""),
        id=f"externo-{e['id']}")


def tabla_externos(q="", sin_pais=True, vincula=False):
    lista = personas.externos(q, sin_pais)
    return Div(Table(Thead(Tr(Th("Persona"), Th("Institución y país"))),
                     Tbody(*[fila_externo(e, vincula) for e in lista]) if lista else
                     Tbody(Tr(Td("No hay personas que coincidan." if q or not sin_pais else
                                 "Todas las personas externas tienen país registrado.", colspan=2,
                                 cls=(TextPresets.muted_sm, "text-center py-6")))),
                     cls="uk-table-divider uk-table-middle", data_tabla="personas-externas", data_tabla_filtro="no"),
               id="tabla-externos", cls="overflow-x-auto")


@rt("/personas/externos")
def get(auth, q: str = "", sin_pais: bool = True, todos: bool = False):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    sin_pais = sin_pais and not todos
    n_sin = len(personas.externos(solo_sin_pais=True))
    return pagina(
        "Coautores externos",
        Div(Div(H2("Coautores y participantes externos"),
                P("Personas sin cuenta en el sistema (coautores, participantes de actividades y proyectos). Su país sirve "
                  "para medir la colaboración internacional (IAC-CINDA 3.5.2). Al importar desde OpenAlex el país se "
                  "completa solo; aquí se completan los que falten.", cls=(TextPresets.muted_sm, "max-w-3xl"))),
            Div(Button(UkIcon("wand-sparkles", height=16, width=16), "Completar países automáticamente",
                       cls=ButtonT.default, hx_post="/personas/externos/completar",
                       title="Normaliza los países escritos y deduce los que faltan desde la institución"),
                A(UkIcon("users", height=16, width=16),
                  f"Duplicados y cuentas ({len(personas.posibles_duplicados()) + len(personas.sugerencias_de_cuenta())})",
                  href="/personas/externos/duplicados", cls="uk-btn uk-btn-default inline-flex items-center gap-1")
                if _fusiona(auth) else "",
                cls="flex flex-wrap gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-4"),
        P(f"{n_sin} persona(s) sin país.", cls="text-sm text-amber-700" if n_sin else "text-sm text-green-700"),
        fh.Form(Input(type="search", name="q", value=q, placeholder="Buscar por nombre o institución…",
                      cls="uk-input max-w-sm", aria_label="Buscar personas externas"),
                fh.Label(fh.Input(type="checkbox", name="todos", value="1", checked=not sin_pais, cls="uk-checkbox"),
                         Span("Mostrar también las que ya tienen país", cls="text-sm"), cls="flex items-center gap-2"),
                hx_get="/personas/externos/tabla", hx_target="#tabla-externos", hx_swap="outerHTML",
                hx_trigger="input delay:300ms, change, search", onsubmit="return false", cls="flex flex-wrap gap-3 mb-4"),
        fh.Datalist(*[fh.Option(value=x) for x in paises.nombres()], id="lista-paises"),
        Card(tabla_externos(q, sin_pais, _fusiona(auth))),
        usuario=auth, seccion="investigadores")


@rt("/personas/externos/tabla")
def get(auth, q: str = "", todos: bool = False):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    return tabla_externos(q, not todos, _fusiona(auth))


@rt("/personas/externos/completar")
def post(auth, sess):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    normalizados, deducidos = personas.completar_paises()
    auditar(auth["id"], "completar_paises", "persona_externa", None, f"{normalizados} normalizados, {deducidos} deducidos")
    add_toast(sess, f"Países: {deducidos} deducido(s) de la institución y {normalizados} normalizado(s).", "success")
    return HtmxResponseHeaders(refresh="true")


# --- Duplicados: dos fichas de la misma persona ------------------------------------------------------

def _fusiona(auth):
    """Fusionar cambia registros de otras personas: solo quien administra las personas externas."""
    return permisos.puede(auth, "gestionar_personas_externas")


def _ficha_externo(e, nombre_radio, valor, marcado):
    datos = [x for x in (e["institucion"], e["pais"], f"ORCID {e['orcid']}" if e["orcid"] else None,
                         e["email"]) if x]
    def n(cantidad, singular, plural):
        return f"{cantidad} {singular if cantidad == 1 else plural}"
    uso = " · ".join([n(e["n_productos"], "producto", "productos"), n(e["n_actividades"], "actividad", "actividades"),
                      n(e["n_proyectos"], "proyecto", "proyectos")]
                     + ([n(e["n_estudiante"], "periodo de estudiante", "periodos de estudiante")] if e["n_estudiante"] else []))
    return (fh.Label if nombre_radio else Div)(
                    Input(type="radio", name=nombre_radio, value=str(valor), checked=marcado, cls="uk-radio mt-1")
                    if nombre_radio else "",
                    Div(Div(f"{e['apellidos']}, {e['nombres']}", cls="font-medium"),
                        Div(" · ".join(datos) or "Sin institución ni país", cls=TextPresets.muted_sm),
                        Div(uso, cls=TextPresets.muted_sm), cls="min-w-0"),
                    cls="flex items-start gap-2 rounded border border-border p-3"
                        + (" hover:bg-muted cursor-pointer" if nombre_radio else ""))


def tarjeta_duplicado(par):
    a, b = par["a"], par["b"]
    clave = f"{a['id']}-{b['id']}"
    return Card(
        Div(Span(par["motivo"], cls="text-xs font-medium text-muted-foreground uppercase tracking-wide"),
            cls="mb-2"),
        fh.Form(P("¿Cuál ficha conservar? La otra se elimina y sus registros pasan a la elegida.", cls="text-sm mb-2"),
                Div(_ficha_externo(a, "conservar", a["id"], True), _ficha_externo(b, "conservar", b["id"], False),
                    cls="grid grid-cols-1 md:grid-cols-2 gap-3"),
                Input(type="hidden", name="par", value=clave),
                Div(boton_espera(UkIcon("merge", height=14, width=14), "Fusionar", type="submit",
                                 cls=(ButtonT.primary, ButtonT.sm)),
                    cls="flex justify-end mt-3"),
                hx_post="/personas/externos/fusionar", hx_target=f"#par-{clave}", hx_swap="outerHTML",
                hx_disabled_elt="find button[type='submit']",
                hx_confirm="¿Fusionar estas dos fichas? No se puede deshacer."),
        id=f"par-{clave}")


def tarjeta_cuenta(c):
    e, u = c["externo"], c["usuario"]
    clave = f"{e['id']}-{u['id']}"
    return Card(
        Div(Span(c["motivo"], cls="text-xs font-medium text-muted-foreground uppercase tracking-wide"), cls="mb-2"),
        Div(_ficha_externo(e, None, None, False),
            Div(UkIcon("arrow-right", height=18, width=18), cls="hidden md:flex items-center justify-center"),
            Div(Div(f"{u['apellidos']}, {u['nombres']}", cls="font-medium"),
                Div(" · ".join(x for x in (u["email"], f"ORCID {u['orcid']}" if u["orcid"] else None) if x),
                    cls=TextPresets.muted_sm),
                Div("Cuenta del sistema", cls=TextPresets.muted_sm),
                cls="rounded border border-primary/40 bg-primary/5 p-3 min-w-0"),
            cls="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 items-stretch"),
        fh.Form(Input(type="hidden", name="externo", value=str(e["id"])),
                Input(type="hidden", name="usuario", value=str(u["id"])),
                boton_espera(UkIcon("link", height=14, width=14), "Vincular a esta cuenta", type="submit",
                             cls=(ButtonT.primary, ButtonT.sm)),
                hx_post="/personas/externos/vincular", hx_target=f"#cuenta-{clave}", hx_swap="outerHTML",
                hx_disabled_elt="find button[type='submit']",
                hx_confirm=f"¿Vincular a {e['nombres']} {e['apellidos']} con la cuenta de {u['nombres']} "
                           f"{u['apellidos']}? No se puede deshacer.", cls="flex justify-end mt-3"),
        id=f"cuenta-{clave}")


@rt("/personas/externos/duplicados")
def get(auth):
    if not _fusiona(auth):
        return Response("No autorizado", status_code=403)
    pares = personas.posibles_duplicados()
    cuentas = personas.sugerencias_de_cuenta()
    return pagina(
        "Duplicados y cuentas",
        A(UkIcon("arrow-left", height=14, width=14), "Coautores externos", href="/personas/externos",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(H2("Coautores externos: duplicados y cuentas"),
            P("Dos casos que distorsionan los indicadores: personas externas que ya tienen cuenta, y dos fichas de una "
              "misma persona. Revise cada sugerencia; nada cambia hasta que usted lo confirme.",
              cls=(TextPresets.muted_sm, "max-w-3xl")),
            cls="mb-6"),
        fh.H3("Ya tienen cuenta en el sistema", cls="text-lg font-semibold mb-1"),
        P("Personas registradas como externas que luego recibieron cuenta (p. ej., un coautor que ahora es docente). "
          "Al vincularlas, sus productos, actividades y proyectos pasan a la cuenta; si tienen periodos de estudiante, "
          "la ficha se conserva enlazada a la cuenta para guardarlos.", cls=(TextPresets.muted_sm, "max-w-3xl mb-3")),
        Div(*[tarjeta_cuenta(c) for c in cuentas], cls="space-y-4 mb-8") if cuentas
        else Card(P("No hay sugerencias.", cls=TextPresets.muted_sm), cls="mb-8"),
        fh.H3("Posibles duplicados", cls="text-lg font-semibold mb-1"),
        P("Fichas que podrían ser la misma persona: mismo ORCID, o mismo apellido con nombres compatibles («H.» y "
          "«Hermann»). Un duplicado cuenta dos veces en coautoría e internacionalización. Si son la misma persona, "
          "elija qué ficha conservar: sus productos, actividades, proyectos y periodos de estudiante pasan a ella (si "
          "ambas figuraban en el mismo registro, queda una vez) y los datos que le falten se toman de la otra.",
          cls=(TextPresets.muted_sm, "max-w-3xl mb-3")),
        Div(*[tarjeta_duplicado(p) for p in pares], cls="space-y-4") if pares
        else Card(P("No hay posibles duplicados.", cls=TextPresets.muted_sm)),
        usuario=auth, seccion="investigadores")


@rt("/personas/externos/fusionar")
def post(auth, sess, par: str = "", conservar: str = ""):
    if not _fusiona(auth):
        return Response("No autorizado", status_code=403)
    ids = [int(x) for x in par.split("-") if x.isdigit()]
    if len(ids) != 2 or not conservar.isdigit() or int(conservar) not in ids:
        return Response("Datos no válidos", status_code=400)
    c = int(conservar)
    e = next(x for x in ids if x != c)
    antes = personas.por_ref(f"e:{e}")
    error = personas.fusionar(c, e)
    if error:
        add_toast(sess, error, "error")
        return HtmxResponseHeaders(refresh="true")
    auditar(auth["id"], "fusionar_externos", "persona_externa", c,
            f"Se unió «{antes['nombres']} {antes['apellidos']}» (id {e})" if antes else f"id {e}")
    add_toast(sess, "Fichas fusionadas.", "success")
    return Div(UkIcon("check", height=14, width=14, cls="shrink-0 text-green-600"),
               Span(f"Fusionadas: queda «{personas.por_ref(f'e:{c}')['nombres']} {personas.por_ref(f'e:{c}')['apellidos']}»."),
               id=f"par-{par}", cls="flex items-center gap-2 rounded border border-border p-3 text-sm")


@rt("/personas/externos/vincular")
def post(auth, sess, externo: int, usuario: int, desde: str = ""):
    if not _fusiona(auth):
        return Response("No autorizado", status_code=403)
    e = personas.por_ref(f"e:{externo}")
    error = personas.vincular_a_cuenta(externo, usuario)
    if error:
        add_toast(sess, error, "error")
        return HtmxResponseHeaders(refresh="true")
    u = personas.por_ref(f"i:{usuario}") or {"nombres": "", "apellidos": f"cuenta {usuario}"}
    auditar(auth["id"], "vincular_externo", "usuario", usuario,
            f"«{e['nombres']} {e['apellidos']}» (externo {externo})" if e else f"externo {externo}")
    add_toast(sess, "Vinculada a la cuenta.", "success")
    if desde == "tabla":       # desde la lista de externos: la fila desaparece al recargar
        return HtmxResponseHeaders(refresh="true")
    return Div(UkIcon("check", height=14, width=14, cls="shrink-0 text-green-600"),
               Span(f"Vinculada: sus registros ahora son de {u['nombres']} {u['apellidos']}."),
               id=f"cuenta-{externo}-{usuario}", cls="flex items-center gap-2 rounded border border-border p-3 text-sm")


@rt("/personas/externos/{eid}/vincular")
def get(auth, eid: int):
    """Vincular a mano: elegir la cuenta (primero las del mismo apellido)."""
    if not _fusiona(auth):
        return Response("No autorizado", status_code=403)
    e = personas.por_ref(f"e:{eid}")
    if not e:
        return Response("No encontrado", status_code=404)
    cuentas = get_db().q("SELECT id, nombres, apellidos, email FROM usuario WHERE activo = 1 ORDER BY apellidos, nombres")
    mismo = [c for c in cuentas if personas.nombres_compatibles(c["apellidos"], e["apellidos"])]
    opciones = mismo + [c for c in cuentas if c not in mismo]
    return modal(
        f"Vincular a {e['nombres']} {e['apellidos']}",
        fh.Form(P("Elija la cuenta de esta persona. Sus productos, actividades y proyectos pasarán a la cuenta; si "
                  "tiene periodos de estudiante, la ficha se conserva enlazada para guardarlos.", cls="text-sm mb-3"),
                fh.Select(*[fh.Option(f"{c['apellidos']}, {c['nombres']} · {c['email']}", value=str(c["id"]))
                            for c in opciones], name="usuario", cls="uk-select", aria_label="Cuenta"),
                Input(type="hidden", name="externo", value=str(eid)), Input(type="hidden", name="desde", value="tabla"),
                Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
                    boton_espera("Vincular", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2 mt-4"),
                hx_post="/personas/externos/vincular", hx_swap="none", hx_disabled_elt="find button[type='submit']",
                hx_confirm="¿Vincular? No se puede deshacer."))


@rt("/personas/externos/{eid}")
def put(auth, eid: int, institucion: str = "", pais: str = ""):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    personas.actualizar_externo(eid, institucion, pais)
    auditar(auth["id"], "editar_externo", "persona_externa", eid, pais)
    e = next((x for x in personas.externos() if x["id"] == eid), None)
    return fila_externo(e, _fusiona(auth)) if e else ""
