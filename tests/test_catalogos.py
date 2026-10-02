"""Catálogos desde la interfaz (PLAN.md §47): tipos de actividad, tipos de producto e índices."""
import pytest
from starlette.testclient import TestClient

from app.investigacion import actividades, catalogos, productos
from app.comun import usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login
from tests.test_actividades import _form as _form_actividad
from tests.test_productos import _form as _form_producto


def _id(tabla, nombre):
    return get_db().q(f"SELECT id FROM {tabla} WHERE nombre = ?", [nombre])[0]["id"]


@pytest.fixture
def emmy(app):
    """La investigadora, en su propio cliente (el fixture `admin` usa el otro)."""
    c = TestClient(app)
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(c, "inv@test.cl", PASS_TEMP)
    c.uid = uid
    return c


def test_los_existentes_son_del_sistema(app):
    for cat in catalogos.CATALOGOS:
        assert all(x["del_sistema"] for x in catalogos.listar(cat))


def test_solo_la_direccion_del_instituto(admin, emmy):
    assert emmy.get("/admin/catalogos").status_code in (302, 303, 403)
    r = admin.get("/admin/catalogos")
    assert r.status_code == 200 and "Tipos de actividad" in r.text and "Índices" in r.text
    assert 'href="/admin/catalogos"' in admin.get("/").text


def test_crear_validar_renombrar_y_eliminar(admin):
    r = admin.post("/admin/catalogos/actividades", headers=HX, data={"nombre": "  seminario  "})
    assert "Ya existe un tipo de actividad con ese nombre." in r.text
    assert "obligatorio" in admin.post("/admin/catalogos/actividades", headers=HX, data={"nombre": " "}).text
    admin.post("/admin/catalogos/actividades", headers=HX, data={"nombre": "Coloquio"})
    xid = _id("tipo_actividad", "Coloquio")
    x = catalogos.obtener("actividades", xid)
    assert not x["del_sistema"] and x["activo"] and x["orden"] > 150
    admin.put(f"/admin/catalogos/actividades/{xid}", headers=HX, data={"nombre": "Coloquio del instituto"})
    assert catalogos.obtener("actividades", xid)["nombre"] == "Coloquio del instituto"
    assert get_db().q("SELECT detalle FROM auditoria WHERE accion = 'editar_catalogo'")[0]["detalle"] == \
        "Coloquio → Coloquio del instituto"
    admin.post(f"/admin/catalogos/actividades/{xid}/subir")
    assert [x["id"] for x in catalogos.listar("actividades")][-2] == xid
    admin.delete(f"/admin/catalogos/actividades/{xid}")
    assert catalogos.obtener("actividades", xid) is None


def test_los_del_sistema_no_se_renombran_ni_eliminan(admin):
    sid = _id("tipo_actividad", "Seminario")
    assert admin.get(f"/admin/catalogos/actividades/{sid}/editar", headers=HX).status_code == 403
    assert admin.put(f"/admin/catalogos/actividades/{sid}", headers=HX, data={"nombre": "Otro"}).status_code == 403
    assert "del sistema" in catalogos.eliminar("actividades", sid)
    # En un índice del sistema se cambia la política (no el nombre), con aviso y auditoría.
    iid = _id("indice", "SciELO")
    r = admin.get(f"/admin/catalogos/indices/{iid}/editar", headers=HX).text
    assert "cambia la clasificación de lo ya registrado" in r and 'name="nombre"' not in r
    admin.put(f"/admin/catalogos/indices/{iid}", headers=HX, data={"nombre": "Otro", "cuenta_como_arbitrado": "1"})
    x = catalogos.obtener("indices", iid)
    assert x["nombre"] == "SciELO" and not x["cuenta_como_indexado"] and x["cuenta_como_arbitrado"]
    a = get_db().q("SELECT * FROM auditoria WHERE accion = 'politica_indice'")[0]
    assert "cuenta_como_indexado: 1 → 0" in a["detalle"] and "cuenta_como_arbitrado: 0 → 1" in a["detalle"]


def test_en_uso_no_se_elimina(emmy):
    xid = catalogos.crear("actividades", {"nombre": "Coloquio"})
    r = emmy.post("/actividades", headers=HX, data=_form_actividad(emmy.uid, tipo_id=str(xid)))
    assert "Actividad registrada" in r.text
    assert "en uso" in catalogos.eliminar("actividades", xid)
    assert catalogos.listar("actividades")[-1]["uso"] == 1


def test_tipo_desactivado(emmy):
    """Deja de ofrecerse; lo ya registrado lo conserva y se puede editar."""
    congreso = _id("tipo_actividad", "Congreso")
    assert "Actividad registrada" in emmy.post("/actividades", headers=HX, data=_form_actividad(emmy.uid)).text
    aid = get_db().q("SELECT max(id) AS id FROM actividad")[0]["id"]
    catalogos.activar("actividades", congreso, False)
    assert f'value="{congreso}"' not in emmy.get("/actividades/nueva", headers=HX).text
    assert f'value="{congreso}"' in emmy.get(f"/actividades/{aid}/editar", headers=HX).text
    assert "Cambios guardados" in emmy.put(f"/actividades/{aid}", headers=HX,
                                           data=_form_actividad(emmy.uid, titulo="Editada")).text
    r = emmy.post("/actividades", headers=HX, data=_form_actividad(emmy.uid))
    assert "El tipo «Congreso» está desactivado: elija otro." in r.text
    assert any(t["id"] == congreso for t in actividades.tipos(todos=True))  # sigue en los filtros


def test_producto_con_tipo_e_indice_desactivados(emmy):
    datos = _form_producto(emmy.uid, revision="indexado", indice=[str(_id("indice", "Scopus"))])
    assert "Producto registrado" in emmy.post("/productos", headers=HX, data=datos).text
    pid = get_db().q("SELECT max(id) AS id FROM producto")[0]["id"]
    catalogos.activar("productos", _id("tipo_producto", "Artículo en revista"), False)
    catalogos.activar("indices", _id("indice", "Scopus"), False)
    r = emmy.get(f"/productos/{pid}/editar", headers=HX).text
    assert ">Artículo en revista<" in r and ">Scopus<" in r
    assert "Cambios guardados" in emmy.put(f"/productos/{pid}", headers=HX, data=datos).text
    assert [i["nombre"] for i in productos.obtener(pid)["indices"]] == ["Scopus"]
    assert "está desactivado" in emmy.post("/productos", headers=HX, data=_form_producto(emmy.uid)).text


def test_tipo_de_producto_nuevo_sin_revision(app):
    xid = catalogos.crear("productos", {"nombre": "Nota técnica", "admite_revision": 0})
    uid = usuarios.por_email("inv@test.cl")["id"]
    d, errores = productos.preparar(_form_producto(uid, tipo_id=str(xid), revision="arbitrado"), [f"i:{uid}"], [])
    assert not errores and d["revision"] == "sin_arbitraje"


def test_cambiar_la_politica_reclasifica_los_articulos(admin):
    """SciELO deja de contar como indexado: el artículo de una revista verificada solo en SciELO pasa a
    arbitrado (si SciELO cuenta como arbitrado); el de una revista sin verificar conserva lo declarado."""
    from app.investigacion import revistas
    aid = usuarios.por_email("admin@test.cl")["id"]
    emmy = usuarios.por_email("inv@test.cl")["id"]
    scielo = _id("indice", "SciELO")
    rid = revistas.crear({"titulo": "Revista Boliviana de Matemática", "issn": "1234-5679", "pais": "Bolivia",
                          "arbitrada": 0}, aid, verificada=True)
    revistas.agregar_indexacion(rid, {"indice_id": scielo, "desde": "2015"}, aid)
    datos = {k: v for k, v in _form_producto(emmy, revista_id=str(rid), anio="2020").items() if k != "autor"}
    d, errores = productos.preparar(datos, [f"i:{emmy}"], [])
    pid = productos.guardar(d, [f"i:{emmy}"], emmy)
    declarado = productos.guardar(productos.preparar(
        {**{k: v for k, v in _form_producto(emmy, titulo="Declarado", revision="indexado").items() if k != "autor"}},
        [f"i:{emmy}"], [str(scielo)])[0], [f"i:{emmy}"], emmy)
    assert not errores and productos.obtener(pid)["revision"] == "indexado"
    r = admin.put(f"/admin/catalogos/indices/{scielo}", headers=HX, data={"cuenta_como_arbitrado": "1"})
    assert r.headers["hx-redirect"] == "/admin/catalogos"
    assert "se reclasificaron 1 artículo(s)" in admin.get("/admin/catalogos").text  # el aviso, al llegar
    p = productos.obtener(pid)
    assert (p["revision"], p["indices"]) == ("arbitrado", [])
    assert productos.obtener(declarado)["revision"] == "indexado"   # lo declarado por los autores no cambia
    assert "1 artículo(s) reclasificado(s)" in get_db().q(
        "SELECT detalle FROM auditoria WHERE accion = 'politica_indice'")[0]["detalle"]
