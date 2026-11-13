"""Rutas de la investigación. «bibtex» va antes que «productos»: /productos/bibtex coincidiría con
/productos/{pid}.

`routers()` da los routers del paquete en el orden en que se registran (main.py, PLAN §62 ARQ-01): una pantalla nueva
se agrega a MODULOS. La importación es diferida para no crear ciclos al importar un módulo suelto del paquete.
"""
from importlib import import_module

MODULOS = ("perfil", "bibtex", "investigadores", "mis_pendientes", "acceso_abierto", "coautores", "actividades", "productos", "personas", "adjuntos", "propuestas", "proyectos", "publico", "admin_revistas", "admin_lineas", "admin_catalogos",)


def routers() -> list:
    return [import_module(f"{__name__}.{m}").rt for m in MODULOS]
