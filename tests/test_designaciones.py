"""PLAN §70, etapa 5: invitados, designaciones, informe final y documentación (arts. 6, 13, 22, 23, 25 y 27 del reglamento de 2023)."""
from datetime import date, datetime, timedelta, timezone

from app.comun import notificaciones
from app.comun.db import get_db
from app.servicios import auxiliaturas as aux
from app.servicios import designaciones as des
from tests.test_auxiliaturas_reglamento import _antigua, _primera_concluida  # noqa: F401
from tests.test_servicios import (  # noqa: F401
    _como, _como_estudiante, _estudiante, convocatoria, gente)

NOTAS = {"Sofía": ("no_seleccionada", 12, 20, 20),       # 52: de 51 a 55
         "Luis": ("no_seleccionada", 14, 20, 20),        # 54
         "Rosa": ("no_seleccionada", 10, 20, 20)}        # 50: no llega


def _segunda_concluida(gente, convocatoria, plazas=2, resultados=None):
    """La segunda convocatoria concluida, con los postulantes de `resultados` (nombre → estado y notas de méritos, escrito y oral)."""
    db = get_db()
    primera = _primera_concluida(gente, convocatoria, cubiertas=0, plazas=plazas)
    nuevo, errores = aux.generar_segunda(primera["id"], gente["dir"]["id"])
    assert errores == []
    [item] = aux.items(nuevo)
    pids = {}
    for nombre, (estado, m, e, o) in (resultados or NOTAS).items():
        pid = db.t.postulacion_auxiliatura.insert(item_id=item["id"], externo_id=gente[nombre]["externo"], estado=estado)["id"]
        for fase, v in (("meritos", m), ("escrito", e), ("oral", o)):
            db.t.calificacion_auxiliatura.insert(postulacion_id=pid, fase=fase, miembro_id=gente["doc1"]["id"], valor=v)
        pids[nombre] = pid
    db.execute("UPDATE item_auxiliatura SET fase = 'concluido' WHERE id = ?", [item["id"]])
    db.execute("UPDATE convocatoria_auxiliatura SET estado = 'concluida' WHERE id = ?", [nuevo])
    db.execute("INSERT INTO fase_auxiliatura (item_id, fase) VALUES (?, 'oral')", [item["id"]])
    return nuevo, aux.item(item["id"]), pids


# --- Invitados (arts. 6 y 13) ---------------------------------------------------------------------------------------------------

def test_candidatos_a_invitado_son_los_de_51_a_55_por_puntaje(app, gente, convocatoria):
    _, it, _ = _segunda_concluida(gente, convocatoria)
    assert [(p["nombres"], p["total"]) for p in des.candidatos(it)] == [("Luis", 54), ("Sofía", 52)]      # Rosa, con 50, no
    assert des.puede_invitar(it)


def test_solo_se_invita_en_la_segunda_convocatoria_concluida_con_plazas_libres(app, gente, convocatoria):
    nuevo, it, _ = _segunda_concluida(gente, convocatoria, plazas=2, resultados={"Sofía": ("titular", 20, 25, 25), "Luis": NOTAS["Luis"]})
    primera = aux.items(aux.obtener(nuevo)["primera_id"])[0]
    assert not des.puede_invitar(primera)                                      # la primera convocatoria no
    assert des.generar_invitaciones(primera, 1) == ["Solo se invita en una segunda convocatoria concluida que dejó plazas sin cubrir."]
    assert des.puede_invitar(it)                                               # una de las dos plazas sigue libre
    get_db().execute("UPDATE postulacion_auxiliatura SET estado = 'titular' WHERE item_id = ?", [it["id"]])
    assert not des.puede_invitar(it)                                           # con las dos plazas cubiertas ya no


def test_con_el_reglamento_antiguo_no_se_invita(app, gente, convocatoria):
    _, it, _ = _segunda_concluida(gente, convocatoria)
    assert des.puede_invitar(it)
    _antigua(it["convocatoria_id"])
    assert not des.puede_invitar(it) and des.generar_invitaciones(it, 1)[0].startswith("Solo se invita")


def test_se_invita_por_puntaje_y_se_avisa_a_cada_uno(app, gente, convocatoria):
    _, it, _ = _segunda_concluida(gente, convocatoria)
    assert des.generar_invitaciones(it, gente["dir"]["id"]) == []
    assert [(v["nombres"], v["orden"], v["origen"], v["puntaje"], v["estado"]) for v in des.invitaciones(it["id"])] == \
        [("Luis", 1, "postulante", 54, "pendiente"), ("Sofía", 2, "postulante", 52, "pendiente")]
    assert any(n["asunto"].startswith("Invitación a ser auxiliar") for n in notificaciones.todas(gente["Luis"]["uid"]))
    assert not any("Invitación" in n["asunto"] for n in notificaciones.todas(gente["Rosa"]["uid"]))
    assert des.generar_invitaciones(it, gente["dir"]["id"]) == ["No hay postulantes con 51 a 55 puntos por invitar."]


def test_aceptar_una_invitacion_designa_al_invitado_y_ocupa_la_plaza(app, gente, convocatoria):
    _, it, _ = _segunda_concluida(gente, convocatoria, plazas=1)
    des.generar_invitaciones(it, 1)
    luis, sofia = des.invitaciones(it["id"])
    assert des.cubiertas(it) == 0
    assert des.responder_invitacion(luis["id"], True) == []
    assert des.cubiertas(it) == 1 and not des.puede_invitar(it)
    [d] = [x for x in get_db().q("SELECT * FROM designacion_auxiliatura")]
    assert (d["categoria"], d["externo_id"], d["invitacion_id"]) == ("invitado", gente["Luis"]["externo"], luis["id"])
    assert des.responder_invitacion(sofia["id"], True) == ["Las plazas de este ítem ya están cubiertas."]
    assert des.responder_invitacion(luis["id"], False) == ["La invitación ya se respondió."]
    assert des.responder_invitacion(sofia["id"], False) == [] and des.invitacion(sofia["id"])["estado"] == "rechazada"


def test_a_los_mejores_estudiantes_se_invita_solo_si_los_de_51_a_55_no_aceptan(app, gente, convocatoria):
    elena = _estudiante("Elena", "elena@correo.bo", "106")
    _, it, _ = _segunda_concluida(gente, convocatoria, plazas=1)
    assert "Primero se invita a quienes obtuvieron de 51 a 55 puntos" in des.invitar_mejor_estudiante(it, "106", "", 1)[0]
    des.generar_invitaciones(it, 1)
    assert "Primero se invita" in des.invitar_mejor_estudiante(it, "106", "", 1)[0]          # aún pendientes
    for v in des.invitaciones(it["id"]):
        assert des.responder_invitacion(v["id"], False) == []
    assert des.invitar_mejor_estudiante(it, "999", "", 1) == ["No hay un estudiante con ese registro universitario."]
    assert des.invitar_mejor_estudiante(it, "103", "", 1) == ["Quien integra la comisión de este ítem no puede ser invitado."]   # Ana, del tribunal
    assert des.invitar_mejor_estudiante(it, "106", "Promedio 82, últimas dos gestiones (Kardex)", gente["dir"]["id"]) == []
    v = des.invitaciones(it["id"])[-1]
    assert (v["origen"], v["orden"], v["nota"], v["ru"], v["estado"]) == ("mejor_estudiante", 3, "Promedio 82, últimas dos gestiones (Kardex)", "106", "pendiente")
    assert des.invitar_mejor_estudiante(it, "106", "", 1) == ["Ya se invitó a ese estudiante."]
    assert [x["item_titulo"] for x in des.invitaciones_de(elena["externo"])] == [it["titulo"]]
    assert des.responder_invitacion(v["id"], True) == [] and des.cubiertas(it) == 1


# --- Designaciones, documentos y memorándum (arts. 23, 25 y 26) ----------------------------------------------------------------

def test_cada_titular_tiene_su_designacion_con_los_documentos_por_recibir(app, gente, convocatoria):
    nuevo, it, pids = _segunda_concluida(gente, convocatoria, plazas=2, resultados={"Sofía": ("titular", 20, 25, 25), "Luis": ("titular", 18, 25, 25)})
    lista = des.designaciones(nuevo)
    assert [(d["nombres"], d["categoria"], len(d["faltan"])) for d in lista] == [("Luis", "titular", 3), ("Sofía", "titular", 3)]
    assert des.designaciones(nuevo) == lista and len(get_db().q("SELECT * FROM designacion_auxiliatura")) == 2        # no se duplican
    assert "Certificación de no tener deudas" in lista[0]["faltan"][0]


def test_una_convocatoria_antigua_no_genera_designaciones(app, gente, convocatoria):
    nuevo, it, _ = _segunda_concluida(gente, convocatoria, plazas=1, resultados={"Sofía": ("titular", 20, 25, 25)})
    _antigua(nuevo)
    assert des.designaciones(nuevo) == [] and get_db().q("SELECT * FROM designacion_auxiliatura") == []


def test_documentos_y_memorandum_del_ganador(app, gente, convocatoria):
    nuevo, it, _ = _segunda_concluida(gente, convocatoria, plazas=1, resultados={"Sofía": ("titular", 20, 25, 25)})
    [d] = des.designaciones(nuevo)
    ok = {"cert_deudas": "2026-11-16", "cert_procesos": "2026-11-16", "sigep": "2026-11-17", "memorandum": " MEM 45/2026 ",
          "memorandum_fecha": "2026-11-30", "inicio": "2027-03-01", "fin": "2027-07-31"}
    assert des.guardar_designacion(d["id"], ok) == []
    [d] = des.designaciones(nuevo)
    assert d["faltan"] == [] and d["memorandum"] == "MEM 45/2026" and (d["inicio"], d["fin"]) == ("2027-03-01", "2027-07-31")
    assert "1 o el 15" in des.guardar_designacion(d["id"], {**ok, "inicio": "2027-03-02"})[0]
    assert des.guardar_designacion(d["id"], {**ok, "inicio": "2027-03-15"}) == []
    assert des.guardar_designacion(d["id"], {**ok, "fin": "2027-02-01"}) == ["El fin de la designación no puede ser anterior al inicio."]
    assert des.guardar_designacion(d["id"], {**ok, "sigep": "ayer"}) == ["Las fechas van como AAAA-MM-DD."]
    assert des.guardar_designacion(9999, ok) == ["No se encontró la designación."]
    assert des.guardar_designacion(d["id"], {}) == [] and des.designaciones(nuevo)[0]["faltan"] != []                # en blanco: se borra


def test_plazo_de_72_horas_para_los_documentos(app, gente, convocatoria):
    nuevo, it, _ = _segunda_concluida(gente, convocatoria, plazas=1, resultados={"Sofía": ("titular", 20, 25, 25)})
    concluido = des.concluido_en(nuevo)
    assert abs((des.limite_documentos(nuevo) - (concluido + timedelta(hours=72))).total_seconds()) < 1
    assert not des.documentos_vencidos(nuevo)
    assert des.documentos_vencidos(nuevo, datetime.now() + timedelta(days=4))
    get_db().execute("UPDATE fase_auxiliatura SET cerrada_en = ?", [(datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")])
    assert des.documentos_vencidos(nuevo)


# --- Informe final y documentación (arts. 22 y 27) -----------------------------------------------------------------------------

def test_informe_final_en_diez_dias(app, gente, convocatoria):
    nuevo, it, _ = _segunda_concluida(gente, convocatoria)
    c = aux.obtener(nuevo)
    ok, texto = des.aviso_informe(c)
    assert ok is True and "debe entregarse al Consejo de Carrera hasta el" in texto and "art. 22" in texto
    assert des.limite_informe(nuevo) == (des.concluido_en(nuevo) + timedelta(days=10)).date()
    assert des.guardar_informe(nuevo, date.today().isoformat(), "Res. CC 150/2026", "Res. CF 60/2026") == []
    c = aux.obtener(nuevo)
    assert (c["resolucion_resultados"], c["resolucion_resultados_hcf"]) == ("Res. CC 150/2026", "Res. CF 60/2026")
    assert des.aviso_informe(c) == (True, f"Informe final entregado el {aux.formato.fecha(date.today().isoformat())} dentro del plazo.")
    tarde = (date.today() + timedelta(days=30)).isoformat()
    des.guardar_informe(nuevo, tarde, "", "")
    ok, texto = des.aviso_informe(aux.obtener(nuevo))
    assert ok is False and "después del plazo de 10 días" in texto
    assert des.guardar_informe(nuevo, "mañana", "", "") == ["La fecha del informe va como AAAA-MM-DD."]


def test_documentacion_para_bienestar_social(app, gente, convocatoria):
    nuevo, it, _ = _segunda_concluida(gente, convocatoria, plazas=1, resultados={"Sofía": ("titular", 20, 25, 25)})
    assert des.documentacion(nuevo) == {} and des.limite_documentacion(nuevo) is None
    assert des.guardar_documentacion(nuevo, {"memorandums": "2026-12-01", "requisitos": "2026-12-02", "otra": "2026-12-03"}, 1) == []
    assert des.documentacion(nuevo) == {"memorandums": "2026-12-01", "requisitos": "2026-12-02"}
    assert des.guardar_documentacion(nuevo, {"memorandums": "x"}, 1) == ["Las fechas van como AAAA-MM-DD."]
    assert des.guardar_documentacion(nuevo, {"formularios": "2026-12-05"}, 1) == [] and set(des.documentacion(nuevo)) == {"formularios"}
    [d] = des.designaciones(nuevo)
    des.guardar_designacion(d["id"], {"memorandum_fecha": "2026-11-30"})
    assert des.limite_documentacion(nuevo) == date(2026, 12, 15)


# --- Pantallas ------------------------------------------------------------------------------------------------------------------

def test_pantalla_de_resultado_y_designacion(app, gente, convocatoria):
    nuevo, it, _ = _segunda_concluida(gente, convocatoria, plazas=2, resultados=NOTAS | {"Rosa": ("titular", 20, 25, 25)})
    d = _como(app, "dir@test.cl")
    assert "Resultado y designación" in d.get(f"/servicios/auxiliaturas/{nuevo}").text
    pagina = d.get(f"/servicios/auxiliaturas/{nuevo}/designacion").text
    assert "Informe final y resoluciones (art. 22)" in pagina and "Documentación para Bienestar Social (art. 27)" in pagina
    assert "Auxiliar titular" in pagina and "faltan 3 documento(s)" in pagina and "Invitar a los 2 postulante(s) con 51 a 55 puntos" in pagina
    assert _como(app, "doc3@test.cl").get(f"/servicios/auxiliaturas/{nuevo}/designacion").status_code == 403
    assert d.post(f"/servicios/auxiliaturas/{nuevo}/informe", data={"informe_final_en": date.today().isoformat(),
                                                                    "resolucion_resultados": "Res. CC 150/2026"}).status_code in (200, 303)
    assert aux.obtener(nuevo)["resolucion_resultados"] == "Res. CC 150/2026"
    d.post(f"/servicios/auxiliaturas/{nuevo}/documentacion", data={"memorandums": "2026-12-01"})
    assert des.documentacion(nuevo) == {"memorandums": "2026-12-01"}
    [desig] = des.designaciones(nuevo)
    d.post(f"/servicios/auxiliaturas/designaciones/{desig['id']}", data={"cert_deudas": "2026-11-16", "inicio": "2027-03-01"})
    assert des.designacion(desig["id"])["cert_deudas"] == "2026-11-16"
    d.post(f"/servicios/auxiliaturas/item/{it['id']}/invitaciones")
    assert [v["nombres"] for v in des.invitaciones(it["id"])] == ["Luis", "Sofía"]
    v = des.invitaciones(it["id"])[0]
    d.post(f"/servicios/auxiliaturas/invitaciones/{v['id']}/responder?acepta=0")
    assert des.invitacion(v["id"])["estado"] == "rechazada"
    acciones = [f["accion"] for f in get_db().q("SELECT accion FROM auditoria")]
    assert {"informe_final_auxiliatura", "documentacion_auxiliatura", "designacion_auxiliatura", "invitar_auxiliares",
            "responder_invitacion_auxiliatura"} <= set(acciones)


def test_las_pantallas_de_designacion_no_son_de_las_convocatorias_antiguas_ni_de_otros(app, gente, convocatoria):
    nuevo, it, _ = _segunda_concluida(gente, convocatoria)
    d = _como(app, "dir@test.cl")
    assert _como(app, "iimat@test.cl").get(f"/servicios/auxiliaturas/{nuevo}/designacion").status_code == 403   # es de docencia
    _antigua(nuevo)
    assert d.get(f"/servicios/auxiliaturas/{nuevo}/designacion").status_code == 403
    assert d.post(f"/servicios/auxiliaturas/item/{it['id']}/invitaciones").status_code == 403
    assert "Resultado y designación" not in d.get(f"/servicios/auxiliaturas/{nuevo}").text


def test_el_estudiante_responde_su_invitacion(app, gente, convocatoria, buzon):
    _, it, _ = _segunda_concluida(gente, convocatoria, plazas=1)
    des.generar_invitaciones(it, 1)
    s = _como_estudiante(app, "luis@correo.bo", buzon)
    pagina = s.get("/estudiante/auxiliaturas").text
    assert f"Invitación: {it['titulo']}" in pagina and "Acepto" in pagina
    otra = _como_estudiante(app, "sofia@correo.bo", buzon)
    v_luis = des.invitaciones(it["id"])[0]
    assert otra.post(f"/estudiante/auxiliaturas/invitaciones/{v_luis['id']}/responder?acepta=1").status_code == 404     # no es suya
    s.post(f"/estudiante/auxiliaturas/invitaciones/{v_luis['id']}/responder?acepta=1")
    assert des.invitacion(v_luis["id"])["estado"] == "aceptada"
    pagina = s.get("/estudiante/auxiliaturas").text
    assert "Mis designaciones" in pagina and "Auxiliar invitado" in pagina and "Falta: Certificación de no tener deudas" in pagina
    assert f"Invitación: {it['titulo']}" not in pagina


def test_el_estudiante_titular_ve_que_documentos_se_le_piden(app, gente, convocatoria, buzon):
    nuevo, it, pids = _segunda_concluida(gente, convocatoria, plazas=1, resultados={"Sofía": ("titular", 20, 25, 25)})
    des.designaciones(nuevo)
    s = _como_estudiante(app, "sofia@correo.bo", buzon)
    assert "Auxiliar titular" in s.get("/estudiante/auxiliaturas").text
    pagina = s.get(f"/estudiante/auxiliaturas/{pids['Sofía']}").text
    assert "Su designación" in pagina and "Debe entregar, en 72 horas de concluido el proceso (art. 23)" in pagina
    assert "Certificación de no tener deudas económicas con la Carrera y la Facultad" in pagina and "Registro de beneficiario en el SIGEP" in pagina
