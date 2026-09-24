"""Carga datos de demostración.

    uv run python scripts/seed.py            # agrega lo que falte
    uv run python scripts/seed.py --reset    # borra la BD y la recrea

Las contraseñas de demostración son fijas para poder probar el portal; en
producción las cuentas se crean desde Administración → Usuarios.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, perfiles, usuarios  # noqa: E402
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

# Perfiles de ejemplo (el de Ramanujan queda vacío para ver un perfil por completar).
# El ORCID es el de Josiah Carberry, investigador ficticio que ORCID usa para pruebas.
PERFILES = {
    "sofia.kovalevskaya@instituto.test": dict(
        grado="Doctorado", cargo="Investigador(a) titular", unidad="Grupo de Ecuaciones Diferenciales",
        areas=["35-XX", "70E17", "35Q35"],
        bio="Estudio el movimiento de un cuerpo rígido alrededor de un punto fijo y la existencia "
            "de soluciones analíticas de ecuaciones en derivadas parciales."),
    "emmy.noether@instituto.test": dict(
        grado="Doctorado", cargo="Investigador(a) titular", unidad="Grupo de Álgebra",
        zbmath_id="noether.emmy", areas=["13-XX", "13E05", "16-XX", "17-XX"],
        bio="Trabajo en álgebra conmutativa y no conmutativa: anillos que satisfacen la condición "
            "de cadena ascendente, $I_1 \\subseteq I_2 \\subseteq \\cdots$, y teoría de ideales.\n\n"
            "También me interesan las relaciones entre simetrías y leyes de conservación:\n"
            "$$\\frac{d}{dt}\\left(\\frac{\\partial L}{\\partial \\dot q}\\,\\delta q\\right) = 0.$$"),
    "alan.turing@instituto.test": dict(
        grado="Doctorado", cargo="Investigador(a) asociado(a)", unidad="Grupo de Lógica y Computación",
        orcid="0000-0002-1825-0097", arxiv_id="turing_a_1", areas=["03D10", "68Q04", "03-XX"],
        bio=None),
}


def _cargar_perfil(uid: int, datos: dict | None):
    if not datos:
        return
    datos = dict(datos)
    for codigo in datos.pop("areas", []):
        perfiles.agregar_area(uid, codigo)
    perfiles.actualizar_campos(uid, **datos)


def main():
    if "--reset" in sys.argv:
        # También los archivos -wal/-shm: si quedan huérfanos, SQLite corrompe la BD nueva.
        for ruta in (config.DB_PATH, *(config.DB_PATH.with_name(config.DB_PATH.name + s)
                                       for s in ("-wal", "-shm", "-journal"))):
            ruta.unlink(missing_ok=True)
        print(f"Base de datos eliminada: {config.DB_PATH} (detenga el servidor antes de --reset)")
    init_db(config.DB_PATH)

    creados = []
    if not usuarios.por_email(ADMIN["email"]):
        usuarios.crear(**ADMIN)
        creados.append((ADMIN["email"], ADMIN["password"], "admin"))
    for inv in INVESTIGADORES:
        if not usuarios.por_email(inv["email"]):
            u = usuarios.crear(password=PASS_TEMPORAL_DEMO, **inv)
            _cargar_perfil(u["id"], PERFILES.get(inv["email"]))
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
