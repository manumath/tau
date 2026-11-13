"""Piezas de interfaz del acceso abierto (PLAN §69, etapa 2), compartidas por su página y por la ficha del producto. Viven
aparte de las rutas para que la ficha pueda usarlas sin importar el módulo de rutas (que importa de `rutas.productos`)."""
from fasthtml.common import A, Div, P, Span
from monsterui.all import Button, ButtonT, TextPresets, UkIcon

from app.comun import formato
from app.comun.componentes.layout import ID_MODAL
from app.comun.componentes.registros import insignia
from app.investigacion import acceso_abierto as aa


def insignias_acceso(a: dict | None) -> list:
    """Situación del texto y de los datos de un producto, como insignias."""
    if not a or not a.get("texto"):
        return [insignia("Acceso sin declarar", "ambar", icono="circle-help")]
    res = [insignia(aa.TEXTOS[a["texto"]], aa.TONOS[a["texto"]], icono="lock-open" if a["texto"] in aa.CON_ENLACE else "lock")]
    if a.get("datos"):
        res.append(insignia(aa.DATOS[a["datos"]], "verde" if a["datos"] == "publicados" else "gris", icono="database"))
    return res


def _enlace(url: str | None, texto: str):
    return A(texto, href=url, target="_blank", rel="noopener noreferrer", cls="text-primary hover:underline") if url else ""


def detalle_acceso(a: dict | None):
    """Texto de la declaración para la ficha: versión, licencia, enlaces, embargo y nota."""
    if not a or not a.get("texto"):
        return None
    partes = []
    if a["version"]:
        partes.append(aa.VERSIONES[a["version"]])
    if a["licencia"]:
        partes.append(aa.LICENCIAS[a["licencia"]])
    if a["embargo_hasta"]:
        partes.append(f"hasta el {formato.fecha(a['embargo_hasta'])}")
    return Div(Div(*insignias_acceso(a), cls="flex flex-wrap gap-1.5"),
               P(" · ".join(partes), cls=TextPresets.muted_sm) if partes else "",
               Div(_enlace(a["enlace"], "Leer el texto"), Span(" · ", cls=TextPresets.muted_sm) if a["enlace"] and a["datos_enlace"] else "",
                   _enlace(a["datos_enlace"], "Datos y código"), cls="text-sm") if a["enlace"] or a["datos_enlace"] else "",
               P(a["nota"], cls=(TextPresets.muted_sm, "whitespace-pre-line")) if a["nota"] else "", cls="space-y-1")


def boton_declarar(p: dict, a: dict | None, **extra):
    return Button(UkIcon("pencil" if a else "lock-open", height=14, width=14), "Editar" if a else "Declarar",
                  cls=(ButtonT.default if not a else ButtonT.ghost, ButtonT.xs), type="button",
                  aria_label=f"{'Editar' if a else 'Declarar'} el acceso abierto de {p['titulo']}",
                  hx_get=f"/productos/{p['id']}/acceso", hx_target=f"#{ID_MODAL}", **extra)


def fila_ficha(p: dict, editable: bool):
    """Para la ficha del producto: la declaración (o la invitación a hacerla) y el botón para quien edita."""
    a = aa.de_producto(p["id"])
    if not a and not (editable and aa.aplica(p)):
        return None
    return Div(detalle_acceso(a) or P("Aún no se declaró dónde se puede leer el texto ni si los datos están disponibles.",
                                      cls=TextPresets.muted_sm),
               boton_declarar(p, a) if editable and aa.aplica(p) else "", cls="space-y-2")
