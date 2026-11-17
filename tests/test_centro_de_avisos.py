"""Centro de avisos: campana, página «Avisos», preferencia y resumen semanal (PLAN.md §33)."""
from datetime import datetime, timedelta

import pytest

from app.comun import notificaciones, usuarios
from app.comun.db import get_db
from app.investigacion import productos, proyectos
from tests.conftest import HX, PASS_TEMP, login


@pytest.fixture
def proyecto(app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP, debe_cambiar_pass=False)["id"]
    pid = proyectos.crear(dict(nombre="Álgebra", estado="vigente"), emmy, emmy)
    proyectos.agregar_participante(pid, f"i:{alan}", "co_investigador", True)
    tipo = get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Artículo en revista'")[0]["id"]
    d, _ = productos.preparar(dict(tipo_id=str(tipo), titulo="Invariantes", anio="2026",
                                   estado_publicacion="publicado", revision="arbitrado"), [f"i:{alan}"], [])
    return {"pid": pid, "emmy": emmy, "alan": alan, "prod": productos.guardar(d, [f"i:{alan}"], alan)}


def test_el_aviso_queda_en_el_sistema_aunque_no_se_envie_correo(proyecto, buzon):
    emmy, alan, pid, prod = proyecto["emmy"], proyecto["alan"], proyecto["pid"], proyecto["prod"]
    notificaciones.fijar_frecuencia(emmy, "nunca")
    proyectos.sincronizar("producto", prod, [pid], {"id": alan})
    assert buzon == []
    assert notificaciones.no_leidas(emmy) == 1 and notificaciones.no_leidas(alan) == 0  # no a quien lo hizo
    n = notificaciones.recientes(emmy)[0]
    assert n["asunto"] == "Nueva propuesta en «Álgebra»" and n["url"] == f"/proyectos/{pid}?tab=pendientes"
    assert notificaciones.abrir(n["id"], alan) is None  # no es suyo
    assert notificaciones.abrir(n["id"], emmy)["url"] == n["url"] and notificaciones.no_leidas(emmy) == 0


def test_resumen_semanal(proyecto, buzon):
    emmy, alan, pid, prod = proyecto["emmy"], proyecto["alan"], proyecto["pid"], proyecto["prod"]
    notificaciones.fijar_frecuencia(emmy, "semanal")
    proyectos.sincronizar("producto", prod, [pid], {"id": alan})
    assert buzon == []  # no se envía al momento
    assert notificaciones.resumen_semanal() == 1
    assert buzon[-1]["To"] == "inv@test.cl" and "Resumen semanal de avisos (1)" in buzon[-1]["Subject"]
    assert "Nueva propuesta en «Álgebra»" in buzon[-1].get_content()
    assert notificaciones.resumen_semanal() == 0  # ya se envió esta semana
    proyectos.rechazar("producto", prod, pid, emmy, "Falta citar")
    proyectos.sincronizar("producto", prod, [pid], {"id": alan})
    assert notificaciones.resumen_semanal(datetime.now() + timedelta(days=3)) == 0  # aún no pasa la semana
    assert notificaciones.resumen_semanal(datetime.now() + timedelta(days=8)) == 1
    assert "Resumen semanal de avisos (1)" in buzon[-1]["Subject"]  # solo lo nuevo


def test_campana_y_pagina(client, proyecto):
    emmy, alan, pid, prod = proyecto["emmy"], proyecto["alan"], proyecto["pid"], proyecto["prod"]
    proyectos.sincronizar("producto", prod, [pid], {"id": alan})
    login(client, "inv@test.cl", PASS_TEMP)
    assert 'id="campana-avisos"' in client.get("/").text  # se carga aparte
    r = client.get("/avisos/campana", headers=HX)
    assert "Avisos (1 sin leer)" in r.text and "Nueva propuesta en «Álgebra»" in r.text
    nid = notificaciones.recientes(emmy)[0]["id"]
    r = client.get(f"/avisos/{nid}", follow_redirects=False)
    assert r.headers["location"] == f"/proyectos/{pid}?tab=pendientes" and notificaciones.no_leidas(emmy) == 0
    r = client.get("/avisos")
    assert "Nueva propuesta en «Álgebra»" in r.text and "Cómo recibir los avisos" in r.text
    client.post("/avisos/preferencia", data={"frecuencia": "semanal"})
    assert usuarios.por_id(emmy)["frecuencia_avisos"] == "semanal"
    assert client.post("/avisos/preferencia", data={"frecuencia": "diaria"}).status_code == 400
    proyectos.rechazar("producto", prod, pid, emmy, "x")
    proyectos.sincronizar("producto", prod, [pid], {"id": alan})
    r = client.post("/avisos/leidas", headers={**HX, "HX-Target": "campana-avisos"})
    assert "No tiene avisos" not in r.text and notificaciones.no_leidas(emmy) == 0
    otra = client.get(f"/avisos/{nid + 1000}")
    assert otra.status_code == 404
