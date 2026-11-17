"""Crea la base de una instalación nueva y carga en ella una instancia (PLAN §74).

    uv run python scripts/instalar.py                              # la instancia de TAU_INSTANCIA (o la de ejemplo)
    uv run python scripts/instalar.py --instancia /ruta/a/mi/instancia  # otra carpeta
    uv run python scripts/instalar.py --db /ruta/otra.db           # otra base (por omisión, TAU_DB)

Aplica el esquema, carga las unidades, los catálogos, los planes de estudio y el marco de calidad de la instancia y
deja activos los módulos de su perfil (`perfil` en instancia.toml; `TAU_PERFIL` manda si está). Sobre una base que ya
tiene cuentas se niega: una instancia se carga al instalar, no encima de datos en uso. Después: scripts/crear_admin.py.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import instalacion, manifiestos  # noqa: E402
from app.comun import config, modulos  # noqa: E402
from app.comun.db import get_db, init_db  # noqa: E402


def instalar(db: Path, carpeta: Path, perfil: str | None = None) -> dict:
    """→ lo que cargó cada paso. La base queda lista para crear la primera cuenta."""
    init_db(db)                                   # el esquema, para poder mirar si la base ya está en uso
    if get_db().q("SELECT 1 FROM usuario LIMIT 1"):
        raise SystemExit(f"{db} ya tiene cuentas: una instancia se carga en una base nueva.")
    res = instalacion.base_con_instancia(db, carpeta)
    manifiestos.registrar()
    modulos.sembrar(perfil or os.environ.get("TAU_PERFIL") or instalacion.leer_toml(carpeta).get("perfil") or config.PERFIL)
    res["módulos activos"] = sum(modulos.activo(m.clave) for m in modulos.todos())
    return res


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--instancia", type=Path, default=config.INSTANCIA, help="carpeta de la instancia")
    p.add_argument("--db", type=Path, default=config.DB_PATH, help="base de datos que se crea")
    p.add_argument("--perfil", help="perfil de módulos (por omisión, el de la instancia)")
    a = p.parse_args()
    res = instalar(a.db, a.instancia, a.perfil)
    print(f"Base: {a.db}\nInstancia: {a.instancia}")
    for paso, n in res.items():
        print(f"  {n:>6}  {paso}")
    print("Ahora cree la primera cuenta: uv run python scripts/crear_admin.py")


if __name__ == "__main__":
    main()
