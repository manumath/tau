from app.comun import config, usuarios
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login


def test_sin_sesion_redirige_al_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_peticion_htmx_sin_sesion_usa_hx_redirect(client):
    r = client.get("/admin/usuarios/filas", headers=HX)
    assert r.headers["hx-redirect"] == "/login"


def test_login_incorrecto_devuelve_solo_el_formulario(client):
    r = login(client, "admin@test.cl", "mala")
    assert "Correo o contraseña incorrectos" in r.text
    assert r.text.lstrip().startswith("<form")


def test_login_sin_htmx_devuelve_pagina_completa(client):
    r = client.post("/login", data={"email": "admin@test.cl", "password": "mala"})
    assert "<html" in r.text and "incorrectos" in r.text


def test_email_inexistente_mismo_mensaje(client):
    assert "Correo o contraseña incorrectos" in login(client, "nadie@test.cl", "x").text


def test_login_correcto(client):
    r = login(client, "ADMIN@test.cl ", PASS_ADMIN)  # mayúsculas y espacios se normalizan
    assert r.headers["hx-redirect"] == "/"
    assert "Hola, Ada" in client.get("/").text


def test_bloqueo_tras_intentos_fallidos(client):
    for _ in range(config.LOGIN_MAX_FALLOS):
        login(client, "admin@test.cl", "mala")
    r = login(client, "admin@test.cl", PASS_ADMIN)
    assert "Demasiados intentos" in r.text
    assert "hx-redirect" not in r.headers


def test_cuenta_inactiva_no_ingresa(client):
    usuarios.set_activo(usuarios.por_email("inv@test.cl")["id"], False)
    assert "incorrectos" in login(client, "inv@test.cl", PASS_TEMP).text


def test_desactivar_expulsa_sesion_abierta(client):
    login(client, "admin@test.cl", PASS_ADMIN)
    usuarios.set_activo(usuarios.por_email("admin@test.cl")["id"], False)
    r = client.get("/", follow_redirects=False)
    assert r.headers["location"] == "/login"


def test_logout(admin):
    admin.post("/logout", headers=HX)
    assert admin.get("/", follow_redirects=False).headers["location"] == "/login"


# --- Contraseña temporal -----------------------------------------------------

def test_password_temporal_obliga_a_cambiarla(client):
    assert login(client, "inv@test.cl", PASS_TEMP).headers["hx-redirect"] == "/cambiar-password"
    r = client.get("/", follow_redirects=False)
    assert r.headers["location"] == "/cambiar-password"
    assert "Defina su contraseña" in client.get("/cambiar-password").text


def test_cambio_de_password_con_errores(client):
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.post("/cambiar-password", headers=HX,
                    data={"actual": "mala", "nueva": "corta", "confirmacion": "otra"})
    assert "no es correcta" in r.text and "10 caracteres" in r.text and "no coincide" in r.text


def test_cambio_de_password_exitoso(client):
    login(client, "inv@test.cl", PASS_TEMP)
    nueva = "Mi-nueva-clave-7"
    r = client.post("/cambiar-password", headers=HX,
                    data={"actual": PASS_TEMP, "nueva": nueva, "confirmacion": nueva})
    assert r.headers["hx-redirect"] == "/"
    assert "Hola, Emmy" in client.get("/").text
    client.post("/logout")
    assert login(client, "inv@test.cl", nueva).headers["hx-redirect"] == "/"
    assert "incorrectos" in login(client, "inv@test.cl", PASS_TEMP).text


def test_nombre_del_sistema(client):
    r = client.get("/login")
    assert "<title>Ingreso · TAU</title>" in r.text
    assert "Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática" in r.text
    assert "Portal de Investigación" not in r.text


# --- Revocación de sesiones y límite por IP (PLAN §62, auditoría del 8-nov-2026) -------------------------------------

def _copia_de_sesion(client, app):
    """Otro navegador con la misma cookie de sesión (p. ej., una copia robada)."""
    from starlette.testclient import TestClient
    otro = TestClient(app)
    otro.cookies.set("tau_sesion", client.cookies.get("tau_sesion"))
    return otro


def test_salir_invalida_las_copias_de_la_cookie(admin, app):
    copia = _copia_de_sesion(admin, app)
    assert "Hola, Ada" in copia.get("/").text
    admin.post("/logout")
    r = copia.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_cambiar_la_password_cierra_las_demas_sesiones_y_no_la_propia(client, app):
    login(client, "inv@test.cl", PASS_TEMP)
    nueva = "Mi-nueva-clave-7"
    client.post("/cambiar-password", headers=HX, data={"actual": PASS_TEMP, "nueva": nueva, "confirmacion": nueva})
    otro = _copia_de_sesion(client, app)
    login(otro, "inv@test.cl", nueva)
    assert "Hola, Emmy" in otro.get("/").text
    otra = "Otra-clave-nueva-8"
    otro.post("/cambiar-password", headers=HX, data={"actual": nueva, "nueva": otra, "confirmacion": otra})
    assert "Hola, Emmy" in otro.get("/").text                       # quien cambió sigue dentro
    assert client.get("/", follow_redirects=False).headers["location"] == "/login"   # la otra sesión se cerró


def test_restablecer_la_password_cierra_la_sesion_del_usuario(admin, app):
    from starlette.testclient import TestClient
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    emmy = TestClient(app)
    login(emmy, "inv@test.cl", PASS_TEMP)
    assert "Hola, Emmy" in emmy.get("/").text
    admin.post(f"/admin/usuarios/{uid}/restablecer", headers=HX)
    assert emmy.get("/", follow_redirects=False).headers["location"] == "/login"


def test_sesion_anterior_al_cambio_sigue_valida(app):
    """Las cookies emitidas antes de la migración no traen «sv»: valen como versión 0 (nadie pierde la sesión)."""
    from starlette.requests import Request

    from app.comun.auth import _cargar_usuario
    uid = usuarios.por_email("admin@test.cl")["id"]
    req = Request({"type": "http", "path": "/", "headers": [], "method": "GET", "query_string": b""})
    assert _cargar_usuario(req, {"uid": uid}) is None and req.scope["auth"]["id"] == uid
    usuarios.cerrar_sesiones(uid)
    assert _cargar_usuario(req, {"uid": uid}) is not None   # tras salir, la cookie sin «sv» ya no vale


def test_limite_de_fallos_por_ip_con_correos_distintos(client):
    for i in range(config.LOGIN_MAX_FALLOS_IP):
        login(client, f"nadie{i}@test.cl", "mala")
    r = login(client, "admin@test.cl", PASS_ADMIN)
    assert "desde esta red" in r.text and "hx-redirect" not in r.headers


def test_bloqueo_por_correo_ofrece_recuperar(client):
    for _ in range(config.LOGIN_MAX_FALLOS):
        login(client, "admin@test.cl", "mala")
    assert "¿Olvidó su contraseña?" in login(client, "admin@test.cl", PASS_ADMIN).text
