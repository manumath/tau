"""Búsqueda global y «Deshacer» en las acciones reversibles (PLAN.md §48, paso 4)."""
import re

from app import busqueda
from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from app.investigacion import catalogos, productos, proyectos
from tests.conftest import HX
from tests.test_catalogos import emmy  # noqa: F401
from tests.test_productos import _form


def _grupos(q, auth):
    return {g["titulo"]: [x["texto"] for x in g["items"]] for g in busqueda.buscar(q, auth, 10)}


def test_busca_en_todo_y_respeta_permisos(emmy):  # noqa: F811
    yo = usuarios.con_perfil(emmy.uid)
    yo["roles"] = permisos.roles_vigentes(emmy.uid)
    assert "Producto registrado" in emmy.post("/productos", headers=HX, data=_form(emmy.uid, titulo="Ideales primos")).text
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", "Clave-colega-1", debe_cambiar_pass=False)["id"]
    proyectos.crear(dict(nombre="Ideales en anillos (de Alan)", estado="vigente"), alan, alan)
    proyectos.crear(dict(nombre="Ideales en anillos (de Emmy)", estado="vigente"), emmy.uid, emmy.uid)
    g = _grupos("ideales", yo)
    assert g["Productos"] == ["Ideales primos"]
    assert g["Proyectos"] == ["Ideales en anillos (de Emmy)"]      # el de Alan no lo puede abrir
    assert "Cuentas" not in g                                         # no administra cuentas
    assert _grupos("turing", yo)["Personas"] == ["Alan Turing"]
    asig = busqueda.buscar("MAT-111", yo, 5)[0]["items"][0]
    assert re.fullmatch(r"/docencia/planes/\d+#asignatura-MAT-111", asig["href"])
    assert busqueda.buscar("i", yo, 5) == []                         # al menos dos letras
    # Quien ve todos los proyectos encuentra también el de Alan.
    assert not permisos.asignar(emmy.uid, "comite_acreditacion", unidades.id_de("UMSA"))
    yo["roles"] = permisos.roles_vigentes(emmy.uid)
    assert len(_grupos("ideales", yo)["Proyectos"]) == 2


def test_cuentas_solo_para_quien_ve_usuarios(admin):
    usuarios.crear("secretaria@test.cl", "Rosa", "Mamani", None, es_investigador=False)
    r = admin.get("/buscar", params={"q": "mamani"}).text
    assert "Cuentas (1)" in r and "Rosa Mamani" in r and "/admin/usuarios?q=secretaria@test.cl" in r


def test_rutas_y_campo_en_la_barra(emmy):  # noqa: F811
    pagina = emmy.get("/").text
    assert 'role="search"' in pagina and 'id="busqueda-global"' in pagina and 'href="/buscar"' in pagina
    assert emmy.get("/buscar/sugerencias", params={"q": "x"}, headers=HX).text == ""
    r = emmy.get("/buscar/sugerencias", params={"q": "zzzz"}, headers=HX).text
    assert "Sin resultados." in r and 'href="/buscar?q=zzzz"' in r
    assert "Escriba al menos dos letras" in emmy.get("/buscar").text


def test_deshacer_desactivar_un_tipo(admin):
    xid = get_db().q("SELECT id FROM tipo_actividad WHERE nombre = 'Escuela'")[0]["id"]
    admin.post(f"/admin/catalogos/actividades/{xid}/activo", headers=HX, data={"activo": "0"})
    assert not catalogos.obtener("actividades", xid)["activo"]
    pagina = admin.get("/admin/catalogos").text
    assert "«Escuela» desactivado" in pagina and "Deshacer" in pagina
    assert f'hx-post="/admin/catalogos/actividades/{xid}/activo"' in pagina
    for _ in range(2):  # «Deshacer» dos veces no vuelve a desactivar
        admin.post(f"/admin/catalogos/actividades/{xid}/activo", headers=HX, data={"activo": "1"})
        assert catalogos.obtener("actividades", xid)["activo"]


def test_deshacer_desactivar_una_cuenta(admin):
    uid = usuarios.crear("alan@test.cl", "Alan", "Turing", "Clave-colega-1", debe_cambiar_pass=False)["id"]
    r = admin.post(f"/admin/usuarios/{uid}/activo", headers=HX, data={"activo": "0"})
    assert not usuarios.por_id(uid)["activo"] and "Cuenta de Alan Turing desactivada" in r.text
    assert "Deshacer" in r.text and f'hx-target="#usuario-{uid}"' in r.text
    admin.post(f"/admin/usuarios/{uid}/activo", headers=HX, data={"activo": "1"})
    admin.post(f"/admin/usuarios/{uid}/activo", headers=HX, data={"activo": "1"})
    assert usuarios.por_id(uid)["activo"]


def test_deshacer_desenlazar_un_preprint(emmy):  # noqa: F811
    def nuevo(**extra):
        emmy.post("/productos", headers=HX, data=_form(emmy.uid, **extra))
        return get_db().q("SELECT max(id) AS id FROM producto")[0]["id"]
    pre = nuevo(titulo="Preprint", tipo_id=str(get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Preprint'")[0]["id"]),
                revision="sin_arbitraje")
    art = nuevo(titulo="Artículo")
    productos.enlazar_version(pre, art)
    r = emmy.delete(f"/productos/{pre}/version", headers=HX)
    assert "Deshacer" in r.text and re.search(rf'publicada(&quot;|")\s*:\s*(&quot;|"){art}', r.text)
    emmy.post(f"/productos/{pre}/version", headers=HX, data={"publicada": art})
    assert productos.obtener(pre)["publicado_como"]["id"] == art
