"""Módulos que declara `app/calidad` (PLAN §73): el Aseguramiento de la Calidad y su plan de mejora."""
from app.calidad import aportes
from app.comun.modulos import Modulo

_R = "app.calidad.rutas."

MODULOS = (
    Modulo(
        "calidad", "Aseguramiento de la calidad",
        "Marco de calidad, indicadores, evidencias, autoevaluación, ficha estadística, capacitación, convenios e impacto.",
        area="Calidad",
        rutas=tuple(_R + m for m in ("marco", "indicadores", "evidencias", "autoevaluacion", "ficha", "capacitacion",
                                     "convenios", "impacto", "publico")),
        acciones=("gestionar_marco_calidad", "registrar_indicadores_calidad", "ver_marco_calidad",
                  "registrar_evidencias_calidad", "ver_evidencias_calidad", "gestionar_autoevaluacion",
                  "registrar_juicios_calidad", "ver_autoevaluacion", "registrar_capacitacion", "registrar_convenios",
                  "registrar_impacto_proyectos"),
        aportes={"menu": aportes.menu_calidad, "mantenimiento": aportes.MANTENIMIENTO_CALIDAD}),
    Modulo(
        "mejora", "Plan de mejora",
        "Acciones y actividades del plan de mejora, avances con evidencia, cortes trimestrales y reprogramaciones.",
        area="Calidad", requiere=("calidad",),
        rutas=tuple(_R + m for m in ("mejora", "actividades_mejora", "importar_mejora", "cortes_mejora")),
        acciones=("gestionar_plan_mejora", "ver_plan_mejora"),
        aportes={"menu": aportes.menu_mejora, "inicio": aportes.inicio_mejora, "eventos": aportes.eventos_mejora,
                 "bloque_pendientes": aportes.bloque_mejora, "mantenimiento": aportes.MANTENIMIENTO_MEJORA}),
)
