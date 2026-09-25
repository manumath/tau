"""Proyectos: lista, alta de proyectos individuales, ficha con pestañas, bandeja de pendientes y
reasignación del responsable (administración).

Patrones HTMX:
- Pestañas: cada una se pide a /proyectos/{id}/tab/{nombre}; el servidor fija ?tab= en la URL
  (HX-Replace-Url), así una pestaña se puede recargar o compartir.
- Tras aprobar o rechazar, la respuesta trae la bandeja actualizada, el contador de la pestaña
  fuera de banda y el evento `pendientes-cambiados` para el contador de la navegación.
"""
import json
from datetime import date

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Div, H3, HtmxResponseHeaders, Input, Li, Option, P,
                             Redirect, Response, Select, Span, Ul)
from fasthtml.toaster import add_toast
from monsterui.all import (H2, Button, ButtonT, Card, Form, FormLabel, LabelInput, LabelTextArea,
                           TextPresets, UkIcon)

from app import actividades, personas, productos, proyectos, usuarios
from app.components import personas as ui_personas
from app.components.layout import ID_MODAL, JS_CERRAR, mensaje_error, modal, pagina
from app.components.registros import dato, enlace_persona, insignia
from app.db import auditar, get_db

rt = APIRouter()

PESTANAS = {"resumen": "Resumen", "participantes": "Participantes", "actividades": "Actividades",
            "productos": "Productos", "pendientes": "Pendientes"}
ID_TAB = "tab-contenido"
EVENTO_PENDIENTES = "pendientes-cambiados"
TONO_ESTADO = {"formulacion": "ambar", "vigente": "verde", "finalizado": "gris"}


def insignia_tipo(p):
    if p["tipo"] == "institucional":
        return insignia("Institucional", "azul", icono="landmark")
    return insignia("Individual", "gris", icono="user-round")


def _proyecto_o_error(pid, auth, gestionar=False):
    """(proyecto, None) si el usuario puede verlo (o gestionarlo); (None, respuesta) si no."""
    p = proyectos.obtener(pid)
    if not p or not proyectos.puede_ver(pid, auth):
        return None, Response("No encontrado", status_code=404)
    if gestionar and not proyectos.puede_gestionar(pid, auth):
        return None, Response("No autorizado", status_code=403)
    return p, None


def _monto(p):
    if p["monto"] is None:
        return None
    return f"{p['moneda']} {p['monto']:,}".replace(",", ".")


def _periodo(p):
    if not p["fecha_inicio"]:
        return None
    ini = date.fromisoformat(p["fecha_inicio"]).strftime("%m/%Y")
    fin = date.fromisoformat(p["fecha_fin"]).strftime("%m/%Y") if p["fecha_fin"] else "…"
    return f"{ini} – {fin}"


# --- Lista de proyectos ---------------------------------------------------------------------------

def tarjeta(p):
    extra = [insignia_tipo(p), insignia(proyectos.ESTADOS[p["estado"]], TONO_ESTADO[p["estado"]])]
    if p.get("mi_rol"):
        extra.append(insignia(proyectos.ROLES[p["mi_rol"]] + ("" if p["vigente"] else " (anterior)"),
                              "azul", icono="user-round"))
    pendientes = proyectos.n_pendientes(p["id"]) if p.get("mi_rol") in proyectos.ROLES_RESPONSABLES \
        and p.get("vigente") else 0
    if pendientes:
        extra.append(insignia(f"{pendientes} por revisar", "ambar", icono="inbox"))
    return A(Card(
        Div(Span(p["codigo"] or "", cls="font-mono text-xs text-muted-foreground"),
            Span(_periodo(p) or "", cls=TextPresets.muted_sm), cls="flex justify-between"),
        H3(p["nombre"], cls="text-base font-semibold mt-1"),
        P(f"{p['n_part']} participante{'s' if p['n_part'] != 1 else ''}"
          + (f" · {p['fuente_financiamiento']}" if p["fuente_financiamiento"] else ""),
          cls=TextPresets.muted_sm),
        Div(*extra, cls="flex flex-wrap gap-1.5 mt-2"),
        cls="h-full hover:shadow-md transition"), href=f"/proyectos/{p['id']}", cls="block")


def seccion_propuestas(uid):
    propias = proyectos.mis_propuestas(uid)
    if not propias:
        return ""
    filas = []
    for v in propias:
        href = f"/{'actividades' if v['tipo'] == 'actividad' else 'productos'}/{v['registro_id']}"
        filas.append(Li(
            Div(A(v["titulo"], href=href, cls="font-medium hover:underline"),
                Span(f" → {v['proyecto']}", cls=TextPresets.muted_sm)),
            insignia("Pendiente", "ambar", icono="clock") if v["estado"] == "pendiente"
            else Div(insignia("Rechazado", "rojo", icono="circle-x"),
                     Span(f" «{v['comentario']}» — edítelo y guárdelo para volver a proponerlo.",
                          cls="text-sm")),
            cls="py-2 space-y-1"))
    return Card(H3("Mis propuestas en revisión", cls="text-base font-semibold"),
                Ul(*filas, cls="divide-y divide-border"), cls="mt-8")


def _filtro_tipo(tipo):
    opciones = [("", "Todos")] + list(proyectos.TIPOS.items())
    return Div(*[A(t, href=f"/proyectos?tipo={v}#todos" if v else "/proyectos#todos",
                   cls="text-sm px-3 py-1 rounded-full border " +
                       ("border-primary bg-primary/10 text-primary" if v == tipo else "border-border hover:bg-muted"))
                 for v, t in opciones], cls="flex gap-2 mb-4")


@rt("/proyectos")
def get(auth, q: str = "", tipo: str = ""):
    tipo = tipo if tipo in proyectos.TIPOS else ""
    mios = proyectos.de_investigador(auth["id"])
    bloques = [
        Div(Div(H2("Proyectos"),
                P("Proyectos de investigación en que participa. Desde el formulario de una actividad o "
                  "un producto puede proponerlo a sus proyectos; el responsable lo aprueba.",
                  cls=TextPresets.muted_sm)),
            Button(UkIcon("plus", height=16, width=16), "Nuevo proyecto individual", cls=ButtonT.primary,
                   hx_get="/proyectos/nuevo", hx_target=f"#{ID_MODAL}") if proyectos.puede_crear(auth) else "",
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        H3("Mis proyectos", cls="text-lg font-semibold mb-3") if auth["es_admin"] and auth["es_investigador"] else "",
        fh.Div(*[tarjeta(p) for p in mios], cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4")
        if mios else P("No participa en proyectos todavía.", cls=TextPresets.muted_sm)
        if auth["es_investigador"] else "",
        seccion_propuestas(auth["id"]),
    ]
    if auth["es_admin"]:
        todos = [p for p in proyectos.todos(q, tipo) if p["id"] not in {m["id"] for m in mios}]
        bloques += [H3("Todos los proyectos del instituto", id="todos", cls="text-lg font-semibold mt-10 mb-1"),
                    P("La administración los ve todos, pero solo los gestionan sus responsables. Desde la "
                      "ficha de un proyecto puede reasignar al responsable.", cls=(TextPresets.muted_sm, "mb-3")),
                    _filtro_tipo(tipo),
                    fh.Div(*[tarjeta(p) for p in todos],
                           cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4")
                    if todos else P("No hay otros proyectos.", cls=TextPresets.muted_sm)]
    return pagina("Proyectos", *bloques, usuario=auth, seccion="proyectos")


@rt("/proyectos/pendientes/contador")
def get(auth):
    """Contador de la navegación: propuestas que esta persona debe revisar."""
    n = proyectos.n_pendientes_para(auth) if auth["es_investigador"] else 0
    return insignia_contador(n)


def insignia_contador(n):
    return Span(str(n) if n else "", id="badge-pendientes",
                title=f"{n} propuesta(s) por revisar" if n else None,
                cls="ml-1 rounded-full bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5"
                    if n else "hidden",
                hx_get="/proyectos/pendientes/contador", hx_swap="outerHTML",
                hx_trigger=f"every 60s, {EVENTO_PENDIENTES} from:body")


# --- Alta y edición de datos -------------------------------------------------------------------------

def form_datos(d, errores=(), pid=None):
    def campo(etiqueta, nombre, **kw):
        return LabelInput(etiqueta, id=nombre, value="" if d.get(nombre) is None else d.get(nombre), **kw)

    return Form(
        P("Usted quedará como responsable: podrá agregar participantes y aprobar sus propuestas. "
          "Los proyectos institucionales no se crean aquí: se proponen en la convocatoria de septiembre.",
          cls=TextPresets.muted_sm) if not pid else "",
        mensaje_error(*errores),
        Div(campo("Nombre del proyecto", "nombre", required=True), cls="sm:col-span-2"),
        Div(Div(campo("Código", "codigo", placeholder="FONDECYT 1260001"), cls="sm:col-span-2"),
            Div(FormLabel("Estado", fr="estado"),
                Select(*[Option(t, value=v, selected=v == d.get("estado")) for v, t in proyectos.ESTADOS.items()],
                       id="estado", name="estado", cls="uk-select"), cls="space-y-2"),
            cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
        Div(campo("Inicio", "fecha_inicio", type="date"), campo("Término", "fecha_fin", type="date"),
            cls="grid grid-cols-2 gap-4"),
        Div(Div(campo("Fuente de financiamiento", "fuente_financiamiento"), cls="sm:col-span-2"),
            campo(f"Monto ({d.get('moneda') or 'CLP'})", "monto", inputmode="numeric"),
            cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
        LabelTextArea("Descripción", id="descripcion", value=d.get("descripcion") or "", rows=3),
        LabelTextArea("Objetivo general", id="objetivo_general", value=d.get("objetivo_general") or "",
                      rows=2),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost,
                   **({"hx_get": f"/proyectos/{pid}/tab/resumen", "hx_target": f"#{ID_TAB}"} if pid
                      else {"onclick": JS_CERRAR})),
            Button("Guardar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
        **({"hx_put": f"/proyectos/{pid}/datos", "hx_target": f"#{ID_TAB}"} if pid
           else {"hx_post": "/proyectos", "hx_target": f"#{ID_MODAL}"}),
        cls="space-y-4")


def _datos(nombre, codigo, estado, fecha_inicio, fecha_fin, fuente_financiamiento, monto, descripcion,
           objetivo_general):
    d = dict(nombre=nombre, codigo=codigo, estado=estado, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
             fuente_financiamiento=fuente_financiamiento, monto=monto, descripcion=descripcion,
             objetivo_general=objetivo_general)
    return {k: (v.strip() or None) if isinstance(v, str) else v for k, v in d.items()}


@rt("/proyectos/nuevo")
def get(auth):
    if not proyectos.puede_crear(auth):
        return Response("No autorizado", status_code=403)
    return modal("Nuevo proyecto individual", form_datos({"estado": "vigente"}), ancho="max-w-2xl")


@rt("/proyectos")
def post(auth, sess, nombre: str = "", codigo: str = "", estado: str = "", fecha_inicio: str = "",
         fecha_fin: str = "", fuente_financiamiento: str = "", monto: str = "", descripcion: str = "",
         objetivo_general: str = ""):
    if not proyectos.puede_crear(auth):
        return Response("No autorizado", status_code=403)
    d = _datos(nombre, codigo, estado, fecha_inicio, fecha_fin, fuente_financiamiento, monto,
               descripcion, objetivo_general)
    errores = proyectos.validar(d)
    if errores:
        return modal("Nuevo proyecto individual", form_datos(d, errores), ancho="max-w-2xl")
    pid = proyectos.crear(d, auth["id"], auth["id"], tipo="individual")
    auditar(auth["id"], "crear_proyecto", "proyecto", pid, d["nombre"])
    add_toast(sess, "Proyecto creado.", "success")
    return Redirect(f"/proyectos/{pid}")


@rt("/proyectos/{pid}/datos/editar")
def get(auth, pid: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    return error or Card(H3("Editar datos del proyecto", cls="text-base font-semibold mb-4"),
                         form_datos(p, pid=pid))


@rt("/proyectos/{pid}/datos")
def put(auth, sess, pid: int, nombre: str = "", codigo: str = "", estado: str = "",
        fecha_inicio: str = "", fecha_fin: str = "", fuente_financiamiento: str = "", monto: str = "",
        descripcion: str = "", objetivo_general: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    d = _datos(nombre, codigo, estado, fecha_inicio, fecha_fin, fuente_financiamiento, monto,
               descripcion, objetivo_general)
    errores = proyectos.validar({**d, "id": pid})
    if errores:
        return Card(H3("Editar datos del proyecto", cls="text-base font-semibold mb-4"),
                    form_datos({**p, **d}, errores, pid))
    proyectos.actualizar(pid, d)
    auditar(auth["id"], "editar_proyecto", "proyecto", pid)
    add_toast(sess, "Datos del proyecto guardados.", "success")
    # La cabecera muestra nombre y estado: se recarga la página completa.
    return Redirect(f"/proyectos/{pid}?tab=resumen")


# --- Pestaña: resumen y objetivos -----------------------------------------------------------------------

def tab_resumen(p, auth):
    pid = p["id"]
    gestiona = proyectos.puede_gestionar(pid, auth)
    objetivos = proyectos.objetivos(pid)
    editados = [r for r in proyectos.registros(pid, "producto") + proyectos.registros(pid, "actividad")
                if r["editado_despues"]]
    lista_obj = fh.Ol(*[Li(Div(Span(o["texto"], cls="flex-1"),
                            fh.Button(UkIcon("x", height=14, width=14), type="button",
                                      cls="p-1 rounded hover:bg-muted hover:text-red-600",
                                      hx_delete=f"/proyectos/{pid}/objetivos/{o['id']}",
                                      hx_target=f"#{ID_TAB}", hx_confirm="¿Quitar este objetivo?",
                                      aria_label="Quitar objetivo") if gestiona else "",
                            cls="flex gap-2 items-start")) for o in objetivos],
                   cls="list-decimal pl-5 space-y-1") if objetivos \
        else P("Sin objetivos específicos registrados.", cls=TextPresets.muted_sm)
    agregar_obj = fh.Form(
        Input(name="texto", placeholder="Nuevo objetivo específico…", cls="uk-input", required=True,
              aria_label="Nuevo objetivo específico"),
        Button("Agregar", type="submit", cls=(ButtonT.default, ButtonT.sm)),
        hx_post=f"/proyectos/{pid}/objetivos", hx_target=f"#{ID_TAB}",
        cls="flex gap-2 mt-3") if gestiona else ""
    return Div(
        Card(Div(H3("Datos", cls="text-base font-semibold"),
                 Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.ghost, ButtonT.sm),
                        hx_get=f"/proyectos/{pid}/datos/editar", hx_target=f"#{ID_TAB}")
                 if gestiona else "", cls="flex justify-between items-center mb-2"),
             dato("Código", p["codigo"]), dato("Periodo", _periodo(p)),
             dato("Financiamiento", p["fuente_financiamiento"]), dato("Monto", _monto(p)),
             dato("Descripción", P(p["descripcion"], cls="whitespace-pre-line") if p["descripcion"] else None),
             dato("Objetivo general", p["objetivo_general"])),
        Card(H3("Objetivos específicos", cls="text-base font-semibold mb-2"), lista_obj, agregar_obj),
        Card(H3("Editados después de aprobados", cls="text-base font-semibold mb-2"),
             P("Registros ya aprobados que sus autores modificaron después. Revíselos si corresponde.",
               cls=(TextPresets.muted_sm, "mb-2")),
             Ul(*[Li(_enlace_registro("producto" if "producto_id" in r else "actividad", r["registro_id"]),
                     cls="py-1") for r in editados])) if gestiona and editados else "",
        cls="space-y-6")


def _enlace_registro(tipo, rid):
    if tipo == "producto":
        x = productos.obtener(rid)
        return A(x["titulo"], href=f"/productos/{rid}", cls="text-primary hover:underline") if x else ""
    x = actividades.obtener(rid)
    return A(x["titulo"], href=f"/actividades/{rid}", cls="text-primary hover:underline") if x else ""


@rt("/proyectos/{pid}/objetivos")
def post(auth, pid: int, texto: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if texto.strip():
        proyectos.agregar_objetivo(pid, texto)
    return tab_resumen(p, auth)


@rt("/proyectos/{pid}/objetivos/{oid}")
def delete(auth, pid: int, oid: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    proyectos.quitar_objetivo(pid, oid)
    return tab_resumen(p, auth)


# --- Pestaña: participantes --------------------------------------------------------------------------------

def tab_participantes(p, auth):
    pid = p["id"]
    gestiona = proyectos.puede_gestionar(pid, auth)
    filas = []
    for x in proyectos.participantes(pid):
        # El rol «responsable» no se asigna ni se quita aquí: lo reasigna la administración.
        roles_permitidos = {k: v for k, v in proyectos.ROLES.items()
                            if k != "responsable" and x["rol"] != "responsable"}
        if not x["interno"]:
            roles_permitidos = {k: v for k, v in roles_permitidos.items()
                                if k not in proyectos.ROLES_RESPONSABLES}
        editable_rol = gestiona and x["vigente"] and (x["rol"] in roles_permitidos)
        rol = Select(*[Option(t, value=k, selected=k == x["rol"]) for k, t in roles_permitidos.items()],
                     name="rol", cls="uk-select h-8 w-48 text-sm", aria_label="Rol",
                     hx_post=f"/proyectos/{pid}/participantes/{x['participante_id']}/rol",
                     hx_trigger="change", hx_target=f"#{ID_TAB}") if editable_rol \
            else Span(proyectos.ROLES[x["rol"]], cls="text-sm")
        accion = ""
        if gestiona and x["rol"] != "responsable":
            accion = fh.Button(
                "Dar de baja" if x["vigente"] else "Reincorporar", type="button",
                cls="text-sm text-primary hover:underline",
                hx_post=f"/proyectos/{pid}/participantes/{x['participante_id']}/"
                        f"{'baja' if x['vigente'] else 'reincorporar'}",
                hx_target=f"#{ID_TAB}",
                hx_confirm=f"¿Dar de baja a {x['nombres']} {x['apellidos']}? Sus registros ya aprobados "
                           "seguirán en el proyecto." if x["vigente"] else None)
        filas.append(fh.Tr(
            fh.Td(enlace_persona(x), Span(" · externo", cls=TextPresets.muted_sm) if not x["interno"] else "",
                  P(x["afiliacion"] or "", cls=TextPresets.muted_sm) if x.get("afiliacion") else ""),
            fh.Td(rol),
            fh.Td(Span(f"desde {x['fecha_desde'] or '—'}" + (f" · hasta {x['fecha_hasta']}" if x["fecha_hasta"] else ""),
                       cls=TextPresets.muted_sm)),
            fh.Td(accion, cls="text-right"),
            cls="" if x["vigente"] else "opacity-60"))
    agregar = Div(
        H3("Agregar participante", cls="text-base font-semibold mb-2"),
        Div(Input(type="search", id="buscar-miembro", name="q", autocomplete="off", cls="uk-input",
                  placeholder="Buscar investigador o persona externa…", aria_label="Buscar participante",
                  hx_get=f"/proyectos/{pid}/participantes/buscar", hx_target="#resultados-miembro",
                  hx_trigger="input changed delay:250ms, search"),
            Div(id="resultados-miembro"), cls="relative max-w-xl"),
        cls="mt-6") if gestiona else ""
    return Card(fh.Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Persona"), fh.Th("Rol"), fh.Th("Periodo"), fh.Th(""))),
                                fh.Tbody(*filas), cls="uk-table uk-table-divider uk-table-middle"),
                       cls="overflow-x-auto"),
                agregar)


def _con_error(sess, error, p, auth):
    if error:
        add_toast(sess, error, "error")
    return tab_participantes(p, auth)


@rt("/proyectos/{pid}/participantes/buscar")
def get(auth, pid: int, q: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if len(q.strip()) < 2:
        return ""
    ya = {x["ref"] for x in proyectos.participantes(pid)}
    encontradas = personas.buscar(q, excluir=ya)
    opciones = [Li(fh.Button(
        Span(f"{x['nombres']} {x['apellidos']}", cls="font-medium"),
        Span(("Instituto" if x["interno"] else "Externo") + (f" · {x['afiliacion']}" if x.get("afiliacion") else ""),
             cls=TextPresets.muted_sm),
        type="button", cls="w-full text-left flex flex-col px-3 py-2 hover:bg-muted",
        hx_post=f"/proyectos/{pid}/participantes", hx_vals=json.dumps({"ref": x["ref"]}),
        hx_target=f"#{ID_TAB}")) for x in encontradas]
    opciones.append(Li(fh.Button(
        UkIcon("user-plus", height=14, width=14), f"Registrar a «{q.strip()}» como persona externa",
        type="button", cls="w-full text-left flex items-center gap-2 px-3 py-2 text-primary hover:bg-muted",
        hx_get=f"/proyectos/{pid}/participantes/externo", hx_vals=json.dumps({"q": q.strip()}),
        hx_target="#resultados-miembro")))
    return Ul(*opciones, cls="absolute z-30 w-full mt-1 max-h-72 overflow-y-auto rounded-md border "
                             "border-border bg-background shadow-lg divide-y divide-border")


@rt("/proyectos/{pid}/participantes/externo")
def get(auth, pid: int, q: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    return ui_personas.form_externo("miembro", q, url=f"/proyectos/{pid}/participantes/externo",
                                    destino=f"#{ID_TAB}")


@rt("/proyectos/{pid}/participantes/externo")
def post(auth, sess, pid: int, ext_nombres: str = "", ext_apellidos: str = "", ext_institucion: str = "",
         ext_pais: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if not ext_nombres.strip() or not ext_apellidos.strip():
        return _con_error(sess, "Nombres y apellidos son obligatorios.", p, auth)
    externo = personas.externo_similar(ext_nombres, ext_apellidos) or personas.crear_externo(
        ext_nombres, ext_apellidos, ext_institucion, ext_pais, auth["id"])
    error = proyectos.agregar_participante(pid, f"e:{externo['id']}", "colaborador", False)
    return _con_error(sess, error, p, auth)


@rt("/proyectos/{pid}/participantes")
def post(auth, sess, pid: int, ref: str = "", rol: str = "co_investigador"):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    if ref.startswith("e:") and rol == "co_investigador":
        rol = "colaborador"
    error = proyectos.agregar_participante(pid, ref, rol, False)
    if not error:
        auditar(auth["id"], "agregar_participante", "proyecto", pid, ref)
    return _con_error(sess, error, p, auth)


@rt("/proyectos/{pid}/participantes/{part_id}/rol")
def post(auth, sess, pid: int, part_id: int, rol: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    error = proyectos.cambiar_rol(pid, part_id, rol, False)
    if not error:
        auditar(auth["id"], "cambiar_rol", "proyecto", pid, f"{part_id}:{rol}")
    return _con_error(sess, error, p, auth)


@rt("/proyectos/{pid}/participantes/{part_id}/baja")
def post(auth, sess, pid: int, part_id: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    error = proyectos.dar_de_baja(pid, part_id, False)
    if not error:
        auditar(auth["id"], "baja_participante", "proyecto", pid, str(part_id))
    return _con_error(sess, error, p, auth)


@rt("/proyectos/{pid}/participantes/{part_id}/reincorporar")
def post(auth, sess, pid: int, part_id: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    proyectos.reincorporar(pid, part_id)
    return tab_participantes(p, auth)


# --- Pestañas: actividades y productos aprobados ---------------------------------------------------------------

def _boton_registrar(p, auth, tipo):
    if not proyectos.rol_de(p["id"], auth["id"]) or p["estado"] == "finalizado":
        return ""
    ruta = "/actividades/nueva" if tipo == "actividad" else "/productos/nuevo"
    texto = "Registrar actividad del proyecto" if tipo == "actividad" else "Registrar producto del proyecto"
    return Button(UkIcon("plus", height=14, width=14), texto, cls=(ButtonT.default, ButtonT.sm),
                  hx_get=f"{ruta}?proyecto={p['id']}", hx_target=f"#{ID_MODAL}")


def _desvincular(p, tipo, rid, gestiona):
    if not gestiona:
        return ""
    return fh.Button(UkIcon("unlink", height=14, width=14), type="button", title="Desvincular del proyecto",
                     aria_label="Desvincular del proyecto",
                     cls="p-1 rounded hover:bg-muted hover:text-red-600",
                     hx_post=f"/proyectos/{p['id']}/{tipo}/{rid}/desvincular", hx_target=f"#{ID_TAB}",
                     hx_confirm="¿Desvincular del proyecto? El registro sigue en el perfil de sus autores.")


def _escuchar(pid, tab, evento):
    """Recarga la pestaña si se registra algo desde el modal (p. ej. «Registrar … del proyecto»)."""
    return Div(hx_get=f"/proyectos/{pid}/tab/{tab}", hx_trigger=f"{evento} from:body",
               hx_target=f"#{ID_TAB}", cls="hidden")


def tab_actividades(p, auth):
    pid = p["id"]
    gestiona = proyectos.puede_gestionar(pid, auth)
    vigentes = proyectos.participantes(pid, solo_vigentes=True)
    filas = []
    for v in proyectos.registros(pid, "actividad"):
        a = actividades.obtener(v["registro_id"])
        if gestiona:
            responsable = Select(Option("— Sin responsable —", value=""),
                                 *[Option(f"{x['nombres']} {x['apellidos']}", value=str(x["participante_id"]),
                                          selected=x["participante_id"] == v["responsable_participante_id"])
                                   for x in vigentes],
                                 name="responsable", cls="uk-select h-8 text-sm w-56",
                                 aria_label="Responsable de la actividad",
                                 hx_post=f"/proyectos/{pid}/actividad/{a['id']}/responsable",
                                 hx_trigger="change", hx_target=f"#{ID_TAB}")
        else:
            r = next((x for x in proyectos.participantes(pid)
                      if x["participante_id"] == v["responsable_participante_id"]), None)
            responsable = Span(f"Responsable: {r['nombres']} {r['apellidos']}" if r else "",
                               cls=TextPresets.muted_sm)
        filas.append(Div(
            Div(actividades.fechas_texto(a), cls="text-sm text-muted-foreground w-28 shrink-0"),
            Div(A(a["titulo"], href=f"/actividades/{a['id']}", cls="block font-medium hover:underline"),
                Div(insignia(a["tipo"]), insignia(actividades.AMBITOS[a["ambito"]], "azul"),
                    insignia("editada después de aprobada", "ambar", icono="pencil") if v["editado_despues"] else "",
                    cls="flex flex-wrap gap-1.5"),
                cls="flex-1 min-w-0 space-y-1"),
            responsable, _desvincular(p, "actividad", a["id"], gestiona),
            cls="flex flex-wrap items-center gap-3 py-3"))
    return Card(_escuchar(pid, "actividades", "actividades-cambiadas"),
                Div(P(f"{len(filas)} actividad{'es' if len(filas) != 1 else ''} aprobada"
                      f"{'s' if len(filas) != 1 else ''}", cls=TextPresets.muted_sm),
                    _boton_registrar(p, auth, "actividad"), cls="flex justify-between items-center mb-2"),
                Div(*filas, cls="divide-y divide-border") if filas
                else P("Aún no hay actividades aprobadas.", cls=(TextPresets.muted_sm, "py-4")))


def tab_productos(p, auth):
    pid = p["id"]
    gestiona = proyectos.puede_gestionar(pid, auth)
    from app.routes.productos import insignias as insignias_producto
    filas, n_informe = [], 0
    for v in proyectos.registros(pid, "producto"):
        x = productos.obtener(v["registro_id"])
        n_informe += productos.cuenta_para_informe(x)
        filas.append(Div(
            Div(str(x["anio"]), cls="font-mono text-sm text-muted-foreground w-12 shrink-0"),
            Div(A(x["titulo"], href=f"/productos/{x['id']}", cls="block font-medium hover:underline"),
                P(", ".join(f"{a['nombres']} {a['apellidos']}" for a in x["autores"]), cls="text-sm"),
                Div(insignias_producto(x),
                    insignia("editado después de aprobado", "ambar", icono="pencil") if v["editado_despues"] else "",
                    cls="flex flex-wrap gap-1.5"),
                cls="flex-1 min-w-0 space-y-1"),
            _desvincular(p, "producto", x["id"], gestiona),
            cls="flex items-start gap-3 py-3"))
    return Card(_escuchar(pid, "productos", "productos-cambiados"),
                Div(P(f"{len(filas)} producto{'s' if len(filas) != 1 else ''} aprobado"
                      f"{'s' if len(filas) != 1 else ''} · {n_informe} para el informe",
                      cls=TextPresets.muted_sm),
                    _boton_registrar(p, auth, "producto"), cls="flex justify-between items-center mb-2"),
                Div(*filas, cls="divide-y divide-border") if filas
                else P("Aún no hay productos aprobados.", cls=(TextPresets.muted_sm, "py-4")))


@rt("/proyectos/{pid}/actividad/{rid}/responsable")
def post(auth, sess, pid: int, rid: int, responsable: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    error = proyectos.asignar_responsable_actividad(rid, pid, int(responsable) if responsable.isdigit() else None)
    if error:
        add_toast(sess, error, "error")
    return tab_actividades(p, auth)


@rt("/proyectos/{pid}/{tipo}/{rid}/desvincular")
def post(auth, sess, pid: int, tipo: str, rid: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error or tipo not in proyectos.TABLAS:
        return error or Response(status_code=404)
    proyectos.desvincular(tipo, rid, pid)
    auditar(auth["id"], "desvincular", tipo, rid, f"proyecto {pid}")
    add_toast(sess, "Registro desvinculado del proyecto.", "success")
    return tab_actividades(p, auth) if tipo == "actividad" else tab_productos(p, auth)


# --- Pestaña: pendientes -----------------------------------------------------------------------------------------

def _tarjeta_pendiente(p, tipo, v, vigentes):
    pid, rid = p["id"], v["registro_id"]
    if tipo == "producto":
        x = productos.obtener(rid)
        titulo = A(x["titulo"], href=f"/productos/{rid}", target="_blank", cls="font-medium hover:underline")
        detalle = P(productos.cita(x), cls="text-sm")
        etiqueta = insignia(x["tipo"])
    else:
        x = actividades.obtener(rid)
        titulo = A(x["titulo"], href=f"/actividades/{rid}", target="_blank", cls="font-medium hover:underline")
        detalle = P(f"{actividades.fechas_texto(x)} · "
                    + ", ".join(y for y in (x["institucion"], x["lugar"], x["pais"]) if y), cls="text-sm")
        etiqueta = insignia(x["tipo"])
    caja_id = f"pendiente-{tipo}-{rid}"
    responsable = Div(FormLabel("Responsable de la actividad (opcional)", fr=f"resp-{rid}"),
                      Select(Option("— Sin responsable —", value=""),
                             *[Option(f"{y['nombres']} {y['apellidos']}", value=str(y["participante_id"]),
                                      selected=y["id"] == v["propuesto_por"] and y["interno"])
                               for y in vigentes],
                             id=f"resp-{rid}", name="responsable", cls="uk-select h-9 text-sm"),
                      cls="space-y-1 max-w-sm") if tipo == "actividad" else ""
    fuera = insignia("Fuera del periodo del proyecto", "ambar", icono="triangle-alert") \
        if proyectos.fuera_de_periodo(p, tipo, x) else ""
    return Card(
        Div(etiqueta, fuera, Span(f"Propuesto por {v['propuesto_por_nombre']}", cls=TextPresets.muted_sm),
            cls="flex flex-wrap items-center gap-2"),
        Div(titulo, detalle, cls="space-y-1 my-2"),
        responsable,
        Div(Button(UkIcon("check", height=14, width=14), "Aprobar", cls=(ButtonT.primary, ButtonT.sm),
                   hx_post=f"/proyectos/{pid}/pendientes/{tipo}/{rid}/aprobar", hx_include=f"#{caja_id}",
                   hx_target=f"#{ID_TAB}"),
            Button(UkIcon("x", height=14, width=14), "Rechazar…", cls=(ButtonT.ghost, ButtonT.sm),
                   hx_get=f"/proyectos/{pid}/pendientes/{tipo}/{rid}/rechazar", hx_target=f"#motivo-{tipo}-{rid}"),
            cls="flex gap-2 mt-3"),
        Div(id=f"motivo-{tipo}-{rid}"),
        id=caja_id)


def tab_pendientes(p, auth):
    pid = p["id"]
    vigentes = proyectos.participantes(pid, solo_vigentes=True)
    tarjetas = [_tarjeta_pendiente(p, "actividad", v, vigentes)
                for v in proyectos.registros(pid, "actividad", "pendiente")]
    tarjetas += [_tarjeta_pendiente(p, "producto", v, vigentes)
                 for v in proyectos.registros(pid, "producto", "pendiente")]
    return Div(
        P("Actividades y productos que los participantes proponen para el proyecto. Al aprobarlos pasan "
          "a formar parte de él; si los rechaza, indique el motivo: quien los propuso lo verá.",
          cls=(TextPresets.muted_sm, "mb-4")),
        Div(*tarjetas, cls="space-y-4") if tarjetas
        else Card(P(UkIcon("inbox", height=16, width=16, cls="inline mr-2"), "No hay propuestas pendientes.",
                    cls=(TextPresets.muted_sm, "text-center py-6"))))


def _tras_revision(p, auth):
    """Bandeja actualizada + contador de la pestaña (fuera de banda) + evento para la navegación."""
    return (tab_pendientes(p, auth), contador_pestana(p["id"], oob=True),
            HtmxResponseHeaders(trigger=EVENTO_PENDIENTES))


@rt("/proyectos/{pid}/pendientes/{tipo}/{rid}/aprobar")
def post(auth, sess, pid: int, tipo: str, rid: int, responsable: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error or tipo not in proyectos.TABLAS:
        return error or Response(status_code=404)
    error = proyectos.aprobar(tipo, rid, pid, auth["id"], int(responsable) if responsable.isdigit() else None)
    if error:
        add_toast(sess, error, "error")
    else:
        auditar(auth["id"], "aprobar", tipo, rid, f"proyecto {pid}")
        add_toast(sess, "Aprobado: ya forma parte del proyecto.", "success")
    return _tras_revision(p, auth)


@rt("/proyectos/{pid}/pendientes/{tipo}/{rid}/rechazar")
def get(auth, pid: int, tipo: str, rid: int):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error:
        return error
    return fh.Form(
        LabelTextArea("Motivo del rechazo", id=f"comentario-{tipo}-{rid}", name="comentario", rows=2,
                      required=True, placeholder="Por ejemplo: el artículo no menciona el financiamiento del proyecto."),
        Div(Button("Cancelar", type="button", cls=(ButtonT.ghost, ButtonT.sm),
                   onclick=f"document.getElementById('motivo-{tipo}-{rid}').innerHTML=''"),
            Button("Rechazar", type="submit", cls=(ButtonT.destructive, ButtonT.sm)),
            cls="flex justify-end gap-2"),
        hx_post=f"/proyectos/{pid}/pendientes/{tipo}/{rid}/rechazar", hx_target=f"#{ID_TAB}",
        cls="space-y-2 mt-3 rounded-md border border-border p-3")


@rt("/proyectos/{pid}/pendientes/{tipo}/{rid}/rechazar")
def post(auth, sess, pid: int, tipo: str, rid: int, comentario: str = ""):
    p, error = _proyecto_o_error(pid, auth, gestionar=True)
    if error or tipo not in proyectos.TABLAS:
        return error or Response(status_code=404)
    error = proyectos.rechazar(tipo, rid, pid, auth["id"], comentario)
    if error:
        add_toast(sess, error, "error")
    else:
        auditar(auth["id"], "rechazar", tipo, rid, f"proyecto {pid}: {comentario.strip()}")
        add_toast(sess, "Propuesta rechazada. Quien la propuso verá el motivo.", "success")
    return _tras_revision(p, auth)


# --- Página del proyecto -----------------------------------------------------------------------------------------

def contador_pestana(pid, oob=False):
    n = proyectos.n_pendientes(pid)
    return Span(str(n) if n else "", id="contador-pestana-pendientes",
                cls="ml-1 rounded-full bg-amber-500 text-white text-[10px] font-bold px-1.5" if n else "hidden",
                hx_swap_oob="true" if oob else None)


def _contenido_pestana(p, auth, tab):
    return {"resumen": tab_resumen, "participantes": tab_participantes, "actividades": tab_actividades,
            "productos": tab_productos, "pendientes": tab_pendientes}[tab](p, auth)


def _pestanas_visibles(pid, auth):
    return [t for t in PESTANAS if t != "pendientes" or proyectos.puede_gestionar(pid, auth)]


def nav_pestanas(p, auth, activa):
    enlaces = []
    for t in _pestanas_visibles(p["id"], auth):
        enlaces.append(Li(A(PESTANAS[t], contador_pestana(p["id"]) if t == "pendientes" else "",
                            href=f"/proyectos/{p['id']}?tab={t}",
                            hx_get=f"/proyectos/{p['id']}/tab/{t}", hx_target=f"#{ID_TAB}",
                            # Marca la pestaña activa en el navegador, sin volver a pedir la barra.
                            hx_on__before_request="this.closest('ul').querySelectorAll('li')"
                                                  ".forEach(li=>li.classList.remove('uk-active'));"
                                                  "this.parentElement.classList.add('uk-active')"),
                          cls="uk-active" if t == activa else ""))
    return fh.Ul(*enlaces, cls="uk-tab mb-6")


@rt("/proyectos/{pid}/tab/{tab}")
def get(auth, pid: int, tab: str):
    p, error = _proyecto_o_error(pid, auth)
    if error:
        return error
    if tab not in _pestanas_visibles(pid, auth):
        tab = "resumen"
    return _contenido_pestana(p, auth, tab), HtmxResponseHeaders(replace_url=f"/proyectos/{pid}?tab={tab}")


@rt("/proyectos/{pid}")
def get(auth, pid: int, tab: str = "resumen"):
    p, error = _proyecto_o_error(pid, auth)
    if error:
        return pagina("No encontrado", P("El proyecto no existe o no participa en él."), usuario=auth)
    if tab not in _pestanas_visibles(pid, auth):
        tab = "resumen"
    responsables = proyectos.responsables(pid)
    return pagina(
        p["nombre"],
        A(UkIcon("arrow-left", height=14, width=14), "Proyectos", href="/proyectos",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(Div(Div(insignia_tipo(p), insignia(proyectos.ESTADOS[p["estado"]], TONO_ESTADO[p["estado"]]),
                    Span(p["codigo"] or "", cls="font-mono text-sm text-muted-foreground"),
                    cls="flex items-center gap-2"),
                A(UkIcon("file-text", height=14, width=14), "Informe", href=f"/proyectos/{pid}/informe",
                  cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1"),
                cls="flex items-center justify-between gap-2"),
            H2(p["nombre"], cls="mt-2"),
            Div(P("Responsable: " + ", ".join(f"{r['nombres']} {r['apellidos']}" for r in responsables)
                  if responsables else "Sin responsable vigente.", cls=TextPresets.muted_sm),
                fh.Button(UkIcon("user-cog", height=14, width=14), "Reasignar responsable", type="button",
                          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline",
                          hx_get=f"/proyectos/{pid}/responsable", hx_target=f"#{ID_MODAL}")
                if proyectos.puede_reasignar(auth) else "",
                cls="flex flex-wrap items-center gap-x-4 gap-y-1"),
            cls="mb-6"),
        nav_pestanas(p, auth, tab),
        # Las pestañas de actividades/productos se refrescan si se registra algo desde el modal.
        Div(_contenido_pestana(p, auth, tab), id=ID_TAB),
        usuario=auth, seccion="proyectos")


# --- Reasignar responsable (administración) --------------------------------------------------------------

def form_reasignar(p, errores=(), nuevo="", anterior="co_investigador"):
    actuales = {r["id"] for r in proyectos.responsables(p["id"])}
    candidatos = [u for u in usuarios.listar() if u["es_investigador"] and u["activo"] and u["id"] not in actuales]
    return modal(
        "Reasignar responsable",
        Form(mensaje_error(*errores),
             P("Úselo cuando el responsable deja el instituto o el proyecto cambia de manos. Los registros "
               "ya aprobados siguen en el proyecto.", cls=TextPresets.muted_sm),
             Div(FormLabel("Nuevo responsable", fr="nuevo"),
                 Select(Option("— Seleccione —", value=""),
                        *[Option(f"{u['apellidos']}, {u['nombres']}", value=str(u["id"]),
                                 selected=str(u["id"]) == nuevo) for u in candidatos],
                        id="nuevo", name="nuevo", cls="uk-select"), cls="space-y-2"),
             Div(FormLabel("El responsable actual"),
                 *[fh.Label(Input(type="radio", name="anterior", value=v, checked=v == anterior, cls="uk-radio"),
                            Span(t, cls="text-sm"), cls="flex items-center gap-2")
                   for v, t in (("co_investigador", "sigue en el proyecto como co-investigador(a)"),
                                ("baja", "deja el proyecto (se le da de baja con fecha de hoy)"))],
                 cls="space-y-2"),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
                 Button("Reasignar", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post=f"/proyectos/{p['id']}/responsable", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt("/proyectos/{pid}/responsable")
def get(auth, pid: int):
    p = proyectos.obtener(pid)
    if not p or not proyectos.puede_reasignar(auth):
        return Response("No autorizado", status_code=403)
    return form_reasignar(p)


@rt("/proyectos/{pid}/responsable")
def post(auth, sess, pid: int, nuevo: str = "", anterior: str = "co_investigador"):
    p = proyectos.obtener(pid)
    if not p or not proyectos.puede_reasignar(auth):
        return Response("No autorizado", status_code=403)
    error = proyectos.reasignar_responsable(pid, int(nuevo), anterior) if nuevo.isdigit() \
        else "Seleccione al nuevo responsable."
    if error:
        return form_reasignar(p, [error], nuevo, anterior)
    auditar(auth["id"], "reasignar_responsable", "proyecto", pid, f"{nuevo} (anterior: {anterior})")
    add_toast(sess, "Responsable reasignado.", "success")
    return Redirect(f"/proyectos/{pid}?tab=participantes")
