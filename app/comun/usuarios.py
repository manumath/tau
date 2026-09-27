"""Acceso a datos de cuentas de usuario."""
from datetime import timedelta

from app.comun import config, permisos, unidades
from app.comun.db import AHORA, get_db, marca_tiempo, sin_tildes
from app.comun.seguridad import hash_password

# Toda fila de usuario lleva `es_admin` calculado de sus roles (transición: ver app.comun.permisos).
_COLUMNAS = f"u.*, {permisos.sql_es_admin('u')} AS es_admin"


def por_id(uid: int) -> dict | None:
    filas = get_db().q(f"SELECT {_COLUMNAS} FROM usuario u WHERE u.id = ?", [uid])
    return filas[0] if filas else None


def por_email(email: str) -> dict | None:
    filas = get_db().q(f"SELECT {_COLUMNAS} FROM usuario u WHERE u.email = ?", [email.strip()])
    return filas[0] if filas else None


def listar(texto: str = "") -> list[dict]:
    patron = f"%{sin_tildes(texto.strip())}%"
    return get_db().q(
        f"""SELECT {_COLUMNAS}, (i.usuario_id IS NOT NULL) AS es_investigador, i.categoria
           FROM usuario u LEFT JOIN investigador i ON i.usuario_id = u.id
           WHERE u.email LIKE :p OR sin_tildes(u.nombres || ' ' || u.apellidos) LIKE :p
                 OR sin_tildes(u.apellidos || ' ' || u.nombres) LIKE :p
           ORDER BY sin_tildes(u.apellidos), sin_tildes(u.nombres)""",
        {"p": patron})


def con_perfil(uid: int) -> dict | None:
    filas = get_db().q(
        f"""SELECT {_COLUMNAS}, (i.usuario_id IS NOT NULL) AS es_investigador, i.categoria
           FROM usuario u LEFT JOIN investigador i ON i.usuario_id = u.id WHERE u.id = ?""", [uid])
    return filas[0] if filas else None


def crear(email: str, nombres: str, apellidos: str, password: str, *,
          es_admin=False, es_investigador=True, debe_cambiar_pass=True,
          categoria: str | None = None, fecha_ingreso: str | None = None) -> dict:
    db = get_db()
    u = db.t.usuario.insert(email=email.strip().lower(), nombres=nombres.strip(),
                            apellidos=apellidos.strip(), pass_hash=hash_password(password),
                            debe_cambiar_pass=int(debe_cambiar_pass))
    if es_admin:
        # Transición: «administrador» = Administración del sistema + Dirección del Instituto.
        permisos.asignar(u["id"], "administracion_sistema", unidades.id_de("UMSA"))
        permisos.asignar(u["id"], "direccion_instituto", unidades.instituto())
        u["es_admin"] = 1
    if es_investigador:
        db.t.investigador.insert(usuario_id=u["id"], categoria=categoria)
        if categoria:
            from app.comun import vinculos
            vinculos.agregar(u["id"], categoria, fecha_ingreso or None)
    return u


def cambiar_password(uid: int, password: str, *, temporal: bool):
    get_db().t.usuario.update(id=uid, pass_hash=hash_password(password),
                              debe_cambiar_pass=int(temporal))


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


def desbloquear(email: str):
    """Borra los fallos recientes (lo usa el admin al restablecer la contraseña)."""
    get_db().execute("DELETE FROM intento_login WHERE email = ? AND exito = 0", [email.strip().lower()])
