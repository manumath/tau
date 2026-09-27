"""Fase 3, pasos 3.2 y 3.3: gestiones académicas, oferta por gestión y asignación docente."""
import pytest

from app.academico import gestiones, oferta
from app.comun import permisos, unidades, usuarios, vinculos
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login


@pytest.fixture
def g2026(app):
    return {g["tipo"]: g for g in gestiones.crear_anio(2026)}


def _asig(sigla):
    return get_db().q("SELECT id FROM asignatura WHERE sigla = ?", [sigla])[0]["id"]


# --- Gestiones ---------------------------------------------------------------------------------------------

def test_gestiones_del_anio(g2026):
    assert [gestiones.codigo(g) for g in gestiones.crear_anio(2026)] == ["I-2026", "INV-2026", "II-2026", "VER-2026"]
    assert (g2026["VER"]["fecha_inicio"], g2026["VER"]["fecha_fin"]) == ("2027-01-02", "2027-01-31")
    assert gestiones.nombre(g2026["VER"]) == "Curso de verano 2026 (enero de 2027)"
    assert gestiones.por_codigo("ver-2026")["id"] == g2026["VER"]["id"] and gestiones.por_codigo("V-2026") is None
    assert gestiones.codigo(gestiones.actual("2026-07-15")) == "INV-2026"
    assert gestiones.codigo(gestiones.actual("2027-01-20")) == "VER-2026"  # enero de 2027, gestión 2026
    assert gestiones.codigo(gestiones.actual("2025-12-01")) == "I-2026"    # la próxima
    assert gestiones.actualizar_fechas(g2026["I"]["id"], "2026-03-01", "2026-02-01") == \
        "El término no puede ser anterior al inicio."
    assert gestiones.actualizar_fechas(g2026["I"]["id"], "2026-02-09", "2026-07-03") is None
    with pytest.raises(ValueError):
        gestiones.crear_anio(1990)


# --- Oferta ------------------------------------------------------------------------------------------------

def test_oferta_valida(g2026):
    gid = g2026["I"]["id"]
    oid, errores = oferta.agregar(gid, "MAT-111 · Algebra I", "a", "35", 1)
    assert errores == [] and oferta.obtener(oid)["paralelo"] == "A" and oferta.obtener(oid)["inscritos"] == 35
    assert "ya está en la oferta" in oferta.agregar(gid, "MAT-111", "A", "", 1)[1][0]
    assert "la dicta otra unidad" in oferta.agregar(gid, "FIS-137", "A", "", 1)[1][0]
    assert oferta.agregar(gid, "MAT-999", "A", "", 1)[1] == ["Elija una asignatura del catálogo."]
    assert "paralelo" in oferta.agregar(gid, "MAT-112", "A-1234", "", 1)[1][0]
    assert "inscritos" in oferta.agregar(gid, "MAT-112", "B", "muchos", 1)[1][0]
    assert oferta.agregar(gid, "MAT-111", "B", "", 1)[1] == []  # otro paralelo
    assert oferta.horas_del_plan(_asig("MAT-278")) == 11           # 4+3+4 y 4+4+3 según el plan
    assert oferta.horas_del_plan(_asig("MAT-399")) == 34
    assert oferta.horas_del_plan(_asig("MAT-412")) is None         # maestría: créditos
    assert oferta.programas_de(_asig("MAT-111")) == ["Licenciatura en Matemática",
                                                     "Licenciatura en Matemática Aplicada"]


def test_asignacion_docente(g2026):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    oid, _ = oferta.agregar(g2026["I"]["id"], "MAT-251", "A", "", 1)
    assert oferta.asignar(oid, emmy, "jefe") == ["Rol no válido."]
    assert oferta.asignar(oid, emmy, "titular") == []
    assert oferta.asignar(oid, emmy, "auxiliar") == ["Esa persona ya está asignada a este paralelo."]
    # Sin vínculo con la Carrera: se avisa, no se impide.
    assert oferta.sin_vinculo_con_la_carrera(emmy, g2026["I"])
    vinculos.agregar(emmy, "titular", "2015-01-01", unidad=unidades.id_de("CMAT"))
    assert not oferta.sin_vinculo_con_la_carrera(emmy, g2026["I"])
    otra, _ = oferta.agregar(g2026["I"]["id"], "MAT-252", "A", "", 1)
    oferta.asignar(otra, emmy, "titular")
    assert oferta.horas_de_docencia(emmy, g2026["I"]["id"]) == 64  # 32 h/mes por materia
    assert oferta.horas_de_docencia(emmy, g2026["II"]["id"]) == 0
    d = oferta.docentes(otra)[0]
    oferta.quitar_docente(d["id"])
    assert oferta.horas_de_docencia(emmy, g2026["I"]["id"]) == 32
    # Los auxiliares no suman carga.
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", None)["id"]
    oferta.asignar(oid, alan, "auxiliar")
    assert oferta.horas_de_docencia(alan, g2026["I"]["id"]) == 0


def test_cursos_de_temporada_solo_titulares(g2026):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", None)["id"]
    oid, _ = oferta.agregar(g2026["VER"]["id"], "MAT-278", "A", "", 1)
    assert "titulares" in oferta.asignar(oid, emmy, "titular")[0]         # sin vínculo con la Carrera
    vinculos.agregar(alan, "interino", "2020-01-01", unidad=unidades.id_de("CMAT"))
    assert "titulares" in oferta.asignar(oid, alan, "titular")[0]         # interino: contrato semestral
    assert oferta.asignar(oid, alan, "auxiliar") == []                    # el auxiliar no tiene esa restricción
    vinculos.agregar(emmy, "titular", "2015-01-01", unidad=unidades.id_de("CMAT"))
    assert oferta.asignar(oid, emmy, "titular") == []
    assert oferta.horas_de_docencia(emmy, g2026["VER"]["id"]) == 0       # no forma parte de la carga


def test_pantallas_y_permisos(client, g2026):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get(f"/docencia/oferta?gestion={g2026['I']['id']}")
    assert "I-2026" in r.text and "Aún no hay asignaturas" in r.text and "Agregar a la oferta" not in r.text
    assert client.post(f"/docencia/oferta/{g2026['I']['id']}", headers=HX,
                       data={"asignatura": "MAT-111"}).status_code == 403
    assert client.post("/docencia/gestiones", headers=HX, data={"anio": "2027"}).status_code == 403
    permisos.asignar(emmy, "coordinacion_academica", unidades.id_de("CMAT"))
    r = client.post(f"/docencia/oferta/{g2026['I']['id']}", headers=HX,
                    data={"asignatura": "MAT-111 · Algebra I", "paralelo": "A", "inscritos": "40"})
    assert "MAT-111" in r.text and "Sin docente" in r.text
    oid = oferta.listar(g2026["I"]["id"])[0]["id"]
    r = client.post(f"/docencia/oferta/{oid}/docentes", headers=HX, data={"usuario": str(emmy), "rol": "titular"})
    assert "Emmy Noether" in r.text and "sin vínculo con la Carrera" in r.text
    assert get_db().q("SELECT accion FROM auditoria WHERE accion = 'asignar_docente'")
    r = client.post("/docencia/gestiones", headers=HX, data={"anio": "2027"})
    assert "VER-2027" in r.text
    assert "Oferta y docentes" in client.get("/docencia/planes").text  # pestañas de la sección
