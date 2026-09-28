"""Término del vínculo y carga horaria de los participantes en proyectos (PLAN.md, sección 26)."""
import pytest

from app.comun import usuarios, vinculos
from app.comun.db import get_db
from app.investigacion import carga_proyectos, proyectos
from tests.conftest import HX, PASS_TEMP, login
from tests.test_vinculos import hoy  # noqa: F401


def _carga(horas, **acts):
    return {"horas": horas, "detalle": None, "actividades": {k: acts.get(k, 0) for k in vinculos.ACTIVIDADES}}


@pytest.fixture
def gente(app, hoy):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP, debe_cambiar_pass=False)["id"]
    vinculos.agregar(emmy, "titular", "2015-01-01", carga=_carga(160, docencia=64, investigacion=64, extension=32))
    # Alan: contrato del primer semestre con 64 h/mes de investigación.
    vinculos.agregar(alan, "contratado", "2026-02-01", "2026-06-30",
                     carga=_carga(96, docencia=32, investigacion=64))
    hoy("2026-03-15")

    def proyecto(nombre, clase="investigacion", tipo="institucional"):
        pid = proyectos.crear(dict(nombre=nombre, estado="vigente", fecha_inicio="2026-01-01"), emmy, emmy,
                              tipo=tipo, clase=clase if tipo == "institucional" else None)
        proyectos.agregar_participante(pid, f"i:{alan}", "co_investigador")
        return pid
    return {"emmy": emmy, "alan": alan, "proyecto": proyecto}


def _part(pid, uid):
    return next(x["participante_id"] for x in proyectos.participantes(pid) if x["id"] == uid)


def test_asignar_dentro_de_la_carga_de_investigacion(gente):
    alan, emmy = gente["alan"], gente["emmy"]
    a, b = gente["proyecto"]("Álgebra"), gente["proyecto"]("Lógica")
    pa, pb = _part(a, alan), _part(b, alan)
    assert carga_proyectos.opciones(alan, proyectos.obtener(a)) == [0, 32, 64]
    assert carga_proyectos.asignar(a, pa, 48, emmy) == "La carga en el proyecto es de 0, 32, 64… h/mes."
    assert carga_proyectos.asignar(a, pa, 32, emmy) is None
    assert carga_proyectos.asignar(b, pb, 64, emmy).startswith("Tiene 32 h/mes de investigación libres")
    assert carga_proyectos.asignar(b, pb, 32, emmy) is None
    assert carga_proyectos.disponible(alan, proyectos.obtener(a))["libres"] == 0
    assert carga_proyectos.asignar(a, pa, 64, emmy).startswith("Tiene 32 h/mes")  # sin contar lo propio
    assert carga_proyectos.asignar(a, pa, 0, emmy) is None and carga_proyectos.actual(pa) is None
    # Interacción social: sale de la extensión (Alan no tiene).
    social = gente["proyecto"]("Olimpiadas", clase="interaccion_social")
    assert "no tiene carga de extensión y servicios" in carga_proyectos.asignar(social, _part(social, alan), 32, emmy)
    # Los individuales no asignan carga; los externos tampoco la tienen.
    individual = gente["proyecto"]("Propio", tipo="individual")
    assert carga_proyectos.asignar(individual, _part(individual, alan), 32, emmy) == \
        "Solo los proyectos institucionales asignan carga horaria."
    # La Dirección de Carrera no puede bajar la investigación por debajo de lo asignado.
    v = vinculos.vigente(alan)
    assert "asignadas a proyectos" in vinculos.editar(v["id"], "contratado", "2026-02-01", "2026-06-30",
                                                        carga=_carga(96, docencia=96))[0]


def test_sin_vinculo_figura_sin_carga_y_se_avisa(gente, hoy, buzon):
    alan, emmy = gente["alan"], gente["emmy"]
    a = gente["proyecto"]("Álgebra")
    pa = _part(a, alan)
    carga_proyectos.asignar(a, pa, 64, emmy)
    hoy("2026-07-10")  # terminó el contrato de Alan
    assert carga_proyectos.actual(pa) is None
    carga_proyectos.revisar()
    avisos = carga_proyectos.pendientes(a)
    assert [x["tipo"] for x in avisos] == ["desvinculado"]
    assert any("quedó sin vínculo" in m["Subject"] for m in buzon)
    assert alan in [x["id"] for x in proyectos.participantes(a, solo_vigentes=True)]  # sigue participando
    assert carga_proyectos.historial(pa) == [{"horas": 64, "desde": "2026-03-15", "hasta": "2026-06-30"}]
    carga_proyectos.revisar()
    assert len(carga_proyectos.pendientes(a)) == 1  # un solo aviso
    assert proyectos.n_pendientes(a) == 1

    # Nuevo contrato: la carga no se reasigna sola; el responsable recibe el aviso.
    n = len(buzon)
    vinculos.agregar(alan, "contratado", "2026-08-01", "2026-12-31", carga=_carga(64, docencia=32, investigacion=32))
    hoy("2026-08-05")
    carga_proyectos.revisar()
    assert carga_proyectos.actual(pa) is None
    assert [x["tipo"] for x in carga_proyectos.pendientes(a)] == ["nuevo_vinculo"]  # el de desvinculación se cierra
    assert any("nuevo periodo de vínculo" in m["Subject"] for m in buzon[n:])
    # El responsable decide asignarle carga: el aviso queda atendido.
    assert carga_proyectos.asignar(a, pa, 32, emmy) is None
    assert carga_proyectos.pendientes(a) == [] and carga_proyectos.actual(pa)["horas"] == 32


def test_si_otro_proyecto_asigna_toda_la_carga_no_hay_aviso(gente, hoy):
    alan, emmy = gente["alan"], gente["emmy"]
    a, b = gente["proyecto"]("Álgebra"), gente["proyecto"]("Lógica")
    carga_proyectos.asignar(a, _part(a, alan), 32, emmy)
    hoy("2026-07-10")
    vinculos.agregar(alan, "contratado", "2026-07-20", "2026-12-31", carga=_carga(64, docencia=32, investigacion=32))
    hoy("2026-07-21")
    # Otro proyecto le asigna toda su investigación nueva antes de que el aviso llegue a ver la luz…
    assert carga_proyectos.asignar(b, _part(b, alan), 32, emmy) is None
    carga_proyectos.revisar()
    assert [x["tipo"] for x in carga_proyectos.pendientes(a)] == []
    # …y si el aviso ya existía, desaparece cuando la carga se agota.
    carga_proyectos.asignar(b, _part(b, alan), 0, emmy)
    carga_proyectos.revisar()
    assert [x["tipo"] for x in carga_proyectos.pendientes(a)] == ["nuevo_vinculo"]
    carga_proyectos.asignar(b, _part(b, alan), 32, emmy)
    assert carga_proyectos.pendientes(a) == []


def test_pantallas(client, gente, hoy):
    alan, emmy = gente["alan"], gente["emmy"]
    a = gente["proyecto"]("Álgebra")
    externo_individual = gente["proyecto"]("Propio", tipo="individual")
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get(f"/proyectos/{a}/tab/participantes", headers=HX)
    assert "Carga (h/mes)" in r.text and "64 h/mes de investigación libres de 64" in r.text
    assert "Carga (h/mes)" not in client.get(f"/proyectos/{externo_individual}/tab/participantes", headers=HX).text
    r = client.post(f"/proyectos/{a}/participantes/{_part(a, alan)}/carga", headers=HX, data={"horas": "64"})
    assert carga_proyectos.actual(_part(a, alan))["horas"] == 64
    # Al agregar a alguien del instituto se indica su carga.
    sofia = usuarios.crear("sofia@test.cl", "Sofía", "Kovalévskaya", PASS_TEMP)["id"]
    vinculos.agregar(sofia, "titular", "2010-01-01", carga=_carga(64, investigacion=64))
    form = client.get(f"/proyectos/{a}/participantes/nuevo", headers=HX, params={"ref": f"i:{sofia}"}).text
    assert "Tiene 64 h/mes de investigación libres" in form
    r = client.post(f"/proyectos/{a}/participantes", headers=HX, data={"ref": f"i:{sofia}", "carga": "96"})
    assert "Tiene 64 h/mes" in r.text and sofia not in [x["id"] for x in proyectos.participantes(a)]
    client.post(f"/proyectos/{a}/participantes", headers=HX, data={"ref": f"i:{sofia}", "carga": "32"})
    assert carga_proyectos.actual(_part(a, sofia))["horas"] == 32
    # Aviso en «Pendientes» y «Entendido».
    hoy("2026-07-10")
    carga_proyectos.revisar()
    r = client.get(f"/proyectos/{a}/tab/pendientes", headers=HX)
    assert "Quedó sin vínculo" in r.text
    aviso = carga_proyectos.pendientes(a)[0]["id"]
    client.post(f"/proyectos/{a}/avisos-carga/{aviso}/atender", headers=HX)
    assert carga_proyectos.pendientes(a) == []
    assert {"carga_participante", "atender_aviso_carga"} <= {x["accion"] for x in get_db().q("SELECT accion FROM auditoria")}
