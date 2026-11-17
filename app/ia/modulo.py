"""Módulos que declara `app/ia` (PLAN §73)."""
from app.comun.modulos import Modulo
from app.ia import aportes

MODULOS = (
    Modulo(
        "ia", "IA con criterio humano",
        "Borradores generados por un modelo, que solo surten efecto cuando una persona los aprueba.",
        area="Transversal", rutas=("app.ia.rutas",), acciones=("gestionar_ia", "ver_uso_ia"),
        aportes={"menu": aportes.menu}),
)
