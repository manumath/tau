"""Rutas de los informes de investigación: informe de I+D+i, índice de informes con CV y memoria, y calidad de datos.
«anexo» va antes que «informes»: sus direcciones anteriores (/informes/acreditacion…) redirigen.

`routers()` da los routers del paquete en el orden en que se registran (main.py, PLAN §62 ARQ-01): una pantalla nueva
se agrega a MODULOS. La importación es diferida para no crear ciclos al importar un módulo suelto del paquete.
"""
from importlib import import_module

MODULOS = ("anexo", "informes", "calidad_datos",)


def routers() -> list:
    return [import_module(f"{__name__}.{m}").rt for m in MODULOS]
