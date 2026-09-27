"""Proyectos: datos, participantes, permisos y vínculos con actividades y productos.

Tipos:
  - Individual: lo registra cualquier investigador(a), que queda como responsable; no requiere
    aprobación.
  - Institucional: nace de una propuesta que decide la administración (etapa C del plan).
La administración ve todos los proyectos, pero no los gestiona: solo reasigna al responsable
(p. ej., si alguien deja el instituto).

Flujo de vínculos (tablas actividad_proyecto y producto_proyecto):
  - Un participante vigente con cuenta *propone* un registro suyo → 'pendiente'.
    Si quien lo vincula es responsable del proyecto, queda 'aprobado' de inmediato.
  - Un responsable (o co-responsable, o el admin) *aprueba* o *rechaza* (con comentario).
  - Quien propuso puede retirar una propuesta pendiente o rechazada, o volver a proponer
    una rechazada (vuelve a 'pendiente'). Lo aprobado solo lo desvincula un responsable.
  - Las fichas e informes del proyecto consideran solo lo 'aprobado'.
"""
from datetime import date

from app.investigacion import avisos
from app import personas
from app.db import get_db, sin_tildes

TIPOS = {"individual": "Individual", "institucional": "Institucional"}
ESTADOS = {"formulacion": "En formulación", "vigente": "Vigente", "finalizado": "Finalizado"}
ROLES = {"responsable": "Responsable", "co_responsable": "Co-responsable",
         "co_investigador": "Co-investigador(a)", "postdoc": "Postdoctorado",
         "tesista": "Tesista", "colaborador": "Colaborador(a)"}
ROLES_RESPONSABLES = ("responsable", "co_responsable")
ESTADOS_VINCULO = {"pendiente": "Pendiente", "aprobado": "Aprobado", "rechazado": "Rechazado"}
# tipo de registro → (tabla de vínculo, columna del registro)
TABLAS = {"actividad": ("actividad_proyecto", "actividad_id"),
          "producto": ("producto_proyecto", "producto_id")}


def _hoy():
    return date.today().isoformat()


# --- Proyecto ----------------------------------------------------------------------------------

def obtener(pid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM proyecto WHERE id = ?", [pid])
    return filas[0] if filas else None


def validar(d: dict) -> list[str]:
    errores = []
    if not d.get("nombre"):
        errores.append("El nombre del proyecto es obligatorio.")
    if d.get("estado") not in ESTADOS:
        errores.append("Estado no válido.")
    if d.get("ambito") not in (None, "", *AMBITOS):
        errores.append("Ámbito no válido.")
    elif "ambito" in d:
        d["ambito"] = d["ambito"] or None
    try:
        ini = date.fromisoformat(d["fecha_inicio"]) if d.get("fecha_inicio") else None
        fin = date.fromisoformat(d["fecha_fin"]) if d.get("fecha_fin") else None
        if ini and fin and fin < ini:
            errores.append("La fecha de término no puede ser anterior a la de inicio.")
    except ValueError:
        errores.append("Fechas no válidas.")
    if d.get("monto") not in (None, ""):
        monto = str(d["monto"]).replace(".", "").replace(",", "").replace(" ", "")
        if not monto.isdigit():
            errores.append("El monto debe ser un número entero (sin decimales).")
        else:
            d["monto"] = int(monto)
    else:
        d["monto"] = None
    if d.get("codigo") and get_db().q("SELECT 1 FROM proyecto WHERE codigo = ? AND id IS NOT ?",
                                      [d["codigo"], d.get("id")]):
        errores.append("Ya existe un proyecto con ese código.")
    return errores


def crear(d: dict, responsable_id: int, creado_por: int, tipo: str = "individual") -> int:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de proyecto no válido: {tipo}")
    from app import config
    db = get_db()
    with db.conn:
        pid = db.t.proyecto.insert(**{"moneda": config.MONEDA, **d}, tipo=tipo, creado_por=creado_por)["id"]
        db.t.proyecto_participante.insert(proyecto_id=pid, investigador_id=responsable_id,
                                          rol="responsable", fecha_desde=d.get("fecha_inicio"))
    return pid


def actualizar(pid: int, d: dict):
    db = get_db()
    db.t.proyecto.update(id=pid, **d)
    db.execute("UPDATE proyecto SET actualizado_en = datetime('now') WHERE id = ?", [pid])


# --- Objetivos específicos -------------------------------------------------------------------------

def objetivos(pid: int) -> list[dict]:
    return get_db().q("SELECT * FROM proyecto_objetivo WHERE proyecto_id = ? ORDER BY orden, id", [pid])


def agregar_objetivo(pid: int, texto: str):
    orden = get_db().q("SELECT COALESCE(MAX(orden), 0) + 1 AS o FROM proyecto_objetivo "
                       "WHERE proyecto_id = ?", [pid])[0]["o"]
    get_db().t.proyecto_objetivo.insert(proyecto_id=pid, orden=orden, texto=texto.strip())


def quitar_objetivo(pid: int, oid: int):
    get_db().execute("DELETE FROM proyecto_objetivo WHERE id = ? AND proyecto_id = ?", [oid, pid])


# --- Participantes -----------------------------------------------------------------------------------

def participantes(pid: int, solo_vigentes=False) -> list[dict]:
    filtro = " AND (fecha_hasta IS NULL OR fecha_hasta >= date('now', 'localtime'))" if solo_vigentes else ""
    filas = get_db().q(f"SELECT * FROM proyecto_participante WHERE proyecto_id = ?{filtro}", [pid])
    orden = list(ROLES)
    res = []
    for f in filas:
        p = personas.por_ref(personas.ref(f["investigador_id"], f["externo_id"]))
        if p:
            vigente = not f["fecha_hasta"] or f["fecha_hasta"] >= _hoy()
            res.append({**p, "participante_id": f["id"], "rol": f["rol"], "vigente": vigente,
                        "fecha_desde": f["fecha_desde"], "fecha_hasta": f["fecha_hasta"]})
    return sorted(res, key=lambda p: (not p["vigente"], orden.index(p["rol"]), sin_tildes(p["apellidos"])))


def participante(pid: int, part_id: int) -> dict | None:
    filas = get_db().q("SELECT * FROM proyecto_participante WHERE id = ? AND proyecto_id = ?",
                       [part_id, pid])
    return filas[0] if filas else None


def rol_de(pid: int, uid: int) -> str | None:
    """Rol vigente del investigador en el proyecto (None si no participa o ya no está)."""
    filas = get_db().q("""SELECT rol FROM proyecto_participante WHERE proyecto_id = ?
                          AND investigador_id = ? AND (fecha_hasta IS NULL OR fecha_hasta >= date('now', 'localtime'))""",
                       [pid, uid])
    return filas[0]["rol"] if filas else None


def _n_responsables(pid: int, excluir: int | None = None) -> int:
    return get_db().q("""SELECT COUNT(*) n FROM proyecto_participante WHERE proyecto_id = ?
                         AND rol = 'responsable' AND (fecha_hasta IS NULL OR fecha_hasta >= date('now', 'localtime'))
                         AND id IS NOT ?""", [pid, excluir])[0]["n"]


def error_categoria(pid: int, uid: int | None, rol: str) -> str | None:
    """En proyectos institucionales: responsables titulares o contratados; co-responsables,
    además, interinos."""
    from app.investigacion import perfiles
    proyecto = obtener(pid)
    if not proyecto or proyecto["tipo"] != "institucional" or rol not in ROLES_RESPONSABLES or not uid:
        return None
    cat = (perfiles.obtener(uid) or {}).get("categoria")
    if rol == "responsable" and cat not in perfiles.CATEGORIAS_RESPONSABLES:
        return "En un proyecto institucional, el responsable debe ser titular o contratado(a)."
    if rol == "co_responsable" and cat not in perfiles.CATEGORIAS_CO_RESPONSABLES:
        return "En un proyecto institucional, los co-responsables deben ser titulares, contratados o interinos."
    return None


def agregar_participante(pid: int, ref: str, rol: str, es_admin: bool) -> str | None:
    """Devuelve un mensaje de error o None si se agregó."""
    if rol not in ROLES:
        return "Rol no válido."
    if rol == "responsable" and not es_admin:
        return "Solo la administración puede asignar responsables."
    if not personas.parsear_ref(ref) or not personas.por_ref(ref):
        return "Persona no válida."
    cols = personas.columnas(ref)
    col, valor = ("investigador_id", cols["investigador_id"]) if cols["investigador_id"] \
        else ("externo_id", cols["externo_id"])
    if get_db().q(f"SELECT 1 FROM proyecto_participante WHERE proyecto_id = ? AND {col} = ?",
                  [pid, valor]):
        return "Esa persona ya participa en el proyecto."
    if rol in ROLES_RESPONSABLES and cols["externo_id"]:
        return "Los responsables deben tener cuenta en el portal."
    if error := error_categoria(pid, cols["investigador_id"], rol):
        return error
    get_db().t.proyecto_participante.insert(proyecto_id=pid, rol=rol, fecha_desde=_hoy(), **cols)
    return None


def cambiar_rol(pid: int, part_id: int, rol: str, es_admin: bool) -> str | None:
    p = participante(pid, part_id)
    if not p or rol not in ROLES:
        return "Datos no válidos."
    if (rol == "responsable" or p["rol"] == "responsable") and not es_admin:
        return "Solo la administración puede asignar o quitar responsables."
    if p["rol"] == "responsable" and rol != "responsable" and _n_responsables(pid, part_id) == 0:
        return "El proyecto debe tener al menos un responsable. Asigne otro antes."
    if rol in ROLES_RESPONSABLES and p["externo_id"]:
        return "Los responsables deben tener cuenta en el portal."
    if error := error_categoria(pid, p["investigador_id"], rol):
        return error
    get_db().t.proyecto_participante.update(id=part_id, rol=rol)
    return None


def dar_de_baja(pid: int, part_id: int, es_admin: bool) -> str | None:
    """Marca la fecha de término. Sus registros ya aprobados siguen en el proyecto."""
    p = participante(pid, part_id)
    if not p:
        return "Participante no válido."
    if p["rol"] == "responsable" and not es_admin:
        return "Solo la administración puede dar de baja a un responsable."
    if p["rol"] == "responsable" and _n_responsables(pid, part_id) == 0:
        return "El proyecto debe tener al menos un responsable. Asigne otro antes."
    get_db().t.proyecto_participante.update(id=part_id, fecha_hasta=_hoy())
    return None


def reasignar_responsable(pid: int, nuevo_uid: int, anterior: str) -> str | None:
    """Solo la administración. El nuevo responsable reemplaza a los actuales, que pasan a
    co-investigadores (`anterior='co_investigador'`) o dejan el proyecto (`anterior='baja'`).
    Sus registros ya aprobados siguen en el proyecto."""
    from app import usuarios
    u = usuarios.con_perfil(nuevo_uid)
    if not u or not u["es_investigador"] or not u["activo"]:
        return "El responsable debe ser un investigador(a) con cuenta activa."
    if anterior not in ("co_investigador", "baja"):
        return "Indique qué pasa con el responsable anterior."
    if error := error_categoria(pid, nuevo_uid, "responsable"):
        return error
    db = get_db()
    actuales = [r for r in responsables(pid) if r["id"] != nuevo_uid]
    if not actuales and rol_de(pid, nuevo_uid) == "responsable":
        return "Esa persona ya es la responsable del proyecto."
    with db.conn:
        existente = db.q("SELECT id FROM proyecto_participante WHERE proyecto_id = ? AND investigador_id = ?",
                         [pid, nuevo_uid])
        if existente:
            db.execute("UPDATE proyecto_participante SET rol = 'responsable', fecha_hasta = NULL WHERE id = ?",
                       [existente[0]["id"]])
        else:
            db.t.proyecto_participante.insert(proyecto_id=pid, investigador_id=nuevo_uid,
                                              rol="responsable", fecha_desde=_hoy())
        for r in actuales:
            # Deja de ser responsable de inmediato. Con «baja», además, hoy es su último día en el
            # proyecto (como en dar_de_baja); el cambio queda en la auditoría.
            db.execute("UPDATE proyecto_participante SET rol = 'co_investigador', fecha_hasta = ? WHERE id = ?",
                       [_hoy() if anterior == "baja" else None, r["participante_id"]])
    return None


def reincorporar(pid: int, part_id: int):
    if participante(pid, part_id):
        get_db().execute("UPDATE proyecto_participante SET fecha_hasta = NULL WHERE id = ?", [part_id])


# --- Permisos ----------------------------------------------------------------------------------------------

def puede_ver(pid: int, usuario: dict) -> bool:
    """Participantes (también los que ya dejaron el proyecto) y administración."""
    return usuario["es_admin"] or bool(get_db().q(
        "SELECT 1 FROM proyecto_participante WHERE proyecto_id = ? AND investigador_id = ?",
        [pid, usuario["id"]]))


def puede_gestionar(pid: int, usuario: dict) -> bool:
    """Editar datos, participantes y revisar propuestas: solo responsables vigentes. La
    administración no gestiona proyectos (ver `puede_reasignar`)."""
    return rol_de(pid, usuario["id"]) in ROLES_RESPONSABLES


def puede_reasignar(usuario: dict) -> bool:
    """Reasignar al responsable de un proyecto: solo la administración."""
    return bool(usuario["es_admin"])


def puede_crear(usuario: dict) -> bool:
    """Proyecto individual: cualquier investigador(a) con cuenta activa."""
    return bool(usuario.get("es_investigador"))


# --- Listados de proyectos -----------------------------------------------------------------------------------

def de_investigador(uid: int) -> list[dict]:
    """Proyectos en que participa (vigentes primero), con su rol y pendientes por revisar."""
    return get_db().q(
        """SELECT p.*, pp.rol AS mi_rol,
                  (pp.fecha_hasta IS NULL OR pp.fecha_hasta >= date('now', 'localtime')) AS vigente,
                  (SELECT COUNT(*) FROM proyecto_participante x WHERE x.proyecto_id = p.id
                     AND (x.fecha_hasta IS NULL OR x.fecha_hasta >= date('now', 'localtime'))) AS n_part
           FROM proyecto p JOIN proyecto_participante pp ON pp.proyecto_id = p.id
           WHERE pp.investigador_id = ?
           ORDER BY p.estado = 'finalizado', p.fecha_inicio DESC, p.nombre""", [uid])


def todos(texto: str = "", tipo: str = "") -> list[dict]:
    patron = f"%{sin_tildes(texto.strip())}%"
    return get_db().q(
        """SELECT p.*, (SELECT COUNT(*) FROM proyecto_participante x WHERE x.proyecto_id = p.id
                         AND (x.fecha_hasta IS NULL OR x.fecha_hasta >= date('now', 'localtime'))) AS n_part
           FROM proyecto p WHERE (sin_tildes(p.nombre) LIKE :p OR sin_tildes(p.codigo) LIKE :p)
             AND (:t = '' OR p.tipo = :t)
           ORDER BY p.estado = 'finalizado', p.fecha_inicio DESC, p.nombre""", {"p": patron, "t": tipo})


def responsables(pid: int) -> list[dict]:
    return [p for p in participantes(pid, solo_vigentes=True) if p["rol"] == "responsable"]


def para_proponer(uid: int) -> list[dict]:
    """Proyectos no finalizados en que el investigador es participante vigente."""
    return get_db().q(
        """SELECT p.*, pp.rol AS mi_rol FROM proyecto p
           JOIN proyecto_participante pp ON pp.proyecto_id = p.id
           WHERE pp.investigador_id = ? AND p.estado != 'finalizado'
             AND (pp.fecha_hasta IS NULL OR pp.fecha_hasta >= date('now', 'localtime'))
           ORDER BY p.nombre""", [uid])


# --- Vínculos ---------------------------------------------------------------------------------------------------

def ligados_a_institucionales(tipo: str, desde: str, hasta: str) -> set[int]:
    """Ids de actividades o productos aprobados en algún proyecto institucional (no en formulación)
    cuya vigencia se cruza con [desde, hasta] (fechas ISO)."""
    tabla, col = TABLAS[tipo]
    return {r[col] for r in get_db().q(
        f"""SELECT DISTINCT v.{col} FROM {tabla} v JOIN proyecto p ON p.id = v.proyecto_id
            WHERE v.estado = 'aprobado' AND p.tipo = 'institucional' AND p.estado != 'formulacion'
              AND (p.fecha_inicio IS NULL OR p.fecha_inicio <= :h)
              AND (p.fecha_fin IS NULL OR p.fecha_fin >= :d)""", {"d": desde, "h": hasta})}


def vinculos_de(tipo: str, registro_id: int) -> list[dict]:
    """Proyectos a los que está vinculado (o propuesto) un registro."""
    tabla, col = TABLAS[tipo]
    return get_db().q(
        f"""SELECT v.*, p.nombre AS proyecto, p.codigo FROM {tabla} v JOIN proyecto p ON p.id = v.proyecto_id
            WHERE v.{col} = ? ORDER BY p.nombre""", [registro_id])


def vinculo(tipo: str, registro_id: int, pid: int) -> dict | None:
    tabla, col = TABLAS[tipo]
    filas = get_db().q(f"SELECT * FROM {tabla} WHERE {col} = ? AND proyecto_id = ?", [registro_id, pid])
    return filas[0] if filas else None


def sincronizar(tipo: str, registro_id: int, marcados: list[int], usuario: dict) -> list[str]:
    """Aplica las casillas «vincular a proyectos» de un formulario.

    - Marcado y sin vínculo: se propone (o se aprueba directo si quien lo hace es responsable).
    - Marcado y rechazado: se vuelve a proponer.
    - Desmarcado: se retira si estaba pendiente o rechazado. Lo aprobado no se toca aquí:
      solo un responsable lo desvincula desde el proyecto.
    Devuelve avisos para el usuario (proyectos en que no puede proponer, etc.).
    """
    tabla, col = TABLAS[tipo]
    db = get_db()
    mensajes = []
    permitidos = {p["id"] for p in para_proponer(usuario["id"])}
    actuales = {v["proyecto_id"]: v for v in vinculos_de(tipo, registro_id)}
    for pid in set(marcados):
        v = actuales.get(pid)
        if v and v["estado"] != "rechazado":
            continue
        if pid not in permitidos:
            mensajes.append("Solo puede proponer a proyectos en que participa y que no han finalizado.")
            continue
        directo = rol_de(pid, usuario["id"]) in ROLES_RESPONSABLES
        estado = "aprobado" if directo else "pendiente"
        revision = dict(revisado_por=usuario["id"], revisado_en=_ahora()) if directo else \
            dict(revisado_por=None, revisado_en=None)
        if v:
            db.execute(f"""UPDATE {tabla} SET estado = ?, comentario = NULL, propuesto_por = ?,
                           propuesto_en = datetime('now'), revisado_por = ?, revisado_en = ?
                           WHERE {col} = ? AND proyecto_id = ?""",
                       [estado, usuario["id"], revision["revisado_por"], revision["revisado_en"],
                        registro_id, pid])
        else:
            db.t[tabla].insert(**{col: registro_id}, proyecto_id=pid, estado=estado,
                               propuesto_por=usuario["id"], **revision)
        if estado == "pendiente":
            avisos.nueva_propuesta(tipo, registro_id, pid, usuario["id"])
    for pid, v in actuales.items():
        if pid not in marcados and v["estado"] in ("pendiente", "rechazado"):
            db.execute(f"DELETE FROM {tabla} WHERE {col} = ? AND proyecto_id = ?", [registro_id, pid])
    return list(dict.fromkeys(mensajes))


def _ahora():
    return get_db().q("SELECT datetime('now') AS t")[0]["t"]


def marcar_agradece(producto_id: int, pid: int, valor: int | None):
    """¿La publicación agradece al proyecto? (1 / 0 / None = sin declarar)."""
    get_db().execute("UPDATE producto_proyecto SET agradece = ? WHERE producto_id = ? AND proyecto_id = ?",
                     [valor, producto_id, pid])


def aprobar(tipo: str, registro_id: int, pid: int, revisor: int,
            responsable_participante_id: int | None = None) -> str | None:
    tabla, col = TABLAS[tipo]
    v = vinculo(tipo, registro_id, pid)
    if not v or v["estado"] != "pendiente":
        return "La propuesta ya no está pendiente."
    extra = ""
    params = [revisor, registro_id, pid]
    if tipo == "actividad":
        if responsable_participante_id and not participante(pid, responsable_participante_id):
            return "El responsable de la actividad debe ser participante del proyecto."
        extra = ", responsable_participante_id = ?"
        params.insert(1, responsable_participante_id)
    get_db().execute(f"""UPDATE {tabla} SET estado = 'aprobado', revisado_por = ?{extra},
                         revisado_en = datetime('now'), comentario = NULL
                         WHERE {col} = ? AND proyecto_id = ?""", params)
    avisos.revision(tipo, registro_id, pid, "aprobado", revisor)
    return None


def rechazar(tipo: str, registro_id: int, pid: int, revisor: int, comentario: str) -> str | None:
    tabla, col = TABLAS[tipo]
    if not comentario.strip():
        return "Indique el motivo del rechazo: quien lo propuso lo verá para corregir."
    v = vinculo(tipo, registro_id, pid)
    if not v or v["estado"] != "pendiente":
        return "La propuesta ya no está pendiente."
    get_db().execute(f"""UPDATE {tabla} SET estado = 'rechazado', revisado_por = ?,
                         revisado_en = datetime('now'), comentario = ?
                         WHERE {col} = ? AND proyecto_id = ?""",
                     [revisor, comentario.strip(), registro_id, pid])
    avisos.revision(tipo, registro_id, pid, "rechazado", revisor, comentario.strip())
    return None


def desvincular(tipo: str, registro_id: int, pid: int):
    tabla, col = TABLAS[tipo]
    get_db().execute(f"DELETE FROM {tabla} WHERE {col} = ? AND proyecto_id = ?", [registro_id, pid])


def asignar_responsable_actividad(actividad_id: int, pid: int, part_id: int | None) -> str | None:
    if part_id and not participante(pid, part_id):
        return "El responsable de la actividad debe ser participante del proyecto."
    get_db().execute("""UPDATE actividad_proyecto SET responsable_participante_id = ?
                        WHERE actividad_id = ? AND proyecto_id = ?""", [part_id, actividad_id, pid])
    return None


def registros(pid: int, tipo: str, estado: str = "aprobado") -> list[dict]:
    """Vínculos de un proyecto en un estado, con marca de «editado después de aprobado»."""
    tabla, col = TABLAS[tipo]
    entidad = "actividad" if tipo == "actividad" else "producto"
    orden = "e.fecha_inicio DESC" if tipo == "actividad" else "e.anio DESC"
    return get_db().q(
        f"""SELECT v.*, v.{col} AS registro_id, u.nombres || ' ' || u.apellidos AS propuesto_por_nombre,
                   (e.actualizado_en IS NOT NULL AND v.revisado_en IS NOT NULL
                    AND e.actualizado_en > v.revisado_en) AS editado_despues
            FROM {tabla} v JOIN {entidad} e ON e.id = v.{col}
            JOIN usuario u ON u.id = v.propuesto_por
            WHERE v.proyecto_id = ? AND v.estado = ? ORDER BY v.propuesto_en DESC, {orden}""",
        [pid, estado])


def fuera_de_periodo(proyecto: dict, tipo: str, registro: dict) -> bool:
    """True si el registro cae fuera del periodo del proyecto (aviso para quien revisa)."""
    ini, fin = proyecto["fecha_inicio"], proyecto["fecha_fin"]
    if tipo == "actividad":
        desde, hasta = registro["fecha_inicio"], registro["fecha_fin"] or registro["fecha_inicio"]
    else:
        desde, hasta = f"{registro['anio']}-01-01", f"{registro['anio']}-12-31"
    return bool((ini and hasta < ini) or (fin and desde > fin))


def n_pendientes(pid: int) -> int:
    return get_db().q("""SELECT (SELECT COUNT(*) FROM actividad_proyecto WHERE proyecto_id = :p
                                 AND estado = 'pendiente')
                              + (SELECT COUNT(*) FROM producto_proyecto WHERE proyecto_id = :p
                                 AND estado = 'pendiente') AS n""", {"p": pid})[0]["n"]


def n_pendientes_para(usuario: dict) -> int:
    """Propuestas que esta persona debe revisar (en proyectos donde es responsable vigente)."""
    return get_db().q(
        """WITH mios AS (SELECT proyecto_id FROM proyecto_participante WHERE investigador_id = :u
                         AND rol IN ('responsable', 'co_responsable')
                         AND (fecha_hasta IS NULL OR fecha_hasta >= date('now', 'localtime')))
           SELECT (SELECT COUNT(*) FROM actividad_proyecto WHERE estado = 'pendiente'
                     AND proyecto_id IN (SELECT proyecto_id FROM mios))
                + (SELECT COUNT(*) FROM producto_proyecto WHERE estado = 'pendiente'
                     AND proyecto_id IN (SELECT proyecto_id FROM mios)) AS n""",
        {"u": usuario["id"]})[0]["n"]


def mis_propuestas(uid: int) -> list[dict]:
    """Propuestas propias aún no aprobadas (pendientes o rechazadas), para el tablero."""
    return get_db().q(
        """SELECT 'actividad' AS tipo, v.actividad_id AS registro_id, a.titulo AS titulo,
                  v.estado AS estado, v.comentario AS comentario, p.id AS proyecto_id,
                  p.nombre AS proyecto, v.propuesto_en AS propuesto_en
           FROM actividad_proyecto v JOIN actividad a ON a.id = v.actividad_id
           JOIN proyecto p ON p.id = v.proyecto_id
           WHERE v.propuesto_por = :u AND v.estado != 'aprobado'
           UNION ALL
           SELECT 'producto', v.producto_id, pr.titulo, v.estado, v.comentario, p.id, p.nombre,
                  v.propuesto_en
           FROM producto_proyecto v JOIN producto pr ON pr.id = v.producto_id
           JOIN proyecto p ON p.id = v.proyecto_id
           WHERE v.propuesto_por = :u AND v.estado != 'aprobado'
           ORDER BY estado DESC, propuesto_en DESC""", {"u": uid})


# --- Ámbito y contrapartes (internacionalización) ---------------------------------------------------------

AMBITOS = {"nacional": "Nacional", "internacional": "Internacional"}


def contrapartes(pid: int) -> list[dict]:
    return get_db().q("SELECT * FROM proyecto_contraparte WHERE proyecto_id = ? ORDER BY id", [pid])


def agregar_contraparte(pid: int, institucion: str, pais: str | None) -> str | None:
    from app import paises
    institucion = (institucion or "").strip()
    if not institucion:
        return "Indique la institución contraparte."
    pais = paises.normalizar(pais) or paises.desde_texto(institucion)
    get_db().t.proyecto_contraparte.insert(proyecto_id=pid, institucion=institucion[:200], pais=pais)
    return None


def quitar_contraparte(pid: int, cid: int):
    get_db().execute("DELETE FROM proyecto_contraparte WHERE id = ? AND proyecto_id = ?", [cid, pid])


def ambito_efectivo(p: dict) -> str | None:
    """El ámbito declarado; si no se declaró, «internacional» cuando alguna contraparte es de otro
    país y «nacional» cuando todas son del país. None si no hay cómo saberlo."""
    from app import config, paises
    if p.get("ambito"):
        return p["ambito"]
    extranjeras = [paises.es_extranjero(c["pais"], config.PAIS) for c in contrapartes(p["id"])]
    if any(extranjeras):
        return "internacional"
    if extranjeras and all(x is False for x in extranjeras):
        return "nacional"
    return None
