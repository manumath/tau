"""Informes de docencia: carga docente por semestre e indicadores del cuerpo académico (PLAN.md §29)."""
import io

import openpyxl
import pytest

from app.academico import gestiones, oferta
from app.acreditacion import cuerpo_academico as ca
from app.comun import academicos, permisos, unidades, usuarios, vinculos
from app.investigacion import carga_proyectos, proyectos
from tests.conftest import HX, PASS_TEMP, login
from tests.test_vinculos import hoy  # noqa: F401


def _carga(horas, **acts):
    return {"horas": horas, "detalles": {}, "actividades": {k: acts.get(k, 0) for k in vinculos.ACTIVIDADES}}


@pytest.fixture
def datos(app, hoy):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP)["id"]
    vinculos.agregar(emmy, "titular", "2015-01-01", carga=_carga(160, docencia=64, investigacion=64, gestion=32))
    vinculos.agregar(alan, "contratado", "2026-08-01", "2026-12-31", carga=_carga(64, docencia=64))
    academicos.agregar_grado(emmy, {"nivel": "doctorado", "anio": 2005})
    academicos.agregar_grado(alan, {"nivel": "maestria", "anio": 2027 - 1})
    academicos.fijar_fecha_nacimiento(emmy, "1980-05-10")
    por = {g["tipo"]: g for g in gestiones.crear_anio(2026)}
    for sigla, inscritos, quien in (("MAT-111", "40", emmy), ("MAT-112", "30", emmy), ("MAT-113", "", alan)):
        oid, _ = oferta.agregar(por["II"]["id"], sigla, "A", inscritos, 1)
        oferta.asignar(oid, quien, "titular")
    oferta.agregar(por["II"]["id"], "MAT-114", "A", "10", 1)  # sin docente
    pid = proyectos.crear(dict(nombre="Anillos", estado="vigente", fecha_inicio="2026-01-01",
                               fecha_fin="2026-12-31"), emmy, emmy, tipo="institucional", clase="investigacion")
    part = next(x["participante_id"] for x in proyectos.participantes(pid) if x["id"] == emmy)
    carga_proyectos.asignar(pid, part, 32, emmy)
    return {"emmy": emmy, "alan": alan, "II": por["II"]}


def test_carga_docente_del_semestre(datos):
    d = ca.carga_docente(datos["II"])
    fila = {f["nombre"]: f for f in d["filas"]}
    emmy, alan = fila["Noether, Emmy"], fila["Turing, Alan"]
    assert (emmy["contratada"], emmy["jce"], emmy["asignada"], emmy["investigacion"], emmy["inv_proyectos"]) == \
        (160, 1.0, 64, 64, 32)
    assert alan["avisos"] and alan["asignada"] == 32  # prevé 64 de docencia y dicta una materia
    t = d["total"]
    assert (t["personas"], t["horas"], t["jce"], t["pct_investigacion"]) == (2, 224, 1.4, 28.6)
    assert d["por_categoria"]["Titular"]["jce"] == 1.0
    assert d["inscripciones"] == {"paralelos": 4, "inscritos": 80, "sin_dato": 1, "sin_docente": 1}
    assert d["inscripciones_por_jce"] == 57.1
    hojas = ca.filas_xlsx(d)
    assert set(hojas) == {"Resumen", "Por persona", "Por categoría"} and len(hojas["Por persona"]) == 2


def test_indicadores_del_cuerpo_academico(datos):
    x = ca.indicadores_anio(2026)
    assert (x["total"], x["jce"], x["doctores"], x["pct_doctores"], x["pct_posgrado"]) == (2, 1.4, 1, 50.0, 100.0)
    assert x["tramos"]["40 a 49 años"] == 1 and x["tramos"]["Sin dato"] == 1  # nunca la fecha
    assert x["pct_investigacion"] == 28.6 and x["con_proyecto"] == 1 and x["semestre"] == "II-2026"
    assert x["inscripciones_por_jce"] == 57.1
    x2025 = ca.indicadores_anio(2025)
    assert (x2025["total"], x2025["pct_posgrado"]) == (1, 100.0)  # Alan aún no estaba; su maestría es de 2026
    serie = ca.indicadores(2024, 2026)
    assert [s["anio"] for s in serie] == [2024, 2025, 2026]
    assert set(ca.filas_indicadores(serie)) == {"Indicadores", "Por categoría", "Por tramo de edad"}


def test_pantallas_y_permisos(client, datos):
    usuarios.cambiar_password(datos["emmy"], PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/informes/carga-docente").status_code == 403
    assert client.get("/informes/cuerpo-academico").status_code == 403
    assert "Carga docente" not in client.get("/informes").text
    permisos.asignar(datos["emmy"], "comite_acreditacion", unidades.id_de("UMSA"))
    r = client.get("/informes")
    assert "Carga docente" in r.text and "Cuerpo académico" in r.text
    r = client.get(f"/informes/carga-docente?gestion={datos['II']['id']}")
    assert "Carga docente II-2026" in r.text and "Noether, Emmy" in r.text and "57.1" in r.text
    assert "1980" not in client.get("/informes/cuerpo-academico?desde=2024&hasta=2026").text
    for url in (f"/informes/carga-docente/xlsx?gestion={datos['II']['id']}",
                "/informes/cuerpo-academico/xlsx?desde=2024&hasta=2026"):
        r = client.get(url)
        assert r.status_code == 200
        libro = openpyxl.load_workbook(io.BytesIO(r.content))
        assert len(libro.sheetnames) == 3
    assert client.get(f"/docencia/carga?gestion={datos['II']['id']}", headers=HX).status_code == 200
