"""Capturas de pantalla de TAU sobre una base temporal (nunca toca data/portal.db).

Uso (desde la raíz del proyecto):

    uv run python .claude/skills/captura-visual/capturar.py [opciones] RUTA [RUTA ...]

Cada RUTA es una ruta del sistema, opcionalmente con textos en los que hacer clic antes de la
captura, separados por «|»:  "/docencia/carga|Noether, Emmy|Registrar o cambiar la carga en el vínculo"

Opciones:
  --base seed|dev     seed (por omisión): base nueva con scripts/seed.py; dev: copia de data/portal.db
  --como EMAIL        cuenta con la que se ingresa (por omisión admin@instituto.test)
  --clave CLAVE       su contraseña (por omisión la de la cuenta admin de ejemplo)
  --clave-prueba      fija CLAVE como contraseña definitiva de EMAIL en la copia (para cuentas con
                      contraseña temporal); solo en la copia
  --rol ROL:SIGLA     asigna un rol en la copia (repetible), p. ej. direccion_carrera:CMAT
  --salida DIR        carpeta de las capturas (por omisión, una temporal que se informa)
  --ancho N --alto N  tamaño de la ventana (1280 × 900); --movil usa 375 × 812
  --pagina-completa   captura la página entera, no solo la ventana

Imprime la ruta de cada PNG. Termina con error si la página registra errores de JavaScript.
"""
import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
CLAVE_ADMIN = "Admin-portal-2026"  # cuenta de ejemplo de scripts/seed.py (ver README)


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def preparar_base(base: str, carpeta: Path) -> Path:
    db = carpeta / "tau.db"
    entorno = {**os.environ, "PORTAL_DB": str(db), "PORTAL_CORREO_MODO": "desactivado"}
    if base == "dev":
        origen = RAIZ / "data" / "portal.db"
        if not origen.exists():
            sys.exit("No existe data/portal.db: use --base seed.")
        # Copia consistente aunque el servidor de desarrollo esté en uso.
        subprocess.run(["sqlite3", str(origen), f".backup '{db}'"], check=True)
    else:
        subprocess.run([sys.executable, "scripts/seed.py"], cwd=RAIZ, env=entorno, check=True,
                       stdout=subprocess.DEVNULL)
    return db


def ajustar_base(db: Path, email: str, clave: str, fijar_clave: bool, roles: list[str]):
    """Contraseña y roles de prueba, solo en la copia."""
    codigo = f"""
from app.comun.db import init_db
init_db({str(db)!r})
from app.comun import permisos, unidades, usuarios
u = usuarios.por_email({email!r})
assert u, "No existe la cuenta {email}"
if {fijar_clave!r}:
    usuarios.cambiar_password(u["id"], {clave!r}, temporal=False)
for r in {roles!r}:
    rol, _, sigla = r.partition(":")
    errores = permisos.asignar(u["id"], rol, unidades.id_de(sigla or "UMSA"))
    assert not errores or "Ya tiene" in errores[0], errores
"""
    subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, check=True,
                   env={**os.environ, "PORTAL_DB": str(db)})


def iniciar_servidor(db: Path, carpeta: Path) -> tuple[subprocess.Popen, str]:
    puerto = _puerto_libre()
    log = open(carpeta / "servidor.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(puerto)], cwd=RAIZ,
                            env={**os.environ, "PORTAL_DB": str(db), "PORTAL_CORREO_MODO": "desactivado"},
                            stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{puerto}"
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{url}/login", timeout=1)
            return proc, url
        except OSError:
            time.sleep(0.25)
    proc.terminate()
    sys.exit(f"El servidor no arrancó: ver {carpeta / 'servidor.log'}")


def capturar(url: str, rutas: list[str], args, salida: Path) -> int:
    from playwright.sync_api import sync_playwright
    errores_js = []
    canal = os.environ.get("PLAYWRIGHT_CANAL", "chrome") or None
    ancho, alto = (375, 812) if args.movil else (args.ancho, args.alto)
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel=canal)
        pagina = navegador.new_page(viewport={"width": ancho, "height": alto})
        pagina.on("pageerror", lambda e: errores_js.append(str(e)))
        pagina.goto(f"{url}/login")
        pagina.fill("input[name=email]", args.como)
        pagina.fill("input[name=password]", args.clave)
        pagina.click("button[type=submit]")
        pagina.wait_for_load_state("networkidle")
        if "/login" in pagina.url:
            navegador.close()
            sys.exit("No se pudo ingresar: revise --como / --clave (o use --clave-prueba).")
        for i, espec in enumerate(rutas, start=1):
            ruta, *clics = espec.split("|")
            pagina.goto(url + ruta)
            pagina.wait_for_load_state("networkidle")
            for texto in clics:
                pagina.get_by_text(texto, exact=False).first.click()
                pagina.wait_for_timeout(600)
            nombre = f"{i:02d}-" + (re.sub(r"[^a-z0-9]+", "-", ruta.lower()).strip("-") or "inicio") + ".png"
            pagina.screenshot(path=str(salida / nombre), full_page=args.pagina_completa)
            print(salida / nombre)
        navegador.close()
    for e in errores_js:
        print(f"Error de JavaScript: {e}", file=sys.stderr)
    return 1 if errores_js else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rutas", nargs="+")
    ap.add_argument("--base", choices=("seed", "dev"), default="seed")
    ap.add_argument("--como", default="admin@instituto.test")
    ap.add_argument("--clave", default=CLAVE_ADMIN)
    ap.add_argument("--clave-prueba", action="store_true")
    ap.add_argument("--rol", action="append", default=[])
    ap.add_argument("--salida")
    ap.add_argument("--ancho", type=int, default=1280)
    ap.add_argument("--alto", type=int, default=900)
    ap.add_argument("--movil", action="store_true")
    ap.add_argument("--pagina-completa", action="store_true")
    args = ap.parse_args()

    carpeta = Path(tempfile.mkdtemp(prefix="tau-captura-"))
    salida = Path(args.salida) if args.salida else carpeta
    salida.mkdir(parents=True, exist_ok=True)
    db = preparar_base(args.base, carpeta)
    if args.clave_prueba or args.rol:
        ajustar_base(db, args.como, args.clave, args.clave_prueba, args.rol)
    proc, url = iniciar_servidor(db, carpeta)
    try:
        codigo = capturar(url, args.rutas, args, salida)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        if args.salida:
            shutil.rmtree(carpeta, ignore_errors=True)
    sys.exit(codigo)


if __name__ == "__main__":
    main()
