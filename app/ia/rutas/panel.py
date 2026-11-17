"""Panel de revisión de los borradores de IA (PLAN §59, etapa 0b). Lo reutilizan todas las pantallas que ofrecen una
función: `bloque(...)` muestra el botón para pedir un borrador o, si hay uno, el panel para aprobarlo, corregirlo o
rechazarlo, con la valoración y el motivo. Nada de esto se imprime (`no-imprimir`): en el documento solo aparece el
texto aprobado con su marca (`texto_aprobado`).
"""
import json

from fasthtml.common import A, Div, Input, Label, Option, P, Select, Span
from monsterui.all import Button, ButtonT, Form, TextArea, TextPresets, UkIcon

from app.comun.componentes.layout import ID_MODAL, boton_espera, mensaje_error
from app.comun.componentes.registros import insignia
from app.ia import servicio
from app.ia.funciones import obtener as funcion

VALORACIONES = {"": "Sin valorar", "5": "5 · Muy útil", "4": "4 · Útil", "3": "3 · Regular", "2": "2 · Poco útil",
                "1": "1 · Nada útil"}


def volver_seguro(volver: str | None) -> str:
    """Solo direcciones internas («/…», nunca «//otro.sitio»)."""
    v = (volver or "").strip()
    return v if v.startswith("/") and not v.startswith("//") and "\\" not in v else "/"


def id_bloque(clave: str, entidad: str) -> str:
    return "ia-" + "".join(c if c.isalnum() else "-" for c in f"{clave}-{entidad}")


def marca(uso: dict):
    """La etiqueta visible del texto (principio 4): se imprime junto al texto aprobado."""
    return P(UkIcon("sparkles", height=12, width=12), servicio.marca(uso),
             cls="flex items-center gap-1 text-xs text-muted-foreground italic mt-1")


def texto_aprobado(clave: str, entidad: str, cls: str = "whitespace-pre-line"):
    """El último texto aprobado de ese documento con su marca, o "" si no hay."""
    uso = servicio.aprobado(clave, entidad)
    return Div(Div(uso["texto_final"], cls=cls), marca(uso)) if uso else ""


def marca_si(clave: str, entidad: str, texto: str | None):
    """La marca, si `texto` es el último aprobado de ese documento (p. ej., el resumen del perfil sin cambios
    posteriores); "" si la persona lo reescribió después o nunca usó la IA."""
    uso = servicio.aprobado(clave, entidad) if texto else None
    return marca(uso) if uso and (uso["texto_final"] or "").strip() == texto.strip() else ""


def _guia():
    return A(UkIcon("book-open", height=14, width=14), "Guía de uso crítico", href="#",
             hx_get="/ia/guia", hx_target=f"#{ID_MODAL}", cls="inline-flex items-center gap-1 text-sm text-primary hover:underline")


def _opciones(f, uso):
    sugeridas = set((uso.get("texto_generado") or "").split(","))
    filas = [Label(Input(type="checkbox", name="elegido", value=v, checked=v in sugeridas, cls="uk-checkbox mt-0.5"),
                   Span(A(etiqueta, href=enlace, target="_blank", cls="hover:underline") if enlace else etiqueta,
                        insignia("Sugerida", "azul", icono="sparkles") if v in sugeridas else "",
                        cls="flex flex-wrap items-center gap-2"),
                   cls="flex items-start gap-2 text-sm py-1")
             for v, etiqueta, enlace in f.opciones(uso)]
    if not sugeridas - {""}:
        filas.insert(0, P("La IA no encontró opciones que correspondan. Puede marcar las que usted elija o descartar.",
                          cls=TextPresets.muted_sm))
    return Div(*filas, cls="max-h-80 overflow-y-auto space-y-0.5")


def panel(uso: dict, auth: dict, volver: str, errores=()):
    """Panel de un uso: esperando, con error, por revisar o solo lectura (si no le corresponde revisarlo)."""
    f = funcion(uso["funcion_clave"])
    volver = volver_seguro(volver)
    pid = f"ia-uso-{uso['id']}"
    caja = "no-imprimir rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-3"
    if uso["estado"] == "generando":
        return Div(Div(UkIcon("loader-circle", height=16, width=16, cls="animate-spin"),
                       Span(f"La IA está preparando el borrador ({f.nombre.lower()}). Puede seguir trabajando: "
                            "le llegará un aviso cuando esté listo."), cls="flex items-center gap-2 text-sm"),
                   id=pid, cls=caja, hx_get=f"/ia/uso/{uso['id']}/panel?volver={volver}", hx_trigger="every 3s",
                   hx_swap="outerHTML")
    if uso["estado"] == "error":
        return Div(P(servicio.NO_DISPONIBLE, cls="text-sm text-destructive"),
                   A("Volver a cargar la página", href=volver, cls="text-sm text-primary hover:underline"),
                   id=pid, cls=caja)
    if uso["estado"] != "borrador_ia":
        return Div(P(f"Borrador revisado: {uso['estado']}.", cls=TextPresets.muted_sm), id=pid, cls=caja)
    encabezado = Div(insignia("Borrador generado con IA", "azul", icono="sparkles"),
                     Span(f.nombre, cls="text-sm font-medium"), _guia(), cls="flex flex-wrap items-center gap-2")
    if not f.puede_aprobar(auth, uso):
        return Div(encabezado, Div(uso["texto_generado"], cls="text-sm whitespace-pre-line"),
                   P(f"Lo revisa {f.revisor}. No surte efecto hasta que lo apruebe.", cls=TextPresets.muted_sm),
                   id=pid, cls=caja)
    contenido = (_opciones(f, uso) if f.opciones else
                 TextArea(uso["texto_generado"], name="texto_final", rows=10, cls="uk-textarea text-sm",
                          aria_label="Texto del borrador"))
    ayuda = ("Marque lo que acepta y desmarque lo que no corresponde." if f.opciones else
             "Corrija el texto lo que haga falta antes de aprobarlo: el sistema registra si lo cambió.")
    return Div(
        Form(encabezado, mensaje_error(*errores), P(ayuda, " Nada se guarda hasta que usted lo apruebe.",
                                                    cls=TextPresets.muted_sm),
             contenido,
             Div(Div(Label("¿Le fue útil?", fr=f"val-{uso['id']}", cls="text-sm"),
                     Select(*[Option(t, value=v) for v, t in VALORACIONES.items()], name="valoracion",
                            id=f"val-{uso['id']}", cls="uk-select uk-form-small"), cls="space-y-1"),
                 Div(Label("Motivo o comentario (opcional)", fr=f"mot-{uso['id']}", cls="text-sm"),
                     Input(name="motivo", id=f"mot-{uso['id']}", maxlength="1000", cls="uk-input uk-form-small"),
                     cls="space-y-1 sm:col-span-2"),
                 cls="grid grid-cols-1 sm:grid-cols-3 gap-3"),
             Input(type="hidden", name="volver", value=volver),
             Div(Button(UkIcon("x", height=14, width=14), "Descartar", type="submit", name="decision",
                        value="rechazar", cls=(ButtonT.ghost, ButtonT.sm)),
                 Button(UkIcon("check", height=14, width=14), "Aprobar", type="submit", name="decision",
                        value="aprobar", cls=(ButtonT.primary, ButtonT.sm)),
                 cls="flex flex-wrap justify-end gap-2"),
             hx_post=f"/ia/uso/{uso['id']}/decidir", hx_target=f"#{pid}", hx_swap="outerHTML", cls="space-y-3"),
        id=pid, cls=caja)


def bloque(clave: str, entidad: str, auth: dict, url_pedir: str, volver: str, etiqueta: str = "Pedir borrador con IA",
           motivo_no: str | None = None):
    """El botón para pedir un borrador o el panel del que está en curso. Vacío si la función no está activa o la persona
    no puede pedirla. `motivo_no`: por qué hoy no se puede pedir (p. ej., «menos de 10 respuestas»)."""
    f = funcion(clave)
    if not f or not servicio.activa(clave) or not f.puede_pedir(auth, entidad):
        return Div(id=id_bloque(clave, entidad))
    uso = servicio.pendiente(clave, entidad)
    if uso:
        return Div(panel(uso, auth, volver), id=id_bloque(clave, entidad))
    if motivo_no:
        return Div(P(UkIcon("sparkles", height=12, width=12), motivo_no, cls=(TextPresets.muted_sm, "flex items-center gap-1")),
                   id=id_bloque(clave, entidad), cls="no-imprimir")
    return Div(boton_espera(UkIcon("sparkles", height=14, width=14), etiqueta, cls=(ButtonT.default, ButtonT.sm),
                            hx_post=url_pedir, hx_target=f"#{id_bloque(clave, entidad)}", hx_swap="outerHTML",
                            hx_vals=json.dumps({"volver": volver})),
               P("La IA prepara un borrador que usted revisa; no surte efecto sin su aprobación.",
                 cls="text-xs text-muted-foreground mt-1"),
               id=id_bloque(clave, entidad), cls="no-imprimir")


def respuesta_pedido(clave: str, entidad: str, auth: dict, volver: str, pedir):
    """Lo que devuelve una ruta «pedir borrador»: llama a `pedir()` (que invoca a servicio.generar en segundo plano) y
    muestra el panel, o el error para la persona."""
    try:
        uso_id = pedir()
    except servicio.IAError as e:
        return Div(P(str(e), cls="text-sm text-destructive"), id=id_bloque(clave, entidad), cls="no-imprimir")
    return Div(panel(servicio.obtener(uso_id), auth, volver), id=id_bloque(clave, entidad))
