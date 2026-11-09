"""Acceso a datos de cuentas de usuario."""
from datetime import timedelta

from app.comun import academicos, config, permisos, unidades, vinculos
from app.comun.db import AHORA, get_db, marca_tiempo, sin_tildes
from app.comun.seguridad import hash_password

_COLUMNAS = "u.*"


def por_id(uid: int) -> dict | None:
    filas = get_db().q(f"SELECT {_COLUMNAS} FROM usuario u WHERE u.id = ?", [uid])
    return filas[0] if filas else None


def por_email(email: str) -> dict | None:
    filas = get_db().q(f"SELECT {_COLUMNAS} FROM usuario u WHERE u.email = ?", [email.strip()])
    return filas[0] if filas else None


def listar(texto: str = "") -> list[dict]:
    patron = f"%{sin_tildes(texto.strip())}%"
    return get_db().q(
        f"""SELECT {_COLUMNAS}, (i.usuario_id IS NOT NULL) AS es_investigador,
                   {vinculos.sql_categoria_vigente('u')} AS categoria
           FROM usuario u LEFT JOIN investigador i ON i.usuario_id = u.id
           WHERE u.email LIKE :p OR sin_tildes(u.nombres || ' ' || u.apellidos) LIKE :p
                 OR sin_tildes(u.apellidos || ' ' || u.nombres) LIKE :p
           ORDER BY sin_tildes(u.apellidos), sin_tildes(u.nombres)""",
        {"p": patron})


def con_perfil(uid: int) -> dict | None:
    filas = get_db().q(
        f"""SELECT {_COLUMNAS}, (i.usuario_id IS NOT NULL) AS es_investigador,
                   {vinculos.sql_categoria_vigente('u')} AS categoria
           FROM usuario u LEFT JOIN investigador i ON i.usuario_id = u.id WHERE u.id = ?""", [uid])
    return filas[0] if filas else None


def crear(email: str, nombres: str, apellidos: str, password: str | None, *,
          es_admin=False, es_investigador=True, debe_cambiar_pass=True,
          categoria: str | None = None, fecha_ingreso: str | None = None,
          fecha_termino: str | None = None) -> dict:
    db = get_db()
    # Sin contraseña: persona registrada sin acceso al portal (ver app.comun.academicos).
    sin_acceso = password is None
    u = db.t.usuario.insert(email=email.strip().lower(), nombres=nombres.strip(),
                            apellidos=apellidos.strip(),
                            pass_hash=academicos.SIN_ACCESO if sin_acceso else hash_password(password),
                            debe_cambiar_pass=0 if sin_acceso else int(debe_cambiar_pass))
    if es_admin:
        # «Administración» al crear la cuenta = Administración del sistema + Dirección del Instituto
        # (otros roles se asignan después, en «Roles»).
        permisos.asignar(u["id"], "administracion_sistema", unidades.id_de("UMSA"))
        permisos.asignar(u["id"], "direccion_instituto", unidades.instituto())
    if es_investigador:
        db.t.investigador.insert(usuario_id=u["id"])
    if categoria:
        vinculos.agregar(u["id"], categoria, fecha_ingreso or None, fecha_termino or None)
    return u


def cambiar_password(uid: int, password: str, *, temporal: bool):
    """Cambia la contraseña y cierra todas las sesiones abiertas de la cuenta (la que hizo el cambio, si debe seguir,
    vuelve a fijar su versión con `version_sesion`)."""
    get_db().t.usuario.update(id=uid, pass_hash=hash_password(password),
                              debe_cambiar_pass=int(temporal))
    cerrar_sesiones(uid)


# --- Sesiones (PLAN §62) -------------------------------------------------------------------------------------------
# La sesión es una cookie firmada que guarda el id de la cuenta y su `sesion_version` al ingresar. Incrementar la
# versión invalida todas las copias de la cookie de esa cuenta, en cualquier equipo.

def version_sesion(uid: int) -> int:
    filas = get_db().q("SELECT sesion_version FROM usuario WHERE id = ?", [uid])
    return filas[0]["sesion_version"] if filas else 0


def cerrar_sesiones(uid: int):
    get_db().execute("UPDATE usuario SET sesion_version = sesion_version + 1 WHERE id = ?", [uid])


def set_activo(uid: int, activo: bool):
    get_db().t.usuario.update(id=uid, activo=int(activo))


def registrar_acceso(uid: int):
    get_db().execute(f"UPDATE usuario SET ultimo_acceso = {AHORA} WHERE id = ?", [uid])


# --- Límite de intentos de login ---------------------------------------------

def registrar_intento(email: str, ip: str | None, exito: bool):
    get_db().t.intento_login.insert(email=email.strip().lower(), ip=ip, exito=int(exito))


def bloqueado(email: str) -> bool:
    """True si hay demasiados fallos recientes desde el último ingreso exitoso."""
    fila = get_db().q(
        """SELECT COUNT(*) AS n FROM intento_login
           WHERE email = :e AND exito = 0 AND fecha >= :desde
             AND fecha > COALESCE((SELECT MAX(fecha) FROM intento_login
                                   WHERE email = :e AND exito = 1), '')""",
        {"e": email.strip().lower(), "desde": marca_tiempo(-timedelta(minutes=config.LOGIN_VENTANA_MIN))})[0]
    return fila["n"] >= config.LOGIN_MAX_FALLOS


def ip_bloqueada(ip: str | None) -> bool:
    """True si desde esa dirección hubo demasiados fallos recientes, con cualquier correo (frena el «password
    spraying» y que alguien bloquee cuentas ajenas probando correos al azar)."""
    if not ip:
        return False
    fila = get_db().q("SELECT COUNT(*) AS n FROM intento_login WHERE ip = ? AND exito = 0 AND fecha >= ?",
                      [ip, marca_tiempo(-timedelta(minutes=config.LOGIN_VENTANA_MIN))])[0]
    return fila["n"] >= config.LOGIN_MAX_FALLOS_IP


def desbloquear(email: str):
    """Borra los fallos recientes (lo usa el admin al restablecer la contraseña)."""
    get_db().execute("DELETE FROM intento_login WHERE email = ? AND exito = 0", [email.strip().lower()])
