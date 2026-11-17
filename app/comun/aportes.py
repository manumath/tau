"""Lo que la plataforma y el módulo del piloto aportan al menú y a la búsqueda (PLAN §73, etapa 2)."""
from app.comun import modulos, permisos
from app.comun.db import get_db, patron_busqueda
from app.comun.menu import item


def menu(auth):
    puede = lambda accion: permisos.puede(auth, accion)  # noqa: E731
    items = [(None, 0, item("inicio", "Inicio", "/", "home"))]
    if puede("ver_usuarios"):
        items.append(("Administración", 10, item("usuarios", "Usuarios", "/admin/usuarios", "users")))
    if puede("ver_auditoria"):
        items.append(("Administración", 20, item("auditoria", "Auditoría", "/admin/auditoria", "scroll-text")))
    if puede("gestionar_modulos"):
        items.append(("Administración", 40, item("modulos", "Módulos", "/admin/modulos", "blocks")))
    if puede("configurar_unidades"):
        items.append(("Administración", 45, item("unidades", "Unidades", "/admin/unidades", "building")))
    return items


def inicio(auth):
    """«Primeros pasos» de una instalación nueva, para la Administración del sistema (PLAN §73, etapa 5): mientras casi
    no haya módulos activos o exista una sola cuenta, el inicio dice por dónde empezar."""
    if not permisos.puede(auth, "gestionar_modulos"):
        return []
    todos = modulos.todos()
    activos = sum(modulos.activo(m.clave) for m in todos)
    cuentas = get_db().q("SELECT COUNT(*) n FROM usuario")[0]["n"]
    if activos > 1 and cuentas > 1:
        return []
    pasos = [(10, activos <= 1, "Elija los módulos que usará su unidad", "/admin/modulos",
              f"Hoy hay {activos} de {len(todos)} activos. Puede cambiarlos cuando quiera: apagar uno no borra sus datos."),
             (20, cuentas <= 1, "Cree las cuentas de su unidad", "/admin/usuarios",
              "Una por una o con un archivo CSV; cada persona define su contraseña con el enlace de invitación."),
             (30, not get_db().q("SELECT 1 FROM rol_asignado WHERE rol = 'direccion_carrera' LIMIT 1"),
              "Asigne el rol de Dirección de Carrera", "/admin/usuarios",
              "Es quien define la categoría, el vínculo y la carga horaria de cada persona.")]
    return [("instalacion", orden, {"texto": texto, "href": href, "tono": "info", "detalle": detalle})
            for orden, falta, texto, href, detalle in pasos if falta]


def menu_estudiante(auth):
    return [(None, 10, item("avisos", "Avisos", "/avisos", "bell"))]


def menu_piloto(auth):
    if not permisos.puede(auth, "ver_auditoria"):
        return []
    return [("Administración", 30, item("piloto", "Piloto y adopción", "/admin/piloto", "message-square-text"))]


def _cuentas(q, auth, limite):
    """Cuentas para quien ve los usuarios. Con Investigación activa, las de investigadores ya salen en «Personas»."""
    if not permisos.puede(auth, "ver_usuarios"):
        return []
    sin_investigadores = ("NOT EXISTS (SELECT 1 FROM investigador i WHERE i.usuario_id = u.id) AND"
                          if modulos.activo("investigacion") else "")
    filas = get_db().q(
        f"""SELECT u.nombres, u.apellidos, u.email FROM usuario u
            WHERE {sin_investigadores} (sin_tildes(u.nombres || ' ' || u.apellidos) LIKE :p OR u.email LIKE :p)
            ORDER BY u.apellidos LIMIT :l""", {"p": patron_busqueda(q), "l": limite})
    return [{"texto": f"{f['nombres']} {f['apellidos']}", "href": f"/admin/usuarios?q={f['email']}",
             "detalle": f["email"]} for f in filas]


BUSQUEDA = [(20, "Cuentas", "user-cog", _cuentas)]
