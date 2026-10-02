"""Preprint y versión publicada como registros enlazados (PLAN.md §46)."""
import re

import pytest

from app.acreditacion import calidad, informes
from app.investigacion import productos, proyectos
from app.comun import usuarios
from app.comun.db import get_db
from tests.conftest import HX
from tests.test_importacion import red  # noqa: F401  (fixture: Crossref y arXiv simulados)
from tests.test_productos import _form, _id, inv  # noqa: F401


def _registrar(cliente, **extra):
    r = cliente.post("/productos", headers=HX, data=_form(cliente.uid, **extra))
    assert "Producto registrado" in r.text, r.text
    return get_db().q("SELECT max(id) AS id FROM producto")[0]["id"]


def _preprint(cliente, titulo="Primary ideals in Noetherian rings", **extra):
    return _registrar(cliente, **{"tipo_id": _id("tipo_producto", "Preprint"), "revision": "sin_arbitraje",
                                  "titulo": titulo, "arxiv_id": "2401.01234", "medio": "arXiv", **extra})


def _articulo(cliente, titulo="Primary ideals in Noetherian rings", **extra):
    return _registrar(cliente, **{"titulo": titulo, "doi": "10.1000/publicado.1", **extra})


def _input(html, nombre, valor=None):
    """La etiqueta <input name=nombre> (con ese valor, si se indica), sea cual sea el orden de los atributos."""
    for tag in re.findall(r"<input[^>]*>", html):
        if f'name="{nombre}"' in tag and (valor is None or f'value="{valor}"' in tag):
            return tag
    return None


def _enlace(pre):
    return get_db().q("SELECT publicado_como_id FROM producto WHERE id = ?", [pre])[0]["publicado_como_id"]


# --- Reglas --------------------------------------------------------------------------------------

def test_enlazar_y_reglas(inv):
    pre, art = _preprint(inv), _articulo(inv)
    otro_pre = _preprint(inv, titulo="Otro preprint", arxiv_id="2402.00001")
    assert "Solo un preprint" in productos.enlazar_version(art, pre)
    assert "«Preprint» no puede ser" in productos.enlazar_version(pre, otro_pre)
    assert productos.enlazar_version(pre, art) is None
    assert productos.obtener(pre)["publicado_como"]["id"] == art
    a = productos.obtener(art)
    assert a["preprint"]["id"] == pre and a["arxiv_id"] is None and productos.arxiv_de(a) == "2401.01234"
    assert "otro preprint" in productos.enlazar_version(otro_pre, art)  # una versión, un preprint
    productos.desenlazar_version(pre)
    assert _enlace(pre) is None


def test_cambiar_el_tipo_o_eliminar_quita_el_enlace(inv):
    pre, art = _preprint(inv), _articulo(inv)
    productos.enlazar_version(pre, art)
    datos = _form(inv.uid, titulo="Primary ideals in Noetherian rings", arxiv_id="2401.01234", medio="arXiv",
                  tipo_id=_id("tipo_producto", "Reporte de investigación"))
    assert "Cambios guardados" in inv.put(f"/productos/{pre}", headers=HX, data=datos).text
    assert _enlace(pre) is None
    productos.enlazar_version(_preprint(inv, titulo="Otro", arxiv_id="2402.00001"), art)
    productos.eliminar(art)
    assert not get_db().q("SELECT 1 FROM producto WHERE publicado_como_id IS NOT NULL")


def test_lista_sin_preprints_publicados(inv):
    pre, art = _preprint(inv), _articulo(inv)
    lista = [productos.obtener(pre), productos.obtener(art)]
    assert [p["id"] for p in productos.sin_preprints_publicados(lista)] == [pre, art]
    productos.enlazar_version(pre, art)
    lista = [productos.obtener(pre), productos.obtener(art)]
    assert [p["id"] for p in productos.sin_preprints_publicados(lista)] == [art]
    # Si la versión publicada no está en la lista (otro periodo), el preprint sí se lista.
    assert [p["id"] for p in productos.sin_preprints_publicados(lista[:1])] == [pre]


# --- Importación --------------------------------------------------------------------------------

def test_importar_la_version_de_un_preprint_registrado(inv, red):  # noqa: F811
    pre = _preprint(inv)
    pid_proyecto = proyectos.crear(dict(nombre="Anillos", estado="vigente"), inv.uid, inv.uid)
    proyectos.sincronizar("producto", pre, [pid_proyecto], {"id": inv.uid})
    # Al importar el arXiv ya registrado, se ofrece importar su versión publicada.
    r = inv.post("/productos/importar", headers=HX, data={"identificador": "2401.01234"})
    assert "ya está registrado" in r.text and "Importar su versión publicada (10.1000/publicado.1)" in r.text
    # Importarla: registro aparte, sin el arXiv (queda en el preprint), con los proyectos del preprint.
    r = inv.post("/productos/importar", headers=HX,
                 data={"identificador": "10.1000/publicado.1", "arxiv_asociado": "2401.01234"})
    assert "Quedará enlazado como versión publicada del preprint" in r.text
    assert _input(r.text, "preprint", pre) and _input(r.text, "arxiv_id", "")
    assert "checked" in _input(r.text, "proyecto", pid_proyecto)
    art = _articulo(inv, titulo="On the computational complexity of algorithms", preprint=str(pre))
    assert _enlace(pre) == art and productos.obtener(pre)["arxiv_id"] == "2401.01234"


def test_preprint_no_registrado_conserva_un_solo_registro(inv, red):  # noqa: F811
    r = inv.post("/productos/importar", headers=HX,
                 data={"identificador": "10.1000/publicado.1", "arxiv_asociado": "2401.01234"})
    assert _input(r.text, "arxiv_id", "2401.01234") and not _input(r.text, "preprint")


def test_no_enlaza_un_preprint_ajeno(inv, client):  # noqa: F811
    otra = usuarios.crear("alan@test.cl", "Alan", "Turing", "Clave-colega-1", debe_cambiar_pass=False)
    d, _ = productos.preparar(dict(tipo_id=_id("tipo_producto", "Preprint"), titulo="Ajeno", anio="2026",
                                   estado_publicacion="publicado", revision="sin_arbitraje", arxiv_id="2403.00001"),
                              [f"i:{otra['id']}"], [])
    ajeno = productos.guardar(d, [f"i:{otra['id']}"], otra["id"])
    _articulo(inv, preprint=str(ajeno))
    assert _enlace(ajeno) is None
    assert inv.get(f"/productos/{ajeno}/version", headers=HX).status_code == 403


# --- Enlace desde la ficha -------------------------------------------------------------------------

def test_enlazar_desde_la_ficha(inv):
    pre = _preprint(inv)
    _articulo(inv, titulo="Un tema muy distinto", doi="10.1000/otro")
    _registrar(inv, titulo="Primary ideals (charla)", tipo_id=_id("tipo_producto", "Presentación"), revision="sin_arbitraje")
    art = _articulo(inv, titulo="Primary ideals in noetherian rings.")
    ficha = inv.get(f"/productos/{pre}").text
    assert "Enlazar con su versión publicada" in ficha
    r = inv.get(f"/productos/{pre}/version", headers=HX).text
    assert r.index("Primary ideals in noetherian rings.") < r.index("Un tema muy distinto")  # el más parecido primero
    assert "(charla)" not in r  # una presentación no es versión publicada
    assert "checked" in _input(r, "publicada", art) and "checked" not in _input(r, "publicada", art - 2)
    assert "&quot;preprint&quot;: " in r or '"preprint": ' in r  # la caja de importar lleva el preprint
    assert inv.get(f"/productos/{art}/version", headers=HX).status_code == 404  # no es un preprint
    r = inv.post(f"/productos/{pre}/version", headers=HX, data={"publicada": art})
    assert r.headers["hx-trigger"] == "productos-cambiados" and _enlace(pre) == art
    assert "Con versión publicada" in inv.get("/productos").text
    assert "Desenlazar" in inv.get(f"/productos/{pre}").text and "Preprint" in inv.get(f"/productos/{art}").text
    assert inv.delete(f"/productos/{pre}/version", headers=HX).status_code == 200 and _enlace(pre) is None


# --- CV, perfil público, BibTeX y calidad ---------------------------------------------------------------

@pytest.fixture
def par(inv):
    pre, art = _preprint(inv), _articulo(inv, titulo="Primary ideals in Noetherian rings (published)")
    return inv, pre, art


def test_calidad_sugiere_enlazar(par):
    inv, pre, art = par
    items = {c["clave"]: c for c in calidad.revisar()}["preprints"]["items"]
    assert [i["href"] for i in items] == [f"/productos/{pre}"] and "published" in items[0]["detalle"]
    productos.enlazar_version(pre, art)
    assert {c["clave"]: c for c in calidad.revisar()}["preprints"]["n"] == 0


def test_cv_perfil_y_bibtex_listan_solo_la_publicada(par):
    inv, pre, art = par
    productos.enlazar_version(pre, art)
    datos = informes.cv(inv.uid, 2026, 2026)
    ids = [p["id"] for g in datos["grupos"].values() for p in g]
    assert art in ids and pre not in ids
    cv = inv.get("/informes/cv", params={"desde": 2026, "hasta": 2026}).text
    assert "arXiv:2401.01234" in cv and cv.count("Primary ideals") == 1
    bib = inv.get("/productos/bibtex").text
    assert bib.count("@") == 1 and "eprint = {2401.01234}" in bib
    get_db().execute("UPDATE investigador SET perfil_publico = 1 WHERE usuario_id = ?", [inv.uid])
    publico = inv.get(f"/publico/investigadores/{inv.uid}").text
    assert publico.count("Primary ideals") == 1 and "arXiv:2401.01234" in publico
    api = inv.get("/api/v1/productos").json()
    assert [(x["id"], x["arxiv"]) for x in api] == [(art, "2401.01234")]
