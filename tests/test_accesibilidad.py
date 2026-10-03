"""Accesibilidad del marco común (PLAN.md §48, paso 2): lo que el navegador no puede comprobar sin el HTML."""
import re

from app.comun.componentes.layout import mensaje_error, modal
from fasthtml.common import to_xml
from tests.conftest import HX, PASS_TEMP, login
from app.comun import usuarios


def test_modal_nombrado_por_su_titulo():
    html = to_xml(modal("Nueva actividad", "contenido"))
    assert 'role="dialog"' in html and 'aria-modal="true"' in html
    assert 'aria-labelledby="modal-titulo"' in html and 'id="modal-titulo"' in html


def test_resumen_de_errores_enfocable_y_anunciado():
    html = to_xml(mensaje_error("Falta el título."))
    assert 'role="alert"' in html and 'tabindex="-1"' in html and "data-resumen-errores" in html
    assert mensaje_error() == ""


def test_saltar_al_contenido(client, app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    assert 'href="#contenido"' not in client.get("/login").text   # sin navegación, no hace falta
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/productos").text
    main = re.search(r"<main[^>]*>", r).group(0)
    assert r.index("Saltar al contenido") < r.index("<nav") and 'id="contenido"' in main and 'tabindex="-1"' in main
    assert client.get("/productos/nuevo", headers=HX).status_code == 200
