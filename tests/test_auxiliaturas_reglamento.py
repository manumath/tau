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
