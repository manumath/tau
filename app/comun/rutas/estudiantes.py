"""Estudiantes y tesistas: lista, alta, ficha con periodos de estudio y participación en la
investigación. Los registran investigadores y administración (quedan en la auditoría)."""
from datetime import date

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Div, H3, HtmxResponseHeaders, Input, Li, Option, P, Redirect, Response,
                             Select, Span, Thead, Tr, Ul)
from fasthtml.toaster import add_toast
from monsterui.all import (H2, Button, ButtonT, Card, Form, FormLabel, LabelInput, Table, Tbody, Td, TextPresets, Th,
                           UkIcon)

from app.comun import estudiantes, permisos, personas
from app.comun.componentes.layout import ID_MODAL, JS_CERRAR, mensaje_error, modal, pagina
from app.comun.componentes.registros import insignia, url_filtrada
from app.comun.db import auditar, get_db, sin_tildes

rt = APIRouter()
ID_LISTA = "lista-estudiantes"


def _permitido(auth):
    return auth["es_investigador"] or permisos.puede(auth, "gestionar_estudiantes")


def _periodo_texto(p):
    return (f"{estudiantes.NIVELES[p['nivel']]} · {p['programa'] or ''} · {p['desde']}–{p['hasta'] or 'cursando'}"
            + (" · titulado(a)" if p["titulado"] else ""))


# --- Lista ---------------------------------------------------------------------------------------------------

def lista(q="", nivel="", estado=""):
    filas = []
    for e in estudiantes.listar(q, nivel, estado):
        part = e["participacion"]
        filas.append(Tr(
            Td(A(f"{e['apellidos']}, {e['nombres']}", href=f"/estudiantes/{e['id']}", cls="font-medium hover:underline"),
               Div(e["institucion"] or "", cls=TextPresets.muted_sm)),
            Td(Div(*[Div(_periodo_texto(p), cls="text-sm") for p in e["periodos"]])),
            Td(insignia("Cursando", "azul") if e["cursando"] else insignia("Egresado(a)", "gris")),
            Td(f"{part['tesis']} tesis · {part['productos']} productos · {part['proyectos']} proyectos · "
               f"{part['actividades']} actividades", cls="text-sm")))
    return Div(Table(Thead(Tr(Th("Estudiante"), Th("Estudios"), Th("Estado"), Th("Participación"))),
                     Tbody(*filas) if filas else Tbody(Tr(Td("No hay estudiantes registrados que coincidan.", colspan=4,
                                                             cls=(TextPresets.muted_sm, "text-center py-6")))),
                     cls="uk-table-divider uk-table-middle uk-table-hover"),
               id=ID_LISTA, cls="overflow-x-auto")


@rt("/estudiantes")
def get(auth, q: str = "", nivel: str = "", estado: str = ""):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    return pagina(
        "Estudiantes",
        Div(Div(H2("Estudiantes y tesistas"),
                P("Estudiantes que participan en la investigación del instituto: tesistas, coautores y participantes de "
                  "proyectos y actividades. Registre sus periodos de estudio para que los informes de acreditación "
                  "cuenten su participación (tesis, publicaciones, proyectos).", cls=(TextPresets.muted_sm, "max-w-3xl"))),
            Button(UkIcon("user-plus", height=16, width=16), "Registrar estudiante", cls=ButtonT.primary,
                   hx_get="/estudiantes/nuevo", hx_target=f"#{ID_MODAL}"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        fh.Form(Input(type="search", name="q", value=q, placeholder="Buscar por nombre…", cls="uk-input max-w-xs",
                      aria_label="Buscar estudiantes"),
                Select(Option("Todos los niveles", value=""),
                       *[Option(t, value=v, selected=v == nivel) for v, t in estudiantes.NIVELES.items()],
                       name="nivel", cls="uk-select w-48", aria_label="Nivel"),
                Select(Option("Cursando y egresados", value=""), Option("Cursando", value="cursando", selected=estado == "cursando"),
                       Option("Egresados", value="egresado", selected=estado == "egresado"),
                       name="estado", cls="uk-select w-52", aria_label="Estado"),
                hx_get="/estudiantes/lista", hx_target=f"#{ID_LISTA}", hx_swap="outerHTML",
                hx_trigger="input delay:300ms, change, search", onsubmit="return false", cls="flex flex-wrap gap-3 mb-4"),
        Card(lista(q, nivel, estado)),
        usuario=auth, seccion="investigadores")


@rt("/estudiantes/lista")
def get(auth, q: str = "", nivel: str = "", estado: str = ""):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    return lista(q, nivel, estado), HtmxResponseHeaders(replace_url=url_filtrada("/estudiantes", q=q, nivel=nivel,
                                                                                    estado=estado))


# --- Alta ----------------------------------------------------------------------------------------------------

def _campos_periodo(d, sufijo=""):
    anios = [str(a) for a in range(date.today().year + 1, 1969, -1)]
    return Div(
        Div(FormLabel("Nivel"), Select(Option("— Elija —", value=""),
                                     *[Option(t, value=v, selected=v == d.get("nivel")) for v, t in estudiantes.NIVELES.items()],
                                     name="nivel", cls="uk-select"), cls="space-y-1"),
        LabelInput("Programa", id=f"programa{sufijo}", name="programa", value=d.get("programa") or "",
                   placeholder="Por omisión: Licenciatura en Matemática (UMSA)"),
        Div(FormLabel("¿Del programa propio?"), Select(Option("Sí (Matemática, UMSA)", value="1",
                                                             selected=str(d.get("del_programa", "1")) != "0"),
                                                      Option("No (otra carrera o institución)", value="0",
                                                             selected=str(d.get("del_programa", "1")) == "0"),
                                                      name="del_programa", cls="uk-select"), cls="space-y-1"),
        Div(FormLabel("Ingreso"), Select(Option("—", value=""), *[Option(a, selected=a == str(d.get("desde") or "")) for a in anios],
                                        name="desde", cls="uk-select"), cls="space-y-1"),
        Div(FormLabel("Egreso"), Select(Option("Cursando", value=""), *[Option(a, selected=a == str(d.get("hasta") or "")) for a in anios],
                                       name="hasta", cls="uk-select"), cls="space-y-1"),
        Div(FormLabel("¿Se tituló?"), Select(Option("No / aún no", value="0", selected=not d.get("titulado")),
                                            Option("Sí", value="1", selected=bool(d.get("titulado"))),
                                            name="titulado", cls="uk-select"), cls="space-y-1"),
        cls="grid grid-cols-2 sm:grid-cols-3 gap-3 items-end")


def _form_nuevo(d=None, errores=()):
    d = d or {}
    return modal(
        "Registrar estudiante",
        Form(mensaje_error(*errores),
             P("Busque a la persona si ya figura en el portal (p. ej., como coautor); si no, escriba su nombre.",
               cls=TextPresets.muted_sm),
             Div(Input(type="search", name="persona_q", placeholder="Buscar persona externa por nombre…", autocomplete="off",
                       cls="uk-input", aria_label="Buscar persona", hx_get="/estudiantes/buscar-persona",
                       hx_trigger="input changed delay:250ms, search", hx_target="#personas-encontradas",
                       onkeydown="if(event.key==='Enter')event.preventDefault()"),
                 Div(id="personas-encontradas"), cls="relative"),
             Div(_elegida(d.get("externo_id")) if d.get("externo_id") else "", id="persona-elegida"),
             Div(LabelInput("Nombres", id="nombres", value=d.get("nombres") or ""),
                 LabelInput("Apellidos", id="apellidos", value=d.get("apellidos") or ""),
                 LabelInput("Correo (opcional)", id="email", type="email", value=d.get("email") or ""),
                 cls="grid grid-cols-1 sm:grid-cols-3 gap-3"),
             H3("Estudios", cls="text-base font-semibold"),
             _campos_periodo(d),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
                 Button("Registrar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post="/estudiantes", hx_target=f"#{ID_MODAL}", cls="space-y-4"),
        ancho="max-w-3xl")


def _elegida(externo_id):
    p = personas.por_ref(f"e:{externo_id}")
    if not p:
        return ""
    return Div(Input(type="hidden", name="externo_id", value=str(externo_id)),
               Span("Persona elegida: ", cls=TextPresets.muted_sm), Span(f"{p['nombres']} {p['apellidos']}", cls="font-medium"),
               Span(f" · {p['afiliacion']}" if p.get("afiliacion") else "", cls=TextPresets.muted_sm),
               fh.Button("Quitar", type="button", cls="text-sm text-primary hover:underline ml-2",
                         onclick="document.getElementById('persona-elegida').innerHTML=''"),
               cls="rounded-md border border-border px-3 py-2")


@rt("/estudiantes/nuevo")
def get(auth):
    return _form_nuevo() if _permitido(auth) else Response("No autorizado", status_code=403)


@rt("/estudiantes/buscar-persona")
def get(auth, persona_q: str = ""):
    if not _permitido(auth) or len(persona_q.strip()) < 2:
        return ""
    patron = f"%{sin_tildes(persona_q.strip())}%"
    filas = get_db().q("""SELECT id, nombres, apellidos, institucion FROM persona_externa WHERE usuario_id IS NULL
                          AND (sin_tildes(nombres || ' ' || apellidos) LIKE :p OR sin_tildes(apellidos || ' ' || nombres) LIKE :p)
                          ORDER BY sin_tildes(apellidos) LIMIT 8""", {"p": patron})
    if not filas:
        return Ul(Li(P("No figura: complete nombres y apellidos abajo.", cls=(TextPresets.muted_sm, "px-3 py-2"))),
                  cls="absolute z-30 w-full mt-1 rounded-md border border-border bg-background shadow-lg")
    return Ul(*[Li(fh.Button(Span(f"{f['nombres']} {f['apellidos']}", cls="font-medium"),
                             Span(f['institucion'] or "", cls=TextPresets.muted_sm), type="button",
                             cls="w-full text-left flex flex-col px-3 py-2 hover:bg-muted",
                             hx_get=f"/estudiantes/elegir/{f['id']}", hx_target="#persona-elegida",
                             hx_on__after_request="document.getElementById('personas-encontradas').innerHTML=''"))
                for f in filas],
              cls="absolute z-30 w-full mt-1 max-h-72 overflow-y-auto rounded-md border border-border bg-background "
                  "shadow-lg divide-y divide-border")


@rt("/estudiantes/elegir/{externo_id}")
def get(auth, externo_id: int):
    return _elegida(externo_id) if _permitido(auth) else Response("No autorizado", status_code=403)


@rt("/estudiantes")
def post(auth, sess, externo_id: str = "", nombres: str = "", apellidos: str = "", email: str = "", nivel: str = "",
         programa: str = "", del_programa: str = "1", desde: str = "", hasta: str = "", titulado: str = "0"):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    d = dict(externo_id=externo_id, nombres=nombres, apellidos=apellidos, email=email, nivel=nivel, programa=programa,
             del_programa=del_programa, desde=desde, hasta=hasta, titulado=titulado == "1")
    if externo_id.isdigit() and personas.por_ref(f"e:{externo_id}"):
        eid = int(externo_id)
    elif nombres.strip() and apellidos.strip():
        existente = personas.externo_similar(nombres, apellidos)
        eid = None if not existente else existente["id"]
    else:
        return _form_nuevo(d, ["Elija a la persona o escriba sus nombres y apellidos."])
    _, errores = estudiantes.validar({**d, "titulado": titulado}, eid or 0)
    if errores:
        return _form_nuevo(d, errores)
    if eid is None:
        externo = personas.crear_externo(nombres, apellidos, None, None, auth["id"])
        eid = externo["id"]
        if email.strip():
            get_db().execute("UPDATE persona_externa SET email = ? WHERE id = ?", [email.strip(), eid])
    estudiantes.agregar(eid, {**d, "titulado": titulado}, auth["id"])
    auditar(auth["id"], "registrar_estudiante", "persona_externa", eid, f"{nivel} {desde}")
    add_toast(sess, "Estudiante registrado.", "success")
    return Redirect(f"/estudiantes/{eid}")


# --- Ficha -------------------------------------------------------------------------------------------------------

def tarjeta_periodos(externo_id, auth, errores=(), editar=None, datos=None):
    filas = []
    for p in estudiantes.periodos(externo_id):
        if editar == p["id"]:
            filas.append(Tr(Td(Form(_campos_periodo({**p, **(datos or {})}, sufijo=f"-{p['id']}"),
                                    Div(Button("Cancelar", type="button", cls=(ButtonT.ghost, ButtonT.sm),
                                               hx_get=f"/estudiantes/{externo_id}/periodos", hx_target="#periodos",
                                               hx_swap="outerHTML"),
                                        Button("Guardar", type="submit", cls=(ButtonT.primary, ButtonT.sm)),
                                        cls="flex justify-end gap-2 mt-2"),
                                    hx_put=f"/estudiantes/periodo/{p['id']}", hx_target="#periodos", hx_swap="outerHTML"),
                               colspan=3)))
            continue
        filas.append(Tr(Td(_periodo_texto(p)),
                        Td("Del programa" if p["del_programa"] else "Otra carrera o institución", cls="text-sm"),
                        Td(Div(Button(UkIcon("pencil", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon),
                                      aria_label="Corregir", hx_get=f"/estudiantes/periodo/{p['id']}/editar",
                                      hx_target="#periodos", hx_swap="outerHTML"),
                               Button(UkIcon("trash-2", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon),
                                      aria_label="Eliminar", hx_delete=f"/estudiantes/periodo/{p['id']}",
                                      hx_target="#periodos", hx_swap="outerHTML",
                                      hx_confirm="¿Eliminar este periodo de estudios?"),
                               cls="flex justify-end"))))
    agregar = fh.Details(fh.Summary("Agregar otro periodo (p. ej., maestría después de la licenciatura)",
                                    cls="cursor-pointer text-sm text-primary"),
                         Form(_campos_periodo(datos or {} if editar is None else {}, sufijo="-nuevo"),
                              Div(Button("Agregar", type="submit", cls=(ButtonT.primary, ButtonT.sm)), cls="flex justify-end mt-2"),
                              hx_post=f"/estudiantes/{externo_id}/periodo", hx_target="#periodos", hx_swap="outerHTML",
                              cls="mt-2"),
                         open=bool(errores and editar is None), cls="rounded-md border border-border p-3")
    return Card(H3("Estudios", cls="text-base font-semibold mb-2"), mensaje_error(*errores),
                Table(Tbody(*filas), cls="uk-table-divider uk-table-small") if filas
                else P("Sin periodos registrados.", cls=TextPresets.muted_sm),
                agregar, id="periodos")


@rt("/estudiantes/{externo_id}")
def get(auth, externo_id: int):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    p = get_db().q("SELECT * FROM persona_externa WHERE id = ?", [externo_id])
    if not p:
        return pagina("No encontrado", P("Esa persona no existe."), usuario=auth)
    p = p[0]
    part = estudiantes.participacion(externo_id)
    return pagina(
        f"{p['nombres']} {p['apellidos']}",
        A(UkIcon("arrow-left", height=14, width=14), "Estudiantes", href="/estudiantes",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        H2(f"{p['nombres']} {p['apellidos']}"),
        P(" · ".join(x for x in (estudiantes.etiqueta(externo_id), p["institucion"], p["email"]) if x),
          cls=(TextPresets.muted_sm, "mb-6")),
        Div(tarjeta_periodos(externo_id, auth),
            Card(H3("Participación en la investigación", cls="text-base font-semibold mb-2"),
                 H3("Tesis y productos", cls="text-sm font-semibold mt-2"),
                 Ul(*[Li(A(x["titulo"], href=f"/productos/{x['id']}", cls="text-primary hover:underline"),
                         Span(f" · {x['tipo']} · {x['anio']}", cls=TextPresets.muted_sm)) for x in part["productos"]],
                    cls="space-y-1 text-sm") if part["productos"] else P("—", cls=TextPresets.muted_sm),
                 H3("Proyectos", cls="text-sm font-semibold mt-3"),
                 Ul(*[Li(A(x["nombre"], href=f"/proyectos/{x['id']}", cls="text-primary hover:underline"),
                         Span(f" · {x['rol']}", cls=TextPresets.muted_sm)) for x in part["proyectos"]],
                    cls="space-y-1 text-sm") if part["proyectos"] else P("—", cls=TextPresets.muted_sm),
                 H3("Actividades", cls="text-sm font-semibold mt-3"),
                 Ul(*[Li(A(x["titulo"], href=f"/actividades/{x['id']}", cls="text-primary hover:underline"),
                         Span(f" · {x['fecha_inicio']} · {x['rol']}", cls=TextPresets.muted_sm)) for x in part["actividades"]],
                    cls="space-y-1 text-sm") if part["actividades"] else P("—", cls=TextPresets.muted_sm)),
            cls="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"),
        usuario=auth, seccion="investigadores")


def _datos_periodo(nivel, programa, del_programa, desde, hasta, titulado):
    return dict(nivel=nivel, programa=programa, del_programa=del_programa, desde=desde, hasta=hasta, titulado=titulado)


@rt("/estudiantes/{externo_id}/periodos")
def get(auth, externo_id: int):
    return tarjeta_periodos(externo_id, auth) if _permitido(auth) else Response("No autorizado", status_code=403)


@rt("/estudiantes/{externo_id}/periodo")
def post(auth, externo_id: int, nivel: str = "", programa: str = "", del_programa: str = "1", desde: str = "",
         hasta: str = "", titulado: str = "0"):
    if not _permitido(auth):
        return Response("No autorizado", status_code=403)
    datos = _datos_periodo(nivel, programa, del_programa, desde, hasta, titulado)
    errores = estudiantes.agregar(externo_id, datos, auth["id"])
    if not errores:
        auditar(auth["id"], "agregar_periodo_estudiante", "persona_externa", externo_id, f"{nivel} {desde}")
    return tarjeta_periodos(externo_id, auth, errores, datos=datos if errores else None)


@rt("/estudiantes/periodo/{eid}/editar")
def get(auth, eid: int):
    p = estudiantes.obtener_periodo(eid)
    if not p or not _permitido(auth):
        return Response(status_code=404)
    return tarjeta_periodos(p["externo_id"], auth, editar=eid)


@rt("/estudiantes/periodo/{eid}")
def put(auth, eid: int, nivel: str = "", programa: str = "", del_programa: str = "1", desde: str = "", hasta: str = "",
        titulado: str = "0"):
    p = estudiantes.obtener_periodo(eid)
    if not p or not _permitido(auth):
        return Response(status_code=404)
    datos = _datos_periodo(nivel, programa, del_programa, desde, hasta, titulado)
    errores = estudiantes.editar(eid, datos)
    if not errores:
        auditar(auth["id"], "corregir_periodo_estudiante", "persona_externa", p["externo_id"], f"{nivel} {desde}")
    return tarjeta_periodos(p["externo_id"], auth, errores, editar=eid if errores else None, datos=datos if errores else None)


@rt("/estudiantes/periodo/{eid}")
def delete(auth, eid: int):
    p = estudiantes.obtener_periodo(eid)
    if not p or not _permitido(auth):
        return Response(status_code=404)
    estudiantes.eliminar(eid)
    auditar(auth["id"], "eliminar_periodo_estudiante", "persona_externa", p["externo_id"], str(eid))
    return tarjeta_periodos(p["externo_id"], auth)
