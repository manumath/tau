"""Archivos adjuntos a actividades y productos (certificados, afiches, diapositivas…).

El tipo se decide por el contenido (firma de bytes), no por la extensión ni por el
Content-Type que envía el navegador. Se guardan con nombre aleatorio fuera de /static y se
descargan solo por una ruta que verifica permisos.
"""
import re
import secrets
import unicodedata
from pathlib import Path

from app.comun.db import dir_datos, get_db

MAX_BYTES = 20 * 1024 * 1024
MAX_POR_ENTIDAD = 10
# firma → (mime, extensión)
FIRMAS = [(b"%PDF-", ("application/pdf", "pdf")),
          (b"\x89PNG\r\n\x1a\n", ("image/png", "png")),
          (b"\xff\xd8\xff", ("image/jpeg", "jpg"))]


def dir_adjuntos() -> Path:
    d = dir_datos() / "adjuntos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def detectar_tipo(contenido: bytes) -> tuple[str, str] | None:
    return next((t for firma, t in FIRMAS if contenido.startswith(firma)), None)


def nombre_seguro(nombre: str) -> str:
    """Nombre legible para mostrar y descargar, sin rutas ni caracteres problemáticos."""
    nombre = Path(nombre.replace("\\", "/")).name
    nombre = unicodedata.normalize("NFC", nombre)
    nombre = re.sub(r'[\x00-\x1f"<>|:*?/\\]', "_", nombre).strip(". ") or "archivo"
    return nombre[:120]


def listar(entidad: str, entidad_id: int) -> list[dict]:
    return get_db().q("SELECT * FROM adjunto WHERE entidad = ? AND entidad_id = ? ORDER BY id",
                      [entidad, entidad_id])


def obtener(adj_id: int) -> dict | None:
    filas = get_db().q("SELECT * FROM adjunto WHERE id = ?", [adj_id])
    return filas[0] if filas else None


def guardar(entidad: str, entidad_id: int, nombre: str, contenido: bytes, usuario_id: int) -> dict:
    """Valida y guarda; lanza ValueError con un mensaje para el usuario."""
    if not contenido:
        raise ValueError("El archivo está vacío.")
    if len(contenido) > MAX_BYTES:
        raise ValueError("El archivo supera los 20 MB.")
    tipo = detectar_tipo(contenido)
    if not tipo:
        raise ValueError("Solo se admiten archivos PDF, PNG o JPG.")
    if len(listar(entidad, entidad_id)) >= MAX_POR_ENTIDAD:
        raise ValueError(f"Se admiten hasta {MAX_POR_ENTIDAD} adjuntos por registro.")
    mime, ext = tipo
    archivo = f"{secrets.token_hex(16)}.{ext}"
    (dir_adjuntos() / archivo).write_bytes(contenido)
    return get_db().t.adjunto.insert(entidad=entidad, entidad_id=entidad_id,
                                     nombre=nombre_seguro(nombre), archivo=archivo, mime=mime,
                                     tamano=len(contenido), subido_por=usuario_id)


def ruta(adj: dict) -> Path:
    return dir_adjuntos() / Path(adj["archivo"]).name


def eliminar(adj: dict):
    ruta(adj).unlink(missing_ok=True)
    get_db().execute("DELETE FROM adjunto WHERE id = ?", [adj["id"]])


def eliminar_de(entidad: str, entidad_id: int):
    """Borra los archivos de un registro que se elimina (las filas las borra quien llama)."""
    for adj in listar(entidad, entidad_id):
        ruta(adj).unlink(missing_ok=True)


def tamano_texto(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{max(1, round(n / 1024))} KB"
