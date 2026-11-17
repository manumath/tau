"""Rutas de lo común: cuentas, estudiantes, auditoría, mis datos y avisos.

`routers()` da los routers del paquete en el orden en que se registran (main.py, PLAN §62 ARQ-01): una pantalla nueva
se agrega a MODULOS. La importación es diferida para no crear ciclos al importar un módulo suelto del paquete.
"""
from importlib import import_module

MODULOS = ("admin_usuarios", "estudiantes", "admin_auditoria", "modulos", "unidades", "privacidad", "fotos", "piloto", "mis_datos", "avisos", "agenda", "instalable",)


def routers() -> list:
    return [import_module(f"{__name__}.{m}").rt for m in MODULOS]
