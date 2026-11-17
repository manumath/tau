"""Menú de navegación (PLAN.md §53): qué secciones ve cada persona, agrupadas como en el menú lateral.

Cada módulo **aporta** sus ítems (`app/<paquete>/aportes.py`, declarados en su `modulo.py`; PLAN §73) con el grupo y el
orden en que van; aquí solo se juntan los de los módulos activos y se ordenan. Por eso este archivo no importa de ningún
paquete. `main.py` se lo entrega al layout (`layout.MENU = navegacion.menu`). Cada ítem respeta el mismo permiso que la
pantalla a la que lleva; el servidor vuelve a comprobarlo en la ruta.
"""
from app.comun import modulos

# Orden de los grupos; uno que no esté aquí va al final.
GRUPOS = (None, "Investigación", "Docencia", "Estudiantes", "Servicios", "Calidad", "Administración")
GRUPOS_ESTUDIANTE = (None, "Mi carrera", "Servicios")
# Las tres secciones de la barra de abajo en el teléfono (además de Inicio y «Más»): las primeras que la persona ve.
PRIORIDAD_MOVIL_ESTUDIANTE = ("estudiante", "plan", "calendario", "oportunidades", "comunicados", "grado")
PRIORIDAD_MOVIL = ("productos", "proyectos", "mia", "investigadores", "informes", "usuarios", "cohortes")


def _armar(punto: str, grupos: tuple, auth: dict) -> list[tuple[str | None, list[dict]]]:
    """Junta los aportes de los módulos activos: por grupo y, dentro de cada uno, por el orden que cada ítem declara.
    Sin los ítems que darían 404 (una pantalla que necesita otro módulo apagado) ni los grupos vacíos."""
    aportados = [x for aporte in modulos.aportes(punto) for x in aporte(auth)]
    aportados = [(g, orden, i) for g, orden, i in aportados if modulos.direccion_activa(i["href"])]
    vistos = set()    # un mismo ítem puede llegar de dos módulos («Mis pendientes»): se muestra una vez
    aportados = [x for x in aportados if (x[0], x[2]["clave"]) not in vistos and not vistos.add((x[0], x[2]["clave"]))]
    titulos = [*grupos, *sorted({g for g, _, _ in aportados if g not in grupos})]
    menu = [(t, [i for g, _, i in sorted((x for x in aportados if x[0] == t), key=lambda x: x[1])]) for t in titulos]
    return [(t, items) for t, items in menu if items]


def menu(auth: dict) -> list[tuple[str | None, list[dict]]]:
    """[(título del grupo o None, ítems)], solo los grupos con algo visible."""
    if auth.get("solo_estudiante"):
        return _armar("menu_estudiante", GRUPOS_ESTUDIANTE, auth)
    return _armar("menu", GRUPOS, auth)


def movil(auth: dict) -> list[dict]:
    """Barra de abajo en el teléfono: Inicio y las tres primeras secciones según PRIORIDAD_MOVIL (sin
    insignias: sus ids ya están en el menú lateral)."""
    todos = {i["clave"]: i for _, items in menu(auth) for i in items}
    if auth.get("solo_estudiante"):      # la barra de abajo: cuatro secciones (las más usadas que tenga) y «Más»
        return [{**todos[c], "insignia": None} for c in PRIORIDAD_MOVIL_ESTUDIANTE if c in todos][:4]
    elegidos = [todos[c] for c in PRIORIDAD_MOVIL if c in todos][:3]
    return [todos["inicio"], *[{**i, "insignia": None} for i in elegidos]]
