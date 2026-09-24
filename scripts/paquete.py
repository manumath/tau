"""Paquete de datos portable: toda la información del portal en un solo archivo .tar.gz.

Sirve para mudar el portal entre instalaciones (p. ej. de Fly.io a un servidor propio, o al
revés) y como respaldo completo. Contiene la base SQLite, las fotos, los adjuntos y un
manifiesto con la versión del esquema y algunos conteos para verificar.

    uv run python scripts/paquete.py exportar [archivo.tar.gz]
    uv run python scripts/paquete.py importar archivo.tar.gz [--reemplazar]

- `exportar` puede ejecutarse con el portal en marcha: la copia de la base es consistente (usa la
  API de respaldo de SQLite).
- `importar` debe ejecutarse con el portal DETENIDO. Si ya hay datos en destino, exige
  --reemplazar y antes los mueve a una carpeta «respaldo-previo-<fecha>» (no borra nada).
  Si el código es más nuevo que el paquete, aplica las migraciones pendientes.

La ubicación de los datos la da PORTAL_DB (igual que para el portal).
"""
import argparse
import io
import json
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmigrate.core import get_db_version, get_migration_scripts  # noqa: E402

from app import config  # noqa: E402

CARPETAS = ("fotos", "adjuntos")
TABLAS_CONTEO = ("usuario", "investigador", "producto", "actividad", "proyecto", "adjunto")


def _conteos(ruta_db: Path) -> dict:
    con = sqlite3.connect(ruta_db)
    try:
        return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLAS_CONTEO}
    finally:
        con.close()


def _version_codigo() -> int:
    return max(get_migration_scripts(config.MIGRACIONES), default=0)


def exportar(destino: Path | None) -> Path:
    db = config.DB_PATH
    if not db.exists():
        sys.exit(f"No existe la base {db}. Revise PORTAL_DB.")
    destino = destino or Path(f"portal-{datetime.now():%Y%m%d-%H%M%S}.tar.gz")
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "portal.db"
        origen, dest = sqlite3.connect(db), sqlite3.connect(copia)
        with dest:
            origen.backup(dest)  # copia consistente aunque el portal esté escribiendo
        origen.close()
        dest.close()
        manifiesto = {"formato": 1, "creado_en": datetime.now().isoformat(timespec="seconds"),
                      "version_esquema": get_db_version(copia), "conteos": _conteos(copia),
                      "instituto": config.NOMBRE_INSTITUTO}
        with tarfile.open(destino, "w:gz") as tar:
            datos = json.dumps(manifiesto, ensure_ascii=False, indent=2).encode()
            info = tarfile.TarInfo("manifiesto.json")
            info.size = len(datos)
            tar.addfile(info, io.BytesIO(datos))
            tar.add(copia, arcname="portal.db")
            # Solo los archivos que la base referencia: los huérfanos (p. ej. de datos borrados) no viajan.
            usados, faltantes = _archivos_referenciados(copia), []
            for carpeta, nombres in usados.items():
                for nombre in sorted(nombres):
                    ruta = db.parent / carpeta / nombre
                    if ruta.is_file():
                        tar.add(ruta, arcname=f"{carpeta}/{nombre}")
                    else:
                        faltantes.append(f"{carpeta}/{nombre}")
            huerfanos = sum(1 for c in CARPETAS if (db.parent / c).is_dir()
                            for f in (db.parent / c).iterdir() if f.name not in usados[c])
    c = manifiesto["conteos"]
    print(f"Paquete creado: {destino} ({destino.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  esquema v{manifiesto['version_esquema']} · {c['usuario']} cuentas · {c['producto']} productos · "
          f"{c['actividad']} actividades · {c['proyecto']} proyectos · {c['adjunto']} adjuntos")
    if faltantes:
        print(f"  ATENCIÓN: {len(faltantes)} archivo(s) referenciado(s) no existen en disco: {', '.join(faltantes[:5])}")
    if huerfanos:
        print(f"  {huerfanos} archivo(s) sin referencia en la base no se incluyeron (restos de datos borrados).")
    return destino


def _archivos_referenciados(ruta_db: Path) -> dict[str, set[str]]:
    con = sqlite3.connect(ruta_db)
    try:
        return {"fotos": {r[0] for r in con.execute("SELECT foto FROM investigador WHERE foto IS NOT NULL")},
                "adjuntos": {r[0] for r in con.execute("SELECT archivo FROM adjunto")}}
    finally:
        con.close()


def importar(archivo: Path, reemplazar: bool):
    db = config.DB_PATH
    if not archivo.exists():
        sys.exit(f"No existe {archivo}.")
    with tarfile.open(archivo, "r:gz") as tar:
        try:
            manifiesto = json.load(tar.extractfile("manifiesto.json"))
        except KeyError:
            sys.exit("El archivo no es un paquete del portal (falta manifiesto.json).")
        if manifiesto["version_esquema"] > _version_codigo():
            sys.exit(f"El paquete viene de una versión más nueva del portal (esquema v{manifiesto['version_esquema']}; "
                     f"este código llega a v{_version_codigo()}). Actualice el código antes de importar.")

        existentes = [p for p in (db, *(db.parent / c for c in CARPETAS)) if p.exists()]
        if existentes and not reemplazar:
            sys.exit(f"Ya hay datos en {db.parent}. Use --reemplazar (se moverán a una carpeta de respaldo, "
                     "no se borran). Detenga el portal antes.")
        db.parent.mkdir(parents=True, exist_ok=True)
        if existentes:
            previo = db.parent / f"respaldo-previo-{datetime.now():%Y%m%d-%H%M%S}"
            previo.mkdir()
            for p in (db, *(db.with_name(db.name + s) for s in ("-wal", "-shm")), *(db.parent / c for c in CARPETAS)):
                if p.exists():
                    shutil.move(str(p), previo / p.name)
            print(f"Datos anteriores movidos a {previo}")

        with tempfile.TemporaryDirectory(dir=db.parent) as tmp:
            # filter="data" rechaza rutas absolutas, «..», enlaces y dispositivos.
            try:
                tar.extractall(tmp, filter="data")
            except tarfile.FilterError as e:
                sys.exit(f"El paquete contiene rutas no permitidas y se rechazó: {e}")
            tmp = Path(tmp)
            if (tmp / "portal.db").stat().st_size == 0:
                sys.exit("La base del paquete está vacía.")
            con = sqlite3.connect(tmp / "portal.db")
            estado = con.execute("PRAGMA integrity_check").fetchone()[0]
            con.close()
            if estado != "ok":
                sys.exit(f"La base del paquete está dañada: {estado}")
            shutil.move(str(tmp / "portal.db"), db)
            for carpeta in CARPETAS:
                if (tmp / carpeta).is_dir():
                    shutil.move(str(tmp / carpeta), db.parent / carpeta)

    from app.db import init_db  # aplica migraciones pendientes si el código es más nuevo
    init_db(db)
    conteos = _conteos(db)
    diferencias = {t: (manifiesto["conteos"][t], conteos[t]) for t in TABLAS_CONTEO
                   if manifiesto["conteos"].get(t) != conteos[t]}
    if diferencias:
        sys.exit(f"Los conteos no coinciden con el manifiesto: {diferencias}")
    print(f"Paquete importado en {db} (esquema v{get_db_version(db)}): {conteos['usuario']} cuentas, "
          f"{conteos['producto']} productos, {conteos['actividad']} actividades, {conteos['proyecto']} proyectos, "
          f"{conteos['adjunto']} adjuntos. Ya puede iniciar el portal.")


def main():
    p = argparse.ArgumentParser(description="Exportar o importar todos los datos del portal.")
    sub = p.add_subparsers(dest="accion", required=True)
    e = sub.add_parser("exportar", help="crea un paquete .tar.gz con base, fotos y adjuntos")
    e.add_argument("archivo", nargs="?", type=Path)
    i = sub.add_parser("importar", help="restaura un paquete en esta instalación (con el portal detenido)")
    i.add_argument("archivo", type=Path)
    i.add_argument("--reemplazar", action="store_true", help="mover los datos actuales a un respaldo y reemplazarlos")
    a = p.parse_args()
    exportar(a.archivo) if a.accion == "exportar" else importar(a.archivo, a.reemplazar)


if __name__ == "__main__":
    main()
