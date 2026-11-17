"""Paquete de datos portable (scripts/paquete.py): exportar e importar entre instalaciones."""
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path

from PIL import Image

from app.calidad import evidencias
from app.comun import adjuntos
from app.investigacion import perfiles, productos
from app.comun import config, fotos, usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login
from tests.test_evidencias_calidad import PDF

RAIZ = Path(__file__).resolve().parent.parent


def paquete(accion, *args, db: Path):
    return subprocess.run([sys.executable, str(RAIZ / "scripts" / "paquete.py"), accion, *map(str, args)],
                          env={**os.environ, "TAU_DB": str(db)}, capture_output=True, text=True, cwd=RAIZ)


def _datos_con_archivos(tmp_path):
    """Base con una foto, un adjunto y un archivo huérfano en la carpeta de adjuntos."""
    uid = usuarios.por_email("inv@test.cl")["id"]
    buf = io.BytesIO()
    Image.new("RGB", (500, 500), (10, 20, 30)).save(buf, "PNG")
    perfiles.actualizar_foto(uid, fotos.guardar(uid, fotos.procesar(buf.getvalue()), None))
    tipo = get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Reporte de investigación'")[0]["id"]
    d, _ = productos.preparar(dict(tipo_id=str(tipo), titulo="Notas", anio="2026",
                                   estado_publicacion="publicado", revision="sin_arbitraje"), [f"i:{uid}"], [])
    pid = productos.guardar(d, [f"i:{uid}"], uid)
    adjuntos.guardar("producto", pid, "notas.pdf", b"%PDF-1.4 contenido", uid)
    (adjuntos.dir_adjuntos() / "huerfano.pdf").write_bytes(b"%PDF-1.4 resto")
    marco = get_db().q("SELECT id FROM marco_calidad LIMIT 1")[0]["id"]
    evidencias.crear(marco, "documento", {"titulo": "Acta", "descripcion": None, "fecha": None, "vigente_hasta": None,
                                          "url": None, "criterios": []}, uid, "acta.pdf", PDF)
    return uid


def test_exportar_e_importar_en_otra_instalacion(app, tmp_path):
    uid = _datos_con_archivos(tmp_path)
    origen = tmp_path / "test.db"
    archivo = tmp_path / "paquete.tar.gz"
    r = paquete("exportar", archivo, db=origen)
    assert r.returncode == 0, r.stderr
    assert "1 archivo(s) sin referencia" in r.stdout
    nombres = tarfile.open(archivo).getnames()
    assert "manifiesto.json" in nombres and "tau.db" in nombres
    assert any(n.startswith("fotos/") for n in nombres) and "adjuntos/huerfano.pdf" not in nombres

    destino = tmp_path / "servidor" / "tau.db"
    r = paquete("importar", archivo, db=destino)
    assert r.returncode == 0, r.stderr + r.stdout
    foto = get_db().q("SELECT foto FROM investigador WHERE usuario_id = ?", [uid])[0]["foto"]
    assert (destino.parent / "fotos" / foto).is_file()
    assert len(list((destino.parent / "adjuntos").iterdir())) == 1
    archivo_ev = get_db().q("SELECT archivo FROM evidencia_calidad")[0]["archivo"]
    assert (destino.parent / "evidencias" / archivo_ev).read_bytes() == PDF   # la huella SHA-256 sigue valiendo

    # Una segunda importación sin --reemplazar se niega; con --reemplazar respalda lo anterior.
    assert paquete("importar", archivo, db=destino).returncode != 0
    r = paquete("importar", archivo, "--reemplazar", db=destino)
    assert r.returncode == 0 and "respaldo-previo" in r.stdout
    assert any(p.name.startswith("respaldo-previo-") for p in destino.parent.iterdir())


def test_toda_carpeta_de_archivos_viaja_en_el_paquete():
    """Cada carpeta que el sistema crea junto a la base (`dir_datos() / "…"`) está en el paquete, salvo los correos de
    desarrollo y los registros, que no son datos."""
    sys.path.insert(0, str(RAIZ / "scripts"))
    import paquete as pq
    usadas = set()
    for f in (RAIZ / "app").rglob("*.py"):
        usadas |= set(re.findall(r'dir_datos\(\) / "([a-z_]+)"', f.read_text(encoding="utf-8")))
    assert usadas - {"correos"} <= set(pq.CARPETAS), usadas - set(pq.CARPETAS)


def test_importa_un_paquete_anterior_sin_evidencias(app, tmp_path):
    """Un paquete hecho antes de que viajaran las evidencias no trae su conteo: se importa igual."""
    origen = tmp_path / "test.db"
    archivo = tmp_path / "viejo.tar.gz"
    assert paquete("exportar", archivo, db=origen).returncode == 0
    viejo = tmp_path / "viejo2.tar.gz"
    with tarfile.open(archivo) as ok, tarfile.open(viejo, "w:gz") as tar:
        for m in ok.getmembers():
            if m.name == "manifiesto.json":
                datos = json.load(ok.extractfile(m))
                datos["conteos"].pop("evidencia_calidad")
                crudo = json.dumps(datos).encode()
                m.size = len(crudo)
                tar.addfile(m, io.BytesIO(crudo))
            else:
                tar.addfile(m, ok.extractfile(m) if m.isfile() else None)
    r = paquete("importar", viejo, db=tmp_path / "dest" / "tau.db")
    assert r.returncode == 0, r.stderr + r.stdout


def test_rechaza_paquetes_de_una_version_mas_nueva(app, tmp_path):
    archivo = tmp_path / "futuro.tar.gz"
    with tarfile.open(archivo, "w:gz") as tar:
        datos = json.dumps({"version_esquema": 999, "conteos": {}}).encode()
        info = tarfile.TarInfo("manifiesto.json")
        info.size = len(datos)
        tar.addfile(info, io.BytesIO(datos))
    r = paquete("importar", archivo, db=tmp_path / "x" / "tau.db")
    assert r.returncode != 0 and "más nueva" in r.stderr


def test_rechaza_rutas_peligrosas(app, tmp_path):
    r = paquete("exportar", tmp_path / "ok.tar.gz", db=tmp_path / "test.db")
    assert r.returncode == 0, r.stderr
    malo = tmp_path / "malo.tar.gz"
    with tarfile.open(tmp_path / "ok.tar.gz") as ok, tarfile.open(malo, "w:gz") as tar:
        for m in ok.getmembers():
            tar.addfile(m, ok.extractfile(m) if m.isfile() else None)
        info = tarfile.TarInfo("../fuera.txt")
        info.size = 3
        tar.addfile(info, io.BytesIO(b"mal"))
    r = paquete("importar", malo, db=tmp_path / "dest" / "tau.db")
    assert r.returncode != 0 and not (tmp_path / "fuera.txt").exists()


# --- Modo solo lectura (para exportar sin que nada cambie después de la copia) ------------------

def test_solo_lectura_permite_consultar_pero_no_modificar(client, monkeypatch, buzon):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    monkeypatch.setattr(config, "SOLO_LECTURA", True)
    assert login(client, "inv@test.cl", PASS_TEMP).headers["hx-redirect"] == "/"  # ingresar sí
    r = client.get("/productos")
    assert r.status_code == 200 and "en mantenimiento" in r.text                  # consultar sí, con aviso
    r = client.put("/perfil/datos", headers=HX, data={"nombres": "Otra", "apellidos": "Persona"})
    assert r.status_code == 503 and usuarios.por_id(uid)["nombres"] == "Emmy"     # modificar no
    r = client.post("/perfil/preferencias/perfil_publico", data={"perfil_publico": "1"})
    assert r.status_code == 503 and "En mantenimiento" in r.text                   # página con estilo
    client.post("/logout")
    assert client.post("/recuperar", headers=HX, data={"email": "inv@test.cl"}).status_code == 503
    assert buzon == []                                                             # también en rutas públicas
