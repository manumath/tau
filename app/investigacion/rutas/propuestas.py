"""Propuestas de proyectos institucionales: editor, envío, decisión y bandeja de la administración.

Patrones HTMX:
- El editor es un solo formulario. «Guardar borrador» (PUT) y «Enviar» (POST …/enviar) mandan
  el formulario completo; la respuesta reemplaza el editor (#editor-propuesta) o redirige.
- Objetivos y actividades previstas son filas repetibles: «Agregar» pide una fila nueva al
  servidor (hx-swap=beforeend) y «Quitar» la elimina en el navegador. Al guardar, las listas
  llegan como campos repetidos (objetivo, act_desc, act_mes) en el orden de la página.
"""
import json

import fasthtml.common as fh
from fasthtml.common import (A, APIRouter, Div, H3, Input, Li, Option, P, Redirect, Response, Select, Span,
                             Strong, Textarea, Ul)
from fasthtml.toaster import add_toast
from monsterui.all import H2, Button, ButtonT, Card, Form, FormLabel, LabelInput, TextPresets, UkIcon

from app.comun import permisos
from app.investigacion import institucionales as inst
from app.investigacion import lineas, proyectos
from app.investigacion.componentes.lineas import casillas_lineas
from app.comun.componentes.layout import ID_MODAL, JS_CERRAR, mensaje_error, modal, pagina
from app.comun.componentes.perfil import texto_con_parrafos
from app.comun.componentes.registros import dato, insignia
from app.comun.db import auditar
from app.comun.rutas.admin_usuarios import fecha_local

rt = APIRouter()

ID_EDITOR = "editor-propuesta"
TONO = {"borrador": "gris", "enviada": "azul", "aceptada": "verde", "condicional": "ambar",
        "rechazada": "rojo", "retirada": "gris"}
ICONO = {"borrador": "pencil", "enviada": "send", "aceptada": "circle-check", "condicional": "circle-alert",
         "rechazada": "circle-x", "retirada": "undo-2"}


def insignia_estado(estado):
    return insignia(inst.ESTADOS[estado], TONO[estado], icono=ICONO[estado])


def _prop_o_error(prop_id, auth):
    prop = inst.obtener(prop_id)
    if not prop or not inst.puede_ver(prop, auth):
        return None, Response("No encontrado", status_code=404)
    return prop, None


# --- Convocatoria y listas (usadas también en /proyectos) ------------------------------------------------

def aviso_convocatoria(auth):
    """Franja con la convocatoria abierta (o la próxima) y el botón para proponer."""
    abierto = inst.periodo_abierto()
    periodo = abierto if abierto is not None else inst.periodo_objetivo()
    p = inst.plazo(periodo)
    if abierto is not None:
        texto = (f"Convocatoria de proyectos institucionales {inst.periodo_texto(periodo)} abierta hasta el "
                 f"{inst.fecha_texto(p['cierra'])}. Las propuestas pueden ser de continuidad o de un proyecto nuevo.")
    else:
        texto = (f"Próxima convocatoria de proyectos institucionales ({inst.periodo_texto(periodo)}): del "
                 f"{inst.fecha_texto(p['abre'])} al {inst.fecha_texto(p['cierra'])}. Puede preparar el borrador desde ya.")
    boton = Button(UkIcon("landmark", height=16, width=16), "Proponer proyecto institucional",
                   cls=ButtonT.primary if abierto is not None else ButtonT.default,
                   hx_get="/propuestas/nueva", hx_target=f"#{ID_MODAL}") if inst.puede_proponer(auth) else ""
    return Div(Div(UkIcon("megaphone", height=18, width=18, cls="shrink-0 mt-0.5"), P(texto, cls="text-sm"),
                   cls="flex gap-2"), boton,
               cls="flex flex-wrap items-center justify-between gap-3 rounded-md border border-primary/30 "
                   "bg-primary/5 p-4 mb-6")


def lista_propuestas(props, con_proyecto=False):
    return Ul(*[Li(
        Div(A(p["nombre"], href=f"/propuestas/{p['id']}", cls="font-medium hover:underline"),
            Span(f" · {inst.MODALIDADES[p['modalidad']].lower()} · {inst.periodo_texto(p['periodo'])}",
                 cls=TextPresets.muted_sm)),
        Div(insignia_estado(p["estado"]),
            Span(f" {p['comentario']}", cls="text-sm") if p["estado"] in ("condicional", "rechazada")
            and p["comentario"] else "", cls="mt-1"),
        cls="py-2") for p in props], cls="divide-y divide-border")


def seccion_mis_propuestas(auth):
    props = inst.mis_propuestas(auth["id"])
    if not props:
        return ""
    return Card(H3("Mis propuestas institucionales", cls="text-base font-semibold"), lista_propuestas(props),
                cls="mt-8")


# --- Nueva propuesta y continuidad -------------------------------------------------------------------------

def _form_nueva(nombre="", error=None):
    periodo = inst.periodo_objetivo()
    return modal(
        "Proponer proyecto institucional",
        Form(mensaje_error(*([error] if error else [])),
             P(f"La propuesta es para el periodo {inst.periodo_texto(periodo)} "
               f"({inst.periodo_largo(periodo)}). Usted quedará como responsable. Primero se crea un borrador "
               "que puede completar con calma; la administración solo lo ve cuando usted lo envía.",
               cls=TextPresets.muted_sm),
             LabelInput("Nombre del proyecto", id="nombre", value=nombre, required=True, maxlength=300),
             Div(Button("Cancelar", type="button", cls=ButtonT.ghost, onclick=JS_CERRAR),
                 Button("Crear borrador", type="submit", cls=ButtonT.primary), cls="flex justify-end gap-2"),
             hx_post="/propuestas", hx_target=f"#{ID_MODAL}", cls="space-y-4"))


@rt("/propuestas/nueva")
def get(auth):
    if not inst.puede_proponer(auth):
        return Response("No autorizado", status_code=403)
    return _form_nueva()


@rt("/propuestas")
def post(auth, sess, nombre: str = ""):
    prop_id, error = inst.crear_nuevo(auth, nombre)
    if error:
        if not inst.puede_proponer(auth):
            return Response(error, status_code=403)
        return _form_nueva(nombre, error)
    prop = inst.obtener(prop_id)
    auditar(auth["id"], "crear_propuesta", "proyecto", prop["proyecto_id"], f"{prop['nombre']} ({prop['periodo']})")
    add_toast(sess, "Borrador creado. Complételo y envíelo dentro del plazo.", "success")
    return Redirect(f"/propuestas/{prop_id}")


@rt("/proyectos/{pid}/continuidad")
def post(auth, sess, pid: int):
    prop_id, error = inst.crear_continuidad(pid, auth)
    if error:
        add_toast(sess, error, "error")
        return Redirect(f"/proyectos/{pid}")
    auditar(auth["id"], "crear_propuesta", "proyecto", pid, "continuidad")
    return Redirect(f"/propuestas/{prop_id}")


# --- Editor ----------------------------------------------------------------------------------------------

def _boton_quitar(etiqueta):
    return fh.Button(UkIcon("x", height=14, width=14), type="button", aria_label=etiqueta, title=etiqueta,
                     cls="p-2 rounded hover:bg-muted hover:text-red-600 shrink-0",
                     onclick="this.closest('.fila-repetible').remove()")


def fila_objetivo(texto=""):
    return Div(Input(name="objetivo", value=texto, cls="uk-input", placeholder="Objetivo específico…",
                     aria_label="Objetivo específico"),
               _boton_quitar("Quitar objetivo"), cls="fila-repetible flex gap-2 items-center")


def fila_actividad(periodo, descripcion="", mes=None):
    return Div(Select(Option("Mes…", value=""),
                      *[Option(t, value=v, selected=v == mes) for v, t in inst.meses(periodo)],
                      name="act_mes", cls="uk-select w-36 shrink-0", aria_label="Mes previsto"),
               Input(name="act_desc", value=descripcion, cls="uk-input", placeholder="Actividad prevista…",
                     aria_label="Actividad prevista"),
               _boton_quitar("Quitar actividad"), cls="fila-repetible flex gap-2 items-center")


@rt("/propuestas/{prop_id}/fila/{tipo}")
def get(auth, prop_id: int, tipo: str):
    prop, error = _prop_o_error(prop_id, auth)
    if error:
        return error
    return fila_objetivo() if tipo == "objetivo" else fila_actividad(prop["periodo"])


def _area(etiqueta, nombre, valor, filas=5, ayuda=None, oculta=False):
    """Área de texto. `oculta`: la etiqueta solo para lectores de pantalla (el título de la sección
    ya la muestra)."""
    return Div(FormLabel(etiqueta, fr=nombre, cls="sr-only" if oculta else ""),
               P(ayuda, cls=TextPresets.muted_sm) if ayuda else "",
               Textarea(valor or "", id=nombre, name=nombre, rows=filas, cls="uk-textarea"),
               cls="space-y-2")


def _seccion(titulo, *contenido, numero=None):
    return Card(H3(f"{numero}. {titulo}" if numero else titulo, cls="text-base font-semibold mb-3"),
                *contenido, cls="space-y-4")


def equipo(prop, auth):
    parts = proyectos.participantes(prop["proyecto_id"], solo_vigentes=True)
    gestiona = proyectos.puede_gestionar(prop["proyecto_id"], auth)
    return Div(
        Ul(*[Li(Strong(f"{x['nombres']} {x['apellidos']}"), Span(f" · {proyectos.ROLES[x['rol']]}"),
                Span(" · externo" if not x["interno"] else "", cls=TextPresets.muted_sm), cls="text-sm py-0.5")
             for x in parts]),
        A(UkIcon("users", height=14, width=14), "Gestionar participantes",
          href=f"/proyectos/{prop['proyecto_id']}?tab=participantes",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mt-2") if gestiona else "",
        P("Responsables: titulares o contratados; co-responsables: también interinos.", cls=TextPresets.muted_sm))


def editor(prop, auth, errores=()):
    faltan = inst.faltantes(prop)
    periodo = prop["periodo"]
    plazo = inst.plazo(periodo)
    if prop["estado"] == "condicional":
        estado_envio = P("Corrija según las condiciones y vuelva a enviarla (no depende del plazo).",
                         cls=TextPresets.muted_sm)
    elif inst.abierta(periodo):
        estado_envio = P(f"Plazo abierto hasta el {inst.fecha_texto(plazo['cierra'])}.", cls="text-sm text-green-700")
    else:
        estado_envio = P(f"Podrá enviarla del {inst.fecha_texto(plazo['abre'])} al "
                         f"{inst.fecha_texto(plazo['cierra'])}.", cls="text-sm text-amber-700")
    return Form(
        mensaje_error(*errores),
        Div(UkIcon("circle-alert", height=16, width=16, cls="shrink-0"),
            Div(Strong("Condiciones de la administración: "), Span(prop["comentario"])),
            cls="flex gap-2 rounded-md border border-amber-300 bg-amber-50 text-amber-900 dark:bg-amber-950 "
                "dark:text-amber-200 p-3 text-sm") if prop["estado"] == "condicional" else "",
        _seccion("Datos básicos",
                 LabelInput("Nombre del proyecto", id="nombre", value=prop["nombre"], required=True, maxlength=300),
                 Div(FormLabel("Líneas de investigación institucionales"),
                     P(f"Seleccione las líneas vigentes en el periodo {inst.periodo_texto(periodo)} a las que se "
                       "adscribe el proyecto (al menos una).", cls=TextPresets.muted_sm),
                     casillas_lineas([x["id"] for x in prop["lineas"]], inst.inicio(periodo),
                                     actuales=prop["lineas"]),
                     cls="space-y-2"),
                 _area("Descripción", "descripcion", prop["descripcion"], 4),
                 _area("Objetivo general", "objetivo_general", prop["objetivo_general"], 2),
                 Div(FormLabel("Objetivos específicos"),
                     Div(*[fila_objetivo(o["texto"]) for o in prop["objetivos"]] or [fila_objetivo()],
                         id="lista-objetivos", cls="space-y-2"),
                     Button(UkIcon("plus", height=14, width=14), "Agregar objetivo", type="button",
                            cls=(ButtonT.ghost, ButtonT.sm), hx_get=f"/propuestas/{prop['id']}/fila/objetivo",
                            hx_target="#lista-objetivos", hx_swap="beforeend"),
                     cls="space-y-2"),
                 numero=1),
        _seccion("Metodología", _area("Metodología", "metodologia", prop["metodologia"], 8,
                                      "Enfoque, métodos y etapas. Puede usar fórmulas LaTeX entre $…$.", oculta=True), numero=2),
        _seccion("Resultados esperados", _area("Resultados esperados", "resultados_esperados",
                                               prop["resultados_esperados"], 5,
                                               "Publicaciones, tesis, software, formación, etc.", oculta=True), numero=3),
        _seccion("Actividades programadas",
                 P(f"Del periodo {inst.periodo_texto(periodo)}, con el mes en que se prevé cada una.",
                   cls=TextPresets.muted_sm),
                 Div(*[fila_actividad(periodo, a["descripcion"], a["mes_previsto"]) for a in prop["actividades"]]
                     or [fila_actividad(periodo)], id="lista-actividades", cls="space-y-2"),
                 Button(UkIcon("plus", height=14, width=14), "Agregar actividad", type="button",
                        cls=(ButtonT.ghost, ButtonT.sm), hx_get=f"/propuestas/{prop['id']}/fila/actividad",
                        hx_target="#lista-actividades", hx_swap="beforeend"),
                 numero=4),
        _seccion("Bibliografía", _area("Bibliografía", "bibliografia", prop["bibliografia"], 6,
                                       "Una referencia por línea.", oculta=True), numero=5),
        _seccion("Equipo", equipo(prop, auth)),
        Div(Div(estado_envio,
                P("Falta: " + ", ".join(faltan) + "." if faltan else "Lista para enviar.",
                  cls=TextPresets.muted_sm if faltan else "text-sm text-green-700")),
            Div(Button("Guardar borrador" if prop["estado"] == "borrador" else "Guardar", type="submit",
                       cls=ButtonT.default),
                Button(UkIcon("send", height=14, width=14),
                       "Reenviar propuesta" if prop["estado"] == "condicional" else "Enviar propuesta",
                       type="button", cls=ButtonT.primary, hx_post=f"/propuestas/{prop['id']}/enviar",
                       hx_include=f"#{ID_EDITOR}", hx_target=f"#{ID_EDITOR}", hx_swap="outerHTML",
                       hx_confirm="Una vez enviada, no podrá modificarla salvo que la administración la acepte "
                                  "con condiciones. ¿Enviar?"),
                cls="flex gap-2 shrink-0"),
            cls="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 rounded-md border "
                "border-border bg-background p-4 shadow-md"),
        id=ID_EDITOR, hx_put=f"/propuestas/{prop['id']}", hx_target=f"#{ID_EDITOR}", hx_swap="outerHTML",
        cls="space-y-6")


# --- Vista de solo lectura ---------------------------------------------------------------------------------

def contenido(c: dict):
    """Muestra una propuesta en el formato de `inst.copia` (la enviada o la actual)."""
    return Div(
        _seccion("Datos básicos",
                 dato("Líneas de investigación", "; ".join(c.get("lineas", [])) or None),
                 dato("Descripción", texto_con_parrafos(c["descripcion"], "—")),
                 dato("Objetivo general", c["objetivo_general"]),
                 dato("Objetivos específicos", fh.Ol(*[Li(o) for o in c["objetivos"]], cls="list-decimal pl-5 space-y-1")
                      if c["objetivos"] else None), numero=1),
        _seccion("Metodología", texto_con_parrafos(c["metodologia"], "—"), numero=2),
        _seccion("Resultados esperados", texto_con_parrafos(c["resultados_esperados"], "—"), numero=3),
        _seccion("Actividades programadas",
                 fh.Table(fh.Tbody(*[fh.Tr(fh.Td(inst.mes_texto(a["mes"]), cls="whitespace-nowrap w-28 text-sm"),
                                           fh.Td(a["descripcion"], cls="text-sm")) for a in c["actividades"]]),
                          cls="uk-table uk-table-divider uk-table-small") if c["actividades"]
                 else P("—", cls=TextPresets.muted_sm), numero=4),
        _seccion("Bibliografía", texto_con_parrafos(c["bibliografia"], "—"), numero=5),
        _seccion("Equipo", Ul(*[Li(Strong(x["nombre"]), f" · {x['rol']}",
                                   Span(f" · {x['categoria']}" if x.get("categoria") else " · externo",
                                        cls=TextPresets.muted_sm), cls="text-sm py-0.5")
                                for x in c.get("equipo", [])]) if c.get("equipo") else
                 P("—", cls=TextPresets.muted_sm)),
        cls="space-y-6")


def historial(prop):
    evs = inst.eventos(prop["id"])
    if not evs:
        return ""
    return Card(H3("Historial", cls="text-base font-semibold mb-2"),
                Ul(*[Li(Span(fecha_local(e["fecha"]), cls=(TextPresets.muted_sm, "mr-2 font-mono")),
                        Strong(inst.ESTADOS.get(e["accion"], e["accion"])),
                        Span(f" · {e['quien']}" if e["quien"] else "", cls=TextPresets.muted_sm),
                        P(e["comentario"], cls="text-sm mt-1") if e["comentario"] else "", cls="py-1.5")
                     for e in evs], cls="divide-y divide-border"))


def panel_decision(prop, errores=(), decision="", comentario=""):
    return Card(
        H3("Decisión", cls="text-base font-semibold mb-2"),
        Form(mensaje_error(*errores),
             *[fh.Label(Input(type="radio", name="decision", value=v, checked=v == decision, cls="uk-radio",
                              required=True), Span(t, cls="text-sm"), cls="flex items-center gap-2")
               for v, t in inst.DECISIONES.items()],
             Div(FormLabel("Condiciones o motivo", fr="comentario"),
                 Textarea(comentario, id="comentario", name="comentario", rows=4, cls="uk-textarea"),
                 P("Obligatorio al aceptar con condiciones o al rechazar. Quien propuso lo recibe por correo.",
                   cls=TextPresets.muted_sm), cls="space-y-1"),
             Button("Registrar decisión", type="submit", cls=ButtonT.primary),
             hx_post=f"/propuestas/{prop['id']}/decidir", hx_target="#panel-decision", hx_swap="outerHTML",
             cls="space-y-3"),
        id="panel-decision", cls="border-primary/40")


def acciones(prop, auth):
    botones = []
    if prop["estado"] == "borrador" and inst.puede_editar(prop, auth):
        botones.append(Button(UkIcon("trash-2", height=14, width=14), "Eliminar borrador", type="button",
                              cls=(ButtonT.ghost, ButtonT.sm), hx_delete=f"/propuestas/{prop['id']}",
                              hx_confirm="¿Eliminar este borrador?" + (
                                  " También se elimina el proyecto en formulación."
                                  if prop["modalidad"] == "nuevo" else "")))
    if prop["estado"] in inst.EN_REVISION and (prop["proponente_id"] == auth["id"]
                                              or proyectos.puede_gestionar(prop["proyecto_id"], auth)):
        botones.append(Button(UkIcon("undo-2", height=14, width=14), "Retirar propuesta", type="button",
                              cls=(ButtonT.ghost, ButtonT.sm), hx_post=f"/propuestas/{prop['id']}/retirar",
                              hx_confirm="¿Retirar la propuesta? No se podrá volver a enviar para este periodo."))
    return Div(*botones, cls="flex gap-2") if botones else ""


@rt("/propuestas/{prop_id}")
def get(auth, prop_id: int):
    prop, error = _prop_o_error(prop_id, auth)
    if error:
        return pagina("No encontrado", P("La propuesta no existe o no tiene acceso a ella."), usuario=auth)
    decide = permisos.puede(auth, "decidir_propuestas")
    editable = inst.puede_editar(prop, auth)
    if editable:
        cuerpo = editor(prop, auth)
    elif decide and prop["estado"] in inst.EDITABLES and prop["copia_enviada"]:
        cuerpo = Div(P("El responsable está corrigiendo la propuesta. Esta es la última versión enviada.",
                       cls=(TextPresets.muted_sm, "mb-4")), contenido(json.loads(prop["copia_enviada"])))
    else:
        cuerpo = contenido(inst.copia(prop) if prop["estado"] in ("borrador",) or not prop["copia_enviada"]
                           else json.loads(prop["copia_enviada"]))
    return pagina(
        prop["nombre"],
        A(UkIcon("arrow-left", height=14, width=14), "Propuestas" if decide else "Proyectos",
          href=f"/admin/propuestas?periodo={prop['periodo']}" if decide else "/proyectos",
          cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
        Div(Div(insignia_estado(prop["estado"]),
                insignia(inst.MODALIDADES[prop["modalidad"]], "gris"),
                insignia(f"Periodo {inst.periodo_texto(prop['periodo'])}", "gris", icono="calendar-range"),
                cls="flex flex-wrap gap-2"),
            acciones(prop, auth), cls="flex flex-wrap items-center justify-between gap-2"),
        H2(prop["nombre"], cls="mt-2"),
        P(f"Propuesta de {prop['proponente']}",
          " · ", A("Ver proyecto", href=f"/proyectos/{prop['proyecto_id']}", cls="text-primary hover:underline")
          if proyectos.puede_ver(prop["proyecto_id"], auth) else "",
          cls=(TextPresets.muted_sm, "mb-6")),
        Div(UkIcon("circle-alert", height=16, width=16, cls="shrink-0"),
            Div(Strong("Aceptada con condiciones: " if prop["estado"] == "condicional" else "Motivo del rechazo: "),
                Span(prop["comentario"] or "")),
            cls="flex gap-2 rounded-md border border-amber-300 bg-amber-50 text-amber-900 dark:bg-amber-950 "
                "dark:text-amber-200 p-3 text-sm mb-6")
        if prop["estado"] in ("condicional", "rechazada") and not editable else "",
        _con_lateral(cuerpo, [panel_decision(prop) if decide and prop["estado"] == "enviada" else "",
                              historial(prop)]),
        usuario=auth, seccion="propuestas" if decide else "proyectos")


def _con_lateral(cuerpo, laterales):
    laterales = [x for x in laterales if x]
    if not laterales:
        return Div(cuerpo, cls="max-w-4xl")
    return Div(Div(cuerpo, cls="lg:col-span-2"), Div(*laterales, cls="space-y-6"),
               cls="grid grid-cols-1 lg:grid-cols-3 gap-6")


def _listas_del_form(objetivo, act_desc, act_mes):
    objetivo, act_desc, act_mes = objetivo or [], act_desc or [], act_mes or []
    act_mes = act_mes + [""] * (len(act_desc) - len(act_mes))
    return objetivo, list(zip(act_desc, act_mes))


def _guardar_form(prop, nombre, descripcion, objetivo_general, metodologia, resultados_esperados, bibliografia,
                  objetivo, act_desc, act_mes, linea):
    """Guarda lo enviado. → (errores, propuesta para volver a mostrar el editor con lo escrito)."""
    objetivos, actividades = _listas_del_form(objetivo, act_desc, act_mes)
    datos = dict(nombre=nombre, descripcion=descripcion, objetivo_general=objetivo_general,
                 metodologia=metodologia, resultados_esperados=resultados_esperados, bibliografia=bibliografia)
    ids = lineas.ids_validos(linea)
    errores = inst.guardar(prop, datos, objetivos, actividades, ids)
    if not errores:
        return [], inst.obtener(prop["id"])
    marcadas = [x for x in (lineas.obtener(i) for i in ids) if x]
    return errores, {**prop, **datos, "lineas": marcadas, "objetivos": [{"texto": t} for t in objetivos],
                     "actividades": [{"descripcion": d, "mes_previsto": m} for d, m in actividades]}


@rt("/propuestas/{prop_id}")
def put(auth, sess, prop_id: int, nombre: str = "", descripcion: str = "", objetivo_general: str = "",
        metodologia: str = "", resultados_esperados: str = "", bibliografia: str = "",
        objetivo: list[str] = None, act_desc: list[str] = None, act_mes: list[str] = None,
        linea: list[str] = None):
    prop, error = _prop_o_error(prop_id, auth)
    if error:
        return error
    if not inst.puede_editar(prop, auth):
        return Response("No autorizado", status_code=403)
    errores, prop = _guardar_form(prop, nombre, descripcion, objetivo_general, metodologia, resultados_esperados,
                                  bibliografia, objetivo, act_desc, act_mes, linea)
    if not errores:
        add_toast(sess, "Cambios guardados.", "success")
    return editor(prop, auth, errores)


@rt("/propuestas/{prop_id}/enviar")
def post(auth, sess, prop_id: int, nombre: str = "", descripcion: str = "", objetivo_general: str = "",
         metodologia: str = "", resultados_esperados: str = "", bibliografia: str = "",
         objetivo: list[str] = None, act_desc: list[str] = None, act_mes: list[str] = None,
        linea: list[str] = None):
    prop, error = _prop_o_error(prop_id, auth)
    if error:
        return error
    if not inst.puede_editar(prop, auth):
        return Response("No autorizado", status_code=403)
    errores, guardada = _guardar_form(prop, nombre, descripcion, objetivo_general, metodologia,
                                      resultados_esperados, bibliografia, objetivo, act_desc, act_mes, linea)
    if errores:
        return editor(guardada, auth, errores)
    error = inst.enviar(inst.obtener(prop_id), auth)
    if error:
        # Lo escrito ya quedó guardado: solo falta poder enviarlo.
        return editor(inst.obtener(prop_id), auth, [error, "Sus cambios quedaron guardados."])
    auditar(auth["id"], "enviar_propuesta", "proyecto", prop["proyecto_id"], str(prop["periodo"]))
    add_toast(sess, "Propuesta enviada. La administración le avisará su decisión.", "success")
    return Redirect(f"/propuestas/{prop_id}")


@rt("/propuestas/{prop_id}/retirar")
def post(auth, sess, prop_id: int):
    prop, error = _prop_o_error(prop_id, auth)
    if error:
        return error
    error = inst.retirar(prop, auth)
    if error:
        return Response(error, status_code=403)
    auditar(auth["id"], "retirar_propuesta", "proyecto", prop["proyecto_id"], str(prop["periodo"]))
    add_toast(sess, "Propuesta retirada.", "success")
    return Redirect(f"/propuestas/{prop_id}")


@rt("/propuestas/{prop_id}")
def delete(auth, sess, prop_id: int):
    prop, error = _prop_o_error(prop_id, auth)
    if error:
        return error
    error = inst.eliminar_borrador(prop, auth)
    if error:
        return Response(error, status_code=403)
    add_toast(sess, "Borrador eliminado.", "success")
    return Redirect("/proyectos" if prop["modalidad"] == "nuevo" else f"/proyectos/{prop['proyecto_id']}")


@rt("/propuestas/{prop_id}/decidir")
def post(auth, sess, prop_id: int, decision: str = "", comentario: str = ""):
    prop, error = _prop_o_error(prop_id, auth)
    if error:
        return error
    if not permisos.puede(auth, "decidir_propuestas"):
        return Response("No autorizado", status_code=403)
    error = inst.decidir(prop, decision, comentario, auth)
    if error:
        return panel_decision(prop, [error], decision, comentario)
    auditar(auth["id"], "decidir_propuesta", "proyecto", prop["proyecto_id"],
            f"{prop['periodo']}: {inst.ESTADOS[decision]}")
    add_toast(sess, f"Decisión registrada: {inst.ESTADOS[decision].lower()}.", "success")
    return Redirect(f"/propuestas/{prop_id}")


# --- Bandeja de la administración ---------------------------------------------------------------------------

def _periodo_valido(valor, por_omision):
    return int(valor) if str(valor).isdigit() and 2000 <= int(valor) <= 2100 else por_omision


def form_plazo(periodo, errores=()):
    p = inst.plazo(periodo)
    return Form(
        mensaje_error(*errores),
        Div(LabelInput("Abre", id="abre", type="date", value=p["abre"]),
            LabelInput("Cierra", id="cierra", type="date", value=p["cierra"]),
            Button("Guardar plazo", type="submit", cls=(ButtonT.default, "self-end")),
            cls="flex flex-wrap gap-3"),
        P("Plazo modificado por la administración. ", A("Volver a todo septiembre", href="#",
                                                         hx_post=f"/admin/propuestas/{periodo}/plazo/restablecer",
                                                         hx_target="#form-plazo", hx_swap="outerHTML",
                                                         cls="text-primary hover:underline"),
          cls=TextPresets.muted_sm) if p["modificado"] else
        P("Por omisión, todo septiembre. Puede ampliarlo o abrir un plazo extraordinario.", cls=TextPresets.muted_sm),
        id="form-plazo", hx_post=f"/admin/propuestas/{periodo}/plazo", hx_target="#form-plazo", hx_swap="outerHTML",
        cls="space-y-2")


@rt("/admin/propuestas")
def get(auth, periodo: str = "", estado: str = ""):
    actual = inst.periodo_objetivo()
    periodo = _periodo_valido(periodo, actual)
    estado = estado if estado in inst.ESTADOS else ""
    props = inst.listar(periodo, estado)
    n = inst.conteos(periodo)
    periodos = sorted(set(inst.periodos_con_propuestas()) | {actual, periodo}, reverse=True)
    filtro = [("", f"Todas ({sum(n.values())})")] + [(e, f"{t} ({n.get(e, 0)})") for e, t in inst.ESTADOS.items()
                                                     if e != "borrador"]
    filas = [fh.Tr(fh.Td(A(p["nombre"], href=f"/propuestas/{p['id']}", cls="font-medium hover:underline")),
                   fh.Td(inst.MODALIDADES[p["modalidad"]], cls="text-sm"),
                   fh.Td(p["proponente"], cls="text-sm"),
                   fh.Td(p["enviada_en"][:10] if p["enviada_en"] else "—", cls="text-sm whitespace-nowrap"),
                   fh.Td(insignia_estado(p["estado"]))) for p in props]
    return pagina(
        "Propuestas institucionales",
        Div(Div(H2("Propuestas institucionales"),
                P("Proyectos institucionales propuestos por periodo (octubre a septiembre). La administración "
                  "los acepta, los acepta con condiciones o los rechaza.", cls=TextPresets.muted_sm)),
            Div(Select(*[Option(f"Periodo {inst.periodo_texto(x)}", value=str(x), selected=x == periodo)
                         for x in periodos],
                       name="periodo", cls="uk-select w-52", aria_label="Periodo",
                       onchange="location.href='/admin/propuestas?periodo='+this.value"),
                A(UkIcon("download", height=14, width=14), "Descargar XLSX", href=f"/admin/propuestas/{periodo}/xlsx",
                  cls="uk-btn uk-btn-default uk-btn-sm inline-flex items-center gap-1") if props or n else "",
                cls="flex items-center gap-2"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Card(H3(f"Plazo de la convocatoria {inst.periodo_texto(periodo)}", cls="text-base font-semibold mb-2"),
             P("Abierta hoy." if inst.abierta(periodo) else "Cerrada hoy.",
               cls="text-sm " + ("text-green-700" if inst.abierta(periodo) else "text-muted-foreground")),
             form_plazo(periodo), cls="mb-6"),
        Div(*[A(t, href=f"/admin/propuestas?periodo={periodo}" + (f"&estado={e}" if e else ""),
                cls="text-sm px-3 py-1 rounded-full border " +
                    ("border-primary bg-primary/10 text-primary" if e == estado else "border-border hover:bg-muted"))
              for e, t in filtro], cls="flex flex-wrap gap-2 mb-4"),
        Div(fh.Table(fh.Thead(fh.Tr(fh.Th("Proyecto"), fh.Th("Modalidad"), fh.Th("Proponente"), fh.Th("Enviada"),
                                    fh.Th("Estado"))), fh.Tbody(*filas),
                     cls="uk-table uk-table-divider uk-table-middle uk-table-hover"),
            cls="overflow-x-auto") if filas else P("No hay propuestas enviadas en este periodo.",
                                                    cls=TextPresets.muted_sm),
        usuario=auth, seccion="propuestas")


@rt("/admin/propuestas/{periodo}/xlsx")
def get(auth, periodo: int):
    # Sin extensión en la URL: la ruta de archivos estáticos capturaría «….xlsx».
    from app.acreditacion.informes import a_xlsx
    return Response(a_xlsx(inst.hojas_convocatoria(periodo)),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="propuestas-{periodo}-{periodo + 1}.xlsx"',
                             "Cache-Control": "private, no-store"})


@rt("/admin/propuestas/{periodo}/plazo")
def post(auth, sess, periodo: int, abre: str = "", cierra: str = ""):
    error = inst.guardar_plazo(periodo, abre, cierra, auth["id"])
    if error:
        return form_plazo(periodo, [error])
    auditar(auth["id"], "plazo_convocatoria", "convocatoria", periodo, f"{abre} a {cierra}")
    add_toast(sess, "Plazo guardado.", "success")
    return Redirect(f"/admin/propuestas?periodo={periodo}")


@rt("/admin/propuestas/{periodo}/plazo/restablecer")
def post(auth, sess, periodo: int):
    inst.restablecer_plazo(periodo)
    auditar(auth["id"], "plazo_convocatoria", "convocatoria", periodo, "septiembre (por omisión)")
    add_toast(sess, "Plazo restablecido a todo septiembre.", "success")
    return Redirect(f"/admin/propuestas?periodo={periodo}")


@rt("/admin/propuestas/contador")
def get(auth):
    n = inst.n_por_decidir()
    return Span(str(n) if n else "", id="badge-propuestas", title=f"{n} propuesta(s) por decidir" if n else None,
                cls="ml-1 rounded-full bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5" if n else "hidden",
                hx_get="/admin/propuestas/contador", hx_swap="outerHTML", hx_trigger="every 60s")
