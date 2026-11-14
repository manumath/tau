"""PLAN §70, etapa 6: formularios imprimibles del reglamento de 2023."""
import pytest

from app.comun.db import get_db
from app.servicios import auxiliaturas as aux
from app.servicios import formularios as frm
from tests.test_auxiliaturas_reglamento import (  # noqa: F401
    MERITOS, _antigua, _en_oral, _hasta_meritos)
from tests.test_servicios import _como, convocatoria, gente  # noqa: F401

RUBRICA = {"conocimiento": "6", "preparacion": "7", "didactica": "9", "metodologia": "4", "respuestas": "4,5"}


def _calificada(gente, convocatoria):
    """Méritos calificados por dos miembros con detalles distintos."""
    pid = _hasta_meritos(gente, convocatoria)
    it = aux.item(convocatoria["iid"])
    assert aux.calificar_detalle(it, gente["doc1"]["id"], pid, MERITOS) == []                      # 24,5
    assert aux.calificar_detalle(it, gente["doc2"]["id"], pid, {**MERITOS, "4": "60", "1a": "0", "1b": "0"}) == []   # 0 + 4 + 3,5 + 4 + 2 + 2 = 15,5
    return pid, it


def test_acta_de_meritos_promedia_a_los_miembros(app, gente, convocatoria):
    pid, it = _calificada(gente, convocatoria)
    acta = frm.acta_meritos(aux.obtener(convocatoria["cid"]), pid)
    assert acta["miembros"] == 2 and acta["total"] == 20          # (24,5 + 15,5) / 2
    por_numero = {s["numero"]: s for s in acta["secciones"]}
    assert [s["puntos"] for s in acta["secciones"]] == [2.5, 4, 3.5, 6, 2, 2]                          # (5+0)/2, 4, 3,5, (8+4)/2, 2, 2
    assert por_numero["1"]["lineas"][0][4] == 1 and por_numero["4"]["lineas"][0][4] == 72.5       # cantidades medias: (2+0)/2 y (85+60)/2
    assert acta["total"] == aux.nota(pid, "meritos")
    assert frm.acta_meritos(aux.obtener(convocatoria["cid"]), 9999) is None


def test_acta_del_oral_promedia_cada_criterio(app, gente, convocatoria):
    pid, _ = _en_oral(gente, convocatoria)
    it = aux.item(convocatoria["iid"])
    assert aux.fijar_tribunal(it, [gente["doc1"]["id"], gente["doc2"]["id"]], [gente["Ana"]["uid"], gente["Pedro"]["uid"]]) == []
    assert frm.acta_oral(pid) is None
    assert aux.calificar_detalle(it, gente["doc1"]["id"], pid, RUBRICA) == []
    assert aux.calificar_detalle(it, gente["doc2"]["id"], pid, {**RUBRICA, "conocimiento": "4", "didactica": "7"}) == []
    acta = frm.acta_oral(pid)
    assert [(k, m, v) for k, _t, m, v in acta["criterios"]] == [("conocimiento", 7, 5), ("preparacion", 8, 7), ("didactica", 10, 8),
                                                                  ("metodologia", 5, 4), ("respuestas", 5, 4.5)]
    assert acta["total"] == 28.5 and acta["total"] == aux.nota(pid, "oral")


def test_formulario_de_habilitacion_y_acta_final(app, gente, convocatoria):
    pid, it = _calificada(gente, convocatoria)
    [h] = frm.habilitacion(aux.item(convocatoria["iid"]))
    assert h["habilitado"] is True and h["plan"] is True and len(h["requisitos"]) == 13
    assert all(ok for _t, ok, _opcional in h["requisitos"])                                        # la postulante lo entregó todo
    [f] = frm.final(aux.item(convocatoria["iid"]))
    assert f["notas"] == {"meritos": 20, "escrito": None, "oral": None} and f["total"] == 20


@pytest.mark.parametrize("n,texto", [("1", "FORMULARIO DE HABILITACIÓN"), ("3", "SORTEO DEL TEMA DEL EXAMEN ORAL"),
                                     ("4", "ACTA DEL EXAMEN ORAL"), ("5", "ACTA FINAL DEL CONCURSO")])
def test_cada_formulario_se_abre_y_se_imprime(app, gente, convocatoria, n, texto):
    _calificada(gente, convocatoria)
    pagina = _como(app, "dir@test.cl").get(f"/servicios/auxiliaturas/item/{convocatoria['iid']}/formulario/{n}")
    assert pagina.status_code == 200 and texto in pagina.text
    assert "Aprobado con Res. HCU N.º 424/2023" in pagina.text and "data-accion=\"imprimir\"" in pagina.text and f"Formulario N.º {n}" in pagina.text
    assert "TRIBUNAL DOCENTE" in pagina.text and "Vo. Bo. DIRECTOR DE CARRERA" in pagina.text


def test_formulario_de_meritos_segun_la_modalidad(app, gente, convocatoria):
    pid, _ = _calificada(gente, convocatoria)
    d = _como(app, "dir@test.cl")
    pagina = d.get(f"/servicios/auxiliaturas/item/{convocatoria['iid']}/formulario/2").text
    assert "ACTA DE CALIFICACIÓN DE MÉRITOS PARA AUXILIARES DE DOCENCIA" in pagina and "Formulario N.º 2-1" in pagina
    assert "Estudiante, Sofía" in pagina and "promedio de 2 miembro(s)" in pagina and "TOTAL (máximo 30)" in pagina and "20" in pagina
    assert "51–59: 2 · 60–69: 4" in pagina and "Curso aprobado" in pagina
    # Para otra modalidad es otro formulario.
    from tests.test_auxiliaturas_reglamento import _nueva
    cid = _nueva(gente, convocatoria, "interaccion_social")
    assert aux.agregar_item(aux.obtener(cid), {"titulo": "Taller", "plazas": "1", "horas": "20"}) == []
    iid = aux.items(cid)[0]["id"]
    assert "AUXILIARES DE INTERACCIÓN SOCIAL" in d.get(f"/servicios/auxiliaturas/item/{iid}/formulario/2").text
    assert pid


def test_los_formularios_no_son_para_cualquiera_ni_para_las_convocatorias_antiguas(app, gente, convocatoria):
    _calificada(gente, convocatoria)
    ruta = f"/servicios/auxiliaturas/item/{convocatoria['iid']}/formulario"
    assert _como(app, "doc1@test.cl").get(f"{ruta}/5").status_code == 200              # integra la comisión
    assert _como(app, "doc3@test.cl").get(f"{ruta}/5").status_code == 403
    d = _como(app, "dir@test.cl")
    assert d.get(f"{ruta}/9").status_code == 404
    assert "Formulario 1 · Habilitación" in d.get(f"/servicios/auxiliaturas/item/{convocatoria['iid']}").text
    _antigua(convocatoria["cid"])
    assert d.get(f"{ruta}/5").status_code == 404
    assert "Formulario 1 · Habilitación" not in d.get(f"/servicios/auxiliaturas/item/{convocatoria['iid']}").text
