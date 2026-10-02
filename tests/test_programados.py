"""Informes programados: qué se envía en cada fecha, a quién y una sola vez."""
from datetime import date

import pytest

from app.academico import gestiones
from app.acreditacion import calidad, programados
from app.comun import config, notificaciones, permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import PASS_ADMIN, PASS_TEMP, login


def _claves(hoy):
    return [(i, o) for i, o, _ in programados.pendientes_de_hoy(hoy)]


@pytest.fixture
def direcciones(app):
    """Ada dirige la Carrera (y, como la cuenta admin de las pruebas, también el Instituto); Emmy, el Instituto."""
    ada = usuarios.por_email("admin@test.cl")
    emmy = usuarios.por_email("inv@test.cl")
    assert permisos.asignar(ada["id"], "direccion_carrera", unidades.id_de("CMAT")) == []
    assert permisos.asignar(emmy["id"], "direccion_instituto", unidades.id_de("IIMAT")) == []
    return {"ada": ada, "emmy": emmy}


def test_calendario(app):
    gestiones.crear_anio(2027)   # I-2027 empieza el 1 de febrero, II-2027 el 1 de agosto (fechas por omisión)
    assert _claves(date(2027, 1, 3)) == [("calidad", "2027-01")]                            # 29 días antes: aún no
    assert _claves(date(2027, 1, 4))[0] == ("preparacion", "I-2027:4 semanas")
    assert ("preparacion", "I-2027:1 semana") in _claves(date(2027, 1, 25))
    assert ("memoria", "2026") in _claves(date(2027, 1, 10)) and ("memoria", "2026") not in _claves(date(2027, 4, 1))
    assert ("carga", "I-2027") in _claves(date(2027, 2, 1)) and ("carga", "I-2027") in _claves(date(2027, 2, 22))
    assert ("carga", "I-2027") not in _claves(date(2027, 2, 23))
    # El 5 de enero ya pasó el envío de 4 semanas antes (4 de enero).
    assert [x[0] for x in programados.proximos(date(2027, 1, 5))] == ["memoria", "preparacion", "carga", "calidad"]


def test_se_envia_una_vez_segun_el_rol(direcciones, buzon):
    hoy = date(2027, 1, 12)
    enviados = programados.revisar(hoy)
    assert {(i, n) for i, _, n in enviados} >= {("preparacion", 1), ("memoria", 2)}
    asuntos = {(m["To"], m["Subject"]) for m in buzon}
    assert ("admin@test.cl", "Preparación de I-2027: 0 de 5 etapas listas") in asuntos
    assert ("inv@test.cl", "Memoria anual 2026 del Instituto") in asuntos
    assert not any(m["To"] == "inv@test.cl" and "Preparación" in m["Subject"] for m in buzon)  # no es su rol
    cuerpo = next(m for m in buzon if "Memoria anual" in m["Subject"]).get_content()
    assert "Productos indexados: 0 (igual que en 2025)" in cuerpo and "/informes/memoria?anio=2026" in cuerpo
    # Queda en la campana (centro de avisos) y no se repite en la siguiente revisión.
    assert notificaciones.no_leidas(direcciones["emmy"]["id"]) >= 1
    n = len(buzon)
    assert programados.revisar(hoy) == [] and len(buzon) == n


def test_respeta_la_preferencia_y_reintenta_sin_destinatarios(app, buzon):
    hoy = date(2027, 1, 12)
    assert all(i != "preparacion" for i, _, _ in programados.revisar(hoy))   # nadie dirige la Carrera: no se registra
    assert not programados.enviado("preparacion", "I-2027:4 semanas")
    emmy = usuarios.por_email("inv@test.cl")
    permisos.asignar(emmy["id"], "direccion_carrera", unidades.id_de("CMAT"))
    notificaciones.fijar_frecuencia(emmy["id"], "nunca")
    assert ("preparacion", "I-2027:4 semanas", 1) in programados.revisar(hoy)   # ahora sí, en la campana…
    assert not any(m["To"] == "inv@test.cl" for m in buzon)              # …pero sin correo, como prefiere
    assert notificaciones.no_leidas(emmy["id"]) == 1


def test_calidad_sin_novedades_no_avisa(direcciones, buzon, monkeypatch):
    monkeypatch.setattr(calidad, "resumen", lambda *a: {"registros": 0, "con_observaciones": 0, "chequeos": 12,
                                                        "por_quien": {}})
    assert ("calidad", "2026-11", 0) in programados.revisar(date(2026, 11, 3))
    assert not any("Calidad de datos" in m["Subject"] for m in buzon)
    assert programados.enviado("calidad", "2026-11")                    # no se reintenta en el mes


def test_el_interruptor_apaga_la_revision_horaria(direcciones, buzon, monkeypatch):
    monkeypatch.setattr(config, "INFORMES_PROGRAMADOS", False)
    programados._ultima_revision = 0.0
    programados.mantenimiento()
    assert get_db().q("SELECT COUNT(*) n FROM informe_programado")[0]["n"] == 0


def test_seccion_en_informes(client, direcciones):
    programados.revisar(date(2027, 1, 12))
    login(client, "admin@test.cl", PASS_ADMIN)
    r = client.get("/informes")
    assert "Informes que recibe automáticamente" in r.text and "Preparación del semestre (I-2027:4 semanas)" in r.text
    client.post("/logout")
    usuarios.cambiar_password(usuarios.por_email("inv@test.cl")["id"], PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    seccion = client.get("/informes").text.split("Informes que recibe automáticamente")[1]
    assert "Memoria anual del Instituto (2026)" in seccion
    assert "Preparación del semestre" not in seccion                     # no es de su rol
