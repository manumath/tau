"""PLAN §70: las auxiliaturas según el Reglamento Específico de Auxiliares Académicos del Pregrado (Res. HCU 424/2023, mod. 364/2025)."""
from datetime import date

from app.comun.db import get_db
from app.servicios import auxiliaturas as aux
from tests.test_servicios import (  # noqa: F401
    _calificar, _completar, _como, _pasar_24h, _publicar, convocatoria, gente)


def _conv(cid):
    return aux.obtener(cid)


def _antigua(cid):
    get_db().execute("UPDATE convocatoria_auxiliatura SET reglamento = 'hcu_251_2021' WHERE id = ?", [cid])


def _a_meritos_con(gente, conv, nota_meritos):
    """Lleva una postulante hasta la fase de méritos y la califica; devuelve su postulación."""
    _publicar(gente, conv)
    pid, _ = aux.postular(conv["iid"], gente["Sofía"]["externo"])
    _completar(aux.postulacion(pid), gente)
    assert aux.enviar(pid) == []
    get_db().execute("UPDATE convocatoria_auxiliatura SET cierre = '2020-01-01T00:00' WHERE id = ?", [conv["cid"]])
    assert aux.cerrar_fase(aux.item(conv["iid"]), gente["dir"]["id"]) == []
    _calificar(conv["iid"], gente, {pid: 1})
    assert aux.cerrar_fase(aux.item(conv["iid"]), gente["dir"]["id"]) == []
    _calificar(conv["iid"], gente, {pid: nota_meritos})
    _pasar_24h(conv["iid"])
    assert aux.cerrar_fase(aux.item(conv["iid"]), gente["dir"]["id"]) == []
    return pid


# --- Qué reglamento rige --------------------------------------------------------------------------------------------

def test_las_convocatorias_nuevas_usan_el_reglamento_de_2023(app, gente, convocatoria):
    c = _conv(convocatoria["cid"])
    assert c["reglamento"] == aux.REGLAMENTO_VIGENTE and "HCU 424/2023" in aux.reglamento_texto(c)
    assert aux.reglas(c)["minimo"] == {"meritos": 5, "escrito": 18}
    _antigua(convocatoria["cid"])
    assert aux.reglas(_conv(convocatoria["cid"]))["minimo"] == {"meritos": 10, "escrito": 17.5}
    assert "HCU 251/2021" in aux.reglamento_texto(_conv(convocatoria["cid"]))


def test_el_minimo_de_meritos_es_5_en_2023_y_10_en_la_convocatoria_antigua(app, gente, convocatoria):
    pid = _a_meritos_con(gente, convocatoria, 7)          # 7 de 30: pasa con 5, no pasa con 10
    assert aux.postulacion(pid)["estado"] == "enviada" and aux.minimo(aux.item(convocatoria["iid"]), "meritos") == 5


def test_con_el_reglamento_antiguo_se_conservan_sus_minimos(app, gente, convocatoria):
    _antigua(convocatoria["cid"])
    pid = _a_meritos_con(gente, convocatoria, 7)
    assert aux.postulacion(pid)["estado"] == "eliminada" and aux.postulacion(pid)["fase_fin"] == "meritos"


def test_el_minimo_del_escrito_es_18(app, gente, convocatoria):
    pid = _a_meritos_con(gente, convocatoria, 20)
    _pasar_24h(convocatoria["iid"])
    _calificar(convocatoria["iid"], gente, {pid: 17.5})   # con el reglamento de 2021 habría pasado
    assert aux.cerrar_fase(aux.item(convocatoria["iid"]), gente["dir"]["id"]) == []
    assert aux.postulacion(pid)["estado"] == "eliminada" and aux.postulacion(pid)["fase_fin"] == "escrito"


# --- Solo semestres regulares -----------------------------------------------------------------------------------------

def test_no_se_convoca_en_las_temporadas(app, gente, convocatoria):
    db = get_db()
    inv = db.t.gestion_academica.insert(anio=2027, tipo="INV", fecha_inicio="2027-07-01", fecha_fin="2027-07-31")["id"]
    ver = db.t.gestion_academica.insert(anio=2027, tipo="VER", fecha_inicio="2028-01-01", fecha_fin="2028-01-31")["id"]
    assert {g["tipo"] for g in aux.gestiones()} <= {"I", "II"} and inv not in {g["id"] for g in aux.gestiones()}
    for gid in (inv, ver):
        _, errores = aux.validar({"modalidad": "docencia", "gestion_id": gid, "titulo": "Temporada"}, ["docencia"])
        assert errores == ["Las auxiliaturas se convocan para los semestres I y II, no para los periodos de temporada."]
    _, errores = aux.validar({"modalidad": "docencia", "gestion_id": _conv(convocatoria["cid"])["gestion_id"], "titulo": "Semestre"},
                             ["docencia"])
    assert errores == []


# --- Plazos y calendario ------------------------------------------------------------------------------------------------

def _c(**kw):
    return {"reglamento": aux.REGLAMENTO_VIGENTE, "numero": 1, "gestion_id": 0, "publicacion": None, "cierre": None, "examen": None, **kw}


def test_plazo_de_presentacion_de_2023_cuenta_hasta_el_cierre(app):
    # Del lunes 2 al lunes 16 de noviembre de 2026 hay 10 días hábiles.
    assert aux.chequeo_fechas(_c(publicacion="2026-11-02", cierre="2026-11-16T17:00"))[0] is True
    ok, texto = aux.chequeo_fechas(_c(publicacion="2026-11-02", cierre="2026-11-13T17:00"))
    assert ok is False and "art. 24" in texto and "el cierre de la recepción" in texto
    assert aux.chequeo_fechas(_c(numero=2, publicacion="2026-12-01", cierre="2026-12-08T17:00"))[0] is True   # 5 días en la segunda
    assert aux.chequeo_fechas(_c(publicacion="2026-11-02")) is None


def test_con_el_reglamento_antiguo_el_plazo_corre_hasta_el_examen(app):
    c = _c(reglamento=aux.REGLAMENTO_ANTERIOR, publicacion="2026-11-02", cierre="2026-11-03T17:00", examen="2026-11-16T09:00")
    ok, texto = aux.chequeo_fechas(c)
    assert ok is True and "el examen escrito" in texto and "art. 10" in texto


def _gestion(tipo, anio):
    return get_db().t.gestion_academica.insert(anio=anio, tipo=tipo, fecha_inicio=f"{anio}-03-01", fecha_fin=f"{anio}-07-31")["id"]


def test_calendario_de_publicacion_del_art_12(app):
    i, ii = _gestion("I", 2027), _gestion("II", 2027)
    cal = lambda gid, numero, dia: aux.chequeo_calendario(_c(gestion_id=gid, numero=numero, publicacion=dia))  # noqa: E731
    assert cal(i, 1, "2026-11-10")[0] is True and cal(i, 1, "2026-11-20")[0] is False
    assert cal(i, 1, "2026-11-04")[0] is True and "una sola convocatoria" in cal(i, 1, "2026-11-04")[1]   # una sola para ambos semestres
    assert cal(i, 2, "2026-12-03")[0] is True and cal(i, 2, "2026-12-15")[0] is False
    assert cal(ii, 1, "2027-05-12")[0] is True and cal(ii, 1, "2027-05-25")[0] is False
    assert cal(ii, 2, "2027-06-10")[0] is True and cal(ii, 2, "2027-06-01")[0] is False
    assert "2.ª semana de noviembre" in cal(i, 1, "2026-11-20")[1]
    assert aux.chequeo_calendario(_c(gestion_id=i)) is None                                               # sin fecha de publicación
    assert aux.chequeo_calendario(_c(reglamento=aux.REGLAMENTO_ANTERIOR, gestion_id=i, publicacion="2026-11-20")) is None


# --- Contenido de la convocatoria (art. 11) ---------------------------------------------------------------------------

def test_para_publicar_hace_falta_donde_y_cuando_se_reciben_los_documentos(app, gente, convocatoria):
    get_db().execute("UPDATE convocatoria_auxiliatura SET recepcion_lugar = NULL, resolucion = 'Res. CC 1/2026' WHERE id = ?",
                     [convocatoria["cid"]])
    it = aux.item(convocatoria["iid"])
    assert aux.fijar_tribunal(it, [gente["doc1"]["id"], gente["doc2"]["id"]], [gente["Ana"]["uid"], gente["Pedro"]["uid"]]) == []
    assert "lugar y el horario de recepción de los documentos (art. 11)" in aux.publicar(convocatoria["cid"])[0]
    get_db().execute("UPDATE convocatoria_auxiliatura SET recepcion_lugar = 'Secretaría' WHERE id = ?", [convocatoria["cid"]])
    assert aux.publicar(convocatoria["cid"]) == []
    # Una convocatoria hecha con el reglamento anterior no tiene ese requisito.
    get_db().execute("UPDATE convocatoria_auxiliatura SET estado = 'borrador', recepcion_lugar = NULL, recepcion_horario = NULL, "
                     "reglamento = 'hcu_251_2021' WHERE id = ?", [convocatoria["cid"]])
    assert aux.faltantes_publicar(_conv(convocatoria["cid"])) == []


def test_validar_guarda_los_datos_del_art_11(app, gente, convocatoria):
    x, errores = aux.validar({"modalidad": "docencia", "gestion_id": _conv(convocatoria["cid"])["gestion_id"], "titulo": "Otra",
                              "recepcion_lugar": " Secretaría ", "recepcion_horario": "9 a 12", "resolucion_hcf": "Res. CF 45/2026"},
                             ["docencia"])
    assert errores == [] and (x["recepcion_lugar"], x["recepcion_horario"], x["resolucion_hcf"]) == ("Secretaría", "9 a 12", "Res. CF 45/2026")
    assert "reglamento" not in x          # al editar no se cambia el reglamento con que se hizo la convocatoria
    cid = aux.crear(x, gente["dir"]["id"])
    assert _conv(cid)["reglamento"] == aux.REGLAMENTO_VIGENTE
    aux.editar(cid, {**x, "titulo": "Otra, editada"})
    assert _conv(cid)["reglamento"] == aux.REGLAMENTO_VIGENTE and _conv(cid)["titulo"] == "Otra, editada"


# --- Pantallas -------------------------------------------------------------------------------------------------------------

def test_pantallas_con_el_reglamento_vigente_y_con_el_anterior(app, gente, convocatoria):
    c = _como(app, "dir@test.cl")
    pagina = c.get(f"/servicios/auxiliaturas/{convocatoria['cid']}").text
    assert "HCU 424/2023" in pagina and "mín. 5" in pagina and "mín. 18" in pagina and "Recepción de documentos" in pagina
    assert "mín. 10" not in pagina and "17,5" not in pagina
    assert "Lugar de recepción de los documentos" in c.get(f"/servicios/auxiliaturas/{convocatoria['cid']}?editar=1").text
    assert "Lugar de recepción de los documentos" in c.get("/servicios/auxiliaturas/nueva").text
    _antigua(convocatoria["cid"])
    antigua = c.get(f"/servicios/auxiliaturas/{convocatoria['cid']}").text
    assert "HCU 251/2021" in antigua and "mín. 10" in antigua and "mín. 17,5" in antigua
    assert "Recepción de documentos" not in antigua


def test_no_se_crea_una_convocatoria_de_temporada_desde_la_pantalla(app, gente, convocatoria):
    inv = get_db().t.gestion_academica.insert(anio=2027, tipo="INV", fecha_inicio="2027-07-01", fecha_fin="2027-07-31")["id"]
    c = _como(app, "dir@test.cl")
    antes = get_db().q("SELECT COUNT(*) n FROM convocatoria_auxiliatura")[0]["n"]
    r = c.post("/servicios/auxiliaturas", data={"modalidad": "docencia", "gestion_id": str(inv), "numero": "1", "titulo": "Invierno",
                                                "publicacion": date.today().isoformat()}, follow_redirects=False)
    assert r.headers["location"] == "/servicios/auxiliaturas/nueva"
    assert get_db().q("SELECT COUNT(*) n FROM convocatoria_auxiliatura")[0]["n"] == antes
    assert "INV-2027" not in c.get("/servicios/auxiliaturas/nueva").text


# --- Etapa 2: modalidades, requisitos y segunda convocatoria ---------------------------------------------------------------

from datetime import datetime, timedelta, timezone  # noqa: E402

from app.servicios.rutas.auxiliaturas import BASE  # noqa: E402,F401


def _gestion_conv(convocatoria):
    return _conv(convocatoria["cid"])["gestion_id"]


def _nueva(gente, convocatoria, modalidad, titulo="Otra"):
    x, errores = aux.validar({"modalidad": modalidad, "gestion_id": _gestion_conv(convocatoria), "titulo": titulo},
                             list(aux.MODALIDADES))
    assert errores == []
    return aux.crear(x, gente["dir"]["id"])


def test_cuatro_modalidades_y_quien_las_gestiona(app, gente, convocatoria):
    assert list(aux.MODALIDADES) == ["docencia", "investigacion", "interaccion_social", "beca_tesis"]
    assert aux.modalidades_de(gente["dir"]) == list(aux.MODALIDADES)
    assert aux.modalidades_de(gente["iimat"]) == ["investigacion", "interaccion_social", "beca_tesis"]
    assert aux.modalidades_de(gente["doc3"]) == []
    for m in ("interaccion_social", "beca_tesis"):
        cid = _nueva(gente, convocatoria, m)
        assert _como(app, "iimat@test.cl").get(f"/servicios/auxiliaturas/{cid}").status_code == 200
        assert _como(app, "coord@test.cl").get(f"/servicios/auxiliaturas/{cid}").status_code == 200
        assert _como(app, "doc3@test.cl").get(f"/servicios/auxiliaturas/{cid}").status_code == 403
    assert "Beca Tesis" in _como(app, "dir@test.cl").get("/servicios/auxiliaturas/nueva").text


def test_requisitos_precargados_del_art_23_y_el_art_10(app, gente, convocatoria):
    rs = aux.requisitos(convocatoria["cid"])
    assert len(rs) == 13 and rs[0]["texto"] == "Nota dirigida a la Dirección de Carrera"
    assert [r["texto"][:25] for r in rs if r["opcional"]] == ["Certificado de Kardex con"]       # solo egresados
    assert {r["clave"] for r in rs if r["acredita"] == "sistema"} == {"gestiones", "materias"}
    assert sum(r["acredita"] == "documento" for r in rs) == 6 and sum(r["acredita"] == "declaracion" for r in rs) == 5
    textos = " ".join(r["texto"] for r in rs)
    assert "carnet de identidad" in textos and "Carta de compromiso" in textos and "foliados" in textos and "título profesional" in textos
    # La Beca Tesis exige haber concluido los estudios y el proyecto aprobado; ya no es una declaración de «estudiante regular».
    beca = aux.requisitos(_nueva(gente, convocatoria, "beca_tesis"))
    assert not any(r["opcional"] for r in beca)
    assert any("homologado por el Consejo Facultativo" in r["texto"] for r in beca)
    assert not any("estudiante regular" in r["texto"] for r in beca)


def test_proyectos_por_modalidad(app, gente):
    from app.investigacion import proyectos
    uid = gente["doc1"]["id"]
    inv = proyectos.crear({"nombre": "Anillos", "estado": "vigente"}, uid, uid, tipo="institucional", clase="investigacion")
    soc = proyectos.crear({"nombre": "Matemática en el barrio", "estado": "vigente"}, uid, uid, tipo="institucional",
                          clase="interaccion_social")
    indiv = proyectos.crear({"nombre": "Individual", "estado": "vigente"}, uid, uid)
    assert {p["id"] for p in aux.proyectos_vigentes("interaccion_social")} == {soc}
    for m in ("investigacion", "beca_tesis"):
        assert {p["id"] for p in aux.proyectos_vigentes(m)} == {inv, indiv}


def test_item_de_interaccion_social_con_su_proyecto(app, gente, convocatoria):
    from app.investigacion import proyectos
    uid = gente["doc1"]["id"]
    soc = proyectos.crear({"nombre": "Matemática en el barrio", "estado": "vigente"}, uid, uid, tipo="institucional",
                          clase="interaccion_social")
    inv = proyectos.crear({"nombre": "Anillos", "estado": "vigente"}, uid, uid, tipo="institucional", clase="investigacion")
    c = _conv(_nueva(gente, convocatoria, "interaccion_social"))
    # Un proyecto de investigación no sirve en una convocatoria de interacción social (y sin título propio no hay ítem).
    assert aux.agregar_item(c, {"proyecto_id": str(inv), "plazas": "1", "horas": "20"}) == ["Elija el proyecto o escriba el nombre de la auxiliatura."]
    assert aux.items(c["id"]) == []
    assert aux.agregar_item(c, {"proyecto_id": str(soc), "plazas": "2", "horas": "20"}) == []
    assert [(i["titulo"], i["proyecto_id"], i["plazas"]) for i in aux.items(c["id"])] == [("Matemática en el barrio", soc, 2)]


def test_no_mas_de_dos_gestiones_en_el_mismo_proyecto(app, gente, convocatoria):
    from app.investigacion import proyectos
    uid = gente["doc1"]["id"]
    soc = proyectos.crear({"nombre": "Matemática en el barrio", "estado": "vigente"}, uid, uid, tipo="institucional",
                          clase="interaccion_social")
    db = get_db()
    ext = gente["Sofía"]["externo"]
    assert aux.veces_auxiliar(ext, None, None, soc) == 0
    for anio, tipo in ((2024, "I"), (2024, "II"), (2025, "I")):
        g = db.t.gestion_academica.insert(anio=anio, tipo=tipo, fecha_inicio=f"{anio}-03-01", fecha_fin=f"{anio}-07-31")["id"]
        c = db.t.convocatoria_auxiliatura.insert(gestion_id=g, modalidad="interaccion_social", titulo=f"Conv {anio}{tipo}",
                                                 creado_por=uid, estado="concluida")["id"]
        i = db.t.item_auxiliatura.insert(convocatoria_id=c, proyecto_id=soc, titulo="Matemática en el barrio", fase="concluido")["id"]
        db.t.postulacion_auxiliatura.insert(item_id=i, externo_id=ext, estado="titular")
    assert aux.veces_auxiliar(ext, None, None, soc) == 3 and aux.veces_auxiliar(ext, None, None, None) == 0


def _tres_items(convocatoria):
    db = get_db()
    ids = [convocatoria["iid"]]
    for sigla in ("MAT-103", "MAT-104"):
        a = db.t.asignatura.insert(sigla=sigla, nombre=f"Materia {sigla}", departamento="MAT")["id"]
        db.t.oferta.insert(gestion_id=_gestion_conv(convocatoria), asignatura_id=a)
        assert aux.agregar_item(_conv(convocatoria["cid"]), {"asignatura_id": a, "plazas": "1", "horas": "20"}) == []
        ids.append(max(i["id"] for i in aux.items(convocatoria["cid"])))
    return ids


def test_no_mas_de_dos_materias_por_convocatoria(app, gente, convocatoria):
    ids = _tres_items(convocatoria)
    for i in ids:
        assert aux.fijar_tribunal(aux.item(i), [gente["doc1"]["id"], gente["doc2"]["id"]],
                                  [gente["Ana"]["uid"], gente["Pedro"]["uid"]]) == []
    get_db().execute("UPDATE convocatoria_auxiliatura SET resolucion = 'Res. 1' WHERE id = ?", [convocatoria["cid"]])
    assert aux.publicar(convocatoria["cid"]) == []
    ps = []
    for i in ids:
        pid, errores = aux.postular(i, gente["Sofía"]["externo"])
        assert errores == []
        _completar(aux.postulacion(pid), gente)
        ps.append(pid)
    assert aux.enviar(ps[0]) == [] and aux.enviar(ps[1]) == []
    r = aux.enviar(ps[2])
    assert r and "No postular a más de dos materias en esta convocatoria" in r[0]
    assert aux.retirar(ps[1]) == []                              # al retirar una, la tercera ya puede enviarse
    assert aux.enviar(ps[2]) == []


def test_ver_los_requisitos_no_escribe(app, gente, convocatoria):
    """La fila de cada requisito nace al declarar o subir algo, no al abrir la postulación (PLAN §72)."""
    _publicar(gente, convocatoria)
    pid, _ = aux.postular(convocatoria["iid"], gente["Sofía"]["externo"])
    antes = get_db().q("SELECT COUNT(*) n FROM postulacion_requisito")[0]["n"]
    reqs = aux.requisitos_de(aux.postulacion(pid))
    assert get_db().q("SELECT COUNT(*) n FROM postulacion_requisito")[0]["n"] == antes
    assert all(not r["cumplido"] for r in reqs if r["acredita"] in ("documento", "declaracion") and not r["opcional"])
    r = next(r for r in reqs if r["acredita"] == "declaracion")
    aux.declarar(pid, r["id"], True)
    assert next(x for x in aux.requisitos_de(aux.postulacion(pid)) if x["id"] == r["id"])["cumplido"]


def test_un_requisito_opcional_no_impide_enviar(app, gente, convocatoria):
    from app.investigacion import adjuntos
    _publicar(gente, convocatoria)
    pid, _ = aux.postular(convocatoria["iid"], gente["Sofía"]["externo"])
    for r in aux.requisitos_de(aux.postulacion(pid)):
        if r["acredita"] == "documento" and not r["opcional"]:
            adjuntos.guardar("requisito_postulacion", aux.fila_requisito(pid, r["id"])["id"], "doc.pdf", b"%PDF-1.4\n" + b"0" * 64, gente["dir"]["id"])
        elif r["acredita"] == "declaracion":
            aux.declarar(pid, r["id"], True)
    aux.guardar_propuesta(pid, "Prácticas semanales")
    assert [r["cumplido"] for r in aux.requisitos_de(aux.postulacion(pid)) if r["opcional"]] == [False]    # no es egresada
    assert aux.faltantes_envio(aux.postulacion(pid)) == [] and aux.enviar(pid) == []


# --- Segunda convocatoria ---------------------------------------------------------------------------------------------------

def _primera_concluida(gente, convocatoria, cubiertas=0, plazas=2):
    """La primera convocatoria concluida con `cubiertas` de `plazas` plazas ocupadas por un titular."""
    db = get_db()
    db.execute("UPDATE item_auxiliatura SET plazas = ?, fase = 'concluido' WHERE id = ?", [plazas, convocatoria["iid"]])
    nombres = ("Sofía", "Luis", "Rosa")
    for n in nombres[:cubiertas]:
        db.t.postulacion_auxiliatura.insert(item_id=convocatoria["iid"], externo_id=gente[n]["externo"], estado="titular")
    db.t.postulacion_auxiliatura.insert(item_id=convocatoria["iid"], externo_id=gente["Rosa"]["externo"], estado="no_seleccionada") \
        if cubiertas < 3 else None
    db.execute("UPDATE convocatoria_auxiliatura SET estado = 'concluida' WHERE id = ?", [convocatoria["cid"]])
    it = aux.item(convocatoria["iid"])
    assert aux.fijar_tribunal(it, [gente["doc1"]["id"], gente["doc2"]["id"]], [gente["Ana"]["uid"], gente["Pedro"]["uid"]]) == []
    db.execute("INSERT INTO fase_auxiliatura (item_id, fase) VALUES (?, 'oral')", [convocatoria["iid"]])
    return _conv(convocatoria["cid"])


def test_un_item_sin_postulantes_queda_desierto_al_cerrar_la_recepcion(app, gente, convocatoria):
    _publicar(gente, convocatoria)
    get_db().execute("UPDATE convocatoria_auxiliatura SET cierre = '2020-01-01T00:00' WHERE id = ?", [convocatoria["cid"]])
    assert aux.cerrar_fase(aux.item(convocatoria["iid"]), gente["dir"]["id"]) == []
    assert aux.item(convocatoria["iid"])["fase"] == "concluido"
    assert aux.obtener(convocatoria["cid"])["estado"] == "concluida"
    assert aux.sin_cubrir(aux.item(convocatoria["iid"])) == 1 and aux.puede_generar_segunda(_conv(convocatoria["cid"]))


def test_segunda_convocatoria_con_las_plazas_sin_cubrir(app, gente, convocatoria):
    c = _primera_concluida(gente, convocatoria, cubiertas=1, plazas=2)
    assert aux.puede_generar_segunda(c)
    nuevo, errores = aux.generar_segunda(c["id"], gente["dir"]["id"])
    assert errores == []
    s = _conv(nuevo)
    assert (s["numero"], s["estado"], s["primera_id"], s["reglamento"], s["modalidad"]) == (2, "borrador", c["id"], c["reglamento"], "docencia")
    assert s["titulo"].endswith(", segunda convocatoria") and s["publicacion"] is None and s["resolucion"] is None
    assert (s["recepcion_lugar"], s["recepcion_horario"]) == (c["recepcion_lugar"], c["recepcion_horario"])
    assert [(r["texto"], r["acredita"], r["opcional"], r["clave"]) for r in aux.requisitos(nuevo)] == \
        [(r["texto"], r["acredita"], r["opcional"], r["clave"]) for r in aux.requisitos(c["id"])]
    [item] = aux.items(nuevo)
    assert (item["plazas"], item["asignatura_id"], item["horas"], item["fase"]) == (1, convocatoria["asignatura"], 40, "postulacion")
    assert {(m["usuario_id"], m["tipo"]) for m in item["tribunal"]} == {(m["usuario_id"], m["tipo"]) for m in aux.items(c["id"])[0]["tribunal"]}
    # Solo una segunda por primera, y la segunda no genera otra.
    assert aux.segunda_de(c["id"])["id"] == nuevo and not aux.puede_generar_segunda(_conv(c["id"]))
    assert aux.generar_segunda(c["id"], gente["dir"]["id"])[0] is None
    assert aux.generar_segunda(nuevo, gente["dir"]["id"])[0] is None


def test_no_hay_segunda_si_la_primera_cubrio_todo_o_no_ha_concluido(app, gente, convocatoria):
    assert aux.generar_segunda(convocatoria["cid"], gente["dir"]["id"])[0] is None            # borrador
    c = _primera_concluida(gente, convocatoria, cubiertas=2, plazas=2)
    assert not aux.puede_generar_segunda(c) and aux.generar_segunda(c["id"], gente["dir"]["id"])[0] is None


def test_plazo_de_72_horas_de_la_segunda(app, gente, convocatoria):
    c = _primera_concluida(gente, convocatoria, cubiertas=0, plazas=1)
    nuevo, _ = aux.generar_segunda(c["id"], gente["dir"]["id"])
    ok, texto = aux.chequeo_segunda(_conv(nuevo))
    assert ok is False and "debe publicarse hasta el" in texto and "72 horas" in texto
    get_db().execute("UPDATE convocatoria_auxiliatura SET publicacion = ? WHERE id = ?", [date.today().isoformat(), nuevo])
    assert aux.chequeo_segunda(_conv(nuevo))[0] is True
    get_db().execute("UPDATE fase_auxiliatura SET cerrada_en = ?", [(datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")])
    ok, texto = aux.chequeo_segunda(_conv(nuevo))
    assert ok is False and "Pasaron más de 72 horas" in texto
    assert aux.chequeo_segunda(_conv(c["id"])) is None                                          # la primera no tiene plazo


def test_pantallas_de_la_segunda_convocatoria(app, gente, convocatoria):
    c = _primera_concluida(gente, convocatoria, cubiertas=0, plazas=1)
    d = _como(app, "dir@test.cl")
    pagina = d.get(f"/servicios/auxiliaturas/{c['id']}").text
    assert "Generar la segunda convocatoria" in pagina
    assert _como(app, "doc3@test.cl").post(f"/servicios/auxiliaturas/{c['id']}/segunda").status_code == 403
    r = d.post(f"/servicios/auxiliaturas/{c['id']}/segunda", follow_redirects=False)
    nuevo = int(r.headers["location"].rsplit("/", 1)[1])
    assert nuevo == aux.segunda_de(c["id"])["id"]
    segunda = d.get(f"/servicios/auxiliaturas/{nuevo}").text
    assert "Es la segunda convocatoria de" in segunda and "arts. 13 y 14" in segunda and "debe publicarse hasta el" in segunda
    primera = d.get(f"/servicios/auxiliaturas/{c['id']}").text
    assert "Generar la segunda convocatoria" not in primera and "Segunda convocatoria:" in primera
    assert get_db().q("SELECT accion FROM auditoria ORDER BY id DESC LIMIT 1")[0]["accion"] == "generar_segunda_convocatoria_auxiliatura"


def test_el_estudiante_ve_los_requisitos_opcionales_y_el_plan_de_trabajo(app, gente, convocatoria, buzon):
    from tests.test_servicios import _como_estudiante
    _publicar(gente, convocatoria)
    s = _como_estudiante(app, "sofia@correo.bo", buzon)
    r = s.post(f"/estudiante/auxiliaturas/item/{convocatoria['iid']}/postular", follow_redirects=False)
    pagina = s.get(r.headers["location"]).text
    assert "Solo si corresponde" in pagina and "Plan de trabajo de la materia, proyecto o programa que postula" in pagina
    assert "Requisitos · 2 de 12" in pagina


# --- Etapa 3: la comisión (art. 15) -------------------------------------------------------------------------------------------

from app.comun import usuarios  # noqa: E402


def _titular_de_la_materia(convocatoria, uid):
    oferta = get_db().q("SELECT id FROM oferta WHERE gestion_id = ? AND asignatura_id = ?",
                        [_gestion_conv(convocatoria), convocatoria["asignatura"]])[0]["id"]
    get_db().t.oferta_docente.insert(oferta_id=oferta, usuario_id=uid, rol="titular")


def _contratado():
    from app.comun import vinculos
    uid = usuarios.crear("contratado@test.cl", "Cora", "Contratada", "Clave-servicios-1", debe_cambiar_pass=False)["id"]
    vinculos.agregar(uid, "contratado", "2020-01-01", "2099-12-31")
    return uid


def _est(gente):
    return [gente["Ana"]["uid"], gente["Pedro"]["uid"]]


def test_los_docentes_de_la_comision_deben_ser_titulares(app, gente, convocatoria):
    contratado = _contratado()
    it = aux.item(convocatoria["iid"])
    errores = aux.fijar_tribunal(it, [gente["doc1"]["id"], contratado], _est(gente))
    assert errores == ["Los dos docentes de la comisión deben ser titulares (art. 15)."]
    assert aux.tribunal(it["id"]) == []
    # Una convocatoria hecha con el reglamento de 2021 no tiene esa regla.
    _antigua(convocatoria["cid"])
    assert aux.fijar_tribunal(aux.item(convocatoria["iid"]), [gente["doc1"]["id"], contratado], _est(gente)) == []


def test_uno_de_los_docentes_es_el_titular_de_la_materia(app, gente, convocatoria):
    it = aux.item(convocatoria["iid"])
    # Sin titular asignado a la materia aún no se puede comprobar: se designa y se avisa.
    assert aux.fijar_tribunal(it, [gente["doc2"]["id"], gente["doc3"]["id"]], _est(gente)) == []
    assert "aún no tiene un docente titular asignado" in aux.avisos_comision(aux.item(convocatoria["iid"]))[0]
    _titular_de_la_materia(convocatoria, gente["doc1"]["id"])
    errores = aux.fijar_tribunal(it, [gente["doc2"]["id"], gente["doc3"]["id"]], _est(gente))
    assert errores == ["Uno de los dos docentes debe ser el titular responsable de la materia en la gestión (art. 15, a)."]
    assert aux.fijar_tribunal(it, [gente["doc1"]["id"], gente["doc3"]["id"]], _est(gente)) == []
    assert aux.avisos_comision(aux.item(convocatoria["iid"])) == []


def test_comision_de_investigacion_con_investigadores_titulares(app, gente, convocatoria):
    cid = _nueva(gente, convocatoria, "investigacion")
    c = _conv(cid)
    assert aux.agregar_item(c, {"titulo": "Apoyo al proyecto de álgebra", "plazas": "1", "horas": "20"}) == []
    it = aux.items(cid)[0]
    no_inv = usuarios.crear("noinv@test.cl", "Nora", "NoInvestigadora", "Clave-servicios-1", es_investigador=False,
                            debe_cambiar_pass=False, categoria="titular", fecha_ingreso="2020-01-01")["id"]
    assert aux.fijar_tribunal(it, [gente["doc1"]["id"], no_inv], _est(gente)) == ["Los dos docentes deben ser investigadores titulares (art. 15, b)."]
    assert aux.fijar_tribunal(it, [gente["doc1"]["id"], gente["doc2"]["id"]], _est(gente)) == []
    beca = _conv(_nueva(gente, convocatoria, "beca_tesis"))
    assert aux.agregar_item(beca, {"titulo": "Tesis en teoría de anillos", "plazas": "1", "horas": "20"}) == []
    assert aux.fijar_tribunal(aux.items(beca["id"])[0], [gente["doc1"]["id"], no_inv], _est(gente))[0].startswith("Los dos docentes deben ser investigadores")


def test_comision_de_interaccion_social_con_el_responsable_del_proyecto(app, gente, convocatoria):
    from app.investigacion import proyectos
    resp = gente["doc1"]["id"]
    soc = proyectos.crear({"nombre": "Matemática en el barrio", "estado": "vigente"}, resp, resp, tipo="institucional",
                          clase="interaccion_social")
    c = _conv(_nueva(gente, convocatoria, "interaccion_social"))
    assert aux.agregar_item(c, {"proyecto_id": str(soc), "plazas": "1", "horas": "20"}) == []
    assert aux.agregar_item(c, {"titulo": "Taller sin proyecto", "plazas": "1", "horas": "20"}) == []
    con, sin = sorted(aux.items(c["id"]), key=lambda i: i["proyecto_id"] is None)
    assert aux.fijar_tribunal(con, [gente["doc2"]["id"], gente["doc3"]["id"]], _est(gente)) == \
        ["Uno de los dos docentes debe ser el responsable del proyecto (art. 15, c)."]
    assert aux.fijar_tribunal(con, [resp, gente["doc3"]["id"]], _est(gente)) == [] and aux.avisos_comision(aux.item(con["id"])) == []
    assert aux.fijar_tribunal(sin, [gente["doc2"]["id"], gente["doc3"]["id"]], _est(gente)) == []        # sin proyecto no se puede comprobar
    assert "no tiene proyecto" in aux.avisos_comision(aux.item(sin["id"]))[0]


def test_sin_la_resolucion_de_la_comision_no_se_cierra_la_recepcion(app, gente, convocatoria):
    _publicar(gente, convocatoria)
    aux.guardar_resolucion_comision(convocatoria["cid"], "", "")
    get_db().execute("UPDATE convocatoria_auxiliatura SET cierre = '2020-01-01T00:00' WHERE id = ?", [convocatoria["cid"]])
    r = aux.cerrar_fase(aux.item(convocatoria["iid"]), gente["dir"]["id"])
    assert r == ["No se puede cerrar: falta el número de la resolución del Consejo de Carrera que designa la comisión (art. 15)."]
    aux.guardar_resolucion_comision(convocatoria["cid"], " Res. CC 130/2026 ", "Res. CF 52/2026")
    c = _conv(convocatoria["cid"])
    assert (c["comision_resolucion"], c["comision_resolucion_hcf"]) == ("Res. CC 130/2026", "Res. CF 52/2026")
    assert aux.cerrar_fase(aux.item(convocatoria["iid"]), gente["dir"]["id"]) == []
    # La convocatoria de 2021 nunca pidió esa resolución.
    otra = _nueva(gente, convocatoria, "docencia", "Antigua")
    _antigua(otra)
    assert not any("comisión" in x for x in aux.faltantes_cierre({"convocatoria_id": otra, "fase": "postulacion", "id": 0}))


def test_pantallas_de_la_comision(app, gente, convocatoria):
    d = _como(app, "dir@test.cl")
    pagina = d.get(f"/servicios/auxiliaturas/{convocatoria['cid']}").text
    assert "falta la resolución del Consejo de Carrera que la designa" in pagina and "Resolución de la comisión (art. 15)" in pagina
    r = d.post(f"/servicios/auxiliaturas/{convocatoria['cid']}/comision", data={"comision_resolucion": "Res. CC 130/2026",
                                                                                "comision_resolucion_hcf": "Res. CF 52/2026"},
               follow_redirects=False)
    assert r.status_code == 303 and _conv(convocatoria["cid"])["comision_resolucion"] == "Res. CC 130/2026"
    pagina = d.get(f"/servicios/auxiliaturas/{convocatoria['cid']}").text
    assert "designada por Res. CC 130/2026" in pagina and "aprobada por Res. CF 52/2026" in pagina
    assert get_db().q("SELECT accion FROM auditoria ORDER BY id DESC LIMIT 1")[0]["accion"] == "resolucion_comision_auxiliatura"
    assert _como(app, "doc3@test.cl").post(f"/servicios/auxiliaturas/{convocatoria['cid']}/comision",
                                           data={"comision_resolucion": "x"}).status_code == 403
    item = d.get(f"/servicios/auxiliaturas/item/{convocatoria['iid']}").text
    assert "docente titular responsable de la materia" in item and "art. 15, a" in item
    _antigua(convocatoria["cid"])
    assert d.post(f"/servicios/auxiliaturas/{convocatoria['cid']}/comision", data={"comision_resolucion": "y"}).status_code == 403
    assert "Resolución de la comisión" not in d.get(f"/servicios/auxiliaturas/{convocatoria['cid']}").text


def test_el_formulario_del_tribunal_muestra_el_error_de_la_regla(app, gente, convocatoria):
    contratado = _contratado()
    d = _como(app, "dir@test.cl")
    r = d.post(f"/servicios/auxiliaturas/item/{convocatoria['iid']}/tribunal",
               data={"docente1": str(gente["doc1"]["id"]), "docente2": str(contratado),
                     "estudiante1": str(gente["Ana"]["uid"]), "estudiante2": str(gente["Pedro"]["uid"])}, follow_redirects=False)
    assert r.status_code == 303 and aux.tribunal(convocatoria["iid"]) == []


# --- Etapa 4: calificación con los formularios ------------------------------------------------------------------------------

def _hasta_meritos(gente, conv):
    """Una postulante enviada, la recepción cerrada y la habilitación concluida: el ítem queda en méritos."""
    _publicar(gente, conv)
    pid, _ = aux.postular(conv["iid"], gente["Sofía"]["externo"])
    _completar(aux.postulacion(pid), gente)
    assert aux.enviar(pid) == []
    get_db().execute("UPDATE convocatoria_auxiliatura SET cierre = '2020-01-01T00:00' WHERE id = ?", [conv["cid"]])
    assert aux.cerrar_fase(aux.item(conv["iid"]), gente["dir"]["id"]) == []
    _calificar(conv["iid"], gente, {pid: 1})
    assert aux.cerrar_fase(aux.item(conv["iid"]), gente["dir"]["id"]) == []
    assert aux.item(conv["iid"])["fase"] == "meritos"
    return pid


MERITOS = {"1a": "2", "1b": "3", "2a": "2", "2b": "1", "3a": "2", "3b": "3", "4": "85", "5a": "1", "5b": "1", "6a": "1", "6b": "1"}


def test_los_meritos_se_califican_con_el_formulario(app, gente, convocatoria):
    pid = _hasta_meritos(gente, convocatoria)
    it = aux.item(convocatoria["iid"])
    assert aux.calificar_detalle(it, gente["doc1"]["id"], pid, MERITOS, "Buen currículum") == []
    assert aux.nota(pid, "meritos") == 24.5 and aux.detalle(pid, "meritos", gente["doc1"]["id"])["4"] == 85
    # Corregir reemplaza el detalle y la nota del miembro; los otros miembros no cambian.
    assert aux.calificar_detalle(it, gente["doc1"]["id"], pid, {**MERITOS, "4": "95"}) == []
    assert aux.nota(pid, "meritos") == 26.5 and len(aux.calificaciones(pid, "meritos")) == 1
    assert aux.calificar_detalle(it, gente["doc2"]["id"], pid, {"4": "60"}) == []
    assert aux.nota(pid, "meritos") == (26.5 + 4) / 2
    # Lo que no se puede: no ser del tribunal, un valor inválido (nada se guarda) o un postulante ajeno a la fase.
    assert aux.calificar_detalle(it, gente["doc3"]["id"], pid, MERITOS) == ["Solo califican los miembros del tribunal."]
    errores = aux.calificar_detalle(it, gente["doc2"]["id"], pid, {"1a": "mucho"})
    assert errores == ["«1a»: escriba un número."] and aux.detalle(pid, "meritos", gente["doc2"]["id"])["4"] == 60
    assert aux.calificar_detalle(it, gente["doc1"]["id"], 999, MERITOS) == ["Ese postulante no está en esta fase."]


def test_con_el_reglamento_antiguo_no_hay_formulario(app, gente, convocatoria):
    _antigua(convocatoria["cid"])
    pid = _hasta_meritos(gente, convocatoria)
    it = aux.item(convocatoria["iid"])
    assert aux.calificar_detalle(it, gente["doc1"]["id"], pid, MERITOS) == ["Esta fase no se califica con un formulario."]
    assert aux.calificar(it, gente["doc1"]["id"], pid, 20) == []           # la nota única de siempre


def test_pantalla_del_formulario_de_meritos(app, gente, convocatoria):
    pid = _hasta_meritos(gente, convocatoria)
    c = _como(app, "doc1@test.cl")
    pagina = c.get(f"/servicios/auxiliaturas/item/{convocatoria['iid']}").text
    assert "Formulario de méritos" in pagina and "Calificación obtenida en la materia que postula" in pagina
    assert "Curso aprobado" in pagina and "(0 a 30, mínimo 5)" in pagina and f"d_{pid}_1a" in pagina and f"d_{pid}_4" in pagina
    datos = {f"d_{pid}_{k}": v for k, v in MERITOS.items()} | {f"o_{pid}": "Buen currículum"}
    r = c.post(f"/servicios/auxiliaturas/item/{convocatoria['iid']}/calificar", data=datos, follow_redirects=False)
    assert r.status_code == 303 and aux.nota(pid, "meritos") == 24.5
    assert "su puntaje: 24,5 de 30" in c.get(f"/servicios/auxiliaturas/item/{convocatoria['iid']}").text
    # Un formulario en blanco no toca lo ya guardado; un valor inválido tampoco.
    c.post(f"/servicios/auxiliaturas/item/{convocatoria['iid']}/calificar", data={f"d_{pid}_1a": ""})
    c.post(f"/servicios/auxiliaturas/item/{convocatoria['iid']}/calificar", data={f"d_{pid}_1a": "x"})
    assert aux.nota(pid, "meritos") == 24.5
    # Los estudiantes del tribunal usan la misma ficha desde su portal.
    assert aux.calificar_detalle(aux.item(convocatoria["iid"]), gente["Ana"]["uid"], pid, {"4": "70"}) == []


def _en_oral(gente, convocatoria, n=2):
    """El ítem en el examen oral con `n` postulantes que siguen en concurso."""
    db = get_db()
    pids = [db.t.postulacion_auxiliatura.insert(item_id=convocatoria["iid"], externo_id=gente[nombre]["externo"], estado="enviada")["id"]
            for nombre in ("Sofía", "Luis", "Rosa")[:n]]
    db.execute("UPDATE item_auxiliatura SET fase = 'oral' WHERE id = ?", [convocatoria["iid"]])
    return pids


def test_el_examen_oral_se_califica_con_la_rubrica(app, gente, convocatoria):
    pid, _ = _en_oral(gente, convocatoria)
    it = aux.item(convocatoria["iid"])
    assert aux.fijar_tribunal(it, [gente["doc1"]["id"], gente["doc2"]["id"]], [gente["Ana"]["uid"], gente["Pedro"]["uid"]]) == []
    rubrica = {"conocimiento": "6", "preparacion": "7", "didactica": "9", "metodologia": "4", "respuestas": "4,5"}
    assert aux.calificar_detalle(it, gente["doc1"]["id"], pid, rubrica) == [] and aux.nota(pid, "oral") == 30.5
    errores = aux.calificar_detalle(it, gente["doc2"]["id"], pid, {"conocimiento": "8", "didactica": "11"})
    assert errores == ["Conocimiento del tema: va de 0 a 7.", "Didáctica: va de 0 a 10."]
    assert aux.nota(pid, "oral") == 30.5
    c = _como(app, "doc2@test.cl")
    pagina = c.get(f"/servicios/auxiliaturas/item/{convocatoria['iid']}").text
    assert "Formulario de examen oral" in pagina and "20 minutos de exposición y 10 de preguntas" in pagina and "Conocimiento del tema (0 a 7)" in pagina


def test_orden_de_participacion_en_el_oral(app, gente, convocatoria):
    a, b = _en_oral(gente, convocatoria)
    it = aux.item(convocatoria["iid"])
    assert aux.fijar_orden_oral(it, [(a, "2", "09:30"), (b, "1", "09:00")]) == []
    assert {p["id"]: (p["orden_oral"], p["hora_oral"]) for p in aux.activos(convocatoria["iid"])} == {a: (2, "09:30"), b: (1, "09:00")}
    assert aux.fijar_orden_oral(it, [(a, "1", ""), (b, "1", "")]) == ["Dos postulantes no pueden tener el mismo orden."]
    assert aux.fijar_orden_oral(it, [(a, "1", "25:00")]) == ["La hora va como HH:MM."]
    assert aux.fijar_orden_oral(it, [(a, "x", "")]) == ["Indique un orden (1, 2, 3…) para cada postulante que participa."]
    assert aux.fijar_orden_oral(it, [(999, "1", "")]) != []
    assert aux.fijar_orden_oral(it, [(a, "", ""), (b, "", "")]) == []                         # en blanco: se borra
    assert {p["orden_oral"] for p in aux.activos(convocatoria["iid"])} == {None}


def test_pantalla_del_sorteo_y_del_orden(app, gente, convocatoria):
    pids = _en_oral(gente, convocatoria)
    it = aux.item(convocatoria["iid"])
    assert aux.fijar_tribunal(it, [gente["doc1"]["id"], gente["doc2"]["id"]], [gente["Ana"]["uid"], gente["Pedro"]["uid"]]) == []
    d = _como(app, "dir@test.cl")
    pagina = d.get(f"/servicios/auxiliaturas/item/{convocatoria['iid']}").text
    assert "Cinco temas propuestos por la comisión" in pagina and "formulario 3" not in pagina       # el orden aparece tras el sorteo
    d.post(f"/servicios/auxiliaturas/item/{convocatoria['iid']}/tema", data={"temas": "Uno\nDos\nTres"})
    assert aux.item(convocatoria["iid"])["tema_oral"] is None
    d.post(f"/servicios/auxiliaturas/item/{convocatoria['iid']}/tema", data={"temas": "Uno\nDos\nTres\nCuatro\nCinco"})
    pagina = d.get(f"/servicios/auxiliaturas/item/{convocatoria['iid']}").text
    assert "Tema sorteado:" in pagina and "Cinco temas propuestos" not in pagina and "formulario 3" in pagina
    d.post(f"/servicios/auxiliaturas/item/{convocatoria['iid']}/orden",
           data={f"orden_{pids[0]}": "2", f"hora_{pids[0]}": "10:00", f"orden_{pids[1]}": "1", f"hora_{pids[1]}": "09:00"})
    assert {p["id"]: p["orden_oral"] for p in aux.activos(convocatoria["iid"])} == {pids[0]: 2, pids[1]: 1}
    assert _como(app, "doc3@test.cl").post(f"/servicios/auxiliaturas/item/{convocatoria['iid']}/orden", data={}).status_code == 403


def test_con_el_reglamento_antiguo_el_sorteo_acepta_dos_temas_y_se_puede_repetir(app, gente, convocatoria):
    _antigua(convocatoria["cid"])
    _en_oral(gente, convocatoria)
    it = aux.item(convocatoria["iid"])
    assert aux.sortear_tema(it, "Uno\nDos") == [] and aux.sortear_tema(aux.item(convocatoria["iid"]), "Uno\nDos") == []
    assert aux.sortear_tema(it, "Uno") == ["Escriba al menos dos temas, uno por línea."]


def _cierre(iid, fase, cuando):
    get_db().execute("INSERT OR REPLACE INTO fase_auxiliatura (item_id, fase, cerrada_en) VALUES (?, ?, ?)", [iid, fase, cuando.strftime("%Y-%m-%d %H:%M:%S")])


def test_avisos_de_los_plazos_del_reglamento(app, gente, convocatoria):
    iid = convocatoria["iid"]
    assert aux.avisos_plazos(aux.item(iid)) == []
    examen = datetime(2027, 1, 20, 9, 0)
    get_db().execute("UPDATE convocatoria_auxiliatura SET examen = ? WHERE id = ?", [examen.strftime("%Y-%m-%dT%H:%M"), convocatoria["cid"]])
    utc = lambda local: local.astimezone().astimezone(timezone.utc).replace(tzinfo=None)  # noqa: E731
    # Todo a tiempo: méritos antes del examen, escrito a las 10 horas, oral a las 5 horas del sorteo.
    _cierre(iid, "meritos", utc(examen - timedelta(hours=2)))
    _cierre(iid, "escrito", utc(examen + timedelta(hours=10)))
    get_db().execute("UPDATE item_auxiliatura SET tema_oral_en = ? WHERE id = ?", [utc(examen + timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S"), iid])
    _cierre(iid, "oral", utc(examen + timedelta(hours=35)))
    assert aux.avisos_plazos(aux.item(iid)) == []
    # Fuera de plazo.
    _cierre(iid, "meritos", utc(examen + timedelta(hours=1)))
    _cierre(iid, "escrito", utc(examen + timedelta(hours=30)))
    _cierre(iid, "oral", utc(examen + timedelta(hours=80)))
    avisos = aux.avisos_plazos(aux.item(iid))
    assert len(avisos) == 3 and "méritos debían publicarse antes del examen escrito" in avisos[0]
    assert "dentro de las 24 horas siguientes al examen" in avisos[1] and "24 horas posteriores al sorteo" in avisos[2]
    # El desempate tiene 48 horas desde los resultados del oral.
    get_db().t.postulacion_auxiliatura.insert(item_id=iid, externo_id=gente["Sofía"]["externo"], estado="empate")
    assert any("desempate debe rendirse dentro de las 48 horas" in a and "art. 20" in a for a in aux.avisos_plazos(aux.item(iid)))
    _antigua(convocatoria["cid"])
    assert aux.avisos_plazos(aux.item(iid)) == []
