"""Plan de mejora y evaluación externa (PLAN §57, etapa 6): acciones, avances, estados y evaluaciones externas."""
from datetime import date

import pytest

from app.calidad import autoevaluacion as ae
from app.calidad import evidencias, indicadores, marco, mejora
from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX, login

CLAVE = "Clave-mejora-1"


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def test_flujo_basico(carrera):
    assert carrera.get("/calidad/mejora").status_code == 200
    uid = usuarios.por_email("admin@test.cl")["id"]
    carrera.post("/calidad/mejora/acciones", headers=HX,
                 data={"titulo": "Plan de retención", "plazo": "2026-12-31", "responsable_id": str(uid),
                       "prioridad": "alta", "origen": "otro"})
    a = mejora.acciones(_marco()["id"])[0]
    url = f"/calidad/mejora/acciones/{a['id']}"
    assert carrera.get(url).status_code == 200
    carrera.post(f"{url}/avances", headers=HX, data={"texto": "Primer taller.", "porcentaje": "40"})
    assert mejora.obtener(a["id"])["estado"] == "en_curso"
    carrera.post(f"{url}/cumplir", headers=HX, data={"fecha": "2026-11-01"})
    assert mejora.obtener(a["id"])["estado"] == "cumplida"
    carrera.post("/calidad/mejora/externas", headers=HX, data={"organismo": "Pares", "tipo": "pares"})
    x = mejora.externas(_marco()["id"])[0]
    carrera.post(f"/calidad/mejora/externas/{x['id']}/recomendaciones", headers=HX, data={"texto": "Una\nDos"})
    assert len(mejora.externa(x["id"])["lista_recomendaciones"]) == 2
    for p in ("/calidad/mejora/externas", f"/calidad/mejora/externas/{x['id']}", "/calidad/mejora/xlsx",
              "/calidad/mejora/debilidades"):
        assert carrera.get(p).status_code == 200, p


def _accion(uid, **kw):
    mid = _marco()["id"]
    x, err = mejora.validar({"titulo": "Acción", "plazo": "2026-12-31", "responsable_id": str(uid), **kw}, mid)
    assert not err, err
    return mejora.obtener(mejora.crear(mid, x, uid))


def test_validaciones_y_estados(carrera):
    mid = _marco()["id"]
    uid = usuarios.por_email("admin@test.cl")["id"]
    _, err = mejora.validar({"titulo": "", "plazo": ""}, mid)
    assert "Indique la acción." in err and "Indique el responsable." in err
    ind = mejora.indicadores_del_marco(mid)[0]
    _, err = mejora.validar({"titulo": "x", "plazo": "2026-12-31", "responsable_id": str(uid), "meta": "5"}, mid)
    assert "Una meta necesita un indicador." in err
    a = _accion(uid, indicador_id=str(ind["id"]), meta="5")
    url = f"/calidad/mejora/acciones/{a['id']}"
    carrera.post(f"{url}/cancelar", headers=HX, data={"motivo": " "})
    assert mejora.obtener(a["id"])["estado"] == "pendiente"
    carrera.post(f"{url}/avances", headers=HX, data={"texto": "Avance."})
    carrera.delete(url, headers=HX)
    assert mejora.obtener(a["id"]) is not None          # con avances no se elimina: se cancela
    carrera.post(f"{url}/cancelar", headers=HX, data={"motivo": "Ya no corresponde."})
    a = mejora.obtener(a["id"])
    assert (a["estado"], a["motivo_cancelacion"]) == ("cancelada", "Ya no corresponde.")
    carrera.post(f"{url}/reabrir", headers=HX)
    assert mejora.obtener(a["id"])["estado"] == "en_curso"
    b = _accion(uid)
    carrera.delete(f"/calidad/mejora/acciones/{b['id']}", headers=HX)
    assert mejora.obtener(b["id"]) is None
    acciones = {x["accion"] for x in get_db().q("SELECT accion FROM auditoria")}
    assert {"avance_accion_mejora", "cancelar_accion_mejora", "reabrir_accion_mejora", "eliminar_accion_mejora"} <= acciones


def test_avisos_de_vencimiento(carrera):
    uid = usuarios.por_email("admin@test.cl")["id"]
    a = _accion(uid, plazo="2026-12-01")
    assert mejora.avisar_vencimientos(date(2026, 10, 1)) == 0            # faltan más de 30 días
    assert mejora.avisar_vencimientos(date(2026, 11, 15)) == 1           # por vencer: al responsable
    assert mejora.avisar_vencimientos(date(2026, 11, 20)) == 0           # no se repite
    assert mejora.avisar_vencimientos(date(2026, 12, 2)) == 1            # vencida: responsable = Dirección
    assert mejora.avisar_vencimientos(date(2026, 12, 3)) == 0
    assert a["id"] not in {x["id"] for x in mejora.acciones(_marco()["id"], "vencidas")}   # hoy aún no vence
    b = _accion(uid, plazo="2025-01-31")
    assert [x["id"] for x in mejora.acciones(_marco()["id"], "vencidas")] == [b["id"]]


def test_indicador_acciones_cumplidas(carrera):
    mid = _marco()["id"]
    uid = usuarios.por_email("admin@test.cl")["id"]
    a = _accion(uid, plazo="2025-06-30")
    _accion(uid, plazo="2025-08-31")                                     # vencida sin cumplir
    mejora.cumplir(a, "2025-06-01")
    i = get_db().q("SELECT * FROM indicador_calidad WHERE fuente = 'auto:acciones_cumplidas'")[0]
    assert indicadores.valores_del_anio(mid, 2025)[i["id"]]["valor"] == 50


def test_debilidades_y_recomendaciones(carrera):
    mid = _marco()["id"]
    uid = usuarios.por_email("admin@test.cl")["id"]
    aid = ae.crear(mid, {"nombre": "AE", "desde_anio": 2025, "hasta_anio": 2025}, uid)
    c = evidencias.criterios_del_marco(mid)[0]
    x, _ = ae.validar_juicio({"nivel": "2", "juicio": "Fundado.", "debilidades": "Poca retención\nSin tutoría"},
                             marco.escala(mid))
    ae.guardar_juicio(aid, c["id"], x, uid)
    debs = mejora.debilidades(ae.obtener(aid))
    assert [d["texto"] for d in debs] == ["Poca retención", "Sin tutoría"]
    r = carrera.get(f"/calidad/mejora/acciones/nueva?autoevaluacion={aid}&criterio={c['id']}&debilidad=Poca+retención")
    assert "Poca retención" in r.text
    _accion(uid, origen="autoevaluacion", autoevaluacion_id=str(aid), criterio_id=str(c["id"]), debilidad="Poca retención")
    debs = mejora.debilidades(ae.obtener(aid))
    assert len(debs[0]["acciones"]) == 1 and not debs[1]["acciones"]
    assert "Poca retención" in carrera.get("/calidad/mejora/debilidades").text
    # Una evaluación externa con recomendaciones que ya originaron acciones no se elimina.
    xid = mejora.crear_externa(mid, mejora.validar_externa({"organismo": "Agencia", "tipo": "acreditacion"}, mid)[0], uid)
    mejora.agregar_recomendaciones(xid, "Mejorar la retención", c["id"])
    rec = mejora.externa(xid)["lista_recomendaciones"][0]
    assert "Mejorar la retención" in carrera.get(f"/calidad/mejora/acciones/nueva?recomendacion={rec['id']}").text
    _accion(uid, origen="externa", recomendacion_id=str(rec["id"]))
    carrera.delete(f"/calidad/mejora/externas/{xid}", headers=HX)
    assert mejora.externa(xid) is not None


@pytest.fixture
def cuenta(app):
    def crear(email, rol=None, sigla=None):
        u = usuarios.crear(email, "Prueba", "Mejora", CLAVE, debe_cambiar_pass=False, es_investigador=False)
        if rol:
            permisos.asignar(u["id"], rol, unidades.id_de(sigla))
        return u
    return crear


def test_permisos(client, cuenta):
    d = cuenta("dir@test.cl", "direccion_carrera", "CMAT")
    cuenta("comision@test.cl", "comision_calidad", "UMSA")
    resp = cuenta("resp@test.cl")
    cuenta("otro@test.cl")
    a = _accion(d["id"], responsable_id=str(resp["id"]))
    url = f"/calidad/mejora/acciones/{a['id']}"
    login(client, "comision@test.cl", CLAVE)
    assert client.get(url).status_code == 200 and "Registrar avance" not in client.get(url).text
    assert client.post(f"{url}/cumplir", data={"fecha": "2026-01-01"}).status_code == 403
    assert client.post(f"{url}/avances", data={"texto": "x"}).status_code == 403
    client.get("/logout")
    # El responsable sin rol ve solo sus acciones y registra avances.
    login(client, "resp@test.cl", CLAVE)
    assert client.get("/calidad/mejora").status_code == 200
    assert client.get("/calidad/mejora/externas").status_code == 403
    client.post(f"{url}/avances", headers=HX, data={"texto": "Hecho el taller."})
    assert mejora.obtener(a["id"])["avances"] == 1
    assert client.post(f"{url}/cumplir", data={"fecha": "2026-01-01"}).status_code == 403
    client.get("/logout")
    login(client, "otro@test.cl", CLAVE)
    assert client.get("/calidad/mejora").status_code == 403
    assert client.get(url).status_code == 403
