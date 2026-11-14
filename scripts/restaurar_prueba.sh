#!/usr/bin/env bash
# Simulacro de restauración (PLAN §72, etapa 9; docs/mantenimiento.md §5.3): restaura la última copia en una base
# TEMPORAL, comprueba su integridad y cuenta las filas de cada tabla. Nunca toca la base en uso ni data/portal.db.
#
#   scripts/restaurar_prueba.sh                      # réplica de Litestream ($LITESTREAM_REPLICA_URL o $BUCKET_NAME)
#   scripts/restaurar_prueba.sh respaldo.tar.gz      # paquete de scripts/paquete.py
#   scripts/restaurar_prueba.sh copia.db             # copia hecha con sqlite3 ".backup"
#
# Termina con código 0 solo si la integridad, las claves foráneas y la versión del esquema están bien. Anote la fecha y el
# resultado en docs/mantenimiento.md §5.3.
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/tau-restaurar.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
DB="$TMP/portal.db"
ORIGEN="${1:-}"

if [ -z "$ORIGEN" ]; then
  if [ -z "${LITESTREAM_REPLICA_URL:-}" ] && [ -n "${BUCKET_NAME:-}" ]; then
    LITESTREAM_REPLICA_URL="s3://${BUCKET_NAME}/portal.db?endpoint=fly.storage.tigris.dev&region=auto"
  fi
  if [ -z "${LITESTREAM_REPLICA_URL:-}" ]; then
    echo "Indique un paquete (.tar.gz) o una copia (.db), o defina LITESTREAM_REPLICA_URL." >&2
    exit 2
  fi
  command -v litestream >/dev/null || { echo "Falta litestream en este equipo." >&2; exit 2; }
  echo "Restaurando la réplica de Litestream…"
  litestream restore -o "$DB" "$LITESTREAM_REPLICA_URL"
elif [[ "$ORIGEN" == *.tar.gz ]]; then
  echo "Importando el paquete $ORIGEN…"
  (cd "$RAIZ" && PORTAL_DB="$DB" uv run python scripts/paquete.py importar "$ORIGEN")
elif [[ "$ORIGEN" == *.db ]]; then
  [ "$(cd "$(dirname "$ORIGEN")" && pwd)/$(basename "$ORIGEN")" != "$RAIZ/data/portal.db" ] || {
    echo "No se ensaya sobre data/portal.db: haga antes una copia con sqlite3 \".backup\"." >&2; exit 2; }
  echo "Copiando $ORIGEN…"
  sqlite3 "$ORIGEN" ".backup '$DB'"
else
  echo "Origen no reconocido: $ORIGEN (se espera .tar.gz o .db)." >&2
  exit 2
fi

cd "$RAIZ"
PORTAL_DB="$DB" uv run python - "$DB" <<'PY'
import sqlite3
import sys
from pathlib import Path

from fastmigrate.core import get_db_version

db = sys.argv[1]
con = sqlite3.connect(db)
ok = True
integridad = con.execute("PRAGMA integrity_check").fetchone()[0]
print(f"Integridad: {integridad}")
ok &= integridad == "ok"
fk = con.execute("PRAGMA foreign_key_check").fetchall()
print(f"Claves foráneas rotas: {len(fk)}")
ok &= not fk
version = get_db_version(db)
ultima = max(int(p.name[:4]) for p in Path("migrations").iterdir() if p.name[:4].isdigit())
print(f"Esquema: versión {version} (el código llega a la {ultima}; al arrancar se aplican las que falten)")
ok &= version <= ultima
print("\nFilas por tabla:")
for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
    n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    if n:
        print(f"  {t:40} {n:>8}")
print("\nSimulacro correcto." if ok else "\nEl simulacro encontró problemas: revise arriba.")
sys.exit(0 if ok else 1)
PY
