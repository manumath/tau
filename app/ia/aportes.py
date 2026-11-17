"""Lo que el módulo de IA aporta al menú (PLAN §73, etapa 2; la página /ia está en el menú del usuario, PLAN §59)."""
from app.comun import permisos
from app.comun.menu import item


def menu(auth):
    gestiona = permisos.puede(auth, "gestionar_ia")
    if not (gestiona or permisos.puede(auth, "ver_uso_ia")):
        return []
    return [("Administración", 80, item("ia", "IA: administración y piloto", "/ia/admin" if gestiona else "/ia/usos",
                                        "sparkles"))]
