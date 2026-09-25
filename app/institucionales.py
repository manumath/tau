"""Proyectos institucionales: periodos, convocatorias y propuestas.

Reglas (ver PLAN.md, sección 11):
  - Un periodo va de octubre a septiembre; se identifica por su año de inicio (2026 = oct 2026 –
    sept 2027). La convocatoria de un periodo es, por omisión, todo septiembre de ese año; la
    administración puede cambiar el plazo (tabla `convocatoria`).
  - Proponen titulares y contratados. Quien propone un proyecto nuevo queda como responsable;
    la continuidad la propone un responsable del proyecto.
  - Flujo: borrador → enviada → aceptada | condicional | rechazada. Una propuesta condicional
    vuelve a ser editable y, al reenviarla, queda enviada otra vez. Los borradores se preparan en
    cualquier momento; el primer envío debe hacerse dentro del plazo (los reenvíos tras
    condiciones, no).
  - Vigencia: el proyecto rige mientras una propuesta aceptada cubra la fecha. Si la
    continuidad está enviada o condicional cuando termina el periodo, sigue vigente («en
    renovación») hasta la decisión. Sin continuidad, concluye el 30 de septiembre. Se calcula
    por fechas (`refrescar_vigencias`), sin tareas programadas.
"""
import json
import time
from datetime import date

from app import avisos, perfiles, personas, proyectos
from app.db import get_db

ESTADOS = {"borrador": "Borrador", "enviada": "Enviada", "aceptada": "Aceptada",
           "condicional": "Aceptada con condiciones", "rechazada": "Rechazada", "retirada": "Retirada"}
MODALIDADES = {"nuevo": "Proyecto nuevo", "continuidad": "Continuidad"}
EDITABLES = ("borrador", "condicional")
EN_REVISION = ("enviada", "condicional")
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]
MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                "septiembre", "octubre", "noviembre", "diciembre"]
LARGO_TEXTO = 20000


def hoy() -> date:
    """Punto único para la fecha actual (las pruebas lo reemplazan)."""
    return date.today()


# --- Periodos y convocatorias ------------------------------------------------------------------

def inicio(periodo: int) -> str:
    return f"{periodo}-10-01"


def fin(periodo: int) -> str:
    return f"{periodo + 1}-09-30"


def periodo_texto(periodo: int) -> str:
    return f"{periodo}–{periodo + 1}"


def periodo_largo(periodo: int) -> str:
    return f"octubre de {periodo} a septiembre de {periodo + 1}"


def meses(periodo: int) -> list[tuple[str, str]]:
    """Los 12 meses del periodo: [('2026-10', 'oct 2026'), …, ('2027-09', 'sept 2027')]."""
    res = []
    for i in range(12):
        m, a = (10 + i - 1) % 12 + 1, periodo + (1 if 10 + i > 12 else 0)
        res.append((f"{a}-{m:02d}", f"{MESES[m - 1]} {a}"))
    return res


def mes_texto(valor: str | None) -> str:
    if not valor:
        return "—"
    a, m = valor.split("-")
    return f"{MESES[int(m) - 1]} {a}"


def fecha_texto(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} de {MESES_LARGOS[d.month - 1]} de {d.year}"


def plazo(periodo: int) -> dict:
    """{'abre', 'cierra', 'modificado'} del plazo de presentación de un periodo."""
    fila = get_db().q("SELECT abre, cierra FROM convocatoria WHERE periodo = ?", [periodo])
    if fila:
        return {**fila[0], "modificado": True}
    return {"abre": f"{periodo}-09-01", "cierra": f"{periodo}-09-30", "modificado": False}


def abierta(periodo: int) -> bool:
    p = plazo(periodo)
    return p["abre"] <= hoy().isoformat() <= p["cierra"]


def periodo_abierto() -> int | None:
    """Periodo cuya convocatoria está abierta hoy (el más próximo, si hubiera dos)."""
    for periodo in (hoy().year - 1, hoy().year, hoy().year + 1):
        if abierta(periodo):
            return periodo
    return None


def periodo_objetivo() -> int:
    """Periodo al que apunta una propuesta nueva: el de la convocatoria abierta o el siguiente."""
    abierto = periodo_abierto()
    if abierto is not None:
        return abierto
    return hoy().year if hoy().isoformat() <= plazo(hoy().year)["cierra"] else hoy().year + 1


def guardar_plazo(periodo: int, abre: str, cierra: str, uid: int) -> str | None:
    try:
        a, c = date.fromisoformat(abre), date.fromisoformat(cierra)
    except ValueError:
        return "Indique fechas válidas."
    if c < a:
        return "El cierre no puede ser anterior a la apertura."
    get_db().execute("""INSERT INTO convocatoria (periodo, abre, cierra, actualizado_por) VALUES (?, ?, ?, ?)
                        ON CONFLICT (periodo) DO UPDATE SET abre = excluded.abre, cierra = excluded.cierra,
                        actualizado_por = excluded.actualizado_por, actualizado_en = datetime('now')""",
                     [periodo, a.isoformat(), c.isoformat(), uid])
    return None


def restablecer_plazo(periodo: int):
    get_db().execute("DELETE FROM convocatoria WHERE periodo = ?", [periodo])


# --- Permisos ------------------------------------------------------------------------------------

def categoria(uid: int) -> str | None:
    p = perfiles.obtener(uid)
    return p["categoria"] if p else None


def puede_proponer(usuario: dict) -> bool:
    """Titulares y contratados (con perfil de investigador)."""
    return bool(usuario.get("es_investigador")) and categoria(usuario["id"]) in perfiles.CATEGORIAS_RESPONSABLES


def puede_ver(prop: dict, usuario: dict) -> bool:
    return (usuario["es_admin"] or prop["proponente_id"] == usuario["id"]
            or proyectos.puede_ver(prop["proyecto_id"], usuario))


def puede_editar(prop: dict, usuario: dict) -> bool:
    """Proponente o responsable vigente del proyecto, mientras la propuesta sea editable."""
    if prop["estado"] not in EDITABLES:
        return False
    return prop["proponente_id"] == usuario["id"] or proyectos.puede_gestionar(prop["proyecto_id"], usuario)


# --- Consultas ------------------------------------------------------------------------------------

def obtener(prop_id: int) -> dict | None:
    filas = get_db().q(
        """SELECT pi.*, p.tipo, p.estado AS estado_proyecto, u.nombres || ' ' || u.apellidos AS proponente
           FROM propuesta_institucional pi JOIN proyecto p ON p.id = pi.proyecto_id
           JOIN usuario u ON u.id = pi.proponente_id WHERE pi.id = ?""", [prop_id])
    if not filas:
        return None
    prop = filas[0]
    prop["objetivos"] = get_db().q("SELECT * FROM propuesta_objetivo WHERE propuesta_id = ? ORDER BY orden, id",
                                   [prop_id])
    prop["actividades"] = get_db().q(
        """SELECT * FROM propuesta_actividad_prevista WHERE propuesta_id = ?
           ORDER BY mes_previsto IS NULL, mes_previsto, orden, id""", [prop_id])
    return prop


def de_proyecto(pid: int) -> list[dict]:
    return get_db().q("SELECT * FROM propuesta_institucional WHERE proyecto_id = ? ORDER BY periodo DESC",
                      [pid])


def de_proyecto_y_periodo(pid: int, periodo: int) -> dict | None:
    filas = get_db().q("SELECT id FROM propuesta_institucional WHERE proyecto_id = ? AND periodo = ?",
                       [pid, periodo])
    return obtener(filas[0]["id"]) if filas else None


def eventos(prop_id: int) -> list[dict]:
    return get_db().q(
        """SELECT e.*, u.nombres || ' ' || u.apellidos AS quien FROM propuesta_evento e
           LEFT JOIN usuario u ON u.id = e.usuario_id WHERE e.propuesta_id = ? ORDER BY e.fecha, e.id""",
        [prop_id])


def mis_propuestas(uid: int) -> list[dict]:
    """Propuestas que presentó o de proyectos en que es responsable vigente."""
    return get_db().q(
        """SELECT pi.*, p.estado AS estado_proyecto FROM propuesta_institucional pi
           JOIN proyecto p ON p.id = pi.proyecto_id
           WHERE pi.proponente_id = :u OR pi.proyecto_id IN (
                 SELECT proyecto_id FROM proyecto_participante WHERE investigador_id = :u
                   AND rol IN ('responsable', 'co_responsable')
                   AND (fecha_hasta IS NULL OR fecha_hasta >= date('now')))
           ORDER BY pi.periodo DESC, pi.estado = 'aceptada', pi.nombre""", {"u": uid})


def listar(periodo: int, estado: str = "") -> list[dict]:
    """Para la administración: propuestas de un periodo, sin borradores (no se han presentado)."""
    return get_db().q(
        """SELECT pi.*, u.nombres || ' ' || u.apellidos AS proponente, u.apellidos AS proponente_apellidos
           FROM propuesta_institucional pi JOIN usuario u ON u.id = pi.proponente_id
           WHERE pi.periodo = :p AND pi.estado != 'borrador' AND (:e = '' OR pi.estado = :e)
           ORDER BY pi.estado != 'enviada', pi.enviada_en""", {"p": periodo, "e": estado})


def conteos(periodo: int) -> dict:
    filas = get_db().q("""SELECT estado, COUNT(*) n FROM propuesta_institucional WHERE periodo = ?
                          AND estado != 'borrador' GROUP BY estado""", [periodo])
    return {f["estado"]: f["n"] for f in filas}


def periodos_con_propuestas() -> list[int]:
    return [f["periodo"] for f in get_db().q(
        "SELECT DISTINCT periodo FROM propuesta_institucional WHERE estado != 'borrador' ORDER BY periodo DESC")]


def n_por_decidir() -> int:
    return get_db().q("SELECT COUNT(*) n FROM propuesta_institucional WHERE estado = 'enviada'")[0]["n"]


# --- Creación y edición -------------------------------------------------------------------------------

def crear_nuevo(usuario: dict, nombre: str) -> tuple[int | None, str | None]:
    """Proyecto institucional en formulación + su propuesta en borrador. → (id propuesta, error)."""
    if not puede_proponer(usuario):
        return None, "Solo investigadores titulares o contratados pueden proponer proyectos institucionales."
    nombre = nombre.strip()
    if not nombre:
        return None, "Indique el nombre del proyecto."
    periodo = periodo_objetivo()
    db = get_db()
    with db.conn:
        pid = db.t.proyecto.insert(nombre=nombre, estado="formulacion", tipo="institucional",
                                   fecha_inicio=inicio(periodo), fecha_fin=fin(periodo),
                                   creado_por=usuario["id"])["id"]
        db.t.proyecto_participante.insert(proyecto_id=pid, investigador_id=usuario["id"], rol="responsable",
                                          fecha_desde=hoy().isoformat())
        prop = db.t.propuesta_institucional.insert(proyecto_id=pid, periodo=periodo, modalidad="nuevo",
                                                   nombre=nombre, proponente_id=usuario["id"])["id"]
    return prop, None


def periodo_de_continuidad(p: dict) -> int | None:
    """Periodo siguiente al último cubierto por el proyecto (None si no aplica)."""
    if p["tipo"] != "institucional" or p["estado"] == "formulacion" or not p["fecha_fin"]:
        return None
    return int(p["fecha_fin"][:4])


def crear_continuidad(pid: int, usuario: dict) -> tuple[int | None, str | None]:
    """Propuesta de continuidad precargada con la última aceptada (o con los datos del proyecto)."""
    p = proyectos.obtener(pid)
    periodo = periodo_de_continuidad(p) if p else None
    if periodo is None or p["estado"] == "finalizado":
        return None, "Este proyecto no admite una propuesta de continuidad."
    if proyectos.rol_de(pid, usuario["id"]) != "responsable":
        return None, "La continuidad la propone el responsable del proyecto."
    if not puede_proponer(usuario):
        return None, "Solo investigadores titulares o contratados pueden proponer proyectos institucionales."
    existente = de_proyecto_y_periodo(pid, periodo)
    if existente:
        return existente["id"], None
    anterior = get_db().q("""SELECT id FROM propuesta_institucional WHERE proyecto_id = ? AND estado = 'aceptada'
                             ORDER BY periodo DESC LIMIT 1""", [pid])
    base = obtener(anterior[0]["id"]) if anterior else None
    db = get_db()
    with db.conn:
        campos = {k: (base or p).get(k) for k in ("nombre", "descripcion", "objetivo_general")}
        if base:
            campos.update({k: base[k] for k in ("metodologia", "resultados_esperados", "bibliografia")})
        prop = db.t.propuesta_institucional.insert(proyecto_id=pid, periodo=periodo, modalidad="continuidad",
                                                   proponente_id=usuario["id"], **campos)["id"]
        objetivos = base["objetivos"] if base else proyectos.objetivos(pid)
        for i, o in enumerate(objetivos):
            db.t.propuesta_objetivo.insert(propuesta_id=prop, orden=i, texto=o["texto"])
        # Las actividades previstas son de un periodo: no se copian las fechas, solo las descripciones
        # pendientes de ubicar en el nuevo calendario.
        for i, a in enumerate(base["actividades"] if base else []):
            db.t.propuesta_actividad_prevista.insert(propuesta_id=prop, orden=i, descripcion=a["descripcion"],
                                                     mes_previsto=None)
    return prop, None


def guardar(prop: dict, datos: dict, objetivos: list[str], actividades: list[tuple[str, str]]) -> list[str]:
    """Guarda el contenido editable. → errores (vacío si se guardó)."""
    errores = []
    datos = {k: (v or "").strip() or None for k, v in datos.items()}
    if not datos.get("nombre"):
        errores.append("El nombre del proyecto es obligatorio.")
    if any(len(v) > LARGO_TEXTO for v in datos.values() if v):
        errores.append(f"Cada sección admite hasta {LARGO_TEXTO:,} caracteres.".replace(",", "."))
    validos = {m for m, _ in meses(prop["periodo"])}
    actividades = [(d.strip(), m or None) for d, m in actividades if d.strip()]
    if any(m and m not in validos for _, m in actividades):
        errores.append("Hay actividades con un mes fuera del periodo.")
    if errores:
        return errores
    db = get_db()
    with db.conn:
        db.execute(f"""UPDATE propuesta_institucional SET {', '.join(f'{k} = :{k}' for k in datos)},
                       actualizada_en = datetime('now') WHERE id = :id""", {**datos, "id": prop["id"]})
        db.execute("DELETE FROM propuesta_objetivo WHERE propuesta_id = ?", [prop["id"]])
        for i, texto in enumerate(t.strip() for t in objetivos if t.strip()):
            db.t.propuesta_objetivo.insert(propuesta_id=prop["id"], orden=i, texto=texto)
        db.execute("DELETE FROM propuesta_actividad_prevista WHERE propuesta_id = ?", [prop["id"]])
        for i, (desc, mes) in enumerate(actividades):
            db.t.propuesta_actividad_prevista.insert(propuesta_id=prop["id"], orden=i, descripcion=desc,
                                                     mes_previsto=mes)
        if prop["modalidad"] == "nuevo" and prop["estado_proyecto"] == "formulacion":
            # Mientras está en formulación, el nombre del proyecto sigue al de su propuesta.
            db.execute("UPDATE proyecto SET nombre = ? WHERE id = ?", [datos["nombre"], prop["proyecto_id"]])
    return []


def faltantes(prop: dict) -> list[str]:
    """Qué falta para poder enviarla."""
    requeridos = [("nombre", "nombre"), ("descripcion", "descripción"), ("objetivo_general", "objetivo general"),
                  ("metodologia", "metodología"), ("resultados_esperados", "resultados esperados"),
                  ("bibliografia", "bibliografía")]
    falta = [texto for campo, texto in requeridos if not (prop[campo] or "").strip()]
    if not prop["objetivos"]:
        falta.append("al menos un objetivo específico")
    if not prop["actividades"]:
        falta.append("al menos una actividad prevista")
    elif any(not a["mes_previsto"] for a in prop["actividades"]):
        falta.append("el mes previsto de cada actividad")
    return falta


def _evento(prop_id, accion, uid, comentario=None):
    get_db().t.propuesta_evento.insert(propuesta_id=prop_id, accion=accion, usuario_id=uid, comentario=comentario)


def copia(prop: dict) -> dict:
    """Lo que se congela al enviar: la administración decide sobre esto."""
    equipo = [{"nombre": f"{x['nombres']} {x['apellidos']}", "rol": proyectos.ROLES[x["rol"]],
               "interno": x["interno"], "afiliacion": x.get("afiliacion"),
               "categoria": perfiles.categoria_texto(categoria(x["id"])) if x["interno"] else None}
              for x in proyectos.participantes(prop["proyecto_id"], solo_vigentes=True)]
    return {"nombre": prop["nombre"], "periodo": prop["periodo"], "modalidad": prop["modalidad"],
            "proponente": prop["proponente"], "descripcion": prop["descripcion"],
            "objetivo_general": prop["objetivo_general"],
            "objetivos": [o["texto"] for o in prop["objetivos"]],
            "metodologia": prop["metodologia"], "resultados_esperados": prop["resultados_esperados"],
            "actividades": [{"descripcion": a["descripcion"], "mes": a["mes_previsto"]} for a in prop["actividades"]],
            "bibliografia": prop["bibliografia"], "equipo": equipo}


def enviar(prop: dict, usuario: dict) -> str | None:
    if not puede_editar(prop, usuario):
        return "Esta propuesta ya no se puede enviar."
    if prop["estado"] == "borrador" and not abierta(prop["periodo"]):
        p = plazo(prop["periodo"])
        return (f"La convocatoria {periodo_texto(prop['periodo'])} recibe propuestas del "
                f"{fecha_texto(p['abre'])} al {fecha_texto(p['cierra'])}.")
    falta = faltantes(prop)
    if falta:
        return "Antes de enviar, complete: " + ", ".join(falta) + "."
    reenvio = prop["estado"] == "condicional"
    get_db().execute("""UPDATE propuesta_institucional SET estado = 'enviada', enviada_en = datetime('now'),
                        envios = envios + 1, copia_enviada = ? WHERE id = ?""",
                     [json.dumps(copia(prop), ensure_ascii=False), prop["id"]])
    _evento(prop["id"], "enviada", usuario["id"], "Reenvío tras las condiciones" if reenvio else None)
    refrescar_vigencias(prop["proyecto_id"])
    avisos.propuesta_enviada(obtener(prop["id"]), reenvio)
    return None


def retirar(prop: dict, usuario: dict) -> str | None:
    if prop["estado"] not in EN_REVISION or not (
            prop["proponente_id"] == usuario["id"] or proyectos.puede_gestionar(prop["proyecto_id"], usuario)):
        return "Esta propuesta no se puede retirar."
    get_db().execute("UPDATE propuesta_institucional SET estado = 'retirada' WHERE id = ?", [prop["id"]])
    _evento(prop["id"], "retirada", usuario["id"])
    refrescar_vigencias(prop["proyecto_id"])
    return None


def eliminar_borrador(prop: dict, usuario: dict) -> str | None:
    """Borra un borrador. Si era un proyecto nuevo sin otra historia, borra también el proyecto."""
    if prop["estado"] != "borrador" or not puede_editar(prop, usuario):
        return "Solo se pueden eliminar borradores."
    db = get_db()
    with db.conn:
        db.execute("DELETE FROM propuesta_institucional WHERE id = ?", [prop["id"]])
        otras = db.q("SELECT 1 FROM propuesta_institucional WHERE proyecto_id = ?", [prop["proyecto_id"]])
        vinculos = db.q("""SELECT 1 FROM actividad_proyecto WHERE proyecto_id = :p
                           UNION ALL SELECT 1 FROM producto_proyecto WHERE proyecto_id = :p""",
                        {"p": prop["proyecto_id"]})
        if prop["modalidad"] == "nuevo" and not otras and not vinculos:
            db.execute("DELETE FROM proyecto WHERE id = ?", [prop["proyecto_id"]])
    return None


# --- Decisión (administración) --------------------------------------------------------------------------

DECISIONES = {"aceptada": "Aceptar", "condicional": "Aceptar con condiciones", "rechazada": "Rechazar"}


def decidir(prop: dict, decision: str, comentario: str, admin: dict) -> str | None:
    if not admin["es_admin"]:
        return "Solo la administración decide las propuestas."
    if decision not in DECISIONES:
        return "Decisión no válida."
    if prop["estado"] != "enviada":
        return "Solo se deciden propuestas enviadas."
    comentario = comentario.strip()
    if decision == "condicional" and not comentario:
        return "Indique las condiciones: el responsable las verá para corregir la propuesta."
    if decision == "rechazada" and not comentario:
        return "Indique el motivo del rechazo."
    db = get_db()
    with db.conn:
        db.execute("""UPDATE propuesta_institucional SET estado = ?, decidida_por = ?, decidida_en = datetime('now'),
                      comentario = ? WHERE id = ?""", [decision, admin["id"], comentario or None, prop["id"]])
        _evento(prop["id"], decision, admin["id"], comentario or None)
        if decision == "aceptada":
            _aplicar(obtener(prop["id"]))
    refrescar_vigencias(prop["proyecto_id"])
    avisos.propuesta_decidida(obtener(prop["id"]), admin["id"])
    return None


def _aplicar(prop: dict):
    """Una propuesta aceptada pasa sus datos básicos y objetivos al proyecto."""
    db = get_db()
    db.execute("""UPDATE proyecto SET nombre = ?, descripcion = ?, objetivo_general = ?,
                  actualizado_en = datetime('now') WHERE id = ?""",
               [prop["nombre"], prop["descripcion"], prop["objetivo_general"], prop["proyecto_id"]])
    db.execute("DELETE FROM proyecto_objetivo WHERE proyecto_id = ?", [prop["proyecto_id"]])
    for i, o in enumerate(prop["objetivos"]):
        db.t.proyecto_objetivo.insert(proyecto_id=prop["proyecto_id"], orden=i + 1, texto=o["texto"])


# --- Vigencia ----------------------------------------------------------------------------------------------

def refrescar_vigencias(pid: int | None = None):
    """Recalcula fechas y estado de los proyectos institucionales con propuestas (o de uno).

    Los proyectos institucionales sin ninguna propuesta (cargados antes de esta función) no se
    tocan: su estado sigue siendo el que se registró.
    """
    db = get_db()
    filtro = "AND p.id = :pid" if pid else ""
    filas = db.q(
        f"""SELECT p.id, p.estado, p.fecha_inicio, p.fecha_fin,
                   (SELECT MIN(periodo) FROM propuesta_institucional WHERE proyecto_id = p.id
                      AND estado = 'aceptada') AS primero,
                   (SELECT MAX(periodo) FROM propuesta_institucional WHERE proyecto_id = p.id
                      AND estado = 'aceptada') AS ultimo
            FROM proyecto p WHERE p.tipo = 'institucional'
              AND EXISTS (SELECT 1 FROM propuesta_institucional x WHERE x.proyecto_id = p.id) {filtro}""",
        {"pid": pid})
    for f in filas:
        if f["ultimo"] is None:
            estado, ini, fn = "formulacion", f["fecha_inicio"], f["fecha_fin"]
        else:
            ini, fn = inicio(f["primero"]), fin(f["ultimo"])
            if hoy().isoformat() <= fn:
                estado = "vigente"
            else:
                renovando = db.q("""SELECT 1 FROM propuesta_institucional WHERE proyecto_id = ? AND periodo = ?
                                    AND estado IN ('enviada', 'condicional')""", [f["id"], f["ultimo"] + 1])
                estado = "vigente" if renovando else "finalizado"
        if (estado, ini, fn) != (f["estado"], f["fecha_inicio"], f["fecha_fin"]):
            db.execute("UPDATE proyecto SET estado = ?, fecha_inicio = ?, fecha_fin = ? WHERE id = ?",
                       [estado, ini, fn, f["id"]])


def en_renovacion(p: dict) -> bool:
    """Vigente después de su último periodo aceptado, a la espera de la decisión de continuidad."""
    return (p["tipo"] == "institucional" and p["estado"] == "vigente" and bool(p["fecha_fin"])
            and hoy().isoformat() > p["fecha_fin"])


def pendiente_de_continuidad(p: dict) -> int | None:
    """Si el proyecto termina con la convocatoria abierta y aún no envía su continuidad, el periodo."""
    periodo = periodo_de_continuidad(p)
    if periodo is None or p["estado"] != "vigente" or not abierta(periodo):
        return None
    prop = de_proyecto_y_periodo(p["id"], periodo)
    return None if prop and prop["estado"] in ("enviada", "condicional", "aceptada") else periodo


def recordatorios():
    """Una vez por proyecto y periodo: avisa a los responsables que su proyecto termina si no
    proponen continuidad (solo con la convocatoria abierta)."""
    periodo = periodo_abierto()
    if periodo is None:
        return
    db = get_db()
    for p in db.q("""SELECT * FROM proyecto WHERE tipo = 'institucional' AND estado = 'vigente'
                     AND fecha_fin = ?""", [f"{periodo}-09-30"]):
        if pendiente_de_continuidad(p) is None:
            continue
        clave = f"continuidad:{p['id']}:{periodo}"
        if db.q("SELECT 1 FROM aviso_enviado WHERE clave = ?", [clave]):
            continue
        db.t.aviso_enviado.insert(clave=clave)
        avisos.recordatorio_continuidad(p, periodo, plazo(periodo)["cierra"])


_ultimo_mantenimiento = 0.0


def mantenimiento(forzar: bool = False):
    """Vigencias y recordatorios; a lo más una vez por hora (lo llama una Beforeware)."""
    global _ultimo_mantenimiento
    if not forzar and time.monotonic() - _ultimo_mantenimiento < 3600:
        return
    _ultimo_mantenimiento = time.monotonic()
    from app import vinculos
    vinculos.sincronizar_categoria()  # un vínculo con fecha de término deja de estar vigente
    refrescar_vigencias()
    recordatorios()


# --- Plan de actividades: previstas frente a realizadas ---------------------------------------------------

def plan(pid: int, desde_anio: int | None = None, hasta_anio: int | None = None) -> list[dict]:
    """Por cada periodo aceptado del proyecto (opcionalmente, los que se cruzan con los años dados):
    sus actividades previstas, con la actividad registrada que la cumple (si se enlazó) y un
    estado: realizada, pendiente o atrasada (el mes previsto ya pasó sin enlace)."""
    mes_actual = hoy().isoformat()[:7]
    res = []
    for prop in get_db().q("""SELECT id, periodo FROM propuesta_institucional WHERE proyecto_id = ?
                              AND estado = 'aceptada' ORDER BY periodo DESC""", [pid]):
        if desde_anio is not None and (int(fin(prop["periodo"])[:4]) < desde_anio or prop["periodo"] > hasta_anio):
            continue
        filas = get_db().q(
            """SELECT ap.*, a.titulo AS realizada_titulo, a.fecha_inicio AS realizada_fecha
               FROM propuesta_actividad_prevista ap LEFT JOIN actividad a ON a.id = ap.actividad_id
               WHERE ap.propuesta_id = ? ORDER BY ap.mes_previsto IS NULL, ap.mes_previsto, ap.orden""",
            [prop["id"]])
        for f in filas:
            f["estado"] = ("realizada" if f["actividad_id"] else
                           "atrasada" if f["mes_previsto"] and f["mes_previsto"] < mes_actual else "pendiente")
        res.append({"periodo": prop["periodo"], "previstas": filas,
                    "realizadas": sum(f["estado"] == "realizada" for f in filas)})
    return res


def actividades_para_enlazar(pid: int, periodo: int) -> list[dict]:
    """Actividades aprobadas en el proyecto con inicio dentro del periodo."""
    return get_db().q(
        """SELECT a.id, a.titulo, a.fecha_inicio FROM actividad_proyecto v JOIN actividad a ON a.id = v.actividad_id
           WHERE v.proyecto_id = ? AND v.estado = 'aprobado' AND a.fecha_inicio BETWEEN ? AND ?
           ORDER BY a.fecha_inicio""", [pid, inicio(periodo), fin(periodo)])


def enlazar_prevista(prevista_id: int, actividad_id: int | None, usuario: dict) -> str | None:
    """Marca una actividad prevista como realizada (enlazándola) o la desmarca (None)."""
    fila = get_db().q(
        """SELECT ap.id, pi.proyecto_id, pi.periodo, pi.estado FROM propuesta_actividad_prevista ap
           JOIN propuesta_institucional pi ON pi.id = ap.propuesta_id WHERE ap.id = ?""", [prevista_id])
    if not fila or fila[0]["estado"] != "aceptada":
        return "Actividad prevista no encontrada."
    f = fila[0]
    if not proyectos.puede_gestionar(f["proyecto_id"], usuario):
        return "Solo los responsables del proyecto registran el avance del plan."
    if actividad_id is not None and actividad_id not in {
            a["id"] for a in actividades_para_enlazar(f["proyecto_id"], f["periodo"])}:
        return "La actividad debe estar aprobada en el proyecto y ser del mismo periodo."
    get_db().execute("UPDATE propuesta_actividad_prevista SET actividad_id = ? WHERE id = ?",
                     [actividad_id, prevista_id])
    return None


# --- Exportación de una convocatoria ------------------------------------------------------------------------

def hojas_convocatoria(periodo: int) -> dict[str, list[dict]]:
    """Propuestas presentadas en un periodo (sin borradores), con el contenido que se envió.
    Para el comité o la administración: una hoja de resumen, una de textos y dos de listas."""
    resumen, textos, objetivos, actividades = [], [], [], []
    for p in listar(periodo):
        c = json.loads(p["copia_enviada"]) if p["copia_enviada"] else copia(obtener(p["id"]))
        clave = {"Proyecto": p["nombre"]}
        resumen.append({**clave, "Modalidad": MODALIDADES[p["modalidad"]], "Proponente": p["proponente"],
                        "Estado": ESTADOS[p["estado"]], "Enviada": (p["enviada_en"] or "")[:10],
                        "Envíos": p["envios"], "Decisión": (p["decidida_en"] or "")[:10],
                        "Condiciones o motivo": p["comentario"] or "",
                        "Equipo": "; ".join(f"{x['nombre']} ({x['rol']})" for x in c.get("equipo", [])),
                        "Objetivos": len(c["objetivos"]), "Actividades previstas": len(c["actividades"])})
        textos.append({**clave, "Descripción": c["descripcion"] or "", "Objetivo general": c["objetivo_general"] or "",
                       "Metodología": c["metodologia"] or "", "Resultados esperados": c["resultados_esperados"] or "",
                       "Bibliografía": c["bibliografia"] or ""})
        objetivos += [{**clave, "N.º": i, "Objetivo específico": o} for i, o in enumerate(c["objetivos"], start=1)]
        actividades += [{**clave, "Mes": mes_texto(a["mes"]), "Actividad prevista": a["descripcion"]}
                        for a in c["actividades"]]
    return {"Propuestas": resumen, "Textos": textos, "Objetivos": objetivos, "Actividades previstas": actividades}
