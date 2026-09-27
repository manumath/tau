"""Filiación y pertenencia, etapa E3: agradecimiento al proyecto y requisitos de los fondos."""
import io

import pytest
from openpyxl import load_workbook

from app.investigacion import filiacion, productos, proyectos
from app.comun import usuarios
from app.acreditacion import informes
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login

CLAVE = "Clave-colega-1"


@pytest.fixture
def equipo(client):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", CLAVE, debe_cambiar_pass=False)["id"]
    pid = proyectos.crear(dict(nombre="Proyecto IDH", estado="vigente", fecha_inicio="2026-01-01"), emmy, emmy)
    proyectos.agregar_participante(pid, f"i:{alan}", "co_investigador", False)
    return {"emmy": emmy, "alan": alan, "pid": pid}


def _form(uid, pid, titulo="Invariantes", agradece="", fil="1"):
    tipo = get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Artículo en revista'")[0]["id"]
    return dict(tipo_id=str(tipo), titulo=titulo, anio="2026", estado_publicacion="publicado",
                revision="arbitrado", autor=[f"i:{uid}"], filiacion=[fil], proyecto=[str(pid)],
                agradece=[f"{pid}:{agradece}"])


def _id(titulo):
    return get_db().q("SELECT id FROM producto WHERE titulo = ?", [titulo])[0]["id"]


def test_leer_agradece():
    assert filiacion.leer_agradece(["3:1", "4:0", "5:", "basura"]) == {3: 1, 4: 0, 5: None}


def test_formulario_registra_el_agradecimiento(client, equipo):
    login(client, "alan@test.cl", CLAVE)
    assert 'name="agradece"' in client.get("/productos/nuevo", headers=HX).text
    client.post("/productos", headers=HX, data=_form(equipo["alan"], equipo["pid"], agradece="1"))
    v = proyectos.vinculo("producto", _id("Invariantes"), equipo["pid"])
    assert (v["estado"], v["agradece"]) == ("pendiente", 1)
    # Si el formulario vuelve con errores, conserva lo elegido.
    r = client.post("/productos", headers=HX, data={**_form(equipo["alan"], equipo["pid"], agradece="0"), "titulo": ""})
    assert f'value="{equipo["pid"]}:0" selected' in r.text


def test_responsable_declara_al_aprobar_y_en_la_pestana(client, equipo):
    login(client, "alan@test.cl", CLAVE)
    client.post("/productos", headers=HX, data=_form(equipo["alan"], equipo["pid"]))
    rid = _id("Invariantes")
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    assert "¿La publicación agradece al proyecto?" in client.get(f"/proyectos/{equipo['pid']}/tab/pendientes", headers=HX).text
    client.post(f"/proyectos/{equipo['pid']}/pendientes/producto/{rid}/aprobar", headers=HX, data={"agradece": "1"})
    v = proyectos.vinculo("producto", rid, equipo["pid"])
    assert (v["estado"], v["agradece"]) == ("aprobado", 1)
    r = client.post(f"/proyectos/{equipo['pid']}/producto/{rid}/agradece", headers=HX, data={"agradece": "0"})
    assert "No agradece al proyecto" in r.text and proyectos.vinculo("producto", rid, equipo["pid"])["agradece"] == 0


def test_solo_responsables_marcan_desde_la_pestana(client, equipo):
    login(client, "alan@test.cl", CLAVE)
    client.post("/productos", headers=HX, data=_form(equipo["alan"], equipo["pid"]))
    rid = _id("Invariantes")
    r = client.post(f"/proyectos/{equipo['pid']}/producto/{rid}/agradece", headers=HX, data={"agradece": "1"})
    assert r.status_code == 403


def test_informe_de_proyecto_con_requisitos(client, equipo):
    login(client, "inv@test.cl", PASS_TEMP)  # responsable: vincula directamente
    emmy, pid = equipo["emmy"], equipo["pid"]
    client.post("/productos", headers=HX, data=_form(emmy, pid, "Cumple", agradece="1", fil="1"))
    client.post("/productos", headers=HX, data=_form(emmy, pid, "Sin agradecimiento", agradece="", fil="1"))
    client.post("/productos", headers=HX, data=_form(emmy, pid, "Sin filiación", agradece="1", fil="0"))
    datos = informes.informe_proyecto(pid, 2026, 2026)
    faltan = {x["titulo"]: x["requisitos_faltan"] for x in datos["productos_informe"]}
    assert faltan == {"Cumple": [], "Sin agradecimiento": ["agradecimiento sin declarar"],
                      "Sin filiación": ["sin filiación del instituto"]}
    assert datos["n_cumplen"] == 1
    r = client.get(f"/proyectos/{pid}/informe?desde=2026&hasta=2026")
    assert "1 de 3 lo cumplen" in r.text and "falta: agradecimiento sin declarar" in r.text
    libro = load_workbook(io.BytesIO(client.get(f"/proyectos/{pid}/informe/xlsx?desde=2026&hasta=2026").content))
    encabezados = [c.value for c in libro["Productos"][1]]
    assert "Filiación IIMAT/UMSA" in encabezados and "Agradece al proyecto" in encabezados


def test_estado_de_filiacion_del_producto():
    autores = lambda *v: {"autores": [{"interno": True, "filiacion": x} for x in v] + [{"interno": False}]}  # noqa: E731
    assert filiacion.estado_producto(autores(0, 1)) == 1
    assert filiacion.estado_producto(autores(0, 0)) == 0
    assert filiacion.estado_producto(autores(0, None)) is None
    assert filiacion.estado_producto({"autores": [{"interno": False}]}) is None
