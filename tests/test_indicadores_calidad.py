"""Cifras de los indicadores del marco de calidad (PLAN §57, etapa 3): cálculos automáticos, cifras manuales, semáforo
frente a la meta, cierre de años, instantáneas «a hoy», tablero y permisos."""
import io
from datetime import date

import pytest
from openpyxl import load_workbook

from app.calidad import indicadores, marco
from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX, login
from tests.test_cohortes import _cargar

CLAVE = "Clave-indicadores-1"
HOY = date.today().year


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def _por_fuente(fuente):
    return get_db().q("SELECT * FROM indicador_calidad WHERE fuente = ?", [fuente])[0]


def _manual():
    return get_db().q("SELECT * FROM indicador_calidad WHERE fuente = 'manual' AND activo = 1 ORDER BY codigo")[0]


def test_registro_cubre_las_fuentes_del_marco(app):
    """Cada fuente automática que ofrece el marco tiene su cálculo, y ninguno sobra."""
    assert set(indicadores.CALCULOS) == set(marco.FUENTES_AUTOMATICAS)
    # Los pendientes dicen por qué; sin datos, cada cálculo devuelve un resultado sin fallar.
    assert "plan de mejora" in indicadores.calcular("acciones_cumplidas", HOY).detalle
    calc = indicadores.Calculadora()
    for clave in indicadores.CALCULOS:
        assert isinstance(indicadores.calcular(clave, HOY - 1, calc), indicadores.Resultado)


def test_semaforo():
    e = indicadores.estado
    assert (e(10, 8, "mayor"), e(7, 8, "mayor"), e(8, 8, "mayor")) == ("cumple", "no_cumple", "cumple")
    assert (e(5, 8, "menor"), e(9, 8, "menor")) == ("cumple", "no_cumple")
    assert (e(None, 8, "mayor"), e(3, None, "mayor"), e(3, 1, "informativo")) == ("sin_dato", "sin_meta", "informativo")


def test_cifras_de_las_cohortes(app):
    _cargar()
    c = indicadores.Calculadora()
    assert indicadores.calcular("ingresantes", 2021, c).valor == 2
    assert indicadores.calcular("ingresantes_mujeres", 2021, c).valor == 100.0
    # En 2022 dejaron la carrera una retirada y una congelada que no volvió, de cinco matriculados.
    d = indicadores.calcular("desercion", 2022, c)
    assert (d.valor, d.n) == (40.0, 5)
    assert indicadores.calcular("brecha_desercion_genero", 2022, c).valor == 66.7
    t = indicadores.calcular("tiempo_titulacion", 2025, c)
    assert (t.valor, t.n) == (5.0, 1)


def test_meta_semaforo_y_cumplimiento(app):
    _cargar()
    mid = _marco()["id"]
    des = _por_fuente("auto:desercion")
    assert des["sentido"] == "menor"
    marco.guardar_meta(des["id"], {"anio": 2022, "valor": 30, "nota": None})
    v = indicadores.valores_del_anio(mid, 2022)
    assert (v[des["id"]]["valor"], v[des["id"]]["meta"], v[des["id"]]["estado"]) == (40.0, 30, "no_cumple")
    cumpl = _por_fuente("auto:cumplimiento_objetivos")
    assert (v[cumpl["id"]]["valor"], v[cumpl["id"]]["n"]) == (0.0, 1)   # 0 de 1 indicador con meta y cifra
    # La serie de la ficha da lo mismo que el tablero.
    assert indicadores.serie(marco.indicador(des["id"]), [2022])[2022]["estado"] == "no_cumple"
    marco.guardar_meta(des["id"], {"anio": 2022, "valor": 45, "nota": None})
    assert indicadores.valores_del_anio(mid, 2022)[cumpl["id"]]["valor"] == 100.0


def test_instantaneas_de_lo_que_solo_se_mide_a_hoy(app):
    mid = _marco()["id"]
    obs = _por_fuente("auto:observaciones_plan")
    assert indicadores.guardar_instantaneas() >= 1
    assert get_db().q("SELECT anio FROM valor_automatico WHERE indicador_id = ?", [obs["id"]])[0]["anio"] == HOY
    # Un año pasado sin instantánea queda sin dato; con ella, se usa la guardada.
    assert indicadores.valores_del_anio(mid, HOY - 1)[obs["id"]]["estado"] == "sin_dato"
    get_db().execute("INSERT INTO valor_automatico (indicador_id, anio, valor, n, detalle) VALUES (?, ?, 4, NULL, 'x')",
                     [obs["id"], HOY - 1])
    x = indicadores.valores_del_anio(mid, HOY - 1)[obs["id"]]
    assert (x["valor"], x["origen"]) == (4, "instantanea")


@pytest.fixture
def cuenta(app):
    def crear(email, rol, sigla):
        u = usuarios.crear(email, "Prueba", "Indicadores", CLAVE, debe_cambiar_pass=False, es_investigador=False)
        permisos.asignar(u["id"], rol, unidades.id_de(sigla))
        return u
    return crear


def test_cifras_manuales_y_cierre(carrera):
    i = _manual()
    url = f"/calidad/marco/indicadores/{i['id']}"
    anio = HOY - 1
    r = carrera.get(url)
    assert "Guardar cifra" in r.text and "Cifras" in r.text
    carrera.post(f"{url}/valores", headers=HX, data={"anio": str(anio), "valor": "7,5", "n": "20", "fuente": "Acta 3"})
    assert indicadores.manuales(i["id"])[anio]["valor"] == 7.5
    r = carrera.post(f"{url}/valores", headers=HX, data={"anio": str(anio), "valor": "x", "n": "dos"})
    assert indicadores.manuales(i["id"])[anio]["valor"] == 7.5   # no se guardó
    # Un automático no recibe cifras a mano.
    auto = _por_fuente("auto:ingresantes")
    carrera.post(f"/calidad/marco/indicadores/{auto['id']}/valores", headers=HX, data={"anio": str(anio), "valor": "3"})
    assert indicadores.manuales(auto["id"]) == {}
    # El tablero la muestra; cerrar el año la congela y bloquea los cambios.
    t = carrera.get("/calidad/indicadores")
    assert t.status_code == 200 and "Cerrar el año" in t.text and "7,5" in t.text
    carrera.post(f"/calidad/indicadores/cierres/{anio}", headers=HX)
    assert anio in indicadores.cierres(_marco()["id"])
    carrera.post(f"{url}/valores", headers=HX, data={"anio": str(anio), "valor": "9"})
    carrera.delete(f"{url}/valores/{anio}", headers=HX)
    assert indicadores.manuales(i["id"])[anio]["valor"] == 7.5
    get_db().execute("DELETE FROM valor_indicador")                       # aunque cambien los datos…
    assert indicadores.valores_del_anio(_marco()["id"], anio)[i["id"]]["valor"] == 7.5   # …lo cerrado no cambia
    assert carrera.post(f"/calidad/indicadores/cierres/{HOY}", headers=HX).status_code in (200, 303)
    assert HOY not in indicadores.cierres(_marco()["id"])                # el año en curso no se cierra
    carrera.delete(f"/calidad/indicadores/cierres/{anio}", headers=HX)
    assert indicadores.valores_del_anio(_marco()["id"], anio)[i["id"]]["valor"] is None
    acciones = {a["accion"] for a in get_db().q("SELECT accion FROM auditoria")}
    assert {"cifra_indicador_calidad", "cerrar_anio_calidad", "reabrir_anio_calidad"} <= acciones


def test_permisos_del_tablero(client, cuenta):
    i = _manual()
    anio = HOY - 1
    cuenta("comision@test.cl", "comision_calidad", "UMSA")
    cuenta("datos@test.cl", "gestion_datos", "CMAT")
    cuenta("datos-iimat@test.cl", "gestion_datos", "IIMAT")
    login(client, "comision@test.cl", CLAVE)
    assert client.get("/calidad/indicadores").status_code == 200
    assert "Guardar cifra" not in client.get(f"/calidad/marco/indicadores/{i['id']}").text
    assert client.post(f"/calidad/indicadores/cierres/{anio}").status_code == 403
    assert client.post(f"/calidad/marco/indicadores/{i['id']}/valores", data={"anio": str(anio), "valor": "1"}
                       ).status_code == 403
    client.get("/logout")
    # Gestión de datos de la Carrera registra cifras, pero no cierra años; la del Instituto no registra en la Carrera.
    login(client, "datos@test.cl", CLAVE)
    assert "Cerrar el año" not in client.get("/calidad/indicadores").text
    assert client.post(f"/calidad/indicadores/cierres/{anio}").status_code == 403
    client.post(f"/calidad/marco/indicadores/{i['id']}/valores", headers=HX, data={"anio": str(anio), "valor": "1"})
    assert indicadores.manuales(i["id"])[anio]["valor"] == 1
    client.get("/logout")
    login(client, "datos-iimat@test.cl", CLAVE)
    assert client.post(f"/calidad/marco/indicadores/{i['id']}/valores", data={"anio": str(anio), "valor": "2"}
                       ).status_code == 403


def test_xlsx_del_tablero(carrera):
    r = carrera.get(f"/calidad/indicadores/xlsx?hasta={HOY}")
    assert r.status_code == 200 and f"indicadores-de-calidad-{HOY - 4}-{HOY}.xlsx" in r.headers["content-disposition"]
    libro = load_workbook(io.BytesIO(r.content))
    assert libro.sheetnames[:3] == ["Indicadores", "Detalle", "Método"]
    cab = [c.value for c in libro["Indicadores"][1]]
    assert cab[:6] == ["dimension", "criterio", "codigo", "indicador", "unidad", "lectura"]
    assert {str(HOY), f"meta {HOY}", f"estado {HOY}"} <= set(cab)
