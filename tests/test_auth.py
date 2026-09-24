from app import config, usuarios
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
