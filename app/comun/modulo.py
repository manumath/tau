"""Módulos que declara `app/comun` (PLAN §73): la plataforma, que no se apaga, y los comentarios del piloto."""
from app.comun import aportes
from app.comun.modulos import PLATAFORMA, Modulo

MODULOS = (
    Modulo(
        PLATAFORMA, "Plataforma",
        "Cuentas e ingreso, roles, unidades, vínculos, personas, avisos, auditoría, privacidad y adjuntos.",
        rutas=("app.comun", "app.inicio", "app.busqueda", "main"),   # `main` es /salud
        acciones=("asignar_roles", "administrar_cuentas", "ver_auditoria", "ver_datos_personales", "ver_usuarios",
                  "gestionar_vinculos", "gestionar_estudiantes", "gestionar_personas_externas", "gestionar_fichas",
                  "gestionar_modulos", "configurar_unidades", "ver_informes_institucionales"),
        aportes={"menu": aportes.menu, "menu_estudiante": aportes.menu_estudiante, "busqueda": aportes.BUSQUEDA,
                 "inicio": aportes.inicio}),
    Modulo(
        "piloto", "Comentarios del piloto",
        "«Comentar esta pantalla» para los usuarios y el tablero de comentarios y adopción por rol.",
        area="Transversal", rutas=("app.comun.rutas.piloto",), aportes={"menu": aportes.menu_piloto}),
)
