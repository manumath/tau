"""Repositorio de evidencias del marco de calidad (PLAN §57, etapa 4): documentos subidos, enlaces e informes generados por
el sistema, cada uno asociado a uno o más criterios y con vigencia.

Los archivos se validan por su contenido (firma de bytes, como `investigacion.adjuntos`), se guardan con nombre aleatorio
en <datos>/evidencias, fuera de /static, y llevan su huella SHA-256: con ella se comprueba después que un archivo entregado
es el mismo que se registró. Por eso el archivo de una evidencia no se reemplaza (se registra otra).
"""
import hashlib
import io
import re
import secrets
import zipfile
from datetime import date
from pathlib import Path

from app.comun.db import dir_datos, get_db, transaccion
from app.investigacion import adjuntos

TIPOS = {"documento": "Documento", "enlace": "Enlace", "informe": "Informe del sistema"}
MAX_BYTES = adjuntos.MAX_BYTES
# Formatos de oficina: un ZIP con la pieza que los distingue.
OFFICE = {"xl/workbook.xml": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
          "word/document.xml": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
          "ppt/presentation.xml": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx")}
FORMATOS = "PDF, PNG, JPG, XLSX, DOCX o PPTX"


def dir_evidencias() -> Path:
    d = dir_datos() / "evidencias"
    d.mkdir(parents=True, exist_ok=True)
    return d


def detectar_tipo(contenido: bytes) -> tuple[str, str] | None:
    """(mime, extensión) según el contenido; None si no es un formato admitido."""
    tipo = adjuntos.detectar_tipo(contenido)
    if tipo or not contenido.startswith(b"PK\x03\x04"):
        return tipo
    try:
        nombres = set(zipfile.ZipFile(io.BytesIO(contenido)).namelist())
    except zipfile.BadZipFile:
        return None
    return next((t for pieza, t in OFFICE.items() if pieza in nombres), None)


def huella(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def ruta(e: dict) -> Path:
    return dir_evidencias() / Path(e["archivo"]).name


# --- Lectura ------------------------------------------------------------------------------------------------

def _con_criterios(filas: list[dict]) -> list[dict]:
    if not filas:
        return filas
    ids = [f["id"] for f in filas]
    crit: dict[int, list[dict]] = {}
    for c in get_db().q(
            f"""SELECT ec.evidencia_id, c.id, c.codigo, c.nombre FROM evidencia_criterio ec
                JOIN criterio_calidad c ON c.id = ec.criterio_id
                JOIN dimension_calidad d ON d.id = c.dimension_id
                WHERE ec.evidencia_id IN ({','.join('?' * len(ids))}) ORDER BY d.codigo, c.codigo""", ids):
        crit.setdefault(c.pop("evidencia_id"), []).append(c)
    hoy = date.today().isoformat()
    for f in filas:
        f["criterios"] = crit.get(f["id"], [])
        f["vencida"] = bool(f["vigente_hasta"] and f["vigente_hasta"] < hoy)
    return filas


def listar(mid: int, criterio: int | None = None, estado: str = "") -> list[dict]:
    """Las evidencias del marco, de la más reciente a la más antigua; con filtro por criterio y por vigencia."""
    sql = """SELECT e.*, u.nombres || ' ' || u.apellidos AS por FROM evidencia_calidad e
             LEFT JOIN usuario u ON u.id = e.registrado_por WHERE e.marco_id = ?"""
    params: list = [mid]
    if criterio:
        sql += " AND e.id IN (SELECT evidencia_id FROM evidencia_criterio WHERE criterio_id = ?)"
        params.append(criterio)
    filas = _con_criterios(get_db().q(sql + " ORDER BY COALESCE(e.fecha, substr(e.registrado_en, 1, 10)) DESC, e.id DESC",
                                      params))
    if estado == "vigentes":
        return [f for f in filas if not f["vencida"]]
    if estado == "vencidas":
        return [f for f in filas if f["vencida"]]
    return filas


def de_actividad(tid: int) -> list[dict]:
    """Las evidencias ligadas a una actividad del plan de mejora (las sube su responsable; PLAN §72, etapa 11)."""
    return _con_criterios(get_db().q(
        """SELECT e.*, u.nombres || ' ' || u.apellidos AS por FROM evidencia_calidad e
           LEFT JOIN usuario u ON u.id = e.registrado_por WHERE e.actividad_id = ?
           ORDER BY COALESCE(e.fecha, substr(e.registrado_en, 1, 10)) DESC, e.id DESC""", [tid]))


def obtener(eid: int) -> dict | None:
    filas = get_db().q("""SELECT e.*, u.nombres || ' ' || u.apellidos AS por FROM evidencia_calidad e
                          LEFT JOIN usuario u ON u.id = e.registrado_por WHERE e.id = ?""", [eid])
    return _con_criterios(filas)[0] if filas else None


def por_huella(sha256: str) -> list[dict]:
    return _con_criterios(get_db().q("SELECT * FROM evidencia_calidad WHERE sha256 = ? ORDER BY id", [sha256]))


def conteo_por_criterio(mid: int) -> dict[int, int]:
    """Cuántas evidencias vigentes respalda cada criterio del marco."""
    return {f["criterio_id"]: f["n"] for f in get_db().q(
        """SELECT ec.criterio_id, COUNT(*) n FROM evidencia_criterio ec JOIN evidencia_calidad e ON e.id = ec.evidencia_id
           WHERE e.marco_id = ? AND (e.vigente_hasta IS NULL OR e.vigente_hasta >= ?) GROUP BY ec.criterio_id""",
        [mid, date.today().isoformat()])}


def criterios_del_marco(mid: int) -> list[dict]:
    return get_db().q(
        """SELECT c.id, c.codigo, c.nombre, d.codigo AS dimension_codigo, d.nombre AS dimension_nombre
           FROM criterio_calidad c JOIN dimension_calidad d ON d.id = c.dimension_id
           WHERE d.marco_id = ? ORDER BY d.codigo, c.codigo""", [mid])


# --- Validación ---------------------------------------------------------------------------------------------

def _fecha(texto: str) -> str | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    date.fromisoformat(texto)   # ValueError si no es AAAA-MM-DD
    return texto


def validar(d: dict, mid: int, tipo: str, criterios_opcionales: bool = False) -> tuple[dict, list[str]]:
    """Datos comunes de una evidencia (título, descripción, fechas, criterios y, en un enlace, la dirección). La de una
    actividad del plan de mejora puede ir sin criterios: la liga la actividad y la Comisión los marca después."""
    errores = []
    x = {"titulo": (d.get("titulo") or "").strip(), "descripcion": (d.get("descripcion") or "").strip() or None,
         "url": (d.get("url") or "").strip() or None}
    if not x["titulo"]:
        errores.append("Indique el título de la evidencia.")
    for campo, texto in (("fecha", "La fecha del documento"), ("vigente_hasta", "La vigencia")):
        try:
            x[campo] = _fecha(d.get(campo))
        except ValueError:
            x[campo] = d.get(campo)
            errores.append(f"{texto} no es una fecha válida.")
    if x["fecha"] and x["vigente_hasta"] and x["vigente_hasta"] < x["fecha"]:
        errores.append("La vigencia termina antes de la fecha del documento.")
    validos = {c["id"] for c in criterios_del_marco(mid)}
    x["criterios"] = sorted({int(c) for c in d.get("criterios") or [] if str(c).isdigit() and int(c) in validos})
    if not x["criterios"] and not criterios_opcionales:
        errores.append("Marque al menos un criterio que la evidencia respalde.")
    if tipo == "enlace":
        if not x["url"]:
            errores.append("Indique la dirección del enlace.")
        elif not re.match(r"https?://[^\s/]+\.[^\s]+$", x["url"]):
            errores.append("La dirección debe empezar con http:// o https://.")
    else:
        x["url"] = None
    return x, errores


def validar_archivo(nombre: str, contenido: bytes) -> list[str]:
    if not contenido:
        return ["Seleccione un archivo."]
    if len(contenido) > MAX_BYTES:
        return ["El archivo supera los 20 MB."]
    if not detectar_tipo(contenido):
        return [f"Solo se admiten archivos {FORMATOS}."]
    return []


# --- Escritura ----------------------------------------------------------------------------------------------

def _criterios(eid: int, ids: list[int]):
    get_db().execute("DELETE FROM evidencia_criterio WHERE evidencia_id = ?", [eid])
    for c in ids:
        get_db().t.evidencia_criterio.insert(evidencia_id=eid, criterio_id=c)


def crear(mid: int, tipo: str, x: dict, uid: int, nombre: str = "", contenido: bytes = b"", informe: str | None = None,
          parametros: str | None = None, actividad_id: int | None = None) -> int:
    """Registra la evidencia; los documentos e informes guardan su archivo y su huella."""
    datos = {k: x[k] for k in ("titulo", "descripcion", "fecha", "vigente_hasta", "url")}
    archivo = None
    if tipo != "enlace":
        mime, ext = detectar_tipo(contenido)
        archivo = f"{secrets.token_hex(16)}.{ext}"
        (dir_evidencias() / archivo).write_bytes(contenido)
        datos |= {"archivo": archivo, "nombre_archivo": adjuntos.nombre_seguro(nombre), "mime": mime,
                  "tamano": len(contenido), "sha256": huella(contenido)}
    try:
        with transaccion():
            eid = get_db().t.evidencia_calidad.insert(marco_id=mid, tipo=tipo, informe=informe, parametros=parametros,
                                                      registrado_por=uid, actividad_id=actividad_id, **datos)["id"]
            _criterios(eid, x["criterios"])
    except Exception:
        if archivo:
            (dir_evidencias() / archivo).unlink(missing_ok=True)
        raise
    return eid


def actualizar(e: dict, x: dict):
    """Cambia los datos y los criterios; el archivo y su huella no cambian."""
    with transaccion():
        get_db().t.evidencia_calidad.update({k: x[k] for k in ("titulo", "descripcion", "fecha", "vigente_hasta")}
                                            | ({"url": x["url"]} if e["tipo"] == "enlace" else {}), e["id"])
        _criterios(e["id"], x["criterios"])


def eliminar(e: dict):
    get_db().execute("DELETE FROM evidencia_calidad WHERE id = ?", [e["id"]])
    if e["archivo"]:
        ruta(e).unlink(missing_ok=True)
