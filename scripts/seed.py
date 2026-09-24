"""Carga datos de demostración.

    uv run python scripts/seed.py            # agrega lo que falte
    uv run python scripts/seed.py --reset    # borra la BD y la recrea

Las contraseñas de demostración son fijas para poder probar el portal; en
producción las cuentas se crean desde Administración → Usuarios.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, usuarios  # noqa: E402
from app.db import init_db  # noqa: E402

ADMIN = dict(email="admin@instituto.test", nombres="Ada", apellidos="Administradora",
             password="Admin-portal-2026", es_admin=True, es_investigador=False,
             debe_cambiar_pass=False)
INVESTIGADORES = [
    # Contraseña temporal común: el portal obliga a cambiarla en el primer ingreso.
    dict(email="sofia.kovalevskaya@instituto.test", nombres="Sofía", apellidos="Kovalévskaya",
         es_admin=True),
    dict(email="emmy.noether@instituto.test", nombres="Emmy", apellidos="Noether"),
    dict(email="alan.turing@instituto.test", nombres="Alan", apellidos="Turing"),
    dict(email="srinivasa.ramanujan@instituto.test", nombres="Srinivasa", apellidos="Ramanujan"),
]
PASS_TEMPORAL_DEMO = "Temporal-2026"


def main():
    if "--reset" in sys.argv and config.DB_PATH.exists():
        config.DB_PATH.unlink()
        print(f"Base de datos eliminada: {config.DB_PATH}")
    init_db(config.DB_PATH)

    creados = []
    if not usuarios.por_email(ADMIN["email"]):
        usuarios.crear(**ADMIN)
        creados.append((ADMIN["email"], ADMIN["password"], "admin"))
    for inv in INVESTIGADORES:
        if not usuarios.por_email(inv["email"]):
            usuarios.crear(password=PASS_TEMPORAL_DEMO, **inv)
            creados.append((inv["email"], PASS_TEMPORAL_DEMO,
                            "investigador + admin" if inv.get("es_admin") else "investigador"))

    if not creados:
        print("No hay nada que agregar: los datos de demostración ya existen.")
        return
    print("Cuentas creadas:")
    for email, pw, rol in creados:
        print(f"  {email:40} {pw:20} {rol}")


if __name__ == "__main__":
    main()
