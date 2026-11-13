"""PLAN §68: servicios para el docente (pendientes, calendario…)."""
import re
from datetime import date, timedelta

from app.academico import docente
from app.comun import usuarios, vinculos
from app.comun.db import get_db
from app.estudiantil import tutoria
from tests.conftest import HX, PASS_TEMP, login
from tests.test_portal_estudiante import _externo, estudiantes_cargados, sofia  # noqa: F401
from tests.test_servicios_estudiante import _docente


def test_sin_nada_no_es_docente_ni_tiene_pendientes(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    assert not docente.es_docente({"id": uid}) and docente.pendientes(uid) == [] and docente.eventos(uid) == []


def test_pendientes_de_tutoria_temas_y_vinculo(sofia):
    from app.servicios import temas
    ext = _externo("1111111")
    doc = _docente()
    assert docente.es_docente({"id": doc["id"]})
    assert tutoria.asignar(ext, doc["id"], None) == []
    assert tutoria.solicitar(ext, "academico", "Quisiera hablar") == []
    tid, _ = temas.crear({"titulo": "Grafos", "cupos": "1", "modalidad": "tesis"}, doc)
    temas.cambiar_estado(tid, "publicado", doc)
    assert temas.solicitar(tid, ext, "Me interesa") == []
    p = docente.pendientes(doc["id"])
    assert {x["tipo"] for x in p} == {"tutoria", "tema"} and all(x["href"] for x in p)
    # Un periodo de vínculo que termina pronto también se avisa (y entra en el calendario).
    hoy = date.today()
    get_db().execute("UPDATE vinculo SET fecha_fin = ? WHERE usuario_id = ?", [(hoy + timedelta(days=10)).isoformat(), doc["id"]])
    assert [x["tipo"] for x in docente.pendientes(doc["id"], hoy) if x["tipo"] == "vinculo"] == ["vinculo"]
    assert any(e["tipo"] == "vinculo" for e in docente.eventos(doc["id"], hoy, hoy + timedelta(days=30)))
    # Una solicitud atendida deja de ser pendiente; lo de otra persona nunca aparece.
    assert docente.pendientes(usuarios.por_email("admin@test.cl")["id"]) == []


def test_situacion_segun_la_fecha():
    hoy = date(2026, 11, 13)
    f = lambda d: {"cuando": d}  # noqa: E731
    assert docente.situacion(f(None), hoy) == "normal" and docente.situacion(f("2026-11-12"), hoy) == "vencido"
    assert docente.situacion(f("2026-11-20"), hoy) == "proximo" and docente.situacion(f("2026-11-21"), hoy) == "normal"


def test_pantallas_del_docente(client, sofia):
    doc = _docente()
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/docencia/pendientes")
    assert r.status_code == 200 and "Mis pendientes" in r.text and "No tiene nada pendiente" in r.text
    assert "Mi calendario" in client.get("/docencia/calendario").text
    ics = client.get("/docencia/calendario.ics")
    assert ics.status_code == 200 and ics.text.startswith("BEGIN:VCALENDAR") and "Calendario docente" in ics.text
    assert "/docencia/pendientes" in client.get("/docencia/mia").text and doc


def test_un_estudiante_no_entra(sofia):
    assert sofia.get("/docencia/pendientes", follow_redirects=False).status_code in (303, 403)


# --- Etapa 2: preferencias para la oferta ------------------------------------------------------------------------------------

def _gestion_en_planificacion(anio=2031, tipo="I"):
    from app.academico import gestiones
    g, e = gestiones.crear(anio, tipo, usuarios.por_email("admin@test.cl")["id"])
    assert e is None
    return g


def _asignatura(sigla="MAT-101"):
    r = get_db().q("SELECT id FROM asignatura WHERE sigla = ?", [sigla])
    if r:
        return r[0]["id"]
    get_db().execute("INSERT INTO asignatura (sigla, nombre, departamento) VALUES (?, ?, ?)", [sigla, "Cálculo I", sigla[:3]])
    return get_db().q("SELECT id FROM asignatura WHERE sigla = ?", [sigla])[0]["id"]


def test_guardar_y_leer_preferencias(sofia):
    from app.academico import preferencias
    doc = _docente()
    g = _gestion_en_planificacion()
    a = _asignatura()
    assert preferencias.tiene(g["id"], doc["id"]) is False
    assert preferencias.guardar(g, doc["id"], {a: ("quizas", "")}, [], "")[0].startswith("Elija")
    assert preferencias.guardar(g, doc["id"], {99999: ("prefiere", "")}, [], "")[0].startswith("Una de las")
    assert preferencias.guardar(g, doc["id"], {a: ("prefiere", "x" * 301)}, [], "")[0].startswith("Las notas")
    assert preferencias.guardar(g, doc["id"], {a: ("prefiere", "La dicté tres veces")}, ["lun-manana", "lun-tarde", "zzz"],
                                "Solo puedo martes y jueves") == []
    mio = preferencias.de_persona(g["id"], doc["id"])
    assert mio["materias"][a] == {"nivel": "prefiere", "nota": "La dicté tres veces"}
    assert mio["indisponible"] == {"lun-manana", "lun-tarde"} and mio["comentario"].startswith("Solo")
    assert preferencias.texto_turnos(mio["indisponible"]) == "lunes: mañana y tarde"
    # Guardar de nuevo reemplaza lo anterior.
    assert preferencias.guardar(g, doc["id"], {a: ("no_puede", "")}, [], "") == []
    assert preferencias.de_persona(g["id"], doc["id"])["materias"][a]["nivel"] == "no_puede"
    assert preferencias.por_asignatura(g["id"], a) == {doc["id"]: "no_puede"}
    [p] = preferencias.de_gestion(g["id"])
    assert p["materias"][0]["sigla"] == "MAT-101" and preferencias.sin_indicar(g["id"]) == []


def test_no_se_indica_sin_vinculo_ni_con_la_gestion_activa(sofia):
    from app.academico import preferencias
    g = _gestion_en_planificacion()
    sin = usuarios.por_email("inv@test.cl")["id"]
    assert "vínculo" in preferencias.puede_indicar(sin, g)
    _docente()
    assert preferencias.puede_indicar(sin, g) is None
    get_db().execute("UPDATE gestion_academica SET estado = 'activa' WHERE id = ?", [g["id"]])
    g = {**g, "estado": "activa"}
    assert "ya no está en planificación" in preferencias.puede_indicar(sin, g)
    assert preferencias.guardar(g, sin, {}, [], "")[0].startswith("La gestión ya no")


def test_pendiente_de_indicar_preferencias_y_su_desaparicion(sofia):
    from app.academico import preferencias
    doc = _docente()
    g = _gestion_en_planificacion()
    assert any(x["tipo"] == "preferencias" for x in docente.pendientes(doc["id"]))
    assert preferencias.guardar(g, doc["id"], {}, ["vie-noche"], "") == []
    assert not any(x["tipo"] == "preferencias" for x in docente.pendientes(doc["id"]))


def test_pantallas_de_preferencias_y_selector_de_la_oferta(client, sofia):
    from app.academico import oferta, preferencias
    from app.comun import permisos, unidades
    doc = _docente()
    g = _gestion_en_planificacion()
    a = _asignatura()
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get(f"/docencia/preferencias?gestion={g['id']}")
    assert r.status_code == 200 and "MAT-101" in r.text and "Cálculo I" in r.text
    r = client.post("/docencia/preferencias", data={"gestion": str(g["id"]), f"m_{a}": "prefiere", "turno": ["sab-noche"],
                                                    "comentario": "Hola"}, follow_redirects=False)
    assert r.status_code in (302, 303) and preferencias.de_persona(g["id"], doc["id"])["materias"][a]["nivel"] == "prefiere"
    assert client.get("/docencia/preferencias/todas").status_code == 403           # solo quien arma la oferta
    client.post("/logout")
    login(client, "admin@test.cl", "Admin-clave-123")
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    r = client.get(f"/docencia/preferencias/todas?gestion={g['id']}")
    assert r.status_code == 200 and "MAT-101" in r.text and "sábado: noche" in r.text
    oid, e = oferta.agregar(g["id"], "MAT-101", "A", "", usuarios.por_email("admin@test.cl")["id"])
    assert e == []
    r = client.get(f"/docencia/oferta?gestion={g['id']}")
    assert "(la prefiere)" in r.text


# --- Etapa 3: programa analítico --------------------------------------------------------------------------------------------

DATOS = {"objetivos": "Dominar el cálculo diferencial", "contenido": "1. Límites\n2. Derivadas", "metodologia": "Clases",
         "evaluacion": "Dos parciales", "bibliografia": "Apostol, Calculus"}


def _titular_de(sigla="MAT-111"):
    """El docente de prueba como titular de la asignatura en una gestión en planificación → (docente, asignatura_id, gestión)."""
    from app.academico import oferta
    doc = _docente()
    g = _gestion_en_planificacion(2032, "I")
    oid, e = oferta.agregar(g["id"], sigla, "A", "", doc["id"])
    assert e == [] and oferta.asignar(oid, doc["id"], "titular") == []
    return doc, get_db().q("SELECT id FROM asignatura WHERE sigla = ?", [sigla])[0]["id"], g


def test_escribir_publicar_y_versionar_un_programa(sofia):
    from app.academico import programas
    doc, aid, g = _titular_de()
    otro = usuarios.crear("otro@test.cl", "Otro", "Docente", PASS_TEMP)
    assert "titular" in programas.guardar(aid, g["id"], otro["id"], DATOS)[0]
    assert [m["sigla"] for m in programas.pendientes_de(doc["id"])] == ["MAT-111"]
    assert programas.guardar(aid, g["id"], doc["id"], {**DATOS, "objetivos": "x" * 6001})[0].startswith("Objetivos")
    assert programas.guardar(aid, g["id"], doc["id"], {"metodologia": "Solo esto"}) == []
    assert "Complete antes de publicar" in programas.publicar(aid, g["id"], doc["id"])[0]
    assert programas.guardar(aid, g["id"], doc["id"], DATOS) == [] and programas.publicar(aid, g["id"], doc["id"]) == []
    assert programas.publicado(aid, g["id"])["version"] == 1 and programas.borrador(aid, g["id"]) is None
    assert programas.pendientes_de(doc["id"]) == [] and programas.vigente(aid)["objetivos"].startswith("Dominar")
    # Para cambiar algo se parte de la última versión y se publica otra: la primera se conserva.
    assert programas.partir_de_la_vigente(aid, g["id"], doc["id"]) == []
    assert "borrador" in programas.partir_de_la_vigente(aid, g["id"], doc["id"])[0]
    assert programas.guardar(aid, g["id"], doc["id"], {**DATOS, "evaluacion": "Tres parciales"}) == []
    assert programas.publicar(aid, g["id"], doc["id"]) == []
    assert [v["version"] for v in programas.versiones(aid, g["id"])] == [2, 1]
    assert programas.vigente(aid)["evaluacion"] == "Tres parciales" and aid in programas.con_programa()
    assert programas.cobertura(g["id"])[0]["version"] == 2 and programas.cobertura(g["id"])[0]["titulares"] == "Noether"
    # Una gestión concluida es historial.
    get_db().execute("UPDATE gestion_academica SET estado = 'concluida' WHERE id = ?", [g["id"]])
    assert "concluyó" in programas.guardar(aid, g["id"], doc["id"], DATOS)[0]


def test_descartar_el_borrador(sofia):
    from app.academico import programas
    doc, aid, g = _titular_de()
    assert programas.guardar(aid, g["id"], doc["id"], DATOS) == []
    assert programas.descartar(aid, g["id"], doc["id"]) == [] and programas.borrador(aid, g["id"]) is None
    assert programas.partir_de_la_vigente(aid, g["id"], doc["id"])[0].startswith("Aún no hay")


def test_pantallas_del_programa_y_vista_del_estudiante(client, sofia):
    from app.academico import programas
    from app.comun import permisos, unidades
    from tests.test_servicios_estudiante import _con_plan
    _con_plan()
    doc, aid, g = _titular_de()
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    assert "MAT-111" in client.get("/docencia/programas").text
    r = client.get(f"/docencia/programas/{aid}/{g['id']}")
    assert r.status_code == 200 and "Guardar y publicar" in r.text
    r = client.post(f"/docencia/programas/{aid}/{g['id']}/publicar", data=DATOS, follow_redirects=False)
    assert r.status_code in (302, 303) and programas.publicado(aid, g["id"])["version"] == 1
    assert client.get(f"/docencia/programas/{aid}/{g['id']}").status_code == 200       # otra vez, como autor
    assert client.get("/docencia/programas/cobertura").status_code == 403
    client.post("/logout")
    login(client, "admin@test.cl", "Admin-clave-123")
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    r = client.get(f"/docencia/programas/cobertura?gestion={g['id']}")
    assert r.status_code == 200 and "MAT-111" in r.text and "Versión 1" in r.text
    r = client.get(f"/docencia/programas/{aid}/{g['id']}")                                  # solo lectura para el resto
    assert "Dominar el cálculo" in r.text and "Guardar y publicar" not in r.text
    assert client.post(f"/docencia/programas/{aid}/{g['id']}", data=DATOS, follow_redirects=False).status_code in (302, 303)
    assert programas.borrador(aid, g["id"]) is None                                         # no es titular: no escribió nada


def test_el_estudiante_ve_el_programa_publicado_desde_su_plan(sofia):
    from app.academico import programas
    from tests.test_servicios_estudiante import _con_plan
    _con_plan()
    doc, aid, g = _titular_de()
    assert "Ver el programa" not in sofia.get("/estudiante/plan").text
    assert sofia.get(f"/estudiante/programa/{aid}").status_code == 404                  # aún sin publicar
    assert programas.guardar(aid, g["id"], doc["id"], DATOS) == [] and programas.publicar(aid, g["id"], doc["id"]) == []
    assert "Ver el programa" in sofia.get("/estudiante/plan").text
    r = sofia.get(f"/estudiante/programa/{aid}")
    assert r.status_code == 200 and "Dominar el cálculo" in r.text and "Apostol" in r.text
    assert sofia.get("/estudiante/programa/999999").status_code == 404


# --- Etapa 4: lista de estudiantes por paralelo --------------------------------------------------------------------------------

CSV = ("sigla,paralelo,ru,apellidos,nombres,correo\n"
       "MAT-111,A,2222222,Zeta,Ana,ana@ejemplo.bo\n"
       "MAT-111,A,1111111,Alfa,Beto,\n"
       "MAT-999,A,3333333,Omega,Omar,\n").encode()


def _curso(rol="titular"):
    """El docente de prueba en el paralelo A de MAT-111 de una gestión en planificación → (docente, oferta_id, gestión)."""
    from app.academico import oferta
    doc = _docente()
    g = _gestion_en_planificacion(2033, "II")
    oid, e = oferta.agregar(g["id"], "MAT-111", "A", "", doc["id"])
    assert e == [] and oferta.asignar(oid, doc["id"], rol) == []
    return doc, oid, g


def test_cargar_la_copia_y_ver_la_lista(app):
    from app.academico import listas
    doc, oid, g = _curso("auxiliar")
    admin = usuarios.por_email("admin@test.cl")["id"]
    assert listas.consultar(doc["id"], oid)["estudiantes"] == [] and listas.cargar(b"", g["id"], admin)[1] == ["El archivo está vacío."]
    assert "Faltan columnas" in listas.cargar(b"sigla,ru\nMAT-111,1\n", g["id"], admin)[1][0]
    resumen, errores = listas.cargar(CSV, g["id"], admin)
    assert errores == [] and resumen == {"paralelos": 1, "estudiantes": 2, "omitidos": ["MAT-999 A"]}
    r = listas.consultar(doc["id"], oid)                                           # el auxiliar también la ve
    assert [e["ru"] for e in r["estudiantes"]] == ["1111111", "2222222"] and r["origen"] == "csv"   # por apellido
    assert get_db().q("SELECT 1 FROM auditoria WHERE accion = 'ver_lista_curso' AND usuario_id = ?", [doc["id"]])
    assert listas.consultar(admin, oid) is None                                    # ni la Dirección ve nombres
    otro = usuarios.crear("otro@test.cl", "Otro", "Docente", PASS_TEMP)
    assert listas.consultar(otro["id"], oid) is None
    # Cargar de nuevo reemplaza; una fila incompleta no carga nada.
    assert listas.cargar(b"sigla,paralelo,ru,apellidos,nombres\nMAT-111,A,,Sin,RU\n", g["id"], admin)[1][0].startswith("Línea 2")
    assert len(listas.consultar(doc["id"], oid)["estudiantes"]) == 2
    assert listas.cargar(b"sigla,paralelo,ru,apellidos,nombres\nMAT-111,A,5555555,Nuevo,Uno\n", g["id"], admin)[0]["estudiantes"] == 1
    assert [e["ru"] for e in listas.consultar(doc["id"], oid)["estudiantes"]] == ["5555555"]
    assert listas.cursos_de(doc["id"])[0]["cargados"] == 1 and listas.cargadas(g["id"])[0]["cargados"] == 1


def test_la_copia_se_retira_al_concluir_la_gestion(app):
    from app.academico import listas, semestre
    doc, oid, g = _curso()
    admin = usuarios.por_email("admin@test.cl")["id"]
    assert listas.cargar(CSV, g["id"], admin)[0]["estudiantes"] == 2
    get_db().execute("UPDATE gestion_academica SET estado = 'activa' WHERE id = ?", [g["id"]])
    assert semestre.concluir(g["id"], "Cierre de prueba", admin) == []
    assert get_db().q("SELECT COUNT(*) n FROM lista_curso")[0]["n"] == 0
    assert listas.consultar(doc["id"], oid) is None and listas.cargar(CSV, g["id"], admin)[1][0].startswith("Elija")


def test_proveedor_de_api_sin_guardar_nada(app, monkeypatch):
    import json
    from app.academico import listas
    from app.comun import config
    doc, oid, g = _curso()
    admin = usuarios.por_email("admin@test.cl")["id"]
    monkeypatch.setattr(config, "LISTAS_URL", "https://kardex.ejemplo.bo/api")
    pedidos = []

    def _pedir(url):
        pedidos.append(url)
        return json.dumps({"estudiantes": [{"ru": 77, "apellidos": "Beta", "nombres": "Ana", "correo": None}]}).encode()
    monkeypatch.setattr(listas, "_pedir", _pedir)
    r = listas.consultar(doc["id"], oid)
    assert r["origen"] == "api" and r["estudiantes"][0]["ru"] == "77" and r["cargada_en"] is None
    assert pedidos == ["https://kardex.ejemplo.bo/api/gestiones/II-2033/cursos/MAT-111/A/estudiantes"]
    assert get_db().q("SELECT COUNT(*) n FROM lista_curso")[0]["n"] == 0                  # nada se guarda
    assert "no hace falta" in listas.cargar(CSV, g["id"], admin)[1][0]
    monkeypatch.setattr(listas, "_pedir", lambda url: b"no es json")                      # respuesta ilegible
    r = listas.consultar(doc["id"], oid)
    assert r["estudiantes"] == [] and "no respondió" in r["error"]
    monkeypatch.undo()
    monkeypatch.setattr(config, "LISTAS_URL", "http://externo.ejemplo.bo/api")             # sin https, no sale a la red
    r = listas.lista(oid)
    assert r["error"] and r["estudiantes"] == []


def test_pantallas_de_listas(client, sofia):
    from app.comun import permisos, unidades
    doc, oid, g = _curso()
    client.post("/logout")
    login(client, "admin@test.cl", "Admin-clave-123")
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    assert "MAT-111" in client.get(f"/docencia/listas/cargar?gestion={g['id']}").text
    assert client.get("/docencia/listas/plantilla").status_code == 200
    r = client.post("/docencia/listas/cargar", data={"gestion": str(g["id"])}, files={"archivo": ("lista.csv", CSV, "text/csv")})
    assert r.status_code == 200 and "Se cargaron 2 estudiantes" in r.text and "MAT-999 A" in r.text
    assert client.get(f"/docencia/listas/{oid}").status_code == 403                    # la Dirección no es docente del paralelo
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/docencia/listas")
    assert r.status_code == 200 and "MAT-111" in r.text and "Cargar listas" not in r.text
    r = client.get(f"/docencia/listas/{oid}")
    assert r.status_code == 200 and "Alfa, Beto" in r.text and "1111111" in r.text
    assert client.get("/docencia/listas/cargar").status_code == 403
    assert client.post("/docencia/listas/cargar", data={"gestion": str(g["id"])},
                       files={"archivo": ("lista.csv", CSV, "text/csv")}).status_code == 403


# --- Etapa 5: evaluación docente con transparencia ---------------------------------------------------------------------------

def _evaluacion_abierta(ru="1111111"):
    """Curso con el docente de prueba y un estudiante inscrito; evaluación abierta hoy. → (docente, oid, gestión, eid)."""
    from app.academico import evaluacion, listas
    doc, oid, g = _curso()
    admin = usuarios.por_email("admin@test.cl")["id"]
    get_db().execute("UPDATE gestion_academica SET estado = 'activa' WHERE id = ?", [g["id"]])
    assert listas.cargar(f"sigla,paralelo,ru,apellidos,nombres\nMAT-111,A,{ru},Perez,Sofia\n".encode(), g["id"], admin)[1] == []
    hoy = date.today()
    eid, e = evaluacion.crear(g["id"], hoy.isoformat(), (hoy + timedelta(days=10)).isoformat(), admin)
    assert e == []
    assert evaluacion.anunciar(eid, admin) == []
    get_db().execute("UPDATE evaluacion_docente SET anunciada_en = ? WHERE id = ?", [(hoy - timedelta(days=8)).isoformat() + " 10:00:00", eid])
    assert evaluacion.abrir(eid, admin) == []
    return doc, oid, g, eid


def _respuestas_falsas(eid, oid, n, valor=4):
    """n respuestas ya guardadas (sin pasar por estudiantes) para probar los resultados."""
    for _ in range(n):
        r = get_db().t.evaluacion_respuesta.insert(evaluacion_id=eid, oferta_id=oid)
        for clave, _t in __import__("app.academico.evaluacion", fromlist=["x"]).CRITERIOS:
            get_db().execute("INSERT INTO evaluacion_valor (respuesta_id, criterio, valor) VALUES (?, ?, ?)", [r["id"], clave, valor])


def test_el_minimo_es_el_de_las_encuestas_anonimas():
    from app.academico import evaluacion
    from app.estudiantil import encuestas
    assert evaluacion.MIN_RESPUESTAS == encuestas.MIN_ANONIMO


def test_ciclo_de_la_evaluacion(app):
    from app.academico import evaluacion
    doc, oid, g = _curso()
    admin = usuarios.por_email("admin@test.cl")["id"]
    hoy = date.today()
    assert "ya esté activo" in evaluacion.crear(g["id"], "2033-01-01", "2033-01-10", admin)[1][0]      # en planificación
    get_db().execute("UPDATE gestion_academica SET estado = 'activa' WHERE id = ?", [g["id"]])
    assert evaluacion.crear(g["id"], "2033-01-10", "2033-01-01", admin)[1][0].startswith("El cierre")
    assert evaluacion.crear(g["id"], "", "", admin)[1][0].startswith("Indique")
    eid, e = evaluacion.crear(g["id"], hoy.isoformat(), (hoy + timedelta(days=10)).isoformat(), admin)
    assert e == [] and "ya tiene" in evaluacion.crear(g["id"], "2033-01-01", "2033-01-10", admin)[1][0]
    assert "Solo se abre" in evaluacion.abrir(eid, admin)[0]                      # primero se anuncia
    assert evaluacion.anunciar(eid, admin) == [] and "Solo se anuncia" in evaluacion.anunciar(eid, admin)[0]
    assert "al menos 7 días" in evaluacion.abrir(eid, admin)[0]                   # anticipación
    assert evaluacion.actualizar_fechas(eid, "2033-02-01", "2033-01-01", admin)[0].startswith("El cierre")
    from app.comun import notificaciones
    assert any("Evaluación docente" in n["asunto"] for n in notificaciones.recientes(doc["id"]))
    get_db().execute("UPDATE evaluacion_docente SET anunciada_en = ? WHERE id = ?", [(hoy - timedelta(days=8)).isoformat() + " 10:00:00", eid])
    assert evaluacion.abrir(eid, admin) == [] and evaluacion.estado(evaluacion.obtener(eid)) == "abierta"
    assert evaluacion.eliminar(eid, admin)[0].startswith("Solo se elimina")
    assert evaluacion.guardar_retorno(eid, "x")[0].startswith("El retorno")         # solo cerrada
    # Pasada la fecha de cierre, ya está cerrada aunque nadie la haya cerrado.
    assert evaluacion.estado(evaluacion.obtener(eid), hoy + timedelta(days=11)) == "cerrada"
    assert evaluacion.cerrar(eid, admin) == [] and evaluacion.cerrar(eid, admin)[0].startswith("Solo se cierra")


def test_el_estudiante_inscrito_evalua_una_vez_y_sin_enlace_con_su_respuesta(sofia):
    from app.academico import evaluacion
    doc, oid, g, eid = _evaluacion_abierta()
    ext = _externo("1111111")
    e, cursos = evaluacion.por_evaluar(ext)
    assert e["id"] == eid and [(c["sigla"], c["hecho"]) for c in cursos] == [("MAT-111", False)]
    assert evaluacion.responder(ext, oid, {"dominio": "5"})[0].startswith("Responda todas")
    assert evaluacion.responder(ext, oid, {c: "9" for c, _t in evaluacion.CRITERIOS})[0].startswith("Responda todas")
    todo = {c: "4" for c, _t in evaluacion.CRITERIOS}
    assert evaluacion.responder(ext, oid, todo) == [] and evaluacion.n_respuestas(eid, oid) == 1
    assert "Ya evaluó" in evaluacion.responder(ext, oid, todo)[0] and evaluacion.por_evaluar(ext)[1][0]["hecho"] is True
    # Anonimato: la respuesta no tiene autor ni hora, y la participación no tiene hora ni orden de inserción.
    cols = {c["name"] for c in get_db().q("PRAGMA table_info(evaluacion_respuesta)")}
    assert cols == {"id", "evaluacion_id", "oferta_id"}
    cols = {c["name"] for c in get_db().q("PRAGMA table_info(evaluacion_participacion)")}
    assert cols == {"evaluacion_id", "oferta_id", "externo_id"}
    assert "WITHOUT ROWID" in get_db().q("SELECT sql FROM sqlite_master WHERE name = 'evaluacion_participacion'")[0]["sql"]
    # Quien no está inscrito (otro RU) no puede evaluar.
    otro = _externo("2222222")
    assert "inscritos" in evaluacion.responder(otro, oid, todo)[0]


def test_resultados_solo_desde_el_minimo_y_sin_desglose_que_revele(app):
    from app.academico import evaluacion, oferta
    doc, oid, g, eid = _evaluacion_abierta()
    admin = usuarios.por_email("admin@test.cl")["id"]
    assert evaluacion.resultados_de(eid, doc["id"]) is None                       # abierta: nadie ve resultados
    _respuestas_falsas(eid, oid, 4)
    evaluacion.cerrar(eid, admin)
    r = evaluacion.resultados_de(eid, doc["id"])
    assert r["n"] == 4 and r["suficiente"] is False and r["criterios"] == [] and evaluacion.media_global(r) is None
    _respuestas_falsas(eid, oid, 1, valor=5)
    r = evaluacion.resultados_de(eid, doc["id"])
    assert r["suficiente"] and evaluacion.media_global(r) == 4.2 and r["criterios"][0]["distribucion"][5] == 1
    assert r["paralelos"] == []                                                    # un solo paralelo: sin desglose
    # Con dos paralelos, el desglose solo sale si ambos llegan al mínimo.
    oid2, e = oferta.agregar(g["id"], "MAT-112", "A", "", admin)
    assert e == [] and oferta.asignar(oid2, doc["id"], "titular") == []
    _respuestas_falsas(eid, oid2, 2)
    r = evaluacion.resultados_de(eid, doc["id"])
    assert r["n"] == 7 and r["suficiente"] and r["paralelos"] == []                # el segundo no llega: no se desglosa
    _respuestas_falsas(eid, oid2, 3)
    assert len(evaluacion.resultados_de(eid, doc["id"])["paralelos"]) == 2
    otro = usuarios.crear("otro@test.cl", "Otro", "Docente", PASS_TEMP)
    assert evaluacion.resultados_de(eid, otro["id"])["n"] == 0                     # no ve lo de otro docente


def test_bitacora_contexto_y_retorno(app):
    from app.academico import evaluacion
    doc, oid, g, eid = _evaluacion_abierta()
    admin = usuarios.por_email("admin@test.cl")["id"]
    _respuestas_falsas(eid, oid, 5)
    evaluacion.cerrar(eid, admin)
    evaluacion.registrar_consulta(eid, doc["id"], doc["id"])                       # el propio docente no deja huella
    assert evaluacion.consultas(eid, doc["id"]) == []
    evaluacion.registrar_consulta(eid, doc["id"], admin)
    assert [c["nombres"] for c in evaluacion.consultas(eid, doc["id"])] == [usuarios.por_email("admin@test.cl")["nombres"]]
    assert get_db().q("SELECT 1 FROM auditoria WHERE accion = 'ver_resultados_evaluacion_docente'")
    assert evaluacion.guardar_contexto(eid, doc["id"], "x" * 2001)[0].startswith("El contexto")
    assert evaluacion.guardar_contexto(eid, doc["id"], "Primera vez con 60 estudiantes") == []
    assert evaluacion.contexto(eid, doc["id"]).startswith("Primera") and evaluacion.guardar_contexto(eid, doc["id"], "") == []
    assert evaluacion.contexto(eid, doc["id"]) == ""
    assert "Escriba el retorno" in evaluacion.publicar_retorno(eid, admin)[0]
    assert evaluacion.guardar_retorno(eid, "Reforzaremos la tutoría de Cálculo") == [] and evaluacion.publicar_retorno(eid, admin) == []
    assert [r["id"] for r in evaluacion.retornos_publicados()] == [eid]
    evaluacion.retirar_retorno(eid)
    assert evaluacion.retornos_publicados() == []
    p = evaluacion.participacion(eid)[0]
    assert (p["n"], p["inscritos"], p["suficiente"]) == (5, 1, True)


def test_pantallas_de_evaluacion_del_personal(client, sofia):
    from app.academico import evaluacion
    from app.comun import permisos, unidades
    doc, oid, g, eid = _evaluacion_abierta()
    _respuestas_falsas(eid, oid, 5)
    client.post("/logout")
    login(client, "admin@test.cl", "Admin-clave-123")
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    assert "Administrar la evaluación" in client.get("/docencia/evaluacion").text
    r = client.post(f"/docencia/evaluacion/{eid}/cerrar", follow_redirects=False)
    assert r.status_code in (302, 303) and evaluacion.estado(evaluacion.obtener(eid)) == "cerrada"
    r = client.get("/docencia/evaluacion/gestion")
    assert r.status_code == 200 and "Participación por docente" in r.text and "Hay resultados" in r.text
    assert "Dominio" not in r.text and "Media" not in r.text                         # sin resultados en lista
    r = client.get(f"/docencia/evaluacion/{eid}/docente/{doc['id']}")
    assert r.status_code == 200 and "Demuestra dominio" in r.text and "Media global" in r.text
    assert len(evaluacion.consultas(eid, doc["id"])) == 1                           # la consulta quedó en la bitácora
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/docencia/evaluacion/gestion").status_code == 403
    r = client.get(f"/docencia/evaluacion/{eid}/docente/{doc['id']}")
    assert r.status_code == 200 and "Quién consultó sus resultados" in r.text
    assert client.get(f"/docencia/evaluacion/{eid}/docente/{usuarios.por_email('admin@test.cl')['id']}").status_code == 403
    assert client.post(f"/docencia/evaluacion/{eid}/anunciar", follow_redirects=False).status_code == 403
    r = client.post(f"/docencia/evaluacion/{eid}/contexto", data={"contexto": "Curso numeroso"}, follow_redirects=False)
    assert r.status_code in (302, 303) and evaluacion.contexto(eid, doc["id"]) == "Curso numeroso"


def test_pantallas_de_evaluacion_del_estudiante(sofia):
    from app.academico import evaluacion
    doc, oid, g, eid = _evaluacion_abierta()
    r = sofia.get("/estudiante/evaluacion")
    assert r.status_code == 200 and "MAT-111" in r.text and "Evaluar" in r.text and "Demuestra dominio" in r.text
    assert sofia.get(f"/estudiante/evaluacion/{oid}").status_code == 200
    assert sofia.get("/estudiante/evaluacion/999999").status_code == 403
    r = sofia.post(f"/estudiante/evaluacion/{oid}", data={c: "5" for c, _t in evaluacion.CRITERIOS}, follow_redirects=False)
    assert r.status_code in (302, 303) and evaluacion.n_respuestas(eid) == 1
    assert sofia.get(f"/estudiante/evaluacion/{oid}").status_code == 403           # ya evaluó
    assert "Ya evaluó" in sofia.get("/estudiante/evaluacion").text


# --- Etapa 6: historial y certificados ----------------------------------------------------------------------------------------

def _trabajos(sofia_cliente_ext, doc, otro_id):
    """Un perfil aprobado y un documento final en borrador de Sofía, con el docente de prueba como tutor y otro en el tribunal."""
    db = get_db()
    a = db.t.tramite_grado.insert(externo_id=sofia_cliente_ext, tipo="perfil", titulo="Grafos aleatorios", tutor_id=doc["id"],
                                  estado="aprobado", enviado_en="2033-03-01 10:00:00")["id"]
    b = db.t.tramite_grado.insert(externo_id=sofia_cliente_ext, tipo="final", titulo="Tesis abierta", tutor_id=doc["id"],
                                  estado="en_revision")["id"]
    db.execute("INSERT INTO tribunal_grado (tramite_id, usuario_id) VALUES (?, ?)", [a, otro_id])
    db.execute("INSERT INTO tribunal_grado (tramite_id, usuario_id) VALUES (?, ?)", [b, otro_id])
    return a, b


def test_historial_y_certificados_solo_de_trabajos_concluidos(sofia):
    from app.academico import historial
    doc, oid, g = _curso()
    otro = usuarios.crear("otro@test.cl", "Otro", "Docente", PASS_TEMP)
    a, b = _trabajos(_externo("1111111"), doc, otro["id"])
    h = historial.historial(doc["id"])
    assert [m["sigla"] for m in h["materias"]] == ["MAT-111"] and h["materias"][0]["gestion"] == "II-2033"
    assert {t["id"] for t in h["tutor"]} == {a, b} and h["tribunal"] == [] and h["tutorados"] == {"total": 0, "vigentes": 0}
    certs = historial.elegibles(doc["id"])                          # el documento final sigue en revisión: no se certifica
    assert [(c["tipo"], c["ref"]) for c in certs] == [("tutor_grado", a)] and certs[0]["fecha"] == "2033-03-01"
    assert historial.obtener_cert(doc["id"], "tutor_grado", b) is None and historial.obtener_cert(otro["id"], "tutor_grado", a) is None
    assert [(c["tipo"], c["ref"]) for c in historial.elegibles(otro["id"])] == [("tribunal_grado", a)]
    # El código verifica a la persona y al trámite correctos, y uno inventado no existe.
    v = historial.verificar(certs[0]["codigo"].lower())
    assert v["persona"] == f"{doc['nombres']} {doc['apellidos']}" and v["ref"] == a
    assert historial.verificar("TAU-0000000000") is None and historial.verificar("") is None
    assert historial.codigo("tutor_grado", a, doc["id"]) != historial.codigo("tribunal_grado", a, doc["id"])


def test_certificado_de_tribunal_de_auxiliatura(app):
    from app.academico import historial
    doc, oid, g = _curso()
    admin = usuarios.por_email("admin@test.cl")["id"]
    db = get_db()
    c = db.t.convocatoria_auxiliatura.insert(gestion_id=g["id"], modalidad="docencia", titulo="Auxiliaturas II-2033", creado_por=admin,
                                             estado="publicada")["id"]
    i = db.t.item_auxiliatura.insert(convocatoria_id=c, titulo="MAT-111 Cálculo I")["id"]
    db.execute("INSERT INTO tribunal_auxiliatura (item_id, usuario_id, tipo) VALUES (?, ?, 'docente')", [i, doc["id"]])
    assert historial.elegibles(doc["id"]) == []                       # la convocatoria sigue publicada
    db.execute("UPDATE convocatoria_auxiliatura SET estado = 'concluida' WHERE id = ?", [c])
    [cert] = historial.elegibles(doc["id"])
    assert cert["tipo"] == "tribunal_auxiliatura" and cert["titulo"] == "Auxiliaturas II-2033" and historial.verificar(cert["codigo"])


def test_pantallas_de_historial_y_certificados(client, sofia):
    from app.comun import permisos, unidades
    doc, oid, g = _curso()
    otro = usuarios.crear("otro@test.cl", "Otro", "Docente", PASS_TEMP)
    a, b = _trabajos(_externo("1111111"), doc, otro["id"])
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/docencia/historial")
    assert r.status_code == 200 and "MAT-111" in r.text and "Grafos aleatorios" in r.text and "II-2033" in r.text
    r = client.get("/docencia/certificados")
    assert r.status_code == 200 and "Grafos aleatorios" in r.text and "Tesis abierta" not in r.text
    r = client.get(f"/docencia/certificados/tutor_grado/{a}")
    assert r.status_code == 200 and "Se certifica que" in r.text and "Código de verificación: TAU-" in r.text
    assert client.get(f"/docencia/certificados/tutor_grado/{b}").status_code == 404          # sin concluir
    assert client.get(f"/docencia/certificados/tribunal_grado/{a}").status_code == 404        # no es de su tribunal
    assert client.get("/docencia/certificados/verificar").status_code == 403
    codigo = re.search(r"TAU-[0-9A-F]{10}", r.text).group(0)
    client.post("/logout")
    login(client, "admin@test.cl", "Admin-clave-123")
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    r = client.get(f"/docencia/certificados/verificar?codigo={codigo}")
    assert "Certificado válido" in r.text and "Grafos aleatorios" in r.text
    assert "No existe" in client.get("/docencia/certificados/verificar?codigo=TAU-FFFFFFFFFF").text
    assert get_db().q("SELECT 1 FROM auditoria WHERE accion = 'verificar_certificado_docente'")
