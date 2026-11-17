"""Muestra o cambia las unidades de esta instalación: universidad, facultad, carrera e instituto (PLAN §73, etapa 6).

    uv run python scripts/unidades.py                                   # las unidades de la base
    uv run python scripts/unidades.py carrera INF "Carrera de Informática"
    uv run python scripts/unidades.py instituto III "Instituto de Investigaciones en Informática"

Una instalación es de una carrera, con su instituto como unidad opcional dentro. La base se crea con las unidades de la
Carrera de Matemática: otra carrera pone aquí sus siglas y nombres (o, ya con una cuenta, en Administración → Unidades).
De la tabla salen los nombres de los membretes, las páginas públicas y los correos, salvo que se impongan con
TAU_UNIVERSIDAD, TAU_FACULTAD, TAU_CARRERA o TAU_INSTITUTO (README). El cambio queda en la auditoría.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.comun import config, unidades  # noqa: E402
from app.comun.db import auditar, init_db  # noqa: E402


def main(args: list[str]) -> int:
    init_db(config.DB_PATH)
    if len(args) == 3:
        tipo, sigla, nombre = args
        errores = unidades.configurar(tipo, sigla, nombre)
        if errores:
            print("\n".join(errores))
            return 1
        auditar(None, "configurar_unidad", "unidad", unidades.de_tipo(tipo), f"{tipo}: {sigla} · {nombre}")
    elif args:
        print(__doc__)
        return 1
    print(f"Base de datos: {config.DB_PATH}")
    for u in unidades.todas():
        print(f"  {unidades.TIPOS[u['tipo']]:12} {u['sigla']:8} {u['nombre']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
