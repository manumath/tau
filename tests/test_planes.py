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


# --- PLAN §65, etapa 3: editor de malla y lista de verificación ----------------------------------------------------

def _borrador_de(programa, modo="copia"):
    from app.academico import reformas
    ids = {p["nombre"]: p["id"] for p in get_db().q("SELECT id, nombre FROM programa")}
    rid, errores = reformas.crear(1, "Plan 2027", "", "2027", {ids[programa]: modo}, [])
    assert not errores
    return get_db().q("SELECT id FROM plan_estudios WHERE reforma_id = ?", [rid])[0]["id"]


def _niveles(pid):
    from app.academico import malla
    return {v["clave"]: v["nivel"] for v in malla.verificar(pid)}


def test_copia_trae_duracion_y_ciclos(app):
    from app.academico import malla
    pid = _borrador_de("Licenciatura en Matemática")
    assert planes.obtener(pid)["duracion_semestres"] == 8
    assert [(c["nombre"], c["semestre_desde"], c["semestre_hasta"]) for c in malla.ciclos(pid)] == [
        ("básico", 1, 4), ("intermedio", 5, 6), ("orientación", 7, 8)]
    assert _niveles(pid)["datos"] == "falta"             # sin resolución
    assert _niveles(pid)["requisitos"] == "falta"        # el plan 2017 trae requisitos que no existen


def test_guardar_y_quitar_filas(app):
    from app.academico import malla
    pid = _borrador_de("Maestría en Matemática", "vacio")
    get_db().execute("UPDATE plan_estudios SET duracion_semestres = 2 WHERE id = ?", [pid])
    assert malla.guardar_fila(pid, None, {"tipo": "obligatoria", "semestre": "1", "sigla": "mat-901",
                                         "nombre": "Topología", "creditos": "6"}, [], 1) == []
    nueva = get_db().q("SELECT * FROM asignatura WHERE sigla = 'MAT-901'")[0]
    assert (nueva["departamento"], nueva["de_la_carrera"]) == ("MAT", 1)
    assert malla.guardar_fila(pid, None, {"tipo": "obligatoria", "semestre": "2", "sigla": "FIS-901",
                                         "nombre": "Física", "creditos": "6"}, ["MAT-901"], 1) == []
    assert get_db().q("SELECT de_la_carrera FROM asignatura WHERE sigla = 'FIS-901'")[0]["de_la_carrera"] == 0
    fis = next(f for f in planes.asignaturas(pid) if f["sigla"] == "FIS-901")
    assert fis["requisitos"] == ["MAT-901"] and fis["ciclo"] is None
    # Errores: duplicada, sigla mal escrita, nombre que contradice al catálogo, requisito ajeno, semestre fuera.
    base = {"tipo": "obligatoria", "semestre": "1", "sigla": "MAT-901", "creditos": "6"}
    assert "ya está en este plan" in malla.guardar_fila(pid, None, base, [], 1)[0]
    assert "debe ser como" in malla.guardar_fila(pid, None, base | {"sigla": "M1"}, [], 1)[0]
    assert "ya existe en el catálogo" in malla.guardar_fila(pid, None, base | {"sigla": "MAT-111", "nombre": "Otro"}, [], 1)[0]
    assert "no está en el plan" in malla.guardar_fila(pid, None, base | {"sigla": "MAT-902", "nombre": "X"}, ["MAT-999"], 1)[0]
    assert "dura 2 semestres" in malla.guardar_fila(pid, None, base | {"sigla": "MAT-902", "nombre": "X", "semestre": "3"}, [], 1)[0]
    assert "es una sigla nueva" in malla.guardar_fila(pid, None, base | {"sigla": "MAT-903"}, [], 1)[0]
    assert get_db().q("SELECT COUNT(*) n FROM asignatura WHERE sigla IN ('MAT-902', 'MAT-903')")[0]["n"] == 0
    # Una sigla del catálogo se reutiliza sin escribir el nombre; quitarla avisa quién la pedía.
    assert malla.guardar_fila(pid, None, {"tipo": "trabajo_final", "semestre": "2", "sigla": "MAT-111", "creditos": "12"},
                              [], 1) == []
    mat901 = next(f for f in planes.asignaturas(pid) if f["sigla"] == "MAT-901")
    assert malla.quitar_fila(pid, mat901["id"], 1) == 1          # FIS-901 lo pedía
    assert "MAT-901" in _niveles_detalle(pid, "requisitos")
    assert malla.quitar_fila(pid, mat901["id"], 1) is None        # ya no está
    # El plan vigente no se toca.
    vigente = _plan("Licenciatura en Matemática")["id"]
    assert malla.guardar_fila(vigente, None, base, [], 1) == ["Solo se edita la malla de un plan en elaboración."]


def _niveles_detalle(pid, clave):
    from app.academico import malla
    return next(v["detalle"] for v in malla.verificar(pid) if v["clave"] == clave)


def test_verificacion_detecta_ciclos_semestres_y_electivas(app):
    from app.academico import malla
    pid = _borrador_de("Maestría en Matemática", "vacio")
    get_db().execute("UPDATE plan_estudios SET duracion_semestres = 3, resolucion = 'HCU 1/2027' WHERE id = ?", [pid])
    f = {"tipo": "obligatoria", "semestre": "1", "creditos": "6"}
    assert malla.guardar_fila(pid, None, f | {"sigla": "MAT-801", "nombre": "A"}, [], 1) == []
    assert malla.guardar_fila(pid, None, f | {"sigla": "MAT-802", "nombre": "B"}, ["MAT-801"], 1) == []
    a = next(x for x in planes.asignaturas(pid) if x["sigla"] == "MAT-801")
    assert malla.guardar_fila(pid, a["id"], f | {"sigla": "MAT-801"}, ["MAT-802"], 1) == []
    assert malla.guardar_fila(pid, None, {"tipo": "casilla_electiva_a", "semestre": "2", "creditos": "6"}, [], 1) == []
    n = _niveles(pid)
    assert n["ciclos_requisitos"] == "falta" and n["semestres"] == "falta" and n["electivas"] == "falta"
    assert "MAT-801 → MAT-802 → MAT-801" in _niveles_detalle(pid, "ciclos_requisitos") or \
        "MAT-802 → MAT-801 → MAT-802" in _niveles_detalle(pid, "ciclos_requisitos")
    assert "3" in _niveles_detalle(pid, "semestres")
    assert not malla.listo_para_vigencia(pid)


def test_plan_listo_para_vigencia(app):
    from app.academico import malla
    pid = _borrador_de("Maestría en Matemática", "vacio")
    get_db().execute("UPDATE plan_estudios SET duracion_semestres = 1, resolucion = 'HCU 1/2027' WHERE id = ?", [pid])
    assert malla.guardar_fila(pid, None, {"tipo": "obligatoria", "semestre": "1", "sigla": "MAT-801", "nombre": "A",
                                         "creditos": "6"}, [], 1) == []
    assert malla.listo_para_vigencia(pid), malla.verificar(pid)


def test_ciclos_del_plan(app):
    from app.academico import malla
    pid = _borrador_de("Licenciatura en Matemática")
    assert "compartir" in malla.guardar_ciclos(pid, [{"nombre": "A", "desde": "1", "hasta": "4"},
                                                     {"nombre": "B", "desde": "4", "hasta": "8"}], 1)[0]
    assert malla.guardar_ciclos(pid, [{"nombre": "Básico", "desde": "1", "hasta": "2"},
                                      {"nombre": "Superior", "desde": "3", "hasta": "8"}, {}], 1) == []
    ciclos = {f["semestre"]: f["ciclo"] for f in planes.asignaturas(pid) if f["semestre"]}
    assert ciclos[1] == ciclos[2] == "Básico" and ciclos[3] == ciclos[8] == "Superior"
    assert [c for _, c, _ in planes.por_semestre(pid)][:3] == ["Básico", "Básico", "Superior"]


def test_importar_csv_de_malla(app):
    from app.academico import malla
    pid = _borrador_de("Licenciatura en Matemática", "vacio")
    n, errores = malla.importar_csv(pid, malla.plantilla_csv(), 1)
    assert errores == [] and n == 4
    assert planes.obtener(pid)["duracion_semestres"] == 8                       # no se acorta
    assert [f["sigla"] for f in planes.asignaturas(pid) if f["sigla"]] == ["MAT-111", "MAT-131", "MAT-392"]
    n, errores = malla.importar_csv(pid, "sigla,nombre,tipo,semestre\nMAT-1,x,y,1\n", 1)
    assert n == 0 and "Faltan columnas" in errores[0]
    mal = malla.plantilla_csv() + "MAT-111,,obligatoria,3,,4,,,,\nXX,,rara,,,,,,,\n"
    n, errores = malla.importar_csv(pid, mal, 1)
    assert n == 0 and any("repetida" in e for e in errores) and any("no es válido" in e for e in errores)
    assert len([f for f in planes.asignaturas(pid) if f["sigla"]]) == 3            # no cambió nada


def test_pantallas_de_la_malla(client, app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    pid = _borrador_de("Maestría en Matemática", "vacio")
    login(client, "inv@test.cl", PASS_TEMP)
    for ruta in (f"/docencia/planes/{pid}/malla", f"/docencia/planes/{pid}/malla/fila/nueva?semestre=1",
                 f"/docencia/planes/{pid}/malla/ciclos", f"/docencia/planes/{pid}/malla/importar"):
        assert client.get(ruta, headers=HX).status_code == 403
    assert client.post(f"/docencia/planes/{pid}/malla/fila", headers=HX, data={"tipo": "obligatoria"}).status_code == 403
    permisos.asignar(emmy, "coordinacion_academica", unidades.id_de("CMAT"))
    r = client.get(f"/docencia/planes/{pid}/malla")
    assert "Para poner en vigencia" in r.text and "Agregar un semestre" in r.text
    assert "Agregar al plan" in client.get(f"/docencia/planes/{pid}/malla/fila/nueva?semestre=1", headers=HX).text
    r = client.post(f"/docencia/planes/{pid}/malla/fila", headers=HX, data={"tipo": "obligatoria", "semestre": "1",
                                                                            "sigla": "x"})
    assert "debe ser como" in r.text
    r = client.post(f"/docencia/planes/{pid}/malla/fila", headers=HX, data={
        "tipo": "obligatoria", "semestre": "1", "sigla": "MAT-801", "nombre": "Análisis", "creditos": "6"})
    assert 'id="malla"' in r.text and "MAT-801" in r.text and "Análisis" in r.text
    fid = next(f["id"] for f in planes.asignaturas(pid) if f["sigla"] == "MAT-801")
    assert "Editar en el plan" in client.get(f"/docencia/planes/{pid}/malla/fila/{fid}", headers=HX).text
    r = client.post(f"/docencia/planes/{pid}/malla/semestre", headers=HX)
    assert "Quinto semestre" in r.text or "semestre" in r.text
    assert "Panel" not in client.get(f"/docencia/planes/{pid}").text
    assert "Para poner en vigencia" in client.get(f"/docencia/planes/{pid}").text and \
        "Editar la malla" in client.get(f"/docencia/planes/{pid}").text
    r = client.post(f"/docencia/planes/{pid}/malla/fila/{fid}/quitar", headers=HX)
    assert "MAT-801" not in r.text
    # Un plan vigente no tiene editor.
    vigente = _plan("Licenciatura en Matemática")["id"]
    assert client.get(f"/docencia/planes/{vigente}/malla").status_code == 404
    assert "Editar la malla" not in client.get(f"/docencia/planes/{vigente}").text


# --- PLAN §65, etapa 4: menciones ----------------------------------------------------------------------------------

def _plan_con_filas():
    from app.academico import malla
    pid = _borrador_de("Maestría en Matemática", "vacio")
    get_db().execute("UPDATE plan_estudios SET duracion_semestres = 2, resolucion = 'HCU 1/2027' WHERE id = ?", [pid])
    for sem, sigla in ((1, "MAT-801"), (1, "MAT-802"), (2, "MAT-803")):
        assert malla.guardar_fila(pid, None, {"tipo": "obligatoria", "semestre": str(sem), "sigla": sigla,
                                             "nombre": f"Materia {sigla}", "creditos": "6"}, [], 1) == []
    return pid, {f["sigla"]: f["id"] for f in planes.asignaturas(pid) if f["sigla"]}


def test_menciones_de_un_plan(app):
    from app.academico import malla, menciones
    pid, ids = _plan_con_filas()
    assert menciones.guardar(pid, None, {"nombre": ""}, 1)[0].startswith("El nombre")
    assert menciones.guardar(pid, None, {"nombre": "Álgebra", "semestre_eleccion": "9"}, 1)[0].startswith("Semestre de elec")
    assert menciones.guardar(pid, None, {"nombre": "Álgebra", "semestre_eleccion": "2", "minimo_asignaturas": "2",
                                        "minimo_medida": "12"}, 1) == []
    assert "ya tiene una mención" in menciones.guardar(pid, None, {"nombre": "Álgebra"}, 1)[0]
    [m] = menciones.listar(pid)
    assert menciones.verificar(pid)["nivel"] == "falta" and "no tiene asignaturas" in menciones.verificar(pid)["detalle"]
    assert menciones.asignar(pid, m["id"], {ids["MAT-801"]: "o", ids["MAT-803"]: "p", 999999: "o"}, 1) == []
    [m] = menciones.listar(pid)
    assert (m["n"], m["total_medida"]) == (2, 12)
    assert [(f["sigla"], f["obligatoria"]) for f in m["asignaturas"]] == [("MAT-801", 1), ("MAT-803", 0)]
    assert menciones.verificar(pid)["nivel"] == "ok"
    assert menciones.de_las_filas(pid)[ids["MAT-801"]] == ["Álgebra"]
    menciones.guardar(pid, m["id"], {"nombre": "Álgebra", "minimo_asignaturas": "3"}, 1)
    assert "pide 3 asignaturas y tiene 2" in menciones.verificar(pid)["detalle"]
    assert not malla.listo_para_vigencia(pid)
    # Quitar una asignatura del plan la saca de la mención; la mención sigue.
    malla.quitar_fila(pid, ids["MAT-803"], 1)
    assert menciones.listar(pid)[0]["n"] == 1
    # Un plan nuevo copia las menciones con sus asignaturas.
    from app.academico import reformas
    pr = get_db().q("SELECT id FROM programa WHERE nombre = 'Maestría en Matemática'")[0]["id"]
    get_db().execute("UPDATE plan_estudios SET estado = 'cerrado' WHERE id = ?", [pid])
    copia = reformas.copiar_plan(pid, pr, "Plan 2037", get_db().q("SELECT reforma_id FROM plan_estudios WHERE id = ?", [pid])[0]["reforma_id"], 2037, None)
    [mc] = menciones.listar(copia)
    assert (mc["nombre"], mc["n"]) == ("Álgebra", 1) and mc["asignaturas"][0]["sigla"] == "MAT-801"
    assert menciones.eliminar(copia, mc["id"], 1) is True and menciones.listar(copia) == []
    assert menciones.listar(pid) != []                                         # la del original no se tocó


def test_pantallas_de_menciones(client, app):
    from app.academico import menciones
    _con_carrera(client)
    pid, ids = _plan_con_filas()
    r = client.get(f"/docencia/planes/{pid}/malla")
    assert "Menciones" in r.text and "tronco común" in r.text
    r = client.post(f"/docencia/planes/{pid}/malla/mencion", headers=HX, data={"nombre": ""})
    assert "El nombre de la mención" in r.text
    r = client.post(f"/docencia/planes/{pid}/malla/mencion", headers=HX, data={"nombre": "Análisis", "mid": ""})
    assert 'id="malla"' in r.text and "Análisis" in r.text
    [m] = menciones.listar(pid)
    assert "Asignaturas de Análisis" in client.get(f"/docencia/planes/{pid}/malla/mencion/{m['id']}/asignaturas",
                                                    headers=HX).text
    r = client.post(f"/docencia/planes/{pid}/malla/mencion/{m['id']}/asignaturas", headers=HX,
                    data={f"pa_{ids['MAT-801']}": "o", f"pa_{ids['MAT-802']}": ""})
    assert "MAT-801" in r.text and menciones.listar(pid)[0]["n"] == 1
    assert "Editar la mención" in client.get(f"/docencia/planes/{pid}/malla/mencion/{m['id']}", headers=HX).text
    assert "Análisis" in client.get(f"/docencia/planes/{pid}").text              # la ficha las muestra
    assert client.post(f"/docencia/planes/{pid}/malla/mencion/{m['id']}/quitar", headers=HX).status_code == 200
    assert menciones.listar(pid) == []
    assert client.post(f"/docencia/planes/{pid}/malla/mencion/99999/quitar", headers=HX).status_code == 404


# --- PLAN §65, etapa 5: vigencia, cierre, equivalencias ------------------------------------------------------------

def _listo(pid):
    """Deja al borrador sin puntos por resolver (resolución puesta y requisitos que no existen, quitados)."""
    from app.academico import malla
    get_db().execute("UPDATE plan_estudios SET resolucion = 'HCU 1/2027' WHERE id = ?", [pid])
    get_db().execute("""DELETE FROM requisito WHERE plan_asignatura_id IN (SELECT id FROM plan_asignatura WHERE plan_id = ?)
                        AND sigla IS NOT NULL AND sigla NOT IN (SELECT a.sigla FROM plan_asignatura pa
                        JOIN asignatura a ON a.id = pa.asignatura_id WHERE pa.plan_id = ?)""", [pid, pid])
    assert malla.listo_para_vigencia(pid), malla.verificar(pid)


def test_poner_en_vigencia_cierra_el_anterior(app):
    from app.academico import vigencia
    pid = _borrador_de("Maestría en Matemática")
    antes = _plan("Maestría en Matemática")["id"]
    assert vigencia.poner_en_vigencia(pid, 1)[0].startswith("Todavía falta")          # sin resolución
    _listo(pid)
    assert vigencia.poner_en_vigencia(pid, 1) == []
    nuevo, viejo = planes.obtener(pid), planes.obtener(antes)
    assert (nuevo["estado"], nuevo["vigente_hasta"]) == ("vigente", None) and nuevo["en_vigencia_en"]
    assert (viejo["estado"], viejo["vigente_hasta"]) == ("cierre", 2026) and viejo["cierre_en"]
    assert "Plan 2027" in viejo["motivo_cierre"]
    assert vigencia.poner_en_vigencia(pid, 1) == ["Solo se pone en vigencia un plan en elaboración."]
    assert pid in [p["id"] for p in planes.listar()]                                  # ya lo ve todo el mundo


def test_reforma_en_vigencia_todo_o_nada(app):
    from app.academico import reformas, vigencia
    ids = {p["nombre"]: p["id"] for p in get_db().q("SELECT id, nombre FROM programa")}
    rid, _ = reformas.crear(1, "Plan 2027", "HCU 1/2027", "2027", {ids["Maestría en Matemática"]: "copia",
                                                                    ids["Licenciatura en Matemática"]: "copia"}, [])
    errores = vigencia.poner_reforma_en_vigencia(rid, 1)
    assert errores and "Licenciatura en Matemática" in errores[0]                     # el plan 2017 trae requisitos rotos
    assert {p["estado"] for p in planes.listar(None)} == {"vigente"}                  # no cambió nada
    for p in get_db().q("SELECT id FROM plan_estudios WHERE reforma_id = ?", [rid]):
        _listo(p["id"])
    assert vigencia.poner_reforma_en_vigencia(rid, 1) == []
    estados = {(p["programa"], p["nombre"]): p["estado"] for p in planes.listar()}
    assert estados[("Licenciatura en Matemática", "Plan 2027")] == "vigente"
    assert estados[("Licenciatura en Matemática", "Plan 2017")] == "cierre"
    # Los programas que no tienen plan en la reforma desaparecen: su plan pasa a cierre (decisión del 13-nov-2026).
    assert estados[("Licenciatura en Matemática Aplicada", "Plan 2017")] == "cierre"
    assert estados[("Maestría en Matemática Aplicada", "Plan 2017")] == "cierre"
    apl = next(p for p in planes.listar() if p["programa"] == "Licenciatura en Matemática Aplicada")
    assert apl["vigente_hasta"] == 2026 and "no continúa en la reforma Plan 2027" in apl["motivo_cierre"]


def test_iniciar_cierre_y_cerrar(app):
    from app.academico import vigencia
    pid = _plan("Maestría en Matemática Aplicada")["id"]
    assert "último ingreso" in vigencia.iniciar_cierre(pid, "2010", "x", 1)[0]
    assert "motivo" in vigencia.iniciar_cierre(pid, "2026", "", 1)[0]
    assert vigencia.iniciar_cierre(pid, "2026", "Resolución HCU 5/2026", 1) == []
    p = planes.obtener(pid)
    assert (p["estado"], p["vigente_hasta"], p["motivo_cierre"]) == ("cierre", 2026, "Resolución HCU 5/2026")
    assert vigencia.iniciar_cierre(pid, "2026", "x", 1) == ["Solo se inicia el cierre de un plan vigente."]
    ext = get_db().t.persona_externa.insert(nombres="Ana", apellidos="Uno")["id"]
    get_db().t.estudiante.insert(externo_id=ext, nivel="maestria", desde=2020, plan_id=pid, estado="cursando")
    assert vigencia.estudiantes_en(pid) == 1
    assert "Quedan 1 estudiantes" in vigencia.cerrar(pid, "", False, 1)[0]
    assert "Indique el motivo" in vigencia.cerrar(pid, "", True, 1)[0]
    assert vigencia.cerrar(pid, "Se reubican en el nuevo plan", True, 1) == []
    p = planes.obtener(pid)
    assert p["estado"] == "cerrado" and p["cerrado_en"] and "Cierre: Se reubican" in p["motivo_cierre"]
    from app.academico import oferta
    assert pid not in [x["id"] for x in get_db().q("SELECT id FROM plan_estudios WHERE estado IN ('vigente', 'cierre')")]
    assert oferta.troncales(2027)                                                     # las licenciaturas siguen


def test_equivalencias_entre_planes(app):
    from app.academico import equivalencias
    pid = _borrador_de("Licenciatura en Matemática", "vacio")
    get_db().execute("UPDATE plan_estudios SET duracion_semestres = 1 WHERE id = ?", [pid])
    from app.academico import malla
    # Una igual (MAT-111, misma sigla), una nueva que reemplaza a MAT-112 y MAT-113 juntas.
    for sigla, nombre in (("MAT-111", ""), ("MAT-190", "Cálculo y geometría")):
        assert malla.guardar_fila(pid, None, {"tipo": "obligatoria", "semestre": "1", "sigla": sigla, "nombre": nombre,
                                             "horas_teoricas": "4"}, [], 1) == []
    ant = equivalencias.anterior(pid)
    assert ant["id"] == _plan("Licenciatura en Matemática")["id"]
    b = equivalencias.brechas(ant["id"], pid)
    estados = {r["fila"]["sigla"]: r["estado"] for r in b["filas"]}
    assert estados["MAT-111"] == "igual" and estados["MAT-112"] == "sin" and b["sin_obligatorias"] > 20
    assert [f["sigla"] for f in b["nuevas"]] == ["MAT-190"]
    ids = {a["sigla"]: a["id"] for a in get_db().q("SELECT id, sigla FROM asignatura")}
    assert "ya está en el nuevo" in equivalencias.crear(ant["id"], pid, [ids["MAT-111"]], [ids["MAT-190"]], "", 1)[0]
    assert equivalencias.crear(ant["id"], pid, [ids["MAT-112"], ids["MAT-113"]], [ids["MAT-190"]], "Se fusionan", 1) == []
    assert "otra equivalencia" in equivalencias.crear(ant["id"], pid, [ids["MAT-112"]], [ids["MAT-190"]], "", 1)[0]
    b = equivalencias.brechas(ant["id"], pid)
    estados = {r["fila"]["sigla"]: r for r in b["filas"]}
    assert estados["MAT-112"]["estado"] == estados["MAT-113"]["estado"] == "equivalente"
    assert estados["MAT-112"]["destino"] == ["MAT-190"] and b["nuevas"] == []
    aviso = next(v for v in malla.verificar(pid) if v["clave"] == "equivalencias")
    assert aviso["nivel"] == "aviso" and "MAT-114" in aviso["detalle"]
    assert equivalencias.eliminar(pid, b["grupos"][0]["id"], 1) and equivalencias.grupos(ant["id"], pid) == []
    # Solo desde un borrador, y contra un plan que no sea borrador.
    assert equivalencias.crear(pid, ant["id"], [], [], "", 1) == ["Las equivalencias se registran desde un plan en elaboración."]


def test_pantallas_de_vigencia_y_equivalencias(client, app):
    from app.academico import vigencia
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    pid = _borrador_de("Maestría en Matemática")
    rid = planes.obtener(pid)["reforma_id"]
    login(client, "inv@test.cl", PASS_TEMP)
    permisos.asignar(emmy, "coordinacion_academica", unidades.id_de("CMAT"))     # elabora, pero no decide
    r = client.get(f"/docencia/planes/{pid}")
    assert "Poner en vigencia" not in r.text and "Equivalencias" in r.text
    r = client.get(f"/docencia/planes/reforma/{rid}")
    assert "Planes de la reforma" in r.text and "Poner en vigencia la reforma" not in r.text
    for ruta in (f"/docencia/planes/{pid}/vigencia", f"/docencia/planes/reforma/{rid}/vigencia"):
        assert client.post(ruta, headers=HX).status_code == 403
    vigente = _plan("Maestría en Matemática")["id"]
    assert client.get(f"/docencia/planes/{vigente}/cierre/iniciar", headers=HX).status_code == 403
    r = client.get(f"/docencia/planes/{pid}/equivalencias")
    assert "Equivalencias con el plan anterior" in r.text and "iguales" in r.text
    r = client.post(f"/docencia/planes/{pid}/equivalencias", headers=HX, data={"origen": str(vigente)})
    assert "al menos una asignatura" in r.text
    # La Dirección de Carrera decide.
    permisos.asignar(emmy, "direccion_carrera", unidades.id_de("CMAT"))
    assert "Poner en vigencia" in client.get(f"/docencia/planes/{pid}").text
    assert "Iniciar el cierre" in client.get(f"/docencia/planes/{vigente}").text
    assert "Iniciar el cierre del plan" in client.get(f"/docencia/planes/{vigente}/cierre/iniciar", headers=HX).text
    assert client.get(f"/docencia/planes/{pid}/cierre/iniciar", headers=HX).status_code == 404   # no es vigente
    r = client.post(f"/docencia/planes/{vigente}/cierre/iniciar", headers=HX, data={"anio": "2026", "motivo": ""})
    assert "resolución o el motivo" in r.text
    r = client.post(f"/docencia/planes/{pid}/vigencia", headers=HX)
    assert r.headers["hx-redirect"] == f"/docencia/planes/{pid}" and planes.obtener(pid)["estado"] == "elaboracion"  # falta resolución
    _listo(pid)
    assert "Cerrar el plan" not in client.get(f"/docencia/planes/{pid}").text
    client.post(f"/docencia/planes/{pid}/vigencia", headers=HX)
    assert planes.obtener(pid)["estado"] == "vigente"
    assert "Cerrar el plan" in client.get(f"/docencia/planes/{vigente}").text
    assert "Quedan" not in client.get(f"/docencia/planes/{vigente}/cierre/cerrar", headers=HX).text
    r = client.post(f"/docencia/planes/{vigente}/cierre/cerrar", headers=HX, data={"motivo": "Sin estudiantes"})
    assert r.headers["hx-redirect"] == f"/docencia/planes/{vigente}" and vigencia.estudiantes_en(vigente) == 0
    assert planes.obtener(vigente)["estado"] == "cerrado"
    assert "Motivo del cierre" in client.get(f"/docencia/planes/{vigente}").text
