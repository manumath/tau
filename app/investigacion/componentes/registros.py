"""Piezas de actividades y productos propias de la investigación: adjuntos y vinculación a proyectos."""
import fasthtml.common as fh
from fasthtml.common import A, Div, Input, Li, Option, P, Select, Span, Ul
from monsterui.all import Button, ButtonT, TextPresets, UkIcon

from app.comun.componentes.layout import mensaje_error
from app.comun.componentes.registros import insignia
from app.investigacion import adjuntos


def seccion_adjuntos(entidad: str, entidad_id: int, editable: bool, error: str | None = None):
    lista = adjuntos.listar(entidad, entidad_id)
    seccion_id = f"adjuntos-{entidad}-{entidad_id}"
    filas = [Li(
        UkIcon("file-text" if a["mime"] == "application/pdf" else "image", height=16, width=16,
               cls="shrink-0 text-muted-foreground"),
        A(a["nombre"], href=f"/adjuntos/{a['id']}", cls="text-primary hover:underline truncate"),
        Span(adjuntos.tamano_texto(a["tamano"]), cls=(TextPresets.muted_sm, "shrink-0")),
        fh.Button(UkIcon("trash-2", height=14, width=14), type="button",
                  cls="ml-auto p-1 rounded hover:bg-muted hover:text-destructive",
                  hx_delete=f"/adjuntos/{a['id']}", hx_target=f"#{seccion_id}",
                  hx_swap="outerHTML", hx_confirm=f"¿Eliminar «{a['nombre']}»?",
                  title="Eliminar", aria_label=f"Eliminar {a['nombre']}") if editable else "",
        cls="flex items-center gap-2 py-2") for a in lista]
    subir = fh.Form(
        Button(UkIcon("paperclip", height=14, width=14), "Adjuntar archivo", type="button",
               cls=(ButtonT.default, ButtonT.sm),
               data_accion="elegir-archivo"),
        Input(type="file", name="archivo", accept="application/pdf,image/png,image/jpeg",
              cls="hidden", aria_label="Archivo adjunto"),
        Span("PDF, PNG o JPG hasta 20 MB.", cls=TextPresets.muted_sm),
        Span(UkIcon("loader-circle", height=14, width=14, cls="animate-spin"), " Subiendo…",
             cls="htmx-indicator text-sm"),
        hx_post=f"/adjuntos/{entidad}/{entidad_id}", hx_trigger="change",
        hx_encoding="multipart/form-data", hx_target=f"#{seccion_id}", hx_swap="outerHTML",
        cls="flex flex-wrap items-center gap-3 mt-3") if editable else ""
    return Div(
        mensaje_error(error) if error else "",
        Ul(*filas, cls="divide-y divide-border") if filas
        else P("Sin archivos adjuntos.", cls=TextPresets.muted_sm),
        subir, id=seccion_id)


TONO_VINCULO = {"pendiente": "ambar", "aprobado": "azul", "rechazado": "rojo"}


ICONO_VINCULO = {"pendiente": "clock", "aprobado": "folder-check", "rechazado": "circle-x"}


def insignias_proyectos(vinculos: list[dict]):
    """Una insignia por proyecto: «Proyecto X · pendiente». El motivo de rechazo va en el title."""
    from app.investigacion.proyectos import ESTADOS_VINCULO
    agradece = {1: " · agradece", 0: " · no agradece"}
    return [insignia(f"{v['proyecto']} · {ESTADOS_VINCULO[v['estado']].lower()}{agradece.get(v.get('agradece'), '')}",
                     TONO_VINCULO[v["estado"]], icono=ICONO_VINCULO[v["estado"]],
                     titulo=f"Motivo: {v['comentario']}" if v.get("comentario") else None)
            for v in vinculos]


def casillas_proyectos(tipo: str, registro_id: int | None, usuario: dict,
                       marcados_form: list[int] | None = None, preseleccion: int | None = None,
                       agradece_form: dict | None = None):
    """Casillas «Vincular a proyectos» para el formulario de una actividad o un producto. En los
    productos, cada proyecto lleva además «¿agradece al proyecto?» (campo `agradece` con valores
    '<proyecto>:1', '<proyecto>:0' o '<proyecto>:')."""
    from app.investigacion import proyectos
    disponibles = {p["id"]: p for p in proyectos.para_proponer(usuario["id"])}
    vinculos = {v["proyecto_id"]: v for v in proyectos.vinculos_de(tipo, registro_id)} \
        if registro_id else {}
    ids = list(dict.fromkeys([*disponibles, *vinculos]))
    if not ids:
        return ""
    filas = []
    for pid in ids:
        p = disponibles.get(pid)
        v = vinculos.get(pid)
        nombre = p["nombre"] if p else v["proyecto"]
        if marcados_form is not None:
            marcado = pid in marcados_form or (v and v["estado"] == "aprobado")
        else:
            marcado = bool(v) or pid == preseleccion
        directo = p and p["mi_rol"] in proyectos.ROLES_RESPONSABLES
        if v and v["estado"] == "aprobado":
            nota = Span("aprobado · solo un responsable puede desvincularlo", cls=TextPresets.muted_sm)
        elif v and v["estado"] == "pendiente":
            nota = Span("propuesta pendiente de aprobación", cls="text-sm text-amber-600")
        elif v and v["estado"] == "rechazado":
            nota = Span(f"rechazado: «{v['comentario']}». Si lo deja marcado, se vuelve a proponer.",
                        cls="text-sm text-destructive")
        elif directo:
            nota = Span("usted es responsable: se vincula directamente", cls=TextPresets.muted_sm)
        else:
            nota = Span("quedará pendiente hasta que un responsable lo apruebe", cls=TextPresets.muted_sm)
        bloqueado = (v and v["estado"] == "aprobado") or not p
        agradece = ""
        if tipo == "producto":
            actual = agradece_form.get(pid) if agradece_form is not None else (v or {}).get("agradece")
            actual = "" if actual is None else str(actual)
            agradece = Select(*[Option(t, value=f"{pid}:{val}", selected=val == actual) for val, t in
                                (("", "Agradecimiento sin declarar"), ("1", "Agradece al proyecto"),
                                 ("0", "No agradece al proyecto"))],
                              name="agradece", aria_label=f"¿La publicación agradece a {nombre}?",
                              title="Los fondos exigen que la publicación agradezca al proyecto.",
                              cls="uk-select h-8 w-56 text-sm ml-auto shrink-0"
                                  + (" border-amber-400 text-amber-700" if actual == "" else ""))
        filas.append(Div(fh.Label(
            Input(type="checkbox", name="proyecto", value=str(pid), checked=marcado,
                  disabled=bloqueado, cls="uk-checkbox mt-0.5"),
            Div(Span(nombre, cls="font-medium text-sm"), nota, cls="flex flex-col"),
            cls="flex items-start gap-2"), agradece, cls="flex flex-wrap items-start gap-2"))
    return Div(Span("Vincular a proyectos", cls="uk-form-label"),
               Div(*filas, cls="space-y-2 rounded-md border border-border p-3"),
               cls="space-y-2")
