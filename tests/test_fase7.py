"""Recuperar contraseña, invitaciones, avisos por correo, perfiles públicos, API y auditoría."""
import re

import pytest

from app import perfiles, productos, proyectos, tokens, usuarios
from app.db import auditar, get_db
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login

CLAVE = "Clave-colega-1"


def _enlace(mensaje):
    return re.search(r"/recuperar/[\w\-]+", mensaje.get_content()).group(0)


@pytest.fixture
def emmy(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    return uid


# --- Recuperar contraseña ---------------------------------------------------------------------------

def test_recuperar_envia_enlace_de_un_solo_uso(client, emmy, buzon):
    r = client.post("/recuperar", headers=HX, data={"email": "INV@test.cl"})
    assert "Si el correo corresponde" in r.text
    assert len(buzon) == 1 and buzon[0]["To"] == "inv@test.cl"
    enlace = _enlace(buzon[0])
    assert "Nueva contraseña" in client.get(enlace).text
    r = client.post(enlace, headers=HX, data={"nueva": "corta", "confirmacion": "corta"})
    assert "10 caracteres" in r.text  # errores de política, el enlace sigue vigente
    r = client.post(enlace, headers=HX, data={"nueva": "Otra-clave-99", "confirmacion": "Otra-clave-99"})
    assert r.headers["hx-redirect"] == "/login"
    assert login(client, "inv@test.cl", "Otra-clave-99").headers["hx-redirect"] == "/"
    assert "venció o ya se usó" in client.get(enlace).text  # un solo uso


def test_recuperar_no_revela_si_la_cuenta_existe(client, emmy, buzon):
    r1 = client.post("/recuperar", headers=HX, data={"email": "nadie@test.cl"})
    r2 = client.post("/recuperar", headers=HX, data={"email": "inv@test.cl"})
    assert r1.text == r2.text and len(buzon) == 1


def test_recuperar_limita_pedidos_y_anula_los_anteriores(client, emmy, buzon):
    for _ in range(5):
        client.post("/recuperar", headers=HX, data={"email": "inv@test.cl"})
    assert len(buzon) == tokens.MAX_RECUPERAR_POR_HORA
    primero, ultimo = _enlace(buzon[0]), _enlace(buzon[-1])
    assert "venció o ya se usó" in client.get(primero).text  # al emitir uno nuevo, el anterior se anula
    assert "Nueva contraseña" in client.get(ultimo).text


def test_token_vencido_y_cuenta_inactiva(client, emmy, buzon):
    token = tokens.emitir(emmy, "recuperar")
    get_db().execute("UPDATE token_acceso SET expira_en = datetime('now', '-1 minute')")
    assert tokens.vigente(token) is None
    usuarios.set_activo(emmy, False)
    client.post("/recuperar", headers=HX, data={"email": "inv@test.cl"})
    assert buzon == []


def test_solo_se_guarda_el_hash_del_token(app, emmy):
    token = tokens.emitir(emmy, "recuperar")
    assert not get_db().q("SELECT 1 FROM token_acceso WHERE token_hash = ?", [token])


# --- Invitación ----------------------------------------------------------------------------------------

def test_invitacion_por_correo(client, buzon):
    login(client, "admin@test.cl", PASS_ADMIN)
    r = client.post("/admin/usuarios", headers=HX, data=dict(
        nombres="Maryam", apellidos="Mirzakhani", email="maryam@test.cl", es_investigador="on", invitar="on",
        categoria="contratado"))
    assert "Invitación enviada" in r.text and "pass-temporal" not in r.text
    assert buzon[0]["To"] == "maryam@test.cl" and "Invitación" in buzon[0]["Subject"]
    client.post("/logout")
    enlace = _enlace(buzon[0])
    assert "Bienvenido(a) al portal" in client.get(enlace).text
    client.post(enlace, headers=HX, data={"nueva": "Superficies-2026", "confirmacion": "Superficies-2026"})
    assert login(client, "maryam@test.cl", "Superficies-2026").headers["hx-redirect"] == "/"


# --- Avisos por correo -----------------------------------------------------------------------------------

@pytest.fixture
def proyecto(emmy):
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", CLAVE, debe_cambiar_pass=False)["id"]
    pid = proyectos.crear(dict(nombre="Álgebra", estado="vigente"), emmy, emmy)
    proyectos.agregar_participante(pid, f"i:{alan}", "co_investigador", True)
    tipo = get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Artículo en revista'")[0]["id"]
    d, _ = productos.preparar(dict(tipo_id=str(tipo), titulo="Invariantes", anio="2026",
                                   estado_publicacion="publicado", revision="arbitrado"), [f"i:{alan}"], [])
    prod = productos.guardar(d, [f"i:{alan}"], alan)
    return {"pid": pid, "alan": alan, "emmy": emmy, "prod": prod}


def test_aviso_de_propuesta_y_de_revision(proyecto, buzon):
    pid, alan, emmy, prod = proyecto["pid"], proyecto["alan"], proyecto["emmy"], proyecto["prod"]
    proyectos.sincronizar("producto", prod, [pid], {"id": alan})
    assert [m["To"] for m in buzon] == ["inv@test.cl"] and "Nueva propuesta" in buzon[0]["Subject"]
    assert f"/proyectos/{pid}?tab=pendientes" in buzon[0].get_content()
    proyectos.rechazar("producto", prod, pid, emmy, "Falta citar el proyecto.")
    assert buzon[-1]["To"] == "alan@test.cl" and "Falta citar el proyecto." in buzon[-1].get_content()
    proyectos.sincronizar("producto", prod, [pid], {"id": alan})  # vuelve a proponer → nuevo aviso
    proyectos.aprobar("producto", prod, pid, emmy)
    assert [m["Subject"].split(" ")[0] for m in buzon] == ["Nueva", "Propuesta", "Nueva", "Aprobado"]


def test_sin_avisos_a_uno_mismo_ni_a_quien_los_desactivo(proyecto, buzon):
    pid, alan, emmy, prod = proyecto["pid"], proyecto["alan"], proyecto["emmy"], proyecto["prod"]
    get_db().execute("UPDATE usuario SET avisos_correo = 0 WHERE id = ?", [emmy])
    proyectos.sincronizar("producto", prod, [pid], {"id": alan})
    assert buzon == []
    # Lo que vincula la responsable queda aprobado directo: no hay propuesta ni aviso.
    get_db().execute("UPDATE usuario SET avisos_correo = 1 WHERE id = ?", [emmy])
    proyectos.desvincular("producto", prod, pid)
    proyectos.sincronizar("producto", prod, [pid], {"id": emmy})
    assert buzon == []


# --- Perfil público y API -----------------------------------------------------------------------------------

@pytest.fixture
def publica(emmy):
    perfiles.actualizar_campos(emmy, perfil_publico=1, cargo="Titular", bio="Anillos $R$.")
    tipo = get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Artículo en revista'")[0]["id"]
    for titulo, estado in (("Publicado", "publicado"), ("En preparación", "en_preparacion")):
        d, _ = productos.preparar(dict(tipo_id=str(tipo), titulo=titulo, anio="2026", estado_publicacion=estado,
                                       revision="arbitrado", doi="10.5555/x" if estado == "publicado" else ""),
                                  [f"i:{emmy}"], [])
        productos.guardar(d, [f"i:{emmy}"], emmy)
    return emmy


def test_perfil_privado_no_se_publica(client, emmy):
    assert client.get(f"/publico/investigadores/{emmy}").status_code == 404
    assert client.get(f"/api/v1/investigadores/{emmy}").status_code == 404
    assert client.get("/api/v1/investigadores").json() == []


def test_perfil_publico_sin_sesion(client, publica):
    r = client.get(f"/publico/investigadores/{publica}")
    assert r.status_code == 200 and "Emmy Noether" in r.text and "Titular" in r.text
    assert "Publicado" in r.text and "En preparación" not in r.text
    assert "inv@test.cl" not in r.text  # el correo no se publica
    assert "Emmy Noether" in client.get("/publico/investigadores?q=noether").text


def test_api(client, publica):
    lista = client.get("/api/v1/investigadores").json()
    assert [x["apellidos"] for x in lista] == ["Noether"] and "email" not in lista[0]
    r = client.get(f"/api/v1/investigadores/{publica}")
    assert r.headers["access-control-allow-origin"] == "*"
    datos = r.json()
    assert [p["titulo"] for p in datos["productos"]] == ["Publicado"]
    assert datos["productos"][0]["autores"][0]["investigador_id"] == publica
    assert [p["doi"] for p in client.get("/api/v1/productos?anio=2026").json()] == ["10.5555/x"]
    assert client.get("/api/v1/productos?anio=1999").json() == []


def test_interruptor_de_perfil_publico(client, emmy):
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.post("/perfil/preferencias/perfil_publico", headers=HX, data={"perfil_publico": "1"})
    assert "Ver mi perfil público" in r.text and perfiles.obtener(emmy)["perfil_publico"] == 1
    client.post("/perfil/preferencias/perfil_publico", headers=HX, data={})
    assert perfiles.obtener(emmy)["perfil_publico"] == 0
    client.post("/perfil/preferencias/avisos_correo", headers=HX, data={})
    assert usuarios.por_id(emmy)["avisos_correo"] == 0


def test_rutas_publicas_no_abren_lo_privado(client, publica):
    assert client.get("/productos", follow_redirects=False).status_code == 303
    assert client.get(f"/fotos/{publica}", follow_redirects=False).status_code == 303
    # Las reglas son exactas: una ruta privada que empieza parecido sigue pidiendo sesión.
    assert client.get("/informes", follow_redirects=False).status_code == 303
    assert client.get(f"/publico/fotos/{publica}").status_code == 404  # sin foto, pero sin exigir sesión


# --- Auditoría --------------------------------------------------------------------------------------------

def test_auditoria_solo_admin_filtros_y_carga_progresiva(client, emmy):
    for i in range(60):
        auditar(emmy, "editar_perfil", "investigador", emmy, f"cambio {i}")
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/admin/auditoria").status_code == 403
    client.post("/logout")
    login(client, "admin@test.cl", PASS_ADMIN)
    r = client.get("/admin/auditoria")
    # Primera página: las 50 más recientes; la última fila pide las siguientes al hacerse visible.
    assert r.text.count('hx-trigger="revealed"') == 1
    assert ">cambio 59</td>" in r.text and ">cambio 0</td>" not in r.text
    r = client.get("/admin/auditoria/filas", headers=HX, params={"desde": 50})
    assert ">cambio 0</td>" in r.text and ">cambio 59</td>" not in r.text
    r = client.get("/admin/auditoria/tabla", headers=HX, params={"accion": "login"})
    assert "Ingreso" in r.text and "Editó perfil" not in r.text
    assert r.headers["hx-replace-url"] == "/admin/auditoria?accion=login"
