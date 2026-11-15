"""Vacantes de admisión y rendimiento por asignatura (PLAN §72, etapa 7)."""
import base64

from app.calidad import indicadores
from app.comun.db import get_db
from app.estudiantil import importar, rendimiento as rd
from app.comun import usuarios
from tests.conftest import HX, PASS_TEMP, login

COHORTES = ("ru,nombres,apellidos,cohorte,estado\n"
            "1000001,Ana,Uno,2025-I,cursando\n1000002,Bea,Dos,2025-I,cursando\n1000003,Ciro,Tres,2025-I,cursando\n"
            "1000004,Dani,Cuatro,2025-II,cursando\n")


def _asignaturas():
    db = get_db()
    for sigla, linea in (("TST-101", "Análisis"), ("TST-102", "Análisis"), ("TST-201", "Álgebra")):
        db.execute("INSERT INTO asignatura (sigla, nombre, departamento, linea_formativa) VALUES (?, ?, 'TST', ?)",
                   [sigla, f"Materia {sigla}", linea])


CSV = ("sigla,gestion,inscritos,aprobados,reprobados,abandonos\n"
       "TST-101,I-2025,40,20,12,8\n"
       "tst-102,2025-I,10,6,3,1\n"
       "TST-201,I-2025,3,2,1,0\n"           # menos de 5: no se muestra ni suma
       "TST-999,I-2025,10,5,5,0\n"          # sigla desconocida
       "TST-101,II-2025,10,5,5,3\n"         # suman más que los inscritos
       "TST-101,I-2025,1,1,0,0\n")          # repetida


def test_vacantes_con_admitidos_de_las_cohortes(app):
    filas, errores = importar.leer(COHORTES.encode())
    assert errores == []
    importar.aplicar(filas, None)
    x, err = rd.guardar_vacantes({"anio": "2025", "ciclo": "I", "vacantes": "4", "postulantes": "10"}, None)
    assert err == []
    assert rd.guardar_vacantes({"anio": "2025", "ciclo": "III", "vacantes": "x"}, None)[1] == [
        "Elija el semestre de la admisión (I o II).", "Escriba las vacantes como número entero."]
    v = rd.vacantes_de(2025, "I")
    assert (v["admitidos"], v["cobertura"], v["postulantes_por_vacante"]) == (3, 75.0, 2.5)
    # Corregir la misma admisión no duplica.
    rd.guardar_vacantes({"anio": "2025", "ciclo": "I", "vacantes": "6"}, None)
    assert len(rd.vacantes()) == 1 and rd.vacantes_de(2025, "I")["postulantes"] is None
    # Indicadores del año: solo la admisión con vacantes registradas.
    c = indicadores.CALCULOS["cobertura_vacantes"].fn(None, 2025)
    assert c.valor == 50.0 and c.n == 6
    assert indicadores.CALCULOS["postulantes_por_vacante"].fn(None, 2025).valor is None
    assert indicadores.CALCULOS["cobertura_vacantes"].fn(None, 2019).valor is None


def test_rendimiento_oculta_las_asignaturas_pequenas(app):
    _asignaturas()
    filas, errores = rd.leer(CSV.encode())
    assert errores == []
    assert [f["estado"] for f in filas] == ["nueva", "nueva", "nueva", "error", "error", "error"]
    assert "no está en el catálogo" in filas[3]["mensaje"] and "suman más" in filas[4]["mensaje"]
    assert "se repiten" in filas[5]["mensaje"]
    assert rd.aplicar(filas, None) == 3
    assert rd.gestiones() == [(2025, "I")]
    por = rd.por_asignatura(2025, "I")
    assert [f["oculta"] for f in por] == [False, False, True] and "inscritos" not in por[2]
    lineas = rd.por_linea(por)
    assert [(x["linea"], x["inscritos"], x["aprobacion"]) for x in lineas] == [
        ("Análisis", 50, 52.0), ("Total de la gestión", 50, 52.0)]
    assert "TST-201,Materia TST-201,Álgebra,menos de 5" in rd.a_csv(2025, "I")
    # Volver a cargar reemplaza.
    assert rd.leer(CSV.encode())[0][0]["estado"] == "reemplaza"


def test_pantallas(carrera):
    _asignaturas()
    r = carrera.get("/docencia/cohortes")
    assert 'href="/docencia/cohortes/vacantes"' in r.text and 'href="/docencia/cohortes/rendimiento"' in r.text
    r = carrera.post("/docencia/cohortes/vacantes", headers=HX, data={"anio": "2025", "ciclo": "I", "vacantes": "40"})
    assert r.headers["hx-redirect"] == "/docencia/cohortes/vacantes"
    r = carrera.post("/docencia/cohortes/vacantes", headers=HX, data={"anio": "2025", "ciclo": "I", "vacantes": "x"})
    assert "número entero" in r.text
    r = carrera.get("/docencia/cohortes/vacantes")
    assert "2025-I" in r.text and "Registrar una admisión" in r.text     # como las cohortes (PLAN §72, etapa 11)
    assert carrera.get("/docencia/cohortes/rendimiento").text.count("Aún no hay datos de rendimiento") == 1
    r = carrera.post("/docencia/cohortes/rendimiento/revisar", headers=HX,
                     files={"archivo": ("r.csv", CSV.encode(), "text/csv")})
    assert "3 fila(s) se guardarán" in r.text
    r = carrera.post("/docencia/cohortes/rendimiento/confirmar", headers=HX,
                     data={"contenido": base64.b64encode(CSV.encode()).decode()})
    assert r.headers["hx-redirect"] == "/docencia/cohortes/rendimiento"
    r = carrera.get("/docencia/cohortes/rendimiento")
    assert "Total de la gestión" in r.text and "menos de 5" in r.text
    r = carrera.get("/docencia/cohortes/rendimiento/csv?gestion=I-2025")
    assert r.status_code == 200 and "TST-101" in r.text
    vid = get_db().q("SELECT id FROM vacante_admision")[0]["id"]
    assert carrera.delete(f"/docencia/cohortes/vacantes/{vid}", headers=HX).status_code == 200
    assert not get_db().q("SELECT 1 FROM vacante_admision")


def test_sin_permiso(client):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    for url in ("/docencia/cohortes/vacantes", "/docencia/cohortes/rendimiento", "/docencia/cohortes/rendimiento/importar"):
        assert client.get(url, headers=HX).status_code == 403
    assert client.post("/docencia/cohortes/vacantes", headers=HX, data={"anio": "2025", "ciclo": "I",
                                                                         "vacantes": "1"}).status_code == 403
