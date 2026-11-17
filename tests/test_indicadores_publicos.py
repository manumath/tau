"""Página pública de indicadores (PLAN §57, etapa 9; decisión 6 del 7-nov-2026): solo los indicadores marcados, solo los
años cerrados, sin detalle y sin cifras con base menor que 5."""
from app.calidad import indicadores, marco, publico
from app.comun import unidades
from app.comun.db import get_db
from tests.conftest import HX


def _manuales(n):
    return get_db().q("""SELECT * FROM indicador_calidad WHERE fuente = 'manual' AND activo = 1 AND unidad_medida = '%'
                         ORDER BY codigo""")[:n]


def _publicar(iid):
    get_db().execute("UPDATE indicador_calidad SET publico = 1 WHERE id = ?", [iid])


def test_solo_lo_marcado_de_los_anios_cerrados(client):
    mid = marco.de_unidad(unidades.id_de("CMAT"))["id"]
    grande, chica, privada = _manuales(3)
    for i, valor, n in ((grande, 80, 12), (chica, 40, 3), (privada, 55, 20)):
        indicadores.registrar(i["id"], {"anio": 2024, "valor": valor, "n": n, "fuente": "Acta 7", "nota": "Nota interna"},
                              None)
    _publicar(grande["id"])
    _publicar(chica["id"])
    # Sin años cerrados no se publica nada, aunque haya indicadores marcados.
    r = client.get("/publico/indicadores")
    assert r.status_code == 200 and "Aún no hay indicadores publicados" in r.text
    assert indicadores.cerrar(mid, 2024, None)
    r = client.get("/publico/indicadores")
    assert grande["nombre"] in r.text and "80%" in r.text and "n = 12" in r.text
    assert chica["nombre"] in r.text and f"n &lt; {publico.MIN_BASE}" in r.text and "40%" not in r.text
    assert privada["nombre"] not in r.text
    assert "Nota interna" not in r.text and "Acta 7" not in r.text
    assert ">2024</th>" in r.text and ">2025<" not in r.text


def test_la_direccion_marca_que_se_publica(carrera):
    i = _manuales(1)[0]
    datos = {k: i[k] or "" for k in ("codigo", "nombre", "tipo", "formula", "fuente", "unidad_medida", "frecuencia",
                                     "sentido", "responsable", "referencia")}
    r = carrera.put(f"/calidad/marco/indicadores/{i['id']}", data={**datos, "publico": "1"}, headers=HX)
    assert r.status_code == 200
    assert marco.indicador(i["id"])["publico"] == 1
    carrera.put(f"/calidad/marco/indicadores/{i['id']}", data=datos, headers=HX)
    assert marco.indicador(i["id"])["publico"] == 0


def test_la_brecha_usa_el_grupo_mas_pequeno(app):
    from tests.test_cohortes import CSV, _cargar
    _cargar(CSV + "6666666,Carlos,Ticona,,hombre,,2021-I,,,,,,cursando,,,,,\n")
    r = indicadores.calcular("brecha_desercion_genero", 2025, indicadores.Calculadora())
    assert r.n == 1          # un solo hombre: en la página pública esta cifra no se muestra
