"""«Mis actividades»: lista con filtros, alta/edición en modal y ficha con adjuntos.

Sigue los mismos patrones que productos (evento `actividades-cambiadas` vía HX-Trigger).
"""
from datetime import date

from fasthtml.common import (A, APIRouter, Datalist, Div, H3, HtmxResponseHeaders, Option, P,
                             Redirect, Response, Select, Span)
from fasthtml.toaster import add_toast
from monsterui.all import (H2, Button, ButtonT, Card, Form, FormLabel, LabelInput, LabelTextArea,
                           TextPresets, UkIcon)

from app.investigacion import actividades, lineas, productos, proyectos
from app.comun import permisos, personas
from app.investigacion.componentes.lineas import insignias_lineas
from app.investigacion.componentes import personas as selector_personas
from app.comun.componentes.layout import ID_MODAL, mensaje_error, modal, pagina
from app.comun.componentes.registros import dato, enlace_persona, filtros, insignia, url_filtrada
from app.investigacion.componentes.registros import casillas_proyectos, insignias_proyectos, seccion_adjuntos
from app.comun.db import auditar, get_db

rt = APIRouter()

EVENTO = "actividades-cambiadas"
ID_LISTA = "lista-actividades"
ID_FILTROS = "filtros-actividades"


# --- Presentación ---------------------------------------------------------------------

def _lugar(a):
    return ", ".join(x for x in (a["institucion"], a["lugar"], a["pais"]) if x)


def item(a, uid):
    editable = actividades.puede_editar(a, uid)
    acciones = Div(
        Button(UkIcon("pencil", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon),
               title="Editar", aria_label=f"Editar {a['titulo']}",
               hx_get=f"/actividades/{a['id']}/editar", hx_target=f"#{ID_MODAL}") if editable else "",
        Button(UkIcon("trash-2", height=14, width=14), cls=(ButtonT.ghost, ButtonT.icon),
               title="Eliminar", aria_label=f"Eliminar {a['titulo']}",
               hx_delete=f"/actividades/{a['id']}", hx_confirm=f"¿Eliminar «{a['titulo']}»?")
        if actividades.puede_eliminar(a, uid) else "",
        cls="flex shrink-0")
    etiquetas = [insignia(a["tipo"]), insignia(actividades.AMBITOS[a["ambito"]], "azul")]
    if a["modalidad"] != "presencial":
        etiquetas.append(insignia(actividades.MODALIDADES[a["modalidad"]]))
    if a.get("mi_rol"):
        etiquetas.append(insignia(actividades.ROLES[a["mi_rol"]], "verde", icono="user-round"))
    return Div(
        Div(actividades.fechas_texto(a), cls="text-sm text-muted-foreground w-28 shrink-0 pt-0.5"),
        Div(A(a["titulo"], href=f"/actividades/{a['id']}", cls="block font-medium hover:underline"),
            P(_lugar(a), cls=TextPresets.muted_sm) if _lugar(a) else "",
            Div(*etiquetas, *insignias_proyectos(proyectos.vinculos_de("actividad", a["id"])),
                cls="flex flex-wrap gap-1.5"),
            cls="min-w-0 flex-1 space-y-1"),
        acciones, cls="flex gap-4 py-4")


def lista(uid, q="", anio="", tipo=""):
    items = actividades.de_investigador(uid, q, anio, tipo)
    contenido = (
        [P(f"{len(items)} actividad{'es' if len(items) != 1 else ''}", cls=TextPresets.muted_sm),
         Div(*[item(a, uid) for a in items], cls="divide-y divide-border")]
        if items else [P("No hay actividades que coincidan." if (q or anio or tipo)
                         else "Aún no registra actividades. Use «Nueva actividad» para empezar.",
                         cls=(TextPresets.muted_sm, "py-8 text-center"))])
    return Div(*contenido, id=ID_LISTA, hx_get="/actividades/lista", hx_include=f"#{ID_FILTROS}",
               hx_trigger=f"{EVENTO} from:body", hx_swap="outerHTML")


# --- Formulario -------------------------------------------------------------------------

def _select(etiqueta, nombre, opciones: dict, valor):
    return Div(FormLabel(etiqueta, fr=nombre),
               Select(*[Option(t, value=v, selected=str(v) == str(valor)) for v, t in opciones.items()],
                      id=nombre, name=nombre, cls="uk-select"),
               cls="space-y-2")


def form_actividad(auth, d, participantes_, errores=(), aid=None, proyectos_sel=None,
                   preseleccion=None):
    def campo(etiqueta, nombre, **kw):
        return LabelInput(etiqueta, id=nombre, value=d.get(nombre) or "", **kw)

    tipos = {t["id"]: t["nombre"] for t in actividades.tipos()}
    tipo = Div(FormLabel("Tipo", fr="tipo_id"),
               # Al cambiar el tipo, el servidor devuelve los campos que corresponden (con lo ya escrito).
               Select(*[Option(t, value=v, selected=str(v) == str(d.get("tipo_id"))) for v, t in tipos.items()],
                      id="tipo_id", name="tipo_id", cls="uk-select", hx_get="/actividades/campos",
                      hx_trigger="change", hx_target=f"#{ID_CAMPOS}", hx_swap="outerHTML",
                      hx_include=f"#{ID_CAMPOS}, #tipo_id"),
               cls="space-y-2")
    return Form(
        mensaje_error(*errores),
        tipo,
        campo("Título", "titulo", required=True, placeholder="Congreso Latinoamericano de Matemáticas"),
        campos_del_tipo(d),
        Div(_select("Modalidad", "modalidad", actividades.MODALIDADES, d.get("modalidad")),
            _select("Ámbito", "ambito", actividades.AMBITOS, d.get("ambito")),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
        selector_personas.selector("participante", participantes_, "Participantes",
                                   "Del instituto o externos, con su rol en la actividad."),
        campo("Enlace (URL)", "url", type="url", placeholder="https://…"),
        LabelTextArea("Descripción", id="descripcion", value=d.get("descripcion") or "", rows=3),
        casillas_proyectos("actividad", aid, auth, proyectos_sel, preseleccion),
        Div(Button("Cancelar", type="button", cls=ButtonT.ghost, data_accion="cerrar-modal"),
            Button("Guardar", type="submit", cls=ButtonT.primary),
            cls="flex justify-end gap-2"),
        hx_put=f"/actividades/{aid}" if aid else None, hx_post=None if aid else "/actividades",
        hx_target=f"#{ID_MODAL}", cls="space-y-4")


ID_CAMPOS = "campos-del-tipo"
ETIQUETA_INSTITUCION = {actividades.PREMIO: "Institución que lo otorga", actividades.ARBITRAJE: "Revista",
                        actividades.SERVICIO: "Contraparte"}
PISTA_INSTITUCION = {actividades.SERVICIO: "A quién se presta el servicio", actividades.ARBITRAJE: "Del catálogo o escrita"}


def campos_del_tipo(d):
    """Fechas, institución y los campos propios del tipo (arbitraje: año, revista y cantidad;
    servicio: monto, moneda, origen e ingresos). Se reemplaza al cambiar el tipo."""
    tipo = actividades.nombre_tipo(d.get("tipo_id"))

    def campo(etiqueta, nombre, **kw):
        return LabelInput(etiqueta, id=nombre, value="" if d.get(nombre) is None else str(d[nombre]), **kw)
    institucion = campo(ETIQUETA_INSTITUCION.get(tipo, "Institución organizadora o anfitriona"), "institucion",
                        list="revistas-catalogo" if tipo == actividades.ARBITRAJE else None,
                        placeholder=PISTA_INSTITUCION.get(tipo))
    rol = actividades.ROL_DEL_TIPO.get(tipo)
    pista_rol = Div(UkIcon("info", height=14, width=14, cls="shrink-0 mt-0.5"),
                    Span(f"En «Participantes», al menos una persona con el rol «{actividades.ROLES[rol]}»."),
                    cls="flex items-start gap-1.5 text-sm text-muted-foreground") if rol else ""
    if tipo == actividades.ARBITRAJE:
        hoy = date.today().year
        anio = int((d.get("fecha_inicio") or str(hoy))[:4])
        return Div(
            Div(_select("Año", "anio", {a: str(a) for a in range(hoy, hoy - 11, -1)}, anio),
                institucion,
                campo("Artículos arbitrados", "cantidad", type="number", min="1", required=True),
                cls="grid grid-cols-1 sm:grid-cols-3 gap-4"),
            Datalist(*[Option(value=r["titulo"]) for r in get_db().q("SELECT titulo FROM revista ORDER BY titulo")],
                     id="revistas-catalogo"),
            P("Una entrada por revista y año, sin títulos de los artículos (el arbitraje es confidencial).",
              cls=TextPresets.muted_sm),
            pista_rol, id=ID_CAMPOS, cls="space-y-2")
    fechas = Div(campo("Fecha" if tipo == actividades.PREMIO else "Inicio", "fecha_inicio", type="date", required=True),
                 campo("Término", "fecha_fin", type="date") if tipo != actividades.PREMIO else "",
                 cls="grid grid-cols-1 sm:grid-cols-2 gap-4")
    lugar = Div(institucion, campo("Ciudad o sede", "lugar"), campo("País", "pais"),
                cls="grid grid-cols-1 sm:grid-cols-3 gap-4")
    extra = ""
    if tipo == actividades.SERVICIO:
        extra = Div(
            Div(campo("Monto del servicio", "monto", inputmode="numeric", placeholder="Sin puntos ni comas"),
                _select("Moneda", "moneda", {"": "—", **actividades.MONEDAS}, d.get("moneda") or ""),
                _select("Financiamiento", "financiamiento", {"": "—", **actividades.FINANCIAMIENTOS},
                        d.get("financiamiento") or ""),
                campo("Ingresos para la unidad", "ingresos", inputmode="numeric", placeholder="En la misma moneda"),
                cls="grid grid-cols-1 sm:grid-cols-4 gap-4"),
            P("Los ingresos son lo que el servicio dejó a la Carrera o el Instituto. La Guía de Antecedentes los pide "
              "en dólares: se convierten con el tipo de cambio que se indica al generarla.", cls=TextPresets.muted_sm),
            cls="space-y-2")
    return Div(fechas, lugar, extra, pista_rol, id=ID_CAMPOS, cls="space-y-4")


def _modal_form(auth, d, participantes_, errores=(), aid=None, proyectos_sel=None, preseleccion=None):
    return modal("Editar actividad" if aid else "Nueva actividad",
                 form_actividad(auth, d, participantes_, errores, aid, proyectos_sel, preseleccion),
                 ancho="max-w-3xl")


def _participantes_de(refs, roles):
    res = []
    for r, rol in zip(refs or [], roles or []):
        if (p := personas.por_ref(r)):
            res.append({**p, "rol": rol})
    return res


def _guardar(auth, sess, aid, d, participante, rol, proyecto):
    pares = list(zip(participante or [], rol or []))
    d = {k: (v.strip() or None) if isinstance(v, str) else v for k, v in d.items()}
    d["tipo_id"] = int(d["tipo_id"]) if str(d.get("tipo_id") or "").isdigit() else None
    tipo = actividades.nombre_tipo(d["tipo_id"])
    errores = []
    anio = d.pop("anio", None)
    for k in ("cantidad", "monto", "ingresos"):
        d[k], ok = actividades.entero(d.get(k))
        if not ok:
            errores.append("Los montos y cantidades van como números enteros, sin puntos ni comas.")
    if tipo == actividades.ARBITRAJE:        # por revista y año
        anio = anio if str(anio or "").isdigit() else str(date.today().year)
        d.update(fecha_inicio=f"{anio}-01-01", fecha_fin=f"{anio}-12-31", lugar=None, pais=None,
                 revista_id=actividades.revista_del_catalogo(d.get("institucion")))
    else:
        d["revista_id"] = None
    if tipo == actividades.PREMIO:
        d["fecha_fin"] = None
    if tipo != actividades.ARBITRAJE:
        d["cantidad"] = None
    if tipo != actividades.SERVICIO:
        d.update(monto=None, moneda=None, financiamiento=None, ingresos=None)
    errores = list(dict.fromkeys(errores)) + actividades.validar(d, pares)
    if errores:
        return _modal_form(auth, d, _participantes_de(participante, rol), errores, aid, proyecto or [])
    nueva = aid is None
    aid = actividades.guardar(d, pares, auth["id"], aid)
    for aviso in proyectos.sincronizar("actividad", aid, proyecto or [], auth):
        add_toast(sess, aviso, "warning")
    auditar(auth["id"], "crear_actividad" if nueva else "editar_actividad", "actividad", aid)
    add_toast(sess, "Actividad registrada." if nueva else "Cambios guardados.", "success")
    return "", HtmxResponseHeaders(trigger=f"{EVENTO}, pendientes-cambiados")


def _datos(tipo_id, titulo, institucion, lugar, pais, fecha_inicio, fecha_fin, modalidad, ambito,
           url, descripcion, anio="", cantidad="", monto="", moneda="", financiamiento="", ingresos=""):
    return dict(tipo_id=tipo_id, titulo=titulo, institucion=institucion, lugar=lugar, pais=pais,
                fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, modalidad=modalidad, ambito=ambito,
                url=url, descripcion=descripcion, anio=anio, cantidad=cantidad, monto=monto, moneda=moneda,
                financiamiento=financiamiento, ingresos=ingresos)


# --- Rutas --------------------------------------------------------------------------------

@rt("/actividades")
def get(auth, q: str = "", anio: str = "", tipo: str = ""):
    uid = auth["id"]
    return pagina(
        "Mis actividades",
        Div(Div(H2("Mis actividades"),
                P("Seminarios, congresos, escuelas, visitas y otras actividades en que participa.",
                  cls=TextPresets.muted_sm)),
            Button(UkIcon("plus", height=16, width=16), "Nueva actividad", cls=ButtonT.primary,
                   hx_get="/actividades/nueva", hx_target=f"#{ID_MODAL}"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        filtros(ID_FILTROS, "/actividades/lista", ID_LISTA, q, anio, actividades.anios_de(uid),
                tipo, actividades.tipos()),
        Card(lista(uid, q, anio, tipo)),
        usuario=auth, seccion="actividades")


@rt("/actividades/lista")
def get(auth, q: str = "", anio: str = "", tipo: str = ""):
    return (lista(auth["id"], q, anio, tipo),
            HtmxResponseHeaders(replace_url=url_filtrada("/actividades", q=q, anio=anio, tipo=tipo)))


@rt("/actividades/nueva")
def get(auth, proyecto: int = None):
    d = dict(tipo_id=actividades.tipos()[0]["id"], fecha_inicio=date.today().isoformat(),
             modalidad="presencial", ambito="nacional")
    yo = personas.por_ref(f"i:{auth['id']}")   # sin perfil de investigador, empieza sin participantes
    return _modal_form(auth, d, [{**yo, "rol": "expositor"}] if yo else [], preseleccion=proyecto)


@rt("/actividades")
def post(auth, sess, tipo_id: str = "", titulo: str = "", institucion: str = "", lugar: str = "",
         pais: str = "", fecha_inicio: str = "", fecha_fin: str = "", modalidad: str = "",
         ambito: str = "", url: str = "", descripcion: str = "", participante: list[str] = None,
         rol: list[str] = None, proyecto: list[int] = None, anio: str = "", cantidad: str = "", monto: str = "",
         moneda: str = "", financiamiento: str = "", ingresos: str = ""):
    d = _datos(tipo_id, titulo, institucion, lugar, pais, fecha_inicio, fecha_fin, modalidad,
               ambito, url, descripcion, anio, cantidad, monto, moneda, financiamiento, ingresos)
    return _guardar(auth, sess, None, d, participante, rol, proyecto)


@rt("/actividades/campos")
def get(auth, tipo_id: str = "", fecha_inicio: str = "", fecha_fin: str = "", institucion: str = "",
        lugar: str = "", pais: str = "", anio: str = "", cantidad: str = "", monto: str = "", moneda: str = "",
        financiamiento: str = "", ingresos: str = ""):
    """Campos del tipo elegido, conservando lo ya escrito (el tipo cambia en el formulario)."""
    hoy = date.today()
    if anio.isdigit():   # viene del arbitraje (solo año): hoy si es el año en curso; si no, el 1 de enero
        inicio = hoy.isoformat() if int(anio) == hoy.year else f"{anio}-01-01"
    else:
        inicio = fecha_inicio or hoy.isoformat()
    return campos_del_tipo(dict(tipo_id=tipo_id, fecha_inicio=inicio, fecha_fin=fecha_fin, institucion=institucion,
                                lugar=lugar, pais=pais, cantidad=cantidad or None, monto=monto or None,
                                moneda=moneda, financiamiento=financiamiento, ingresos=ingresos or None))


@rt("/actividades/{aid}/editar")
def get(auth, aid: int):
    a = actividades.obtener(aid)
    if not a or not actividades.puede_editar(a, auth["id"]):
        return Response("No autorizado", status_code=403)
    return _modal_form(auth, a, actividades.participantes(aid), aid=aid)


@rt("/actividades/{aid}")
def put(auth, sess, aid: int, tipo_id: str = "", titulo: str = "", institucion: str = "",
        lugar: str = "", pais: str = "", fecha_inicio: str = "", fecha_fin: str = "",
        modalidad: str = "", ambito: str = "", url: str = "", descripcion: str = "",
        participante: list[str] = None, rol: list[str] = None, proyecto: list[int] = None, anio: str = "",
        cantidad: str = "", monto: str = "", moneda: str = "", financiamiento: str = "", ingresos: str = ""):
    a = actividades.obtener(aid)
    if not a or not actividades.puede_editar(a, auth["id"]):
        return Response("No autorizado", status_code=403)
    d = _datos(tipo_id, titulo, institucion, lugar, pais, fecha_inicio, fecha_fin, modalidad,
               ambito, url, descripcion, anio, cantidad, monto, moneda, financiamiento, ingresos)
    return _guardar(auth, sess, aid, d, participante, rol, proyecto)


@rt("/actividades/{aid}")
def delete(auth, sess, aid: int, desde: str = ""):
    a = actividades.obtener(aid)
    if not a or not actividades.puede_eliminar(a, auth["id"]):
        return Response("No autorizado", status_code=403)
    actividades.eliminar(aid)
    auditar(auth["id"], "eliminar_actividad", "actividad", aid, a["titulo"])
    add_toast(sess, "Actividad eliminada.", "success")
    if desde == "ficha":
        return Redirect("/actividades")
    return "", HtmxResponseHeaders(trigger=EVENTO)


# --- Ficha ----------------------------------------------------------------------------------

def ficha(a, auth):
    uid = auth["id"]
    editable = actividades.puede_editar(a, uid)
    participantes_ = actividades.participantes(a["id"])
    presentaciones = [productos.obtener(r["id"]) for r in get_db().q(
        "SELECT id FROM producto WHERE actividad_id = ? ORDER BY anio DESC", [a["id"]])]
    acciones = Div(
        Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.default, ButtonT.sm),
               hx_get=f"/actividades/{a['id']}/editar", hx_target=f"#{ID_MODAL}") if editable else "",
        Button(UkIcon("trash-2", height=14, width=14), "Eliminar", cls=(ButtonT.ghost, ButtonT.sm),
               hx_delete=f"/actividades/{a['id']}?desde=ficha",
               hx_confirm=f"¿Eliminar «{a['titulo']}»?") if actividades.puede_eliminar(a, uid) else "",
        cls="flex gap-2")
    return Div(
        Div(Div(Div(insignia(a["tipo"]), insignia(actividades.AMBITOS[a["ambito"]], "azul"),
                    cls="flex gap-1.5"),
                H2(a["titulo"], cls="mt-2"), cls="min-w-0"),
            acciones, cls="flex flex-wrap items-start justify-between gap-4 mb-6"),
        Card(
            dato("Año" if actividades.anual(a) else "Fechas", actividades.fechas_texto(a)),
            dato(ETIQUETA_INSTITUCION.get(a["tipo"], "Lugar"), _lugar(a)),
            dato("Artículos arbitrados", str(a["cantidad"]) if a.get("cantidad") else None),
            dato("En el catálogo de revistas", "Sí" if a.get("revista_id") else None),
            dato("Monto", f"{a['monto']:,} {a['moneda'] or ''}".replace(",", ".") if a.get("monto") is not None else None),
            dato("Financiamiento", actividades.FINANCIAMIENTOS.get(a.get("financiamiento") or "")),
            dato("Ingresos para la unidad",
                 f"{a['ingresos']:,} {a['moneda'] or ''}".replace(",", ".") if a.get("ingresos") is not None else None),
            dato("Modalidad", actividades.MODALIDADES[a["modalidad"]]) if a["tipo"] not in (
                actividades.PREMIO, actividades.ARBITRAJE) else "",
            dato("Enlace", A(a["url"], href=a["url"], target="_blank", rel="noopener noreferrer",
                             cls="text-primary hover:underline break-all") if a["url"] else None),
            dato("Participantes", Div(*[Div(enlace_persona(p),
                                            Span(f" · {actividades.ROLES[p['rol']]}",
                                                 cls=TextPresets.muted_sm)) for p in participantes_])),
            dato("Proyectos", Div(*insignias_proyectos(proyectos.vinculos_de("actividad", a["id"])),
                                  cls="flex flex-wrap gap-1.5")
                 if proyectos.vinculos_de("actividad", a["id"]) else None),
            dato("Líneas de investigación", insignias_lineas(lin) if (lin := lineas.de_registro("actividad", a["id"]))
                 else None),
            dato("Presentaciones", Div(*[Div(A(p["titulo"], href=f"/productos/{p['id']}",
                                               cls="text-primary hover:underline"))
                                         for p in presentaciones]) if presentaciones else None),
        ),
        Card(H3("Descripción", cls="text-base font-semibold mb-2"),
             P(a["descripcion"], cls="whitespace-pre-line")) if a["descripcion"] else "",
        Card(H3("Archivos adjuntos", cls="text-base font-semibold mb-2"),
             P("Certificados de participación, afiches, programas…", cls=(TextPresets.muted_sm, "mb-2")),
             seccion_adjuntos("actividad", a["id"], editable)) if editable or permisos.puede(auth, "ver_evidencias") else "",
        id="ficha-actividad", hx_get=f"/actividades/{a['id']}/ficha",
        hx_trigger=f"{EVENTO} from:body", hx_swap="outerHTML", cls="space-y-6")


@rt("/actividades/{aid}/ficha")
def get(auth, aid: int):
    a = actividades.obtener(aid)
    return ficha(a, auth) if a else Redirect("/actividades")


@rt("/actividades/{aid}")
def get(auth, aid: int):
    a = actividades.obtener(aid)
    if not a:
        return Redirect("/actividades")
    return pagina(a["titulo"],
                  A(UkIcon("arrow-left", height=14, width=14), "Mis actividades", href="/actividades",
                    cls="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"),
                  ficha(a, auth), usuario=auth, seccion="actividades")
