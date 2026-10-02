"""Política de seguridad de contenido estricta: ni scripts en línea ni código en atributos.

La CSP solo admite scripts propios ('self'), sin 'unsafe-inline' ni 'unsafe-eval'. Si una pantalla
vuelve a usar onclick=…, hx-on… o un <script> en línea, el navegador lo bloquearía en silencio: estas
pruebas lo detectan antes (y las de tests/navegador fallan con cualquier violación en la consola).
"""
import re
from pathlib import Path

from monsterui.core import ThemeFont, ThemeRadii, ThemeShadows, headers_theme

from app.comun import config, permisos, unidades, usuarios
from app.comun.cabeceras import CSP
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login

SCRIPT_EN_LINEA = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>\s*\S", re.S)
MANEJADOR = re.compile(r"\s(on[a-z]+|hx-on[:a-z-]*)=", re.I)
PAGINAS = ["/login", "/", "/proyectos", "/productos", "/actividades", "/informes", "/informes/memoria",
           "/informes/acreditacion", "/informes/calidad", "/informes/guia-antecedentes", "/docencia/oferta",
           "/docencia/carga", "/docencia/planes", "/docencia/gestiones", "/docencia/preparacion", "/admin/usuarios",
           "/admin/auditoria", "/admin/propuestas", "/admin/revistas", "/admin/lineas", "/avisos",
           "/personas/externos", "/personas/externos/duplicados", "/estudiantes", "/investigadores"]
MODALES = ["/actividades/nueva", "/productos/nuevo", "/admin/usuarios/nuevo",
           "/admin/revistas/nueva", "/estudiantes/nuevo"]


def test_politica_estricta_para_scripts():
    directivas = dict(d.split(" ", 1) for d in CSP.split("; "))
    assert directivas["script-src"] == "'self'"
    assert "unsafe" not in directivas["script-src"]


def _sin_codigo_en_linea(html, donde):
    assert not SCRIPT_EN_LINEA.search(html), f"script en línea en {donde}"
    assert not MANEJADOR.search(html), f"manejador en el HTML en {donde}: {MANEJADOR.search(html).group(0)}"


def test_paginas_y_modales_sin_codigo_en_linea(client, app):
    ada = usuarios.por_email("admin@test.cl")
    permisos.asignar(ada["id"], "direccion_carrera", unidades.id_de("CMAT"))
    _sin_codigo_en_linea(client.get("/login").text, "/login")
    login(client, "admin@test.cl", PASS_ADMIN)
    for ruta in PAGINAS + MODALES:
        r = client.get(ruta, headers=HX if ruta in MODALES else {})
        assert r.status_code < 400, (ruta, r.status_code)
        _sin_codigo_en_linea(r.text, ruta)
    client.post("/logout")
    usuarios.cambiar_password(usuarios.por_email("inv@test.cl")["id"], PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    for ruta in ("/", "/productos", "/actividades", "/proyectos", "/perfil", "/informes/cv"):
        _sin_codigo_en_linea(client.get(ruta).text, ruta)


def test_el_codigo_no_vuelve_a_usar_manejadores():
    """Barrera barata en el código: nada de onclick=…, onchange=… ni hx_on… al armar el HTML."""
    patron = re.compile(r"\b(on(click|change|submit|input|keydown|keyup|load|blur|focus)|hx_on\w*)\s*=")
    hallados = [f"{p}:{n}" for p in (config.RAIZ / "app").rglob("*.py")
                for n, linea in enumerate(p.read_text().splitlines(), 1) if patron.search(linea)]
    assert hallados == []


def test_tema_inicial_igual_al_de_monsterui():
    """static/js/tema-inicial.js reemplaza al script en línea de headers_theme: si MonsterUI lo cambia
    al actualizarse, hay que regenerar el archivo (docs/mantenimiento.md)."""
    esperado = "".join(str(c) for c in headers_theme("blue", mode="auto", radii=ThemeRadii.sm,
                                                     shadows=ThemeShadows.sm, font=ThemeFont.sm).children).strip()
    archivo = Path(config.RAIZ / "static/js/tema-inicial.js").read_text()
    assert esperado in archivo
