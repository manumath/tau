"""Fase 3, paso 3.4: carga horaria contratada en el vínculo con la Carrera y vista por semestre."""
import pytest

from app.academico import carga, gestiones, oferta
from app.acreditacion import anexo
from app.comun import permisos, unidades, usuarios, vinculos
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login


def _carga(horas, **acts):
    return {"horas": horas, "detalles": {k: None for k in vinculos.CON_DETALLE},
            "actividades": {k: acts.get(k, 0) for k in vinculos.ACTIVIDADES}}


@pytest.fixture
def g(app):
    return {x["tipo"]: x for x in gestiones.crear_anio(2026)}


@pytest.fixture
def emmy(app):
    return usuarios.por_email("inv@test.cl")["id"]


@pytest.fixture
def cmat(app):
    return unidades.id_de("CMAT")


def _dictar(gestion, uid, *siglas):
    for sigla in siglas:
        oid, _ = oferta.agregar(gestion["id"], sigla, "A", "", 1)
        oferta.asignar(oid, uid, "titular")


def test_validacion_de_la_carga(emmy, cmat):
    assert vinculos.leer_carga({"horas": "", "docencia": "", "carga_detalle": ""}) is None
    assert vinculos.leer_carga({"horas": "160", "docencia": "64", "investigacion": "64", "extension": "32"}) == \
        _carga(160, docencia=64, investigacion=64, extension=32)
    assert vinculos.agregar(emmy, "titular", "2020-01-01", carga=_carga(100, docencia=100)) == [
        "La carga contratada es de 32, 64, 96, 128 o 160 h/mes.", "Cada actividad es múltiplo de 32 h/mes (0, 32, 64…)."]
    assert vinculos.agregar(emmy, "titular", "2020-01-01", carga=_carga(160, docencia=64)) == [
        "La distribución por actividad suma 64 h/mes y debe sumar la carga contratada (160 h/mes)."]
    assert vinculos.agregar(emmy, "titular", "2020-01-01", carga={**_carga(None, docencia=64)})[0] \
        .startswith("La carga contratada es de")
    assert vinculos.agregar(emmy, "titular", "2020-01-01",
                            carga=_carga(160, docencia=64, investigacion=64, extension=32)) == []
    v = vinculos.vigente(emmy)
    assert vinculos.texto_carga(v) == "160 h/mes: docencia 64, investigación 64, extensión 32"
    # Un cambio de carga es un periodo nuevo; el anterior se cierra.
    assert vinculos.cambiar_categoria(emmy, "titular", "2026-02-01", carga=_carga(96, docencia=96)) == []
    periodos = vinculos.listar(emmy)
    assert [(p["fecha_fin"], p["horas_contratadas"]) for p in periodos] == [("2026-01-31", 160), (None, 96)]
    # Corregir sin carga deja el periodo sin carga registrada.
    assert vinculos.editar(periodos[1]["id"], "titular", "2026-02-01", None) == []
    assert vinculos.carga_de(vinculos.obtener(periodos[1]["id"])) is None


def test_resumen_por_semestre(g, emmy, cmat):
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", None)["id"]
    _dictar(g["I"], alan, "MAT-111")
    r = carga.resumen(alan, g["I"])
    assert (r["contratada"], r["asignada"], r["avisos"]) == (None, 32, ["Sin vínculo con la Carrera al inicio del semestre."])
    vinculos.agregar(emmy, "titular", "2020-01-01")
    assert carga.resumen(emmy, g["I"])["avisos"] == ["Falta registrar la carga contratada en su vínculo con la Carrera (la registra la Dirección de Carrera)."]
    vid = vinculos.vigente(emmy)["id"]
    vinculos.editar(vid, "titular", "2020-01-01", None, carga=_carga(160, docencia=64, investigacion=64, extension=32))
    _dictar(g["I"], emmy, "MAT-251")
    assert carga.resumen(emmy, g["I"])["avisos"] == [
        "Falta asignar 1 materia (docencia prevista: 64 h/mes; asignada: 32 h/mes)."]
    _dictar(g["I"], emmy, "MAT-252")
    r = carga.resumen(emmy, g["I"])
    assert (r["prevista"], r["asignada"], r["avisos"]) == (64, 64, [])
    _dictar(g["I"], emmy, "MAT-253")
    assert "Tiene 1 materia más de lo previsto" in carga.resumen(emmy, g["I"])["avisos"][0]
    # El verano no suma; sin materias en el II, la docencia prevista queda por asignar.
    assert carga.resumen(emmy, g["II"])["asignada"] == 0
    assert [p["id"] for p in carga.personas(g["I"])] == [emmy, alan]  # Noether, Turing


def test_jce_del_anexo(g, emmy, cmat):
    vinculos.agregar(emmy, "titular", "2020-01-01", "2025-12-31", 40)  # jornada histórica de RR. HH.
    assert anexo.cuerpo_academico(2025, "2025-12-31")["horas"] == 160  # sin carga: jornada 40 h/semana × 4
    vinculos.agregar(emmy, "titular", "2026-01-01", carga=_carga(128, docencia=64, investigacion=64))
    c = anexo.cuerpo_academico(2026, "2026-12-31")
    assert (c["horas"], c["jce"]) == (128, 0.8)                        # la carga contratada manda
    assert carga.contratada_en(emmy, "2025-06-01") is None


def test_pantallas_y_permisos(client, g, emmy, cmat):
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/docencia/carga").status_code == 403
    permisos.asignar(emmy, "coordinacion_academica", cmat)  # ve, pero no registra
    vinculos.agregar(emmy, "titular", "2020-01-01", carga=_carga(64, docencia=32, gestion=32))
    r = client.get(f"/docencia/carga?gestion={g['I']['id']}")
    assert "Noether" in r.text and "La registra la Dirección de Carrera" in r.text
    assert "Falta asignar 1 materia" in r.text
    detalle = client.get(f"/docencia/carga/{g['I']['id']}/{emmy}", headers=HX).text
    assert "64 h/mes" in detalle and "Registrar o cambiar la carga" not in detalle
    assert client.get(f"/admin/usuarios/{emmy}/vinculo", headers=HX).status_code == 403

    # La Dirección de Carrera registra la carga desde Usuarios → Vínculo (pestaña de la Carrera).
    permisos.asignar(emmy, "direccion_carrera", cmat)
    assert "Registrar o cambiar la carga" in client.get(f"/docencia/carga/{g['I']['id']}/{emmy}", headers=HX).text
    modal = client.get(f"/admin/usuarios/{emmy}/vinculo", headers=HX).text
    assert "Carga horaria contratada" in modal and "64 h/mes: docencia 32, gestión 32" in modal
    r = client.post(f"/admin/usuarios/{emmy}/vinculo/cambio", headers=HX,
                    data={"categoria": "titular", "desde": "2026-08-01", "unidad": str(cmat), "horas": "160",
                          "docencia": "64", "investigacion": "64", "extension": "0", "gestion": "32", "otras": "0"})
    assert "160 h/mes: docencia 64, investigación 64, gestión 32" in r.text
    r = client.post(f"/admin/usuarios/{emmy}/vinculo/periodo", headers=HX,
                    data={"categoria": "interino", "desde": "2010-01-01", "hasta": "2011-12-31", "unidad": str(cmat),
                          "horas": "96", "docencia": "64"})
    assert "debe sumar la carga contratada (96 h/mes)" in r.text and 'value="96" selected' in r.text
    vid = vinculos.vigente(emmy)["id"]
    client.put(f"/admin/usuarios/vinculo/{vid}", headers=HX,
               data={"categoria": "titular", "desde": "2026-08-01", "horas": "128", "docencia": "96", "otras": "32",
                     "detalle_otras": "Tutoría"})
    assert vinculos.texto_carga(vinculos.obtener(vid)) == "128 h/mes: docencia 96, otras 32 (Tutoría)"
    assert {"cambiar_categoria", "corregir_vinculo"} <= {a["accion"] for a in get_db().q("SELECT accion FROM auditoria")}
    assert carga.contratada_en(emmy, "2026-09-01") == 128 and carga.contratada_en(emmy, "2026-03-01") == 64
