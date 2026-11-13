"""Rutas del seguimiento estudiantil (PLAN §49).

`routers()` da los routers del paquete en el orden en que se registran (main.py, PLAN §62 ARQ-01): una pantalla nueva
se agrega a MODULOS. La importación es diferida para no crear ciclos al importar un módulo suelto del paquete.
"""
from importlib import import_module

MODULOS = ("cohortes", "actividades", "estudiante", "mi_plan", "encuestas", "responder", "tutoria",)


def routers() -> list:
    return [import_module(f"{__name__}.{m}").rt for m in MODULOS]
