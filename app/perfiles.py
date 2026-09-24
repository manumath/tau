"""Acceso a datos del perfil del investigador y sus áreas MSC."""
from app.db import get_db, sin_tildes

MAX_AREAS = 10
LARGO_BIO = 3000

GRADOS = ["Doctorado", "Magíster", "Licenciatura o título profesional", "Otro"]
CARGOS_SUGERIDOS = ["Investigador(a) titular", "Investigador(a) asociado(a)",
                    "Investigador(a) adjunto(a)", "Investigador(a) postdoctoral",
                    "Estudiante de doctorado", "Profesor(a) emérito(a)", "Investigador(a) visitante"]


def obtener(uid: int) -> dict | None:
    """Usuario + investigador en un solo dict (None si la cuenta no es de investigador)."""
    filas = get_db().q(
        """SELECT u.id, u.email, u.nombres, u.apellidos, u.activo, i.*
           FROM usuario u JOIN investigador i ON i.usuario_id = u.id WHERE u.id = ?""", [uid])
    return filas[0] if filas else None


def actualizar_datos(uid: int, *, nombres, apellidos, grado, cargo, unidad):
    db = get_db()
    db.t.usuario.update(id=uid, nombres=nombres, apellidos=apellidos)
    actualizar_campos(uid, grado=grado, cargo=cargo, unidad=unidad)


def actualizar_campos(uid: int, **campos):
    asignaciones = ", ".join(f"{c} = :{c}" for c in campos)
    get_db().execute(
        f"UPDATE investigador SET {asignaciones}, actualizado_en = datetime('now') "
        "WHERE usuario_id = :uid", {**campos, "uid": uid})


def actualizar_identificadores(uid: int, valores: dict):
    actualizar_campos(uid, **valores)


def actualizar_bio(uid: int, bio: str | None):
    actualizar_campos(uid, bio=bio)


def actualizar_foto(uid: int, archivo: str | None):
    actualizar_campos(uid, foto=archivo)


# --- Áreas MSC ---------------------------------------------------------------

def areas(uid: int) -> list[dict]:
    return get_db().q(
        """SELECT m.*, im.principal FROM investigador_msc im JOIN msc m ON m.codigo = im.codigo
           WHERE im.usuario_id = ? ORDER BY im.principal DESC, im.orden, m.codigo""", [uid])


def agregar_area(uid: int, codigo: str) -> str | None:
    """Agrega un área; devuelve un mensaje de error o None si se agregó."""
    actuales = [a["codigo"] for a in areas(uid)]
    if codigo in actuales:
        return "Esa área ya está en su perfil."
    if len(actuales) >= MAX_AREAS:
        return f"Puede declarar hasta {MAX_AREAS} áreas."
    if not get_db().q("SELECT 1 FROM msc WHERE codigo = ?", [codigo]):
        return "Código MSC inexistente."
    get_db().t.investigador_msc.insert(usuario_id=uid, codigo=codigo,
                                       principal=int(not actuales), orden=len(actuales))
    return None


def quitar_area(uid: int, codigo: str):
    db = get_db()
    era_principal = db.q("SELECT principal FROM investigador_msc WHERE usuario_id = ? AND codigo = ?",
                         [uid, codigo])
    db.execute("DELETE FROM investigador_msc WHERE usuario_id = ? AND codigo = ?", [uid, codigo])
    if era_principal and era_principal[0]["principal"]:
        # La siguiente en orden pasa a ser la principal.
        db.execute("""UPDATE investigador_msc SET principal = 1 WHERE usuario_id = ? AND codigo =
                      (SELECT codigo FROM investigador_msc WHERE usuario_id = ? ORDER BY orden LIMIT 1)""",
                   [uid, uid])


def marcar_principal(uid: int, codigo: str):
    db = get_db()
    if not db.q("SELECT 1 FROM investigador_msc WHERE usuario_id = ? AND codigo = ?", [uid, codigo]):
        return
    db.execute("UPDATE investigador_msc SET principal = 0 WHERE usuario_id = ?", [uid])
    db.execute("UPDATE investigador_msc SET principal = 1 WHERE usuario_id = ? AND codigo = ?",
               [uid, codigo])


# --- Completitud -------------------------------------------------------------

def completitud(perfil: dict, n_areas: int) -> tuple[int, list[str]]:
    """Porcentaje de perfil completo y lista de lo que falta."""
    chequeos = [
        (bool(perfil["grado"]), "grado académico"),
        (bool(perfil["cargo"]), "cargo"),
        (bool(perfil["unidad"]), "unidad o grupo"),
        (bool(perfil["orcid"]), "ORCID"),
        (bool(perfil["mr_id"] or perfil["zbmath_id"]), "MathSciNet o zbMATH"),
        (n_areas > 0, "áreas MSC"),
        (bool(perfil["bio"]), "resumen de investigación"),
        (bool(perfil["foto"]), "foto"),
    ]
    faltan = [nombre for ok, nombre in chequeos if not ok]
    return round(100 * (len(chequeos) - len(faltan)) / len(chequeos)), faltan


# --- Directorio --------------------------------------------------------------

def directorio(texto: str = "", solo_publicos: bool = False) -> list[dict]:
    """Investigadores activos; filtra por nombre, cargo, unidad o área MSC (código o texto)."""
    texto = texto.strip()
    patron = f"%{sin_tildes(texto)}%"
    filas = get_db().q(
        """SELECT u.id, u.nombres, u.apellidos, i.cargo, i.unidad, i.foto,
                  (SELECT m.codigo || char(31) || m.texto FROM investigador_msc im
                     JOIN msc m ON m.codigo = im.codigo
                    WHERE im.usuario_id = u.id AND im.principal = 1) AS area_principal
           FROM usuario u JOIN investigador i ON i.usuario_id = u.id
           WHERE u.activo = 1 AND (:pub = 0 OR i.perfil_publico = 1) AND (
                 :t = '' OR sin_tildes(u.nombres || ' ' || u.apellidos) LIKE :p
                 OR sin_tildes(i.cargo) LIKE :p OR sin_tildes(i.unidad) LIKE :p
                 OR EXISTS (SELECT 1 FROM investigador_msc im JOIN msc m ON m.codigo = im.codigo
                             WHERE im.usuario_id = u.id
                               AND (m.codigo LIKE :c OR m.texto_plano LIKE :p)))
           ORDER BY sin_tildes(u.apellidos), sin_tildes(u.nombres)""",
        {"t": texto, "p": patron, "c": texto.replace("x", "_").replace("X", "_") + "%",
         "pub": int(solo_publicos)})
    for f in filas:
        codigo, _, texto_area = (f.pop("area_principal") or "").partition(chr(31))
        f["area"] = {"codigo": codigo, "texto": texto_area} if codigo else None
    return filas
