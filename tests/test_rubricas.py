"""PLAN §70, etapa 4: rúbricas de méritos (formularios 2-1, 2-2 y 2-3) y del examen oral (formulario 4)."""
import pytest

from app.servicios import rubricas as r


@pytest.mark.parametrize("modalidad,formulario,tope_secciones", [
    ("docencia", "2-1", [5, 5, 5, 10, 2, 3]), ("investigacion", "2-2", [3, 9, 3, 10, 2, 3]),
    ("beca_tesis", "2-2", [3, 9, 3, 10, 2, 3]), ("interaccion_social", "2-3", [5, 7, 3, 10, 2, 3])])
def test_cada_formulario_suma_30_puntos(modalidad, formulario, tope_secciones):
    assert r.formulario_de(modalidad) == formulario
    assert [s["maximo"] for s in r.secciones(modalidad)] == tope_secciones and sum(tope_secciones) == r.MERITOS_MAXIMO
    assert [s["numero"] for s in r.secciones(modalidad)] == ["1", "2", "3", "4", "5", "6"]


def test_el_oral_suma_35_con_cinco_criterios():
    assert [(c, m) for c, _t, m in r.ORAL] == [("conocimiento", 7), ("preparacion", 8), ("didactica", 10), ("metodologia", 5), ("respuestas", 5)]
    assert sum(m for *_, m in r.ORAL) == r.ORAL_MAXIMO == 35


def test_claves_del_formulario():
    assert r.claves_meritos("docencia") == ["1a", "1b", "2a", "2b", "3a", "3b", "4", "5a", "5b", "6a", "6b"]
    assert len(r.claves_meritos("investigacion")) == 2 + 7 + 2 + 1 + 2 + 2
    assert r.claves_meritos("interaccion_social")[2:6] == ["2a", "2b", "2c", "2d"]


@pytest.mark.parametrize("nota,puntos", [(0, 0), (50, 0), (50.9, 0), (51, 2), (59.5, 2), (60, 4), (69, 4), (70, 6), (80, 8), (89.9, 8),
                                         (90, 10), (100, 10)])
def test_puntos_de_la_nota_de_la_materia(nota, puntos):
    assert r.puntos_materia(nota) == puntos


def test_calculo_de_meritos_de_docencia_con_topes():
    entradas = {"1a": 2, "1b": 3,            # 6 + 3 = 9 → tope 5
                "2a": 2, "2b": 1,            # 2 + 2 = 4
                "3a": 2, "3b": 3,            # 2 + 1,5 = 3,5
                "4": 85,                     # 8
                "5a": 1, "5b": 1,            # 2
                "6a": 1, "6b": 1}            # 2
    res = r.calcular_meritos("docencia", entradas)
    assert [(s["numero"], s["puntos"]) for s in res["secciones"]] == [("1", 5), ("2", 4), ("3", 3.5), ("4", 8), ("5", 2), ("6", 2)]
    assert res["secciones"][0]["sin_tope"] == 9 and res["total"] == 24.5


def test_el_total_nunca_pasa_de_30():
    todo = {c: r.LIMITE_CANTIDAD for c in r.claves_meritos("investigacion")} | {"4": 100}
    res = r.calcular_meritos("investigacion", todo)
    assert res["total"] == 30 and [s["puntos"] for s in res["secciones"]] == [3, 9, 3, 10, 2, 3]
    assert r.calcular_meritos("docencia", {})["total"] == 0


def test_articulos_en_la_formacion_de_investigacion_se_topan_en_9():
    assert r.calcular_meritos("investigacion", {"2c": 3})["secciones"][1]["puntos"] == 9          # 3 artículos × 4 = 12 → 9
    assert r.calcular_meritos("interaccion_social", {"2a": 1, "2c": 2})["secciones"][1]["puntos"] == 7   # 3 + 4 = 7


def test_validar_meritos():
    ok, errores = r.validar_meritos("docencia", {"1a": "2", "1b": " ", "4": "85,5"})
    assert errores == [] and ok["1a"] == 2 and ok["1b"] == 0 and ok["4"] == 85.5 and set(ok) == set(r.claves_meritos("docencia"))
    _, errores = r.validar_meritos("docencia", {"1a": "mucho", "1b": "-1", "4": "101", "2a": "100"})
    assert len(errores) == 4 and any("«4»: debe estar entre 0 y 100" in e for e in errores)


def test_calculo_y_validacion_del_oral():
    assert r.calcular_oral({"conocimiento": 6, "preparacion": 7, "didactica": 9, "metodologia": 4, "respuestas": 4.5}) == 30.5
    assert r.calcular_oral({"conocimiento": 50}) == 7              # nunca más que el tope del criterio
    ok, errores = r.validar_oral({"conocimiento": "7", "preparacion": "8,5", "didactica": "", "metodologia": "x"})
    assert [e.split(":")[0] for e in errores] == ["Preparación del tema", "Metodología"] and ok["conocimiento"] == 7
