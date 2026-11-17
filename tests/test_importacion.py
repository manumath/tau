"""Importación desde Crossref y arXiv. La red se simula: `importacion._get` se reemplaza por
respuestas fijas, así los tests no dependen de servicios externos."""
import json
import re

import httpx2
import pytest

from app.investigacion import importacion, productos
from app.comun import personas, usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login

CROSSREF = {"message": {
    "type": "journal-article",
    "title": ["On the <i>computational</i> complexity of algorithms"],
    "author": [{"given": "J.", "family": "Hartmanis", "affiliation": [{"name": "GE Research Lab"}]},
               {"given": "Emmy", "family": "Noether", "ORCID": "http://orcid.org/0000-0002-1825-0097"},
               {"given": "R. E.", "family": "Stearns"}],
    "container-title": ["Transactions of the American Mathematical Society"],
    "volume": "117", "issue": "0", "page": "285-306",
    "issued": {"date-parts": [[1965, 5]]},
    "abstract": "<jats:p>Abstract. We study <jats:italic>time</jats:italic> &amp; space.</jats:p>",
}}

ARXIV = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <title>Primary ideals in
      Noetherian rings</title>
    <summary>We prove that every ideal $I$ has a
      primary decomposition.</summary>
    <published>2024-01-03T10:00:00Z</published>
    <author><name>Emmy Noether</name></author>
    <author><name>Bartel Leendert van der Waerden</name><arxiv:affiliation>Leipzig</arxiv:affiliation></author>
    <arxiv:doi>10.1000/publicado.1</arxiv:doi>
    <arxiv:journal_ref>Math. Ann. 83 (2024) 24-66</arxiv:journal_ref>
    <arxiv:primary_category term="math.AC"/>
  </entry>
</feed>"""

ARXIV_VACIO = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>"""


class Falso:
    """Reemplazo de importacion._get: responde según la URL y registra las llamadas."""
    def __init__(self, crossref=CROSSREF, arxiv=ARXIV, estado=200):
        self.crossref, self.arxiv, self.estado, self.llamadas = crossref, arxiv, estado, []

    def __call__(self, url, params=None):
        self.llamadas.append((url, params))
        if "crossref" in url:
            return httpx2.Response(self.estado, content=json.dumps(self.crossref).encode(),
                                   headers={"content-type": "application/json"})
        return httpx2.Response(self.estado, content=self.arxiv.encode())


@pytest.fixture
def red(monkeypatch):
    falso = Falso()
    monkeypatch.setattr(importacion, "_get", falso)
    return falso


@pytest.fixture
def inv(client):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    client.uid = uid
    return client


# --- Detección ---------------------------------------------------------------------------------

@pytest.mark.parametrize("texto,esperado", [
    ("10.1090/S0002-9947-1965-0170805-7", ("doi", "10.1090/s0002-9947-1965-0170805-7")),
    ("https://doi.org/10.1090/ABC", ("doi", "10.1090/abc")),
    ("2401.01234", ("arxiv", "2401.01234")),
    ("https://arxiv.org/abs/2401.01234v3", ("arxiv", "2401.01234")),
    ("10.48550/arXiv.2401.01234", ("arxiv", "2401.01234")),  # DOI de arXiv → arXiv
])
def test_detectar(texto, esperado):
    assert importacion.detectar(texto) == esperado


def test_detectar_invalido():
    with pytest.raises(importacion.ErrorImportacion, match="No reconozco"):
        importacion.detectar("cualquier cosa")


# --- Crossref ------------------------------------------------------------------------------------

def test_crossref(app, red):
    r = importacion.importar("https://doi.org/10.1090/X")
    d = r["datos"]
    assert d["titulo"] == "On the computational complexity of algorithms"
    assert (d["anio"], d["volumen"], d["paginas"], d["doi"]) == (1965, "117", "285–306", "10.1090/x")
    assert d["medio"] == "Transactions of the American Mathematical Society"
    assert d["resumen"] == "We study time & space."
    assert d["tipo_id"] == productos.tipos()[0]["id"] and d["revision"] == "arbitrado"
    assert [a["apellidos"] for a in r["autores"]] == ["Hartmanis", "Noether", "Stearns"]
    assert r["autores"][1]["orcid"] == "0000-0002-1825-0097"
    assert any("indexada" in a for a in r["avisos"])


def test_crossref_no_encontrado(app, red):
    red.estado = 404
    with pytest.raises(importacion.ErrorImportacion, match="Crossref no tiene registro"):
        importacion.importar("10.1090/no-existe")


def test_error_de_red(app, monkeypatch):
    def caido(*a, **k):
        raise httpx2.ConnectError("sin red")
    monkeypatch.setattr(importacion.httpx2, "get", caido)
    with pytest.raises(importacion.ErrorImportacion, match="No se pudo conectar"):
        importacion.importar("10.1090/x")


# --- arXiv -------------------------------------------------------------------------------------------

def test_arxiv(app, red):
    r = importacion.importar("arXiv:2401.01234v2")
    d = r["datos"]
    assert d["titulo"] == "Primary ideals in Noetherian rings"
    assert d["resumen"] == "We prove that every ideal $I$ has a primary decomposition."
    assert (d["anio"], d["arxiv_id"], d["medio"]) == (2024, "2401.01234", "arXiv [math.AC]")
    assert productos.tipo(d["tipo_id"])["nombre"] == "Preprint"
    assert r["autores"][1] == {"nombres": "Bartel Leendert", "apellidos": "van der Waerden",
                               "orcid": None, "afiliacion": "Leipzig"}
    assert r["doi_publicado"] == "10.1000/publicado.1" and "versión publicada" in r["avisos"][0]


def test_arxiv_no_encontrado(app, red):
    red.arxiv = ARXIV_VACIO
    with pytest.raises(importacion.ErrorImportacion, match="arXiv no tiene"):
        importacion.importar("2401.99999")


def test_version_publicada_conserva_el_arxiv(app, red):
    r = importacion.importar("10.1000/publicado.1", arxiv_asociado="2401.01234")
    assert r["datos"]["doi"] == "10.1000/publicado.1" and r["datos"]["arxiv_id"] == "2401.01234"


# --- Autores ---------------------------------------------------------------------------------------------

def test_resolver_autores(app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    ramirez = usuarios.crear("r@test.cl", "Ana", "Ramírez Soto", "x" * 12)
    stearns = personas.crear_externo("R. E.", "Stearns", None, None, emmy)
    refs, resumen = importacion.resolver_autores([
        {"nombres": "E.", "apellidos": "Noether", "orcid": None, "afiliacion": None},       # por nombre
        {"nombres": "Ana", "apellidos": "Ramirez", "orcid": None, "afiliacion": None},      # 1er apellido, sin tilde
        {"nombres": "R. E.", "apellidos": "Stearns", "orcid": None, "afiliacion": None},   # externo existente
        {"nombres": "Juris", "apellidos": "Hartmanis", "orcid": None, "afiliacion": "GE"},  # nuevo
        {"nombres": "Max", "apellidos": "Noether", "orcid": None, "afiliacion": None},     # otra inicial
    ])
    assert refs[:3] == [f"i:{emmy}", f"i:{ramirez['id']}", f"e:{stearns['id']}"]
    assert refs[3].startswith("n:") and refs[4].startswith("n:")
    assert resumen["nuevos"] == ["Juris Hartmanis", "Max Noether"]
    assert get_db().q("SELECT COUNT(*) n FROM persona_externa")[0]["n"] == 1  # nada creado aún


def test_orcid_tiene_prioridad_sobre_el_nombre(app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    get_db().execute("UPDATE investigador SET orcid = '0000-0002-1825-0097' WHERE usuario_id = ?", [emmy])
    refs, _ = importacion.resolver_autores([{"nombres": "A. E.", "apellidos": "Nöther",
                                             "orcid": "0000-0002-1825-0097", "afiliacion": None}])
    assert refs == [f"i:{emmy}"]


def test_materializar(app):
    r = personas.ref_nueva("Juris", "Hartmanis", "Cornell")
    assert personas.por_ref(r)["nueva"] and personas.por_ref(r)["afiliacion"] == "Cornell"
    e1 = personas.materializar(r, 1)
    e2 = personas.materializar(personas.ref_nueva("juris", "HARTMANIS", None), 1)  # reutiliza
    assert e1 == e2 and e1.startswith("e:")
    assert personas.materializar("i:5", 1) == "i:5" and personas.por_ref("n:basura") is None


# --- Rutas ----------------------------------------------------------------------------------------------

def test_importar_prellena_el_formulario(inv, red):
    r = inv.post("/productos/importar", headers=HX, data={"identificador": "10.1090/x"})
    assert "Datos importados de Crossref" in r.text
    assert 'value="On the computational complexity of algorithms"' in r.text
    assert 'value="285–306"' in r.text and "Externos nuevos" in r.text
    assert "Del instituto: Emmy Noether" in r.text  # reconoce a la investigadora por el nombre
    assert r.text.count('name="autor"') == 3


def test_importar_error_solo_actualiza_la_caja(inv, red):
    r = inv.post("/productos/importar", headers=HX, data={"identificador": "nada"})
    assert r.headers["hx-retarget"] == "#caja-importar" and "No reconozco" in r.text
    assert red.llamadas == []  # ni siquiera consulta si el identificador no es válido


def test_importar_producto_existente_ofrece_sumarse(inv, red):
    tipo = str(productos.tipos()[0]["id"])
    inv.post("/productos", headers=HX, data=dict(tipo_id=tipo, titulo="Ya está", anio="1965",
                                                 estado_publicacion="publicado", revision="arbitrado",
                                                 doi="10.1090/x", autor=[f"i:{inv.uid}"]))
    r = inv.post("/productos/importar", headers=HX, data={"identificador": "https://doi.org/10.1090/X"})
    assert r.headers["hx-retarget"] == "#caja-importar" and "ya está registrado" in r.text


def test_cancelar_no_deja_externos_y_guardar_los_registra(inv, red):
    r = inv.post("/productos/importar", headers=HX, data={"identificador": "10.1090/x"})
    refs = re.findall(r'name="autor" value="([^"]+)"', r.text)
    assert get_db().q("SELECT COUNT(*) n FROM persona_externa")[0]["n"] == 0  # «cancelar»
    tipo = str(productos.tipos()[0]["id"])
    inv.post("/productos", headers=HX, data=dict(
        tipo_id=tipo, titulo="On the computational complexity of algorithms", anio="1965",
        estado_publicacion="publicado", revision="arbitrado", doi="10.1090/x", autor=refs))
    p = productos.existente("10.1090/x", None)
    assert [a["apellidos"] for a in p["autores"]] == ["Hartmanis", "Noether", "Stearns"]
    assert get_db().q("SELECT COUNT(*) n FROM persona_externa")[0]["n"] == 2


def test_aviso_si_el_usuario_no_esta_entre_los_autores(client, red):
    usuarios.crear("sofia@test.cl", "Sofía", "Kovalévskaya", "Clave-colega-1", debe_cambiar_pass=False)
    login(client, "sofia@test.cl", "Clave-colega-1")
    r = client.post("/productos/importar", headers=HX, data={"identificador": "10.1090/x"})
    assert "no aparece entre los autores" in r.text


def test_arxiv_limitado_reintenta_una_vez(app, red, monkeypatch):
    monkeypatch.setattr(importacion, "ARXIV_ESPERA", 0)
    respuestas = iter([406, 200])
    original = red.__call__

    def a_veces_limitado(url, params=None):
        r = original(url, params)
        return httpx2.Response(next(respuestas), content=r.content)
    monkeypatch.setattr(importacion, "_get", a_veces_limitado)
    assert importacion.importar("2401.01234")["datos"]["arxiv_id"] == "2401.01234"


def test_arxiv_limitado_persistente(app, red, monkeypatch):
    monkeypatch.setattr(importacion, "ARXIV_ESPERA", 0)
    red.estado = 429
    with pytest.raises(importacion.ErrorImportacion, match="limitando"):
        importacion.importar("2401.01234")
    assert len(red.llamadas) == 2
