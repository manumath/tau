"""Páginas de error con estilo, desbloqueo manual e importación de cuentas desde CSV."""
import base64

import pytest

from app.comun import config, importar_usuarios, usuarios
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login


@pytest.fixture
def admin(client):
    login(client, "admin@test.cl", PASS_ADMIN)
    return client


# --- Páginas de error ----------------------------------------------------------------------------

def test_403_con_estilo_y_navegacion(client):
    usuarios.cambiar_password(usuarios.por_email("inv@test.cl")["id"], PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/admin/usuarios")
    assert r.status_code == 403 and "<html" in r.text and "Sin permiso" in r.text
    assert "Volver al inicio" in r.text and 'href="/proyectos"' in r.text  # con la barra de navegación
    r = client.get("/admin/usuarios", headers=HX)
    assert r.status_code == 403 and "<html" not in r.text  # a HTMX, solo el código (avisa el navegador)


def test_404_de_ruta_inexistente(client, admin):
    r = admin.get("/no-existe")
    assert r.status_code == 404 and "No encontrado" in r.text and "Volver al inicio" in r.text


def test_404_sin_sesion_invita_a_ingresar(client, app):
    r = client.get("/no-existe")
    assert r.status_code == 404 and "Ir al ingreso" in r.text


def test_404_de_registro_y_api_quedan_como_estan(client, admin):
    # Un 404 que devuelve una ruta existente también se ve con estilo si no es HTMX…
    r = admin.get("/proyectos/9999/tab/resumen")
    assert r.status_code == 404 and "Volver al inicio" in r.text
    # …pero la API conserva su JSON.
    r = admin.get("/api/v1/investigadores/9999")
    assert r.status_code == 404 and r.json() == {"error": "no encontrado"}
    assert admin.get("/api/v1/no-existe").text == "No encontrado"


def test_aviso_de_error_htmx_incluido(client, app):
    assert "htmx:responseError" in client.get("/login").text


# --- Desbloqueo manual -------------------------------------------------------------------------------

def test_desbloquear_sin_cambiar_la_contrasena(client, admin):
    u = usuarios.por_email("inv@test.cl")
    for _ in range(config.LOGIN_MAX_FALLOS):
        usuarios.registrar_intento(u["email"], None, False)
    r = admin.get("/admin/usuarios")
    assert "Bloqueada por intentos fallidos" in r.text and f"/admin/usuarios/{u['id']}/desbloquear" in r.text
    hash_antes = usuarios.por_id(u["id"])["pass_hash"]
    r = admin.post(f"/admin/usuarios/{u['id']}/desbloquear", headers=HX)
    assert "Bloqueada" not in r.text and not usuarios.bloqueado(u["email"])
    assert usuarios.por_id(u["id"])["pass_hash"] == hash_antes
    assert "desbloqueada" in r.text  # aviso


# --- Importación CSV ---------------------------------------------------------------------------------------

CSV = ("Correo;Nombre;Apellido;Investigador;Admin\n"
       "sofia@test.cl;Sofía;Kovalévskaya;sí;\n"
       "INV@test.cl;Emmy;Noether;;\n"
       "no-es-correo;X;Y;;\n"
       "gauss@test.cl;Carl;Gauss;talvez;no\n"
       "sofia@test.cl;Sofía;Repetida;;\n"
       ";;;;\n"
       "ada@test.cl;Ada;Lovelace;no;sí\n")


def test_leer_csv(app):
    filas, errores = importar_usuarios.leer(CSV.encode("utf-8"))
    assert errores == []
    resumen = [(f["linea"], f["estado"]) for f in filas]
    assert resumen == [(2, "nueva"), (3, "existe"), (4, "error"), (5, "error"), (6, "error"), (8, "nueva")]
    assert "sí/no" in filas[3]["mensaje"] and "repetido" in filas[4]["mensaje"]
    assert filas[-1]["es_admin"] and not filas[-1]["es_investigador"]


def test_leer_csv_latin1_y_coma(app):
    contenido = "email,nombres,apellidos\nana@test.cl,Ana,Muñoz\n".encode("latin-1")
    filas, _ = importar_usuarios.leer(contenido)
    assert filas[0]["apellidos"] == "Muñoz" and filas[0]["es_investigador"] is True


def test_leer_csv_sin_columnas(app):
    _, errores = importar_usuarios.leer(b"correo,telefono\na@b.cl,123\n")
    assert "Faltan columnas: nombres, apellidos" in errores[0]


def test_importar_con_vista_previa_y_contrasenas(client, admin):
    r = admin.post("/admin/usuarios/importar/revisar", headers=HX,
                   files={"archivo": ("cuentas.csv", CSV.encode("utf-8"), "text/csv")})
    assert "2 cuenta(s) nueva(s)" in r.text and "Crear 2 cuenta(s)" in r.text
    assert usuarios.por_email("sofia@test.cl") is None  # la vista previa no crea nada
    r = admin.post("/admin/usuarios/importar/confirmar", headers=HX,
                   data={"contenido": base64.b64encode(CSV.encode()).decode()})
    assert "Importación terminada" in r.text and r.text.count('class="font-mono"') == 2
    sofia = usuarios.con_perfil(usuarios.por_email("sofia@test.cl")["id"])
    assert sofia["es_investigador"] and sofia["debe_cambiar_pass"]
    assert usuarios.por_email("ada@test.cl")["es_admin"]


def test_importar_con_invitaciones(client, admin, buzon):
    admin.post("/admin/usuarios/importar/confirmar", headers=HX,
               data={"contenido": base64.b64encode(CSV.encode()).decode(), "invitar": "1"})
    assert sorted(m["To"] for m in buzon) == ["ada@test.cl", "sofia@test.cl"]
    assert not usuarios.por_email("sofia@test.cl")["debe_cambiar_pass"]


def test_importar_dos_veces_no_duplica(client, admin):
    datos = {"contenido": base64.b64encode(CSV.encode()).decode()}
    admin.post("/admin/usuarios/importar/confirmar", headers=HX, data=datos)
    r = admin.post("/admin/usuarios/importar/confirmar", headers=HX, data=datos)
    assert "Se crearon 0 cuenta(s)" in r.text


def test_importar_solo_admin(client):
    usuarios.cambiar_password(usuarios.por_email("inv@test.cl")["id"], PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.post("/admin/usuarios/importar/confirmar", headers=HX,
                    data={"contenido": base64.b64encode(CSV.encode()).decode()})
    assert r.status_code == 403 and usuarios.por_email("sofia@test.cl") is None


def test_plantilla(client, admin):
    r = admin.get("/admin/usuarios/plantilla")
    assert "attachment" in r.headers["content-disposition"]
    filas, errores = importar_usuarios.leer(r.content)
    assert not errores and [f["estado"] for f in filas] == ["nueva", "nueva"]
