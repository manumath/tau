"""Recursos propios (sin CDN), estilos compilados al día y cabeceras de seguridad (fase 1, paso 1.4)."""
import ast
import re

from app.comun import config
from app.comun.cabeceras import CSP
from tests.conftest import PASS_ADMIN, login

RAIZ = config.RAIZ
CSS = "".join((RAIZ / "static" / f).read_text() for f in ("css/tailwind.css", "vendor/franken-ui/core.min.css",
                                                         "vendor/katex/katex.min.css"))
# Clases propias (con estilos en línea o usadas solo como marca) y de Franken UI sin regla propia.
SIN_REGLA = {"hoja", "no-imprimir", "citas", "apagado", "nomath", "htmx-indicator", "monster-navbar",
             "fila-repetible", "uk-table-small", "grafico", "cifra", "membrete", "membrete-logo",
             "fh-toast", "fh-toast-", "fh-toast-success"}   # los avisos emergentes traen su propio CSS (fasthtml.toaster)


def test_paginas_sin_recursos_externos(client):
    for url in ("/login", "/publico"):
        html = client.get(url).text
        externos = re.findall(r'<script[^>]+src="(https?://[^"]+)"', html) + re.findall(
            r'<link[^>]+rel="(?:stylesheet|preload|modulepreload)"[^>]+href="(https?://[^"]+)"', html)
        assert externos == [], externos
        for ruta in re.findall(r'(?:src|href)="(/static/[^"?]+)', html):
            assert client.get(ruta).status_code == 200, ruta


def test_cabeceras_de_seguridad(client):
    for url in ("/login", "/static/css/tailwind.css"):
        r = client.get(url)
        assert r.headers["content-security-policy"] == CSP
        assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in CSP and "frame-ancestors 'none'" in CSP


def test_estaticos_acotados(client):
    r = client.get("/static/vendor/htmx/htmx.min.js?v=1")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    for url in ("/static/../main.py", "/static/%2e%2e/main.py", "/main.py", "/informe.xlsx"):
        assert client.get(url).status_code == 404, url


def test_admin_usa_los_mismos_recursos(client):
    login(client, "admin@test.cl", PASS_ADMIN)
    assert "cdn." not in client.get("/admin/usuarios").text


def _clases_en_codigo():
    """Clases escritas literalmente en argumentos cls=… del código de la app."""
    clases = {}
    for f in (RAIZ / "app").rglob("*.py"):
        for nodo in ast.walk(ast.parse(f.read_text())):
            if isinstance(nodo, ast.keyword) and nodo.arg == "cls":
                # Las claves y comparaciones (p["interno"], x == "a") no son clases.
                otras = {id(n.slice) for n in ast.walk(nodo.value) if isinstance(n, ast.Subscript)}
                otras |= {id(c) for n in ast.walk(nodo.value) if isinstance(n, ast.Compare)
                          for c in [n.left, *n.comparators]}
                for c in ast.walk(nodo.value):
                    if isinstance(c, ast.Constant) and isinstance(c.value, str) and id(c) not in otras:
                        for t in c.value.split():
                            clases.setdefault(t, f"{f.relative_to(RAIZ)}:{c.lineno}")
    return clases


def _definida(clase: str) -> bool:
    selector = "." + re.sub(r"([:\[\]./%#()!,'&@*+])", r"\\\1", clase)
    return re.search(re.escape(selector) + r"(?![\w-])", CSS) is not None


def test_estilos_compilados_al_dia():
    """Si falla: se usó una clase de Tailwind nueva. Ejecute scripts/estilos.sh y confirme el CSS."""
    faltan = {c: donde for c, donde in _clases_en_codigo().items()
              if c not in SIN_REGLA and not c.startswith("uk-") and not _definida(c)}
    assert not faltan, f"Clases sin CSS (ejecute scripts/estilos.sh): {faltan}"
