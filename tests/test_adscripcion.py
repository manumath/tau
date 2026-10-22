"""Cargo y «unidad o grupo» calculados (PLAN.md, sección 27)."""
from app.comun import adscripcion, usuarios, vinculos
from app.investigacion import perfiles, proyectos
from tests.conftest import HX, PASS_TEMP, login
from tests.test_vinculos import hoy  # noqa: F401


def _carga(horas, detalles=None, **acts):
    return {"horas": horas, "detalles": detalles or {},
            "actividades": {k: acts.get(k, 0) for k in vinculos.ACTIVIDADES}}


def test_cargo_segun_la_carga_de_investigacion(app, hoy):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    assert adscripcion.cargo(emmy) is None  # sin vínculo vigente
    vinculos.agregar(emmy, "contratado", "2026-01-01", "2026-06-30", carga=_carga(64, docencia=64))
    vinculos.agregar(emmy, "titular", "2026-07-01", carga=_carga(96, docencia=64, investigacion=32))
    hoy("2026-03-01")
    assert adscripcion.cargo(emmy) == "Docente"
    hoy("2026-07-02")
    assert adscripcion.cargo(emmy) == "Docente Investigador"
    assert perfiles.obtener(emmy)["cargo"] == "Docente Investigador"


def test_unidad_o_grupo_en_orden(app, hoy):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    otra = usuarios.crear("sofia@test.cl", "Sofía", "Kovalévskaya", PASS_TEMP)["id"]
    assert adscripcion.grupos(emmy) == ["Carrera de Matemática"]  # nada más aplica
    vinculos.agregar(emmy, "titular", "2015-01-01", carga=_carga(
        128, {"extension": "Olimpiadas de matemática", "gestion": "Jefatura de estudios", "investigacion": "No se muestra"},
        docencia=32, investigacion=32, extension=32, gestion=32))
    assert adscripcion.grupos(emmy) == ["Olimpiadas de matemática", "Jefatura de estudios"]
    participa = proyectos.crear(dict(nombre="Trompos", estado="vigente"), otra, otra)
    proyectos.agregar_participante(participa, f"i:{emmy}", "co_investigador")
    proyectos.crear(dict(nombre="Anillos", estado="vigente"), emmy, emmy)  # lo dirige
    proyectos.crear(dict(nombre="Terminado", estado="finalizado"), emmy, emmy)  # no cuenta
    assert adscripcion.grupos(emmy) == ["Anillos", "Trompos", "Olimpiadas de matemática", "Jefatura de estudios"]
    assert adscripcion.unidad(emmy) == "Anillos · Trompos · Olimpiadas de matemática · Jefatura de estudios"



def test_el_perfil_no_edita_cargo_ni_unidad(client, app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    client.put("/perfil/datos", headers=HX, data={"nombres": "Emmy", "apellidos": "Noether", "cargo": "Rectora",
                                                  "unidad": "Otra"})
    p = perfiles.obtener(emmy)
    assert p["cargo"] is None and p["unidad"] == "Carrera de Matemática"
    assert "se calculan" in client.get("/perfil").text
