"""Conexión a SQLite (fastlite) y migraciones versionadas (fastmigrate)."""
import unicodedata
from pathlib import Path

from fastlite import database
from fastmigrate.core import create_db, run_migrations

from app.comun import config

_db = None
_ruta: Path | None = None


def init_db(path: Path | str = config.DB_PATH):
    """Crea la BD si no existe, aplica migraciones pendientes y abre la conexión."""
    global _db, _ruta
    path = _ruta = Path(path)
    create_db(path)
    if not run_migrations(path, config.MIGRACIONES):
        raise RuntimeError(f"Fallaron las migraciones sobre {path}")
    _db = database(path)
    _db.execute("PRAGMA foreign_keys = ON")
    _db.conn.create_scalar_function("sin_tildes", sin_tildes, 1, deterministic=True)
    return _db


def sin_tildes(texto: str | None) -> str | None:
    """'Kovalévskaya ÁLGEBRA' → 'kovalevskaya algebra'. Registrada en SQLite para buscar
    sin distinguir tildes ni mayúsculas (LIKE de SQLite solo ignora mayúsculas en ASCII)."""
    if texto is None:
        return None
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn").lower()


def get_db():
    if _db is None:
        raise RuntimeError("Base de datos no inicializada: llame a init_db()")
    return _db


def dir_datos() -> Path:
    """Directorio de la BD; los archivos subidos (fotos) se guardan junto a ella."""
    if _ruta is None:
        raise RuntimeError("Base de datos no inicializada: llame a init_db()")
    return _ruta.parent


def auditar(usuario_id, accion, entidad=None, entidad_id=None, detalle=None):
    get_db().t.auditoria.insert(usuario_id=usuario_id, accion=accion, entidad=entidad,
                                entidad_id=entidad_id, detalle=detalle)
