"""Actividades del plan de mejora, avance, semáforo, reprogramaciones y aprobación del plan (PLAN §72, etapa 2)."""
from datetime import date

from app.calidad import actividades_mejora as am
from app.calidad import indicadores, marco, mejora
from app.comun import notificaciones, permisos, unidades, usuarios
from app.comun.db import get_db

HOY = date(2027, 6, 1)


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def _gente():
    d = usuarios.por_email("admin@test.cl")
    permisos.asignar(d["id"], "direccion_carrera", unidades.id_de("CMAT"))
    r = usuarios.por_email("inv@test.cl")
    return {**d, "es_admin": True}, r


def _accion(uid, **kw):
    mid = _marco()["id"]
    x, err = mejora.validar({"titulo": "Retención", "plazo": "2030-12-31", "responsable_id": str(uid), **kw}, mid)
    assert not err, err
    return mejora.obtener(mejora.crear(mid, x, uid))


def _actividad(a, uid, **kw):
    datos = {"codigo": "4.1", "descripcion": "Taller de inducción", "plazo": "2027-12-31", "inicio": "2027-01-01",
             "responsable_id": str(uid), **kw}
    x, err = am.validar(datos, a["marco_id"])
    assert not err, err
    return am.obtener(am.crear(a["id"], x, uid), HOY)


def test_validaciones(app):
    d, r = _gente()
    mid = _marco()["id"]
    _, err = am.validar({"descripcion": "", "plazo": ""}, mid)
    assert "Describa la actividad." in err and "Indique el plazo." in err
    assert "Indique la persona o la unidad responsable." in err
    _, err = am.validar({"descripcion": "x", "plazo": "2027-01-01", "inicio": "2027-02-01", "unidad_responsable": "DTIC",
                         "presupuesto": "-3"}, mid)
    assert "El presupuesto no puede ser negativo." in err
    x, err = am.validar({"descripcion": "x", "plazo": "2027-01-01", "inicio": "2027-02-01", "unidad_responsable": "DTIC"}, mid)
    assert err == ["El inicio no puede ser posterior al plazo."]
    x, err = am.validar({"descripcion": "x", "plazo": "2027-01-01", "unidad_responsable": "DEAGEC", "presupuesto": "2.300,50"}, mid)
    assert not err and x["presupuesto"] == 2300.5 and x["responsable_id"] is None
    ind = mejora.indicadores_del_marco(mid)[0]
    _, err = am.validar({"descripcion": "x", "plazo": "2027-01-01", "unidad_responsable": "DTIC", "indicador_id": str(ind["id"]),
                         "linea_base_valor": "10"}, mid)
    assert any("línea base y la meta" in e for e in err)


def test_plazo_de_la_accion_sigue_a_sus_actividades(app):
    d, r = _gente()
    a = _accion(d["id"])
    _actividad(a, r["id"], codigo="4.1", plazo="2027-12-31")
    t2 = _actividad(a, r["id"], codigo="4.2", plazo="2028-06-30")
    assert mejora.obtener(a["id"])["plazo"] == "2028-06-30"
    am.cancelar(t2, "Se fusionó con la 4.1")
    assert mejora.obtener(a["id"])["plazo"] == "2027-12-31"
    assert not mejora.eliminar(mejora.obtener(a["id"]))          # con actividades no se borra: se cancela
    assert [t["codigo"] for t in am.de_accion(a["id"], HOY)] == ["4.1", "4.2"]


def test_orden_numerico_de_codigos(app):
    d, r = _gente()
    a = _accion(d["id"])
    for c in ("4.10", "4.2", "4.9"):
        _actividad(a, r["id"], codigo=c)
    assert [t["codigo"] for t in am.de_accion(a["id"], HOY)] == ["4.2", "4.9", "4.10"]


def test_avance_y_semaforo(app):
    d, r = _gente()
    a = _accion(d["id"])
    t = _actividad(a, r["id"], inicio="2027-01-01", plazo="2027-12-31")
    assert t["avance"] is None and t["semaforo"] == "al_dia"               # pasó menos de la mitad del plazo
    assert am.obtener(t["id"], date(2027, 8, 1))["semaforo"] == "en_riesgo"  # más de la mitad sin avance
    am.registrar_avance(t, {"texto": "Primer taller", "fecha": "2027-05-30", "porcentaje": 60, "evidencia_id": None}, r["id"])
    t = am.obtener(t["id"], date(2027, 8, 1))
    assert t["avance"] == 60 and t["semaforo"] == "al_dia" and t["estado"] == "en_curso"
    assert mejora.obtener(a["id"])["estado"] == "en_curso"
    assert am.obtener(t["id"], date(2027, 12, 15))["semaforo"] == "en_riesgo"   # vence en menos de 30 días
    assert am.obtener(t["id"], date(2028, 1, 2))["semaforo"] == "vencida"
    assert am.cumplir(t, "2026-11-01") == []
    t = am.obtener(t["id"], date(2028, 1, 2))
    assert t["semaforo"] == "cumplida" and t["avance"] == 100
    t2 = _actividad(a, r["id"], codigo="4.2", plazo="2027-07-31")
    resumen = am.resumen_accion(am.de_accion(a["id"], date(2027, 8, 1)))
    assert resumen["avance"] == 50 and resumen["semaforo"] == "vencida" and resumen["conteo"]["cumplida"] == 1
    assert [x["id"] for x in am.de_responsable(r["id"], date(2027, 8, 1))] == [t2["id"]]


def test_avance_con_indicador(app, monkeypatch):
    d, r = _gente()
    mid = _marco()["id"]
    ind = mejora.indicadores_del_marco(mid)[0]
    a = _accion(d["id"])
    t = _actividad(a, r["id"], indicador_id=str(ind["id"]), linea_base_valor="40", meta_valor="60")
    monkeypatch.setattr(indicadores, "serie", lambda i, anios: {x: {"valor": 45.0 if x == HOY.year else None} for x in anios})
    assert am.obtener(t["id"], HOY)["avance"] == 25                     # 45 está a un cuarto del camino de 40 a 60
    monkeypatch.setattr(indicadores, "serie", lambda i, anios: {x: {"valor": 75.0 if x == HOY.year - 1 else None} for x in anios})
    assert am.obtener(t["id"], HOY)["avance"] == 100                    # se pasó de la meta: no más de 100


def test_aprobacion_y_reprogramacion(app):
    d, r = _gente()
    mid = _marco()["id"]
    a = _accion(d["id"])
    t = _actividad(a, r["id"])
    assert am.aprobar_plan(mid, "", "2026-11-01") == ["Indique la resolución que aprueba el plan."]
    assert am.aprobar_plan(mid, "Res. HCC 12/2026", "2026-11-01") == []
    assert am.aprobado(marco.obtener(mid))
    # Aprobado el plan, el plazo no se edita en el formulario.
    _, err = am.validar({"descripcion": "Taller", "plazo": "2028-03-31", "responsable_id": str(r["id"])}, mid, actual=t)
    assert err == ["El plan ya está aprobado: el plazo cambia solo por reprogramación."]
    x, err = am.validar({"descripcion": "Taller corregido", "plazo": t["plazo"], "responsable_id": str(r["id"])}, mid, actual=t)
    assert not err
    # El responsable pide; la Dirección aprueba o rechaza.
    resp = {"id": r["id"]}
    _, err = am.solicitar_reprogramacion(resp, t, {"plazo_nuevo": "2028-03-31", "causa": " "})
    assert err == ["Explique la causa de la reprogramación."]
    rid, err = am.solicitar_reprogramacion(resp, t, {"plazo_nuevo": "2028-03-31", "causa": "Paro universitario"})
    assert not err and am.obtener(t["id"])["plazo"] == "2027-12-31"
    assert any(n["asunto"] == "Reprogramación por resolver" for n in notificaciones.todas(d["id"]))
    _, err = am.solicitar_reprogramacion(resp, am.obtener(t["id"]), {"plazo_nuevo": "2028-04-30", "causa": "Otra"})
    assert err == ["Ya hay una reprogramación por resolver para esta actividad."]
    assert am.resolver_reprogramacion(am.reprogramacion(rid), False, d["id"], "") == ["Indique el motivo del rechazo."]
    assert am.resolver_reprogramacion(am.reprogramacion(rid), True, d["id"]) == []
    assert am.obtener(t["id"])["plazo"] == "2028-03-31" and mejora.obtener(a["id"])["plazo"] == "2028-03-31"
    assert any(n["asunto"] == "Reprogramación aprobada" for n in notificaciones.todas(r["id"]))
    assert am.resolver_reprogramacion(am.reprogramacion(rid), True, d["id"]) == ["Esa reprogramación ya se resolvió."]
    # Quien gestiona el plan la registra ya aprobada.
    rid2, err = am.solicitar_reprogramacion(d, am.obtener(t["id"]), {"plazo_nuevo": "2028-05-31", "causa": "Ajuste del calendario"})
    assert not err and am.reprogramacion(rid2)["estado"] == "aprobada" and am.obtener(t["id"])["plazo"] == "2028-05-31"
    historial = am.obtener(t["id"])["reprogramaciones"]
    assert [(h["plazo_anterior"], h["plazo_nuevo"], h["estado"]) for h in historial] == [
        ("2028-03-31", "2028-05-31", "aprobada"), ("2027-12-31", "2028-03-31", "aprobada")]
    assert not am.eliminar(am.obtener(t["id"]))                         # con historial no se borra


def test_puede_avanzar(app):
    d, r = _gente()
    a = _accion(d["id"])
    t = _actividad(a, r["id"])
    otro = usuarios.crear("otro@test.cl", "Otro", "Docente", "Clave-otro-12345", debe_cambiar_pass=False)
    assert am.puede_avanzar({"id": r["id"]}, t)
    assert not am.puede_avanzar({"id": otro["id"]}, t)
    assert am.tiene_actividades(r["id"]) and not am.tiene_actividades(otro["id"])
    assert get_db().q("SELECT COUNT(*) n FROM actividad_mejora")[0]["n"] == 1
