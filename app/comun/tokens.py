"""Enlaces de un solo uso (recuperar contraseña, invitación a una cuenta nueva).

El token viaja solo en el enlace del correo; en la BD se guarda su hash SHA-256. Un token
vale una vez, vence, y al emitir uno nuevo del mismo propósito se anulan los anteriores.
"""
import hashlib
import secrets
from datetime import timedelta

from app.comun.db import AHORA, get_db, marca_tiempo

VIGENCIA = {"recuperar": timedelta(hours=1), "invitacion": timedelta(days=3), "acceso": timedelta(minutes=30)}
PROPOSITOS_PASSWORD = ("recuperar", "invitacion")
MAX_RECUPERAR_POR_HORA = 3


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def emitir(usuario_id: int, proposito: str, vigencia: timedelta | None = None) -> str:
    db = get_db()
    db.execute(f"""UPDATE token_acceso SET usado_en = {AHORA}
                  WHERE usuario_id = ? AND proposito = ? AND usado_en IS NULL""", [usuario_id, proposito])
    token = secrets.token_urlsafe(32)
    db.execute("""INSERT INTO token_acceso (usuario_id, token_hash, proposito, expira_en)
                  VALUES (?, ?, ?, ?)""",
               [usuario_id, _hash(token), proposito, marca_tiempo(vigencia or VIGENCIA[proposito])])
    return token


def vigente(token: str, propositos: tuple[str, ...] = PROPOSITOS_PASSWORD) -> dict | None:
    """Datos del token si existe, no se usó, no venció y es de alguno de los propósitos (no lo consume). Por
    omisión solo sirven los de definir contraseña: un enlace de acceso no vale para cambiarla."""
    filas = get_db().q(f"""SELECT * FROM token_acceso WHERE token_hash = ? AND usado_en IS NULL
                          AND expira_en > {AHORA}""", [_hash(token or "")])
    return filas[0] if filas and filas[0]["proposito"] in propositos else None


def consumir(token: str, propositos: tuple[str, ...] = PROPOSITOS_PASSWORD) -> dict | None:
    """Marca el token como usado y lo devuelve; None si no es válido."""
    t = vigente(token, propositos)
    if t:
        get_db().execute(f"UPDATE token_acceso SET usado_en = {AHORA} WHERE id = ?", [t["id"]])
    return t


def demasiados_pedidos(usuario_id: int, proposito: str = "recuperar") -> bool:
    """Límite de solicitudes de recuperación o de acceso, para que nadie inunde un buzón ajeno."""
    return get_db().q("""SELECT COUNT(*) n FROM token_acceso WHERE usuario_id = ? AND proposito = ?
                         AND creado_en > ?""", [usuario_id, proposito, marca_tiempo(-timedelta(hours=1))])[0]["n"] \
        >= MAX_RECUPERAR_POR_HORA
