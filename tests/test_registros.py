"""Registros de actividad y de errores, página de error 500 y /salud (PLAN.md §48, paso 3)."""
import logging

import pytest
from starlette.testclient import TestClient

from app.comun import config, registros
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login


@pytest.fixture
def registro(caplog):
    """El registro «portal» no propaga a la raíz (evita líneas duplicadas): se le conecta el capturador."""
    log = logging.getLogger("portal")
    log.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="portal")
    yield caplog
    log.removeHandler(caplog.handler)


@pytest.fixture
def con_falla(app):
    """Una ruta que falla, para probar el manejo de errores."""
    @app.get("/prueba-falla")
    def falla():
        raise RuntimeError("falla de prueba")
    c = TestClient(app, raise_server_exceptions=False)
    login(c, "admin@test.cl", PASS_ADMIN)
    return c


def test_una_linea_por_peticion_sin_datos_sensibles(client, registro):
    from app.comun import usuarios
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    registro.clear()
    client.get("/productos", params={"q": "Noether secreto"})
    client.get("/recuperar/token-secreto-123")
    client.get("/static/js/acciones.js")
    client.get("/salud")
    lineas = [r.getMessage() for r in registro.records if r.name == "portal.peticiones"]
    assert lineas[0].startswith("GET /productos 200 ") and f"usuario={uid}" in lineas[0]
    assert "secreto" not in " ".join(lineas)                      # ni la búsqueda ni el token
    assert any(x.startswith("GET /recuperar/… ") for x in lineas)
    assert not any("/static/" in x or "/salud" in x for x in lineas)


def test_peticion_lenta(client, registro, monkeypatch):
    monkeypatch.setattr(registros, "LENTA_MS", 0)
    client.get("/login")
    r = [x for x in registro.records if x.name == "portal.peticiones"][-1]
    assert r.levelno == logging.WARNING and r.getMessage().endswith("(lenta)")


def test_error_con_referencia_traza_y_aviso(con_falla, registro, buzon, monkeypatch):
    monkeypatch.setattr(config, "AVISO_ERRORES", "sistemas@instituto.test")
    monkeypatch.setattr(registros, "_ultimo_aviso", -1e9)
    r = con_falla.get("/prueba-falla")
    r_htmx = con_falla.get("/prueba-falla", headers=HX)
    errores = [x for x in registro.records if x.levelno == logging.ERROR]
    ref = errores[0].getMessage().split()[1]
    assert r.status_code == 500 and "Error del sistema" in r.text and f">{ref}<" in r.text
    assert "RuntimeError: falla de prueba" in errores[0].getMessage()      # la traza queda en el registro
    assert r_htmx.status_code == 500 and r_htmx.headers["x-referencia"] in r_htmx.text
    assert len(buzon) == 1 and ref in buzon[0]["Subject"]                  # un solo aviso en 15 minutos
    assert "RuntimeError" in buzon[0].get_content()


def test_salud(client):
    r = client.get("/salud")
    assert r.status_code == 200 and r.text == "ok"


def test_archivo_de_registro(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REGISTROS", "archivo")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "portal.db")
    log = logging.getLogger("portal")
    antes = list(log.handlers)
    monkeypatch.setattr(log, "_configurado", False, raising=False)
    try:
        log.handlers = []
        registros.configurar()
        registros.log.info("hola registro")
        for h in log.handlers:
            h.flush()
        assert "hola registro" in (tmp_path / "registros" / "portal.log").read_text(encoding="utf-8")
    finally:
        for h in log.handlers:
            h.close()
        log.handlers = antes
