"""Roles con alcance y vigencia, y el punto único de decisión `puede()` (PLAN.md, sección 23).

- Un rol se asigna a una persona para una unidad, desde una fecha y, si corresponde, hasta otra.
  Solo Administración del sistema asigna roles, a pedido de las direcciones. Un rol que termina no
  se borra: se le pone fecha de término.
- `puede(usuario, accion, unidad)`: ¿alguno de sus roles vigentes permite la acción en esa unidad?
  Los roles de toda la universidad (Administración del sistema, Comité de acreditación) cubren
  todas las unidades; los demás, solo la suya. Aunque el IIMAT está dentro de la CMAT en la
  jerarquía, la Dirección de Carrera no decide sobre el Instituto ni al revés.
- Los roles derivados (investigador, docente, responsable de un proyecto) no se asignan: se
  deducen de los datos, como antes.

Las rutas /admin se autorizan con REGLAS_ADMIN (app/comun/auth.py); el resto, con `puede()` en cada
ruta o regla de negocio. No hay otra marca de administración.
"""
from datetime import date, timedelta

from app.comun import unidades
from app.comun.db import HOY, get_db

# rol → (nombre, siglas de las unidades en que se puede asignar)
ROLES = {
    "administracion_sistema": ("Administración del sistema", ("UMSA",)),
    "direccion_instituto": ("Dirección del Instituto", ("IIMAT",)),
    "direccion_carrera": ("Dirección de Carrera", ("CMAT",)),
    "coordinacion_academica": ("Coordinación académica", ("CMAT",)),
    "comite_acreditacion": ("Comité de acreditación", ("UMSA",)),
    "gestion_datos": ("Gestión de datos", ("IIMAT", "CMAT")),
}
# Roles que cubren todas las unidades (se asignan en la UMSA); el resto vale solo en su unidad.
ROLES_DE_TODA_LA_UNIVERSIDAD = ("administracion_sistema", "comite_acreditacion")
DESCRIPCIONES = {
    "administracion_sistema": "Cuentas y roles, auditoría y configuración. No decide sobre contenido académico.",
    "direccion_instituto": "Propuestas y convocatoria, catálogos de revistas y líneas, vínculos del IIMAT, "
                           "memoria y anexo de I+D+i.",
    "direccion_carrera": "Plan de estudios, asignación docente y programas, vínculos e informes de la Carrera.",
    "coordinacion_academica": "Prepara asignaciones y revisa programas, sin aprobarlos.",
    "comite_acreditacion": "Ve todos los informes, anexos y exportaciones; no modifica nada.",
    "gestion_datos": "Carga vínculos de RR. HH., estudiantes e importaciones de su unidad.",
}

# acción → roles que la permiten. Las acciones con unidad se consultan con ella (p. ej., vínculos
# de la Carrera: puede(u, "gestionar_vinculos", CMAT)).
ACCIONES = {
    # Cuentas y sistema
    "asignar_roles": {"administracion_sistema"},
    "administrar_cuentas": {"administracion_sistema"},
    "ver_auditoria": {"administracion_sistema"},
    "ver_datos_personales": {"administracion_sistema"},
    "ver_usuarios": {"administracion_sistema", "direccion_instituto", "direccion_carrera", "gestion_datos"},
    # Datos de personas (por unidad)
    "gestionar_vinculos": {"direccion_carrera"},  # categoría y vínculo: solo la Dirección de Carrera
    "gestionar_estudiantes": {"direccion_instituto", "direccion_carrera", "gestion_datos"},
    "gestionar_personas_externas": {"direccion_instituto", "gestion_datos"},
    "gestionar_fichas": {"direccion_instituto", "direccion_carrera", "gestion_datos"},
    # Investigación (Instituto)
    "decidir_propuestas": {"direccion_instituto"},
    "gestionar_convocatoria": {"direccion_instituto"},
    "gestionar_catalogos": {"direccion_instituto"},
    "reasignar_responsable": {"direccion_instituto"},
    "actualizar_citas": {"direccion_instituto"},
    # Docencia (Carrera)
    "revisar_planes": {"direccion_carrera", "coordinacion_academica"},
    "gestionar_oferta": {"direccion_carrera", "coordinacion_academica"},
    "ver_carga": {"direccion_carrera", "coordinacion_academica", "direccion_instituto", "comite_acreditacion"},
    # Lectura
    "ver_todos_los_proyectos": {"direccion_instituto", "comite_acreditacion"},
    "ver_propuestas": {"direccion_instituto", "comite_acreditacion"},
    "ver_evidencias": {"direccion_instituto", "comite_acreditacion"},
    "ver_cv_ajeno": {"direccion_instituto", "direccion_carrera", "comite_acreditacion"},
    "ver_informes_institucionales": {"direccion_instituto", "direccion_carrera", "comite_acreditacion"},
}


def nombre(rol: str) -> str:
    return ROLES[rol][0]


# --- Consultas ---------------------------------------------------------------------------------------

def roles_vigentes(uid: int, fecha: str | None = None) -> list[dict]:
    f = fecha or date.today().isoformat()
    return get_db().q("""SELECT r.*, u.sigla FROM rol_asignado r JOIN unidad u ON u.id = r.unidad_id
                         WHERE r.usuario_id = ? AND r.desde <= ? AND (r.hasta IS NULL OR r.hasta >= ?)
                         ORDER BY r.rol""", [uid, f, f])


def historial(uid: int) -> list[dict]:
    return get_db().q("""SELECT r.*, u.sigla, a.nombres || ' ' || a.apellidos AS asignado_por_nombre
                         FROM rol_asignado r JOIN unidad u ON u.id = r.unidad_id
                         LEFT JOIN usuario a ON a.id = r.asignado_por
                         WHERE r.usuario_id = ? ORDER BY r.hasta IS NOT NULL, r.desde DESC, r.id DESC""", [uid])


def obtener(aid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM rol_asignado WHERE id = ?", [aid])
    return filas[0] if filas else None


def con_rol(rol: str, unidad: int | None = None) -> list[dict]:
    """Personas activas con el rol vigente (en la unidad o en una que la contiene)."""
    filas = get_db().q(
        f"""SELECT DISTINCT u.*, r.unidad_id AS rol_unidad FROM rol_asignado r JOIN usuario u ON u.id = r.usuario_id
            WHERE r.rol = ? AND u.activo = 1 AND r.desde <= {HOY} AND (r.hasta IS NULL OR r.hasta >= {HOY})
            ORDER BY u.apellidos, u.nombres""", [rol])
    if unidad is None:
        return filas
    return [f for f in filas if _cubre(rol, f["rol_unidad"], unidad)]


# --- Decisión ------------------------------------------------------------------------------------------

def _cubre(rol: str, unidad_del_rol: int, unidad: int) -> bool:
    return rol in ROLES_DE_TODA_LA_UNIVERSIDAD or unidad == unidad_del_rol


def tiene_rol(usuario: dict, rol: str) -> bool:
    return any(r["rol"] == rol for r in _roles(usuario))


def puede(usuario: dict | None, accion: str, unidad: int | None = None) -> bool:
    """¿Alguno de los roles vigentes del usuario permite la acción en la unidad (o en alguna, sin
    unidad)? Una acción desconocida es un error de programación."""
    if accion not in ACCIONES:
        raise ValueError(f"Acción desconocida: {accion}")
    if not usuario:
        return False
    for r in _roles(usuario):
        if r["rol"] in ACCIONES[accion] and (unidad is None or _cubre(r["rol"], r["unidad_id"], unidad)):
            return True
    return False


def _roles(usuario: dict) -> list[dict]:
    """Los roles cargados en la sesión (auth) o, si no vienen, los de la base."""
    if "roles" not in usuario:
        usuario["roles"] = roles_vigentes(usuario["id"])
    return usuario["roles"]


# --- Asignación ------------------------------------------------------------------------------------------

def _fecha(valor) -> str | None:
    return date.fromisoformat(str(valor)).isoformat() if valor else None


def asignar(uid: int, rol: str, unidad_id: int, desde=None, hasta=None, nota: str | None = None,
            asignado_por: int | None = None) -> list[str]:
    if rol not in ROLES:
        return ["Rol no válido."]
    permitidas = [unidades.id_de(s) for s in ROLES[rol][1]]
    if unidad_id not in permitidas:
        return [f"{nombre(rol)} se asigna en: {', '.join(ROLES[rol][1])}."]
    try:
        d, h = _fecha(desde) or date.today().isoformat(), _fecha(hasta)
    except ValueError:
        return ["Fechas no válidas."]
    if h and h < d:
        return ["La fecha de término no puede ser anterior a la de inicio."]
    otros = get_db().q("""SELECT 1 FROM rol_asignado WHERE usuario_id = ? AND rol = ? AND unidad_id = ?
                          AND desde <= ? AND (hasta IS NULL OR hasta >= ?)""", [uid, rol, unidad_id, h or "9999-12-31", d])
    if otros:
        return ["Ya tiene ese rol en esa unidad durante parte de ese periodo."]
    get_db().t.rol_asignado.insert(usuario_id=uid, rol=rol, unidad_id=unidad_id, desde=d, hasta=h,
                                   nota=(nota or "").strip() or None, asignado_por=asignado_por)
    return []


def terminar(aid: int, fecha=None) -> list[str]:
    """Pone el último día de una asignación. Sin fecha, el rol deja de regir hoy: último día, ayer;
    si empezó hoy o aún no empieza, la asignación se anula (la auditoría conserva ambos pasos).
    No deja el sistema sin Administración del sistema."""
    a = obtener(aid)
    if not a:
        return ["Asignación no encontrada."]
    try:
        f = _fecha(fecha) or (date.today() - timedelta(days=1)).isoformat()
    except ValueError:
        return ["Fecha no válida."]
    anular = fecha is None and f < a["desde"]
    if f < a["desde"] and not anular:
        return ["La fecha de término no puede ser anterior al inicio."]
    if a["rol"] == "administracion_sistema":
        quedan = [x for x in con_rol("administracion_sistema") if x["id"] != a["usuario_id"]]
        if not quedan:
            return ["Es la única persona con Administración del sistema: asígnela a otra antes de terminarla."]
    if anular:
        get_db().execute("DELETE FROM rol_asignado WHERE id = ?", [aid])
    else:
        get_db().execute("UPDATE rol_asignado SET hasta = ? WHERE id = ?", [f, aid])
    return []
