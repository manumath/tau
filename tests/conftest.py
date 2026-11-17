import os
import tempfile
from pathlib import Path

# Antes de importar la app: que el import de main.py no toque la BD de desarrollo.
os.environ["TAU_DB"] = str(Path(tempfile.mkdtemp()) / "import.db")
# Las pruebas usan la instancia de la Carrera de Matemática (sus unidades, planes y marco de calidad): PLAN §74.
# Con TAU_INSTANCIA se elige otra; sin ella, la de Matemática si está en este equipo (no se versiona en el repositorio público)
# y, si no, la de ejemplo: las pruebas que dependen de los datos de Matemática se omiten (ver `pytest_collection_modifyitems`).
_RAIZ = Path(__file__).resolve().parent.parent
_cmat = _RAIZ / "instancias" / "cmat"
os.environ.setdefault("TAU_INSTANCIA", str(_cmat if _cmat.is_dir() else _RAIZ / "instancias" / "ejemplo"))
os.environ["TAU_PERFIL"] = "completo"  # las pruebas usan todos los módulos; los apagados, tests/test_modulos.py
os.environ["TAU_CORREO_MODO"] = "memoria"  # los correos quedan en app.correo.ENVIADOS
os.environ["TAU_INFORMES_PROGRAMADOS"] = "0"  # se prueban llamando a programados.revisar(hoy)
os.environ["TAU_REGISTROS"] = "consola"  # sin archivos de registro (pytest captura la consola)

import shutil  # noqa: E402

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.comun import db as _db  # noqa: E402

# Cada prueba usa una base nueva con la instancia cargada (unidades, planes de estudio, marco de calidad, catálogos).
# Prepararla cuesta más de un segundo y serían más de mil veces por corrida: se instala una sola base «plantilla» por
# sesión (el esquema y la instancia, sin fijar módulos) y cada base nueva parte de su copia (PLAN §73, mejora 7, y §74).
# Se reemplaza antes de importar `main` y las pruebas, para que todos reciban esta versión de `init_db`.
_PLANTILLA = Path(tempfile.mkdtemp()) / "plantilla.db"
_init_db_real = _db.init_db


def _crear_plantilla():
    """En otro proceso: la carga de la instancia abre la base con `sqlite3`, que no debe convivir con la conexión de la
    aplicación en este."""
    import subprocess
    import sys
    codigo = ("import sqlite3, sys; from pathlib import Path; from app.comun.db import init_db, get_db; from app import instalacion;"
              "init_db(sys.argv[1]); get_db().conn.close(); instalacion.cargar(sys.argv[1], sys.argv[2]);"
              "c = sqlite3.connect(sys.argv[1]); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close()")
    subprocess.run([sys.executable, "-c", codigo, str(_PLANTILLA), os.environ["TAU_INSTANCIA"]], check=True,
                   cwd=Path(__file__).resolve().parent.parent)


def _init_db_desde_plantilla(path=None):
    path = Path(path if path is not None else _db.config.DB_PATH)
    if not path.exists():
        if not _PLANTILLA.exists():
            _crear_plantilla()
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(_PLANTILLA, path)
    return _init_db_real(path)


_db.init_db = _init_db_desde_plantilla

import main  # noqa: E402
from app.comun import usuarios  # noqa: E402

HX = {"HX-Request": "true"}
PASS_ADMIN = "Admin-clave-123"
PASS_TEMP = "Temp-clave-123"


@pytest.fixture(autouse=True)
def buzon():
    """Correos enviados durante el test (se vacía antes de cada uno)."""
    from app.comun import correo
    correo.ENVIADOS.clear()
    return correo.ENVIADOS


@pytest.fixture
def app(tmp_path):
    """App con una BD nueva por test, con un admin y un investigador."""
    app = main.create_app(tmp_path / "test.db")
    usuarios.crear("admin@test.cl", "Ada", "Admin", PASS_ADMIN, es_admin=True,
                   es_investigador=False, debe_cambiar_pass=False)
    usuarios.crear("inv@test.cl", "Emmy", "Noether", PASS_TEMP)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password}, headers=HX)


@pytest.fixture
def admin(client):
    assert login(client, "admin@test.cl", PASS_ADMIN).headers["hx-redirect"] == "/"
    return client


@pytest.fixture
def carrera(admin):
    """La cuenta admin con, además, la Dirección de Carrera: la única que define categoría y vínculo."""
    from app.comun import permisos, unidades, usuarios
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    return admin


# --- Pruebas en navegador (tests/navegador) -----------------------------------------------------
# Son opcionales: necesitan Chrome (o el Chromium de Playwright) y levantan un servidor aparte.

def pytest_addoption(parser):
    parser.addoption("--navegador", action="store_true",
                     help="Ejecuta también las pruebas en navegador (tests/navegador).")


def _requieren_cmat() -> set[str]:
    archivo = Path(__file__).parent / "requieren_cmat.txt"
    return {x.strip() for x in archivo.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")}


def pytest_collection_modifyitems(config, items):
    # Las pruebas que dependen de los datos de Matemática solo corren con esa instancia (PLAN §74).
    if Path(os.environ["TAU_INSTANCIA"]).name != "cmat":
        omitir_cmat = pytest.mark.skip(reason="depende de los datos de instancias/cmat, que no está en este equipo")
        lista = _requieren_cmat()
        for item in items:
            if item.nodeid in lista or "navegador" in item.path.parts:      # los flujos en Chrome usan sus datos
                item.add_marker(omitir_cmat)
    if config.getoption("--navegador"):
        return
    omitir = pytest.mark.skip(reason="prueba en navegador: use pytest --navegador")
    for item in items:
        if "navegador" in item.path.parts:
            item.add_marker(omitir)
