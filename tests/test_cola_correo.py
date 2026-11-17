"""Cola persistente de correo (PLAN §56, etapa 4): transacciones, reintentos, rechazos y reservas."""
import smtplib

import pytest

from app.comun import config, correo
from app.comun.db import al_confirmar, get_db, init_db, transaccion


class _Inmediato:
    """Reemplaza el pool de hilos del correo: ejecuta en el acto (pruebas deterministas)."""

    def submit(self, fn, *args):
        fn(*args)


@pytest.fixture
def smtp(tmp_path, monkeypatch):
    """Modo smtp con un servidor simulado: `smtp.enviados` y `smtp.fallo` (excepción a lanzar o None)."""
    init_db(tmp_path / "c.db")
    monkeypatch.setattr(config, "CORREO_MODO", "smtp")
    monkeypatch.setattr(correo, "_hilos", _Inmediato())

    class Servidor:
        enviados, fallo = [], None
    srv = Servidor()

    def falso(m):
        if srv.fallo:
            raise srv.fallo
        srv.enviados.append(m)
    monkeypatch.setattr(correo, "_smtp", falso)
    return srv


def _cola():
    return get_db().q("SELECT * FROM correo_pendiente")


def _vencer_esperas():
    get_db().execute("UPDATE correo_pendiente SET proximo_intento = datetime('now', '-1 second')")


def test_envia_y_no_deja_rastro(smtp):
    correo.enviar("ana@test.cl", "Hola", "Texto")
    assert [m["To"] for m in smtp.enviados] == ["ana@test.cl"]
    assert _cola() == []  # sin historial de mensajes enviados (llevan enlaces personales)


def test_si_la_transaccion_se_revierte_el_correo_no_sale(smtp):
    with pytest.raises(ValueError):
        with transaccion():
            correo.enviar("ana@test.cl", "Hola", "Texto")
            raise ValueError
    assert smtp.enviados == [] and _cola() == []


def test_dentro_de_una_transaccion_sale_al_confirmarse(smtp):
    with transaccion():
        correo.enviar("ana@test.cl", "Hola", "Texto")
        with transaccion():  # anidada: no adelanta el envío
            pass
        assert smtp.enviados == []
    assert len(smtp.enviados) == 1 and _cola() == []


def test_un_fallo_pasajero_se_reintenta_con_el_mismo_message_id(smtp):
    smtp.fallo = smtplib.SMTPServerDisconnected("se cortó")
    correo.enviar("ana@test.cl", "Hola", "Texto")
    [fila] = _cola()
    assert fila["intentos"] == 1 and "se cortó" in fila["ultimo_error"]
    assert correo.reintentar() == 0  # aún no le toca (espera de 1 minuto)
    smtp.fallo = None
    _vencer_esperas()
    assert correo.reintentar() == 1
    assert _cola() == [] and len(smtp.enviados) == 1
    original = correo.email.message_from_bytes(fila["mensaje"], policy=correo.email.policy.default)
    assert smtp.enviados[0]["Message-ID"] == original["Message-ID"]  # el receptor puede descartar duplicados


def test_un_rechazo_definitivo_no_se_reintenta(smtp):
    smtp.fallo = smtplib.SMTPRecipientsRefused({"nadie@test.cl": (550, b"no existe")})
    correo.enviar("nadie@test.cl", "Hola", "Texto")
    assert _cola() == []


def test_se_descarta_tras_agotar_los_intentos(smtp):
    smtp.fallo = OSError("sin red")
    correo.enviar("ana@test.cl", "Hola", "Texto")
    for _ in range(correo.MAX_INTENTOS - 1):
        assert len(_cola()) == 1
        _vencer_esperas()
        correo.reintentar()
    assert _cola() == [] and smtp.enviados == []


def test_dos_hilos_no_envian_el_mismo_correo(smtp, monkeypatch):
    monkeypatch.setattr(correo, "_hilos", type("SinEnviar", (), {"submit": lambda *a: None})())
    correo.enviar("ana@test.cl", "Hola", "Texto")
    [fila] = _cola()
    assert correo.entregar(fila["id"]) is True
    assert correo.entregar(fila["id"]) is False  # ya salió y se borró
    assert len(smtp.enviados) == 1


def test_la_reserva_impide_un_segundo_envio_mientras_el_primero_sigue(smtp, monkeypatch):
    """Si el proceso muere a medio enviar, la fila queda reservada y se reintenta después, no al instante."""
    monkeypatch.setattr(correo, "_hilos", type("SinEnviar", (), {"submit": lambda *a: None})())
    correo.enviar("ana@test.cl", "Hola", "Texto")
    [fila] = _cola()
    get_db().execute(f"UPDATE correo_pendiente SET intentos = 1, proximo_intento = datetime('now', '+1 minute') "
                     f"WHERE id = {fila['id']}")  # como lo deja una reserva en curso
    assert correo.reintentar() == 0 and smtp.enviados == []


def test_sin_cola_se_envia_directo(smtp, monkeypatch):
    """Si la base no responde (p. ej., el aviso de un error del servidor), el correo igual se intenta."""
    def roto(m):
        raise RuntimeError("la base no responde")
    monkeypatch.setattr(correo, "_encolar", roto)
    directos = []
    monkeypatch.setattr(correo, "_directo", directos.append)
    correo.enviar("admin@test.cl", "Error", "Texto")
    assert [m["To"] for m in directos] == ["admin@test.cl"]


def test_otros_modos_no_usan_la_cola(tmp_path):
    init_db(tmp_path / "c.db")
    correo.enviar("ana@test.cl", "Hola", "Texto")  # las pruebas usan el modo memoria
    assert correo.ENVIADOS[-1]["To"] == "ana@test.cl" and _cola() == []
    assert correo.reintentar() == 0


def test_al_confirmar_fuera_de_una_transaccion_es_inmediato(tmp_path):
    init_db(tmp_path / "c.db")
    hecho = []
    al_confirmar(lambda: hecho.append(1))
    assert hecho == [1]
