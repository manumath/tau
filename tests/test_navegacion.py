"""Menú lateral, barra superior y pestañas del teléfono (PLAN.md §53)."""
import re

from app import navegacion
from app.comun import permisos, unidades, usuarios
from tests.conftest import PASS_TEMP, login
from tests.test_portal_estudiante import estudiantes_cargados, sofia  # noqa: F401


def _auth(email):
    u = usuarios.con_perfil(usuarios.por_email(email)["id"])
    u["roles"] = permisos.roles_vigentes(u["id"])
    return u


def _grupos(auth):
    return {t: [i["clave"] for i in items] for t, items in navegacion.menu(auth)}


def test_cada_rol_ve_sus_grupos(app):
    emmy = _grupos(_auth("inv@test.cl"))
    assert emmy[None] == ["inicio"] and emmy["Investigación"] == ["actividades", "productos", "proyectos", "investigadores"]
    assert "Administración" not in emmy and "Estudiantes" not in emmy        # ni cuentas ni seguimiento estudiantil
    admin = _grupos(_auth("admin@test.cl"))   # Administración del sistema y Dirección del Instituto
    assert admin["Administración"] == ["usuarios", "auditoria", "revistas", "lineas", "catalogos"]
    assert "propuestas" in admin["Investigación"] and "calidad" in admin["Acreditación"]
    assert "actividades" not in admin["Investigación"]                        # no es investigadora
    permisos.asignar(usuarios.por_email("inv@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    assert "cohortes" in _grupos(_auth("inv@test.cl"))["Estudiantes"]         # ve el seguimiento estudiantil
    # «Gestiones» solo para quien las prepara (PLAN.md §54): para los demás era una lista de fechas.
    assert "gestiones" not in emmy.get("Docencia", []) and "gestiones" not in admin["Docencia"]
    assert "gestiones" in _grupos(_auth("inv@test.cl"))["Docencia"]


def test_pestanas_del_telefono(app):
    assert [i["clave"] for i in navegacion.movil(_auth("inv@test.cl"))] == ["inicio", "productos", "proyectos",
                                                                            "investigadores"]
    assert all(i["insignia"] is None for i in navegacion.movil(_auth("inv@test.cl")))  # sus ids van en el lateral


def test_pagina_con_menu_unico(client):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/productos").text
    for id_ in ("menu-lateral", "campana-avisos", "badge-pendientes", "busqueda-global"):
        assert len(re.findall(rf'id="{id_}"', r)) == 1, id_                  # una sola vez: sin ids repetidos
    assert 'aria-label="Menú principal"' in r and 'aria-label="Secciones principales"' in r
    assert 'data-accion="plegar-lateral"' in r and 'data-accion="abrir-menu"' in r
    assert "<span>Más</span>" in r                                              # la barra del teléfono termina en «Más»
    assert "js/disposicion-inicial.js" in r                                     # el plegado, antes de pintar
    assert 'data-grupo="investigacion"' in r and 'data-accion="plegar-grupo"' in r  # grupos plegables (§54)
    assert "img/marca/isotipo.svg" in r and "img/marca/isotipo-blanco.svg" in r  # marca de la Carrera (§55)
    r = client.get("/perfil").text                                              # cada «Falta» lleva a su sección
    assert 'href="#seccion-identificadores"' in r and 'id="seccion-identificadores"' in r
    assert re.search(r'class="[^"]*\blateral\b[^"]*no-imprimir', r)              # el menú no sale en los PDF


def test_cuenta_de_estudiante(sofia):  # noqa: F811
    r = sofia.get("/estudiante").text
    assert re.findall(r'href="([^"]+)"[^>]*data-nav', r) == ["/estudiante", "/avisos", "/estudiante", "/avisos"]
    assert 'id="busqueda-global"' not in r and "<span>Más</span>" not in r   # sin búsqueda ni «Más»: solo dos secciones
