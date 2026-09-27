import pytest

from app.investigacion import adjuntos, productos
from app.comun import personas, usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login


def _id(tabla, nombre):
    return str(get_db().q(f"SELECT id FROM {tabla} WHERE nombre = ?", [nombre])[0]["id"])


@pytest.fixture
def inv(client):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    client.uid = uid
    return client


@pytest.fixture
def colega(app):
    return usuarios.crear("alan@test.cl", "Alan", "Turing", "Clave-colega-1", debe_cambiar_pass=False)


def _form(uid, **extra):
    base = dict(tipo_id=_id("tipo_producto", "Artículo en revista"), titulo="Sobre ideales",
                anio="2026", estado_publicacion="publicado", revision="arbitrado",
                medio="Revista de Álgebra", autor=[f"i:{uid}"])
    return {**base, **extra}


# --- Identificadores -----------------------------------------------------------------

@pytest.mark.parametrize("entrada", ["10.1000/XYZ.1", "https://doi.org/10.1000/xyz.1",
                                     "doi: 10.1000/xyz.1", "http://dx.doi.org/10.1000/xyz.1"])
def test_normalizar_doi(entrada):
    assert productos.normalizar_doi(entrada) == "10.1000/xyz.1"


@pytest.mark.parametrize("entrada,esperado", [
    ("2401.01234", "2401.01234"), ("arXiv:2401.01234v2", "2401.01234"),
    ("https://arxiv.org/abs/2401.01234v3", "2401.01234"), ("https://arxiv.org/pdf/2401.01234.pdf", "2401.01234"),
    ("math/0501001", "math/0501001"), ("math.AG/0501001", "math.AG/0501001"),
])
def test_normalizar_arxiv(entrada, esperado):
    assert productos.normalizar_arxiv(entrada) == esperado


def test_identificadores_invalidos():
    with pytest.raises(ValueError):
        productos.normalizar_doi("no-es-doi")
    with pytest.raises(ValueError):
        productos.normalizar_arxiv("12345")


# --- Reglas de revisión e informe --------------------------------------------------------

def test_reporte_siempre_sin_arbitraje(inv):
    d, errores = productos.preparar(
        _form(inv.uid, tipo_id=_id("tipo_producto", "Reporte de investigación"), revision="indexado"),
        [f"i:{inv.uid}"], [_id("indice", "Scopus")])
    assert not errores and d["revision"] == "sin_arbitraje" and d["_indices"] == []


def test_indexado_requiere_indice_reconocido(inv):
    _, errores = productos.preparar(_form(inv.uid, revision="indexado"), [f"i:{inv.uid}"], [])
    assert any("índice" in e for e in errores)
    _, errores = productos.preparar(_form(inv.uid, revision="indexado"), [f"i:{inv.uid}"],
                                    [_id("indice", "Latindex Catálogo")])  # no cuenta como indexado
    assert any("índice" in e for e in errores)
    _, errores = productos.preparar(_form(inv.uid, revision="indexado"), [f"i:{inv.uid}"],
                                    [_id("indice", "MathSciNet")])
    assert not errores


@pytest.mark.parametrize("revision,estado,cuenta", [
    ("indexado", "publicado", True), ("arbitrado", "aceptado", True),
    ("arbitrado", "enviado", False), ("sin_arbitraje", "publicado", False),
])
def test_cuenta_para_informe(revision, estado, cuenta):
    assert productos.cuenta_para_informe({"revision": revision, "estado_publicacion": estado}) is cuenta


def test_validaciones_basicas(inv):
    _, errores = productos.preparar(_form(inv.uid, titulo="", anio="1500", tipo_id="999"), [], [])
    texto = " ".join(errores)
    assert "tipo" in texto and "título" in texto and "año" in texto and "autor" in texto


# --- Rutas -----------------------------------------------------------------------------------

def test_crear_producto_con_coautor_externo_y_orden(inv, colega):
    weyl = personas.crear_externo("Hermann", "Weyl", "IAS", "EE. UU.", inv.uid)
    r = inv.post("/productos", headers=HX,
                 data=_form(inv.uid, autor=[f"e:{weyl['id']}", f"i:{colega['id']}", f"i:{inv.uid}"]))
    assert "productos-cambiados" in r.headers["hx-trigger"]
    assert "Producto registrado" in r.text and "<form" not in r.text  # modal vacío + aviso
    p = productos.de_investigador(inv.uid)[0]
    assert [a["apellidos"] for a in p["autores"]] == ["Weyl", "Turing", "Noether"]
    # Registrado una sola vez, aparece también para el coautor del instituto.
    assert [x["id"] for x in productos.de_investigador(colega["id"])] == [p["id"]]


def test_errores_se_muestran_en_el_modal_conservando_datos(inv):
    r = inv.post("/productos", headers=HX, data=_form(inv.uid, titulo="", doi="nada"))
    assert "El título es obligatorio" in r.text and "El DOI tiene la forma" in r.text
    assert 'value="Revista de Álgebra"' in r.text and "hx-trigger" not in r.headers


def test_duplicado_por_doi(inv, colega):
    inv.post("/productos", headers=HX, data=_form(inv.uid, doi="10.5555/abc"))
    r = inv.post("/productos", headers=HX, data=_form(inv.uid, titulo="Otro", doi="https://doi.org/10.5555/ABC"))
    assert "Ya existe un producto" in r.text
    # Verificación en vivo, vista por el colega: ofrece sumarse como autor.
    inv.post("/logout")
    login(inv, "alan@test.cl", "Clave-colega-1")
    r = inv.post("/productos/verificar", headers=HX, data={"doi": "10.5555/abc"})
    assert "ya está registrado" in r.text and "Sumarme como autor" in r.text
    pid = productos.existente("10.5555/abc", None)["id"]
    inv.post(f"/productos/{pid}/sumarme", headers=HX)
    assert productos.es_autor(pid, colega["id"])


def test_campos_dependientes_del_tipo(inv):
    r = inv.get("/productos/campos", params={"tipo_id": _id("tipo_producto", "Reporte de investigación")})
    assert "sin arbitraje" in r.text and 'name="revision"' not in r.text
    r = inv.get("/productos/campos", params={"tipo_id": _id("tipo_producto", "Artículo en revista"),
                                             "revision": "indexado"})
    assert 'name="indice"' in r.text and "Latindex" in r.text
    r = inv.get("/productos/campos", params={"tipo_id": _id("tipo_producto", "Presentación")})
    assert 'name="actividad_id"' in r.text


def test_filtros_y_url(inv):
    inv.post("/productos", headers=HX, data=_form(inv.uid, titulo="Álgebra conmutativa", anio="2025"))
    inv.post("/productos", headers=HX, data=_form(inv.uid, titulo="Lógica", medio="Otra revista",
                                                   revision="sin_arbitraje"))
    r = inv.get("/productos/lista", headers=HX, params={"q": "algebra"})
    assert "Álgebra conmutativa" in r.text and "Lógica" not in r.text
    assert r.headers["hx-replace-url"] == "/productos?q=algebra"
    r = inv.get("/productos/lista", headers=HX, params={"informe": "1"})
    assert "Álgebra conmutativa" in r.text and "Lógica" not in r.text


def test_permisos_edicion_y_borrado(inv, colega, client):
    inv.post("/productos", headers=HX, data=_form(inv.uid, autor=[f"i:{inv.uid}", f"i:{colega['id']}"]))
    pid = productos.de_investigador(inv.uid)[0]["id"]
    inv.post("/logout")
    login(client, "alan@test.cl", "Clave-colega-1")
    # El coautor puede editar, pero no eliminar (lo creó otra persona).
    assert client.get(f"/productos/{pid}/editar", headers=HX).status_code == 200
    assert client.delete(f"/productos/{pid}", headers=HX).status_code == 403
    r = client.put(f"/productos/{pid}", headers=HX,
                   data=_form(inv.uid, titulo="Título corregido", autor=[f"i:{inv.uid}", f"i:{colega['id']}"]))
    assert "productos-cambiados" in r.headers["hx-trigger"]
    assert productos.obtener(pid)["titulo"] == "Título corregido"


def test_ajeno_no_puede_editar(inv, colega, client):
    inv.post("/productos", headers=HX, data=_form(inv.uid))
    pid = productos.de_investigador(inv.uid)[0]["id"]
    inv.post("/logout")
    login(client, "alan@test.cl", "Clave-colega-1")
    assert client.put(f"/productos/{pid}", headers=HX, data=_form(inv.uid)).status_code == 403
    assert "Editar" not in client.get(f"/productos/{pid}").text


def test_eliminar_borra_adjuntos(inv):
    inv.post("/productos", headers=HX, data=_form(inv.uid))
    pid = productos.de_investigador(inv.uid)[0]["id"]
    inv.post(f"/adjuntos/producto/{pid}", headers=HX,
             files={"archivo": ("slides.pdf", b"%PDF-1.4 contenido", "application/pdf")})
    adj = adjuntos.listar("producto", pid)[0]
    assert adjuntos.ruta(adj).exists()
    r = inv.delete(f"/productos/{pid}", headers=HX)
    assert "productos-cambiados" in r.headers["hx-trigger"]
    assert productos.obtener(pid) is None and not adjuntos.ruta(adj).exists()


# --- Adjuntos ---------------------------------------------------------------------------------

def test_adjuntos_validan_contenido_y_permisos(inv, colega, client):
    inv.post("/productos", headers=HX, data=_form(inv.uid))
    pid = productos.de_investigador(inv.uid)[0]["id"]
    r = inv.post(f"/adjuntos/producto/{pid}", headers=HX,
                 files={"archivo": ("virus.pdf", b"MZ\x90\x00 ejecutable", "application/pdf")})
    assert "Solo se admiten" in r.text
    r = inv.post(f"/adjuntos/producto/{pid}", headers=HX,
                 files={"archivo": ("../../Diapositivas finales.pdf", b"%PDF-1.7 x", "application/pdf")})
    adj = adjuntos.listar("producto", pid)[0]
    assert adj["nombre"] == "Diapositivas finales.pdf" and adj["mime"] == "application/pdf"
    r = inv.get(f"/adjuntos/{adj['id']}")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert "Diapositivas%20finales.pdf" in r.headers["content-disposition"]
    inv.post("/logout")
    login(client, "alan@test.cl", "Clave-colega-1")  # no es autor
    assert client.get(f"/adjuntos/{adj['id']}").status_code == 404
    assert client.delete(f"/adjuntos/{adj['id']}", headers=HX).status_code == 403


def test_nombre_seguro():
    assert adjuntos.nombre_seguro("../../etc/passwd") == "passwd"
    assert adjuntos.nombre_seguro('C:\\x\\a"b.pdf') == "a_b.pdf"
    assert adjuntos.nombre_seguro("...") == "archivo"


def test_cita():
    p = {"autores": [{"nombres": "Carl Friedrich", "apellidos": "Gauss"},
                     {"nombres": "Emmy", "apellidos": "Noether"}],
         "anio": 2026, "titulo": "Un título.", "medio": "Revista", "volumen": "12", "numero": "3",
         "paginas": "1–20"}
    assert productos.cita(p) == "Gauss, C. F.; Noether, E. (2026). Un título. Revista, 12(3), 1–20."
