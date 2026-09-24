"""Crea una cuenta de administrador pidiendo los datos por consola (para producción).

    uv run python scripts/crear_admin.py
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, usuarios  # noqa: E402
from app.db import init_db  # noqa: E402
from app.seguridad import errores_password  # noqa: E402


def main():
    init_db(config.DB_PATH)
    print(f"Base de datos: {config.DB_PATH}")
    email = input("Correo: ").strip().lower()
    if usuarios.por_email(email):
        sys.exit("Ya existe una cuenta con ese correo.")
    nombres = input("Nombres: ").strip()
    apellidos = input("Apellidos: ").strip()
    es_investigador = input("¿Es también investigador? [s/N]: ").strip().lower() == "s"
    while True:
        password = getpass.getpass("Contraseña: ")
        errores = errores_password(password, getpass.getpass("Repita la contraseña: "), email)
        if not errores:
            break
        print("\n".join(f"  - {e}" for e in errores))
    usuarios.crear(email, nombres, apellidos, password, es_admin=True,
                   es_investigador=es_investigador, debe_cambiar_pass=False)
    print(f"Administrador creado: {email}")


if __name__ == "__main__":
    main()
