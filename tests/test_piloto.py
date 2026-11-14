"""Piloto con usuarios reales (PLAN §72, etapa 9): comentarios por pantalla y adopción por rol y semana."""
from datetime import date, timedelta

import pytest

from app.comun import config, piloto, usuarios
from app.comun.db import auditar, get_db
from tests.conftest import HX, PASS_TEMP, login


def test_ruta_sin_parametros():
    assert piloto.ruta_sin_parametros("http://x/calidad/mejora/actividades/12?volver=/a") == "/calidad/mejora/actividades/:id"
    assert piloto.ruta_sin_parametros("/encuesta/AbCdEfGhIjKlMnOpQrStUvWxYz012") == "/encuesta/:id"
    assert piloto.ruta_sin_parametros("") == "/"


def test_comentario_sin_cuenta_ni_hora(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    assert piloto.comentar(uid, "/docencia/pendientes?x=1", "  ") == ["Escriba su comentario."]
    assert piloto.comentar(uid, "/docencia/pendientes?x=1", "No encontré dónde registrar el avance.") == []
    c = get_db().q("SELECT * FROM comentario_piloto")[0]
    assert (c["ruta"], c["rol"], c["dia"]) == ("/docencia/pendientes", piloto.SIN_ROL, date.today().isoformat())
    assert "usuario_id" not in c and "creado_por" not in c
    assert piloto.atender(c["id"], uid, "Se agregó el botón.") and piloto.conteo() == {"pendientes": 0, "atendidos": 1}
    assert piloto.reabrir(c["id"]) and piloto.conteo()["pendientes"] == 1


def test_adopcion_por_rol_y_semana(app):
    admin = usuarios.por_email("admin@test.cl")["id"]
    inv = usuarios.por_email("inv@test.cl")["id"]
    hoy = date.today()
    hace_dos = (hoy - timedelta(weeks=2)).isoformat() + " 12:00:00"
    auditar(inv, "login", "usuario", inv)
    auditar(inv, "crear_producto", "producto", 1)
    get_db().execute("INSERT INTO auditoria (usuario_id, accion, fecha) VALUES (?, 'login', ?)", [inv, hace_dos])
    auditar(admin, "ver_tutorias", "tutoria", 1)
    a = piloto.adopcion(hoy)
    assert len(a["semanas"]) == piloto.SEMANAS and a["semanas"][-1].weekday() == 0
    filas = {f["rol"]: f for f in a["filas"]}
    assert filas[piloto.SIN_ROL]["entraron"][-1] == 1 and filas[piloto.SIN_ROL]["registraron"][-1] == 1
    assert filas[piloto.SIN_ROL]["entraron"][-3] == 1 and filas[piloto.SIN_ROL]["registraron"][-3] == 0
    adm = [f for r, f in filas.items() if r != piloto.SIN_ROL]
    assert adm and all(f["registraron"][-1] == 0 for f in adm)        # consultar no es registrar


@pytest.fixture
def con_piloto(monkeypatch):
    monkeypatch.setattr(config, "PILOTO", True)


def test_comentar_desde_una_pantalla(client, con_piloto):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert "Comentar esta pantalla" in client.get("/").text
    r = client.get("/piloto/comentar", headers={**HX, "HX-Current-URL": "http://x/perfil/12?a=1"})
    assert r.status_code == 200 and "Pantalla: /perfil/:id" in r.text
    r = client.post("/piloto/comentar", headers=HX, data={"ruta": "/perfil/:id", "texto": "Falta un ejemplo."})
    assert r.status_code == 200 and get_db().q("SELECT ruta FROM comentario_piloto")[0]["ruta"] == "/perfil/:id"
    # Sin rol de administración no ve la lista.
    assert client.get("/admin/piloto", headers=HX).status_code in (302, 303, 403)


def test_sin_piloto_no_hay_enlace(client):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert "Comentar esta pantalla" not in client.get("/").text
    assert client.get("/piloto/comentar", headers=HX).status_code == 404


def test_la_administracion_atiende(admin, con_piloto):
    from app.comun import permisos, unidades
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "administracion_sistema", unidades.id_de("UMSA"))
    piloto.comentar(usuarios.por_email("inv@test.cl")["id"], "/inicio", "No entiendo el semáforo.")
    r = admin.get("/admin/piloto")
    assert r.status_code == 200 and "No entiendo el semáforo." in r.text and "Adopción por rol y semana" in r.text
    cid = get_db().q("SELECT id FROM comentario_piloto")[0]["id"]
    r = admin.post(f"/admin/piloto/{cid}/atendido", headers=HX, data={"nota": "Se explicó en la guía."})
    assert r.headers["hx-redirect"] == "/admin/piloto"
    assert "Se explicó en la guía." in admin.get("/admin/piloto?ver=atendidos").text
