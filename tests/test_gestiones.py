"""PLAN §66, etapa 1: ciclo de vida de las gestiones (estado, creación suelta y borrado)."""
from datetime import date
from pathlib import Path

from app.academico import gestiones, oferta, preparacion
from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login


def test_la_migracion_clasifica_las_gestiones_por_sus_fechas(app):
    db = get_db()
    ayer, manana = (date.today().replace(year=date.today().year + d).isoformat() for d in (-1, 1))
    for tipo, ini, fin in (("I", "2020-02-01", "2020-06-30"), ("II", ayer, manana), ("INV", manana, manana)):
        db.t.gestion_academica.insert(anio=2020 + len(tipo), tipo=tipo, fecha_inicio=ini, fecha_fin=fin)
    sql = Path("migrations/0070-estado-de-la-gestion.sql").read_text()
    db.execute("UPDATE gestion_academica SET estado = 'planificacion', activada_en = NULL, concluida_en = NULL")
    db.execute(sql[sql.index("UPDATE gestion_academica"):])
    estados = {g["tipo"]: g["estado"] for g in gestiones.listar() if g["anio"] > 2020}
    assert estados == {"I": "concluida", "II": "activa", "INV": "planificacion"}
    assert gestiones.listar()[-1]["concluida_en"] == "2020-06-30"            # la más antigua


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
