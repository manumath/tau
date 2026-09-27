import re

from app.comun import permisos, usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login

NUEVO = {"nombres": "Carl", "apellidos": "Gauss", "email": "Carl@Test.cl", "es_investigador": "on",
         "categoria": "titular"}


def _password_mostrada(html):
    return re.search(r'id="pass-temporal"[^>]*>([^<]+)<', html).group(1)


def test_investigador_no_accede_a_admin(client):
    usuarios.cambiar_password(usuarios.por_email("inv@test.cl")["id"], PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/admin/usuarios").status_code == 403
    assert client.post("/admin/usuarios", data=NUEVO).status_code == 403


def test_listado_y_busqueda(admin):
    r = admin.get("/admin/usuarios")
    assert "Noether" in r.text and "admin@test.cl" in r.text
    r = admin.get("/admin/usuarios/filas", params={"q": "noe"}, headers=HX)
    assert r.text.startswith("<tbody") and "Noether" in r.text and "admin@test.cl" not in r.text
    assert "No hay usuarios" in admin.get("/admin/usuarios/filas", params={"q": "zzz"}).text


def test_crear_usuario_muestra_password_temporal_y_actualiza_tabla(admin, client):
    r = admin.post("/admin/usuarios", data=NUEVO, headers=HX)
    assert "Cuenta creada" in r.text
    assert 'id="tabla-usuarios"' in r.text and 'hx-swap-oob="true"' in r.text
    assert "carl@test.cl" in r.text.split('hx-swap-oob="true"')[1]  # la tabla ya incluye la cuenta nueva
    password = _password_mostrada(r.text)

    u = usuarios.con_perfil(usuarios.por_email("carl@test.cl")["id"])
    assert u["es_investigador"] and not permisos.roles_vigentes(u["id"]) and u["debe_cambiar_pass"]
    assert get_db().q("SELECT accion FROM auditoria WHERE entidad_id = ? AND accion = 'crear_usuario'",
                      [u["id"]])

    admin.post("/logout")
    assert login(client, "carl@test.cl", password).headers["hx-redirect"] == "/cambiar-password"


def test_crear_usuario_valida_datos(admin):
    r = admin.post("/admin/usuarios", headers=HX,
                   data={"nombres": "", "apellidos": "X", "email": "inv@test.cl"})
    assert "obligatorios" in r.text and "Ya existe" in r.text
    assert 'value="X"' in r.text  # conserva lo ingresado
    r = admin.post("/admin/usuarios", headers=HX, data={**NUEVO, "email": "no-es-correo"})
    assert "correo válido" in r.text


def test_desactivar_y_reactivar(admin):
    uid = usuarios.por_email("inv@test.cl")["id"]
    r = admin.post(f"/admin/usuarios/{uid}/activo", headers=HX)
    assert r.text.startswith("<tr") and "Inactiva" in r.text
    assert not usuarios.por_id(uid)["activo"]
    admin.post(f"/admin/usuarios/{uid}/activo", headers=HX)
    assert usuarios.por_id(uid)["activo"]


def test_admin_no_puede_desactivarse_a_si_mismo(admin):
    uid = usuarios.por_email("admin@test.cl")["id"]
    admin.post(f"/admin/usuarios/{uid}/activo", headers=HX)
    assert usuarios.por_id(uid)["activo"]


def test_restablecer_password(admin, client):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, "Clave-olvidada-1", temporal=False)
    for _ in range(5):
        usuarios.registrar_intento("inv@test.cl", None, False)
    assert usuarios.bloqueado("inv@test.cl")

    r = admin.post(f"/admin/usuarios/{uid}/restablecer", headers=HX)
    assert "Contraseña restablecida" in r.text and f'id="usuario-{uid}"' in r.text
    password = _password_mostrada(r.text)
    assert not usuarios.bloqueado("inv@test.cl")
    assert usuarios.por_id(uid)["debe_cambiar_pass"]

    admin.post("/logout")
    assert "incorrectos" in login(client, "inv@test.cl", "Clave-olvidada-1").text
    assert login(client, "inv@test.cl", password).headers["hx-redirect"] == "/cambiar-password"
