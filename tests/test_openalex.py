"""Carga de la producción desde OpenAlex (punto 5) y citas. La red se simula: `openalex._get`
responde con obras fijas."""
import base64
import json

import httpx2
import pytest

from app import cosecha, informes, openalex, perfiles, productos, revistas, usuarios, vinculos
from app.db import get_db
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login

ORCID = "0000-0002-1825-0097"


def _autor(nombre, orcid=None, afiliacion=None):
    return {"author": {"display_name": nombre, "orcid": f"https://orcid.org/{orcid}" if orcid else None},
            "raw_author_name": nombre, "raw_affiliation_strings": [afiliacion] if afiliacion else [],
            "institutions": []}


def _obra(n, titulo, tipo="article", fuente=None, autores=None, fecha="2024-05-10", doi=None, citas=3, **extra):
    return {"id": f"https://openalex.org/W{n}", "doi": f"https://doi.org/{doi}" if doi else None, "title": titulo,
            "publication_year": int(fecha[:4]), "publication_date": fecha, "type": tipo,
            "primary_location": {"source": fuente} if fuente else None, "locations": extra.pop("locations", []),
            "authorships": autores or [_autor("Emmy Noether", ORCID, "IIMAT, Universidad Mayor de San Andrés")],
            "cited_by_count": citas, "open_access": {"is_oa": True}, "biblio": {"volume": "7", "issue": "2",
                                                                                 "first_page": "10", "last_page": "20"},
            "abstract_inverted_index": {"Probamos": [0], "que": [1], "sí.": [2]}, **extra}


JSL = {"display_name": "Journal of Symbolic Logic", "issn_l": "0022-4812", "issn": ["0022-4812", "1943-5886"],
       "type": "journal"}
OBRAS = [
    _obra(1, "Tipos y anillos", fuente=JSL, doi="10.5555/uno",
          autores=[_autor("Emmy Noether", ORCID, "IIMAT, Universidad Mayor de San Andrés"),
                   _autor("Hermann Weyl", None, "IAS Princeton")]),
    _obra(2, "Un preprint", tipo="preprint", fuente={"display_name": "arXiv (Cornell University)", "type": "repository"},
          locations=[{"landing_page_url": "https://arxiv.org/abs/2401.01234v2"}], fecha="2025-01-01"),
    _obra(3, "Mi tesis doctoral", tipo="dissertation"),
    _obra(4, "Ya registrado", fuente=JSL, doi="10.5555/existe"),
    _obra(5, "En revista nueva", fuente={"display_name": "Revista Andina", "issn": ["0028-0836"], "type": "journal"}),
    _obra(6, "De otra persona", fuente=JSL, autores=[_autor("Juana Pérez", "0000-0001-0000-0000")]),
]


class Falso:
    def __init__(self, obras=OBRAS, total=None, estado=200):
        self.obras, self.total, self.estado, self.llamadas = obras, total, estado, []

    def __call__(self, url, params=None):
        self.llamadas.append((url, params))
        filtro = (params or {}).get("filter", "")
        if filtro.startswith("doi:"):
            dois = filtro[4:].split("|")
            res = [{"id": f"https://openalex.org/W9{i}", "doi": f"https://doi.org/{d}", "cited_by_count": 40 + i}
                   for i, d in enumerate(dois)]
        else:
            res = self.obras
        return httpx2.Response(self.estado, content=json.dumps({"results": res, "meta": {
            "count": self.total or len(res)}}).encode(), headers={"content-type": "application/json"})


@pytest.fixture
def red(monkeypatch):
    falso = Falso()
    monkeypatch.setattr(openalex, "_get", falso)
    return falso


@pytest.fixture
def emmy(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    perfiles.actualizar_campos(uid, orcid=ORCID)
    vinculos.agregar(uid, "titular", "2010-01-01")
    admin = usuarios.por_email("admin@test.cl")["id"]
    rid = revistas.crear({"titulo": "Journal of Symbolic Logic", "issn": "0022-4812", "pais": "Estados Unidos"},
                         admin, verificada=True)
    revistas.agregar_indexacion(rid, {"indice_id": get_db().q("SELECT id FROM indice WHERE nombre = 'Scopus'")[0]["id"],
                                      "desde": "2000"}, admin)
    tipo = str(get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Artículo en revista'")[0]["id"])
    d, _ = productos.preparar(dict(tipo_id=tipo, titulo="Ya registrado", anio="2024", estado_publicacion="publicado",
                                   revision="arbitrado", doi="10.5555/existe"), [f"i:{uid}"], [])
    productos.guardar(d, [f"i:{uid}"], uid)
    return uid


# --- Conversión ----------------------------------------------------------------------------------------

def test_convertir():
    c = openalex.convertir(OBRAS[0])
    assert (c["openalex_id"], c["tipo"], c["citas"], c["issns"]) == ("W1", "Artículo en revista", 3,
                                                                    ["0022-4812", "1943-5886"])
    d = c["datos"]
    assert (d["titulo"], d["anio"], d["mes"], d["paginas"], d["doi"], d["medio"]) == (
        "Tipos y anillos", 2024, 5, "10–20", "10.5555/uno", "Journal of Symbolic Logic")
    assert d["resumen"] == "Probamos que sí."
    assert c["autores"][1] == {"nombres": "Hermann", "apellidos": "Weyl", "orcid": None, "afiliacion": "IAS Princeton"}
    p = openalex.convertir(OBRAS[1])
    assert (p["tipo"], p["datos"]["arxiv_id"], p["datos"]["medio"], p["datos"]["mes"]) == ("Preprint", "2401.01234",
                                                                                          "arXiv", None)
    assert openalex.convertir(OBRAS[2])["tipo"] is None and "tesis" in openalex.convertir(OBRAS[2])["motivo"]


@pytest.mark.parametrize("tipo,fuente,esperado", [
    ("article", "journal", "Artículo en revista"), ("article", "conference", "Artículo en actas de congreso"),
    ("article", "repository", "Preprint"), ("book", None, "Libro"), ("book-chapter", None, "Capítulo de libro"),
    ("report", None, "Reporte de investigación"), ("dataset", None, None)])
def test_tipo_portal(tipo, fuente, esperado):
    w = {"type": tipo, "primary_location": {"source": {"type": fuente}} if fuente else None}
    assert openalex.tipo_portal(w)[0] == esperado


# --- Búsqueda y registro ----------------------------------------------------------------------------------

def test_candidatos(emmy, red):
    res = cosecha.candidatos(emmy, 2021, 2026)
    estados = {c["openalex_id"]: c["estado"] for c in res["lista"]}
    assert estados == {"W1": "nueva", "W2": "nueva", "W3": "no_aplica", "W4": "registrada", "W5": "nueva", "W6": "nueva"}
    assert "author.orcid:0000-0002-1825-0097,publication_year:2021-2026" in red.llamadas[0][1]["filter"]


def test_sin_orcid(app, red):
    uid = usuarios.por_email("inv@test.cl")["id"]
    with pytest.raises(Exception, match="Registre su ORCID"):
        cosecha.candidatos(uid, 2021, 2026)


def test_aviso_de_orcid_sospechoso(emmy, monkeypatch):
    monkeypatch.setattr(openalex, "_get", Falso(total=1246))
    avisos = cosecha.candidatos(emmy, 2021, 2026)["avisos"]
    assert any("1246" in a for a in avisos) and any("ORCID de ejemplo" in a for a in avisos)


def test_registrar(emmy, red):
    elegidas = [c for c in cosecha.candidatos(emmy, 2021, 2026)["lista"] if c["estado"] == "nueva"]
    creados, mensajes = cosecha.registrar(emmy, elegidas)
    assert creados == 3 and len(mensajes) == 1 and "De otra persona" in mensajes[0]
    uno = productos.obtener(get_db().q("SELECT id FROM producto WHERE openalex_id = 'W1'")[0]["id"])
    assert (uno["citas"], uno["revision"], uno["clasificacion_catalogo"]) == (3, "indexado", True)  # JSL verificada
    assert [(a["apellidos"], a["interno"], a.get("filiacion")) for a in uno["autores"]] == [
        ("Noether", True, 1), ("Weyl", False, None)]  # filiación detectada en la afiliación publicada
    pre = productos.obtener(get_db().q("SELECT id FROM producto WHERE openalex_id = 'W2'")[0]["id"])
    assert (pre["tipo"], pre["revision"], pre["arxiv_id"]) == ("Preprint", "sin_arbitraje", "2401.01234")
    andina = revistas.por_issn("0028-0836")
    assert andina and andina["estado"] == "pendiente"  # la revista desconocida queda propuesta
    # Una segunda búsqueda las muestra como ya registradas y no las duplica.
    assert cosecha.registrar(emmy, elegidas)[0] == 0
    assert {c["estado"] for c in cosecha.candidatos(emmy, 2021, 2026)["lista"] if c["openalex_id"] in ("W1", "W2", "W5")} \
        == {"registrada"}


def test_descartar_y_restaurar(emmy, red):
    cosecha.descartar(emmy, "W5", "En revista nueva")
    estados = {c["openalex_id"]: c["estado"] for c in cosecha.candidatos(emmy, 2021, 2026)["lista"]}
    assert estados["W5"] == "descartada"
    cosecha.restaurar(emmy, "W5")
    assert {c["openalex_id"]: c["estado"] for c in cosecha.candidatos(emmy, 2021, 2026)["lista"]}["W5"] == "nueva"


def test_rutas(client, emmy, red):
    login(client, "inv@test.cl", PASS_TEMP)
    assert ORCID in client.get("/productos/openalex").text
    r = client.post("/productos/openalex/buscar", headers=HX, data={"desde": "2021", "hasta": "2026"})
    assert "Tipos y anillos" in r.text and "Ya registrada" in r.text and "No se importa" in r.text
    carga = r.text.split('name="carga" value="')[1].split('"')[0]
    nuevas = json.loads(base64.b64decode(carga))
    assert {c["openalex_id"] for c in nuevas} == {"W1", "W2", "W5", "W6"}
    r = client.post("/productos/openalex/registrar", headers=HX, data={"carga": carga, "sel": ["W1"]})
    assert "Se registraron 1 producto(s)" in r.text
    assert get_db().q("SELECT COUNT(*) n FROM producto WHERE openalex_id IS NOT NULL")[0]["n"] == 1
    r = client.post("/productos/openalex/descartar", headers=HX, data={"openalex_id": "W6", "titulo": "De otra persona"})
    assert "Descartada" in r.text
    assert client.post("/productos/openalex/descartar", headers=HX, data={"openalex_id": "x'; DROP"}).status_code == 400


def test_error_de_openalex(emmy, monkeypatch):
    monkeypatch.setattr(openalex, "_get", Falso(estado=429))
    with pytest.raises(Exception, match="limitó las consultas"):
        cosecha.candidatos(emmy, 2021, 2026)


# --- Citas ---------------------------------------------------------------------------------------------------

def test_actualizar_citas_y_memoria(client, emmy, red):
    consultados, actualizados = cosecha.actualizar_citas()
    assert (consultados, actualizados) == (1, 1)
    p = productos.obtener(get_db().q("SELECT id FROM producto WHERE doi = '10.5555/existe'")[0]["id"])
    assert (p["citas"], p["openalex_id"]) == (40, "W90") and p["citas_actualizadas"]
    get_db().execute("UPDATE producto_autor SET filiacion_instituto = 1")
    m = informes.memoria(2024)
    assert (m["impacto"]["citas"], m["impacto"]["con_datos"]) == (40, 1)
    login(client, "admin@test.cl", PASS_ADMIN)
    assert "citas (OpenAlex)" in client.get("/informes/memoria?anio=2024").text
    r = client.post("/informes/citas/actualizar", headers=HX)
    assert r.headers.get("hx-refresh") == "true"
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.post("/informes/citas/actualizar", headers=HX).status_code == 403
