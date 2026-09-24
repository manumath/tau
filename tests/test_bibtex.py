import base64

import pytest

from app import bibtex, productos, usuarios
from app.db import get_db
from tests.conftest import HX, PASS_TEMP, login

BIB = r"""
@string{ann = "Mathematische Annalen"}
@article{Noether1921,
  author  = {Noether, Emmy and van der Waerden, B. L. and M{\"u}ller, J{\'o}zsef},
  title   = {Idealtheorie in {R}ingbereichen: el caso $\zeta(s)$ \& otros},
  journal = ann, year = 1921, volume = {83}, number = 1, pages = {24--66},
  doi     = {10.1007/BF01464225},
}
@misc{Tao2024, author = {Terence Tao}, title = {Un preprint}, eprint = {2401.01234},
  archivePrefix = {arXiv}, year = {2024}}
@article{scholar, author = {Tao, T.}, title = {Visto en Scholar}, journal = {arXiv preprint arXiv:2402.00001},
  year = {2024}}
@inproceedings{actas, author = {Noether, E.}, title = {Charla invitada}, booktitle = {Proc. ICM},
  year = {1932}, note = {to appear}}
@phdthesis{tesis, author = {Noether, Emmy}, title = {Über die Bildung des Formensystems}, school = {Erlangen},
  year = {1907}}
@article{sin_anio, author = {Noether, Emmy}, title = {Sin año}}
@article{roto, title = {llave sin cerrar
"""


def _tipo(nombre):
    return productos.tipo(get_db().q("SELECT id FROM tipo_producto WHERE nombre = ?", [nombre])[0]["id"])


@pytest.fixture
def inv(client):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    client.uid = uid
    return client


# --- Lectura ------------------------------------------------------------------------------------------

def test_leer(app):
    entradas, generales = bibtex.leer(BIB)
    assert "1 entrada(s) con errores de sintaxis" in generales[0] and "@article{roto" in generales[0]
    e = {x["clave"]: x for x in entradas}
    n = e["Noether1921"]
    assert n["estado"] == "nueva"
    assert n["datos"]["titulo"] == r"Idealtheorie in Ringbereichen: el caso $\zeta(s)$ & otros"
    assert (n["datos"]["medio"], n["datos"]["paginas"], n["datos"]["anio"]) == ("Mathematische Annalen", "24–66", "1921")
    assert [(a["nombres"], a["apellidos"]) for a in n["autores"]] == [
        ("Emmy", "Noether"), ("B. L.", "van der Waerden"), ("József", "Müller")]
    assert e["Tao2024"]["datos"]["arxiv_id"] == "2401.01234"
    assert productos.tipo(e["Tao2024"]["datos"]["tipo_id"])["nombre"] == "Preprint"
    # Google Scholar exporta preprints como @article con journal «arXiv preprint …».
    assert productos.tipo(e["scholar"]["datos"]["tipo_id"])["nombre"] == "Preprint"
    assert e["scholar"]["datos"]["arxiv_id"] == "2402.00001"
    assert e["actas"]["datos"]["estado_publicacion"] == "aceptado"
    assert e["tesis"]["estado"] == "error" and "@phdthesis" in e["tesis"]["errores"][0]
    assert e["sin_anio"]["estado"] == "error" and "año" in e["sin_anio"]["errores"][0]


def test_leer_vacio_o_sin_entradas(app):
    assert bibtex.leer("texto cualquiera")[1][0].startswith("No se encontraron")


def test_duplicados_por_doi_y_por_titulo(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    for titulo, doi in (("Idealtheorie in Ringbereichen: el caso $\\zeta(s)$ & otros", "10.1007/bf01464225"),
                        ("UN   PREPRINT", None)):
        d, _ = productos.preparar(dict(tipo_id=str(_tipo("Preprint")["id"]), titulo=titulo,
                                       anio="1921" if doi else "2024", estado_publicacion="publicado",
                                       revision="sin_arbitraje", doi=doi), [f"i:{uid}"], [])
        productos.guardar(d, [f"i:{uid}"], uid)
    e = {x["clave"]: x for x in bibtex.leer(BIB)[0]}
    assert e["Noether1921"]["estado"] == "duplicada"   # mismo DOI (sin importar mayúsculas)
    assert e["Tao2024"]["estado"] == "duplicada"       # mismo título normalizado y año
    assert e["scholar"]["estado"] == "nueva"


def test_crear_reconoce_autores_del_instituto(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    entradas, _ = bibtex.leer(BIB)
    creados = bibtex.crear(entradas, {"Noether1921", "Tao2024"}, uid)
    assert len(creados) == 2
    p = productos.existente("10.1007/bf01464225", None)
    assert p["autores"][0]["interno"] and p["autores"][0]["id"] == uid
    assert [a["apellidos"] for a in p["autores"][1:]] == ["van der Waerden", "Müller"]
    assert get_db().q("SELECT COUNT(*) n FROM persona_externa")[0]["n"] == 3  # Waerden, Müller, Tao


# --- Exportación ------------------------------------------------------------------------------------------

def test_escapar_respeta_formulas():
    assert bibtex._escapar(r"A & B $x \% y$ 50% #1") == r"A \& B $x \% y$ 50\% \#1"
    assert bibtex._escapar(r"ya \& escapado") == r"ya \& escapado"


def test_claves_unicas():
    usadas = set()
    p = {"autores": [{"apellidos": "Müller", "nombres": "J."}], "anio": 2024}
    assert [bibtex._clave(p, usadas) for _ in range(3)] == ["Muller2024", "Muller2024a", "Muller2024b"]


def test_ida_y_vuelta(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    bibtex.crear(bibtex.leer(BIB)[0], {"Noether1921", "Tao2024", "actas"}, uid)
    texto = bibtex.exportar(productos.de_investigador(uid))
    assert "@article{Noether1921," in texto and r"$\zeta(s)$ \& otros}}," in texto and "pages = {24--66}" in texto
    assert "title = {{Idealtheorie in Ringbereichen" in texto  # doble llave: conserva mayúsculas
    assert "eprint = {2401.01234}" in texto and "note = {Aceptado}" in texto
    # Reimportado en una base vacía de productos, se obtienen los mismos datos.
    originales = {p["titulo"]: p for p in productos.de_investigador(uid)}
    get_db().execute("DELETE FROM producto")
    entradas, generales = bibtex.leer(texto)
    assert not generales and all(x["estado"] == "nueva" for x in entradas)
    for x in entradas:
        o = originales[x["datos"]["titulo"]]
        assert (x["datos"]["anio"], x["datos"]["paginas"] or None, x["datos"]["arxiv_id"]) == \
               (str(o["anio"]), o["paginas"], o["arxiv_id"])
        assert [a["apellidos"] for a in x["autores"]] == [a["apellidos"] for a in o["autores"]]
        assert x["datos"]["estado_publicacion"] == o["estado_publicacion"]


# --- Rutas -----------------------------------------------------------------------------------------------

def test_importar_con_vista_previa(inv):
    r = inv.post("/productos/importar-bibtex/revisar", headers=HX,
                 files={"archivo": ("refs.bib", BIB.encode("utf-8"), "application/x-bibtex")})
    assert "4 nueva(s) · 0 ya registrada(s) · 2 con error" in r.text and "errores de sintaxis" in r.text
    assert productos.de_investigador(inv.uid) == []  # la vista previa no registra nada
    contenido = base64.b64encode(BIB.encode()).decode()
    r = inv.post("/productos/importar-bibtex/confirmar", headers=HX,
                 data={"contenido": contenido, "clave": ["Noether1921", "actas"]})
    assert r.headers["hx-trigger"] == "productos-cambiados" and "2 producto(s) nuevo(s)" in r.text
    assert sorted(p["titulo"] for p in productos.de_investigador(inv.uid)) == [
        "Charla invitada", r"Idealtheorie in Ringbereichen: el caso $\zeta(s)$ & otros"]


def test_importar_texto_pegado_y_sumarse_a_existente(inv):
    otro = usuarios.crear("alan@test.cl", "Alan", "Turing", "Clave-colega-1")["id"]
    d, _ = productos.preparar(dict(tipo_id=str(_tipo("Preprint")["id"]), titulo="Un preprint", anio="2024",
                                   estado_publicacion="publicado", revision="sin_arbitraje"), [f"i:{otro}"], [])
    pid = productos.guardar(d, [f"i:{otro}"], otro)
    texto = "@misc{Tao2024, author={Terence Tao}, title={Un preprint}, eprint={2401.01234}, year={2024}}"
    r = inv.post("/productos/importar-bibtex/revisar", headers=HX, data={"texto": texto})
    assert "ya registrada" in r.text and f'name="sumarme" value="{pid}"' in r.text
    inv.post("/productos/importar-bibtex/confirmar", headers=HX,
             data={"contenido": base64.b64encode(texto.encode()).decode(), "sumarme": [str(pid)]})
    assert productos.es_autor(pid, inv.uid)


def test_no_se_puede_sumarse_a_un_registro_ajeno_al_archivo(inv):
    otro = usuarios.crear("alan@test.cl", "Alan", "Turing", "Clave-colega-1")["id"]
    d, _ = productos.preparar(dict(tipo_id=str(_tipo("Preprint")["id"]), titulo="Otro trabajo", anio="2024",
                                   estado_publicacion="publicado", revision="sin_arbitraje"), [f"i:{otro}"], [])
    pid = productos.guardar(d, [f"i:{otro}"], otro)
    texto = "@misc{x, author={Tao, T.}, title={Nada que ver}, eprint={2401.09999}, year={2024}}"
    inv.post("/productos/importar-bibtex/confirmar", headers=HX,
             data={"contenido": base64.b64encode(texto.encode()).decode(), "sumarme": [str(pid)]})
    assert not productos.es_autor(pid, inv.uid)


def test_importar_sin_contenido(inv):
    r = inv.post("/productos/importar-bibtex/revisar", headers=HX, data={"texto": "  "})
    assert "Suba un archivo o pegue" in r.text


def test_exportar_con_filtros_y_cv(inv):
    bibtex.crear(bibtex.leer(BIB)[0], {"Noether1921", "actas"}, inv.uid)
    r = inv.get("/productos/bibtex")
    assert r.headers["content-disposition"] == 'attachment; filename="productos.bib"'
    assert r.text.count("\n@") == 2
    r = inv.get("/productos/bibtex?q=charla")
    assert r.text.count("\n@") == 1 and "Charla invitada" in r.text
    r = inv.get("/informes/cv/bibtex?desde=1900&hasta=1925")
    assert "Noether1921" in r.text and "Charla invitada" not in r.text
    assert 'filename="cv-noether-1900-1925.bib"' in r.headers["content-disposition"]
    assert "/informes/cv/bibtex?desde=" in inv.get("/informes/cv").text  # botón en el CV
