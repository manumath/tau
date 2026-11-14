"""Mide las pantallas de TAU y busca las que escriben en la base al abrirse (PLAN §72, etapa 1).

Arma una base temporal con los datos del manual (seed + `scripts/manual.py --datos`), o usa una copia de la que se le
indique, y la recorre con un cliente de pruebas (sin servidor, sin red, sin concurrencia):

    uv run python scripts/medir.py                       # tiempo y tamaño de las pantallas principales
    uv run python scripts/medir.py --inflar              # lo mismo con +5.000 productos, +3.000 estudiantes, +60.000 avisos
                                                         # y +80.000 filas de auditoría (datos sintéticos)
    uv run python scripts/medir.py --escrituras          # abre todas las pantallas (GET) y lista las que escriben
    uv run python scripts/medir.py --base copia.db ...   # parte de una copia (nunca de data/portal.db directamente)

`--escrituras` anota cada INSERT, UPDATE o DELETE de las conexiones de la aplicación (update hook de apsw). Se aceptan las escrituras
que son de registro (auditoría, consultas que la regla obliga a registrar, sesiones e ingresos): ver `REGISTRO`. Sale con
código 1 si alguna pantalla escribe otra cosa. No va en GitHub Actions: tarda unos minutos.
"""
import argparse
import logging
import os
import random
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CLAVE = "Manual-de-usuario-2026"            # solo en la base temporal (scripts/manual.py)
CUENTAS = {"direccion": ("admin@instituto.test", "Admin-portal-2026"), "docente": ("emmy.noether@instituto.test", CLAVE)}

# Tablas que una pantalla puede escribir al abrirse porque la regla lo pide (registro de quién vio qué) o porque son de la
# sesión. Cualquier otra escritura en un GET es un error.
REGISTRO = {"auditoria", "evaluacion_consulta", "lista_consulta", "sesion", "ingreso", "token", "aviso_enviado",
            "cola_correo"}

PANTALLAS = {
    "docente": ["/", "/productos", "/proyectos", "/investigadores", "/investigacion/pendientes", "/investigacion/coautores",
                "/investigacion/acceso-abierto", "/informes", "/informes/cv", "/docencia/mia", "/docencia/pendientes", "/avisos",
                "/buscar?q=algebra"],
    "direccion": ["/", "/estudiantes", "/docencia/cohortes", "/docencia/oferta", "/calidad/indicadores", "/calidad/ficha",
                  "/calidad/mejora", "/admin/auditoria", "/admin/usuarios", "/informes/calidad", "/docencia/carga"],
}


def preparar(base: str | None, carpeta: Path) -> Path:
    destino = carpeta / "tau.db"
    if base:
        if Path(base).resolve() == (RAIZ / "data" / "portal.db").resolve():
            sys.exit("Haga una copia: sqlite3 data/portal.db \".backup 'copia.db'\"")
        con = sqlite3.connect(base)
        con.execute(f"VACUUM INTO '{destino}'")
        con.close()
        if Path(base).with_suffix(".enlace").exists():      # el enlace de ingreso de la estudiante del manual
            shutil.copy(Path(base).with_suffix(".enlace"), destino.with_suffix(".enlace"))
        return destino
    entorno = {**os.environ, "PORTAL_DB": str(destino), "PORTAL_CORREO_MODO": "desactivado", "PORTAL_INFORMES_PROGRAMADOS": "0"}
    subprocess.run([sys.executable, "scripts/seed.py"], cwd=RAIZ, env=entorno, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "scripts/manual.py", "--datos", str(destino)], cwd=RAIZ, env=entorno, check=True,
                   stdout=subprocess.DEVNULL)
    return destino


def inflar(db: Path):
    """Datos sintéticos de una escala mucho mayor que la de la Carrera, para ver qué pantallas no escalan."""
    c = sqlite3.connect(db)
    c.execute("PRAGMA foreign_keys = OFF")
    tipo = c.execute("SELECT id FROM tipo_producto WHERE nombre = 'Preprint'").fetchone()[0]
    uids = [r[0] for r in c.execute("SELECT usuario_id FROM investigador")]
    random.seed(1)
    palabras = "anillos grupos módulos espacios variedades grafos álgebras funtores categorías esquemas haces cuerpos ideales".split()
    for i in range(5000):
        t = f"{random.choice(palabras).capitalize()} {random.choice(palabras)} y {random.choice(palabras)} {i % 400}"
        cur = c.execute("INSERT INTO producto (tipo_id, titulo, anio, estado_publicacion, revision, creado_por) VALUES (?,?,?,?,?,?)",
                        (tipo, t, 2005 + i % 21, "publicado", "sin_arbitraje", uids[0]))
        c.execute("INSERT INTO producto_autor (producto_id, orden, investigador_id) VALUES (?,?,?)", (cur.lastrowid, 0, random.choice(uids)))
    for i in range(3000):
        cur = c.execute("INSERT INTO persona_externa (nombres, apellidos, email) VALUES (?,?,?)", (f"Est{i}", f"Apellido{i}", f"e{i}@x.test"))
        c.execute("INSERT INTO estudiante (externo_id, nivel, desde, registro_universitario, cohorte_anio, cohorte_ciclo) "
                  "VALUES (?,?,?,?,?,?)", (cur.lastrowid, "licenciatura", 2010 + i % 15, f"9{i:06d}", 2010 + i % 15, "I"))
    c.executemany("INSERT INTO notificacion (usuario_id, asunto, texto) VALUES (?,?,?)", [(uids[0], f"Aviso {i}", "texto") for i in range(60000)])
    c.executemany("INSERT INTO auditoria (usuario_id, accion, entidad, entidad_id) VALUES (?,?,?,?)",
                  [(uids[0], "x", "producto", i) for i in range(80000)])
    c.commit()
    c.close()


ESCRITURAS: list[tuple[str, str]] = []
_OPS = {9: "DELETE", 18: "INSERT", 23: "UPDATE"}     # códigos de SQLite que entrega el update hook


def vigilar():
    """Anota en `ESCRITURAS` cada fila que escribe cualquier conexión que abra la aplicación (update hook de apsw)."""
    from app.comun import db as mod
    abrir = mod._abrir

    def _abrir_vigilado(path):
        con = abrir(path)
        con.conn.set_update_hook(lambda op, _base, tabla, _fila: ESCRITURAS.append((tabla, _OPS.get(op, str(op)))))
        return con
    mod._abrir = _abrir_vigilado


def rutas_get(app, con_ids: list[str]) -> list[str]:
    """Las rutas GET sin parámetros en la dirección, más `con_ids` (las de la base del manual que llevan ids)."""
    from starlette.routing import Route
    simples = sorted({r.path for r in app.routes if isinstance(r, Route) and "GET" in (r.methods or ())
                      and "{" not in r.path and not re.search(r"\.(ics|csv|xlsx|pdf|bib|zip)$", r.path)
                      and r.path not in ("/logout", "/acceso", "/login")})
    return simples + con_ids


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", help="copia de una base (por omisión, la del manual)")
    ap.add_argument("--inflar", action="store_true", help="agrega datos sintéticos de gran escala")
    ap.add_argument("--escrituras", action="store_true", help="busca las pantallas que escriben al abrirse")
    args = ap.parse_args()
    carpeta = Path(tempfile.mkdtemp(prefix="medir-tau-"))
    db = preparar(args.base, carpeta)
    if args.inflar:
        inflar(db)
    con_ids = []
    if args.escrituras:
        # Antes de abrir la aplicación: el sqlite3 de Python y el SQLite de apsw no deben tener la base abierta a la vez en
        # el mismo proceso (al cerrar uno se pierden los bloqueos del otro y apsw da «disk I/O error»).
        sys.path.insert(0, str(RAIZ / "scripts"))
        import manual
        try:
            con_ids = sorted(set(manual._rutas_de_la_base(db).values()))
            con = sqlite3.connect(db)      # las postulaciones (la de la estudiante abre; las demás dan 404)
            con_ids += [f"/estudiante/auxiliaturas/{f[0]}" for f in con.execute("SELECT id FROM postulacion_auxiliatura")]
            con.close()
        except (TypeError, sqlite3.Error):
            print("La base no tiene los datos del manual: solo se recorren las rutas sin ids.")
    os.environ.update(PORTAL_DB=str(db), PORTAL_CORREO_MODO="desactivado", PORTAL_INFORMES_PROGRAMADOS="0")
    sys.path.insert(0, str(RAIZ))
    logging.disable(logging.CRITICAL)
    from starlette.testclient import TestClient

    import main as tau
    if args.escrituras:
        vigilar()
    app = tau.create_app(db)
    tau._ultimo_mantenimiento = float("inf")     # el mantenimiento periódico escribe a propósito: aquí no se dispara
    errores = 0
    enlace = db.with_suffix(".enlace")
    cuentas = {**CUENTAS, **({"estudiante": None} if args.escrituras and enlace.exists() else {})}
    for rol, credenciales in cuentas.items():
        cl = TestClient(app)
        if credenciales:
            r = cl.post("/login", data={"email": credenciales[0], "password": credenciales[1]}, headers={"HX-Request": "true"})
        else:
            r = cl.get(enlace.read_text().strip())        # la estudiante entra con el enlace de su correo
        assert r.status_code == 200, r.text[:200]
        if not args.escrituras:
            print(f"\n{rol}:")
            for ruta in PANTALLAS[rol]:
                ts = []
                for _ in range(3):
                    t0 = time.perf_counter()
                    r = cl.get(ruta)
                    ts.append((time.perf_counter() - t0) * 1000)
                print(f"{statistics.median(ts):8.0f} ms  {r.status_code}  {len(r.content) / 1024:7.0f} KB  {ruta}")
            continue
        rutas, registro, codigos = rutas_get(app, con_ids), 0, Counter()
        for ruta in rutas:
            ESCRITURAS.clear()
            r = cl.get(ruta)
            codigos[r.status_code] += 1
            registro += sum(e[0] in REGISTRO for e in ESCRITURAS)
            malas = Counter(e for e in ESCRITURAS if e[0] not in REGISTRO)
            if malas:
                errores += 1
                print(f"{rol:10} {r.status_code}  {ruta}: " + ", ".join(f"{t} {op}×{n}" for (t, op), n in malas.items()))
        print(f"{rol}: {len(rutas)} pantallas ({', '.join(f'{n} con {c}' for c, n in sorted(codigos.items()))}); "
              f"{registro} escrituras de registro aceptadas.")
    if args.escrituras:
        print("Ninguna pantalla escribe al abrirse." if not errores else f"\n{errores} pantalla(s) escriben al abrirse.")
    shutil.rmtree(carpeta, ignore_errors=True)
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
