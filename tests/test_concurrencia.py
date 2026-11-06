"""Peticiones simultáneas: cada hilo con su conexión y el mantenimiento periódico sin duplicarse."""
import threading
import time

import main
from app.comun import db as dbmod
from app.comun.db import get_db, init_db, transaccion


def test_cada_hilo_tiene_su_conexion(tmp_path):
    init_db(tmp_path / "c.db")
    otra = []
    hilo = threading.Thread(target=lambda: otra.append(get_db()))
    hilo.start()
    hilo.join()
    assert otra[0] is not get_db()
    assert get_db() is get_db()  # el mismo hilo reutiliza la suya
    assert get_db().q("PRAGMA busy_timeout")[0]["timeout"] == dbmod.ESPERA_MS
    assert get_db().q("PRAGMA foreign_keys")[0]["foreign_keys"] == 1


def test_revertir_una_transaccion_no_borra_lo_escrito_por_otro_hilo(tmp_path):
    """Con una conexión compartida, la fila de B quedaba dentro de la transacción de A y se perdía."""
    init_db(tmp_path / "c.db")
    get_db().execute("CREATE TABLE t (x TEXT)")
    a_dentro, b_listo = threading.Event(), threading.Event()

    def a():
        try:
            with transaccion():
                get_db().execute("INSERT INTO t VALUES ('A')")
                a_dentro.set()
                b_listo.wait(5)
                raise ValueError
        except ValueError:
            pass

    def b():
        a_dentro.wait(5)
        get_db().execute("INSERT INTO t VALUES ('B')")  # espera (busy_timeout) a que A termine
        b_listo.set()

    hilos = [threading.Thread(target=a), threading.Thread(target=b)]
    for h in hilos:
        h.start()
    time.sleep(0.2)
    b_listo.set()  # B está esperando el turno de escritura: A puede revertir
    for h in hilos:
        h.join()
    assert [f["x"] for f in get_db().q("SELECT x FROM t")] == ["B"]


def test_init_db_nuevo_reemplaza_la_conexion_de_los_hilos(tmp_path):
    init_db(tmp_path / "uno.db")
    primera = get_db()
    init_db(tmp_path / "dos.db")
    assert get_db() is not primera
    assert get_db().q("PRAGMA database_list")[0]["file"].endswith("dos.db")


def test_el_mantenimiento_no_se_ejecuta_dos_veces_a_la_vez(app, monkeypatch):
    llamadas, soltar = [], threading.Event()

    def lento():
        llamadas.append(1)
        soltar.wait(5)

    monkeypatch.setattr(main.institucionales, "mantenimiento", lento)
    monkeypatch.setattr(main.programados, "mantenimiento", lambda: None)
    monkeypatch.setattr(main.seguimiento_egresados, "mantenimiento", lambda: None)
    monkeypatch.setattr(main, "_ultimo_mantenimiento", float("-inf"))
    main._mantenimiento(None)
    monkeypatch.setattr(main, "_ultimo_mantenimiento", float("-inf"))  # aunque ya «tocara» otra vez
    main._mantenimiento(None)  # sigue corriendo el primero: no lanza otro
    soltar.set()
    for _ in range(50):
        if not main._candado_mantenimiento.locked():
            break
        time.sleep(0.02)
    assert llamadas == [1]
    assert not main._candado_mantenimiento.locked()


def test_un_error_del_mantenimiento_libera_el_candado(app, monkeypatch):
    def falla():
        raise RuntimeError("prueba")

    monkeypatch.setattr(main.institucionales, "mantenimiento", falla)
    monkeypatch.setattr(main, "_ultimo_mantenimiento", float("-inf"))
    main._mantenimiento(None)
    for _ in range(50):
        if not main._candado_mantenimiento.locked():
            break
        time.sleep(0.02)
    assert not main._candado_mantenimiento.locked()
