"""Autoevaluación con el marco de calidad (PLAN §57, etapa 5): proceso, juicios por criterio, síntesis, conclusión,
informe, XLSX, indicador «autoevaluación vigente» y permisos."""
import io
from datetime import date

import pytest
from openpyxl import load_workbook

from app.calidad import autoevaluacion as ae
from app.calidad import evidencias, indicadores, marco
from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX, login

CLAVE = "Clave-autoevaluacion-1"
HOY = date.today().year


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def _criterio(codigo):
    return get_db().q("SELECT * FROM criterio_calidad WHERE codigo = ?", [codigo])[0]


def _crear(cliente, nombre="Autoevaluación de prueba"):
    cliente.post("/calidad/autoevaluaciones", headers=HX,
                 data={"nombre": nombre, "desde_anio": str(HOY - 2), "hasta_anio": str(HOY - 1)})
    return ae.en_curso(_marco()["id"])


def _juzgar_todo(aid, uid):
    escala = marco.escala(_marco()["id"])
    for c in evidencias.criterios_del_marco(_marco()["id"]):
        x, _ = ae.validar_juicio({"nivel": str(escala[2]["valor"]), "juicio": "Fundado."}, escala)
        ae.guardar_juicio(aid, c["id"], x, uid)


def test_proceso_completo(carrera):
    a = _crear(carrera)
    assert a and a["desde_anio"] == HOY - 2
    # Solo una en curso.
    r = carrera.post("/calidad/autoevaluaciones", headers=HX,
                     data={"nombre": "Otra", "desde_anio": str(HOY - 1), "hasta_anio": str(HOY - 1)})
    assert "Ya hay una autoevaluación en curso" in r.text
    url = f"/calidad/autoevaluaciones/{a['id']}"
    cid = _criterio("D3.2")["id"]
    p = carrera.get(f"{url}/criterios/{cid}")
    assert p.status_code == 200 and "Deserción de la cohorte" in p.text and "Juicio fundado" in p.text
    # Un nivel sin juicio fundado no se guarda.
    r = carrera.post(f"{url}/criterios/{cid}", headers=HX, data={"nivel": "3"})
    assert "Fundamente el nivel" in r.text and ae.juicios(a["id"]) == {}
    carrera.post(f"{url}/criterios/{cid}", headers=HX,
                 data={"nivel": "2", "juicio": "La deserción supera la meta.", "fortalezas": "Tutoría\n",
                       "debilidades": "- Deserción en primer año\nPoca retención"})
    j = ae.juicios(a["id"])[cid]
    assert (j["nivel"], j["nivel_nombre"], j["debilidades"]) == (2, "Cumple parcialmente",
                                                                 "- Deserción en primer año\nPoca retención")
    # Síntesis y análisis global.
    dim = _criterio("D3.2")["dimension_id"]
    carrera.put(f"{url}/dimensiones/{dim}/sintesis", headers=HX, data={"texto": "Estudiantes: retención por mejorar."})
    carrera.put(f"{url}/analisis", headers=HX, data={"texto": "Balance general."})
    assert ae.sintesis(a["id"])[dim] == "Estudiantes: retención por mejorar."
    # No se concluye con criterios sin juzgar.
    carrera.post(f"{url}/concluir", headers=HX)
    assert ae.obtener(a["id"])["estado"] == "en_curso"
    _juzgar_todo(a["id"], usuarios.por_email("admin@test.cl")["id"])
    carrera.post(f"{url}/concluir", headers=HX)
    assert ae.obtener(a["id"])["estado"] == "concluida"
    # Concluida: los juicios no cambian y no se elimina; un criterio con juicios tampoco se elimina del marco.
    assert carrera.post(f"{url}/criterios/{cid}", headers=HX, data={"nivel": "4", "juicio": "x"}).status_code == 409
    carrera.delete(url, headers=HX)
    assert ae.obtener(a["id"]) is not None
    assert not marco.eliminar_criterio(cid)
    # Informe e indicador «autoevaluación vigente».
    inf = carrera.get(f"{url}/informe")
    assert inf.status_code == 200 and "Informe de autoevaluación" in inf.text and "Balance general." in inf.text
    vig = get_db().q("SELECT * FROM indicador_calidad WHERE fuente = 'auto:autoevaluacion_vigente'")[0]
    assert indicadores.valores_del_anio(_marco()["id"], HOY)[vig["id"]]["valor"] == 1
    assert indicadores.valores_del_anio(_marco()["id"], HOY - 6)[vig["id"]]["valor"] == 0
    # Reabrir.
    carrera.post(f"{url}/reabrir", headers=HX)
    assert ae.obtener(a["id"])["estado"] == "en_curso"
    acciones = {x["accion"] for x in get_db().q("SELECT accion FROM auditoria")}
    assert {"crear_autoevaluacion", "juicio_criterio_calidad", "sintesis_dimension_calidad", "concluir_autoevaluacion",
            "reabrir_autoevaluacion"} <= acciones


def test_xlsx(carrera):
    a = _crear(carrera)
    r = carrera.get(f"/calidad/autoevaluaciones/{a['id']}/xlsx")
    assert r.status_code == 200
    libro = load_workbook(io.BytesIO(r.content))
    assert libro.sheetnames == ["Autoevaluación", "Juicios", "Dimensiones", "Indicadores", "Evidencias", "Escala"]
    assert libro["Juicios"].max_row - 1 == len(evidencias.criterios_del_marco(_marco()["id"]))
    assert {str(HOY - 2), str(HOY - 1)} <= {c.value for c in libro["Indicadores"][1]}


def test_eliminar_en_curso(carrera):
    a = _crear(carrera)
    carrera.delete(f"/calidad/autoevaluaciones/{a['id']}", headers=HX)
    assert ae.obtener(a["id"]) is None


@pytest.fixture
def cuenta(app):
    def crear(email, rol, sigla):
        u = usuarios.crear(email, "Prueba", "Autoevaluación", CLAVE, debe_cambiar_pass=False, es_investigador=False)
        permisos.asignar(u["id"], rol, unidades.id_de(sigla))
        return u
    return crear


def test_permisos(client, cuenta):
    d = cuenta("dir@test.cl", "direccion_carrera", "CMAT")
    cuenta("comision@test.cl", "comision_calidad", "UMSA")
    cuenta("coord@test.cl", "coordinacion_academica", "CMAT")
    a = ae.crear(_marco()["id"], {"nombre": "AE", "desde_anio": HOY - 1, "hasta_anio": HOY - 1}, d["id"])
    url = f"/calidad/autoevaluaciones/{a}"
    cid = _criterio("D1.1")["id"]
    # La Comisión juzga, pero no abre, concluye ni elimina.
    login(client, "comision@test.cl", CLAVE)
    assert "Nueva autoevaluación" not in client.get("/calidad/autoevaluaciones").text
    client.post(f"{url}/criterios/{cid}", headers=HX, data={"nivel": "4", "juicio": "Plan aprobado."})
    assert ae.juicios(a)[cid]["nivel"] == 4
    assert client.post(f"{url}/concluir").status_code == 403
    assert client.delete(url).status_code == 403
    client.get("/logout")
    # La Coordinación académica solo mira.
    login(client, "coord@test.cl", CLAVE)
    p = client.get(f"{url}/criterios/{cid}")
    assert p.status_code == 200 and "Plan aprobado." in p.text and "Juicio fundado" not in p.text
    assert client.post(f"{url}/criterios/{cid}", data={"nivel": "1", "juicio": "x"}).status_code == 403
    assert client.get(f"{url}/informe").status_code == 200
