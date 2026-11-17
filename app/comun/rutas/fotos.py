"""Foto de perfil de una persona, para quien tiene sesión. Es de la plataforma (PLAN §73): la muestran las listas y fichas
de todos los módulos, también con Investigación apagada. La versión pública del directorio (`/publico/fotos`) es de ese
módulo."""
from fasthtml.common import APIRouter, FileResponse, Response

from app.comun import fotos
from app.comun.db import get_db

rt = APIRouter()


@rt("/fotos/{uid}")
def get(uid: int):
    """Requiere sesión (pasa por la Beforeware); no es pública."""
    fila = get_db().q("SELECT foto FROM investigador WHERE usuario_id = ?", [uid])
    if not fila or not fila[0]["foto"] or not fotos.ruta(fila[0]["foto"]).exists():
        return Response(status_code=404)
    # La URL lleva ?v=<archivo>, así que puede cachearse: al cambiar la foto cambia la URL.
    return FileResponse(fotos.ruta(fila[0]["foto"]), media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=31536000, immutable"})
