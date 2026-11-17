"""Módulos que declara `app/egresados` (PLAN §73)."""
from app.comun.modulos import Modulo
from app.egresados import aportes

MODULOS = (
    Modulo(
        "egresados", "Egresados y empleadores",
        "Titulación, seguimiento de egresados por hitos, directorio opcional y registro de empleadores.",
        area="Estudiantes", requiere=("estudiantes", "encuestas"), rutas=("app.egresados.rutas",),
        acciones=("gestionar_egresados",), aportes={"menu": aportes.menu, "mantenimiento": aportes.MANTENIMIENTO},
        privacidad=("directorio", "empleadores")),
)
