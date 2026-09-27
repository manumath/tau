"""Conexión a SQLite (fastlite), migraciones versionadas (fastmigrate) y dialecto SQL.

Lo propio de SQLite está concentrado aquí para que un cambio de motor (p. ej., a PostgreSQL)
toque un solo lugar. Qué habría que cambiar en ese caso:

- Las constantes y funciones de «Dialecto SQL» (más abajo): fecha local, marca de tiempo,
  comparación que trata NULL como un valor.
- `sin_tildes`: aquí es una función de Python registrada en la conexión; en PostgreSQL, una
  función SQL con el mismo nombre (`lower(unaccent($1))`, extensión unaccent). Las consultas no
  cambian.
- La conexión y la API de fastlite que usa el código: `q`, `execute`, `t.<tabla>.insert` (devuelve
  la fila) y `t.<tabla>.update`, más `transaccion()`. Un adaptador delgado sobre psycopg basta.
- Las migraciones (`migrations/`), escritas en SQL de SQLite, y `scripts/paquete.py` (copia con
  la API de respaldo de sqlite3).
- `LIKE` de SQLite no distingue mayúsculas ASCII; el de PostgreSQL sí. Las búsquedas pasan por
  `sin_tildes` (que pasa a minúsculas), salvo la del código MSC (`msc.py`, `perfiles.directorio`),
  que en PostgreSQL necesitaría `ILIKE`.
"""
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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


# --- Dialecto SQL -------------------------------------------------------------------------------
# Se interpolan en el texto de las consultas (f-strings); nunca llevan datos del usuario.

# Fecha local de hoy ('AAAA-MM-DD', hora de La Paz: main.py fija TZ). PostgreSQL: CURRENT_DATE con
# la zona de la sesión en America/La_Paz.
HOY = "date('now', 'localtime')"
# Marca de tiempo en UTC ('AAAA-MM-DD HH:MM:SS'), como los DEFAULT (datetime('now')) de las
# tablas. PostgreSQL: to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS').
AHORA = "datetime('now')"
# Comparación que trata NULL como un valor más. PostgreSQL: IS DISTINCT FROM / IS NOT DISTINCT FROM.
DISTINTO_DE = "IS NOT"
IGUAL_A = "IS"


def vigente_hasta(columna: str) -> str:
    """Condición «sin fecha de término o termina hoy o después» sobre `columna`."""
    return f"({columna} IS NULL OR {columna} >= {HOY})"


def marca_tiempo(desplazamiento: timedelta = timedelta()) -> str:
    """Marca de tiempo UTC calculada en Python, en el formato de AHORA, para pasarla como
    parámetro (p. ej., «hace 15 minutos» o «vence en 48 horas»)."""
    return (datetime.now(timezone.utc) + desplazamiento).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def transaccion():
    """Todo o nada: `with transaccion(): …`. Se puede anidar (SQLite usa puntos de guardado)."""
    with get_db().conn:
        yield
