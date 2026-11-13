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
