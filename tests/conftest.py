import os
import tempfile
from pathlib import Path

# Antes de importar la app: que el import de main.py no toque la BD de desarrollo.
os.environ["PORTAL_DB"] = str(Path(tempfile.mkdtemp()) / "import.db")
os.environ["PORTAL_CORREO_MODO"] = "memoria"  # los correos quedan en app.correo.ENVIADOS
os.environ["PORTAL_INFORMES_PROGRAMADOS"] = "0"  # se prueban llamando a programados.revisar(hoy)
os.environ["PORTAL_REGISTROS"] = "consola"  # sin archivos de registro (pytest captura la consola)

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

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


def pytest_collection_modifyitems(config, items):
    if config.getoption("--navegador"):
        return
    omitir = pytest.mark.skip(reason="prueba en navegador: use pytest --navegador")
    for item in items:
        if "navegador" in item.path.parts:
            item.add_marker(omitir)
