"""Conexión a SQLite (fastlite) y migraciones versionadas (fastmigrate)."""
from pathlib import Path

from fastlite import database
from fastmigrate.core import create_db, run_migrations

from app import config

_db = None


def init_db(path: Path | str = config.DB_PATH):
    """Crea la BD si no existe, aplica migraciones pendientes y abre la conexión."""
    global _db
    path = Path(path)
    create_db(path)
    if not run_migrations(path, config.MIGRACIONES):
        raise RuntimeError(f"Fallaron las migraciones sobre {path}")
    _db = database(path)
    _db.execute("PRAGMA foreign_keys = ON")
    return _db


def get_db():
    if _db is None:
        raise RuntimeError("Base de datos no inicializada: llame a init_db()")
    return _db


def auditar(usuario_id, accion, entidad=None, entidad_id=None, detalle=None):
    get_db().t.auditoria.insert(usuario_id=usuario_id, accion=accion, entidad=entidad,
                                entidad_id=entidad_id, detalle=detalle)
