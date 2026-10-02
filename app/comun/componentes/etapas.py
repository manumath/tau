"""Indicador de etapas de un trámite (por ejemplo, una propuesta institucional): en qué paso va,
cuáles se cumplieron y cuáles faltan. Lista ordenada con Tailwind, sin JavaScript; se imprime igual.

Cada paso es un dict: `titulo`, `estado` y, opcional, `detalle` (p. ej., la fecha). Estados:
- `hecho`: cumplido; `actual`: en curso o esperando; `pendiente`: aún no llega;
- `alerta`: requiere una acción (p. ej., condiciones por atender); `error`: terminó mal (rechazo);
- `omitido`: ya no ocurrirá (p. ej., el proyecto de una propuesta rechazada).
"""
from fasthtml.common import Div, Li, Ol, Span
from monsterui.all import UkIcon

_CIRCULO = {
    "hecho": "bg-primary text-primary-foreground border-primary",
    "actual": "bg-background text-primary border-primary ring-4 ring-primary/15",
    "pendiente": "bg-background text-muted-foreground border-border",
    "alerta": "bg-amber-500 text-white border-amber-500",
    "error": "bg-red-600 text-white border-red-600",
    "omitido": "bg-background text-muted-foreground border-dashed border-border",
}
_ICONO = {"hecho": "check", "alerta": "circle-alert", "error": "x", "omitido": "minus"}
_LEIDO = {"hecho": "cumplida", "actual": "en curso", "pendiente": "pendiente", "alerta": "requiere acción",
          "error": "no se cumplió", "omitido": "no ocurrirá"}
_APAGADOS = ("pendiente", "omitido")   # títulos en gris
# Tramo que une un paso con el siguiente: lleno si el paso ya se cumplió.
_TRAMO = {"hecho": "bg-primary"}


def etapas(pasos: list[dict], compacto: bool = False, etiqueta: str = "Etapas"):
    tam, icono = ("h-5 w-5 text-[10px]", 11) if compacto else ("h-8 w-8 text-sm", 16)
    items = []
    for i, p in enumerate(pasos):
        estado = p["estado"]
        marca = UkIcon(_ICONO[estado], height=icono, width=icono) if estado in _ICONO else Span(str(i + 1))
        tramo = Div(cls="absolute top-1/2 left-1/2 -z-0 h-0.5 w-full -translate-y-1/2 "
                        + _TRAMO.get(estado, "bg-border")) if i < len(pasos) - 1 else ""
        texto = "" if compacto else Div(
            Div(p["titulo"], cls="text-sm font-medium leading-tight "
                                 + ("text-muted-foreground" if estado in _APAGADOS else "")),
            Div(p["detalle"], cls="text-xs text-muted-foreground leading-tight mt-0.5") if p.get("detalle") else "",
            cls="mt-2 text-center px-1")
        items.append(Li(
            Div(tramo, Div(marca, cls=f"relative z-10 flex {tam} items-center justify-center rounded-full border-2 "
                                      f"font-semibold {_CIRCULO[estado]}"),
                cls="relative flex justify-center"),
            texto,
            Span(f"{p['titulo']}: {_LEIDO[estado]}" + (f" ({p['detalle']})" if p.get("detalle") else ""),
                 cls="sr-only"),
            title=None if not compacto else f"{p['titulo']}" + (f" · {p['detalle']}" if p.get("detalle") else ""),
            aria_current="step" if estado in ("actual", "alerta") else None,
            cls="relative flex-1 min-w-0"))
    return Ol(*items, aria_label=etiqueta, cls="flex items-start " + ("w-40" if compacto else "w-full"))
