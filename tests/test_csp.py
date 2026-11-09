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
           "/informes/investigacion", "/informes/calidad", "/calidad/marco", "/calidad/indicadores", "/calidad/evidencias", "/calidad/autoevaluaciones", "/calidad/mejora", "/calidad/ficha", "/calidad/capacitacion", "/calidad/convenios", "/calidad/impacto", "/docencia/empleadores", "/calidad/ficha/plantilla", "/publico/indicadores", "/docencia/oferta",
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
    esperado = "".join(str(c) for c in headers_theme("cmat", mode="auto", radii=ThemeRadii.sm,
                                                     shadows=ThemeShadows.sm, font=ThemeFont.sm).children).strip()
    archivo = Path(config.RAIZ / "static/js/tema-inicial.js").read_text()
    assert esperado in archivo


def test_envio_demasiado_grande_responde_413(client):
    """LimiteCuerpo (PLAN §62, etapa 9): por Content-Length y también contando lo recibido si no lo declara."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    from app.comun.cabeceras import LimiteCuerpo
    r = client.post("/login", content=b"x", headers={"content-length": str(config.MAX_CUERPO + 1)})
    assert r.status_code == 413 and "máximo" in r.text
    assert client.post("/login", data={"email": "a@b.c", "password": "x"}).status_code != 413

    async def app_que_lee(scope, receive, send):
        while (await receive()).get("more_body"):
            pass
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    partes = [{"type": "http.request", "body": b"x" * 600, "more_body": True} for _ in range(2)]
    enviados = []

    async def recibir():
        return partes.pop(0)

    async def enviar(m):
        enviados.append(m)

    # En un hilo aparte: con las pruebas en navegador, Playwright ya tiene un bucle de eventos en este.
    with ThreadPoolExecutor(1) as hilo:
        hilo.submit(asyncio.run, LimiteCuerpo(app_que_lee, maximo=1000)({"type": "http", "headers": []}, recibir,
                                                                       enviar)).result()
    assert enviados[0]["status"] == 413
