"""Lo que el módulo de egresados aporta al menú (PLAN §73, etapa 2)."""
from app.comun import permisos
from app.comun.menu import item
from app.egresados import egresados


def menu(auth):
    if not permisos.puede(auth, "ver_seguimiento_estudiantil"):
        return []
    return [("Estudiantes", 40, item("egresados", "Egresados", "/docencia/egresados", "graduation-cap")),
            ("Estudiantes", 50, item("empleadores", "Empleadores", "/docencia/empleadores", "building-2"))]


MANTENIMIENTO = [lambda: egresados.mantenimiento()]    # invitaciones del seguimiento de egresados (PLAN §73, etapa 3)
