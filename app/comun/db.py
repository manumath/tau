"""Conexión a SQLite (fastlite), migraciones versionadas (fastmigrate) y dialecto SQL.

Lo propio de SQLite está concentrado aquí para que un cambio de motor (p. ej., a PostgreSQL)
toque un solo lugar. Qué habría que cambiar en ese caso:

- Las constantes y funciones de «Dialecto SQL» (más abajo): fecha local, marca de tiempo,
  comparación que trata NULL como un valor.
- `sin_tildes`: aquí es una función de Python registrada en la conexión; en PostgreSQL, una
  función SQL con el mismo nombre (`lower(unaccent($1))`, extensión unaccent). Las consultas no
  cambian.
- La conexión (una por hilo, `get_db`) y la API de fastlite que usa el código: `q`, `execute`, `t.<tabla>.insert` (devuelve
  la fila) y `t.<tabla>.update`, más `transaccion()`. Un adaptador delgado sobre psycopg basta.
- Las migraciones (`migrations/`), escritas en SQL de SQLite, y `scripts/paquete.py` (copia con
  la API de respaldo de sqlite3).
- `LIKE` de SQLite no distingue mayúsculas ASCII; el de PostgreSQL sí. Las búsquedas pasan por
  `sin_tildes` (que pasa a minúsculas), salvo la del código MSC (`msc.py`, `perfiles.directorio`),
  que en PostgreSQL necesitaría `ILIKE`.
"""
import threading
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import apsw.bestpractice
from fastlite import database
from fastmigrate.core import create_db, run_migrations

from app.comun import config

# Una conexión por hilo. Las rutas síncronas corren en un pool de hilos: con una conexión compartida,
# la transacción de una petición (`with conn:`) abarcaría las escrituras de otra, que se perderían si
# la primera se revierte (y `last_insert_rowid` sería el de otro hilo). En WAL, las lecturas no se
# bloquean y las escrituras se turnan esperando hasta ESPERA_MS. `_generacion` cambia con cada
# init_db (pruebas, scripts): un hilo que tenía abierta la base anterior abre la nueva.
_ruta: Path | None = None
_generacion = 0
_local = threading.local()
ESPERA_MS = 5000
# apswutils (bajo fastlite) aplica a toda conexión nueva las «buenas prácticas» de apsw: una espera de
# 100 ms y en seguida `PRAGMA optimize`, que puede necesitar el turno de escritura. Si otro hilo está
# escribiendo, abrir la conexión fallaría con «database is locked»: la espera se alarga antes de eso.
apsw.bestpractice.connection_busy_timeout.__defaults__ = (ESPERA_MS,)


def init_db(path: Path | str = config.DB_PATH):
    """Crea la BD si no existe, aplica migraciones pendientes y abre la conexión de este hilo."""
    global _ruta, _generacion
    path = Path(path)
    create_db(path)
    if not run_migrations(path, config.MIGRACIONES):
        raise RuntimeError(f"Fallaron las migraciones sobre {path}")
    _ruta = path
    _generacion += 1
    return get_db()


def _abrir(path: Path):
    db = database(path)  # activa WAL (y la espera de ESPERA_MS, ver arriba)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA synchronous = NORMAL")  # seguro en WAL: un corte de luz no corrompe la base
    db.conn.create_scalar_function("sin_tildes", sin_tildes, 1, deterministic=True)
    return db


def sin_tildes(texto: str | None) -> str | None:
    """'Kovalévskaya ÁLGEBRA' → 'kovalevskaya algebra'. Registrada en SQLite para buscar
    sin distinguir tildes ni mayúsculas (LIKE de SQLite solo ignora mayúsculas en ASCII)."""
    if texto is None:
        return None
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn").lower()


def get_db():
    """La conexión de este hilo (la abre la primera vez)."""
    if _ruta is None:
        raise RuntimeError("Base de datos no inicializada: llame a init_db()")
    if getattr(_local, "generacion", None) != _generacion:
        _local.db, _local.generacion = _abrir(_ruta), _generacion
    return _local.db


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
    """Todo o nada: `with transaccion(): …`. Se puede anidar (SQLite usa puntos de guardado).
    Al confirmarse la más externa se ejecuta lo registrado con `al_confirmar`; si se revierte, se descarta."""
    conn = get_db().conn
    externa = not conn.in_transaction
    if externa:
        _local.al_confirmar = []
    try:
        with conn:
            yield
    except BaseException:
        if externa:
            _local.al_confirmar = []
        raise
    if externa:
        pendientes, _local.al_confirmar = _local.al_confirmar, []
        for fn in pendientes:
            fn()


def al_confirmar(fn):
    """Ejecuta `fn` cuando lo escrito hasta ahora quede confirmado: ya mismo si no hay una transacción abierta
    en este hilo, o al confirmarse la de `transaccion()` (nunca si se revierte). Sirve para acciones que no
    se pueden deshacer, como enviar un correo, y que deben ver confirmado lo que se acaba de guardar."""
    if not get_db().conn.in_transaction:
        fn()
    else:
        _local.__dict__.setdefault("al_confirmar", []).append(fn)
