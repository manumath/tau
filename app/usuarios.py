"""Acceso a datos de cuentas de usuario."""
from app import config
from app.db import get_db
from app.seguridad import hash_password


def por_id(uid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM usuario WHERE id = ?", [uid])
    return filas[0] if filas else None


def por_email(email: str) -> dict | None:
    filas = get_db().q("SELECT * FROM usuario WHERE email = ?", [email.strip()])
    return filas[0] if filas else None


def listar(texto: str = "") -> list[dict]:
    patron = f"%{texto.strip()}%"
    return get_db().q(
        """SELECT u.*, (i.usuario_id IS NOT NULL) AS es_investigador
           FROM usuario u LEFT JOIN investigador i ON i.usuario_id = u.id
           WHERE u.email LIKE :p OR u.nombres LIKE :p OR u.apellidos LIKE :p
                 OR (u.nombres || ' ' || u.apellidos) LIKE :p
           ORDER BY u.apellidos, u.nombres""",
        {"p": patron})


def con_perfil(uid: int) -> dict | None:
    filas = get_db().q(
        """SELECT u.*, (i.usuario_id IS NOT NULL) AS es_investigador
           FROM usuario u LEFT JOIN investigador i ON i.usuario_id = u.id WHERE u.id = ?""", [uid])
    return filas[0] if filas else None


def crear(email: str, nombres: str, apellidos: str, password: str, *,
          es_admin=False, es_investigador=True, debe_cambiar_pass=True) -> dict:
    db = get_db()
    u = db.t.usuario.insert(email=email.strip().lower(), nombres=nombres.strip(),
                            apellidos=apellidos.strip(), pass_hash=hash_password(password),
                            es_admin=int(es_admin), debe_cambiar_pass=int(debe_cambiar_pass))
    if es_investigador:
        db.t.investigador.insert(usuario_id=u["id"])
    return u


def cambiar_password(uid: int, password: str, *, temporal: bool):
    get_db().t.usuario.update(id=uid, pass_hash=hash_password(password),
                              debe_cambiar_pass=int(temporal))


def set_activo(uid: int, activo: bool):
    get_db().t.usuario.update(id=uid, activo=int(activo))


def registrar_acceso(uid: int):
    get_db().execute("UPDATE usuario SET ultimo_acceso = datetime('now') WHERE id = ?", [uid])


# --- Límite de intentos de login ---------------------------------------------

def registrar_intento(email: str, ip: str | None, exito: bool):
    get_db().t.intento_login.insert(email=email.strip().lower(), ip=ip, exito=int(exito))


def bloqueado(email: str) -> bool:
    """True si hay demasiados fallos recientes desde el último ingreso exitoso."""
    ventana = f"-{config.LOGIN_VENTANA_MIN} minutes"
    fila = get_db().q(
        """SELECT COUNT(*) AS n FROM intento_login
           WHERE email = :e AND exito = 0 AND fecha >= datetime('now', :v)
             AND fecha > COALESCE((SELECT MAX(fecha) FROM intento_login
                                   WHERE email = :e AND exito = 1), '')""",
        {"e": email.strip().lower(), "v": ventana})[0]
    return fila["n"] >= config.LOGIN_MAX_FALLOS


def desbloquear(email: str):
    """Borra los fallos recientes (lo usa el admin al restablecer la contraseña)."""
    get_db().execute("DELETE FROM intento_login WHERE email = ? AND exito = 0", [email.strip().lower()])
