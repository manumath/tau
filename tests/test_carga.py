"""Fase 3, paso 3.4: carga horaria semestral (unidades de 32 h/mes)."""
import pytest

from app.academico import carga, gestiones, oferta
from app.acreditacion import anexo
from app.comun import permisos, unidades, usuarios, vinculos
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login


@pytest.fixture
def g(app):
    gestiones.crear_anio(2025)
    return {x["tipo"]: x for x in gestiones.crear_anio(2026)}


@pytest.fixture
def emmy(app):
    return usuarios.por_email("inv@test.cl")["id"]


def _dictar(gestion, emmy, *siglas):
    for sigla in siglas:
        oid, _ = oferta.agregar(gestion["id"], sigla, "A", "", 1)
        oferta.asignar(oid, emmy, "titular")


def test_distribucion_y_avisos(g, emmy):
    # Dos materias + dos de investigación + una de extensión = 160 h/mes.
    _dictar(g["I"], emmy, "MAT-111", "MAT-251")
    r = carga.resumen(emmy, g["I"])
    assert (r["docencia"], r["contratada"], r["avisos"]) == (64, None, ["Falta registrar la carga contratada del semestre."])
    assert carga.fijar_contratada(emmy, g["I"], "100", emmy) == "La carga contratada es de 32, 64, 96, 128 o 160 h/mes."
    assert carga.fijar_contratada(emmy, g["I"], "160", emmy) is None
    assert carga.agregar_actividad(emmy, g["I"], "investigacion", "48", "") == \
        "Las horas son múltiplos de 32 h/mes (32, 64, 96…)."
    assert carga.agregar_actividad(emmy, g["I"], "viajes", "32", "") == "Elija el tipo de actividad."
    assert carga.agregar_actividad(emmy, g["I"], "investigacion", "64", "Proyecto IDH") is None
    assert carga.resumen(emmy, g["I"])["avisos"] == ["Faltan 32 h/mes por asignar."]
    carga.agregar_actividad(emmy, g["I"], "extension", "32", "Olimpiadas")
    r = carga.resumen(emmy, g["I"])
    assert (r["total"], r["por_tipo"]["investigacion"], r["avisos"]) == (160, 64, [])
    carga.agregar_actividad(emmy, g["I"], "gestion", "32", "Jefatura")
    assert carga.resumen(emmy, g["I"])["avisos"] == [
        "La distribución supera la carga contratada en 32 h/mes.", "El total (192 h/mes) supera el tiempo completo (160 h/mes)."]
    assert carga.fijar_contratada(emmy, g["I"], "128", emmy) is None  # una sola carga por persona y semestre
    assert get_db().q("SELECT COUNT(*) n FROM carga_semestral")[0]["n"] == 1
    assert [p["id"] for p in carga.personas(g["I"])] == [emmy]


def test_solo_semestres_y_copia(g, emmy):
    assert "por semestre" in carga.fijar_contratada(emmy, g["VER"], "64", emmy)
    assert carga.agregar_actividad(emmy, g["II"], "gestion", "32", "") == "Registre primero la carga contratada del semestre."
    carga.fijar_contratada(emmy, g["I"], "96", emmy)
    carga.agregar_actividad(emmy, g["I"], "investigacion", "32", "Proyecto")
    assert gestiones.codigo(carga.anterior(g["I"])) == "II-2025" and carga.anterior(g["II"])["id"] == g["I"]["id"]
    assert carga.copiar_del_anterior(g["II"], emmy) == 1
    assert carga.copiar_del_anterior(g["II"], emmy) == 0  # no pisa lo ya registrado
    r = carga.resumen(emmy, g["II"])
    assert r["contratada"] == 96 and [a["detalle"] for a in r["actividades"]] == ["Proyecto"]
    assert carga.contratada_en(emmy, "2026-12-31") == 96 and carga.contratada_en(emmy, "2025-12-31") is None


def test_jce_del_anexo(g, emmy):
    vinculos.agregar(emmy, "titular", "2020-01-01", None, 40, unidad=unidades.id_de("IIMAT"))
    carga.fijar_contratada(emmy, g["II"], "128", emmy)
    c = anexo.cuerpo_academico(2026, "2026-12-31")
    assert (c["horas"], c["jce"]) == (128, 0.8)                        # la carga contratada manda
    assert anexo.cuerpo_academico(2025, "2025-12-31")["horas"] == 160  # sin carga: jornada 40 h/semana × 4


def test_pantallas_y_permisos(client, g, emmy):
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/docencia/carga").status_code == 403
    assert "Carga horaria" not in client.get("/docencia/planes").text
    cmat = unidades.id_de("CMAT")
    permisos.asignar(emmy, "coordinacion_academica", cmat)  # ve, pero no asigna
    assert "Carga horaria" in client.get("/docencia/planes").text
    assert client.post(f"/docencia/carga/{g['I']['id']}", headers=HX,
                       data={"usuario": str(emmy), "horas": "64"}).status_code == 403
    permisos.asignar(emmy, "direccion_carrera", cmat)
    client.post(f"/docencia/carga/{g['I']['id']}", headers=HX, data={"usuario": str(emmy), "horas": "64"})
    client.post(f"/docencia/carga/{g['I']['id']}/{emmy}/actividades", headers=HX,
                data={"tipo": "investigacion", "horas": "32", "detalle": "Proyecto IDH"})
    assert carga.resumen(emmy, g["I"])["total"] == 32
    r = client.get(f"/docencia/carga?gestion={g['I']['id']}")
    assert "Emmy" in r.text and "Faltan 32 h/mes por asignar." in r.text
    assert "Proyecto IDH" in client.get(f"/docencia/carga/{g['I']['id']}/{emmy}", headers=HX).text
    aid = carga.resumen(emmy, g["I"])["actividades"][0]["id"]
    assert client.delete(f"/docencia/carga/actividades/{aid}", headers=HX).status_code == 200
    assert carga.resumen(emmy, g["I"])["total"] == 0
    assert {"carga_contratada", "carga_actividad", "quitar_carga_actividad"} <= {
        a["accion"] for a in get_db().q("SELECT accion FROM auditoria")}
