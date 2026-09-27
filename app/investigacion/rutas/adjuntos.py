"""Subida, descarga y borrado de adjuntos. Solo quien puede editar el registro (o un admin)
puede verlos: suelen ser certificados u otros documentos personales."""
from urllib.parse import quote

from fasthtml.common import APIRouter, FileResponse, Response, UploadFile

from app.investigacion import actividades, adjuntos, productos
from app.components.registros import seccion_adjuntos
from app.db import auditar

rt = APIRouter()


def _registro(entidad: str, entidad_id: int):
    if entidad == "producto":
        return productos.obtener(entidad_id), productos.puede_editar
    if entidad == "actividad":
        return actividades.obtener(entidad_id), actividades.puede_editar
    return None, None


def _puede_editar(auth, entidad, entidad_id) -> bool:
    registro, puede = _registro(entidad, entidad_id)
    return bool(registro) and puede(registro, auth["id"])


@rt("/adjuntos/{entidad}/{entidad_id}")
async def post(auth, entidad: str, entidad_id: int, archivo: UploadFile = None):
    if not _puede_editar(auth, entidad, entidad_id):
        return Response("No autorizado", status_code=403)
    if archivo is None or not archivo.filename:
        return seccion_adjuntos(entidad, entidad_id, True, "Seleccione un archivo.")
    try:
        adj = adjuntos.guardar(entidad, entidad_id, archivo.filename,
                               await archivo.read(adjuntos.MAX_BYTES + 1), auth["id"])
    except ValueError as e:
        return seccion_adjuntos(entidad, entidad_id, True, str(e))
    auditar(auth["id"], "subir_adjunto", entidad, entidad_id, adj["nombre"])
    return seccion_adjuntos(entidad, entidad_id, True)


@rt("/adjuntos/{adj_id}")
def get(auth, adj_id: int):
    adj = adjuntos.obtener(adj_id)
    if not adj or not (auth["es_admin"] or _puede_editar(auth, adj["entidad"], adj["entidad_id"])):
        return Response("No encontrado", status_code=404)
    # Los PDF e imágenes se muestran en el navegador; el nombre original se conserva al guardar.
    return FileResponse(adjuntos.ruta(adj), media_type=adj["mime"], headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(adj['nombre'])}",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store"})


@rt("/adjuntos/{adj_id}")
def delete(auth, adj_id: int):
    adj = adjuntos.obtener(adj_id)
    if not adj or not _puede_editar(auth, adj["entidad"], adj["entidad_id"]):
        return Response("No autorizado", status_code=403)
    adjuntos.eliminar(adj)
    auditar(auth["id"], "eliminar_adjunto", adj["entidad"], adj["entidad_id"], adj["nombre"])
    return seccion_adjuntos(adj["entidad"], adj["entidad_id"], True)
