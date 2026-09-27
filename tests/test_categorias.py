"""Ajustes, etapa A: categoría de cada investigador(a)."""
import base64

import pytest

from app.comun import importar_usuarios, usuarios
from app.investigacion import perfiles
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login


def _uid(email="inv@test.cl"):
    return usuarios.por_email(email)["id"]


def test_cuenta_nueva_sin_categoria_por_omision(app):
    assert usuarios.con_perfil(_uid())["categoria"] is None
    assert perfiles.categoria_texto(None) == "Sin categoría"


def test_la_base_rechaza_categorias_desconocidas(app):
    with pytest.raises(Exception):
        get_db().execute("UPDATE investigador SET categoria = 'emerito' WHERE usuario_id = ?", [_uid()])
    with pytest.raises(ValueError):
        perfiles.cambiar_categoria(_uid(), "emerito")


def test_alta_exige_categoria_para_investigadores(admin):
    datos = {"nombres": "Carl", "apellidos": "Gauss", "email": "gauss@test.cl", "es_investigador": "on"}
    r = admin.post("/admin/usuarios", headers=HX, data=datos)
    assert "Elija la categoría" in r.text and not usuarios.por_email("gauss@test.cl")
    admin.post("/admin/usuarios", headers=HX, data={**datos, "categoria": "interino"})
    assert usuarios.con_perfil(_uid("gauss@test.cl"))["categoria"] == "interino"


def test_alta_de_solo_admin_no_lleva_categoria(admin):
    admin.post("/admin/usuarios", headers=HX, data={"nombres": "Ada", "apellidos": "Lovelace",
                                                    "email": "ada@test.cl", "es_admin": "on",
                                                    "categoria": "titular"})
    u = usuarios.con_perfil(_uid("ada@test.cl"))
    assert u["es_admin"] and not u["es_investigador"] and u["categoria"] is None


def test_cambiar_categoria_desde_el_listado(admin):
    uid = _uid()
    assert "Sin categoría" in admin.get("/admin/usuarios").text
    r = admin.post(f"/admin/usuarios/{uid}/categoria", headers=HX, data={"categoria": "contratado"})
    assert r.status_code == 200 and f'id="usuario-{uid}"' in r.text
    assert usuarios.con_perfil(uid)["categoria"] == "contratado"
    assert get_db().q("SELECT detalle FROM auditoria WHERE accion = 'cambiar_categoria'")[0]["detalle"] \
        == "Sin categoría → Contratado(a)"
    admin.post(f"/admin/usuarios/{uid}/categoria", headers=HX, data={"categoria": ""})
    assert usuarios.con_perfil(uid)["categoria"] is None
    r = admin.post(f"/admin/usuarios/{uid}/categoria", headers=HX, data={"categoria": "emerito"})
    assert r.status_code == 400


def test_solo_admin_cambia_la_categoria(client):
    usuarios.cambiar_password(_uid(), PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.post(f"/admin/usuarios/{_uid()}/categoria", headers=HX, data={"categoria": "titular"})
    assert r.status_code == 403 and usuarios.con_perfil(_uid())["categoria"] is None


def test_csv_con_categoria(app):
    csv = ("email,nombres,apellidos,categoría,investigador,admin\n"
           "a@test.cl,Ana,Uno,Titular,sí,no\n"
           "b@test.cl,Beatriz,Dos,contratada,,\n"
           "c@test.cl,Carla,Tres,,,\n"
           "d@test.cl,Diana,Cuatro,emérita,,\n"
           "e@test.cl,Elena,Cinco,interina,no,sí\n")
    filas, errores = importar_usuarios.leer(csv.encode())
    assert not errores
    por_email = {f["email"]: f for f in filas}
    assert por_email["a@test.cl"]["categoria"] == "titular"
    assert por_email["b@test.cl"]["categoria"] == "contratado"
    assert por_email["c@test.cl"]["estado"] == "nueva" and "Sin categoría" in por_email["c@test.cl"]["mensaje"]
    assert por_email["d@test.cl"]["estado"] == "error" and "categoría no válida" in por_email["d@test.cl"]["mensaje"].lower()
    assert por_email["e@test.cl"]["estado"] == "error"  # solo investigadores tienen categoría


def test_csv_crea_cuentas_con_categoria(admin):
    csv = "email,nombres,apellidos,categoria\nx@test.cl,Xenia,Equis,externa\n"
    admin.post("/admin/usuarios/importar/confirmar", headers=HX,
               data={"contenido": base64.b64encode(csv.encode()).decode()})
    assert usuarios.con_perfil(_uid("x@test.cl"))["categoria"] == "externo"


def test_plantilla_incluye_categoria(app):
    filas, errores = importar_usuarios.leer(importar_usuarios.PLANTILLA.encode("utf-8-sig"))
    assert not errores and [f["categoria"] for f in filas] == ["titular", "invitado"]


def test_perfil_y_directorio_muestran_categoria(client):
    uid = _uid()
    perfiles.cambiar_categoria(uid, "titular")
    otro = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP, debe_cambiar_pass=False,
                          categoria="invitado")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert "Titular" in client.get("/perfil").text
    assert "Invitado(a)" in client.get(f"/investigadores/{otro}").text

    todos = client.get("/investigadores").text
    assert "Emmy" in todos and "Alan" in todos
    r = client.get("/investigadores/resultados?categoria=invitado", headers=HX)
    assert "Alan" in r.text and "Emmy" not in r.text
    assert r.headers["hx-replace-url"] == "/investigadores?categoria=invitado"
    # Un valor desconocido se ignora (no filtra).
    assert "Emmy" in client.get("/investigadores/resultados?categoria=xyz", headers=HX).text
    # «Sin categoría» es un filtro de la administración: para los demás no aparece.
    assert 'value="sin"' not in todos


def test_directorio_sin_categoria(app):
    usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP, categoria="titular")
    assert [p["apellidos"] for p in perfiles.directorio(categoria="sin")] == ["Noether"]
    assert [p["apellidos"] for p in perfiles.directorio(categoria="titular")] == ["Turing"]
