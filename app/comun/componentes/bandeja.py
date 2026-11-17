"""Textos de los pendientes del inicio que arman los aportes de cada módulo (PLAN §73, etapa 2) y la fila de «Le toca a
usted» del portal del estudiante."""
from fasthtml.common import A, Div, Span
from monsterui.all import TextPresets, UkIcon


def le_toca(texto, href, detalle=None, icono="circle-alert"):
    """Una fila de «Le toca a usted»: qué hacer, con enlace."""
    return A(UkIcon(icono, height=16, width=16, cls="shrink-0 text-primary"),
             Div(Span(texto, cls="font-medium"), Div(detalle, cls=TextPresets.muted_sm) if detalle else ""),
             UkIcon("chevron-right", height=16, width=16, cls="ml-auto shrink-0 text-muted-foreground"),
             href=href, cls="flex items-center gap-3 rounded-md border border-border p-3 hover:bg-muted")



def plural(n, singular, plural=None):
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def nombres(filas, n=3):
    """«Ana Pérez, Luis Rojas y 4 más»."""
    lista = [f"{f['nombres']} {f['apellidos']}" for f in filas[:n]]
    return ", ".join(lista) + (f" y {len(filas) - n} más" if len(filas) > n else "")
