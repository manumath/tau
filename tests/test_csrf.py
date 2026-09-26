"""Protección CSRF: las peticiones que modifican datos deben venir del propio portal (Origin o Referer)."""
import pytest

from app import config, usuarios
from tests.conftest import HX, PASS_ADMIN, login

DATOS = {"nombres": "Carl", "apellidos": "Gauss", "email": "gauss@test.cl", "es_admin": "on"}


@pytest.mark.parametrize("encabezados,permitido", [
    ({"Origin": "http://testserver"}, True),                        # el propio portal
    ({"Referer": "http://testserver/admin/usuarios"}, True),        # sin Origin: se mira el Referer
    ({}, True),                                                     # sin ninguno: no es un navegador ajeno
    ({"Origin": "https://evil.example"}, False),                    # otro sitio
    ({"Origin": "https://estudiantes.umsa.bo"}, False),             # otro subdominio del mismo sitio
    ({"Origin": "null"}, False),                                    # iframe aislado o redirección
    ({"Referer": "https://evil.example/pagina"}, False),
    ({"Origin": "http://testserver.evil.example"}, False),          # no basta con que empiece igual
])
def test_origen(client, encabezados, permitido):
    login(client, "admin@test.cl", PASS_ADMIN)
    r = client.post("/admin/usuarios", headers={**HX, **encabezados}, data=DATOS)
    assert (r.status_code != 403) == permitido
    assert bool(usuarios.por_email("gauss@test.cl")) == permitido


def test_get_no_se_revisa(client):
    login(client, "admin@test.cl", PASS_ADMIN)
    assert client.get("/admin/usuarios", headers={"Origin": "https://evil.example"}).status_code == 200


def test_tambien_protege_el_ingreso(client):
    r = client.post("/login", headers={**HX, "Origin": "https://evil.example"},
                    data={"email": "admin@test.cl", "password": PASS_ADMIN})
    assert r.status_code == 403 and "hx-redirect" not in r.headers


def test_direccion_publica_y_extra(client, monkeypatch):
    """Detrás de un proxy, el dominio público (PORTAL_URL) y los extra configurados se aceptan."""
    monkeypatch.setattr(config, "URL_BASE", "https://portal.iimat.umsa.bo")
    monkeypatch.setattr(config, "ORIGENES_EXTRA", ["http://10.0.0.5:8080"])
    login(client, "admin@test.cl", PASS_ADMIN)
    for origen in ("https://portal.iimat.umsa.bo", "http://10.0.0.5:8080"):
        r = client.post("/admin/usuarios", headers={**HX, "Origin": origen},
                        data={**DATOS, "email": f"x{len(origen)}@test.cl"})
        assert r.status_code != 403
    assert client.post("/admin/usuarios", headers={**HX, "Origin": "https://iimat.umsa.bo"},
                       data=DATOS).status_code == 403
