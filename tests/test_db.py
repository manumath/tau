from datetime import date, timedelta

import pytest
from fastmigrate.core import get_db_version

from app.comun import config
from app.comun.db import AHORA, HOY, get_db, init_db, marca_tiempo, transaccion, vigente_hasta


def test_migraciones_aplicadas(app, tmp_path):
    ultima = max(int(p.name[:4]) for p in config.MIGRACIONES.glob("[0-9][0-9][0-9][0-9]-*"))
    assert get_db_version(tmp_path / "test.db") == ultima


def test_migraciones_idempotentes(tmp_path):
    ruta = tmp_path / "doble.db"
    init_db(ruta)
    init_db(ruta)  # la segunda vez no reaplica nada
    assert get_db().q("SELECT COUNT(*) AS n FROM tipo_producto")[0]["n"] == 11  # 9 iniciales + patente y traducción


def test_catalogo_de_productos(app):
    tipos = {t["nombre"]: t["admite_revision"] for t in get_db().q("SELECT * FROM tipo_producto")}
    assert tipos["Artículo en revista"] == 1
    assert tipos["Reporte de investigación"] == 0


# --- Dialecto SQL (app/comun/db.py) --------------------------------------------------------------

def test_marca_tiempo_con_el_formato_de_sqlite(app):
    sql = get_db().q(f"SELECT {AHORA} AS t")[0]["t"]
    py = marca_tiempo()
    assert len(py) == len(sql) == 19 and py[:15] == sql[:15]  # mismo formato y casi el mismo instante
    assert marca_tiempo(-timedelta(days=1)) < py < marca_tiempo(timedelta(minutes=1))


def test_hoy_es_la_fecha_local(app):
    assert get_db().q(f"SELECT {HOY} AS d")[0]["d"] == date.today().isoformat()  # main.py fija TZ


def test_vigente_hasta(app):
    ayer, hoy = (date.today() - timedelta(days=1)).isoformat(), date.today().isoformat()
    fila = get_db().q(f"""SELECT {vigente_hasta(':nulo')} AS a, {vigente_hasta(':hoy')} AS b,
                                 {vigente_hasta(':ayer')} AS c""", {"nulo": None, "hoy": hoy, "ayer": ayer})[0]
    assert (fila["a"], fila["b"], fila["c"]) == (1, 1, 0)


def test_transaccion_deshace_todo_ante_un_error(app):
    antes = get_db().q("SELECT COUNT(*) n FROM auditoria")[0]["n"]
    with pytest.raises(RuntimeError):
        with transaccion():
            get_db().t.auditoria.insert(accion="prueba")
            with transaccion():  # anidada
                get_db().t.auditoria.insert(accion="prueba")
            raise RuntimeError("falla a medio camino")
    assert get_db().q("SELECT COUNT(*) n FROM auditoria")[0]["n"] == antes
