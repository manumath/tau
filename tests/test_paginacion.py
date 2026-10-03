"""Listas largas: «Cargar más» de 50 en 50 en productos y actividades (valoración de usabilidad, paso 1)."""
import re

from app.comun.componentes.registros import POR_PAGINA
from app.comun.db import get_db
from app.investigacion import actividades, productos
from tests.conftest import HX
from tests.test_productos import _form, inv  # noqa: F401


def _muchos_productos(uid, n, titulo="Artículo"):
    for i in range(n):
        d, errores = productos.preparar({k: v for k, v in _form(uid, titulo=f"{titulo} {i:03d}").items()
                                         if k != "autor"}, [f"i:{uid}"], [])
        assert not errores
        productos.guardar(d, [f"i:{uid}"], uid)


def _n_items(html, prefijo):
    return len(re.findall(rf'id="{prefijo}-\d+"', html))


def test_productos_por_paginas(inv):
    _muchos_productos(inv.uid, POR_PAGINA + 12)
    pagina = inv.get("/productos").text
    assert _n_items(pagina, "producto") == POR_PAGINA
    assert "62 productos" in pagina and "Cargar 12 más" in pagina and "quedan 12" in pagina
    resto = inv.get("/productos/mas", params={"desde": POR_PAGINA}, headers=HX).text
    assert _n_items(resto, "producto") == 12 and "Cargar" not in resto
    # Con filtros: la página siguiente respeta la búsqueda.
    filtrada = inv.get("/productos/lista", params={"q": "Artículo 00"}, headers=HX).text
    assert _n_items(filtrada, "producto") == 10 and "Cargar" not in filtrada
    assert inv.get("/productos/mas", params={"desde": 0, "q": "Artículo 06"}, headers=HX).text.count('id="producto-') == 2


def test_inicio_y_cv_cuentan_todo(inv):
    _muchos_productos(inv.uid, POR_PAGINA + 5)
    assert len(productos.buscar(inv.uid)) == POR_PAGINA + 5
    assert "55" in inv.get("/").text  # «en total»


def test_actividades_por_paginas(inv):
    tipo = get_db().q("SELECT id FROM tipo_actividad WHERE nombre = 'Seminario'")[0]["id"]
    for i in range(POR_PAGINA + 3):
        actividades.guardar(dict(tipo_id=tipo, titulo=f"Seminario {i}", institucion=None, lugar=None, pais=None,
                                 fecha_inicio=f"2026-01-{1 + i % 28:02d}", fecha_fin=None, modalidad="presencial",
                                 ambito="local", url=None, descripcion=None), [(f"i:{inv.uid}", "expositor")], inv.uid)
    pagina = inv.get("/actividades").text
    assert _n_items(pagina, "actividad") == POR_PAGINA and "Cargar 3 más" in pagina
    assert _n_items(inv.get("/actividades/mas", params={"desde": POR_PAGINA}, headers=HX).text, "actividad") == 3
