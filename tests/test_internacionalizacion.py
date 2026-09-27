"""Internacionalización (IAC-CINDA 3.5.2 c y 3.6.3 h): país de coautores externos y ámbito de los
proyectos."""
import pytest

from app.acreditacion import anexo as acreditacion
from app import importacion, openalex, paises, personas, productos, proyectos, revistas, usuarios, vinculos
from app.db import get_db
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login


@pytest.mark.parametrize("texto,esperado", [("USA", "Estados Unidos"), ("EE. UU.", "Estados Unidos"),
                                            ("united kingdom", "Reino Unido"), ("Peru", "Perú"), ("Bolivia", "Bolivia"),
                                            ("Narnia", "Narnia"), ("", None), (None, None)])
def test_normalizar(texto, esperado):
    assert paises.normalizar(texto) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("Mathematical Institute, University of Oxford, Oxford, UK", "Reino Unido"),
    ("Universidad de Chile", "Chile"),
    ("New Mexico State University, Las Cruces, NM, USA", "Estados Unidos"),  # el último tramo manda
    ("Carrera de Matemática, UMSA, La Paz, Bolivia", "Bolivia"),
    ("Indiana University", None),                                           # «India» no es «Indiana»
    ("IAS Princeton", None), (None, None)])
def test_desde_texto(texto, esperado):
    assert paises.desde_texto(texto) == esperado


def test_por_codigo():
    assert (paises.por_codigo("br"), paises.por_codigo("GB"), paises.por_codigo("XX")) == ("Brasil", "Reino Unido", None)


@pytest.fixture
def emmy(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    vinculos.agregar(uid, "titular", "2015-01-01")
    return uid


def test_pais_al_crear_e_importar(emmy):
    assert personas.crear_externo("Ana", "Uno", "Universidad de Chile", None, emmy)["pais"] == "Chile"
    assert personas.crear_externo("Bea", "Dos", None, "U.S.A.", emmy)["pais"] == "Estados Unidos"
    # Referencia provisional de una importación: el país viaja y se guarda al registrar.
    ref = importacion.resolver_autores([{"nombres": "Ben", "apellidos": "Green", "orcid": None,
                                         "afiliacion": "Mathematical Institute, University of Oxford, Oxford, UK"}])[0][0]
    e = personas.materializar(ref, emmy)
    assert get_db().q("SELECT pais FROM persona_externa WHERE id = ?", [int(e[2:])])[0]["pais"] == "Reino Unido"
    # Un externo ya registrado sin país lo recibe de una importación posterior (sin sobrescribir).
    sin = personas.crear_externo("Juris", "Hartmanis", None, None, emmy)
    importacion.resolver_autores([{"nombres": "Juris", "apellidos": "Hartmanis", "orcid": None,
                                   "afiliacion": "Cornell University, Ithaca, NY, USA"}])
    assert get_db().q("SELECT pais FROM persona_externa WHERE id = ?", [sin["id"]])[0]["pais"] == "Estados Unidos"


def test_pais_desde_openalex():
    obra = {"id": "https://openalex.org/W1", "title": "T", "publication_year": 2024, "type": "article",
            "authorships": [{"author": {"display_name": "Ana Souza"}, "countries": ["BR"], "institutions": [],
                             "raw_affiliation_strings": []}]}
    assert openalex.convertir(obra)["autores"][0]["pais"] == "Brasil"


def test_pagina_de_coautores_externos(client, emmy):
    sin = get_db().t.persona_externa.insert(nombres="Ana", apellidos="Uno", institucion="Universidad de Chile")
    raro = get_db().t.persona_externa.insert(nombres="Bea", apellidos="Dos", pais="EE. UU.")
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/personas/externos")
    assert "Uno" in r.text and "Dos" not in r.text and "1 persona(s) sin país" in r.text
    assert client.post("/personas/externos/completar", headers=HX).headers.get("hx-refresh") == "true"
    assert get_db().q("SELECT pais FROM persona_externa WHERE id = ?", [sin["id"]])[0]["pais"] == "Chile"
    assert get_db().q("SELECT pais FROM persona_externa WHERE id = ?", [raro["id"]])[0]["pais"] == "Estados Unidos"
    r = client.put(f"/personas/externos/{sin['id']}", headers=HX, data={"institucion": "UChile", "pais": "peru"})
    assert f'id="externo-{sin["id"]}"' in r.text
    assert get_db().q("SELECT institucion, pais FROM persona_externa WHERE id = ?", [sin["id"]])[0] == {
        "institucion": "UChile", "pais": "Perú"}


def test_ambito_y_contrapartes(client, emmy):
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.post("/proyectos", headers=HX, data={"nombre": "Colaboración andina", "estado": "vigente", "ambito": ""})
    pid = int(r.headers["hx-redirect"].rsplit("/", 1)[1])
    p = proyectos.obtener(pid)
    assert p["ambito"] is None and proyectos.ambito_efectivo(p) is None
    client.post(f"/proyectos/{pid}/contrapartes", headers=HX, data={"institucion": "Universidad Mayor de San Simón",
                                                                     "pais": "Bolivia"})
    assert proyectos.ambito_efectivo(proyectos.obtener(pid)) == "nacional"
    r = client.post(f"/proyectos/{pid}/contrapartes", headers=HX, data={"institucion": "Universidad de Chile"})
    assert "Universidad de Chile" in r.text and "Internacional (según sus contrapartes)" in r.text
    assert proyectos.contrapartes(pid)[1]["pais"] == "Chile"  # deducido del nombre
    # El ámbito declarado manda sobre las contrapartes.
    client.put(f"/proyectos/{pid}/datos", headers=HX, data={"nombre": "Colaboración andina", "estado": "vigente",
                                                            "ambito": "nacional"})
    assert proyectos.ambito_efectivo(proyectos.obtener(pid)) == "nacional"
    cid = proyectos.contrapartes(pid)[0]["id"]
    client.delete(f"/proyectos/{pid}/contrapartes/{cid}", headers=HX)
    assert len(proyectos.contrapartes(pid)) == 1


def test_anexo_internacionalizacion(client, emmy):
    admin = usuarios.por_email("admin@test.cl")["id"]
    rid = revistas.crear({"titulo": "Revista X", "pais": "Bolivia", "arbitrada": 1}, admin, verificada=True)
    chile = personas.crear_externo("Ana", "Uno", "Universidad de Chile", None, emmy)["id"]
    brasil = personas.crear_externo("Bea", "Dos", None, "Brasil", emmy)["id"]
    local = personas.crear_externo("Carla", "Tres", "UMSA", "Bolivia", emmy)["id"]
    sin = personas.crear_externo("Dora", "Cuatro", None, None, emmy)["id"]
    tipo = str(get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Artículo en revista'")[0]["id"])
    for titulo, coautores in (("Con Chile y Brasil", [chile, brasil]), ("Con Chile", [chile]), ("Local", [local]),
                              ("Sin país", [sin]), ("Solo del instituto", [])):
        autores = [f"i:{emmy}", *[f"e:{x}" for x in coautores]]
        d, _ = productos.preparar(dict(tipo_id=tipo, titulo=titulo, anio="2024", estado_publicacion="publicado",
                                       revision="arbitrado", revista_id=str(rid)), autores, [])
        productos.guardar(d, autores, emmy, filiaciones=[1] + [None] * len(coautores))
    pid = proyectos.crear(dict(nombre="Proyecto con Suecia", estado="vigente", fecha_inicio="2024-01-01",
                               fecha_fin="2025-12-31"), emmy, emmy)
    proyectos.agregar_contraparte(pid, "Uppsala University", "Sweden")

    a = acreditacion.anexo(2022, 2026)
    c = a["coautoria"]
    assert (c["internacionales"], c["con_externos"], c["con_pais"]) == (2, 4, 3)
    assert c["por_pais"] == {"Chile": 2, "Brasil": 1}
    anio = {x["anio"]: x for x in a["anios"]}
    assert (anio[2024]["coautoria_internacional"], anio[2024]["proyectos_internacionales"]) == (2, 1)
    login(client, "admin@test.cl", PASS_ADMIN)
    r = client.get("/informes/acreditacion?desde=2022&hasta=2026")
    assert "Cobertura incompleta" in r.text and "Proyecto con Suecia" in r.text and "Uppsala University (Suecia)" in r.text
    assert "Ámbito nacional o internacional de los proyectos" not in r.text  # ya no figura como pendiente
