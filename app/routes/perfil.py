"""«Mi perfil»: edición en línea por sección, áreas MSC con autocompletar y foto.

Patrón de cada sección editable (datos, identificadores, bio):
  GET  /perfil/<s>          vista (también sirve para «Cancelar»)
  GET  /perfil/<s>/editar   formulario que reemplaza a la vista
  PUT  /perfil/<s>          guarda y devuelve la vista, o el formulario con errores
Toda modificación devuelve además, fuera de banda, la tarjeta de completitud actualizada.
"""
import json

import fasthtml.common as fh

from fasthtml.common import A, APIRouter, Datalist, Div, Hr, Li, Option, P, Select, Span, Ul, UploadFile
from fasthtml.toaster import add_toast
from monsterui.all import (H2, Button, ButtonT, Card, Form, FormLabel, Input, LabelInput,
                           LabelTextArea, Progress, TextPresets, UkIcon)

from app import fotos, msc, perfiles, usuarios
from app.components.layout import mensaje_error, pagina
from app.components.perfil import (avatar, chip_msc, lista_identificadores, seccion,
                                   texto_con_parrafos)
from app.db import auditar, get_db
from app.identificadores import IDENTIFICADORES, normalizar_todos

rt = APIRouter()

ID_COMPLETITUD = "perfil-completitud"


# --- Piezas comunes ----------------------------------------------------------

def _boton_editar(nombre):
    return Button(UkIcon("pencil", height=14, width=14), "Editar", cls=(ButtonT.ghost, ButtonT.sm),
                  hx_get=f"/perfil/{nombre}/editar", hx_target=f"#seccion-{nombre}",
                  hx_swap="outerHTML")


def _botones_form(nombre):
    return Div(Button("Cancelar", type="button", cls=ButtonT.ghost, hx_get=f"/perfil/{nombre}",
                      hx_target=f"#seccion-{nombre}", hx_swap="outerHTML"),
               Button("Guardar", type="submit", cls=ButtonT.primary),
               cls="flex justify-end gap-2")


def _form(nombre, *campos):
    return Form(*campos, _botones_form(nombre), hx_put=f"/perfil/{nombre}",
                hx_target=f"#seccion-{nombre}", hx_swap="outerHTML", cls="space-y-4")


def tarjeta_completitud(p, oob=False):
    porcentaje, faltan = perfiles.completitud(p, len(perfiles.areas(p["id"])))
    detalle = (P("Falta: " + ", ".join(faltan) + ".", cls=TextPresets.muted_sm) if faltan
               else P("¡Perfil completo!", cls="text-sm text-green-600"))
    return Div(Div(Span("Perfil completo", cls="text-sm font-medium"),
                   Span(f"{porcentaje} %", cls="text-sm font-semibold"),
                   cls="flex justify-between mb-1"),
               Progress(value=str(porcentaje), cls="mb-2"), detalle,
               id=ID_COMPLETITUD, hx_swap_oob="true" if oob else None)


def _respuesta(uid, fragmento):
    return fragmento, tarjeta_completitud(perfiles.obtener(uid), oob=True)


# --- Datos básicos -----------------------------------------------------------

def vista_datos(p):
    def fila(etiqueta, valor):
        return Div(Span(etiqueta, cls=(TextPresets.muted_sm, "w-40 shrink-0")),
                   Span(valor or "—"), cls="flex flex-col sm:flex-row gap-1 py-1")
    return seccion("seccion-datos", "Datos básicos",
                   fila("Nombre", f"{p['nombres']} {p['apellidos']}"),
                   fila("Correo", p["email"]),
                   fila("Categoría", perfiles.categoria_texto(p["categoria"])),
                   fila("Grado académico", p["grado"]),
                   fila("Cargo", p["cargo"]),
                   fila("Unidad o grupo", p["unidad"]),
                   accion=_boton_editar("datos"))


def form_datos(d, errores=()):
    return seccion("seccion-datos", "Datos básicos", _form(
        "datos",
        mensaje_error(*errores),
        Div(LabelInput("Nombres", id="nombres", value=d["nombres"], required=True, maxlength=80),
            LabelInput("Apellidos", id="apellidos", value=d["apellidos"], required=True, maxlength=80),
            cls="grid grid-cols-1 sm:grid-cols-2 gap-4"),
        P(f"Correo: {d['email']} · Categoría: {perfiles.categoria_texto(d['categoria'])} "
          "(los cambia la administración).", cls=TextPresets.muted_sm),
        Div(FormLabel("Grado académico", fr="grado"),
            Select(Option("—", value=""),
                   *[Option(g, value=g, selected=g == d["grado"]) for g in perfiles.GRADOS],
                   id="grado", name="grado", cls="uk-select"),
            cls="space-y-2"),
        LabelInput("Cargo", id="cargo", value=d["cargo"] or "", list="cargos", maxlength=100,
                   placeholder="Investigador(a) asociado(a)"),
        Datalist(*[Option(value=c) for c in perfiles.CARGOS_SUGERIDOS], id="cargos"),
        LabelInput("Unidad o grupo", id="unidad", value=d["unidad"] or "", maxlength=120,
                   placeholder="Grupo de Teoría de Números"),
    ))


@rt("/perfil/datos")
def get(auth):
    return vista_datos(perfiles.obtener(auth["id"]))


@rt("/perfil/datos/editar")
def get(auth):
    return form_datos(perfiles.obtener(auth["id"]))


@rt("/perfil/datos")
def put(auth, sess, nombres: str = "", apellidos: str = "", grado: str = "", cargo: str = "",
        unidad: str = ""):
    p = perfiles.obtener(auth["id"])
    d = dict(nombres=nombres.strip(), apellidos=apellidos.strip(), grado=grado.strip() or None,
             cargo=cargo.strip() or None, unidad=unidad.strip() or None)
    errores = []
    if not d["nombres"] or not d["apellidos"]:
        errores.append("Nombres y apellidos son obligatorios.")
    if d["grado"] and d["grado"] not in perfiles.GRADOS:
        errores.append("Grado académico no válido.")
    for campo, maximo in (("nombres", 80), ("apellidos", 80), ("cargo", 100), ("unidad", 120)):
        if d[campo] and len(d[campo]) > maximo:
            errores.append(f"«{campo.capitalize()}» admite hasta {maximo} caracteres.")
    if errores:
        return form_datos({**p, **d}, errores)
    perfiles.actualizar_datos(auth["id"], **d)
    auditar(auth["id"], "editar_perfil", "investigador", auth["id"], "datos")
    add_toast(sess, "Datos guardados.", "success")
    return _respuesta(auth["id"], vista_datos(perfiles.obtener(auth["id"])))


# --- Identificadores ---------------------------------------------------------

def vista_identificadores(p):
    return seccion("seccion-identificadores", "Identificadores de autor", lista_identificadores(p),
                   accion=_boton_editar("identificadores"))


def form_identificadores(valores, errores=None):
    errores = errores or {}
    campos = []
    for campo, (etiqueta, _, _, ejemplo) in IDENTIFICADORES.items():
        error = errores.get(campo)
        campos.append(Div(
            LabelInput(etiqueta, id=campo, value=valores.get(campo) or "", placeholder=ejemplo,
                       aria_invalid="true" if error else None,
                       input_cls="border-red-500" if error else ""),
            P(error, cls="text-sm text-red-600 mt-1") if error else ""))
    return seccion("seccion-identificadores", "Identificadores de autor", _form(
        "identificadores",
        P("Puede pegar la dirección de su perfil; se guarda solo el identificador.",
          cls=TextPresets.muted_sm),
        *campos))


@rt("/perfil/identificadores")
def get(auth):
    return vista_identificadores(perfiles.obtener(auth["id"]))


@rt("/perfil/identificadores/editar")
def get(auth):
    return form_identificadores(perfiles.obtener(auth["id"]))


@rt("/perfil/identificadores")
def put(auth, sess, orcid: str = "", mr_id: str = "", zbmath_id: str = "", arxiv_id: str = "",
        scholar_url: str = "", pagina_web: str = ""):
    valores, errores = normalizar_todos(dict(orcid=orcid, mr_id=mr_id, zbmath_id=zbmath_id,
                                             arxiv_id=arxiv_id, scholar_url=scholar_url,
                                             pagina_web=pagina_web))
    if errores:
        return form_identificadores(valores, errores)
    perfiles.actualizar_identificadores(auth["id"], valores)
    auditar(auth["id"], "editar_perfil", "investigador", auth["id"], "identificadores")
    add_toast(sess, "Identificadores guardados.", "success")
    return _respuesta(auth["id"], vista_identificadores(perfiles.obtener(auth["id"])))


# --- Resumen de investigación (con LaTeX) ------------------------------------

def vista_bio(p):
    return seccion("seccion-bio", "Resumen de investigación", texto_con_parrafos(p["bio"]),
                   accion=_boton_editar("bio"))


def form_bio(bio, errores=()):
    return seccion("seccion-bio", "Resumen de investigación", _form(
        "bio",
        mensaje_error(*errores),
        LabelTextArea("Texto", id="bio", value=bio or "", rows=8, maxlength=perfiles.LARGO_BIO,
                      placeholder="Mi trabajo se centra en la función $\\zeta(s)$ y …",
                      hx_post="/perfil/bio/vista-previa", hx_target="#bio-vista-previa",
                      hx_trigger="input changed delay:500ms, load"),
        P("Separe párrafos con una línea en blanco. Use $…$ para fórmulas en línea y $$…$$ "
          f"para fórmulas centradas. Máximo {perfiles.LARGO_BIO} caracteres.",
          cls=TextPresets.muted_sm),
        Div(Span("Vista previa", cls=(TextPresets.muted_sm, "block mb-2")),
            Div(id="bio-vista-previa"),
            cls="rounded-md border border-dashed border-border p-4"),
    ))


@rt("/perfil/bio")
def get(auth):
    return vista_bio(perfiles.obtener(auth["id"]))


@rt("/perfil/bio/editar")
def get(auth):
    return form_bio(perfiles.obtener(auth["id"])["bio"])


@rt("/perfil/bio/vista-previa")
def post(bio: str = ""):
    return texto_con_parrafos(bio[:perfiles.LARGO_BIO], vacio="(vacío)")


@rt("/perfil/bio")
def put(auth, sess, bio: str = ""):
    bio = bio.strip()
    if len(bio) > perfiles.LARGO_BIO:
        return form_bio(bio, [f"El resumen admite hasta {perfiles.LARGO_BIO} caracteres "
                              f"(tiene {len(bio)})."])
    perfiles.actualizar_bio(auth["id"], bio or None)
    auditar(auth["id"], "editar_perfil", "investigador", auth["id"], "bio")
    add_toast(sess, "Resumen guardado.", "success")
    return _respuesta(auth["id"], vista_bio(perfiles.obtener(auth["id"])))


# --- Áreas MSC2020 -----------------------------------------------------------

def seccion_areas(uid, error=None):
    areas = perfiles.areas(uid)

    def acciones(a):
        codigo = a["codigo"]
        estrella = "" if a["principal"] else fh.Button(
            UkIcon("star", height=12, width=12), cls="hover:text-amber-500 p-0.5", type="button",
            title="Marcar como área principal", aria_label=f"Marcar {codigo} como principal",
            hx_post=f"/perfil/msc/{codigo}/principal", hx_target="#seccion-areas",
            hx_swap="outerHTML")
        quitar = fh.Button(UkIcon("x", height=12, width=12), cls="hover:text-red-600 p-0.5",
                           type="button",
                        title="Quitar", aria_label=f"Quitar {codigo}",
                        hx_delete=f"/perfil/msc/{codigo}", hx_target="#seccion-areas",
                        hx_swap="outerHTML")
        return estrella, quitar

    chips = [chip_msc(a, *acciones(a), principal=bool(a["principal"])) for a in areas]
    lleno = len(areas) >= perfiles.MAX_AREAS
    buscador = Div(
        Input(type="search", name="q", autocomplete="off", disabled=lleno,
              placeholder=("Máximo de áreas alcanzado" if lleno
                           else "Agregar área: código (11M) o tema en inglés (zeta, graph coloring)"),
              hx_get="/perfil/msc/buscar", hx_target="#msc-resultados",
              hx_trigger="input changed delay:250ms, search", aria_label="Buscar área MSC"),
        Div(id="msc-resultados"),
        cls="relative mt-4")
    return seccion(
        "seccion-areas", "Áreas de investigación (MSC2020)",
        mensaje_error(error) if error else "",
        Div(*chips, cls="flex flex-wrap gap-2") if chips
        else P("Aún no declara áreas.", cls=TextPresets.muted_sm),
        P(f"La marcada con ★ es su área principal y se muestra en el directorio. "
          f"Hasta {perfiles.MAX_AREAS} áreas.", cls=(TextPresets.muted_sm, "mt-3")) if chips else "",
        buscador)


@rt("/perfil/msc/buscar")
def get(auth, q: str = ""):
    ya = tuple(a["codigo"] for a in perfiles.areas(auth["id"]))
    resultados = msc.buscar(q, excluir=ya)
    if not q.strip():
        return ""
    if not resultados:
        return Div(P("Sin resultados. Pruebe con otro término (el catálogo MSC está en inglés).",
                     cls=(TextPresets.muted_sm, "p-3")),
                   cls="absolute z-20 w-full mt-1 rounded-md border border-border bg-background shadow-lg")
    secciones = {}

    def ruta_seccion(m):
        if m["nivel"] == 1:
            return ""
        s = secciones.setdefault(m["codigo"][:2], msc.seccion(m["codigo"]))
        return s["texto"] + " › " if s else ""

    return Ul(*[Li(fh.Button(
        Span(m["codigo"], cls="font-mono text-xs font-semibold w-14 shrink-0 nomath"),
        Span(Span(ruta_seccion(m), cls=TextPresets.muted_sm), m["texto"], cls="text-sm"),
        type="button", cls="w-full flex gap-3 items-baseline text-left px-3 py-2 "
                           "hover:bg-muted focus:bg-muted focus:outline-none",
        hx_post="/perfil/msc", hx_vals=json.dumps({"codigo": m["codigo"]}),
        hx_target="#seccion-areas", hx_swap="outerHTML")) for m in resultados],
        cls="absolute z-20 w-full mt-1 max-h-80 overflow-y-auto rounded-md border border-border "
            "bg-background shadow-lg divide-y divide-border", role="listbox")


@rt("/perfil/msc")
def post(auth, codigo: str = ""):
    error = perfiles.agregar_area(auth["id"], codigo.strip())
    return _respuesta(auth["id"], seccion_areas(auth["id"], error))


@rt("/perfil/msc/{codigo}")
def delete(auth, codigo: str):
    perfiles.quitar_area(auth["id"], codigo)
    return _respuesta(auth["id"], seccion_areas(auth["id"]))


@rt("/perfil/msc/{codigo}/principal")
def post(auth, codigo: str):
    perfiles.marcar_principal(auth["id"], codigo)
    return seccion_areas(auth["id"])


# --- Foto ----------------------------------------------------------------------

def seccion_foto(p, error=None):
    subtitulo = " · ".join(x for x in (p["cargo"], p["unidad"]) if x)
    return Div(
        Div(avatar(p, "size-32", "text-4xl"),
            Div(H2(f"{p['nombres']} {p['apellidos']}", cls="text-xl"),
                P(subtitulo, cls=TextPresets.muted_sm) if subtitulo else "",
                cls="text-center"),
            cls="flex flex-col items-center gap-3"),
        mensaje_error(error) if error else "",
        Form(
            Div(Button(UkIcon("camera", height=14, width=14),
                       "Cambiar foto" if p["foto"] else "Subir foto", type="button",
                       cls=(ButtonT.default, ButtonT.sm),
                       onclick="this.closest('form').querySelector('input[type=file]').click()"),
                Button(UkIcon("trash-2", height=14, width=14), "Quitar", type="button",
                       cls=(ButtonT.ghost, ButtonT.sm), hx_delete="/perfil/foto",
                       hx_target="#seccion-foto", hx_swap="outerHTML",
                       hx_confirm="¿Quitar la foto de perfil?") if p["foto"] else "",
                cls="flex justify-center gap-2"),
            Input(type="file", name="foto", accept="image/jpeg,image/png,image/webp", cls="hidden",
                  aria_label="Foto de perfil"),
            P("JPG, PNG o WebP hasta 5 MB. Se recorta en un cuadrado.",
              cls=(TextPresets.muted_sm, "text-center")),
            Span(UkIcon("loader-circle", height=16, width=16, cls="animate-spin"), " Subiendo…",
                 id="foto-subiendo", cls="htmx-indicator text-sm text-center block"),
            hx_post="/perfil/foto", hx_trigger="change", hx_encoding="multipart/form-data",
            hx_target="#seccion-foto", hx_swap="outerHTML", hx_indicator="#foto-subiendo",
            cls="space-y-2"),
        id="seccion-foto", cls="space-y-4")


@rt("/perfil/foto")
async def post(auth, sess, foto: UploadFile = None):
    p = perfiles.obtener(auth["id"])
    if foto is None or not foto.filename:
        return seccion_foto(p, "Seleccione una imagen.")
    try:
        jpeg = fotos.procesar(await foto.read(fotos.MAX_BYTES + 1))
    except ValueError as e:
        return seccion_foto(p, str(e))
    perfiles.actualizar_foto(auth["id"], fotos.guardar(auth["id"], jpeg, p["foto"]))
    auditar(auth["id"], "editar_perfil", "investigador", auth["id"], "foto")
    add_toast(sess, "Foto actualizada.", "success")
    return _respuesta(auth["id"], seccion_foto(perfiles.obtener(auth["id"])))


@rt("/perfil/foto")
def delete(auth):
    p = perfiles.obtener(auth["id"])
    fotos.borrar(p["foto"])
    perfiles.actualizar_foto(auth["id"], None)
    return _respuesta(auth["id"], seccion_foto(perfiles.obtener(auth["id"])))


# --- Privacidad y avisos -----------------------------------------------------------

def seccion_preferencias(p, avisos_correo):
    def interruptor(nombre, activo, titulo, ayuda):
        return fh.Label(
            Input(type="checkbox", name=nombre, value="1", checked=bool(activo),
                  cls="uk-toggle-switch uk-toggle-switch-primary min-w-9 mt-0.5",
                  hx_post=f"/perfil/preferencias/{nombre}", hx_trigger="change",
                  hx_target="#seccion-preferencias", hx_swap="outerHTML"),
            Div(Span(titulo, cls="text-sm font-medium"), Span(ayuda, cls=TextPresets.muted_sm),
                cls="flex flex-col"),
            cls="flex items-start gap-3 cursor-pointer")
    return seccion(
        "seccion-preferencias", "Privacidad y avisos",
        Div(interruptor("perfil_publico", p["perfil_publico"], "Perfil público",
                        "Publica en la web del portal su nombre, cargo, áreas, resumen, identificadores, "
                        "foto y productos publicados. No se muestran su correo, sus actividades ni los "
                        "productos en preparación."),
            A(UkIcon("external-link", height=14, width=14), "Ver mi perfil público",
              href=f"/publico/investigadores/{p['id']}", target="_blank",
              cls="inline-flex items-center gap-1 text-sm text-primary hover:underline ml-12")
            if p["perfil_publico"] else "",
            interruptor("avisos_correo", avisos_correo, "Avisos por correo",
                        "Cuando alguien propone algo a un proyecto que usted dirige, o cuando revisan "
                        "una propuesta suya."),
            cls="space-y-4"))


@rt("/perfil/preferencias/{nombre}")
def post(auth, sess, nombre: str, perfil_publico: bool = False, avisos_correo: bool = False):
    if nombre == "perfil_publico":
        perfiles.actualizar_campos(auth["id"], perfil_publico=int(perfil_publico))
        auditar(auth["id"], "perfil_publico" if perfil_publico else "perfil_privado", "investigador", auth["id"])
        add_toast(sess, "Su perfil ahora es público." if perfil_publico else "Su perfil ya no es público.",
                  "success")
    elif nombre == "avisos_correo":
        get_db().execute("UPDATE usuario SET avisos_correo = ? WHERE id = ?", [int(avisos_correo), auth["id"]])
    p = perfiles.obtener(auth["id"])
    return seccion_preferencias(p, usuarios.por_id(auth["id"])["avisos_correo"])


# --- Página ----------------------------------------------------------------------

@rt("/perfil")
def get(auth):
    p = perfiles.obtener(auth["id"])
    return pagina(
        "Mi perfil",
        Div(Div(H2("Mi perfil"),
                P("Lo que registre aquí se muestra en el directorio del instituto y más adelante "
                  "alimentará su CV.", cls=TextPresets.muted_sm)),
            A(UkIcon("eye", height=16, width=16), "Ver como lo ven otros",
              href=f"/investigadores/{p['id']}", cls="inline-flex items-center gap-1 text-sm "
                                                      "text-primary hover:underline"),
            cls="flex flex-wrap items-end justify-between gap-4 mb-6"),
        Div(
            Div(Card(seccion_foto(p), Hr(cls="my-4 border-border"), tarjeta_completitud(p)),
                cls="lg:col-span-1 space-y-6"),
            Div(vista_datos(p), vista_identificadores(p), seccion_areas(p["id"]), vista_bio(p),
                seccion_preferencias(p, usuarios.por_id(auth["id"])["avisos_correo"]),
                cls="lg:col-span-2 space-y-6"),
            cls="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start"),
        usuario=auth, seccion="perfil")
