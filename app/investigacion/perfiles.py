"""Acceso a datos del perfil del investigador y sus áreas MSC."""
from app.comun import academicos, adscripcion, vinculos
from app.comun.db import AHORA, IGUAL_A, get_db, sin_tildes

MAX_AREAS = 10
LARGO_BIO = 3000

# Categoría del vínculo (dependencia única con la Carrera; definida en app.comun.vinculos; None = sin categoría).
CATEGORIAS = vinculos.CATEGORIAS
# Quiénes pueden proponer proyectos institucionales y ser sus responsables; los interinos pueden
# además ser co-responsables.
CATEGORIAS_RESPONSABLES = ("titular", "contratado")
CATEGORIAS_CO_RESPONSABLES = ("titular", "contratado", "interino")

def obtener(uid: int) -> dict | None:
    """Usuario + investigador en un solo dict, con el cargo y la unidad o grupo calculados
    (app.comun.adscripcion). None si la cuenta no es de investigador."""
    filas = get_db().q(
        f"""SELECT u.id, u.email, u.nombres, u.apellidos, u.activo, i.*,
                   {vinculos.sql_categoria_vigente('u')} AS categoria, {academicos.sql_grado_principal('u')} AS grado
            FROM usuario u JOIN investigador i ON i.usuario_id = u.id WHERE u.id = ?""", [uid])
    return adscripcion.completar(filas[0]) if filas else None


def actualizar_datos(uid: int, *, nombres, apellidos):
    get_db().t.usuario.update(id=uid, nombres=nombres, apellidos=apellidos)


def actualizar_campos(uid: int, **campos):
    asignaciones = ", ".join(f"{c} = :{c}" for c in campos)
    get_db().execute(
        f"UPDATE investigador SET {asignaciones}, actualizado_en = {AHORA} "
        "WHERE usuario_id = :uid", {**campos, "uid": uid})


categoria_texto = vinculos.categoria_texto


cambiar_categoria = vinculos.corregir_categoria_vigente


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
        (bool(perfil["orcid"]), "ORCID"),
        (bool(perfil["mr_id"] or perfil["zbmath_id"]), "MathSciNet o zbMATH"),
        (n_areas > 0, "áreas MSC"),
        (bool(perfil["bio"]), "resumen de investigación"),
        (bool(perfil["foto"]), "foto"),
    ]
    faltan = [nombre for ok, nombre in chequeos if not ok]
    return round(100 * (len(chequeos) - len(faltan)) / len(chequeos)), faltan


# --- Directorio --------------------------------------------------------------

def directorio(texto: str = "", solo_publicos: bool = False, categoria: str = "") -> list[dict]:
    """Investigadores activos; filtra por nombre, cargo, unidad o grupo, o área MSC (código o
    texto) y, si se indica, por categoría ('sin' = sin categoría). El cargo y la unidad se calculan
    (app.comun.adscripcion), así que se filtran aquí y no en SQL."""
    texto = texto.strip()
    patron = f"%{sin_tildes(texto)}%"
    filas = get_db().q(
        f"""SELECT * FROM (
               SELECT u.id, u.nombres, u.apellidos, i.foto,
                      (:t = '' OR sin_tildes(u.nombres || ' ' || u.apellidos) LIKE :p
                       OR EXISTS (SELECT 1 FROM investigador_msc im JOIN msc m ON m.codigo = im.codigo
                                   WHERE im.usuario_id = u.id
                                     AND (m.codigo LIKE :c OR m.texto_plano LIKE :p))) AS coincide,
                      {vinculos.sql_categoria_vigente('u')} AS categoria,
                      (SELECT m.codigo || char(31) || m.texto FROM investigador_msc im
                         JOIN msc m ON m.codigo = im.codigo
                        WHERE im.usuario_id = u.id AND im.principal = 1) AS area_principal
               FROM usuario u JOIN investigador i ON i.usuario_id = u.id
               WHERE u.activo = 1 AND (:pub = 0 OR i.perfil_publico = 1))
           WHERE :cat = '' OR categoria {IGUAL_A} :cat OR (:cat = 'sin' AND categoria IS NULL)
           ORDER BY sin_tildes(apellidos), sin_tildes(nombres)""",
        {"t": texto, "p": patron, "c": texto.replace("x", "_").replace("X", "_") + "%",
         "pub": int(solo_publicos), "cat": categoria})
    res = []
    buscado = sin_tildes(texto)
    for f in filas:
        adscripcion.completar(f)
        if not (f.pop("coincide") or buscado in sin_tildes(f["cargo"] or "") or buscado in sin_tildes(f["unidad"])):
            continue
        codigo, _, texto_area = (f.pop("area_principal") or "").partition(chr(31))
        f["area"] = {"codigo": codigo, "texto": texto_area} if codigo else None
        res.append(f)
    return res
