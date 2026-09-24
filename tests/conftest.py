import os
import tempfile
from pathlib import Path

# Antes de importar la app: que el import de main.py no toque la BD de desarrollo.
os.environ["PORTAL_DB"] = str(Path(tempfile.mkdtemp()) / "import.db")

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from app import usuarios  # noqa: E402

HX = {"HX-Request": "true"}
PASS_ADMIN = "Admin-clave-123"
PASS_TEMP = "Temp-clave-123"


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
