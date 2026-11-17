"""Marco de calidad como datos (PLAN §57, etapa 2): borrador de la Carrera, carga desde CSV, edición y permisos."""
import io

import pytest
from openpyxl import load_workbook

from app.calidad import marco, marco_csv
from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX, login

CLAVE = "Clave-marco-1"


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def _indicador(codigo):
    return get_db().q("SELECT * FROM indicador_calidad WHERE codigo = ?", [codigo])[0]


def test_borrador_de_la_carrera(app):
    """La migración 0051 carga el borrador: D1–D9, la escala de 4 niveles y los 20 atributos de la UMSA."""
    m = _marco()
    assert m["version"] == "2026-borrador" and m["ventana_anios"] == 5 and m["vigente_desde"] is None
    assert [d["codigo"] for d in marco.dimensiones(m["id"])] == [f"D{i}" for i in range(1, 10)]
    assert [n["nombre"] for n in marco.escala(m["id"])] == ["No cumple", "Cumple parcialmente", "Cumple",
                                                            "Cumple plenamente"]
    assert len(marco.atributos(m["id"])) == 20
    r = marco.resumen(m["id"])
    assert r["criterios"] >= 30 and r["indicadores"] == r["activos"] >= 50 and r["automaticos"] > r["manuales"]
    arbol = marco.arbol(m["id"])
    inds = [i for d in arbol for c in d["criterios"] for i in c["indicadores"]]
    # Cada indicador tiene fórmula, al menos un atributo y una fuente conocida; los códigos no se repiten.
    assert all(i["formula"] and i["atributos"] for i in inds)
    assert all(i["fuente"] == "manual" or i["fuente"][5:] in marco.FUENTES_AUTOMATICAS for i in inds)
    assert len({i["codigo"] for i in inds}) == len(inds)
    # Los objetivos de la Política de Calidad de la UMSA están como referencia de sus indicadores.
    refs = " ".join(i["referencia"] or "" for i in inds)
    assert all(f"objetivo {n}" in refs for n in range(2, 10))
    assert "CINDA" not in refs and "CINDA" not in (m["descripcion"] or "")


def test_filtro_por_atributo(app):
    m = _marco()
    arbol = marco.arbol(m["id"], "equidad")
    inds = [i for d in arbol for c in d["criterios"] for i in c["indicadores"]]
    assert inds and all("equidad" in {a["clave"] for a in i["atributos"]} for i in inds)
    assert all(d["criterios"] for d in arbol)   # sin dimensiones vacías


def test_carga_desde_csv(app, tmp_path):
    """Una versión que ya existe no se vuelve a cargar; un código desconocido es un error."""
    con = get_db().conn
    assert marco_csv.cargar_carpeta(con) is None
    carpeta = tmp_path / "m"
    carpeta.mkdir()
    for f in marco_csv.CARPETA.glob("*.csv"):
        (carpeta / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (carpeta / "marco.csv").write_text("campo,valor\nnombre,Otro\nversion,2027\nventana_anios,4\n", encoding="utf-8")
    with open(carpeta / "indicadores.csv", "a", encoding="utf-8") as f:
        f.write("D1.1,X.1,Nuevo,proceso,Fórmula,manual,%,anual,mayor,,,inexistente\n")
    with pytest.raises(ValueError, match="atributo inexistente"):
        marco_csv.cargar_carpeta(con, carpeta)


def test_validaciones(app):
    mid = _marco()["id"]
    base = dict(codigo="D1.1.a", nombre="Repetido", tipo="proceso", formula="x", fuente="manual")
    _, errores = marco.validar_indicador(base, mid)
    assert any("Ya hay otro elemento con el código" in e for e in errores)
    _, errores = marco.validar_indicador({**base, "codigo": "D1.1.z", "fuente": "auto:inventada", "tipo": "otro"}, mid)
    assert "Elija una fuente de la lista." in errores and "Elija el tipo de indicador." in errores
    x, errores = marco.validar_indicador({**base, "codigo": "D1.1.z", "atributos": ["999999", "x"]}, mid)
    assert not errores and x["atributos"] == []   # solo atributos de este marco
    niveles, errores = marco.validar_escala("Bajo: poco\nAlto")
    assert not errores and niveles == [{"valor": 1, "nombre": "Bajo", "descripcion": "poco"},
                                       {"valor": 2, "nombre": "Alto", "descripcion": None}]
    assert marco.validar_escala("Único")[1]
    assert marco.validar_meta("2027", "12,5")[0]["valor"] == 12.5
    assert marco.validar_meta("", "x")[1] == ["Indique el año de la meta.",
                                             "La meta es un número (use punto o coma para los decimales)."]
    assert marco.validar_marco(dict(nombre="M", version="1", ventana_anios="11"))[1] == [
        "La ventana de evidencia es de 1 a 10 años."]


@pytest.fixture
def comision(app):
    u = usuarios.crear("comision@test.cl", "Comisión", "Prueba", CLAVE, debe_cambiar_pass=False, es_investigador=False)
    permisos.asignar(u["id"], "comision_calidad", unidades.id_de("UMSA"))
    return u


def test_la_comision_ve_pero_no_edita(client, comision):
    login(client, "comision@test.cl", CLAVE)
    r = client.get("/calidad/marco")
    assert r.status_code == 200 and "D9" in r.text and "Cumple plenamente" in r.text
    assert "Agregar indicador" not in r.text and "Datos del marco" not in r.text
    mid, iid = _marco()["id"], _indicador("D3.2.b")["id"]
    assert "Deserción de la cohorte" in client.get(f"/calidad/marco/indicadores/{iid}").text
    assert client.get(f"/calidad/marco/{mid}/editar").status_code == 403
    assert client.post(f"/calidad/marco/indicadores/{iid}/metas", data={"anio": "2027", "valor": "10"}).status_code == 403
    assert client.delete(f"/calidad/marco/indicadores/{iid}").status_code == 403
    assert marco.indicador(iid)["metas"] == []


def test_un_investigador_no_lo_ve(client, app):
    from tests.conftest import PASS_TEMP
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/calidad/marco").status_code == 403
    assert client.get(f"/calidad/marco/indicadores/{_indicador('D1.1.a')['id']}").status_code == 403


def test_la_direccion_de_carrera_edita(carrera):
    m = _marco()
    d = marco.dimensiones(m["id"])[0]
    r = carrera.get("/calidad/marco")
    assert "Agregar indicador" in r.text and "Datos del marco" in r.text
    # Datos del marco y escala.
    r = carrera.put(f"/calidad/marco/{m['id']}", headers=HX, data=dict(
        nombre=m["nombre"], version="2027", ventana_anios="6", vigente_desde="2027-01-01", vigente_hasta="2026-01-01"))
    assert "La vigencia termina antes de empezar." in r.text
    carrera.put(f"/calidad/marco/{m['id']}", headers=HX, data=dict(nombre=m["nombre"], version="2027", ventana_anios="6",
                                                                   vigente_desde="2027-01-01"))
    assert (_marco()["version"], _marco()["ventana_anios"]) == ("2027", 6)
    carrera.put(f"/calidad/marco/{m['id']}/escala", headers=HX, data={"niveles": "Insuficiente\nSuficiente: basta\nDestacado"})
    assert [n["nombre"] for n in marco.escala(m["id"])] == ["Insuficiente", "Suficiente", "Destacado"]
    # Un criterio nuevo y un indicador en él, con atributos.
    r = carrera.post(f"/calidad/marco/dimensiones/{d['id']}/criterios", headers=HX,
                     data={"codigo": "D1.9", "nombre": "Sostenibilidad financiera"})
    cid = get_db().q("SELECT id FROM criterio_calidad WHERE codigo = 'D1.9'")[0]["id"]
    equidad = next(a["id"] for a in marco.atributos(m["id"]) if a["clave"] == "equidad")
    datos = dict(codigo="D1.9.a", nombre="Becas", tipo="estructura", formula="Becas / estudiantes × 100",
                 fuente="manual", frecuencia="anual", sentido="mayor", unidad_medida="%", atributos=[str(equidad)])
    r = carrera.post(f"/calidad/marco/criterios/{cid}/indicadores", headers=HX, data={**datos, "codigo": "D1.1.a"})
    assert "Ya hay otro elemento con el código" in r.text
    carrera.post(f"/calidad/marco/criterios/{cid}/indicadores", headers=HX, data=datos)
    i = _indicador("D1.9.a")
    assert [a["clave"] for a in marco.indicador(i["id"])["atributos"]] == ["equidad"]
    # Metas por año: se reemplaza la del mismo año; con metas, el indicador no se elimina (se desactiva).
    url = f"/calidad/marco/indicadores/{i['id']}"
    carrera.post(f"{url}/metas", headers=HX, data={"anio": "2027", "valor": "10"})
    carrera.post(f"{url}/metas", headers=HX, data={"anio": "2027", "valor": "12,5", "nota": "Ajustada"})
    assert [(x["anio"], x["valor"], x["nota"]) for x in marco.metas(i["id"])] == [(2027, 12.5, "Ajustada")]
    carrera.delete(url, headers=HX)
    assert marco.indicador(i["id"]) is not None
    carrera.post(f"{url}/desactivar", headers=HX)
    assert marco.indicador(i["id"])["activo"] == 0
    assert "Becas" not in "".join(x["nombre"] for d_ in marco.arbol(m["id"], inactivos=False)
                                  for c in d_["criterios"] for x in c["indicadores"])
    # El criterio con indicadores no se elimina; sin ellos, sí.
    carrera.delete(f"/calidad/marco/criterios/{cid}", headers=HX)
    assert marco.criterio(cid) is not None
    carrera.delete(f"{url}/metas/2027", headers=HX)
    carrera.delete(url, headers=HX)
    carrera.delete(f"/calidad/marco/criterios/{cid}", headers=HX)
    assert marco.criterio(cid) is None and marco.indicador(i["id"]) is None
    acciones = {a["accion"] for a in get_db().q("SELECT accion FROM auditoria")}
    assert {"editar_marco_calidad", "editar_escala_calidad", "crear_criterio_calidad", "crear_indicador_calidad",
            "meta_indicador_calidad", "desactivar_indicador_calidad", "eliminar_indicador_calidad"} <= acciones


def test_xlsx_con_las_columnas_de_carga(carrera):
    r = carrera.get("/calidad/marco/xlsx")
    assert r.status_code == 200 and "marco-de-calidad-2026-borrador.xlsx" in r.headers["content-disposition"]
    libro = load_workbook(io.BytesIO(r.content))
    assert libro.sheetnames == ["Marco", "Escala", "Atributos", "Dimensiones", "Criterios", "Indicadores", "Metas"]
    cab = [c.value for c in libro["Indicadores"][1]]
    assert cab == marco_csv.COLUMNAS["indicadores"] + ["activo"]
    assert [c.value for c in libro["Criterios"][1]] == marco_csv.COLUMNAS["criterios"]


def test_otra_unidad_no_gestiona_el_marco_de_la_carrera(app):
    """La Dirección de Carrera gestiona el marco de su unidad: el rol en otra unidad no alcanza."""
    u = usuarios.crear("otra@test.cl", "Otra", "Prueba", CLAVE, debe_cambiar_pass=False, es_investigador=False)
    auth = {"id": u["id"]}
    assert not permisos.puede(auth, "gestionar_marco_calidad", unidades.id_de("CMAT"))
    permisos.asignar(u["id"], "direccion_carrera", unidades.id_de("CMAT"))
    assert permisos.puede({"id": u["id"]}, "gestionar_marco_calidad", unidades.id_de("CMAT"))
    assert not permisos.puede({"id": u["id"]}, "gestionar_marco_calidad", unidades.id_de("IIMAT"))
