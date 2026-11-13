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


def test_lineas_formativas(app):
    """Migración 0063: cada asignatura de licenciatura tiene su línea formativa; el área sale del archivo o de la
    línea de investigación."""
    p = _plan("Licenciatura en Matemática")
    filas = {f["sigla"]: f for f in planes.asignaturas(p["id"]) if f["sigla"]}
    assert all(f["linea_formativa"] for f in filas.values())
    assert (filas["MAT-111"]["linea_formativa"], filas["MAT-111"]["area"]) == ("Álgebra", "Álgebra")
    assert filas["MAT-111"]["linea"].lower() == "estructuras algebraicas ordenadas"
    assert (filas["MAT-112"]["area"], filas["MAT-112"]["linea"]) == ("Análisis", None)
    assert filas["MAT-114"]["area"] is None  # formación básica, sin área
    assert filas["FIS-137"]["linea_formativa"].startswith("Ciencias Básicas")
    # Volver a cargar el archivo no cambia nada.
    assert importar_planes.cargar_lineas_formativas(get_db().conn) == len(
        list(csv.DictReader(open(importar_planes.CARPETA / "lineas-formativas.csv", encoding="utf-8"))))


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
    # El plan 2017 y el 2027 del mismo programa coexisten; el nuevo nace como borrador (no lo ve cualquiera).
    nombres = [(f["nombre"], f["estado"]) for f in get_db().q(
        "SELECT p.nombre, p.estado FROM plan_estudios p JOIN programa pr ON pr.id = p.programa_id "
        "WHERE pr.nombre = 'Licenciatura en Matemática' ORDER BY p.id DESC")]
    assert nombres == [("Plan 2027", "elaboracion"), ("Plan 2017", "vigente")]
    assert nuevo not in [p["id"] for p in planes.listar()]


def test_pantallas_y_resolucion(client, app):
    p = _plan("Licenciatura en Matemática Aplicada")
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/docencia/planes")
    assert "Licenciatura en Matemática Aplicada" in r.text and "por revisar" in r.text
    r = client.get(f"/docencia/planes/{p['id']}")
    assert "Octavo semestre" in r.text and "MAT-394" in r.text and "la dicta otra unidad" in r.text
    assert "Línea formativa" in r.text and "Fundamentos y Matemática Discreta" in r.text
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


# --- PLAN §65, etapa 1: reformas y estados -------------------------------------------------------------------------

def _borrador(programa="Licenciatura en Matemática", nombre="Plan 2027"):
    db = get_db()
    pid = db.q("SELECT id FROM programa WHERE nombre = ?", [programa])[0]["id"]
    ref = db.t.reforma_curricular.insert(nombre="Reforma 2027", resolucion=None, vigente_desde=2027)["id"]
    return db.t.plan_estudios.insert(programa_id=pid, nombre=nombre, vigente_desde=2027, sistema="horas",
                                     estado="elaboracion", reforma_id=ref)["id"]


def test_los_planes_2017_son_vigentes_de_una_reforma(app):
    todos = planes.listar()
    assert {p["estado"] for p in todos} == {"vigente"} and {p["reforma"] for p in todos} == {"Plan 2017"}
    [(reforma, grupo)] = planes.por_reforma(todos)
    assert reforma["resolucion"] == "HCU 041/2017" and len(grupo) == 4


def test_solo_un_plan_vigente_por_programa(app):
    pid = _borrador()
    import apsw
    import pytest
    with pytest.raises(apsw.ConstraintError):
        get_db().execute("UPDATE plan_estudios SET estado = 'vigente' WHERE id = ?", [pid])


def test_el_borrador_solo_lo_ven_quienes_elaboran(client, app):
    pid = _borrador()
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert pid not in [p["id"] for p in planes.listar(usuarios.por_email("inv@test.cl"))]
    assert "Plan 2027" not in client.get("/docencia/planes").text
    assert "En elaboración" not in client.get("/docencia/planes").text            # ni el filtro
    assert "no existe" in client.get(f"/docencia/planes/{pid}").text
    permisos.asignar(emmy, "coordinacion_academica", unidades.id_de("CMAT"))
    r = client.get("/docencia/planes")
    assert "Plan 2027" in r.text and "En elaboración" in r.text
    assert "Octavo" not in client.get(f"/docencia/planes/{pid}").text            # existe (vacío)
    assert "no existe" not in client.get(f"/docencia/planes/{pid}").text


def test_filtro_por_estado(client, app):
    pid = _borrador()
    get_db().execute("UPDATE plan_estudios SET estado = 'cierre', vigente_hasta = 2026 WHERE id = 1")
    login(client, "admin@test.cl", "Admin-clave-123")
    from app.comun import permisos as p
    p.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    r = client.get("/docencia/planes?estado=cierre")
    assert "En proceso de cierre" in r.text and "Licenciatura en Matemática Aplicada" not in r.text
    assert "Plan 2027" not in r.text
    assert "Plan 2027" in client.get("/docencia/planes?estado=elaboracion").text
    assert "No hay planes" in client.get("/docencia/planes?estado=cerrado").text
    assert pid


def test_los_borradores_no_entran_en_oferta_ni_en_cohortes(app):
    from app.academico import oferta
    from app.estudiantil import importar
    antes = len(oferta.troncales(2027))
    pid = _borrador()
    get_db().execute("""INSERT INTO plan_asignatura (plan_id, asignatura_id, tipo, semestre, horas_teoricas)
                        VALUES (?, (SELECT id FROM asignatura WHERE sigla = 'MAT-111'), 'obligatoria', 1, 4)""", [pid])
    get_db().execute("INSERT INTO asignatura (sigla, nombre, departamento) VALUES ('MAT-900', 'Nueva', 'MAT')")
    get_db().execute("""INSERT INTO plan_asignatura (plan_id, asignatura_id, tipo, semestre)
                        VALUES (?, (SELECT id FROM asignatura WHERE sigla = 'MAT-900'), 'obligatoria', 1)""", [pid])
    assert len(oferta.troncales(2027)) == antes                      # MAT-900 solo está en el borrador
    assert pid not in [p["id"] for p in importar.planes_de_licenciatura()]


# --- PLAN §65, etapa 2: nueva reforma y datos del borrador ---------------------------------------------------------

def _con_carrera(client):
    login(client, "admin@test.cl", "Admin-clave-123")
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    return client


def _prog(nombre):
    return get_db().q("SELECT id FROM programa WHERE nombre = ?", [nombre])[0]["id"]


def test_crear_reforma_copia_vacio_y_programa_nuevo(app):
    from app.academico import reformas
    lic, apl = _prog("Licenciatura en Matemática"), _prog("Licenciatura en Matemática Aplicada")
    mae, mea = _prog("Maestría en Matemática"), _prog("Maestría en Matemática Aplicada")
    estadistica = {"nombre": "Licenciatura en Estadística", "nivel": "licenciatura", "titulo": "Licenciado en Estadística",
                   "sistema": "horas", "inicio": str(_plan("Licenciatura en Matemática")["id"])}
    rid, errores = reformas.crear(1, "Plan 2027", "HCU 1/2027", "2027",
                                  {lic: "copia", apl: "no", mae: "vacio", mea: "no"}, [estadistica])
    assert errores == [] and rid
    nuevos = get_db().q("SELECT p.*, pr.nombre AS programa FROM plan_estudios p JOIN programa pr ON pr.id = p.programa_id "
                        "WHERE p.reforma_id = ?", [rid])
    assert {p["programa"] for p in nuevos} == {"Licenciatura en Matemática", "Maestría en Matemática",
                                               "Licenciatura en Estadística"}
    assert {p["estado"] for p in nuevos} == {"elaboracion"} and {p["vigente_desde"] for p in nuevos} == {2027}
    por = {p["programa"]: p for p in nuevos}
    original = _plan("Licenciatura en Matemática")
    copia = por["Licenciatura en Matemática"]
    def n(pid):
        return get_db().q("SELECT COUNT(*) n FROM plan_asignatura WHERE plan_id = ?", [pid])[0]["n"]
    assert n(copia["id"]) == n(original["id"]) == n(por["Licenciatura en Estadística"]["id"])
    assert n(por["Maestría en Matemática"]["id"]) == 0
    assert copia["total_teoricas"] is None and copia["resolucion"] == "HCU 1/2027"
    def req(pid):
        return get_db().q("SELECT COUNT(*) n FROM requisito r JOIN plan_asignatura pa ON pa.id = r.plan_asignatura_id "
                          "WHERE pa.plan_id = ?", [pid])[0]["n"]
    assert req(copia["id"]) == req(original["id"]) > 0
    assert get_db().q("SELECT titulo FROM programa WHERE nombre = 'Licenciatura en Estadística'")[0]["titulo"]
    assert not planes.listar() or all(p["estado"] != "elaboracion" for p in planes.listar())  # nadie más los ve


def test_crear_reforma_valida(app):
    from app.academico import reformas
    lic = _prog("Licenciatura en Matemática")
    _, e = reformas.crear(1, "", "", "abc", {lic: "copia"}, [])
    assert len(e) == 2
    _, e = reformas.crear(1, "Plan 2017", "", "2027", {lic: "copia"}, [])
    assert "Ya existe una reforma" in e[0]
    _, e = reformas.crear(1, "Plan 2027", "", "2027", {lic: "no"}, [])
    assert "al menos un plan" in e[0]
    _, e = reformas.crear(1, "Plan 2027", "", "2027", {lic: "copia"},
                          [{"nombre": "licenciatura en matemática", "nivel": "licenciatura"}])
    assert "Ya existe un programa" in e[0]
    assert get_db().q("SELECT COUNT(*) n FROM reforma_curricular")[0]["n"] == 1      # nada quedó a medias


def test_asistente_de_reforma_por_rol(client, app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/docencia/planes/reforma/nueva").status_code == 403
    assert client.post("/docencia/planes/reforma/nueva", headers=HX, data={"nombre": "X"}).status_code == 403
    assert "Nueva reforma curricular" not in client.get("/docencia/planes").text
    permisos.asignar(emmy, "coordinacion_academica", unidades.id_de("CMAT"))
    assert "Nueva reforma curricular" in client.get("/docencia/planes").text
    r = client.get("/docencia/planes/reforma/nueva")
    assert "Qué programas tendrá" in r.text and "Licenciatura en Matemática Aplicada" in r.text
    r = client.post("/docencia/planes/reforma/nueva", headers=HX, data={"nombre": "", "anio": "2027"})
    assert "Escriba el nombre de la reforma" in r.text
    datos = {"nombre": "Plan 2027", "anio": "2027", "resolucion": "",
             f"prog_{_prog('Licenciatura en Matemática')}": "copia",
             f"prog_{_prog('Licenciatura en Matemática Aplicada')}": "no",
             f"prog_{_prog('Maestría en Matemática')}": "no", f"prog_{_prog('Maestría en Matemática Aplicada')}": "no",
             "nuevo_nombre": ["", "", ""], "nuevo_nivel": ["licenciatura"] * 3, "nuevo_titulo": ["", "", ""],
             "nuevo_sistema": ["horas"] * 3, "nuevo_inicio": ["vacio"] * 3}
    r = client.post("/docencia/planes/reforma/nueva", headers=HX, data=datos)
    assert r.headers["hx-redirect"] == "/docencia/planes?estado=elaboracion"
    r = client.get("/docencia/planes?estado=elaboracion")
    assert "Reforma Plan 2027" in r.text and "En elaboración" in r.text


def test_editar_y_eliminar_borrador(client, app):
    _con_carrera(client)
    from app.academico import reformas
    lic = _prog("Licenciatura en Matemática")
    rid, _ = reformas.crear(1, "Plan 2027", "", "2027", {lic: "copia"}, [])
    pid = get_db().q("SELECT id FROM plan_estudios WHERE reforma_id = ?", [rid])[0]["id"]
    assert "Datos generales del plan" in client.get(f"/docencia/planes/{pid}/editar", headers=HX).text
    base = {"nombre": "Plan 2027", "vigente_desde": "2027", "sistema": "horas", "semanas_semestre": "18",
            "resolucion": "HCU 7/2027", "titulo": "Licenciado en Matemática", "nota_minima": "51",
            "total_teoricas": "2.500", "total_practicas": "", "total_laboratorio": "", "total_creditos": ""}
    r = client.post(f"/docencia/planes/{pid}/editar", headers=HX, data=base | {"semanas_semestre": "0"})
    assert "Semanas del semestre" in r.text
    r = client.post(f"/docencia/planes/{pid}/editar", headers=HX, data=base)
    assert r.headers["hx-redirect"] == f"/docencia/planes/{pid}"
    p = planes.obtener(pid)
    assert (p["semanas_semestre"], p["resolucion"], p["total_teoricas"]) == (18, "HCU 7/2027", 2500)
    assert get_db().q("SELECT titulo FROM programa WHERE id = ?", [lic])[0]["titulo"] == "Licenciado en Matemática"
    # Un plan vigente no se edita ni se elimina por aquí.
    vigente = _plan("Licenciatura en Matemática")["id"]
    assert client.get(f"/docencia/planes/{vigente}/editar", headers=HX).status_code == 404
    assert client.post(f"/docencia/planes/{vigente}/eliminar", headers=HX).status_code == 404
    assert planes.obtener(vigente)
    r = client.post(f"/docencia/planes/{pid}/eliminar", headers=HX)
    assert r.headers["hx-redirect"] == "/docencia/planes?estado=elaboracion"
    assert planes.obtener(pid) is None
    assert get_db().q("SELECT COUNT(*) n FROM reforma_curricular WHERE id = ?", [rid])[0]["n"] == 0   # sin planes
    assert get_db().q("SELECT COUNT(*) n FROM plan_asignatura WHERE plan_id = ?", [pid])[0]["n"] == 0
