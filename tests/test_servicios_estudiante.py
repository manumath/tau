"""PLAN §67: servicios nuevos del estudiante. Reutiliza las cuentas y el ingreso de test_portal_estudiante."""
from app.academico import planes
from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from app.estudiantil import mi_plan, tutoria
from tests.conftest import HX, PASS_TEMP, login
from tests.test_portal_estudiante import (_aceptar, _externo, _ingresar, estudiantes_cargados, sofia)  # noqa: F401


def _con_plan(ru="1111111", programa="Licenciatura en Matemática"):
    plan = next(p for p in planes.listar() if p["programa"] == programa)
    get_db().execute("UPDATE estudiante SET plan_id = ? WHERE registro_universitario = ?", [plan["id"], ru])
    return plan


def _aid(sigla):
    return get_db().q("SELECT id FROM asignatura WHERE sigla = ?", [sigla])[0]["id"]


# --- Etapa 1: Mi plan de estudios -----------------------------------------------------------------------------------

def test_mi_plan_marca_y_avance(sofia):
    plan = _con_plan()
    ext = _externo("1111111")
    assert mi_plan.plan_de(ext)["id"] == plan["id"]
    av = mi_plan.avance(ext, plan)
    assert (av["hechas"], av["pct"]) == (0, 0) and av["obligatorias"] > 20
    disponibles = {f["sigla"] for f in av["disponibles"]}
    assert "MAT-111" in disponibles and "MAT-131" not in disponibles            # MAT-131 pide MAT-111
    assert mi_plan.marcar(ext, _aid("MAT-111"), plan["id"]) is True
    av = mi_plan.avance(ext, plan)
    assert av["hechas"] == 1 and "MAT-131" in {f["sigla"] for f in av["disponibles"]}
    assert mi_plan.marcar(ext, _aid("MAT-111"), plan["id"]) is False             # alterna
    assert mi_plan.marcar(ext, 99999, plan["id"]) is None   # no es del plan
    # «Egresado»: el trabajo final no está disponible hasta tener todas las demás obligatorias.
    final = next(f for s in av["semestres"] for f in s["filas"] if f["tipo"] == "trabajo_final")
    assert final["estado"] == "bloqueada"


def test_mi_plan_pantalla_y_privacidad(client, sofia):
    plan = _con_plan()
    r = client.get("/estudiante/plan")
    assert "Mi plan de estudios" in r.text and "obligatorias aprobadas" in r.text and plan["nombre"] in r.text
    assert "Es una ayuda personal" in r.text and "Kardex" in r.text
    aid = _aid("MAT-111")
    r = client.post(f"/estudiante/plan/marca/{aid}", headers=HX)
    assert 'id="mi-plan"' in r.text and "1 de" in r.text
    assert client.post("/estudiante/plan/marca/99999", headers=HX).status_code == 404
    assert not mi_plan.comparte(_externo("1111111"))
    client.post("/estudiante/plan/compartir", headers=HX, data={"comparte": "1"})
    assert mi_plan.comparte(_externo("1111111"))
    client.post("/estudiante/plan/compartir", headers=HX, data={})
    assert not mi_plan.comparte(_externo("1111111"))
    # Sin plan registrado: lo dice.
    get_db().execute("UPDATE estudiante SET plan_id = NULL")
    assert "todavía no está registrado" in client.get("/estudiante/plan").text


def test_el_tutor_ve_el_avance_solo_si_el_estudiante_lo_comparte(client, sofia, estudiantes_cargados):
    _con_plan()
    ext = _externo("1111111")
    emmy = usuarios.por_email("inv@test.cl")["id"]
    from app.comun import vinculos
    vinculos.agregar(emmy, "titular", "2020-01-01")
    assert tutoria.asignar(ext, emmy, None) == []
    mi_plan.marcar(ext, _aid("MAT-111"), mi_plan.plan_de(ext)["id"])
    assert mi_plan.para_tutor(emmy, ext) is None                                  # no lo comparte
    client.post("/estudiante/plan/compartir", headers=HX, data={"comparte": "1"})
    av = mi_plan.para_tutor(emmy, ext)
    assert av and av["hechas"] == 1
    assert mi_plan.para_tutor(usuarios.por_email("admin@test.cl")["id"], ext) is None   # ni la administración
    client.post("/logout")
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get(f"/tutoria/{ext}")
    assert "Avance en su plan" in r.text and "1 de" in r.text
    client.post("/logout")
    login(client, "admin@test.cl", "Admin-clave-123")
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    assert "Avance en su plan" not in client.get(f"/tutoria/{ext}").text            # la Dirección no lo ve


def test_el_menu_del_estudiante_esta_agrupado(client, sofia):
    r = client.get("/estudiante")
    for texto in ("Mi carrera", "Mi plan de estudios", "Servicios", "Comunicados", "Auxiliaturas"):
        assert texto in r.text
    assert "Más" in r.text                                                          # la barra del teléfono


# --- Etapa 2: calendario académico ---------------------------------------------------------------------------------------

def test_el_calendario_reune_las_fechas_del_estudiante(sofia):
    from datetime import date, timedelta
    from app.academico import gestiones
    from app.estudiantil import calendario
    ext = _externo("1111111")
    hoy = date.today()
    g = gestiones.crear_anio(hoy.year + 1)[0]                 # I-(año+1): sus fechas caen a menos de 120 días solo a veces
    get_db().execute("UPDATE gestion_academica SET fecha_inicio = ? WHERE id = ?", [(hoy + timedelta(days=10)).isoformat(), g["id"]])
    # Un evento al que lo convocan, otro para todos, uno de otra persona y uno en borrador.
    u = estudiantes_uid(ext)
    def ev(**k):
        return get_db().t.comunicado.insert(tipo="evento", titulo=k["t"], publica_como="direccion_carrera",
                                            para_todos=k.get("todos", 0), inicio=k.get("inicio"), lugar="Aula 1",
                                            estado=k.get("estado", "publicado"), creado_por=1)["id"]
    manana = (hoy + timedelta(days=1)).strftime("%Y-%m-%dT15:00")
    mio = ev(t="Seminario", inicio=manana)
    ev(t="Feria", inicio=manana, todos=1)
    ev(t="Ajeno", inicio=manana)
    ev(t="Borrador", inicio=manana, estado="borrador")
    get_db().t.comunicado_destinatario.insert(comunicado_id=mio, usuario_id=u)
    get_db().t.convocatoria_auxiliatura.insert(gestion_id=g["id"], modalidad="docencia", numero=1, titulo="Auxiliaturas I",
                                               estado="publicada", cierre=(hoy + timedelta(days=5)).strftime("%Y-%m-%dT18:00"),
                                               examen=(hoy + timedelta(days=9)).strftime("%Y-%m-%dT09:00"), creado_por=1)
    titulos = [e["titulo"] for e in calendario.eventos(ext)]
    assert "Seminario" in titulos and "Feria" in titulos and "Ajeno" not in titulos and "Borrador" not in titulos
    assert any(t.startswith("Cierra la recepción") for t in titulos) and "Inicia I-%d" % (hoy.year + 1) in titulos
    assert titulos == [e["titulo"] for e in sorted(calendario.eventos(ext), key=lambda e: (e["fecha"], e["hora"], e["titulo"]))]
    assert all(e["fecha"] >= hoy.isoformat() for e in calendario.eventos(ext))
    assert calendario.eventos(ext, hoy, hoy) == []


def estudiantes_uid(ext):
    return get_db().q("SELECT usuario_id FROM cuenta_estudiante WHERE externo_id = ?", [ext])[0]["usuario_id"]


def test_pantalla_del_calendario_y_archivo_ics(client, sofia):
    from datetime import date, timedelta
    hoy = date.today()
    inicio = (hoy + timedelta(days=2)).strftime("%Y-%m-%dT15:30")
    get_db().t.comunicado.insert(tipo="evento", titulo="Charla de, prueba; con signos", publica_como="direccion_carrera", para_todos=1,
                                 inicio=inicio, lugar="Auditorio", estado="publicado", creado_por=1)
    r = client.get("/estudiante/calendario")
    assert "Calendario académico" in r.text and "Charla de, prueba; con signos" in r.text and "15:30" in r.text
    assert "30 días" in r.text and "Llevar a mi calendario" in r.text
    r = client.get("/estudiante/calendario.ics")
    assert r.headers["content-type"].startswith("text/calendar") and "attachment" in r.headers["content-disposition"]
    assert "BEGIN:VCALENDAR" in r.text and "SUMMARY:Charla de\\, prueba\\; con signos" in r.text
    assert f"DTSTART:{(hoy + timedelta(days=2)):%Y%m%d}T153000" in r.text and r.text.endswith("END:VCALENDAR\r\n")
    assert "Calendario" in client.get("/estudiante").text


# --- Etapa 3: tutoría desde el estudiante ------------------------------------------------------------------------------

def _con_tutor(ext):
    from app.comun import vinculos
    emmy = usuarios.por_email("inv@test.cl")["id"]
    vinculos.agregar(emmy, "titular", "2020-01-01")
    assert tutoria.asignar(ext, emmy, None) == []
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    return emmy


def test_solicitar_programar_y_atender_una_reunion(sofia, buzon):
    from datetime import datetime, timedelta
    ext = _externo("1111111")
    assert tutoria.solicitar(ext, "academico", "")[0].startswith("Aún no tiene tutor")
    emmy = _con_tutor(ext)
    assert tutoria.solicitar(ext, "x", "")[0].startswith("Elija")
    assert tutoria.solicitar(ext, "academico", "x" * 1001)[0].startswith("El mensaje")
    assert tutoria.solicitar(ext, "academico", "Quisiera hablar de mis materias") == []
    assert "ya tiene una solicitud abierta" in tutoria.solicitar(ext, "otro", "")[0].lower()
    [s] = tutoria.solicitudes_abiertas_de_tutor(emmy)
    assert (s["estado"], s["tema"], s["nombres"]) == ("pendiente", "academico", "Sofía")
    from app.comun import notificaciones
    assert any("Reunión pedida" in n["asunto"] for n in notificaciones.recientes(emmy))
    assert tutoria.programar(s["id"], emmy, "", "")[0].startswith("Indique la fecha")
    assert tutoria.programar(s["id"], emmy, "2020-01-01T10:00", "")[0].startswith("La reunión debe ser en el futuro")
    otro = usuarios.por_email("admin@test.cl")["id"]
    assert tutoria.programar(s["id"], otro, "2099-01-01T10:00", "")[0].startswith("Esa solicitud no está abierta")
    cuando = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT10:00")
    assert tutoria.programar(s["id"], emmy, cuando, "Aula 3") == []
    assert tutoria.solicitudes_de(ext)[0]["estado"] == "programada"
    from app.estudiantil import calendario
    assert any(e["tipo"] == "tutoria" and e["detalle"] == "Aula 3" for e in calendario.eventos(ext))
    assert tutoria.atender(s["id"], emmy) == [] and tutoria.solicitudes_abiertas_de_tutor(emmy) == []
    assert tutoria.solicitar(ext, "otro", "") == [] and tutoria.cancelar(tutoria.solicitudes_de(ext)[0]["id"], ext) == []
    assert tutoria.cancelar(s["id"], ext)[0].startswith("Esa solicitud no está abierta")      # ya atendida


def test_pantallas_de_tutoria_del_estudiante_y_del_tutor(client, sofia):
    from datetime import datetime, timedelta
    ext = _externo("1111111")
    r = client.get("/estudiante/tutoria")
    assert "Todavía no tiene tutor" in r.text
    emmy = _con_tutor(ext)
    tutoria.registrar(ext, emmy, {"fecha": "2026-10-01", "modalidad": "presencial", "tema": "otro",
                                  "resumen": "Texto reservado del tutor", "acuerdos": "", "derivacion": "ninguna"})
    r = client.get("/estudiante/tutoria")
    assert "Mi tutor(a)" in r.text and "1: 1 oct 2026" in r.text and "Texto reservado del tutor" not in r.text
    assert "confidencial" in r.text and "Pedir una reunión" in r.text
    r = client.post("/estudiante/tutoria/solicitud", data={"tema": "economico", "mensaje": "Necesito orientación"},
                    follow_redirects=False)
    assert r.headers["location"] == "/estudiante/tutoria"
    r = client.get("/estudiante/tutoria")
    assert "Económico" in r.text and "Pendiente" in r.text and "Ya tiene una solicitud abierta" in r.text
    sid = tutoria.solicitudes_de(ext)[0]["id"]
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    assert "Pidió una reunión" in client.get("/tutoria").text
    r = client.get(f"/tutoria/{ext}")
    assert "Reunión pedida por el estudiante" in r.text and "Necesito orientación" in r.text
    cuando = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT09:30")
    r = client.post(f"/tutoria/{ext}/solicitudes/{sid}/programar", data={"fecha_reunion": cuando, "respuesta": "Oficina 5"},
                    follow_redirects=False)
    assert r.status_code == 303 and tutoria.solicitudes_de(ext)[0]["estado"] == "programada"
    # Otro docente no toca la solicitud.
    client.post("/logout")
    login(client, "admin@test.cl", "Admin-clave-123")
    assert client.post(f"/tutoria/{ext}/solicitudes/{sid}/atender", follow_redirects=False).status_code == 403
    client.post("/logout")
    _ingresar(client, "sofia@correo.bo", __import__("app.comun.correo", fromlist=["ENVIADOS"]).ENVIADOS)
    r = client.get("/estudiante/tutoria")
    assert "Programada" in r.text and "Oficina 5" in r.text
    client.post(f"/estudiante/tutoria/solicitud/{sid}/cancelar", follow_redirects=False)
    assert tutoria.solicitudes_de(ext)[0]["estado"] == "cancelada"
    assert client.post("/estudiante/tutoria/solicitud/99999/cancelar", follow_redirects=False).status_code == 404


# --- Etapa 4: oportunidades -------------------------------------------------------------------------------------------------

def _dir(client):
    """Entra como la administración con la Dirección de Carrera (quien publica oportunidades)."""
    client.post("/logout")
    login(client, "admin@test.cl", "Admin-clave-123")
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    return usuarios.por_email("admin@test.cl")


def _datos(**k):
    return {"tipo": "beca", "titulo": "Beca de excelencia", "descripcion": "Para estudiantes destacados", "para": "estudiantes",
            "cierre": "2099-12-31", **k}


def test_crear_publicar_postular_y_decidir(sofia):
    from app.servicios import oportunidades as op
    ext = _externo("1111111")
    admin = {**usuarios.por_email("admin@test.cl")}
    permisos.asignar(admin["id"], "direccion_carrera", unidades.id_de("CMAT"))
    assert op.crear(_datos(titulo=""), admin)[1][0].startswith("El título")
    assert "enlace" in op.crear(_datos(enlace="ftp://x"), admin)[1][0].lower()
    assert "cierre" in op.crear(_datos(cierre="mañana"), admin)[1][0].lower()
    oid, errores = op.crear(_datos(enlace="https://ejemplo.org/beca", plazas="2"), admin)
    assert errores == [] and op.obtener(oid)["estado"] == "borrador"
    assert op.para_estudiante(ext) == []                                              # un borrador no se ve
    assert op.postular(oid, ext, "")[0].startswith("Esa oportunidad no está disponible")
    assert op.cambiar_estado(oid, "cerrada", admin)[0].startswith("Ese cambio")
    assert op.cambiar_estado(oid, "publicada", admin) == []
    assert [o["id"] for o in op.para_estudiante(ext)] == [oid] and op.para_estudiante(ext, "empleo") == []
    assert op.postular(oid, ext, "x" * 1001)[0].startswith("El mensaje")
    assert op.postular(oid, ext, "Me interesa") == []
    assert op.postular(oid, ext, "")[0] == "Ya postuló a esta oportunidad."
    [x] = op.postulaciones(oid)
    assert (x["nombres"], x["estado"], x["registro_universitario"]) == ("Sofía", "postulada", "1111111")
    assert op.decidir(x["id"], "pendiente", "", admin)[0].startswith("Elija una decisión")
    assert op.decidir(x["id"], "seleccionada", "Felicitaciones", admin) == []
    assert op.postulacion_de(oid, ext)["estado"] == "seleccionada"
    from app.comun import notificaciones
    uid = estudiantes_uid(ext)
    assert any("Seleccionada" in n["asunto"] for n in notificaciones.recientes(uid))
    assert op.retirar(oid, ext)[0].startswith("No hay una postulación")                # ya decidida
    # Retirar y volver a postular, antes de la decisión.
    oid2, _ = op.crear(_datos(titulo="Pasantía", tipo="pasantia"), admin)
    op.cambiar_estado(oid2, "publicada", admin)
    assert op.postular(oid2, ext, "") == [] and op.retirar(oid2, ext) == [] and op.postular(oid2, ext, "otra vez") == []
    assert op.postulacion_de(oid2, ext)["estado"] == "postulada"
    assert op.cambiar_estado(oid, "cerrada", admin) == []
    assert "cerrada" in op.actualizar(oid, _datos(), admin)[0]


def test_el_empleo_es_para_egresados_y_la_ayudantia_para_el_responsable(sofia):
    from app.investigacion import proyectos
    from app.servicios import oportunidades as op
    ext = _externo("1111111")
    admin = {**usuarios.por_email("admin@test.cl")}
    permisos.asignar(admin["id"], "direccion_carrera", unidades.id_de("CMAT"))
    oid, _ = op.crear(_datos(tipo="empleo", titulo="Analista de datos", para=""), admin)
    assert op.obtener(oid)["para"] == "egresados"                                      # por omisión
    op.cambiar_estado(oid, "publicada", admin)
    assert op.para_estudiante(ext) == []                                              # quien cursa no lo ve
    get_db().execute("UPDATE estudiante SET estado = 'titulado', fecha_titulacion = '2025-12-01' WHERE registro_universitario = '1111111'")
    assert [o["id"] for o in op.para_estudiante(ext)] == [oid]
    # Ayudantía: la publica el responsable del proyecto, no cualquier docente.
    emmy = {**usuarios.por_email("inv@test.cl")}
    pid = proyectos.crear(dict(nombre="Anillos", estado="vigente", fecha_inicio="2026-01-01"), emmy["id"], emmy["id"])
    assert op.puede_publicar(emmy) and op.crear(_datos(tipo="beca"), emmy)[1][0].startswith("Este tipo")
    assert "proyecto" in op.crear(_datos(tipo="ayudantia"), emmy)[1][0]
    otro = usuarios.crear("otro@test.cl", "Otro", "Docente", PASS_TEMP)
    assert op.crear(_datos(tipo="ayudantia", proyecto_id=str(pid)), {**otro, "roles": []})[1][0].startswith("Solo el responsable")
    aid, errores = op.crear(_datos(tipo="ayudantia", titulo="Ayudante en Anillos", proyecto_id=str(pid)), emmy)
    assert errores == [] and op.puede_gestionar(emmy, op.obtener(aid)) and not op.puede_gestionar({**otro, "roles": []}, op.obtener(aid))
    assert [o["id"] for o in op.listar(emmy)] == [aid]


def test_pantallas_de_oportunidades(client, sofia):
    from app.servicios import oportunidades as op
    ext = _externo("1111111")
    r = client.get("/estudiante/oportunidades")
    assert "No hay oportunidades abiertas" in r.text and "Oportunidades" in r.text
    assert client.get("/servicios/oportunidades", follow_redirects=False).status_code == 303   # no es del personal
    admin = _dir(client)
    assert "Oportunidades" in client.get("/").text
    r = client.post("/servicios/oportunidades", data=_datos(titulo="Beca Ejemplo"), follow_redirects=False)
    oid = int(r.headers["location"].rsplit("/", 1)[1])
    assert client.get(f"/servicios/oportunidades/{oid}").status_code == 200
    r = client.post("/servicios/oportunidades", data={"tipo": "beca", "titulo": ""})
    assert "El título es obligatorio" in r.text
    client.post(f"/servicios/oportunidades/{oid}/publicar", follow_redirects=False)
    assert op.obtener(oid)["estado"] == "publicada"
    client.post("/logout")
    _ingresar(client, "sofia@correo.bo", __import__("app.comun.correo", fromlist=["ENVIADOS"]).ENVIADOS)
    r = client.get("/estudiante/oportunidades")
    assert "Beca Ejemplo" in r.text and "Cierra el 31 dic 2099" in r.text
    r = client.get(f"/estudiante/oportunidades/{oid}")
    assert "Postular" in r.text and "Para estudiantes destacados" in r.text
    client.post(f"/estudiante/oportunidades/{oid}/postular", data={"mensaje": "Quiero"}, follow_redirects=False)
    assert "Mi postulación" in client.get(f"/estudiante/oportunidades/{oid}").text
    assert "Postulada" in client.get("/estudiante/oportunidades").text
    assert client.get("/estudiante/oportunidades/99999").status_code == 404
    # El estudiante no entra a las pantallas de quien publica.
    assert client.get(f"/servicios/oportunidades/{oid}", follow_redirects=False).status_code == 303
    client.post("/logout")
    login(client, "admin@test.cl", "Admin-clave-123")
    r = client.get(f"/servicios/oportunidades/{oid}")
    assert "Postulaciones (1)" in r.text and "Sofía" in r.text and "Mamani" in r.text
    pid = op.postulaciones(oid)[0]["id"]
    client.post(f"/servicios/oportunidades/{oid}/postulaciones/{pid}/preseleccionada", data={"nota": "Entrevista"},
                follow_redirects=False)
    assert op.postulacion_de(oid, ext)["estado"] == "preseleccionada" and op.postulacion_de(oid, ext)["nota"] == "Entrevista"
    assert admin


# --- Etapa 5: banco de temas de grado -----------------------------------------------------------------------------------------

def _docente():
    from app.comun import vinculos
    emmy = usuarios.por_email("inv@test.cl")["id"]
    vinculos.agregar(emmy, "titular", "2020-01-01")
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    return {**usuarios.por_email("inv@test.cl")}


def test_publicar_pedir_y_aceptar_un_tema(sofia):
    from app.servicios import temas
    ext = _externo("1111111")
    doc = _docente()
    assert temas.crear({"titulo": ""}, doc)[1][0].startswith("El título")
    assert temas.crear({"titulo": "T", "cupos": "99"}, doc)[1][0].startswith("Los cupos")
    tid, e = temas.crear({"titulo": "Coloraciones de grafos", "descripcion": "Polinomio cromático", "cupos": "1",
                          "modalidad": "tesis"}, doc)
    assert e == [] and temas.disponibles() == []                                       # borrador
    assert temas.solicitar(tid, ext, "")[0] == "Ese tema no está disponible."
    assert temas.cambiar_estado(tid, "publicado", doc) == []
    assert [t["id"] for t in temas.disponibles()] == [tid] and temas.disponibles("grafos") != [] and temas.disponibles("zzz") == []
    assert temas.disponibles(modalidad="proyecto_grado") == []                         # el tema es solo para tesis
    assert temas.solicitar(tid, ext, "Me interesa") == []
    assert temas.solicitar(tid, ext, "")[0] == "Ya pidió este tema."
    [s] = temas.solicitudes(tid)
    assert (s["nombres"], s["estado"], s["registro_universitario"]) == ("Sofía", "pendiente", "1111111")
    from app.comun import notificaciones
    assert any("Pidieron su tema" in n["asunto"] for n in notificaciones.recientes(doc["id"]))
    otro = {**usuarios.crear("otro@test.cl", "Otro", "Docente", PASS_TEMP), "roles": []}
    assert temas.responder(s["id"], True, "", otro)[0].startswith("Esa solicitud no está pendiente")
    assert temas.responder(s["id"], True, "Adelante", doc) == []
    assert temas.aceptado_para(ext, tid)["titulo"] == "Coloraciones de grafos" and temas.disponibles() == []   # sin cupos
    assert temas.responder(s["id"], False, "", doc)[0].startswith("Esa solicitud no está pendiente")
    assert "Aceptaron su pedido" in notificaciones.recientes(estudiantes_uid(ext))[0]["asunto"]
    assert temas.actualizar(tid, {"titulo": "X", "cupos": "1"}, doc) == []
    assert temas.cambiar_estado(tid, "retirado", doc) == [] and temas.actualizar(tid, {"titulo": "Y"}, doc)[0].startswith("No puede")


def test_pantallas_de_temas_y_perfil_con_el_tema(client, sofia):
    from app.servicios import temas
    ext = _externo("1111111")
    doc = _docente()
    tid, _ = temas.crear({"titulo": "Grafos y álgebra", "descripcion": "Un tema", "modalidad": "cualquiera", "cupos": "2"}, doc)
    temas.cambiar_estado(tid, "publicado", doc)
    r = client.get("/estudiante/temas")
    assert "Grafos y álgebra" in r.text and "Temas de grado" in r.text
    r = client.get(f"/estudiante/temas/{tid}")
    assert "Pedirle ser mi tutor(a)" in r.text and "Un tema" in r.text
    client.post(f"/estudiante/temas/{tid}/pedir", data={"mensaje": "Hola"}, follow_redirects=False)
    assert "Pendiente" in client.get(f"/estudiante/temas/{tid}").text
    assert client.get("/estudiante/temas/99999").status_code == 404
    # El docente responde por la pantalla.
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    assert "Grafos y álgebra" in client.get("/servicios/temas").text
    r = client.get(f"/servicios/temas/{tid}")
    assert "Pedidos de tutoría (1)" in r.text and "Mamani" in r.text
    sid = temas.solicitudes(tid)[0]["id"]
    client.post(f"/servicios/temas/{tid}/solicitudes/{sid}/aceptar", data={"respuesta": "Bienvenida"}, follow_redirects=False)
    assert temas.solicitud_de(tid, ext)["estado"] == "aceptada"
    # El estudiante empieza su perfil con el tema: título y tutor ya puestos.
    client.post("/logout")
    _ingresar(client, "sofia@correo.bo", __import__("app.comun.correo", fromlist=["ENVIADOS"]).ENVIADOS)
    assert "Empezar mi perfil con este tema" in client.get("/estudiante/temas").text
    r = client.get(f"/estudiante/grado/nuevo?tema={tid}")
    assert 'value="Grafos y álgebra"' in r.text and "que aceptó Emmy Noether" in r.text
    assert f'value="{doc["id"]}" selected' in r.text or f'value="{doc["id"]}"' in r.text
    assert "Grafos y álgebra" not in client.get("/estudiante/grado/nuevo").text         # sin el tema, el formulario va vacío
    assert "Grafos" not in client.get("/estudiante/grado/nuevo?tema=99999").text
    # Quien no es docente no publica.
    assert client.get("/servicios/temas", follow_redirects=False).status_code == 303
