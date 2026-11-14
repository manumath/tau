"""Rutas de Aseguramiento de la Calidad (PLAN §57).

`routers()` da los routers del paquete en el orden en que se registran (main.py, PLAN §62 ARQ-01): una pantalla nueva
se agrega a MODULOS. La importación es diferida para no crear ciclos al importar un módulo suelto del paquete.
"""
from importlib import import_module

MODULOS = ("anexo", "marco", "indicadores", "evidencias", "autoevaluacion", "mejora", "actividades_mejora", "importar_mejora", "ficha", "capacitacion", "convenios", "impacto", "informes", "publico", "cuerpo_academico", "calidad_datos", "seguimiento_estudiantil",)


def routers() -> list:
    return [import_module(f"{__name__}.{m}").rt for m in MODULOS]
