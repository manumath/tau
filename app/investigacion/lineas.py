"""Líneas de investigación institucionales.

Reglas (ver PLAN.md, sección 21):
  - La Dirección del Instituto mantiene el catálogo (`gestionar_catalogos`), agrupado en áreas (PLAN §60). Cada línea rige entre `vigente_desde` (NULL: desde
    antes del portal) y `vigente_hasta` (NULL: sigue vigente). Una línea que deja de regir no se
    borra: se le pone fecha de término y quienes ya la usaban la conservan en su historia. Solo
    se puede eliminar una línea que nadie ha usado (p. ej., creada por error).
  - Una propuesta institucional debe adscribirse al menos a una línea vigente al inicio de su
    periodo; al aceptarse, sus líneas pasan al proyecto.
  - Los proyectos individuales y los investigadores (desde su perfil) se adscriben de forma
    opcional, solo a líneas vigentes hoy. La Dirección del Instituto también puede adscribir o quitar
    proyectos desde la ficha de la línea.
  - Productos y actividades no eligen línea: la heredan de los proyectos en que están aprobados
    (`de_registro`). Sin proyecto aprobado, no tienen línea.
"""
from datetime import date

from app.comun.db import AHORA, DISTINTO_DE, get_db, transaccion

LARGO_NOMBRE = 200
# Orden del catálogo: por área (las líneas sin área al final) y, dentro de ella, por el orden de la línea.
_AREA = "(SELECT orden FROM area_investigacion WHERE id = l.area_id)"
ORDEN = f"{_AREA} IS NULL, {_AREA}, l.orden, l.nombre"
LARGO_DESCRIPCION = 2000


def hoy() -> str:
    return date.today().isoformat()


def vigente(linea: dict, fecha: str | None = None) -> bool:
    f = fecha or hoy()
    return ((linea["vigente_desde"] is None or linea["vigente_desde"] <= f)
            and (linea["vigente_hasta"] is None or linea["vigente_hasta"] >= f))


def estado(linea: dict, fecha: str | None = None) -> str:
    """'vigente', 'proxima' (aún no rige) o 'cerrada'."""
    f = fecha or hoy()
    if linea["vigente_desde"] and linea["vigente_desde"] > f:
        return "proxima"
    return "vigente" if vigente(linea, f) else "cerrada"


# --- Consultas ---------------------------------------------------------------------------------------

def obtener(lid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM linea_investigacion WHERE id = ?", [lid])
    return filas[0] if filas else None


def todas() -> list[dict]:
    """Catálogo completo (por área y orden) con cuántos proyectos, propuestas e investigadores usan cada línea."""
    return get_db().q(
        f"""SELECT l.*, a.nombre AS area,
                  (SELECT COUNT(*) FROM proyecto_linea WHERE linea_id = l.id) AS n_proyectos,
                  (SELECT COUNT(*) FROM propuesta_linea WHERE linea_id = l.id) AS n_propuestas,
                  (SELECT COUNT(*) FROM investigador_linea x JOIN usuario u ON u.id = x.usuario_id
                    WHERE x.linea_id = l.id AND u.activo = 1) AS n_investigadores
           FROM linea_investigacion l LEFT JOIN area_investigacion a ON a.id = l.area_id
           ORDER BY {ORDEN}""")


def vigentes(fecha: str | None = None) -> list[dict]:
    f = fecha or hoy()
    return get_db().q(
        f"""SELECT l.* FROM linea_investigacion l WHERE (l.vigente_desde IS NULL OR l.vigente_desde <= :f)
           AND (l.vigente_hasta IS NULL OR l.vigente_hasta >= :f) ORDER BY {ORDEN}""", {"f": f})


def _de(tabla: str, columna: str, valor: int) -> list[dict]:
    return get_db().q(f"""SELECT l.* FROM {tabla} x JOIN linea_investigacion l ON l.id = x.linea_id
                          WHERE x.{columna} = ? ORDER BY {ORDEN}""", [valor])


def de_proyecto(pid: int) -> list[dict]:
    return _de("proyecto_linea", "proyecto_id", pid)


def de_propuesta(prop_id: int) -> list[dict]:
    return _de("propuesta_linea", "propuesta_id", prop_id)


def de_investigador(uid: int) -> list[dict]:
    return _de("investigador_linea", "usuario_id", uid)


def de_registro(tipo: str, registro_id: int) -> list[dict]:
    """Líneas de un producto o una actividad: las de los proyectos en que está aprobado y, en los productos, las que el
    investigador le asignó directamente (`producto_linea`, PLAN §59)."""
    tabla, columna = {"producto": ("producto_proyecto", "producto_id"),
                      "actividad": ("actividad_proyecto", "actividad_id")}[tipo]
    directas = " OR l.id IN (SELECT linea_id FROM producto_linea WHERE producto_id = :r)" if tipo == "producto" else ""
    return get_db().q(
        f"""SELECT l.* FROM linea_investigacion l
            WHERE l.id IN (SELECT pl.linea_id FROM {tabla} v JOIN proyecto_linea pl ON pl.proyecto_id = v.proyecto_id
                           WHERE v.{columna} = :r AND v.estado = 'aprobado'){directas}
            ORDER BY {ORDEN}""", {"r": registro_id})


def directas_de_producto(pid: int) -> list[dict]:
    """Las líneas asignadas directamente a un producto (no las heredadas de sus proyectos)."""
    return get_db().q(f"""SELECT l.* FROM producto_linea x JOIN linea_investigacion l ON l.id = x.linea_id
                          WHERE x.producto_id = ? ORDER BY {ORDEN}""", [pid])


def quitar_de_producto(pid: int, lid: int):
    get_db().execute("DELETE FROM producto_linea WHERE producto_id = ? AND linea_id = ?", [pid, lid])


def investigadores(lid: int) -> list[dict]:
    return get_db().q(
        """SELECT u.id, u.nombres, u.apellidos FROM investigador_linea x JOIN usuario u ON u.id = x.usuario_id
           WHERE x.linea_id = ? AND u.activo = 1 ORDER BY u.apellidos, u.nombres""", [lid])


def proyectos(lid: int) -> list[dict]:
    return get_db().q(
        """SELECT p.id, p.nombre, p.tipo, p.estado FROM proyecto_linea x JOIN proyecto p ON p.id = x.proyecto_id
           WHERE x.linea_id = ? ORDER BY p.estado != 'vigente', p.nombre""", [lid])


def nombres(lineas: list[dict]) -> str:
    return "; ".join(x["nombre"] for x in lineas)


# --- Adscripción -------------------------------------------------------------------------------------

def ids_validos(valores) -> list[int]:
    """Ids enteros sin repetir, en el orden recibido (lo que llega de un formulario)."""
    res = []
    for v in valores or []:
        if str(v).strip().isdigit() and int(v) not in res:
            res.append(int(v))
    return res


def no_vigentes(ids: list[int], fecha: str | None = None) -> list[str]:
    """Nombres de las líneas (entre `ids`) que no rigen en la fecha; «desconocida» si no existe."""
    validas = {x["id"] for x in vigentes(fecha)}
    res = []
    for i in ids:
        if i not in validas:
            linea = obtener(i)
            res.append(linea["nombre"] if linea else f"línea {i} (desconocida)")
    return res


def _reemplazar(tabla: str, columna: str, valor: int, ids: list[int]):
    db = get_db()
    db.execute(f"DELETE FROM {tabla} WHERE {columna} = ?", [valor])
    for i in ids:
        db.execute(f"INSERT INTO {tabla} ({columna}, linea_id) VALUES (?, ?)", [valor, i])


def _adscribir(tabla, columna, valor, ids, actuales) -> str | None:
    """Solo se agregan líneas vigentes hoy; las ya adscritas que dejaron de regir se pueden
    conservar (o quitar), pero no volver a agregar."""
    nuevas = [i for i in ids if i not in {x["id"] for x in actuales}]
    malas = no_vigentes(nuevas)
    if malas:
        return "Solo puede adscribirse a líneas vigentes: " + ", ".join(malas) + "."
    with transaccion():
        _reemplazar(tabla, columna, valor, ids)
    return None


def adscribir_investigador(uid: int, ids: list[int]) -> str | None:
    return _adscribir("investigador_linea", "usuario_id", uid, ids, de_investigador(uid))


def adscribir_proyecto(pid: int, ids: list[int]) -> str | None:
    return _adscribir("proyecto_linea", "proyecto_id", pid, ids, de_proyecto(pid))


def fijar_propuesta(prop_id: int, ids: list[int]):
    """Sin validar: `institucionales.guardar` comprueba la vigencia en el periodo."""
    _reemplazar("propuesta_linea", "propuesta_id", prop_id, ids)


def fijar_proyecto(pid: int, ids: list[int]):
    _reemplazar("proyecto_linea", "proyecto_id", pid, ids)


# --- Catálogo (administración) -------------------------------------------------------------------------

def validar(d: dict, lid: int | None = None) -> tuple[dict, list[str]]:
    d = {k: (v or "").strip() or None for k, v in d.items()}
    errores = []
    if not d.get("nombre"):
        errores.append("Indique el nombre de la línea.")
    elif len(d["nombre"]) > LARGO_NOMBRE:
        errores.append(f"El nombre admite hasta {LARGO_NOMBRE} caracteres.")
    elif get_db().q(f"SELECT 1 FROM linea_investigacion WHERE lower(nombre) = lower(?) AND id {DISTINTO_DE} ?",
                    [d["nombre"], lid]):
        errores.append("Ya existe una línea con ese nombre.")
    if d.get("area_id"):
        if not str(d["area_id"]).isdigit() or not area(int(d["area_id"])):
            errores.append("Elija un área de la lista.")
        else:
            d["area_id"] = int(d["area_id"])
    elif areas():
        errores.append("Elija el área de la línea.")
    if d.get("descripcion") and len(d["descripcion"]) > LARGO_DESCRIPCION:
        errores.append(f"La descripción admite hasta {LARGO_DESCRIPCION} caracteres.")
    for campo in ("vigente_desde", "vigente_hasta"):
        if d.get(campo):
            try:
                d[campo] = date.fromisoformat(d[campo]).isoformat()
            except ValueError:
                errores.append("Indique fechas válidas.")
                d[campo] = None
    if d.get("vigente_desde") and d.get("vigente_hasta") and d["vigente_hasta"] < d["vigente_desde"]:
        errores.append("El término de la vigencia no puede ser anterior a su inicio.")
    return d, errores


def crear(d: dict, uid: int) -> int:
    orden = get_db().q("SELECT COALESCE(MAX(orden), 0) + 1 AS n FROM linea_investigacion")[0]["n"]
    return get_db().t.linea_investigacion.insert(**d, orden=orden, creado_por=uid)["id"]


def actualizar(lid: int, d: dict):
    get_db().execute(f"""UPDATE linea_investigacion SET {', '.join(f'{k} = :{k}' for k in d)},
                         actualizado_en = {AHORA} WHERE id = :id""", {**d, "id": lid})


def cerrar(lid: int, fecha: str) -> str | None:
    """Pone fecha de término a la vigencia (la línea deja de poder elegirse después de esa fecha)."""
    linea = obtener(lid)
    try:
        fecha = date.fromisoformat(fecha).isoformat()
    except ValueError:
        return "Indique una fecha válida."
    if linea["vigente_desde"] and fecha < linea["vigente_desde"]:
        return "La fecha de término no puede ser anterior al inicio de la vigencia."
    actualizar(lid, {"vigente_hasta": fecha})
    return None


def reabrir(lid: int):
    actualizar(lid, {"vigente_hasta": None})


def en_uso(lid: int) -> bool:
    return bool(get_db().q("""SELECT 1 FROM proyecto_linea WHERE linea_id = :l
                              UNION ALL SELECT 1 FROM propuesta_linea WHERE linea_id = :l
                              UNION ALL SELECT 1 FROM investigador_linea WHERE linea_id = :l
                              UNION ALL SELECT 1 FROM producto_linea WHERE linea_id = :l LIMIT 1""",
                           {"l": lid}))


def eliminar(lid: int) -> str | None:
    if en_uso(lid):
        return ("La línea ya se usó en proyectos, propuestas o perfiles: en lugar de eliminarla, "
                "póngale fecha de término.")
    get_db().execute("DELETE FROM linea_investigacion WHERE id = ?", [lid])
    return None


def mover(lid: int, delta: int):
    """Sube (-1) o baja (+1) la línea dentro de su área."""
    linea = obtener(lid)
    if not linea:
        return
    ids = [x["id"] for x in todas() if x["area_id"] == linea["area_id"]]
    i = ids.index(lid)
    j = i + delta
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
    with transaccion():
        for n, x in enumerate(ids, start=1):
            get_db().execute("UPDATE linea_investigacion SET orden = ? WHERE id = ?", [n, x])


# --- Áreas -----------------------------------------------------------------------------------------------

LARGO_AREA = 120


def areas() -> list[dict]:
    """Áreas en su orden, con cuántas líneas tiene cada una."""
    return get_db().q("""SELECT a.*, (SELECT COUNT(*) FROM linea_investigacion WHERE area_id = a.id) AS n_lineas
                         FROM area_investigacion a ORDER BY a.orden, a.nombre""")


def area(aid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM area_investigacion WHERE id = ?", [aid])
    return filas[0] if filas else None


def validar_area(nombre: str, aid: int | None = None) -> tuple[str, list[str]]:
    nombre = (nombre or "").strip()
    if not nombre:
        return nombre, ["Indique el nombre del área."]
    if len(nombre) > LARGO_AREA:
        return nombre, [f"El nombre admite hasta {LARGO_AREA} caracteres."]
    if get_db().q(f"SELECT 1 FROM area_investigacion WHERE lower(nombre) = lower(?) AND id {DISTINTO_DE} ?", [nombre, aid]):
        return nombre, ["Ya existe un área con ese nombre."]
    return nombre, []


def crear_area(nombre: str) -> int:
    orden = get_db().q("SELECT COALESCE(MAX(orden), 0) + 1 AS n FROM area_investigacion")[0]["n"]
    return get_db().t.area_investigacion.insert(nombre=nombre, orden=orden)["id"]


def renombrar_area(aid: int, nombre: str):
    get_db().execute(f"UPDATE area_investigacion SET nombre = ?, actualizado_en = {AHORA} WHERE id = ?", [nombre, aid])


def eliminar_area(aid: int) -> str | None:
    if get_db().q("SELECT 1 FROM linea_investigacion WHERE area_id = ? LIMIT 1", [aid]):
        return "El área tiene líneas: muévalas a otra área antes de eliminarla."
    get_db().execute("DELETE FROM area_investigacion WHERE id = ?", [aid])
    return None


def mover_area(aid: int, delta: int):
    ids = [x["id"] for x in areas()]
    if aid not in ids:
        return
    i, j = ids.index(aid), ids.index(aid) + delta
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
    with transaccion():
        for n, x in enumerate(ids, start=1):
            get_db().execute("UPDATE area_investigacion SET orden = ? WHERE id = ?", [n, x])


# --- Proyectos de una línea (desde la ficha de la línea) ---------------------------------------------------

def proyectos_para_agregar(lid: int) -> list[dict]:
    """Proyectos vigentes que aún no están en la línea."""
    return get_db().q("""SELECT id, nombre, tipo FROM proyecto WHERE estado = 'vigente'
                         AND id NOT IN (SELECT proyecto_id FROM proyecto_linea WHERE linea_id = ?)
                         ORDER BY nombre""", [lid])


def agregar_proyecto(lid: int, pid: int) -> str | None:
    linea = obtener(lid)
    if not linea or not vigente(linea):
        return "Solo se pueden adscribir proyectos a una línea vigente."
    if not any(p["id"] == pid for p in proyectos_para_agregar(lid)):
        return "Elija un proyecto vigente que aún no esté en la línea."
    get_db().execute("INSERT INTO proyecto_linea (proyecto_id, linea_id) VALUES (?, ?)", [pid, lid])
    return None


def quitar_proyecto(lid: int, pid: int):
    get_db().execute("DELETE FROM proyecto_linea WHERE proyecto_id = ? AND linea_id = ?", [pid, lid])
