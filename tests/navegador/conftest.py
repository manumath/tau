"""Montaje de las pruebas en navegador (Playwright).

Cada sesión levanta el portal con uvicorn en un puerto libre, con una base temporal preparada
por `preparar.py`, en un proceso aparte: no toca data/portal.db ni el servidor de desarrollo.
Usa Google Chrome instalado (canal «chrome»); con PLAYWRIGHT_CANAL="" usa el Chromium de
Playwright (`playwright install chromium`).

Cada prueba falla si la página registra errores de JavaScript, recursos que no cargan o
violaciones de la política de seguridad de contenido (CSP).
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from app.comun import config
from tests.navegador.preparar import ADMIN, CLAVE, INVESTIGADORA


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def servidor(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("portal")
    entorno = {**os.environ, "PORTAL_DB": str(carpeta / "portal.db"), "PORTAL_CORREO_MODO": "memoria"}
    subprocess.run([sys.executable, "-m", "tests.navegador.preparar", entorno["PORTAL_DB"]], env=entorno,
                   cwd=config.RAIZ, check=True)
    puerto = _puerto_libre()
    url = f"http://127.0.0.1:{puerto}"
    registro = open(carpeta / "servidor.log", "w")
    proceso = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
                                "--port", str(puerto)], env=entorno, cwd=config.RAIZ, stdout=registro,
                               stderr=subprocess.STDOUT)
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/login", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    else:
        proceso.terminate()
        pytest.fail(f"El portal no arrancó: ver {carpeta / 'servidor.log'}")
    yield url
    proceso.terminate()
    proceso.wait(timeout=10)
    registro.close()


@pytest.fixture(scope="session")
def base_url(servidor):
    """pytest-playwright resuelve page.goto("/ruta") contra esta URL."""
    return servidor


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    canal = os.environ.get("PLAYWRIGHT_CANAL", "chrome")
    return {**browser_type_launch_args, **({"channel": canal} if canal else {})}


@pytest.fixture(autouse=True)
def sin_errores_en_la_pagina(page):
    """Junta errores de consola y de JavaScript; la prueba falla si hubo alguno."""
    errores = []
    page.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errores.append(f"JavaScript: {e}"))
    page.on("dialog", lambda d: d.accept())  # confirmaciones hx-confirm: se aceptan
    yield errores
    assert errores == [], "Errores en la página:\n" + "\n".join(errores)


def entrar(page, quien: str):
    """Ingresa como 'admin' o 'investigadora' con las cuentas de preparar.py."""
    email = {"admin": ADMIN, "investigadora": INVESTIGADORA}[quien]
    page.goto("/login")
    page.fill("#email", email)
    page.fill("#password", CLAVE)
    page.click("button:has-text('Ingresar')")
    page.wait_for_url("**/")
