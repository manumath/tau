"""Cortes de seguimiento del plan de mejora (PLAN §72, etapa 5): congelar, atención, comentarios, cierre con evidencia,
avisos y permisos."""
from datetime import date

from app.calidad import actividades_mejora as am
from app.calidad import cortes_mejora as cm
from app.calidad import evidencias, marco, mejora
from app.comun import notificaciones, permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX, login


def _mid():
    return marco.de_unidad(unidades.id_de("CMAT"))["id"]


def _plan():
    d = usuarios.por_email("admin@test.cl")
    permisos.asignar(d["id"], "direccion_carrera", unidades.id_de("CMAT"))
    r = usuarios.por_email("inv@test.cl")
    x, err = mejora.validar({"codigo": "A4", "titulo": "Retención", "plazo": "2027-12-31", "responsable_id": str(d["id"]),
                             "prioridad": "alta"}, _mid())
    assert not err
    aid = mejora.crear(_mid(), x, d["id"])
    ids = []
    for codigo, inicio, plazo in (("4.1", "2026-01-01", "2026-11-20"), ("4.2", "2026-01-01", "2027-12-31"),
                                  ("4.3", "2026-10-01", "2028-12-31")):
        x, err = am.validar({"codigo": codigo, "descripcion": f"Actividad {codigo}", "inicio": inicio, "plazo": plazo,
                             "responsable_id": str(r["id"])}, _mid())
        assert not err, err
        ids.append(am.crear(aid, x, d["id"]))
    return d, r, ids


def test_abrir_congela_y_ordena_lo_que_pide_atencion(app):
    d, r, (t1, t2, t3) = _plan()
    am.registrar_avance(am.obtener(t3), {"texto": "Hecho algo", "fecha": "2026-11-01", "porcentaje": 10,
                                         "evidencia_id": None}, r["id"])
    assert cm.abrir(_mid(), "trimestral", "2027-01-01", d["id"], hoy=date(2026, 11, 14))[1] == [
        "La fecha del corte no puede ser futura."]
    cid, err = cm.abrir(_mid(), "trimestral", "2026-11-14", d["id"], hoy=date(2026, 11, 14))
    assert not err
    assert cm.abrir(_mid(), "anual", "2026-11-14", d["id"])[1] == ["Ya hay un corte abierto: ciérrelo antes de abrir otro."]
    items = cm.items(cid)
    # 4.1 vence en 6 días (en riesgo); 4.2 y 4.3 están al día y, sin corte anterior, no piden atención.
    assert [(x["codigo"], x["atencion"]) for x in items] == [("4.1", "en_riesgo"), ("4.2", None), ("4.3", None)]
    assert items[2]["ultimo_texto"] == "Hecho algo" and items[2]["avance"] == 10
    # Lo congelado no cambia aunque la actividad cambie.
    am.actualizar(am.obtener(t3), {**am.obtener(t3), "descripcion": "Otro texto"})
    assert cm.items(cid)[2]["descripcion"] == "Actividad 4.3"
    c = cm.obtener(cid)
    assert cm.comentar(c, items[0]["id"], "Pedir reprogramación.", d["id"]) == []
    assert cm.cerrar(c, "Avance razonable.", "", d["id"]) == [
        "Elija el criterio del marco al que se agrega el informe como evidencia."]
    crit = cm.criterio_propuesto(_mid()) or evidencias.criterios_del_marco(_mid())[0]["id"]
    assert cm.cerrar(c, "Avance razonable.", str(crit), d["id"]) == []
    c = cm.obtener(cid)
    assert c["estado"] == "cerrado" and evidencias.obtener(c["evidencia_id"])["nombre_archivo"].endswith(".xlsx")
    assert cm.comentar(c, items[1]["id"], "Tarde", d["id"]) == ["El corte ya está cerrado."]
    assert not cm.eliminar(c)
    # El corte siguiente marca «sin avance desde el corte anterior» a la 4.3, que no avanzó.
    cid2, _ = cm.abrir(_mid(), "trimestral", "2026-11-14", d["id"], hoy=date(2026, 11, 14))
    x3 = next(x for x in cm.items(cid2) if x["codigo"] == "4.3")
    assert x3["atencion"] == "sin_avance"
    r2 = cm.resumen(cid2)
    assert r2["anterior"]["semaforo"]["en_riesgo"] == 1 and r2["previo"]["id"] == cid
    assert cm.a_xlsx(cid2)[:2] == b"PK"


def test_avisos_de_actividades(app):
    d, r, (t1, t2, t3) = _plan()
    assert cm.avisar(date(2026, 11, 14)) >= 1                         # 4.1 vence en 6 días
    asuntos = [n["asunto"] for n in notificaciones.todas(r["id"])]
    assert "Actividad del plan por vencer" in asuntos
    assert cm.avisar(date(2026, 11, 14)) == 0                         # no se repite
    # La acción con actividades no avisa por su cuenta (lo hacen sus actividades).
    assert mejora.avisar_vencimientos(date(2027, 12, 1)) == 0
    # Sin avance desde el último corte, 15 días antes del fin del trimestre.
    cid, _ = cm.abrir(_mid(), "trimestral", "2026-11-14", d["id"], hoy=date(2026, 11, 14))
    crit = evidencias.criterios_del_marco(_mid())[0]["id"]
    cm.cerrar(cm.obtener(cid), "", str(crit), d["id"])
    assert cm.fin_de_trimestre(date(2027, 3, 20)) == date(2027, 3, 31)
    cm.avisar(date(2027, 3, 20))
    assert "Corte del plan de mejora" in [n["asunto"] for n in notificaciones.todas(r["id"])]


def test_pantallas_y_permisos(carrera, client):
    d, r, ids = _plan()
    assert carrera.get("/calidad/mejora/cortes").status_code == 200
    assert carrera.get("/calidad/mejora/cortes/nuevo", headers=HX).status_code == 200
    carrera.post("/calidad/mejora/cortes", headers=HX, data={"tipo": "trimestral", "fecha": date.today().isoformat()})
    c = cm.listar(_mid())[0]
    url = f"/calidad/mejora/cortes/{c['id']}"
    assert "Piden atención" in carrera.get(url).text
    item = next(x for x in cm.items(c["id"]) if x["atencion"])
    resp = carrera.post(f"{url}/comentarios/{item['id']}", headers=HX, data={"texto": "Revisar con el responsable."})
    assert resp.status_code == 200 and "Revisar con el responsable." in resp.text
    assert carrera.get(f"{url}/xlsx").status_code == 200
    assert carrera.get(f"{url}/cerrar", headers=HX).status_code == 200
    crit = evidencias.criterios_del_marco(_mid())[0]["id"]
    carrera.post(f"{url}/cerrar", headers=HX, data={"conclusion": "Bien.", "criterio_id": str(crit)})
    assert cm.obtener(c["id"])["estado"] == "cerrado"
    assert carrera.get("/calidad/mejora/xlsx").status_code == 200       # con actividades y reprogramaciones
    acciones = {x["accion"] for x in get_db().q("SELECT accion FROM auditoria")}
    assert {"abrir_corte_mejora", "comentar_corte_mejora", "cerrar_corte_mejora"} <= acciones
    # El responsable sin rol no ve los cortes.
    carrera.post("/logout", headers=HX)
    usuarios.cambiar_password(r["id"], "Clave-resp-12345", temporal=False)
    login(carrera, "inv@test.cl", "Clave-resp-12345")
    assert carrera.get("/calidad/mejora/cortes").status_code == 403
    assert carrera.get(url).status_code == 403
    assert carrera.post("/calidad/mejora/cortes", headers=HX, data={"tipo": "anual", "fecha": "2026-11-01"}).status_code == 403
