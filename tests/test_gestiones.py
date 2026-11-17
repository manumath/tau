"""PLAN §66, etapa 1: ciclo de vida de las gestiones (estado, creación suelta y borrado)."""
from datetime import date
from pathlib import Path

from app.academico import gestiones, oferta, preparacion
from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login


def test_una_gestion_nace_en_planificacion(app):
    todas = gestiones.crear_anio(2030)
    assert {g["estado"] for g in todas} == {"planificacion"}
    g, error = gestiones.crear(2031, "I", 1)
    assert error is None and g["estado"] == "planificacion" and (g["fecha_inicio"], g["fecha_fin"]) == ("2031-02-01", "2031-06-30")
    assert gestiones.crear(2031, "I", 1)[1] == "Ya existe la gestión I-2031."
    assert "entre 2000 y 2100" in gestiones.crear(1800, "I", 1)[1]
    assert "Elija el tipo" in gestiones.crear(2032, "X", 1)[1]
    assert "todavía no termina" in gestiones.crear(2031, "II", 1, concluida=True)[1]


def test_crear_una_gestion_pasada_como_concluida(app):
    g, error = gestiones.crear(2019, "II", 1, concluida=True)
    assert error is None and g["estado"] == "concluida" and g["concluida_en"] and g["activada_en"] == "2019-08-01"
    assert "historial" in g["motivo_conclusion"]
    assert "no cambian" in gestiones.actualizar_fechas(g["id"], "2019-08-02", "2019-12-30")


def test_borrar_solo_en_planificacion(app):
    [i, inv, ii, ver] = gestiones.crear_anio(2030)
    oid, _ = oferta.agregar(i["id"], "MAT-111", "A", "30", 1)
    assert oferta.listar(i["id"])
    assert gestiones.eliminar(i["id"], 1) is None
    assert gestiones.obtener(i["id"]) is None and not get_db().q("SELECT 1 FROM oferta WHERE id = ?", [oid])
    get_db().execute("UPDATE gestion_academica SET estado = 'activa' WHERE id = ?", [inv["id"]])
    assert "planificación" in gestiones.eliminar(inv["id"], 1)
    assert gestiones.obtener(inv["id"])
    get_db().t.convocatoria_auxiliatura.insert(gestion_id=ii["id"], modalidad="docencia", numero=1, titulo="Prueba",
                                                 creado_por=1)
    assert "1 convocatoria a auxiliaturas" in gestiones.eliminar(ii["id"], 1)
    assert gestiones.obtener(ii["id"])
    assert gestiones.eliminar(99999, 1) == "La gestión no existe."
    assert gestiones.eliminar(ver["id"], 1) is None


def test_pantalla_de_gestiones(client, app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    gestiones.crear_anio(2030)
    r = client.get("/docencia/gestiones")
    assert "En planificación" in r.text and "Crear una sola gestión" not in r.text
    pid = gestiones.por_codigo("I-2030")["id"]
    assert client.delete(f"/docencia/gestiones/{pid}", headers=HX).status_code == 403
    assert client.post("/docencia/gestiones/una", headers=HX, data={"anio": "2031", "tipo": "I"}).status_code == 403
    permisos.asignar(emmy, "coordinacion_academica", unidades.id_de("CMAT"))
    r = client.get("/docencia/gestiones")
    assert "Crear una sola gestión" in r.text and "Planificar" in r.text and "Borrar la gestión I-2030" in r.text
    r = client.post("/docencia/gestiones/una", headers=HX, data={"anio": "2031", "tipo": "II"})
    assert "II-2031" in r.text and gestiones.por_codigo("II-2031")["estado"] == "planificacion"
    assert "Ya existe" in client.post("/docencia/gestiones/una", headers=HX, data={"anio": "2031", "tipo": "II"}).text
    r = client.post("/docencia/gestiones/una", headers=HX, data={"anio": "2018", "tipo": "I", "concluida": "1"})
    assert gestiones.por_codigo("I-2018")["estado"] == "concluida"
    assert "Ver la planificación" in client.get("/docencia/gestiones").text
    assert "no cambian" not in client.put(f"/docencia/gestiones/{pid}", headers=HX,
                                         data={"inicio": "2030-02-02", "fin": "2030-06-30"}).text
    r = client.delete(f"/docencia/gestiones/{pid}", headers=HX)
    assert gestiones.por_codigo("I-2030") is None and ">I-2030<" not in r.text
    concluida = gestiones.por_codigo("I-2018")["id"]
    assert "planificación" in client.delete(f"/docencia/gestiones/{concluida}", headers=HX).text
    assert "no cambian" in client.put(f"/docencia/gestiones/{concluida}", headers=HX,
                                      data={"inicio": "2018-02-02", "fin": "2018-06-30"}).text
    assert client.delete("/docencia/gestiones/99999", headers=HX).status_code == 404


def test_la_preparacion_acepta_las_gestiones_de_temporada(app):
    gestiones.crear_anio(2030)
    est = preparacion.estado(2030, "INV")
    assert [e["clave"] for e in est["etapas"]] == ["gestion", "oferta", "docentes"]        # sin contratos ni carga
    assert [e["clave"] for e in preparacion.estado(2030, "I")["etapas"]] == ["gestion", "oferta", "contratos", "docentes",
                                                                             "carga"]
    assert [e["clave"] for e in preparacion.estado(2031, "VER")["etapas"]] == ["gestion", "oferta", "docentes"]


# --- Etapa 2: activar el semestre ---------------------------------------------------------------------------------------

def test_para_activar_hace_falta_oferta_y_titulares(app):
    from app.academico import semestre
    [i, inv, _, _] = gestiones.crear_anio(2031)
    inv = gestiones.por_codigo("INV-2031")
    assert semestre.bloqueos(inv) == ["Falta cargar la oferta del semestre."]
    emmy = usuarios.por_email("inv@test.cl")["id"]
    oid, _ = oferta.agregar(inv["id"], "MAT-111", "A", "", 1)
    assert semestre.bloqueos(inv) == ["Falta asignar titular a 1 paralelo."]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    from app.comun import vinculos
    vinculos.agregar(emmy, "titular", "2020-01-01")
    assert oferta.asignar(oid, emmy, "titular") == []
    assert semestre.bloqueos(inv) == []
    # Contratos y carga solo avisan, y los cursos de temporada no los tienen.
    assert semestre.avisos(inv) == []
    assert semestre.activar(i["id"], 1) == ["Falta cargar la oferta del semestre."]
    assert gestiones.por_codigo("I-2031")["estado"] == "planificacion"
    assert semestre.activar(inv["id"], 1) == []
    a = gestiones.por_codigo("INV-2031")
    assert a["estado"] == "activa" and a["activada_en"] and a["activada_por"] == 1
    assert semestre.activar(inv["id"], 1) == ["Solo se activa una gestión en planificación."]
    assert "planificación" in gestiones.eliminar(inv["id"], 1)               # ya no se borra
    assert get_db().q("SELECT accion FROM auditoria WHERE accion = 'activar_gestion'")


def test_pantalla_de_planificacion_con_activar_y_borrar(client, app):
    from app.comun import vinculos
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    vinculos.agregar(emmy, "titular", "2020-01-01")
    permisos.asignar(emmy, "coordinacion_academica", unidades.id_de("CMAT"))     # planifica, no decide
    gestiones.crear_anio(2031)
    g = gestiones.por_codigo("INV-2031")
    r = client.get("/docencia/preparacion?semestre=INV-2031")
    assert "En planificación" in r.text and "Para activarla falta" in r.text and "La activa la Dirección de Carrera" in r.text
    assert "Activar el semestre" not in r.text and "Borrar la gestión" in r.text
    assert client.post(f"/docencia/preparacion/{g['id']}/activar", headers=HX).status_code == 403
    oid, _ = oferta.agregar(g["id"], "MAT-111", "A", "", 1)
    oferta.asignar(oid, emmy, "titular")
    permisos.asignar(emmy, "direccion_carrera", unidades.id_de("CMAT"))
    r = client.get("/docencia/preparacion?semestre=INV-2031")
    assert "Activar el semestre" in r.text and "Para activarla falta" not in r.text
    r = client.post(f"/docencia/preparacion/{g['id']}/activar", headers=HX)
    assert r.headers["hx-redirect"] == "/docencia/preparacion?semestre=INV-2031"
    assert gestiones.por_codigo("INV-2031")["estado"] == "activa"
    r = client.get("/docencia/preparacion?semestre=INV-2031")
    assert "Activa desde" in r.text and "Activar el semestre" not in r.text and "Borrar la gestión" not in r.text
    assert client.post(f"/docencia/preparacion/{g['id']}/borrar", headers=HX).headers["hx-redirect"] == \
        "/docencia/preparacion?semestre=INV-2031"                                # activa: no se borra
    assert gestiones.por_codigo("INV-2031")
    ii = gestiones.por_codigo("II-2031")
    assert client.post(f"/docencia/preparacion/{ii['id']}/borrar", headers=HX).headers["hx-redirect"] == "/docencia/gestiones"
    assert gestiones.por_codigo("II-2031") is None
    assert client.post("/docencia/preparacion/99999/activar", headers=HX).status_code == 404


def test_el_inicio_avisa_de_una_gestion_sin_activar(client, carrera):
    from datetime import timedelta
    hoy = date.today()
    g, _ = gestiones.crear(hoy.year + 1, "II", 1)
    get_db().execute("UPDATE gestion_academica SET fecha_inicio = ?, fecha_fin = ? WHERE id = ?",
                     [(hoy - timedelta(days=3)).isoformat(), (hoy + timedelta(days=100)).isoformat(), g["id"]])
    r = client.get("/")
    assert f"II-{hoy.year + 1} empezó el" in r.text and "sigue en planificación" in r.text
    assert "Para activarla: falta cargar la oferta" in r.text


# --- Etapa 3: cambios con el semestre activo -----------------------------------------------------------------------------

def _semestre_activo():
    """II-2031 activa con MAT-111 A (titular: Emmy) y MAT-112 A (sin docente), más Alan y Grace con vínculo."""
    from app.comun import vinculos
    from app.academico import semestre
    gestiones.crear_anio(2031)
    g = gestiones.por_codigo("II-2031")
    emmy = usuarios.por_email("inv@test.cl")["id"]
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP)["id"]
    grace = usuarios.crear("grace@test.cl", "Grace", "Hopper", PASS_TEMP)["id"]
    for u in (emmy, alan, grace):
        vinculos.agregar(u, "titular", "2020-01-01")
    o1, _ = oferta.agregar(g["id"], "MAT-111", "A", "40", 1)
    o2, _ = oferta.agregar(g["id"], "MAT-112", "A", "", 1)
    oferta.asignar(o1, emmy, "titular")
    oferta.asignar(o2, alan, "titular")
    assert semestre.activar(g["id"], 1) == []
    return gestiones.por_codigo("II-2031"), o1, o2, emmy, alan, grace


def _f(fecha="2031-09-01", motivo="renuncia", detalle=""):
    return {"fecha": fecha, "motivo": motivo, "detalle": detalle}


def test_reasignar_un_docente_conserva_las_fechas(app):
    from app.academico import cambios
    g, o1, _, emmy, alan, grace = _semestre_activo()
    did = oferta.docentes(o1)[0]["id"]
    assert "motivo" in cambios.reasignar_docente(did, grace, {"fecha": "2031-09-01", "motivo": ""}, 1)[0]
    assert "entre el inicio y el término" in cambios.reasignar_docente(did, grace, _f("2031-01-01"), 1)[0]
    assert "explique" in cambios.reasignar_docente(did, grace, _f(motivo="otro"), 1)[0]
    assert "otra persona" in cambios.reasignar_docente(did, emmy, _f(), 1)[0]
    assert "posterior al día" in cambios.reasignar_docente(did, grace, _f("2031-08-01"), 1)[0]
    assert cambios.reasignar_docente(did, grace, _f(detalle="Presentó su carta"), 1) == []
    todos = oferta.docentes(o1, historial=True)
    por = {d["usuario_id"]: d for d in todos}
    assert (por[emmy]["desde"], por[emmy]["hasta"]) == (None, "2031-08-31")
    assert (por[grace]["desde"], por[grace]["hasta"], por[grace]["rol"]) == ("2031-09-01", None, "titular")
    assert [d["usuario_id"] for d in oferta.docentes(o1)] == [grace]                # solo la vigente
    assert oferta.titular_de(o1)["usuario_id"] == grace
    assert [m["id"] for m in oferta.materias_de(emmy, g["id"])] == []              # Emmy ya no la dicta
    [c] = cambios.listar(g["id"])
    assert (c["tipo"], c["motivo"], c["anterior"], c["nuevo"]) == ("reasignar_docente", "renuncia", "Emmy Noether",
                                                                    "Grace Hopper")
    # Avisos a los dos (Emmy y Grace; quien registra, 1, no se avisa a sí mismo).
    assert {n["usuario_id"] for n in get_db().q("SELECT usuario_id FROM notificacion")} == {emmy, grace}
    assert get_db().q("SELECT accion FROM auditoria WHERE accion = 'reasignar_docente'")
    # Quien dejó el paralelo no puede volver a salir ni entrar con el mismo registro.
    assert "ya dejó" in cambios.retirar_docente(did, _f("2031-10-01"), 1)[0]
    assert "ya está asignada" in cambios.agregar_docente(o1, emmy, "titular", _f("2031-10-01"), 1)[0]


def test_retirar_docente_y_agregar_docente(app):
    from app.academico import cambios, preparacion
    g, o1, o2, emmy, alan, grace = _semestre_activo()
    assert cambios.retirar_docente(oferta.docentes(o2)[0]["id"], _f("2031-10-15", "fallecimiento"), 1) == []
    assert [x["sigla"] for x in preparacion._sin_docente(g["id"])] == ["MAT-112"]   # queda sin titular
    assert cambios.agregar_docente(o2, grace, "titular", _f("2031-10-15", "reasignacion"), 1) == []
    assert preparacion._sin_docente(g["id"]) == []
    alan_fila = next(d for d in oferta.docentes(o2, historial=True) if d["usuario_id"] == alan)
    assert alan_fila["hasta"] == "2031-10-14"
    assert [c["tipo"] for c in cambios.listar(g["id"])] == ["agregar_docente", "retirar_docente"]


def test_agregar_y_retirar_materia(app):
    from app.academico import cambios
    g, o1, o2, emmy, alan, grace = _semestre_activo()
    assert "Elija una asignatura del catálogo" in cambios.agregar_materia(g["id"], "MAT-XYZ", "A", "", _f(), 1)[0]
    assert cambios.agregar_materia(g["id"], "MAT-113", "A", "25", _f("2031-09-15", "necesidad"), 1) == []
    nueva = next(o for o in oferta.listar(g["id"]) if o["sigla"] == "MAT-113")
    assert nueva["agregada_en"] == "2031-09-15"
    assert cambios.retirar_materia(o2, _f("2031-10-20", "falta_inscritos"), 1) == []
    assert [o["sigla"] for o in oferta.listar(g["id"])] == ["MAT-111", "MAT-113"]            # la retirada sale de lo vigente
    historial = {o["sigla"]: o for o in oferta.listar(g["id"], historial=True)}
    assert historial["MAT-112"]["retirada_en"] == "2031-10-20" and historial["MAT-112"]["motivo_retiro"] == "Falta de inscritos"
    assert oferta.docentes(o2) == [] and oferta.docentes(o2, historial=True)[0]["hasta"] == "2031-10-19"
    assert "ya fue retirada" in cambios.retirar_materia(o2, _f("2031-10-21"), 1)[0]
    assert "ya está en la oferta" in cambios.agregar_materia(g["id"], "MAT-112", "A", "", _f("2031-10-25"), 1)[0]
    assert [c["tipo"] for c in cambios.listar(g["id"])] == ["retirar_materia", "agregar_materia"]
    assert oferta.materias_de(alan, g["id"]) == []


def test_los_cambios_solo_con_la_gestion_activa(app):
    from app.academico import cambios
    gestiones.crear_anio(2031)
    g = gestiones.por_codigo("I-2031")                           # en planificación
    o, _ = oferta.agregar(g["id"], "MAT-111", "A", "", 1)
    assert "solo se hacen con la gestión activa" in cambios.retirar_materia(o, _f("2031-03-01"), 1)[0]
    assert "solo se hacen con la gestión activa" in cambios.agregar_materia(g["id"], "MAT-112", "A", "", _f("2031-03-01"), 1)[0]


def test_pantallas_del_semestre_activo(client, app):
    from app.academico import cambios
    g, o1, o2, emmy, alan, grace = _semestre_activo()
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    url = f"/docencia/oferta?gestion={g['id']}"
    assert "Agregar una materia" not in client.get(url).text                    # solo consulta
    assert client.get(f"/docencia/oferta/cambio/{o1}/retirar", headers=HX).status_code == 403
    assert client.get(f"/docencia/oferta/{g['id']}/cambios").status_code == 403
    permisos.asignar(emmy, "coordinacion_academica", unidades.id_de("CMAT"))
    r = client.get(url)
    assert "Activa" in r.text and "piden motivo y fecha de efecto" in r.text and "Agregar una materia" in r.text
    assert "Agregar las troncales" not in r.text and "Asignar en grilla" not in r.text and "Importar CSV" not in r.text
    assert "Retirar MAT-111 A" in r.text and "Reasignar a Emmy Noether" in r.text
    # La edición libre queda cerrada: 409 con la explicación.
    assert client.post(f"/docencia/oferta/{g['id']}", headers=HX, data={"asignatura": "MAT-113"}).status_code == 409
    assert client.delete(f"/docencia/oferta/{o1}", headers=HX).status_code == 409
    did = oferta.docentes(o1)[0]["id"]
    assert client.delete(f"/docencia/oferta/docentes/{did}", headers=HX).status_code == 409
    assert client.post(f"/docencia/oferta/{o1}/docentes", headers=HX, data={"usuario": str(grace)}).status_code == 409
    assert client.get(f"/docencia/oferta/{g['id']}/grilla").status_code == 409
    # Los formularios de cambio y su resultado.
    assert "Fecha de efecto" in client.get(f"/docencia/oferta/cambio/docente/{did}/reasignar", headers=HX).text
    r = client.post(f"/docencia/oferta/cambio/docente/{did}/reasignar", headers=HX,
                    data={"usuario": str(grace), "fecha": "2031-09-01", "motivo": ""})
    assert "Elija el motivo" in r.text
    r = client.post(f"/docencia/oferta/cambio/docente/{did}/reasignar", headers=HX,
                    data={"usuario": str(grace), "fecha": "2031-09-01", "motivo": "licencia"})
    assert 'id="oferta-gestion"' in r.text and "Hopper" in r.text and "hasta el" in r.text
    r = client.get(f"/docencia/oferta/{g['id']}/cambios")
    assert "Docente reasignado" in r.text and "Licencia o baja" in r.text and "Emmy Noether → Grace Hopper" in r.text
    r = client.post(f"/docencia/oferta/cambio/{o2}/retirar", headers=HX, data={"fecha": "2031-10-20", "motivo": "falta_inscritos"})
    assert "Retirada desde" in r.text and cambios.listar(g["id"])[0]["tipo"] == "retirar_materia"
    r = client.post(f"/docencia/oferta/cambio/{g['id']}/materia", headers=HX, data={
        "asignatura": "MAT-113 · Geometría I", "paralelo": "A", "fecha": "2031-09-20", "motivo": "necesidad"})
    assert "MAT-113" in r.text and "agregada el" in r.text
    # Un archivo CSV no importa una gestión activa.
    from app.academico import importar_oferta
    lista, _ = importar_oferta.leer(b"gestion,sigla,paralelo,email\nII-2031,MAT-111,A,\n")
    assert "está activa" in lista[0]["errores"][0]


# --- Etapa 4: concluir, historial y carga por meses dictados -------------------------------------------------------------

def test_concluir_y_reabrir(app):
    from app.academico import semestre
    g, *_ = _semestre_activo()                              # II-2031 termina en el futuro
    assert "para concluirla antes, indique el motivo" in semestre.concluir(g["id"], "", 1)[0]
    assert semestre.concluir(g["id"], "Cierre anticipado por paro docente", 1) == []
    c = gestiones.obtener(g["id"])
    assert c["estado"] == "concluida" and c["concluida_en"] and c["concluida_por"] == 1
    assert c["motivo_conclusion"] == "Cierre anticipado por paro docente"
    assert semestre.concluir(g["id"], "x", 1) == ["Solo se concluye una gestión activa."]
    assert "por qué se reabre" in semestre.reabrir(g["id"], "", 1)[0]
    assert semestre.reabrir(g["id"], "Se omitió una reasignación", 1) == []
    a = gestiones.obtener(g["id"])
    assert (a["estado"], a["concluida_en"], a["motivo_conclusion"]) == ("activa", None, None)
    assert semestre.reabrir(g["id"], "otra vez", 1) == ["Solo se reabre una gestión concluida."]
    # Un semestre que ya terminó se concluye sin motivo.
    get_db().execute("UPDATE gestion_academica SET fecha_inicio = '2025-08-01', fecha_fin = '2025-12-31' WHERE id = ?", [g["id"]])
    assert semestre.concluir(g["id"], "", 1) == []
    assert gestiones.obtener(g["id"])["motivo_conclusion"] is None
    acciones = [x["accion"] for x in get_db().q("SELECT accion FROM auditoria ORDER BY id")]
    assert acciones.count("concluir_gestion") == 2 and "reabrir_gestion" in acciones


def test_una_gestion_concluida_es_solo_lectura(client, app):
    from app.academico import cambios, semestre
    g, o1, o2, emmy, alan, grace = _semestre_activo()
    assert semestre.concluir(g["id"], "Cierre anticipado", 1) == []
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    permisos.asignar(emmy, "direccion_carrera", unidades.id_de("CMAT"))
    r = client.get(f"/docencia/oferta?gestion={g['id']}")
    assert "Concluida" in r.text and "Es historial, de solo lectura" in r.text
    assert "Agregar una materia" not in r.text and "Retirar MAT-111" not in r.text and "Importar CSV" in r.text
    r = client.post(f"/docencia/oferta/{g['id']}", headers=HX, data={"asignatura": "MAT-113"})
    assert r.status_code == 409 and "concluida" in r.text
    assert cambios.retirar_materia(o1, _f(), 1) == ["Los cambios con motivo solo se hacen con la gestión activa."]
    assert client.get(f"/docencia/oferta/{g['id']}/grilla").status_code == 409
    # La Dirección de Carrera la reabre desde la planificación.
    r = client.get("/docencia/preparacion?semestre=II-2031")
    assert "Concluida el" in r.text and "Reabrir para corregir" in r.text and "Cierre anticipado" in r.text
    assert "Reabrir II-2031" in client.get(f"/docencia/preparacion/{g['id']}/reabrir", headers=HX).text
    r = client.post(f"/docencia/preparacion/{g['id']}/reabrir", headers=HX, data={"motivo": ""})
    assert "Indique por qué se reabre" in r.text
    r = client.post(f"/docencia/preparacion/{g['id']}/reabrir", headers=HX, data={"motivo": "Corregir una asignación"})
    assert r.headers["hx-redirect"] == "/docencia/preparacion?semestre=II-2031"
    assert gestiones.obtener(g["id"])["estado"] == "activa"
    assert "Concluir el semestre" in client.get("/docencia/preparacion?semestre=II-2031").text
    assert "Concluir II-2031" in client.get(f"/docencia/preparacion/{g['id']}/concluir", headers=HX).text
    r = client.post(f"/docencia/preparacion/{g['id']}/concluir", headers=HX, data={"motivo": ""})
    assert "indique el motivo" in r.text                                          # termina en 2031
    r = client.post(f"/docencia/preparacion/{g['id']}/concluir", headers=HX, data={"motivo": "Fin anticipado"})
    assert r.headers["hx-redirect"] == "/docencia/preparacion?semestre=II-2031"


def test_el_inicio_pide_concluir_un_semestre_terminado(client, carrera):
    from datetime import timedelta
    hoy = date.today()
    g, _ = gestiones.crear(hoy.year + 1, "I", 1)
    get_db().execute("UPDATE gestion_academica SET estado = 'activa', fecha_inicio = ?, fecha_fin = ? WHERE id = ?",
                     [(hoy - timedelta(days=150)).isoformat(), (hoy - timedelta(days=2)).isoformat(), g["id"]])
    r = client.get("/")
    assert f"I-{hoy.year + 1} terminó el" in r.text and "sigue activa" in r.text and "Al concluirlo pasa al historial" in r.text


def test_la_carga_se_cuenta_por_meses_dictados(app):
    from app.academico import cambios, carga
    from app.comun import vinculos
    from tests.test_carga import _carga
    g, o1, o2, emmy, alan, grace = _semestre_activo()
    for u in (emmy, grace):                              # carga contratada de 32 h/mes de docencia
        get_db().execute("DELETE FROM vinculo WHERE usuario_id = ?", [u])
        assert vinculos.agregar(u, "titular", "2020-01-01", carga=_carga(32, docencia=32)) == []
    assert oferta.horas_de_docencia(emmy, g["id"]) == 32 and carga.resumen(emmy, g)["avisos"] == []
    did = oferta.docentes(o1)[0]["id"]
    assert cambios.reasignar_docente(did, grace, _f("2031-09-01", "renuncia"), 1) == []
    # II-2031 va del 1 de agosto al 31 de diciembre (153 días): Emmy dictó 31 y Grace 122.
    assert oferta.horas_de_docencia(emmy, g["id"]) == 6.5
    assert oferta.horas_de_docencia(grace, g["id"]) == 25.5 + 32 * 0                 # MAT-111 desde septiembre
    [t] = oferta.tramos_de(emmy, g["id"])
    assert (t["sigla"], t["parcial"], t["inicio"], t["fin"]) == ("MAT-111", True, "2031-08-01", "2031-08-31")
    assert round(t["fraccion"], 3) == 0.203
    aviso = carga.resumen(emmy, g)["avisos"][0]
    # Parte de una materia se dice en horas, no en «0,8 materias» (ensayo del piloto, PLAN §72, etapa 11).
    assert "Falta asignar 25,5 h/mes de docencia" in aviso and "asignada: 6,5 h/mes" in aviso
    assert "por los meses dictados" in aviso
    # Los dos juntos suman la materia entera.
    assert oferta.horas_de_docencia(emmy, g["id"]) + oferta.horas_de_docencia(grace, g["id"]) == 32
    # Una materia retirada deja de contar desde su fecha, y no cuenta si se retira el primer día.
    assert cambios.retirar_materia(o2, _f("2031-09-01", "falta_inscritos"), 1) == []
    assert oferta.horas_de_docencia(alan, g["id"]) == 6.5
    assert [m["parcial"] for m in carga.materias_con_detalle(alan, g["id"])] == [True]


def test_el_historial_por_csv_crea_la_gestion_pasada_como_concluida(app):
    from app.academico import importar_oferta
    lista, errores = importar_oferta.leer(b"gestion,sigla,paralelo,email\nI-2019,MAT-111,A,\n")
    assert errores == [] and lista[0]["errores"] == []
    assert importar_oferta.aplicar(lista, 1) == 1
    g = gestiones.por_codigo("I-2019")
    assert g["estado"] == "concluida" and "historial" in g["motivo_conclusion"]
    assert [o["sigla"] for o in oferta.listar(g["id"])] == ["MAT-111"]
    # Se puede volver a cargar (reemplaza), pero no una gestión activa.
    assert importar_oferta.aplicar(importar_oferta.leer(b"gestion,sigla,paralelo,email\nI-2019,MAT-112,A,\n")[0], 1) == 1
    assert [o["sigla"] for o in oferta.listar(g["id"])] == ["MAT-112"]
