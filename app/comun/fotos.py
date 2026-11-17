"""Procesamiento y almacenamiento de fotos de perfil.

Toda imagen subida se decodifica y se vuelve a codificar como JPEG cuadrado de 400 px:
así se validan el formato y el tamaño, se descartan los metadatos (EXIF, GPS) y no se
guarda nunca el archivo original tal como llegó.
"""
import io
import secrets
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.comun.db import dir_datos

MAX_BYTES = 5 * 1024 * 1024
LADO = 400
FORMATOS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 40_000_000  # evita "bombas" de descompresión


def dir_fotos() -> Path:
    d = dir_datos() / "fotos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def procesar(contenido: bytes) -> bytes:
    """Devuelve el JPEG normalizado o lanza ValueError con un mensaje para el usuario."""
    if len(contenido) > MAX_BYTES:
        raise ValueError("La imagen supera los 5 MB.")
    try:
        img = Image.open(io.BytesIO(contenido))
        if img.format not in FORMATOS:
            raise ValueError("Use una imagen JPG, PNG o WebP.")
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ValueError("El archivo no es una imagen válida.") from e
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (LADO, LADO), Image.Resampling.LANCZOS)
    salida = io.BytesIO()
    img.save(salida, "JPEG", quality=85, optimize=True)
    return salida.getvalue()


def guardar(uid: int, jpeg: bytes, anterior: str | None) -> str:
    """Guarda con nombre nuevo (sirve de cache-busting) y borra la anterior."""
    nombre = f"{uid}-{secrets.token_hex(4)}.jpg"
    (dir_fotos() / nombre).write_bytes(jpeg)
    borrar(anterior)
    return nombre


def borrar(nombre: str | None):
    if nombre:
        (dir_fotos() / Path(nombre).name).unlink(missing_ok=True)


def ruta(nombre: str) -> Path:
    return dir_fotos() / Path(nombre).name
