"""Módulos que declara `app/informes` (PLAN §73)."""
from app.comun.modulos import Modulo
from app.informes import aportes

MODULOS = (
    Modulo(
        "informes", "Informes de investigación",
        "Memoria anual, informe de I+D+i, currículum, listados y tablero de calidad de datos.",
        area="Investigación", requiere=("investigacion",), rutas=("app.informes.rutas",),
        acciones=("ver_cv_ajeno", "ver_calidad_datos", "avisar_calidad"),
        aportes={"menu": aportes.menu_informes, "inicio": aportes.inicio_informes, "cifras": aportes.cifras_informes,
                 "mantenimiento": aportes.MANTENIMIENTO}),
)
