"""Servicios para estudiantes (PLAN §58): comunicados y eventos, auxiliaturas y trámites de grado."""
import io
import re
import shutil
import subprocess
import zipfile
from datetime import date, datetime, timedelta

import pytest
from starlette.testclient import TestClient

from app.comun import estudiantes, notificaciones, permisos, unidades, usuarios
from app.comun.db import get_db
from app.servicios import auxiliaturas as aux
from app.servicios import comunicados as com
from app.servicios import grado, latex
from tests.conftest import HX, login

CLAVE = "Clave-servicios-1"
PDF = b"%PDF-1.4\n" + b"0" * 64


def _personal(email, rol=None, sigla="CMAT", categoria="titular"):
    u = usuarios.crear(email, email.split("@")[0].capitalize(), "Prueba", CLAVE, debe_cambiar_pass=False,
                       categoria=categoria, fecha_ingreso="2020-01-01" if categoria else None)
    if rol:
        assert permisos.asignar(u["id"], rol, unidades.id_de(sigla)) == []
    return u


def _estudiante(nombre, email, ru):
    p = get_db().t.persona_externa.insert(nombres=nombre, apellidos="Estudiante", email=email)
    get_db().t.estudiante.insert(externo_id=p["id"], nivel="licenciatura", desde=2022, registro_universitario=ru,
                                 cohorte_anio=2022, cohorte_ciclo="I")
    u = estudiantes.crear_cuenta(p["id"], None)
    estudiantes.aceptar_consentimiento(p["id"])
    return {"externo": p["id"], "uid": u["id"], "email": email}


@pytest.fixture
def gente(app):
    g = {"dir": _personal("dir@test.cl", "direccion_carrera"), "coord": _personal("coord@test.cl", "coordinacion_academica"),
         "iimat": _personal("iimat@test.cl", "direccion_instituto", "IIMAT", categoria=None),
         "doc1": _personal("doc1@test.cl"), "doc2": _personal("doc2@test.cl"), "doc3": _personal("doc3@test.cl")}
    for i, n in enumerate(("Sofía", "Luis", "Ana", "Pedro", "Rosa"), 1):
        g[n] = _estudiante(n, f"{n.lower().replace('í', 'i')}@correo.bo", f"10{i}")
    return g


def _como(app, email):
    c = TestClient(app)
    assert login(c, email, CLAVE).headers["hx-redirect"] == "/"
    return c


def _como_estudiante(app, email, buzon):
    c = TestClient(app)
    c.post("/acceso", data={"email": email}, headers=HX)
    enlace = re.search(r"/acceso/[\w\-]+", buzon[-1].get_content()).group(0)
    assert c.post(enlace, follow_redirects=False).status_code == 303
    return c


# --- Comunicados y eventos --------------------------------------------------------------------------------------

def test_comunicado_con_convocados_y_confirmacion(app, gente, buzon):
    d = _como(app, "dir@test.cl")
    manana = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    r = d.post("/servicios/comunicados", data={"tipo": "evento", "titulo": "Reunión de tesistas", "texto": "Orden del día",
                                               "publica_como": "direccion_carrera", "inicio": manana, "lugar": "Aula 4",
                                               "confirmar": "1"}, follow_redirects=False)
    cid = int(r.headers["location"].rsplit("/", 1)[1])
    d.post(f"/servicios/comunicados/{cid}/convocados/grupo", data={"grupo": "cohorte:2022"})
    d.post(f"/servicios/comunicados/{cid}/convocados/{gente['doc1']['id']}")
    assert com.alcance(com.obtener(cid)) == 6                     # cinco estudiantes de la cohorte y un docente
    d.post(f"/servicios/comunicados/{cid}/convocados/{gente['Rosa']['uid']}/quitar")
    assert d.post(f"/servicios/comunicados/{cid}/publicar").status_code == 200
    assert com.obtener(cid)["estado"] == "publicado"
    assert len(notificaciones.todas(gente["Sofía"]["uid"])) == 1 and notificaciones.todas(gente["Rosa"]["uid"]) == []
    aviso = notificaciones.todas(gente["Sofía"]["uid"])[0]
    assert aviso["url"] == f"/estudiante/comunicados/{cid}"
    assert notificaciones.todas(gente["doc1"]["id"])[0]["url"] == f"/servicios/comunicados/{cid}"
    # La estudiante lo ve en su inicio («Le toca a usted») y confirma.
    s = _como_estudiante(app, "sofia@correo.bo", buzon)
    assert "Confirme su asistencia: Reunión de tesistas" in s.get("/estudiante").text
    assert "¿Asistirá?" in s.get(f"/estudiante/comunicados/{cid}").text
    s.post(f"/estudiante/comunicados/{cid}/respuesta", data={"respuesta": "asistire"})
    assert com.cifras(cid)["asistire"] == 1
    assert "Confirme su asistencia" not in s.get("/estudiante").text
    # Otro estudiante no convocado no lo ve; el personal no convocado tampoco.
    rosa = _como_estudiante(app, "rosa@correo.bo", buzon)
    assert rosa.get(f"/estudiante/comunicados/{cid}").status_code == 404
    assert _como(app, "doc2@test.cl").get(f"/servicios/comunicados/{cid}").status_code == 403
    # La asistencia se registra después de que empieza.
    d.post(f"/servicios/comunicados/{cid}/asistencia", data={"presentes": [str(gente["Sofía"]["uid"])]})
    assert com.cifras(cid)["registrada"] is False
    get_db().execute("UPDATE comunicado SET inicio = ? WHERE id = ?", [(datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"), cid])
    d.post(f"/servicios/comunicados/{cid}/asistencia", data={"presentes": [str(gente["Sofía"]["uid"])]})
    assert com.cifras(cid)["asistieron"] == 1


def test_para_todos_sin_registro_de_asistencia(app, gente):
    d = _como(app, "coord@test.cl")
    r = d.post("/servicios/comunicados", data={"tipo": "convocatoria", "titulo": "Becas de apoyo", "texto": "Postule",
                                               "publica_como": "coordinacion_academica"}, follow_redirects=False)
    cid = int(r.headers["location"].rsplit("/", 1)[1])
    assert com.publicar(cid) == ["Agregue al menos un convocado, o márquelo para todos."]
    d.post(f"/servicios/comunicados/{cid}/para-todos", data={"valor": "1"})
    d.post(f"/servicios/comunicados/{cid}/publicar")
    n = get_db().q("SELECT COUNT(*) n FROM usuario WHERE activo = 1")[0]["n"]
    assert com.cifras(cid)["total"] == n - 1                       # todas las cuentas menos quien publica
    assert not com.puede_registrar_asistencia(com.obtener(cid))


def test_quien_publica_y_el_responsable_de_un_proyecto(app, gente):
    assert _como(app, "doc1@test.cl").get("/servicios/comunicados/nuevo").status_code == 403   # sin cargo ni proyecto
    assert "Nuevo" in _como(app, "iimat@test.cl").get("/servicios/comunicados").text
    pid = get_db().t.proyecto.insert(nombre="Grafos expansores", creado_por=gente["doc1"]["id"])["id"]
    get_db().t.proyecto_participante.insert(proyecto_id=pid, investigador_id=gente["doc1"]["id"], rol="responsable")
    get_db().t.proyecto_participante.insert(proyecto_id=pid, externo_id=gente["Luis"]["externo"], rol="tesista")
    c = _como(app, "doc1@test.cl")
    r = c.post("/servicios/comunicados", data={"tipo": "comunicado", "titulo": "Seminario del proyecto",
                                               "publica_como": f"proyecto:{pid}"}, follow_redirects=False)
    cid = int(r.headers["location"].rsplit("/", 1)[1])
    assert [g for g, _ in com.grupos(gente["doc1"], com.obtener(cid))] == [f"proyecto:{pid}"]
    assert c.post(f"/servicios/comunicados/{cid}/para-todos", data={"valor": "1"}).status_code == 403
    c.post(f"/servicios/comunicados/{cid}/convocados/grupo", data={"grupo": "estudiantes"})   # no es su grupo
    assert com.convocados(cid) == []
    c.post(f"/servicios/comunicados/{cid}/convocados/grupo", data={"grupo": f"proyecto:{pid}"})
    assert [d["usuario_id"] for d in com.convocados(cid)] == [gente["Luis"]["uid"]]


# --- Auxiliaturas -----------------------------------------------------------------------------------------------

@pytest.fixture
def convocatoria(gente):
    db = get_db()
    g = db.t.gestion_academica.insert(anio=2027, tipo="I", fecha_inicio="2027-03-01", fecha_fin="2027-07-31")
    a = db.t.asignatura.insert(sigla="MAT-102", nombre="Cálculo II", departamento="MAT")
    db.t.oferta.insert(gestion_id=g["id"], asignatura_id=a["id"])
    cierre = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
    x, errores = aux.validar({"modalidad": "docencia", "gestion_id": g["id"], "numero": "1", "titulo": "Auxiliaturas I-2027",
                              "publicacion": date.today().isoformat(), "cierre": cierre,
                              "recepcion_lugar": "Secretaría de la Carrera", "recepcion_horario": "Lunes a viernes, de 9 a 12",
                              "examen": (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%dT%H:%M")}, ["docencia"])
    assert errores == []
    cid = aux.crear(x, gente["dir"]["id"])
    c = aux.obtener(cid)
    assert aux.agregar_item(c, {"asignatura_id": a["id"], "plazas": "1", "horas": "40"}) == []
    it = aux.items(cid)[0]
    return {"cid": cid, "iid": it["id"], "asignatura": a["id"]}


def _publicar(gente, conv):
    it = aux.item(conv["iid"])
    assert aux.fijar_tribunal(it, [gente["doc1"]["id"], gente["doc2"]["id"]], [gente["Ana"]["uid"]]) != []
    assert aux.fijar_tribunal(it, [gente["doc1"]["id"], gente["doc2"]["id"]], [gente["Ana"]["uid"], gente["Pedro"]["uid"]]) == []
    assert aux.publicar(conv["cid"]) == ["Falta el número de la resolución del Consejo de Carrera."]
    get_db().execute("UPDATE convocatoria_auxiliatura SET resolucion = 'Res. CC 12/2026' WHERE id = ?", [conv["cid"]])
    assert aux.publicar(conv["cid"]) == []


def _completar(p, gente):
    for r in aux.requisitos_de(p):
        if r["acredita"] == "documento":
            from app.investigacion import adjuntos
            adjuntos.guardar("requisito_postulacion", r["fila"], "doc.pdf", PDF, gente["dir"]["id"])
        elif r["acredita"] == "declaracion":
            aux.declarar(p["id"], r["id"], True)
    aux.guardar_propuesta(p["id"], "Prácticas semanales")


def test_convocatoria_y_postulacion_desde_el_telefono(app, gente, convocatoria, buzon):
    assert aux.requisitos(convocatoria["cid"])[0]["texto"].startswith("Ser estudiante regular")
    _publicar(gente, convocatoria)
    assert any("Convocatoria: Auxiliaturas I-2027" == n["asunto"] for n in notificaciones.todas(gente["Sofía"]["uid"]))
    s = _como_estudiante(app, "sofia@correo.bo", buzon)
    assert "Cálculo II" in s.get("/estudiante/auxiliaturas").text
    r = s.post(f"/estudiante/auxiliaturas/item/{convocatoria['iid']}/postular", follow_redirects=False)
    pid = int(r.headers["location"].rsplit("/", 1)[1])
    pagina = s.get(f"/estudiante/auxiliaturas/{pid}").text
    assert "Requisitos · 1 de 6" in pagina and "Enviar postulación" in pagina     # el del sistema ya está cumplido
    assert aux.enviar(pid)[0].startswith("Falta: Ser estudiante regular")
    req = next(x for x in aux.requisitos_de(aux.postulacion(pid)) if x["acredita"] == "documento")
    s.post(f"/estudiante/auxiliaturas/{pid}/requisitos/{req['id']}/archivo", files={"archivo": ("matricula.pdf", PDF, "application/pdf")})
    assert next(x for x in aux.requisitos_de(aux.postulacion(pid)) if x["id"] == req["id"])["cumplido"]
    _completar(aux.postulacion(pid), gente)
    s.post(f"/estudiante/auxiliaturas/{pid}/enviar")
    assert aux.postulacion(pid)["estado"] == "enviada"
    # Otra estudiante no ve la postulación ajena; un miembro del tribunal no puede postular.
    luis = _como_estudiante(app, "luis@correo.bo", buzon)
    assert luis.get(f"/estudiante/auxiliaturas/{pid}").status_code == 404
    assert aux.postular(convocatoria["iid"], gente["Ana"]["externo"])[1] != []
    # El tribunal ve el documento; otro docente no.
    adj = aux.requisitos_de(aux.postulacion(pid))[0]["documentos"][0]
    assert _como(app, "doc1@test.cl").get(f"/servicios/auxiliaturas/documento/{adj['id']}").status_code == 200
    assert _como(app, "doc3@test.cl").get(f"/servicios/auxiliaturas/documento/{adj['id']}").status_code == 404
    ana = _como_estudiante(app, "ana@correo.bo", buzon)
    assert ana.get(f"/estudiante/tribunal/documento/{adj['id']}").status_code == 200
    assert luis.get(f"/estudiante/tribunal/documento/{adj['id']}").status_code == 404


def _calificar(it, gente, fase_valores: dict[int, float], miembros=("doc1", "doc2", "Ana")):
    for m in miembros:
        uid = gente[m]["id"] if "id" in gente[m] else gente[m]["uid"]
        for pid, v in fase_valores.items():
            assert aux.calificar(aux.item(it), uid, pid, v) == []


def _pasar_24h(iid):
    get_db().execute("UPDATE fase_auxiliatura SET cerrada_en = datetime('now', '-25 hours') WHERE item_id = ?", [iid])


def test_fases_quorum_impugnacion_y_resultado(app, gente, convocatoria):
    _publicar(gente, convocatoria)
    pids = []
    for n in ("Sofía", "Luis", "Rosa"):
        pid, _ = aux.postular(convocatoria["iid"], gente[n]["externo"])
        _completar(aux.postulacion(pid), gente)
        assert aux.enviar(pid) == []
        pids.append(pid)
    sofia, luis, rosa = pids
    iid = convocatoria["iid"]
    assert aux.cerrar_fase(aux.item(iid), gente["dir"]["id"])[0].startswith("No se puede cerrar: La recepción cierra")
    get_db().execute("UPDATE convocatoria_auxiliatura SET cierre = '2020-01-01T00:00' WHERE id = ?", [convocatoria["cid"]])
    assert aux.cerrar_fase(aux.item(iid), gente["dir"]["id"]) == []
    assert aux.item(iid)["fase"] == "habilitacion"
    # Habilitación: con dos miembros no alcanza el quórum.
    _calificar(iid, gente, {sofia: 1, luis: 1, rosa: 0}, miembros=("doc1", "doc2"))
    assert "menos de 3 calificaciones" in aux.cerrar_fase(aux.item(iid), gente["doc1"]["id"])[0]
    _calificar(iid, gente, {sofia: 1, luis: 1, rosa: 0}, miembros=("Ana",))
    assert aux.cerrar_fase(aux.item(iid), gente["doc1"]["id"]) == []
    assert aux.postulacion(rosa)["estado"] == "no_habilitada"
    # Méritos: hay que esperar 24 horas y resolver las impugnaciones.
    _calificar(iid, gente, {sofia: 25, luis: 20})
    assert "24 horas" in aux.cerrar_fase(aux.item(iid), gente["dir"]["id"])[0]
    _pasar_24h(iid)
    assert aux.registrar_impugnacion(aux.item(iid), rosa, "habilitacion", "2026-11-08", "Presenté la matrícula", gente["dir"]["id"]) == []
    assert "impugnaciones sin resolver" in aux.cerrar_fase(aux.item(iid), gente["dir"]["id"])[0]
    mid = aux.impugnaciones(iid)[0]["id"]
    assert aux.resolver_impugnacion(iid, mid, "Se ratifica: la matrícula no estaba vigente.") == []
    assert aux.cerrar_fase(aux.item(iid), gente["dir"]["id"]) == []
    # Escrito: Luis no llega al mínimo de 17,5.
    _pasar_24h(iid)
    _calificar(iid, gente, {sofia: 30, luis: 15})
    assert aux.cerrar_fase(aux.item(iid), gente["dir"]["id"]) == []
    assert aux.postulacion(luis)["estado"] == "eliminada" and aux.postulacion(luis)["fase_fin"] == "escrito"
    _pasar_24h(iid)
    assert aux.sortear_tema(aux.item(iid), "Integrales dobles\nSeries de potencias") == []
    assert aux.item(iid)["tema_oral"] in ("Integrales dobles", "Series de potencias")
    _calificar(iid, gente, {sofia: 28})
    assert aux.cerrar_fase(aux.item(iid), gente["dir"]["id"]) == []
    assert aux.item(iid)["fase"] == "concluido" and aux.total(sofia) == 83
    assert aux.postulacion(sofia)["estado"] == "titular"
    assert aux.obtener(convocatoria["cid"])["estado"] == "concluida"
    assert any(n["asunto"].startswith("Resultado: Examen oral") for n in notificaciones.todas(gente["Sofía"]["uid"]))
    # La próxima vez cuenta como una gestión de auxiliar en la materia (art. 8).
    assert aux.veces_auxiliar(gente["Sofía"]["externo"], convocatoria["asignatura"]) == 1


def test_empate_en_el_corte(app, gente, convocatoria):
    _publicar(gente, convocatoria)
    pids = []
    for n in ("Sofía", "Luis"):
        pid, _ = aux.postular(convocatoria["iid"], gente[n]["externo"])
        _completar(aux.postulacion(pid), gente)
        aux.enviar(pid)
        pids.append(pid)
    iid = convocatoria["iid"]
    get_db().execute("UPDATE convocatoria_auxiliatura SET cierre = '2020-01-01T00:00' WHERE id = ?", [convocatoria["cid"]])
    aux.cerrar_fase(aux.item(iid), gente["dir"]["id"])
    for valores in ({p: 1 for p in pids}, {p: 20 for p in pids}, {p: 25 for p in pids}, {p: 25 for p in pids}):
        _calificar(iid, gente, valores)
        assert aux.cerrar_fase(aux.item(iid), gente["dir"]["id"]) == []
        _pasar_24h(iid)
    assert {aux.postulacion(p)["estado"] for p in pids} == {"empate"}
    assert aux.obtener(convocatoria["cid"])["estado"] == "publicada"
    assert aux.resolver_empate(aux.item(iid), pids) != []                 # una sola plaza
    assert aux.resolver_empate(aux.item(iid), [pids[1]]) == []
    assert [aux.postulacion(p)["estado"] for p in pids] == ["no_seleccionada", "titular"]
    assert aux.obtener(convocatoria["cid"])["estado"] == "concluida"


def test_permisos_de_auxiliaturas(app, gente, convocatoria, buzon):
    assert _como(app, "dir@test.cl").get(f"/servicios/auxiliaturas/{convocatoria['cid']}").status_code == 200
    assert _como(app, "coord@test.cl").get(f"/servicios/auxiliaturas/{convocatoria['cid']}").status_code == 200
    assert _como(app, "iimat@test.cl").get(f"/servicios/auxiliaturas/{convocatoria['cid']}").status_code == 403  # es de docencia
    assert "investigacion" in aux.modalidades_de(gente["iimat"]) and "docencia" not in aux.modalidades_de(gente["iimat"])
    assert _como(app, "doc3@test.cl").get("/servicios/auxiliaturas").status_code == 403
    s = _como_estudiante(app, "sofia@correo.bo", buzon)
    assert s.get("/servicios/auxiliaturas", follow_redirects=False).headers["location"] == "/estudiante"


# --- Proyecto de grado -------------------------------------------------------------------------------------------

def _perfil_listo(gente):
    tid, errores = grado.crear_perfil(gente["Sofía"]["externo"], {"titulo": "Grafos de Cayley", "tutor_id": gente["doc1"]["id"]},
                                      ["justificacion"])
    assert errores == []
    t = grado.obtener(tid)
    assert "Escribir «Introducción»" in grado.faltantes(t)
    textos = {k: f"Texto de la sección {i} con $x^2$" for i, k in enumerate(grado.OBLIGATORIAS)}
    textos["bibliografia"] = "@book{serre,\n  author={J.-P. Serre}, title={Trees}, year={1980}, publisher={Springer}}"
    assert grado.guardar(t, {"titulo": t["titulo"], "modalidad": "proyecto_grado", "tutor_id": gente["doc1"]["id"]}, textos,
                         ["justificacion"]) == []
    return grado.obtener(tid)


def test_perfil_de_punta_a_punta(app, gente, buzon):
    t = _perfil_listo(gente)
    assert grado.faltantes(t) == [] and "justificacion" in grado.seleccion(t)
    assert grado.pedir_visto_bueno(t) == []
    assert any("Visto bueno" in n["asunto"] for n in notificaciones.todas(gente["doc1"]["id"]))
    tutor = _como(app, "doc1@test.cl")
    assert "Dar el visto bueno" in tutor.get("/servicios/grado").text
    tutor.post(f"/servicios/grado/{t['id']}/tutor", data={"decision": "aprobar"})
    t = grado.obtener(t["id"])
    assert t["estado"] == "enviado"
    d = _como(app, "coord@test.cl")
    assert "Designar el tribunal" in d.get("/servicios/grado").text
    d.post(f"/servicios/grado/{t['id']}/tribunal", data={"miembros": [str(gente["doc1"]["id"]), str(gente["doc2"]["id"])]})
    assert grado.obtener(t["id"])["estado"] == "enviado"           # el tutor no integra el tribunal
    d.post(f"/servicios/grado/{t['id']}/tribunal", data={"miembros": [str(gente["doc2"]["id"]), str(gente["doc3"]["id"])]})
    t = grado.obtener(t["id"])
    assert t["estado"] == "en_revision" and t["ronda"] == 1
    assert aux.habiles_entre(date.today(), date.fromisoformat(t["plazo"])) == grado.DIAS_REVISION
    aspectos = {k: "suficiente" for k in grado.ASPECTOS}
    r2 = _como(app, "doc2@test.cl")
    r2.post(f"/servicios/grado/{t['id']}/informe", data={**{f"a_{k}": v for k, v in aspectos.items()}, "a_aporte": "observado",
                                                         "dictamen": "observado",
                                                         "observaciones": "Precise el objetivo 2.\n\nAgregue a Lubotzky."})
    assert len(grado.informes(t["id"], 1)) == 1 and grado.obtener(t["id"])["estado"] == "en_revision"   # falta el otro
    s = _como_estudiante(app, "sofia@correo.bo", buzon)
    assert "Precise el objetivo 2" not in s.get(f"/estudiante/grado/{t['id']}").text    # aún no se muestran
    assert grado.enviar_informe(grado.obtener(t["id"]), gente["doc3"]["id"], aspectos, "aprobado", "", []) == []
    t = grado.obtener(t["id"])
    assert t["estado"] == "observado"
    pagina = s.get("/estudiante").text
    assert "Responda las observaciones del tribunal (2 pendientes)" in pagina
    assert grado.reenviar(t)[0].startswith("Falta: Responder 2")
    for o in grado.observaciones_pendientes(t):
        s.post(f"/estudiante/grado/{t['id']}/observaciones/{o['id']}", data={"respuesta": "Hecho."})
    s.post(f"/estudiante/grado/{t['id']}/reenviar")
    t = grado.obtener(t["id"])
    assert t["estado"] == "en_revision" and t["ronda"] == 2
    for m in ("doc2", "doc3"):
        assert grado.enviar_informe(grado.obtener(t["id"]), gente[m]["id"], aspectos, "aprobado", "", []) == []
    assert grado.obtener(t["id"])["estado"] == "favorable"
    assert grado.registrar_resolucion(grado.obtener(t["id"]), "") != []
    d.post(f"/servicios/grado/{t['id']}/resolucion", data={"numero": "Res. CC 45/2026"})
    assert grado.obtener(t["id"])["estado"] == "aprobado"
    # Documento final, defensa y nota.
    s.post(f"/estudiante/grado/{t['id']}/final")
    final = next(x for x in grado.de_estudiante(gente["Sofía"]["externo"]) if x["tipo"] == "final")
    assert grado.faltantes(final) == ["Subir el documento final (PDF)"]
    s.post(f"/estudiante/grado/{final['id']}/archivo", files={"archivo": ("final.pdf", PDF, "application/pdf")})
    assert grado.pedir_visto_bueno(grado.obtener(final["id"])) == []
    grado.responder_tutor(grado.obtener(final["id"]), gente["doc1"]["id"], True, "")
    assert grado.designar_tribunal(grado.obtener(final["id"]), [gente["doc2"]["id"], gente["doc3"]["id"]], gente["dir"]["id"]) == []
    for m in ("doc2", "doc3"):
        grado.enviar_informe(grado.obtener(final["id"]), gente[m]["id"], aspectos, "aprobado", "", [])
    hoy = date.today().isoformat()
    assert grado.registrar_defensa(grado.obtener(final["id"]), hoy, hoy) == []
    assert grado.calificar_defensa(grado.obtener(final["id"]), gente["doc2"]["id"], "88") == []
    assert grado.obtener(final["id"])["estado"] == "favorable"
    assert grado.calificar_defensa(grado.obtener(final["id"]), gente["doc3"]["id"], "93") == []
    final = grado.obtener(final["id"])
    assert final["estado"] == "defendido" and grado.nota_final(final["id"]) == 90.5
    assert grado.calificacion_literal(90.5) == "Excelente"
    assert "Acta de defensa" in d.get(f"/servicios/grado/{final['id']}/acta").text


def test_no_aprobado_y_aislamiento(app, gente, buzon):
    t = _perfil_listo(gente)
    grado.pedir_visto_bueno(t)
    grado.responder_tutor(grado.obtener(t["id"]), gente["doc1"]["id"], False, "")
    assert grado.obtener(t["id"])["estado"] == "con_tutor"         # devolver exige comentario
    grado.responder_tutor(grado.obtener(t["id"]), gente["doc1"]["id"], False, "Corrija la metodología")
    assert grado.obtener(t["id"])["estado"] == "borrador"
    s = _como_estudiante(app, "sofia@correo.bo", buzon)
    assert "Su tutor le devolvió el trámite" in s.get("/estudiante").text
    luis = _como_estudiante(app, "luis@correo.bo", buzon)
    assert luis.get(f"/estudiante/grado/{t['id']}").status_code == 404
    assert luis.get(f"/estudiante/grado/{t['id']}/latex.zip").status_code == 404
    assert _como(app, "doc3@test.cl").get(f"/servicios/grado/{t['id']}").status_code == 403
    grado.pedir_visto_bueno(grado.obtener(t["id"]))
    grado.responder_tutor(grado.obtener(t["id"]), gente["doc1"]["id"], True, "")
    grado.designar_tribunal(grado.obtener(t["id"]), [gente["doc2"]["id"], gente["doc3"]["id"]], gente["dir"]["id"])
    aspectos = {k: "observado" for k in grado.ASPECTOS}
    assert grado.enviar_informe(grado.obtener(t["id"]), gente["doc2"]["id"], aspectos, "no_aprobado", "", []) != []   # sin fundamento
    grado.enviar_informe(grado.obtener(t["id"]), gente["doc2"]["id"], aspectos, "no_aprobado", "El tema no es viable.", [])
    grado.enviar_informe(grado.obtener(t["id"]), gente["doc3"]["id"], aspectos, "observado", "", ["Rehacer"])
    assert grado.obtener(t["id"])["estado"] == "rechazado"
    assert grado.crear_perfil(gente["Sofía"]["externo"], {"titulo": "Otro tema"}, [])[1] == []   # puede empezar otro


def test_recordatorios_del_plazo(app, gente):
    t = _perfil_listo(gente)
    grado.pedir_visto_bueno(t)
    grado.responder_tutor(grado.obtener(t["id"]), gente["doc1"]["id"], True, "")
    grado.designar_tribunal(grado.obtener(t["id"]), [gente["doc2"]["id"], gente["doc3"]["id"]], gente["dir"]["id"])
    plazo = date.fromisoformat(grado.obtener(t["id"])["plazo"])
    assert grado.recordar(date.today()) == 0
    antes = plazo - timedelta(days=1)
    assert grado.recordar(antes) == 2 and grado.recordar(antes) == 0     # una vez por persona
    assert grado.recordar(plazo + timedelta(days=1)) == 2
    assert any(n["asunto"].startswith("Informe vencido") for n in notificaciones.todas(gente["dir"]["id"]))


def test_latex_del_perfil(app, gente, tmp_path):
    t = _perfil_listo(gente)
    get_db().execute("UPDATE persona_externa SET nombres = 'Sofía & Co_' WHERE id = ?", [gente["Sofía"]["externo"]])
    z = zipfile.ZipFile(io.BytesIO(latex.zip_perfil(grado.obtener(t["id"]))))
    assert set(z.namelist()) == {"perfil.tex", "nota.tex", "perfil-cmat.cls", "referencias.bib", "LEAME.txt"}
    tex = z.read("perfil.tex").decode()
    assert r"\postulante{Sofía \& Co\_ Estudiante}{101}" in tex and "\\section{Justificación}" in tex
    assert "Texto de la sección 1 con $x^2$" in tex and "\\bibliography{referencias}" in tex
    if not shutil.which("pdflatex"):
        pytest.skip("sin pdflatex en este equipo")
    z.extractall(tmp_path)
    for orden in (["pdflatex", "perfil.tex"], ["bibtex", "perfil"], ["pdflatex", "perfil.tex"], ["pdflatex", "nota.tex"]):
        extra = ["-interaction=nonstopmode", "-halt-on-error"] if orden[0] == "pdflatex" else []
        r = subprocess.run([orden[0], *extra, orden[1]], cwd=tmp_path, capture_output=True, timeout=120)
        assert r.returncode == 0, r.stdout.decode(errors="replace")[-2000:]
    assert (tmp_path / "perfil.pdf").exists() and (tmp_path / "nota.pdf").exists()
