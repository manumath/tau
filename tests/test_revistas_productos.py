"""Catálogo de revistas, etapa R2 (revista de cada artículo y clasificación derivada) y tipos de
productos y actividades de IAC-CINDA."""
import copy

import pytest

from app.investigacion import bibtex, importacion, productos, revistas
from app.comun import usuarios, vinculos
from app.acreditacion import informes
from app.comun.db import get_db
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login
from tests.test_importacion import CROSSREF, red  # noqa: F401


def _id(tabla, nombre):
    return get_db().q(f"SELECT id FROM {tabla} WHERE nombre = ?", [nombre])[0]["id"]


@pytest.fixture
def emmy(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    vinculos.agregar(uid, "titular", "2010-01-01")
    return uid


@pytest.fixture
def admin_id(app):
    return usuarios.por_email("admin@test.cl")["id"]


@pytest.fixture
def jsl(admin_id):
    """Revista verificada: en Scopus desde 2015 y en Latindex (que no cuenta) desde 2010."""
    rid = revistas.crear({"titulo": "Journal of Symbolic Logic", "issn": "0022-4812", "eissn": "1943-5886",
                          "pais": "Estados Unidos", "arbitrada": 1}, admin_id, verificada=True)
    revistas.agregar_indexacion(rid, {"indice_id": _id("indice", "Scopus"), "desde": "2015"}, admin_id)
    revistas.agregar_indexacion(rid, {"indice_id": _id("indice", "Latindex Catálogo"), "desde": "2010"}, admin_id)
    return rid


def _form(uid, **extra):
    base = dict(tipo_id=str(_id("tipo_producto", "Artículo en revista")), titulo="Tipos computables", anio="2020",
                estado_publicacion="publicado", revision="sin_arbitraje", medio="JSL", autor=[f"i:{uid}"],
                filiacion=["1"])
    return {**base, **extra}


def _datos(uid, **extra):
    """Como el formulario, sin los campos que no son del producto (autores y filiación)."""
    return {k: v for k, v in _form(uid, **extra).items() if k not in ("autor", "filiacion")}


def _producto(titulo="Tipos computables"):
    return productos.obtener(get_db().q("SELECT id FROM producto WHERE titulo = ?", [titulo])[0]["id"])


# --- Formulario ----------------------------------------------------------------------------------------------

def test_revista_verificada_define_la_clasificacion(client, emmy, jsl):
    login(client, "inv@test.cl", PASS_TEMP)
    client.post("/productos", headers=HX, data=_form(emmy, revista_id=str(jsl)))
    p = _producto()
    # Lo declarado («sin arbitraje», medio «JSL») se reemplaza por el catálogo del año 2020.
    assert (p["revista_id"], p["medio"], p["revision"]) == (jsl, "Journal of Symbolic Logic", "indexado")
    assert [i["nombre"] for i in p["indices"]] == ["Scopus", "Latindex Catálogo"]
    assert p["clasificacion_catalogo"]
    client.post("/productos", headers=HX, data=_form(emmy, titulo="Antiguo", anio="2012", revista_id=str(jsl)))
    antiguo = _producto("Antiguo")
    assert (antiguo["revision"], antiguo["indices"]) == ("arbitrado", [])  # 2012: solo Latindex
    assert "según el catálogo" in client.get(f"/productos/{p['id']}").text


def test_formulario_muestra_la_clasificacion(client, emmy, jsl):
    login(client, "inv@test.cl", PASS_TEMP)
    tipo = str(_id("tipo_producto", "Artículo en revista"))
    r = client.get(f"/productos/campos?tipo_id={tipo}&revista_id={jsl}&anio=2020", headers=HX)
    assert "Según el catálogo" in r.text and "indexado" in r.text and 'name="revision"' in r.text
    r = client.get(f"/productos/campos?tipo_id={tipo}", headers=HX)
    assert "Buscar revista del catálogo" in r.text and "Propóngala" in r.text
    r = client.get("/productos/revistas?revista_q=4812", headers=HX)
    assert "Journal of Symbolic Logic" in r.text and f'"revista_id": "{jsl}"' in r.text


def test_revista_pendiente_y_verificacion_posterior(client, emmy, admin_id):
    login(client, "inv@test.cl", PASS_TEMP)
    client.post("/productos", headers=HX, data=_form(emmy, revision="arbitrado", revista_nueva_titulo="Revista Andina",
                                                    revista_nueva_issn="0028-0836"))
    p = _producto()
    r = revistas.obtener(p["revista_id"])
    assert (r["titulo"], r["estado"], r["issn"], r["propuesta_por"]) == ("Revista Andina", "pendiente", "0028-0836", emmy)
    assert (p["revision"], p["clasificacion_catalogo"]) == ("arbitrado", False)  # rige lo declarado
    # La administración la verifica e indexa: el artículo se reclasifica.
    revistas.verificar(r["id"], admin_id)
    revistas.agregar_indexacion(r["id"], {"indice_id": _id("indice", "SciELO"), "desde": "2019"}, admin_id)
    assert revistas.reclasificar(r["id"]) == 1
    assert _producto()["revision"] == "indexado"
    # Otro artículo que propone la misma revista (mismo ISSN) la reutiliza.
    client.post("/productos", headers=HX, data=_form(emmy, titulo="Segundo", revista_nueva_titulo="Rev. Andina",
                                                    revista_nueva_issn="00280836"))
    assert _producto("Segundo")["revista_id"] == r["id"]


def test_propuesta_con_issn_invalido(client, emmy):
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.post("/productos", headers=HX, data=_form(emmy, revision="arbitrado", revista_nueva_titulo="X",
                                                        revista_nueva_issn="1234-5678"))
    assert "Revista propuesta" in r.text and "ISSN no válido" in r.text
    assert not get_db().q("SELECT 1 FROM producto")


def test_otros_tipos_no_llevan_revista(client, emmy, jsl):
    login(client, "inv@test.cl", PASS_TEMP)
    client.post("/productos", headers=HX, data=_form(emmy, tipo_id=str(_id("tipo_producto", "Libro")),
                                                    revision="arbitrado", revista_id=str(jsl)))
    assert _producto()["revista_id"] is None


def test_cambios_del_catalogo_reclasifican(admin, emmy, jsl):
    d, _ = productos.preparar(_datos(emmy, revista_id=str(jsl), anio="2014"), [f"i:{emmy}"], [])
    pid = productos.guardar(d, [f"i:{emmy}"], emmy, filiaciones=[1])
    assert productos.obtener(pid)["revision"] == "arbitrado"
    admin.post(f"/admin/revistas/{jsl}/indexacion", headers=HX,
               data={"indice_id": str(_id("indice", "MathSciNet")), "desde": "2000"})
    assert productos.obtener(pid)["revision"] == "indexado"
    iid = next(x["id"] for x in revistas.indexaciones(jsl) if x["indice"] == "MathSciNet")
    admin.delete(f"/admin/revistas/{jsl}/indexacion/{iid}", headers=HX)
    assert productos.obtener(pid)["revision"] == "arbitrado"


# --- Importación --------------------------------------------------------------------------------------------------

def test_crossref_reconoce_la_revista_por_issn(app, red, jsl, monkeypatch):  # noqa: F811
    datos = copy.deepcopy(CROSSREF)
    datos["message"]["issn-type"] = [{"value": "1943-5886", "type": "electronic"}]
    red.crossref = datos
    r = importacion.importar("10.1090/x")
    assert r["datos"]["revista_id"] == jsl and any("reconocida en el catálogo" in a for a in r["avisos"])
    datos["message"]["issn-type"] = [{"value": "0028-0836", "type": "print"}]
    r = importacion.importar("10.1090/x")
    assert "revista_id" not in r["datos"]
    assert (r["datos"]["revista_nueva_titulo"], r["datos"]["revista_nueva_issn"]) == (
        "Transactions of the American Mathematical Society", "0028-0836")


def test_bibtex_reconoce_la_revista(app, jsl):
    entradas, _ = bibtex.leer("@article{a, author={Noether, E.}, title={T}, journal={J}, year={2020}, issn={0022-4812}}\n"
                              "@article{b, author={Noether, E.}, title={U}, journal={Journal of symbolic logic}, year={2020}}\n"
                              "@article{c, author={Noether, E.}, title={V}, journal={Otra}, year={2020}}")
    assert [x["datos"]["revista_id"] for x in entradas] == [jsl, jsl, None]


# --- Artículos sin revista (administración) ---------------------------------------------------------------------

def test_vincular_articulos_existentes(admin, emmy, jsl):
    for titulo, medio in (("A", "Journal of Symbolic Logic"), ("B", "journal of symbolic logic"), ("C", "Revista Local")):
        d, _ = productos.preparar(_datos(emmy, titulo=titulo, medio=medio, revision="arbitrado"), [f"i:{emmy}"], [])
        productos.guardar(d, [f"i:{emmy}"], emmy)
    grupos = {g["clave"]: g for g in revistas.sin_vincular()}
    assert grupos["journal of symbolic logic"]["n"] == 2 and grupos["journal of symbolic logic"]["sugerida"]["id"] == jsl
    r = admin.get("/admin/revistas/sin-vincular")
    assert "Revista Local" in r.text and "Artículos sin revista del catálogo" in r.text
    admin.post("/admin/revistas/sin-vincular", headers=HX,
               data={"clave": "journal of symbolic logic", "revista_id": str(jsl), "accion": "vincular"})
    assert {_producto(t)["revista_id"] for t in "AB"} == {jsl} and _producto("A")["revision"] == "indexado"
    admin.post("/admin/revistas/sin-vincular", headers=HX, data={"clave": "revista local", "accion": "crear"})
    c = _producto("C")
    assert revistas.obtener(c["revista_id"])["estado"] == "pendiente" and c["revision"] == "arbitrado"
    assert revistas.sin_vincular() == []


# --- Tipos de IAC-CINDA ------------------------------------------------------------------------------------------

def test_tipos_nuevos(app):
    productos_ = {t["nombre"] for t in productos.tipos()}
    assert {"Patente", "Traducción"} <= productos_
    actividades_ = {f["nombre"] for f in get_db().q("SELECT nombre FROM tipo_actividad")}
    assert {"Transferencia de conocimiento", "Participación en red de investigación",
            "Estancia o pasantía de investigación"} <= actividades_
    assert "Estadía de investigación" not in actividades_


def test_patente_en_cv_y_memoria(client, emmy):
    tipo = str(_id("tipo_producto", "Patente"))
    d, errores = productos.preparar(dict(tipo_id=tipo, titulo="Método de cifrado", anio="2026", mes="3",
                                         estado_publicacion="enviado", revision="arbitrado", medio="SENAPI"),
                                    [f"i:{emmy}"], [])
    assert not errores and d["revision"] == "sin_arbitraje"
    productos.guardar(d, [f"i:{emmy}"], emmy)
    cv = informes.cv(emmy, 2026, 2026)
    assert [p["titulo"] for p in cv["grupos"]["patentes"]] == ["Método de cifrado"]  # aunque esté en trámite
    m = informes.memoria(2026)
    assert [p["titulo"] for p in m["otros_resultados"]] == ["Método de cifrado"] and m["productos"] == []
    login(client, "inv@test.cl", PASS_TEMP)
    assert "SENAPI" in client.get(f"/productos/campos?tipo_id={tipo}", headers=HX).text
    client.post("/logout")
    login(client, "admin@test.cl", PASS_ADMIN)
    assert "Patentes y traducciones (1)" in client.get("/informes/memoria?anio=2026").text
