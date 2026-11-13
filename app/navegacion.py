"""Menú de navegación (PLAN.md §53): qué secciones ve cada persona, agrupadas como en el menú lateral.

Vive aquí, y no en app/comun/componentes/layout.py, porque necesita saber qué ve cada rol en Docencia y en
Estudiantes (app/academico), y `comun` no importa de los otros paquetes: main.py se lo entrega al layout
(`layout.MENU = navegacion.menu`). Cada ítem respeta el mismo permiso que la pantalla a la que lleva; el
servidor vuelve a comprobarlo en la ruta.
"""
from fasthtml.common import Span

from app.academico.componentes import PESTANAS, visible
from app.calidad import impacto, mejora
from app.comun import permisos
from app.comun.db import get_db
from app.servicios import oportunidades, recursos, temas

DOCENCIA = ("mia", "pendientes", "calendario", "programas", "preferencias", "preparacion", "planes", "oferta", "preferencias_todas", "carga", "gestiones")
ESTUDIANTES = ("cohortes", "encuestas", "tutoria", "egresados", "empleadores")
ICONOS = {"mia": "presentation", "pendientes": "list-checks", "calendario": "calendar-days", "programas": "notebook-text", "preferencias": "list-filter", "preferencias_todas": "users-round", "preparacion": "calendar-check", "planes": "book-marked", "oferta": "layout-list",
          "carga": "clock", "gestiones": "calendar-range", "cohortes": "users-round", "encuestas": "clipboard-list",
          "tutoria": "message-circle", "egresados": "graduation-cap",
          "empleadores": "building-2"}
# Las tres secciones de la barra de abajo en el teléfono (además de Inicio y «Más»): las primeras que la persona ve.
PRIORIDAD_MOVIL_ESTUDIANTE = ("estudiante", "plan", "calendario", "oportunidades", "comunicados", "grado")
PRIORIDAD_MOVIL = ("productos", "proyectos", "mia", "investigadores", "informes", "usuarios", "cohortes")


def _item(clave, texto, href, icono, insignia=None):
    return {"clave": clave, "texto": texto, "href": href, "icono": icono, "insignia": insignia}


def _contador(id_, url):
    """Insignia que se carga aparte y se refresca sola (para no consultar la base en cada página)."""
    return Span(id=id_, cls="hidden", hx_get=url, hx_trigger="load", hx_swap="outerHTML")


def _academico(claves, auth):
    return [_item(c, t, u, ICONOS[c]) for c, t, u, cond in PESTANAS if c in claves and visible(cond, auth)]


def _miembro_auxiliatura(uid: int) -> bool:
    return bool(get_db().q("""SELECT 1 FROM tribunal_auxiliatura t JOIN item_auxiliatura i ON i.id = t.item_id
                              JOIN convocatoria_auxiliatura c ON c.id = i.convocatoria_id
                              WHERE t.usuario_id = ? AND c.estado = 'publicada' LIMIT 1""", [uid]))


def _en_grado(uid: int) -> bool:
    """¿Es tutor o tribunal de algún trámite de grado?"""
    return bool(get_db().q("""SELECT 1 FROM tramite_grado WHERE tutor_id = ? AND estado <> 'borrador'
                              UNION SELECT 1 FROM tribunal_grado WHERE usuario_id = ? LIMIT 1""", [uid, uid]))


def menu(auth: dict) -> list[tuple[str | None, list[dict]]]:
    """[(título del grupo o None, ítems)], solo los grupos con algo visible."""
    if auth.get("solo_estudiante"):
        # El portal del estudiante, en grupos (PLAN §67): cada servicio nuevo se agrega a su grupo.
        return [(None, [_item("estudiante", "Mi seguimiento", "/estudiante", "graduation-cap"),
                        _item("avisos", "Avisos", "/avisos", "bell")]),
                ("Mi carrera", [_item("plan", "Mi plan de estudios", "/estudiante/plan", "book-marked"),
                                _item("calendario", "Calendario", "/estudiante/calendario", "calendar-days"),
                                _item("tutoria", "Mi tutoría", "/estudiante/tutoria", "message-circle-heart"),
                                _item("apoyo", "Apoyo", "/estudiante/apoyo", "life-buoy"),
                                _item("biblioteca", "Biblioteca", "/estudiante/biblioteca", "library-big"),
                                _item("orientacion", "Orientación", "/estudiante/orientacion", "compass"),
                                _item("buzon", "Buzón", "/estudiante/buzon", "mail")]),
                ("Servicios", [_item("comunicados", "Comunicados", "/estudiante/comunicados", "megaphone"),
                               _item("auxiliaturas", "Auxiliaturas", "/estudiante/auxiliaturas", "badge-check"),
                               _item("oportunidades", "Oportunidades", "/estudiante/oportunidades", "briefcase"),
                               _item("temas", "Temas de grado", "/estudiante/temas", "lightbulb"),
                               _item("encuestas", "Encuestas", "/estudiante/encuestas", "clipboard-list"),
                               _item("grado", "Grado", "/estudiante/grado", "scroll")])]
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
    if auth.get("es_tutor") or puede("gestionar_apoyo"):
        estudiantes.append(_item("apoyo-estudiantil", "Apoyo estudiantil", "/apoyo", "life-buoy"))
    calidad = []
    if auth["es_investigador"] or puede("ver_informes_institucionales") or puede("ver_cv_ajeno"):
        calidad.append(_item("informes", "Informes", "/informes", "file-text"))
    if puede("ver_marco_calidad"):
        calidad.append(_item("marco", "Marco de calidad", "/calidad/marco", "layers"))
        calidad.append(_item("indicadores", "Indicadores", "/calidad/indicadores", "gauge"))
    if puede("ver_evidencias_calidad"):
        calidad.append(_item("evidencias", "Evidencias", "/calidad/evidencias", "folder-open"))
    if puede("ver_autoevaluacion"):
        calidad.append(_item("autoevaluacion", "Autoevaluación", "/calidad/autoevaluaciones", "clipboard-check"))
    if puede("ver_marco_calidad"):
        calidad.append(_item("ficha", "Ficha estadística", "/calidad/ficha", "table-2"))
        calidad.append(_item("capacitacion", "Capacitación", "/calidad/capacitacion", "school"))
        calidad.append(_item("convenios", "Convenios", "/calidad/convenios", "handshake"))
    if puede("ver_marco_calidad") or impacto.tiene_proyectos(auth["id"]):
        calidad.append(_item("impacto", "Impacto social", "/calidad/impacto", "heart-handshake"))
    if puede("ver_plan_mejora") or mejora.tiene_acciones(auth["id"]):
        calidad.append(_item("mejora", "Plan de mejora", "/calidad/mejora", "list-todo"))
    if puede("ver_calidad_datos"):
        calidad.append(_item("calidad", "Calidad de datos", "/informes/calidad", "list-checks"))
    servicios = [_item("comunicados", "Comunicados y eventos", "/servicios/comunicados", "megaphone")]
    if puede("gestionar_auxiliaturas") or puede("gestionar_auxiliaturas_investigacion") or _miembro_auxiliatura(auth["id"]):
        servicios.append(_item("auxiliaturas", "Auxiliaturas", "/servicios/auxiliaturas", "badge-check"))
    if puede("gestionar_buzon"):
        servicios.append(_item("buzon", "Buzón de consultas", "/servicios/buzon", "inbox"))
    if recursos.puede_publicar(auth):
        servicios.append(_item("recursos", "Biblioteca y recursos", "/servicios/recursos", "library-big"))
    if temas.puede_publicar(auth):
        servicios.append(_item("temas", "Temas de grado", "/servicios/temas", "lightbulb"))
    if oportunidades.puede_publicar(auth):
        servicios.append(_item("oportunidades", "Oportunidades", "/servicios/oportunidades", "handshake"))
    if puede("gestionar_grado") or _en_grado(auth["id"]):
        servicios.append(_item("grado", "Proyectos de grado", "/servicios/grado", "scroll"))
    administracion = []
    if puede("ver_usuarios"):
        administracion.append(_item("usuarios", "Usuarios", "/admin/usuarios", "users"))
    if puede("ver_auditoria"):
        administracion.append(_item("auditoria", "Auditoría", "/admin/auditoria", "scroll-text"))
    if puede("gestionar_catalogos"):
        administracion += [_item("revistas", "Catálogo de revistas", "/admin/revistas", "library"),
                           _item("lineas", "Líneas de investigación", "/admin/lineas", "route"),
                           _item("catalogos", "Tipos e índices", "/admin/catalogos", "tags")]
    if puede("gestionar_ia") or puede("ver_uso_ia"):          # PLAN §59; la página /ia está en el menú del usuario
        administracion.append(_item("ia", "IA: administración y piloto",
                                    "/ia/admin" if puede("gestionar_ia") else "/ia/usos", "sparkles"))
    grupos = [(None, [_item("inicio", "Inicio", "/", "home")]), ("Investigación", investigacion),
              ("Docencia", _academico(DOCENCIA, auth)), ("Estudiantes", estudiantes), ("Servicios", servicios),
              ("Calidad", calidad), ("Administración", administracion)]
    return [(t, items) for t, items in grupos if items]


def movil(auth: dict) -> list[dict]:
    """Barra de abajo en el teléfono: Inicio y las tres primeras secciones según PRIORIDAD_MOVIL (sin
    insignias: sus ids ya están en el menú lateral)."""
    todos = {i["clave"]: i for _, items in menu(auth) for i in items}
    if auth.get("solo_estudiante"):      # la barra de abajo: cuatro secciones (las más usadas que tenga) y «Más»
        return [{**todos[c], "insignia": None} for c in PRIORIDAD_MOVIL_ESTUDIANTE if c in todos][:4]
    elegidos = [todos[c] for c in PRIORIDAD_MOVIL if c in todos][:3]
    return [todos["inicio"], *[{**i, "insignia": None} for i in elegidos]]
