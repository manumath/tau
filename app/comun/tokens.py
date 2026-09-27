"""Enlaces de un solo uso (recuperar contraseña, invitación a una cuenta nueva).

El token viaja solo en el enlace del correo; en la BD se guarda su hash SHA-256. Un token
vale una vez, vence, y al emitir uno nuevo del mismo propósito se anulan los anteriores.
"""
import hashlib
import secrets
from datetime import timedelta

from app.comun.db import AHORA, get_db, marca_tiempo

VIGENCIA = {"recuperar": timedelta(hours=1), "invitacion": timedelta(days=3)}
MAX_RECUPERAR_POR_HORA = 3


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def emitir(usuario_id: int, proposito: str) -> str:
    db = get_db()
    db.execute(f"""UPDATE token_acceso SET usado_en = {AHORA}
                  WHERE usuario_id = ? AND proposito = ? AND usado_en IS NULL""", [usuario_id, proposito])
    token = secrets.token_urlsafe(32)
    db.execute("""INSERT INTO token_acceso (usuario_id, token_hash, proposito, expira_en)
                  VALUES (?, ?, ?, ?)""",
               [usuario_id, _hash(token), proposito, marca_tiempo(VIGENCIA[proposito])])
    return token


def vigente(token: str) -> dict | None:
    """Datos del token si existe, no se usó y no venció (no lo consume)."""
    filas = get_db().q(f"""SELECT * FROM token_acceso WHERE token_hash = ? AND usado_en IS NULL
                          AND expira_en > {AHORA}""", [_hash(token or "")])
    return filas[0] if filas else None


def consumir(token: str) -> dict | None:
    """Marca el token como usado y lo devuelve; None si no es válido."""
    t = vigente(token)
    if t:
        get_db().execute(f"UPDATE token_acceso SET usado_en = {AHORA} WHERE id = ?", [t["id"]])
    return t


def demasiados_pedidos(usuario_id: int) -> bool:
    """Límite de solicitudes de recuperación, para que nadie inunde un buzón ajeno."""
    return get_db().q("""SELECT COUNT(*) n FROM token_acceso WHERE usuario_id = ? AND proposito = 'recuperar'
                         AND creado_en > ?""", [usuario_id, marca_tiempo(-timedelta(hours=1))])[0]["n"] \
        >= MAX_RECUPERAR_POR_HORA
