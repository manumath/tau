"""Menú de navegación (PLAN.md §53): qué secciones ve cada persona, agrupadas como en el menú lateral.

Vive aquí, y no en app/comun/componentes/layout.py, porque necesita saber qué ve cada rol en Docencia y en
Estudiantes (app/academico), y `comun` no importa de los otros paquetes: main.py se lo entrega al layout
(`layout.MENU = navegacion.menu`). Cada ítem respeta el mismo permiso que la pantalla a la que lleva; el
servidor vuelve a comprobarlo en la ruta.
"""
from fasthtml.common import Span

from app.academico.componentes import PESTANAS, visible
from app.comun import permisos

DOCENCIA = ("mia", "preparacion", "planes", "oferta", "carga", "gestiones")
ESTUDIANTES = ("cohortes", "encuestas", "tutoria", "egresados")
ICONOS = {"mia": "presentation", "preparacion": "calendar-check", "planes": "book-marked", "oferta": "layout-list",
          "carga": "clock", "gestiones": "calendar-range", "cohortes": "users-round", "encuestas": "clipboard-list",
          "tutoria": "message-circle", "egresados": "graduation-cap"}
# Las tres secciones de la barra de abajo en el teléfono (además de Inicio y «Más»): las primeras que la persona ve.
PRIORIDAD_MOVIL = ("productos", "proyectos", "mia", "investigadores", "informes", "usuarios", "cohortes")


def _item(clave, texto, href, icono, insignia=None):
    return {"clave": clave, "texto": texto, "href": href, "icono": icono, "insignia": insignia}


def _contador(id_, url):
    """Insignia que se carga aparte y se refresca sola (para no consultar la base en cada página)."""
    return Span(id=id_, cls="hidden", hx_get=url, hx_trigger="load", hx_swap="outerHTML")


def _academico(claves, auth):
    return [_item(c, t, u, ICONOS[c]) for c, t, u, cond in PESTANAS if c in claves and visible(cond, auth)]


def menu(auth: dict) -> list[tuple[str | None, list[dict]]]:
    """[(título del grupo o None, ítems)], solo los grupos con algo visible."""
    if auth.get("solo_estudiante"):
        return [(None, [_item("estudiante", "Mi seguimiento", "/estudiante", "graduation-cap"),
                        _item("avisos", "Avisos", "/avisos", "bell")])]
    puede = lambda accion: permisos.puede(auth, accion)  # noqa: E731
    investigacion = []
    if auth["es_investigador"]:
        investigacion += [_item("actividades", "Actividades", "/actividades", "calendar-days"),
                          _item("productos", "Productos", "/productos", "book-open")]
    if auth["es_investigador"] or puede("ver_todos_los_proyectos"):
        investigacion.append(_item("proyectos", "Proyectos", "/proyectos", "folder-kanban",
                                   _contador("badge-pendientes", "/proyectos/pendientes/contador")))
    investigacion.append(_item("investigadores", "Investigadores", "/investigadores", "book-user"))
    if puede("decidir_propuestas"):
        investigacion.append(_item("propuestas", "Propuestas", "/admin/propuestas", "landmark",
                                   _contador("badge-propuestas", "/admin/propuestas/contador")))
    estudiantes = _academico(ESTUDIANTES, auth)
    if auth.get("es_tutor"):
        estudiantes.insert(0, _item("mis-tutorados", "Mis tutorados", "/tutoria", "message-circle-heart"))
    acreditacion = []
    if auth["es_investigador"] or puede("ver_informes_institucionales") or puede("ver_cv_ajeno"):
        acreditacion.append(_item("informes", "Informes", "/informes", "file-text"))
    if puede("ver_calidad_datos"):
        acreditacion.append(_item("calidad", "Calidad de datos", "/informes/calidad", "list-checks"))
    administracion = []
    if puede("ver_usuarios"):
        administracion.append(_item("usuarios", "Usuarios", "/admin/usuarios", "users"))
    if puede("ver_auditoria"):
        administracion.append(_item("auditoria", "Auditoría", "/admin/auditoria", "scroll-text"))
    if puede("gestionar_catalogos"):
        administracion += [_item("revistas", "Catálogo de revistas", "/admin/revistas", "library"),
                           _item("lineas", "Líneas de investigación", "/admin/lineas", "route"),
                           _item("catalogos", "Tipos e índices", "/admin/catalogos", "tags")]
    grupos = [(None, [_item("inicio", "Inicio", "/", "home")]), ("Investigación", investigacion),
              ("Docencia", _academico(DOCENCIA, auth)), ("Estudiantes", estudiantes),
              ("Acreditación", acreditacion), ("Administración", administracion)]
    return [(t, items) for t, items in grupos if items]


def movil(auth: dict) -> list[dict]:
    """Barra de abajo en el teléfono: Inicio y las tres primeras secciones según PRIORIDAD_MOVIL (sin
    insignias: sus ids ya están en el menú lateral)."""
    todos = {i["clave"]: i for _, items in menu(auth) for i in items}
    if auth.get("solo_estudiante"):
        return list(todos.values())
    elegidos = [todos[c] for c in PRIORIDAD_MOVIL if c in todos][:3]
    return [todos["inicio"], *[{**i, "insignia": None} for i in elegidos]]
