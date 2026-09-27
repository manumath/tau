"""Filiación y pertenencia, etapa E2 (filiación IIMAT/UMSA) y contexto boliviano."""
import os

import pytest

from app.investigacion import filiacion, importacion, productos, proyectos
from app.comun import personas, usuarios, vinculos
from app.acreditacion import informes
from app.comun.db import get_db
from app.comun.rutas.admin_usuarios import fecha_local
from tests.conftest import HX, PASS_TEMP, login


@pytest.fixture
def emmy(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    vinculos.agregar(uid, "titular", "2015-01-01")
    return uid


def _tipo():
    return str(get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Artículo en revista'")[0]["id"])


def _datos(titulo="Anillos", anio="2026", mes="4", **extra):
    return dict(tipo_id=_tipo(), titulo=titulo, anio=anio, mes=mes, estado_publicacion="publicado",
                revision="arbitrado", **extra)


def _producto(autores, filiaciones, titulo="Anillos", anio=2026, mes=4):
    d, errores = productos.preparar(_datos(titulo, str(anio), str(mes or "")), autores, [])
    assert not errores
    return productos.guardar(d, autores, int(autores[0][2:]), filiaciones=filiaciones)


# --- Detección --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("texto,esperado", [
    ("Instituto de Investigación Matemática, UMSA, La Paz, Bolivia", True),
    ("Universidad Mayor de San Andres", True),                          # sin tilde
    ("Carrera de Matemática, Facultad de Ciencias Puras y Naturales", True),
    ("IIMAT", True),
    ("Dept. of Mathematics, Uppsala University; FCPN-UMSA", True),     # doble filiación
    ("Universidad de Chile", False),
    ("Consumsa Ltda.", False),                                          # la sigla, como palabra
    ("", False), (None, False),
])
def test_detecta(texto, esperado):
    assert filiacion.detecta(texto) is esperado


# --- Formulario ------------------------------------------------------------------------------------------------

def test_formulario_guarda_la_filiacion_por_autor(client, emmy):
    weyl = personas.crear_externo("Hermann", "Weyl", "IAS", None, emmy)["id"]
    login(client, "inv@test.cl", PASS_TEMP)
    client.post("/productos", headers=HX, data={**_datos(), "autor": [f"i:{emmy}", f"e:{weyl}"],
                                                "filiacion": ["1", ""]})
    pid = get_db().q("SELECT id FROM producto")[0]["id"]
    assert [a["filiacion"] for a in productos.obtener(pid)["autores"]] == [1, None]
    r = client.get(f"/productos/{pid}/editar", headers=HX)
    assert '<option value="1" selected>Firmó con IIMAT/UMSA</option>' in r.text
    assert r.text.count('name="filiacion"') == 2  # el externo lleva un campo oculto (listas paralelas)
    # Si el formulario vuelve con errores, conserva lo elegido.
    r = client.put(f"/productos/{pid}", headers=HX, data={**_datos(titulo=""), "autor": [f"i:{emmy}"],
                                                          "filiacion": ["0"]})
    assert '<option value="0" selected>' in r.text


def test_importar_marca_la_filiacion_segun_la_afiliacion(emmy):
    autores = [{"nombres": "Emmy", "apellidos": "Noether", "orcid": None,
                "afiliacion": "IIMAT, Universidad Mayor de San Andrés"},
               {"nombres": "Juris", "apellidos": "Hartmanis", "orcid": None, "afiliacion": "UMSA"}]
    refs, resumen = importacion.resolver_autores(autores)
    # Solo se marca a los autores del instituto (el externo no lleva filiación).
    assert resumen["filiacion"] == {f"i:{emmy}": "1"}
    _, resumen = importacion.resolver_autores([{**autores[0], "afiliacion": "Universität Göttingen"}])
    assert resumen["filiacion"] == {}


# --- Declaración desde la lista ------------------------------------------------------------------------------

def test_declarar_desde_la_lista(client, emmy):
    pendiente = _producto([f"i:{emmy}"], [None], "Pendiente")
    _producto([f"i:{emmy}"], [None], "Otro pendiente")
    _producto([f"i:{emmy}"], [1], "Declarado")
    assert filiacion.pendientes(emmy) == 2
    login(client, "inv@test.cl", PASS_TEMP)
    assert "2 sin filiación declarada" in client.get("/").text
    r = client.get("/productos/lista?sin_filiacion=1", headers=HX)
    assert "Pendiente" in r.text and "Declarado" not in r.text and "¿Firmó con IIMAT/UMSA?" in r.text
    r = client.post(f"/productos/{pendiente}/filiacion", headers=HX, data={"valor": "0"})
    assert f'id="producto-{pendiente}"' in r.text and "¿Firmó con IIMAT/UMSA?" not in r.text
    assert filiacion.pendientes(emmy) == 1
    client.post("/productos/filiacion/todos", headers=HX, data={})
    assert filiacion.pendientes(emmy) == 0
    assert productos.obtener(pendiente)["autores"][0]["filiacion"] == 0  # «todos» no toca lo ya declarado


def test_solo_el_autor_declara_su_filiacion(client, emmy):
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", "Clave-colega-1", debe_cambiar_pass=False)["id"]
    pid = _producto([f"i:{alan}"], [None])
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.post(f"/productos/{pid}/filiacion", headers=HX, data={"valor": "1"}).status_code == 403


# --- Informes ------------------------------------------------------------------------------------------------------

def test_memoria_exige_filiacion(emmy):
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP, categoria="contratado",
                          fecha_ingreso="2020-01-01")["id"]
    _producto([f"i:{emmy}"], [1], "Con filiación")
    _producto([f"i:{emmy}"], [0], "Sin filiación")
    _producto([f"i:{emmy}"], [None], "Sin declarar")
    _producto([f"i:{emmy}", f"i:{alan}"], [0, 1], "Solo Alan firmó con UMSA")
    m = informes.memoria(2026)
    assert {p["titulo"] for p in m["productos"]} == {"Con filiación", "Solo Alan firmó con UMSA"}
    assert [(p["titulo"], p["motivo"]) for p in m["por_confirmar"]] == [("Sin declarar", "filiación sin declarar")]
    por_inv = {x["apellidos"]: x["productos"] for x in m["por_investigador"]}
    assert por_inv == {"Noether": 1, "Turing": 1}  # el mixto cuenta para Alan, no para Emmy


def test_cv_con_filtro_de_filiacion(client, emmy):
    _producto([f"i:{emmy}"], [1], "Con filiación")
    _producto([f"i:{emmy}"], [0], "Previo, en otra institución", anio=2014)
    assert {p["titulo"] for g in informes.cv(emmy, 2010, 2026)["grupos"].values() for p in g} == {
        "Con filiación", "Previo, en otra institución"}
    solo = informes.cv(emmy, 2010, 2026, solo_filiacion=True)
    assert {p["titulo"] for g in solo["grupos"].values() for p in g} == {"Con filiación"}
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/informes/cv?desde=2010&hasta=2026&filiacion=1")
    assert "Previo, en otra institución" not in r.text and "filiacion=1" in r.text


# --- Contexto boliviano -------------------------------------------------------------------------------------------

def test_contexto_bolivia(client, emmy):
    assert os.environ["TZ"] == "America/La_Paz"
    assert fecha_local("2026-09-25 12:00:00") == "25-09-2026 08:00"  # UTC-4
    pid = proyectos.crear(dict(nombre="Proyecto IDH", estado="vigente", monto=150000), emmy, emmy)
    assert proyectos.obtener(pid)["moneda"] == "BOB"
    login(client, "inv@test.cl", PASS_TEMP)
    assert "Bs 150.000" in client.get(f"/proyectos/{pid}").text
