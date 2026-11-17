"""Carga de grados académicos desde CSV (PLAN §61).

Formato: una fila por grado con `email`, `nivel` (licenciatura, maestría, doctorado, especialidad, técnico u otro;
también «Licenciado», «Magíster», «Doctor», «M.Sc.», «Ph.D.»…) y, si se tienen, `titulo`, `institucion`, `pais` y
`anio`. La carga **agrega**: no borra ningún grado y omite el que ya está registrado (mismo nivel e institución, o mismo
nivel y título), así que volver a subir el archivo no duplica nada.

Flujo en dos pasos, como las demás cargas: `leer` valida y agrupa por persona sin cambiar nada; `aplicar` agrega los
grados nuevos de las personas sin errores.
"""
from app.comun import academicos, usuarios
from app.comun.db import auditar, get_db, sin_tildes
from app.comun.importar_usuarios import MAX_BYTES, leer_tabla  # noqa: F401  (MAX_BYTES lo usa la ruta)

MAX_FILAS = 2000
ALIAS = {
    "email": ("email", "correo", "e-mail", "mail", "correo electronico", "correo institucional"),
    "nivel": ("nivel", "grado", "nivel del grado"),
    "titulo": ("titulo", "nombre del grado", "titulo obtenido"),
    "institucion": ("institucion", "universidad", "institucion en que lo obtuvo"),
    "pais": ("pais",),
    "anio": ("anio", "ano", "ano de obtencion", "anio de obtencion"),
}
PLANTILLA = ("email,nivel,titulo,institucion,pais,anio\n"
             "emmy.noether@universidad.example,licenciatura,Licenciatura en Matemática,Universidad de Ejemplo,Bolivia,2004\n"
             "emmy.noether@universidad.example,doctorado,Doctorado en Matemática,Universidad de Gotinga,Alemania,2010\n")
# Cómo se escribe el nivel en la práctica (sin tildes, minúsculas y sin puntos).
NIVEL = {
    **{k: k for k in academicos.NIVELES},
    "licenciado": "licenciatura", "licenciada": "licenciatura", "lic": "licenciatura", "titulo profesional": "licenciatura",
    "maestria": "maestria", "magister": "maestria", "master": "maestria", "msc": "maestria", "mgr": "maestria",
    "doctor": "doctorado", "doctora": "doctorado", "phd": "doctorado", "dr": "doctorado", "dra": "doctorado",
    "especialista": "especialidad", "tecnico superior": "tecnico",
}


def nivel(texto: str) -> str | None:
    return NIVEL.get(sin_tildes(texto or "").replace(".", "").strip())


def _registrado(uid: int, g: dict) -> bool:
    for x in get_db().q("SELECT nivel, titulo, institucion FROM grado_academico WHERE usuario_id = ?", [uid]):
        if x["nivel"] != g["nivel"]:
            continue
        if any(x[k] and g[k] and sin_tildes(x[k]).strip() == sin_tildes(g[k]).strip() for k in ("institucion", "titulo")):
            return True
        if not g["institucion"] and not g["titulo"]:
            return True
    return False


def leer(contenido: bytes) -> tuple[list[dict], list[str]]:
    """→ (personas, errores generales). Una entrada por persona: email, usuario, grados (nuevos), repetidos, errores."""
    filas, errores = leer_tabla(contenido, ALIAS, ("email", "nivel"), MAX_FILAS)
    if errores:
        return [], errores
    personas = {}
    for linea, f in filas:
        email = f["email"].lower()
        p = personas.setdefault(email, {"email": email, "grados": [], "repetidos": 0, "errores": []})
        d, problemas = academicos.validar_grado({**f, "nivel": nivel(f["nivel"])})
        if problemas:
            p["errores"].append(f"Fila {linea}: " + " ".join(problemas))
        else:
            p["grados"].append(d)
    for p in personas.values():
        u = usuarios.por_email(p["email"])
        p["usuario"] = u
        if not u:
            p["errores"].insert(0, "No hay una persona registrada con ese correo.")
            continue
        nuevos = []
        for g in p["grados"]:
            if _registrado(u["id"], g) or g in nuevos:
                p["repetidos"] += 1
            else:
                nuevos.append(g)
        p["grados"] = nuevos
    return sorted(personas.values(), key=lambda p: p["email"]), []


def aplicar(personas: list[dict], admin_id: int) -> int:
    """Agrega los grados nuevos de las personas sin errores. → cuántos grados se agregaron."""
    n = 0
    for p in personas:
        if p["errores"] or not p["usuario"]:
            continue
        for g in p["grados"]:
            get_db().t.grado_academico.insert(usuario_id=p["usuario"]["id"], **g)
            auditar(admin_id, "agregar_grado", "usuario", p["usuario"]["id"], academicos.texto_grado(g))
            n += 1
    return n
