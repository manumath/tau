"""Hash de contraseñas (Argon2), contraseñas temporales y política de contraseñas."""
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.comun import config

_ph = PasswordHasher()
# Hash de relleno: se verifica contra él cuando el email no existe, para que el
# tiempo de respuesta no revele qué cuentas existen.
_HASH_RELLENO = _ph.hash(secrets.token_hex(16))

# Sin caracteres ambiguos (0/O, 1/l/I) para que se puedan dictar o copiar a mano.
_ALFABETO = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verificar_password(pass_hash: str | None, password: str) -> bool:
    try:
        return _ph.verify(pass_hash or _HASH_RELLENO, password) and pass_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def password_temporal() -> str:
    """Contraseña temporal legible, p. ej. 'k7Rt-mQ4x-Zp9e'."""
    bloques = ("".join(secrets.choice(_ALFABETO) for _ in range(4)) for _ in range(3))
    return "-".join(bloques)


def errores_password(nueva: str, confirmacion: str, email: str = "", actual: str = "") -> list[str]:
    """Devuelve la lista de problemas de la nueva contraseña (vacía si es válida)."""
    errores = []
    if len(nueva) < config.PASS_MIN_LARGO:
        errores.append(f"Debe tener al menos {config.PASS_MIN_LARGO} caracteres.")
    if nueva != confirmacion:
        errores.append("La confirmación no coincide.")
    if actual and nueva == actual:
        errores.append("Debe ser distinta de la contraseña actual.")
    if email and nueva.lower() == email.lower():
        errores.append("No puede ser igual al correo.")
    if nueva and (nueva.isdigit() or nueva.isalpha()):
        errores.append("Combine letras con números o símbolos.")
    return errores
