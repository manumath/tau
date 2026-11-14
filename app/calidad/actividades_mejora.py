"""Actividades del plan de mejora, reprogramaciones y aprobación del plan (PLAN §72, etapa 2).

- Cada acción del plan tiene actividades con línea base, meta, indicador del SIAC opcional, responsable (persona del sistema
  o unidad en texto), inicio y plazo, presupuesto y fuente, medio de verificación y de difusión.
- **Avance calculado, no guardado.** El de una actividad es, si tiene indicador con línea base y meta numéricas, la
  distancia recorrida de la línea base a la meta según la última cifra del indicador; si no, el último porcentaje
  registrado. El de la acción es el promedio de sus actividades no canceladas.
- **Semáforo:** cumplida, cancelada, vencida (plazo pasado sin cumplirse), en riesgo (vence en 30 días o menos, o pasó más
  de la mitad del plazo con menos de la mitad del avance) y al día.
- **Plan aprobado:** el marco guarda la resolución y la fecha. Desde entonces el plazo de una actividad solo cambia por
  reprogramación: el responsable la pide con su causa y la Dirección de Carrera la aprueba o la rechaza (decisión del
  usuario del 14-nov-2026); quien gestiona el plan puede registrarla ya aprobada.
"""
from datetime import date

from app.calidad import evidencias, marco, mejora
from app.comun import formato, notificaciones, permisos, usuarios
from app.comun.db import AHORA, get_db, transaccion

ESTADOS = mejora.ESTADOS
ABIERTAS = mejora.ABIERTAS
PRIORIDAD_P = {"alta": "P1", "media": "P2", "baja": "P3"}
SEMAFOROS = {"vencida": "Vencida", "en_riesgo": "En riesgo", "al_dia": "Al día", "cumplida": "Cumplida",
             "cancelada": "Cancelada"}
ORDEN_SEMAFORO = ("vencida", "en_riesgo", "al_dia", "cumplida", "cancelada")
DIAS_RIESGO = 30
ESTADOS_REPROGRAMACION = {"pendiente": "Pendiente", "aprobada": "Aprobada", "rechazada": "Rechazada"}

_texto = mejora._texto
_fecha = mejora._fecha


# --- Aprobación del plan -----------------------------------------------------------------------------------------------

def aprobado(m: dict) -> bool:
    return bool(m.get("plan_aprobado_en"))


def aprobar_plan(mid: int, resolucion: str, fecha: str) -> list[str]:
    """Registra (o corrige) la resolución y la fecha con que se aprobó el plan de mejora."""
    errores: list[str] = []
    resolucion = _texto(resolucion, 200)
    f = _fecha(fecha, "la fecha de aprobación", errores, obligatoria=True)
    if not resolucion:
        errores.append("Indique la resolución que aprueba el plan.")
    if not errores and f > date.today().isoformat():
        errores.append("La fecha de aprobación no puede ser futura.")
    if not errores:
        get_db().execute("UPDATE marco_calidad SET plan_resolucion = ?, plan_aprobado_en = ? WHERE id = ?",
                         [resolucion, f, mid])
    return errores


# --- Actividades ----------------------------------------------------------------------------------------------------

_SELECT = """SELECT t.*, a.marco_id, a.codigo AS accion_codigo, a.titulo AS accion_titulo, a.prioridad,
                    u.nombres || ' ' || u.apellidos AS responsable,
                    i.codigo AS indicador_codigo, i.nombre AS indicador_nombre, i.unidad_medida,
                    (SELECT porcentaje FROM avance_accion v WHERE v.actividad_id = t.id AND v.porcentaje IS NOT NULL
                     ORDER BY v.fecha DESC, v.id DESC LIMIT 1) AS porcentaje,
                    (SELECT MAX(fecha) FROM avance_accion v WHERE v.actividad_id = t.id) AS ultimo_avance,
                    (SELECT COUNT(*) FROM avance_accion v WHERE v.actividad_id = t.id) AS avances,
                    (SELECT COUNT(*) FROM reprogramacion_mejora r WHERE r.actividad_id = t.id AND r.estado = 'pendiente')
                        AS reprogramacion_pendiente
             FROM actividad_mejora t JOIN accion_mejora a ON a.id = t.accion_id
             LEFT JOIN usuario u ON u.id = t.responsable_id LEFT JOIN indicador_calidad i ON i.id = t.indicador_id"""
_ORDEN = " ORDER BY a.codigo IS NULL, a.codigo, a.id, t.codigo IS NULL, t.codigo, t.plazo, t.id"


def _clave_codigo(codigo: str | None) -> tuple:
    """«4.10» después de «4.9»: orden numérico de los códigos."""
    partes = []
    for p in (codigo or "").replace("A", "").split("."):
        partes.append((0, int(p), "") if p.isdigit() else (1, 0, p))
    return (codigo is None, partes)


def _inicio(t: dict, m: dict | None) -> str:
    """Desde cuándo corre el plazo de la actividad: su inicio, la aprobación del plan o su registro."""
    return t["inicio"] or (m or {}).get("plan_aprobado_en") or t["creada_en"][:10]


def valor_indicador(t: dict, hoy: date) -> tuple[float | None, int | None]:
    """La última cifra del indicador de la actividad (la del año en curso o, si aún no la hay, la del anterior) y su año.
    Solo dos años: la cifra más reciente es la que mide el avance, y calcular más años haría lenta la lista."""
    if not t["indicador_id"]:
        return None, None
    from app.calidad import indicadores
    i = get_db().q("""SELECT i.*, c.dimension_id, d.marco_id FROM indicador_calidad i JOIN criterio_calidad c ON c.id = i.criterio_id
                      JOIN dimension_calidad d ON d.id = c.dimension_id WHERE i.id = ?""", [t["indicador_id"]])
    if not i:
        return None, None
    i[0]["metas"] = get_db().q("SELECT * FROM meta_indicador WHERE indicador_id = ? ORDER BY anio", [t["indicador_id"]])
    anios = [hoy.year - 1, hoy.year]
    serie = indicadores.serie(i[0], anios)
    for a in reversed(anios):
        if serie[a]["valor"] is not None:
            return serie[a]["valor"], a
    return None, None


def avance(t: dict, hoy: date | None = None) -> int | None:
    """Porcentaje de avance de la actividad (0 a 100) o None si no hay cómo saberlo."""
    if t["estado"] == "cumplida":
        return 100
    if t["indicador_id"] and t["linea_base_valor"] is not None and t["meta_valor"] is not None \
            and t["meta_valor"] != t["linea_base_valor"]:
        actual, _ = valor_indicador(t, hoy or date.today())
        if actual is not None:
            p = (actual - t["linea_base_valor"]) / (t["meta_valor"] - t["linea_base_valor"])
            return max(0, min(100, round(100 * p)))
    return t["porcentaje"]


def semaforo(t: dict, pct: int | None, hoy: date, m: dict | None = None) -> str:
    if t["estado"] in ("cumplida", "cancelada"):
        return t["estado"]
    plazo = date.fromisoformat(t["plazo"])
    if plazo < hoy:
        return "vencida"
    if (plazo - hoy).days <= DIAS_RIESGO and (pct or 0) < 100:
        return "en_riesgo"
    inicio = date.fromisoformat(_inicio(t, m))
    total = (plazo - inicio).days
    if total > 0 and (hoy - inicio).days / total > 0.5 and (pct or 0) < 50:
        return "en_riesgo"
    return "al_dia"


def _completar(filas: list[dict], hoy: date | None = None) -> list[dict]:
    hoy = hoy or date.today()
    marcos: dict[int, dict] = {}
    for t in filas:
        m = marcos.setdefault(t["marco_id"], marco.obtener(t["marco_id"]) or {})
        t["avance"] = avance(t, hoy)
        t["semaforo"] = semaforo(t, t["avance"], hoy, m)
        t["prioridad_p"] = PRIORIDAD_P[t["prioridad"]]
    return filas


def de_accion(aid: int, hoy: date | None = None) -> list[dict]:
    filas = get_db().q(_SELECT + " WHERE t.accion_id = ?" + _ORDEN, [aid])
    return sorted(_completar(filas, hoy), key=lambda t: _clave_codigo(t["codigo"]))


def de_marco(mid: int, hoy: date | None = None) -> list[dict]:
    filas = _completar(get_db().q(_SELECT + " WHERE a.marco_id = ?" + _ORDEN, [mid]), hoy)
    return sorted(filas, key=lambda t: (_clave_codigo(t["accion_codigo"]), _clave_codigo(t["codigo"])))


def de_responsable(uid: int, hoy: date | None = None) -> list[dict]:
    """Las actividades abiertas a cargo de la persona, la más urgente primero («Mi parte del plan»)."""
    filas = _completar(get_db().q(_SELECT + " WHERE t.responsable_id = ? AND t.estado IN ('pendiente', 'en_curso')"
                                  + _ORDEN, [uid]), hoy)
    return sorted(filas, key=lambda t: (ORDEN_SEMAFORO.index(t["semaforo"]), t["plazo"]))


def obtener(tid: int, hoy: date | None = None) -> dict | None:
    f = get_db().q(_SELECT + " WHERE t.id = ?", [tid])
    if not f:
        return None
    t = _completar(f, hoy)[0]
    t["lista_avances"] = get_db().q(
        """SELECT v.*, u.nombres || ' ' || u.apellidos AS por, e.titulo AS evidencia_titulo FROM avance_accion v
           LEFT JOIN usuario u ON u.id = v.registrado_por LEFT JOIN evidencia_calidad e ON e.id = v.evidencia_id
           WHERE v.actividad_id = ? ORDER BY v.fecha DESC, v.id DESC""", [tid])
    t["reprogramaciones"] = reprogramaciones(tid)
    return t


def resumen_accion(actividades: list[dict]) -> dict:
    """Avance (promedio de las no canceladas) y semáforo (el peor de las abiertas) de una acción con actividades."""
    vigentes = [t for t in actividades if t["estado"] != "cancelada"]
    if not vigentes:
        return {"avance": None, "semaforo": None, "conteo": {}}
    avances = [t["avance"] or 0 for t in vigentes]
    abiertas = [t["semaforo"] for t in vigentes if t["estado"] in ABIERTAS]
    peor = min(abiertas, key=ORDEN_SEMAFORO.index) if abiertas else "cumplida"
    conteo = {s: sum(t["semaforo"] == s for t in actividades) for s in ORDEN_SEMAFORO}
    return {"avance": round(sum(avances) / len(avances)), "semaforo": peor, "conteo": conteo}


def _numero(texto, campo: str, errores: list) -> float | None:
    texto = str(texto or "").strip().replace(" ", "")
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")       # «1.500,50» → 1500.50
    try:
        return float(texto)
    except ValueError:
        errores.append(f"{campo} es un número.")
        return None


def validar(d: dict, mid: int, actual: dict | None = None) -> tuple[dict, list[str]]:
    """Datos de una actividad. Con el plan aprobado, el plazo de una actividad existente no se edita aquí."""
    errores: list[str] = []
    m = marco.obtener(mid)
    x = {"codigo": _texto(d.get("codigo"), 20), "descripcion": _texto(d.get("descripcion"), 1000),
         "linea_base": _texto(d.get("linea_base"), 500), "meta": _texto(d.get("meta"), 500),
         "unidad_responsable": _texto(d.get("unidad_responsable"), 200), "fuente": _texto(d.get("fuente"), 200),
         "verificacion": _texto(d.get("verificacion"), 500), "difusion": _texto(d.get("difusion"), 500)}
    if not x["descripcion"]:
        errores.append("Describa la actividad.")
    x["linea_base_valor"] = _numero(d.get("linea_base_valor"), "La línea base (valor)", errores)
    x["meta_valor"] = _numero(d.get("meta_valor"), "La meta (valor)", errores)
    x["presupuesto"] = _numero(d.get("presupuesto"), "El presupuesto", errores)
    if x["presupuesto"] is not None and x["presupuesto"] < 0:
        errores.append("El presupuesto no puede ser negativo.")
    x["inicio"] = _fecha(d.get("inicio"), "el inicio", errores)
    x["plazo"] = _fecha(d.get("plazo"), "el plazo", errores, obligatoria=True)
    if actual and aprobado(m) and x["plazo"] != actual["plazo"]:
        errores.append("El plan ya está aprobado: el plazo cambia solo por reprogramación.")
        x["plazo"] = actual["plazo"]
    if x["inicio"] and x["plazo"] and not errores and x["inicio"] > x["plazo"]:
        errores.append("El inicio no puede ser posterior al plazo.")

    def entero(clave, validos, texto):
        v = str(d.get(clave) or "").strip()
        if not v:
            return None
        if v.isdigit() and int(v) in validos:
            return int(v)
        errores.append(texto)
        return None
    x["responsable_id"] = entero("responsable_id", {u["id"] for u in mejora.responsables()},
                                 "Elija un responsable de la lista.")
    x["indicador_id"] = entero("indicador_id", {i["id"] for i in mejora.indicadores_del_marco(mid)},
                               "Elija un indicador del marco.")
    if not x["responsable_id"] and not x["unidad_responsable"] and "Elija un responsable de la lista." not in errores:
        errores.append("Indique la persona o la unidad responsable.")
    if x["indicador_id"] and (x["linea_base_valor"] is None) != (x["meta_valor"] is None):
        errores.append("Con un indicador, indique la línea base y la meta en números (las dos) o ninguna.")
    return x, errores


CAMPOS = ("codigo", "descripcion", "linea_base", "linea_base_valor", "meta", "meta_valor", "indicador_id", "responsable_id",
          "unidad_responsable", "inicio", "plazo", "presupuesto", "fuente", "verificacion", "difusion")


def _sincronizar_accion(aid: int):
    """El plazo de una acción con actividades es el último de sus actividades no canceladas (lo usan el tablero de
    indicadores y los avisos de la acción)."""
    f = get_db().q("SELECT MAX(plazo) AS p FROM actividad_mejora WHERE accion_id = ? AND estado <> 'cancelada'", [aid])
    if f and f[0]["p"]:
        get_db().execute("UPDATE accion_mejora SET plazo = ? WHERE id = ?", [f[0]["p"], aid])


def crear(aid: int, x: dict, uid: int) -> int:
    with transaccion():
        tid = get_db().t.actividad_mejora.insert(accion_id=aid, creada_por=uid, **{k: x[k] for k in CAMPOS})["id"]
        _sincronizar_accion(aid)
    return tid


def actualizar(t: dict, x: dict):
    with transaccion():
        get_db().t.actividad_mejora.update({k: x[k] for k in CAMPOS}, t["id"])
        _sincronizar_accion(t["accion_id"])


def eliminar(t: dict) -> bool:
    """Solo una actividad sin avances ni reprogramaciones; las demás se cancelan con su motivo."""
    if t["avances"] or get_db().q("SELECT 1 FROM reprogramacion_mejora WHERE actividad_id = ? LIMIT 1", [t["id"]]):
        return False
    with transaccion():
        get_db().execute("DELETE FROM actividad_mejora WHERE id = ?", [t["id"]])
        _sincronizar_accion(t["accion_id"])
    return True


def cumplir(t: dict, fecha: str) -> list[str]:
    errores: list[str] = []
    f = _fecha(fecha, "la fecha en que se cumplió", errores, obligatoria=True)
    if not errores and f > date.today().isoformat():
        errores.append("La fecha en que se cumplió no puede ser futura.")
    if not errores:
        get_db().execute("""UPDATE actividad_mejora SET estado = 'cumplida', cumplida_en = ?, motivo_cancelacion = NULL
                            WHERE id = ?""", [f, t["id"]])
    return errores


def cancelar(t: dict, motivo: str) -> list[str]:
    motivo = _texto(motivo, 500)
    if not motivo:
        return ["Indique el motivo de la cancelación."]
    with transaccion():
        get_db().execute("""UPDATE actividad_mejora SET estado = 'cancelada', motivo_cancelacion = ?, cumplida_en = NULL
                            WHERE id = ?""", [motivo, t["id"]])
        _sincronizar_accion(t["accion_id"])
    return []


def reabrir(t: dict):
    with transaccion():
        get_db().execute("""UPDATE actividad_mejora SET estado = ?, cumplida_en = NULL, motivo_cancelacion = NULL
                            WHERE id = ?""", ["en_curso" if t["avances"] else "pendiente", t["id"]])
        _sincronizar_accion(t["accion_id"])


# --- Avances ------------------------------------------------------------------------------------------------------------

def registrar_avance(t: dict, x: dict, uid: int) -> int:
    """El avance queda en la actividad y en su acción; ambas pasan a «en curso» si estaban pendientes."""
    with transaccion():
        vid = get_db().t.avance_accion.insert(accion_id=t["accion_id"], actividad_id=t["id"], registrado_por=uid, **x)["id"]
        get_db().execute("UPDATE actividad_mejora SET estado = 'en_curso' WHERE id = ? AND estado = 'pendiente'", [t["id"]])
        get_db().execute("UPDATE accion_mejora SET estado = 'en_curso' WHERE id = ? AND estado = 'pendiente'",
                         [t["accion_id"]])
    return vid


# --- Permisos -----------------------------------------------------------------------------------------------------------

def gestiona(auth, mid: int) -> bool:
    return marco.puede(auth, "gestionar_plan_mejora", marco.obtener(mid))


def es_responsable(auth, t: dict) -> bool:
    return bool(t["responsable_id"]) and t["responsable_id"] == auth["id"]


def puede_avanzar(auth, t: dict) -> bool:
    """Registran avances y piden reprogramaciones el responsable de la actividad y quien gestiona el plan."""
    return es_responsable(auth, t) or gestiona(auth, t["marco_id"])


# --- Reprogramaciones ---------------------------------------------------------------------------------------------------

def reprogramaciones(tid: int) -> list[dict]:
    return get_db().q(
        """SELECT r.*, s.nombres || ' ' || s.apellidos AS solicitante, q.nombres || ' ' || q.apellidos AS resolvio,
                  e.titulo AS evidencia_titulo
           FROM reprogramacion_mejora r LEFT JOIN usuario s ON s.id = r.solicitada_por
           LEFT JOIN usuario q ON q.id = r.resuelta_por LEFT JOIN evidencia_calidad e ON e.id = r.evidencia_id
           WHERE r.actividad_id = ? ORDER BY r.solicitada_en DESC, r.id DESC""", [tid])


def pendientes_de_marco(mid: int) -> list[dict]:
    """Las reprogramaciones por resolver del plan (para la Dirección de Carrera)."""
    return get_db().q(
        """SELECT r.*, t.descripcion, t.codigo, t.accion_id, s.nombres || ' ' || s.apellidos AS solicitante
           FROM reprogramacion_mejora r JOIN actividad_mejora t ON t.id = r.actividad_id
           JOIN accion_mejora a ON a.id = t.accion_id LEFT JOIN usuario s ON s.id = r.solicitada_por
           WHERE a.marco_id = ? AND r.estado = 'pendiente' ORDER BY r.solicitada_en""", [mid])


def reprogramacion(rid: int) -> dict | None:
    f = get_db().q("""SELECT r.*, a.marco_id FROM reprogramacion_mejora r JOIN actividad_mejora t ON t.id = r.actividad_id
                      JOIN accion_mejora a ON a.id = t.accion_id WHERE r.id = ?""", [rid])
    return f[0] if f else None


def _nombre(t: dict) -> str:
    return f"{t['codigo']} " if t["codigo"] else ""


def solicitar_reprogramacion(auth, t: dict, d: dict) -> tuple[int | None, list[str]]:
    """El responsable pide un plazo nuevo con su causa; quien gestiona el plan la registra ya aprobada. → (id, errores)"""
    errores: list[str] = []
    if t["estado"] not in ABIERTAS:
        errores.append("Solo se reprograma una actividad pendiente o en curso.")
    if t["reprogramacion_pendiente"]:
        errores.append("Ya hay una reprogramación por resolver para esta actividad.")
    nuevo = _fecha(d.get("plazo_nuevo"), "el plazo nuevo", errores, obligatoria=True)
    causa = _texto(d.get("causa"), 2000)
    if not causa:
        errores.append("Explique la causa de la reprogramación.")
    if nuevo and not errores:
        if nuevo == t["plazo"]:
            errores.append("El plazo nuevo es igual al actual.")
        elif t["inicio"] and nuevo < t["inicio"]:
            errores.append("El plazo nuevo no puede ser anterior al inicio de la actividad.")
    e = str(d.get("evidencia_id") or "").strip()
    evidencia_id = None
    if e:
        if e.isdigit() and int(e) in {v["id"] for v in evidencias.listar(t["marco_id"])}:
            evidencia_id = int(e)
        else:
            errores.append("Elija una evidencia del repositorio.")
    if errores:
        return None, errores
    directo = gestiona(auth, t["marco_id"])
    with transaccion():
        rid = get_db().t.reprogramacion_mejora.insert(
            actividad_id=t["id"], plazo_anterior=t["plazo"], plazo_nuevo=nuevo, causa=causa, evidencia_id=evidencia_id,
            solicitada_por=auth["id"])["id"]
        if directo:
            _resolver(rid, t, "aprobada", auth["id"], None)
    if not directo:
        m = marco.obtener(t["marco_id"])
        for u in permisos.con_rol("direccion_carrera", m["unidad_id"]):
            notificaciones.avisar(usuarios.por_id(u["id"]), "Reprogramación por resolver",
                                  f"Se pide mover el plazo de la actividad {_nombre(t)}«{t['descripcion'][:80]}» del "
                                  f"{formato.fecha(t['plazo'])} al {formato.fecha(nuevo)}.", f"/calidad/mejora/actividades/{t['id']}")
    return rid, []


def _resolver(rid: int, t: dict, estado: str, uid: int, respuesta: str | None):
    r = get_db().q("SELECT * FROM reprogramacion_mejora WHERE id = ?", [rid])[0]
    get_db().execute(f"""UPDATE reprogramacion_mejora SET estado = ?, resuelta_por = ?, resuelta_en = {AHORA}, respuesta = ?
                         WHERE id = ?""", [estado, uid, respuesta, rid])
    if estado == "aprobada":
        get_db().execute("UPDATE actividad_mejora SET plazo = ? WHERE id = ?", [r["plazo_nuevo"], t["id"]])
        _sincronizar_accion(t["accion_id"])


def resolver_reprogramacion(r: dict, aprobar: bool, uid: int, respuesta: str = "") -> list[str]:
    """La Dirección de Carrera aprueba (cambia el plazo) o rechaza (con motivo) una reprogramación pendiente."""
    if r["estado"] != "pendiente":
        return ["Esa reprogramación ya se resolvió."]
    respuesta = _texto(respuesta, 1000)
    if not aprobar and not respuesta:
        return ["Indique el motivo del rechazo."]
    t = obtener(r["actividad_id"])
    if aprobar and t["estado"] not in ABIERTAS:
        return ["La actividad ya no está abierta: no se puede cambiar su plazo."]
    with transaccion():
        _resolver(r["id"], t, "aprobada" if aprobar else "rechazada", uid, respuesta)
    if r["solicitada_por"] and r["solicitada_por"] != uid:
        texto = (f"Se aprobó el plazo nuevo ({formato.fecha(r['plazo_nuevo'])}) de la actividad {_nombre(t)}«{t['descripcion'][:80]}»."
                 if aprobar else f"Se rechazó la reprogramación de la actividad {_nombre(t)}«{t['descripcion'][:80]}»: {respuesta}")
        notificaciones.avisar(usuarios.por_id(r["solicitada_por"]),
                              "Reprogramación " + ("aprobada" if aprobar else "rechazada"), texto,
                              f"/calidad/mejora/actividades/{t['id']}")
    return []


def tiene_actividades(uid: int) -> bool:
    return bool(get_db().q("SELECT 1 FROM actividad_mejora WHERE responsable_id = ? LIMIT 1", [uid]))

