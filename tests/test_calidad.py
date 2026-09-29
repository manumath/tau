"""Tablero de calidad de datos (punto 4 de la evaluación, PLAN.md §31)."""
from app.academico import gestiones, oferta
from app.acreditacion import calidad
from app.comun import academicos, permisos, unidades, usuarios, vinculos
from app.investigacion import proyectos
from tests.conftest import PASS_TEMP, login
from tests.test_vinculos import hoy  # noqa: F401


def _por_clave():
    return {c["clave"]: c for c in calidad.revisar()}


def test_chequeos(app, hoy):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    c = _por_clave()
    assert c["investigadores_sin_vinculo"]["n"] == 1  # Emmy, investigadora sin vínculo
    vinculos.agregar(emmy, "titular", None)            # vínculo sin fecha de ingreso ni carga
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP)["id"]
    vinculos.agregar(alan, "interino")                  # dato antiguo: sin ingreso ni término
    c = _por_clave()
    assert c["investigadores_sin_vinculo"]["n"] == 0
    assert [i["texto"] for i in c["sin_termino"]["items"]] == ["Turing, Alan"]
    assert c["sin_carga"]["n"] == 2 and c["sin_ingreso"]["n"] == 2
    assert c["sin_grado"]["n"] == 2 and c["sin_nacimiento"]["n"] == 2
    academicos.agregar_grado(emmy, {"nivel": "doctorado", "anio": 2005})
    academicos.fijar_fecha_nacimiento(emmy, "1980-01-01")
    c = _por_clave()
    assert [i["texto"] for i in c["sin_grado"]["items"]] == ["Turing, Alan"] and c["sin_nacimiento"]["n"] == 1
    assert c["sin_termino"]["items"][0]["href"] == "/admin/usuarios?q=Turing"
    # Docencia: paralelo sin docente ni inscritos.
    por = {g["tipo"]: g for g in gestiones.crear_anio(2026)}
    oferta.agregar(por["II"]["id"], "MAT-111", "A", "", 1)
    c = _por_clave()
    assert c["oferta"]["items"][0]["detalle"] == "sin docente titular y sin inscritos registrados"
    assert c["planes"]["n"] > 0  # los planes 2017 traen observaciones por revisar
    # Proyectos vigentes sin ámbito y de investigación sin línea.
    proyectos.crear(dict(nombre="Anillos", estado="vigente"), emmy, emmy, tipo="institucional")
    c = _por_clave()
    assert [i["texto"] for i in c["sin_ambito"]["items"]] == ["Anillos"]
    assert [i["texto"] for i in c["sin_lineas"]["items"]] == ["Anillos"]
    r = calidad.resumen()
    assert r["chequeos"] == len(calidad.CHEQUEOS) and r["registros"] == sum(x["n"] for x in calidad.revisar())


def test_pantalla_y_permisos(client, app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/informes/calidad").status_code == 403
    assert "Calidad de datos" not in client.get("/").text
    permisos.asignar(emmy, "coordinacion_academica", unidades.id_de("CMAT"))
    r = client.get("/informes/calidad")
    assert r.status_code == 200 and "revisiones con observaciones" in r.text and "Corrige:" in r.text
    assert "Calidad de datos" in client.get("/informes").text
    assert "por completar" in client.get("/").text
