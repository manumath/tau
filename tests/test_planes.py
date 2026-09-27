"""Fase 3, paso 3.1: planes de estudio 2017 cargados por la migración 0028, con sus observaciones."""
import csv

from app.academico import importar_planes, planes
from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login


def _plan(programa):
    return next(p for p in planes.listar() if p["programa"] == programa)


def test_cuatro_planes_cargados(app):
    listado = {p["programa"]: p for p in planes.listar()}
    assert list(listado) == ["Licenciatura en Matemática", "Licenciatura en Matemática Aplicada",
                             "Maestría en Matemática", "Maestría en Matemática Aplicada"]
    assert {p["resolucion"] for p in listado.values()} == {"HCU 041/2017"}
    assert listado["Licenciatura en Matemática"]["n_asignaturas"] == 95   # 101 filas − 5 casillas − 1 repetida
    assert listado["Maestría en Matemática"]["n_asignaturas"] == 28      # 5 + tesis + 22 electivas
    asig = get_db().q("SELECT COUNT(*) n, SUM(de_la_carrera) propias FROM asignatura")[0]
    assert (asig["n"], asig["propias"]) == (123, 92)
    assert get_db().q("SELECT de_la_carrera FROM asignatura WHERE sigla = 'FIS-137'")[0]["de_la_carrera"] == 0


def test_estructura_del_plan(app):
    p = _plan("Licenciatura en Matemática")
    semestres = planes.por_semestre(p["id"])
    assert [s for s, _, _ in semestres] == list(range(1, 9))
    assert [c for _, c, _ in semestres][:5:4] == ["básico", "intermedio"]
    octavo = {f["sigla"] or f["tipo"]: f for f in semestres[7][2]}
    assert octavo["MAT-399"]["tipo"] == "trabajo_final" and octavo["MAT-399"]["requisitos"] == ["Egresado"]
    assert (octavo["MAT-399"]["horas_teoricas"], octavo["MAT-399"]["horas_practicas"],
            octavo["MAT-399"]["horas_laboratorio"]) == (4, 20, 10)
    assert sum(f["tipo"] == "casilla_electiva_b" for f in semestres[7][2]) == 2
    electivas = planes.electivas(p["id"])
    assert set(electivas) == {"electiva_a", "electiva_b"} and len(electivas["electiva_a"]) == 31  # 32 filas, MAT-278 repetida
    segundo = {f["sigla"]: f for f in semestres[1][2]}
    assert segundo["MAT-131"]["requisitos"] == ["MAT-111"]
    # Los totales teóricos y prácticos coinciden con el documento; el de laboratorio no.
    assert planes.totales(p["id"]) == {"teóricas": (2560, 2560), "prácticas": (2040, 2040),
                                       "de laboratorio": (720, 680)}
    m = _plan("Maestría en Matemática")
    assert planes.totales(m["id"]) == {"en créditos": (None, 60)}  # 5×6 + 3 electivas×6 + tesis 12


def test_observaciones_marcadas(app):
    def detalles(programa):
        return sorted(o["tipo"] for o in planes.observaciones(_plan(programa)["id"]))
    assert detalles("Licenciatura en Matemática") == ["documento", "documento", "documento", "duplicada",
                                                     "requisito", "requisito", "totales"]
    textos = " ".join(o["detalle"] for o in planes.observaciones(_plan("Licenciatura en Matemática Aplicada")["id"]))
    assert "Intiligencia" in textos and "1.080" in textos and "1.160" in textos and "MAT-241" in textos
    assert detalles("Maestría en Matemática") == []
    assert detalles("Maestría en Matemática Aplicada") == ["nombre", "nombre", "nombre"]  # «Algebra» sin tilde


def test_carga_idempotente(app):
    assert importar_planes.cargar_carpeta(get_db().conn) == []  # ya estaban: no se duplican


def test_carga_detecta_requisito_inexistente(app, tmp_path):
    carpeta = tmp_path / "planes"
    carpeta.mkdir()
    with open(carpeta / "planes.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["archivo", "programa", "nivel", "plan", "resolucion", "vigente_desde", "sistema",
                    "semanas_semestre", "horas_por_credito", "nota_minima", "total_teoricas", "total_practicas",
                    "total_laboratorio", "total_creditos"])
        w.writerow(["nuevo.csv", "Licenciatura en Matemática", "licenciatura", "Plan 2027", "", "2027", "horas",
                    "20", "", "51", "160", "", "", ""])
    with open(carpeta / "nuevo.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sigla", "nombre", "tipo", "semestre", "ciclo", "horas_teoricas",
                                             "horas_practicas", "horas_laboratorio", "creditos", "requisitos"])
        w.writerow(["MAT-111", "Algebra I", "obligatoria", "1", "básico", "4", "2", "", "", ""])
        w.writerow(["MAT-900", "Nueva", "obligatoria", "2", "básico", "4", "2", "", "", "MAT-111;MAT-999"])
    [nuevo] = importar_planes.cargar_carpeta(get_db().conn, carpeta)
    tipos = sorted(o["tipo"] for o in planes.observaciones(nuevo))
    assert tipos == ["requisito"]  # 8 h × 20 = 160 teóricas: coincide
    assert "MAT-999" in planes.observaciones(nuevo)[0]["detalle"]
    # El plan 2017 y el 2027 del mismo programa coexisten.
    assert [p["nombre"] for p in planes.listar() if p["programa"] == "Licenciatura en Matemática"] == [
        "Plan 2027", "Plan 2017"]


def test_pantallas_y_resolucion(client, app):
    p = _plan("Licenciatura en Matemática Aplicada")
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/docencia/planes")
    assert "Licenciatura en Matemática Aplicada" in r.text and "por revisar" in r.text
    r = client.get(f"/docencia/planes/{p['id']}")
    assert "Octavo semestre" in r.text and "MAT-394" in r.text and "la dicta otra unidad" in r.text
    assert "No coincide" in r.text and "Marcar resuelta" not in r.text  # un investigador solo consulta
    oid = next(o["id"] for o in planes.observaciones(p["id"]) if o["tipo"] == "totales")
    assert client.post(f"/docencia/planes/observaciones/{oid}/resolver", headers=HX,
                       data={"resolucion": "x"}).status_code == 403
    permisos.asignar(emmy, "direccion_carrera", unidades.id_de("CMAT"))
    r = client.post(f"/docencia/planes/observaciones/{oid}/resolver", headers=HX, data={"resolucion": ""})
    assert "Indique cómo se resolvió" in r.text
    r = client.post(f"/docencia/planes/observaciones/{oid}/resolver", headers=HX,
                    data={"resolucion": "Confirmado: el total correcto es 1.160."})
    assert "Resuelta" in r.text and "Confirmado: el total correcto es 1.160." in r.text
    assert planes.observacion(oid)["estado"] == "resuelta"
