"""PLAN §68: servicios para el docente (pendientes, calendario…)."""
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
