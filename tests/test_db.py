from fastmigrate.core import get_db_version

from app import config
from app.db import get_db, init_db


def test_migraciones_aplicadas(app, tmp_path):
    ultima = max(int(p.name[:4]) for p in config.MIGRACIONES.glob("[0-9][0-9][0-9][0-9]-*"))
    assert get_db_version(tmp_path / "test.db") == ultima


def test_migraciones_idempotentes(tmp_path):
    ruta = tmp_path / "doble.db"
    init_db(ruta)
    init_db(ruta)  # la segunda vez no reaplica nada
    assert get_db().q("SELECT COUNT(*) AS n FROM tipo_producto")[0]["n"] == 9


def test_catalogo_de_productos(app):
    tipos = {t["nombre"]: t["admite_revision"] for t in get_db().q("SELECT * FROM tipo_producto")}
    assert tipos["Artículo en revista"] == 1
    assert tipos["Reporte de investigación"] == 0
