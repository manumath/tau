"""Plan de mejora y evaluación externa (PLAN §57, etapa 6).

Cada acción nace de una debilidad de la autoevaluación, de una recomendación de una evaluación externa o de otra fuente;
tiene criterio, responsable, plazo, indicador y meta, y se sigue con avances (con evidencia si la hay). Los vencimientos
llegan como avisos al responsable (30 días antes y al vencer) y, al vencer, también a la Dirección de Carrera.
"""
from datetime import date, timedelta

from app.calidad import autoevaluacion as ae
from app.calidad import evidencias, marco
from app.comun import exportar, notificaciones, permisos, usuarios
from app.comun.db import get_db, transaccion

ORIGENES = {"autoevaluacion": "Autoevaluación", "externa": "Evaluación externa", "otro": "Otro"}
ESTADOS = {"pendiente": "Pendiente", "en_curso": "En curso", "cumplida": "Cumplida", "cancelada": "Cancelada"}
PRIORIDADES = {"alta": "Alta", "media": "Media", "baja": "Baja"}
TIPOS_EXTERNA = {"acreditacion": "Acreditación", "pares": "Evaluación por pares", "otra": "Otra"}
ABIERTAS = ("pendiente", "en_curso")
DIAS_AVISO = 30
LARGO = 5_000


def _texto(v, largo=LARGO) -> str | None:
    return (v or "").strip()[:largo] or None


def _fecha(texto: str | None, campo: str, errores: list, obligatoria=False) -> str | None:
    texto = (texto or "").strip()
    if not texto:
        if obligatoria:
            errores.append(f"Indique {campo}.")
        return None
    try:
        return date.fromisoformat(texto).isoformat()
    except ValueError:
        errores.append(f"{campo[0].upper()}{campo[1:]} no es una fecha válida.")
        return texto


# --- Responsables -----------------------------------------------------------------------------------------------

def responsables() -> list[dict]:
    """Cuentas activas del personal (no las de estudiante)."""
    return get_db().q("""SELECT id, nombres, apellidos, email FROM usuario WHERE activo = 1
                         AND id NOT IN (SELECT usuario_id FROM cuenta_estudiante) ORDER BY apellidos, nombres""")


def tiene_acciones(uid: int) -> bool:
    return bool(get_db().q("SELECT 1 FROM accion_mejora WHERE responsable_id = ? LIMIT 1", [uid]))


# --- Acciones ---------------------------------------------------------------------------------------------------

_SELECT = """SELECT a.*, c.codigo AS criterio_codigo, c.nombre AS criterio_nombre,
                    u.nombres || ' ' || u.apellidos AS responsable, i.codigo AS indicador_codigo,
                    i.nombre AS indicador_nombre, i.unidad_medida,
                    (SELECT porcentaje FROM avance_accion v WHERE v.accion_id = a.id AND v.porcentaje IS NOT NULL
                     ORDER BY v.fecha DESC, v.id DESC LIMIT 1) AS porcentaje,
                    (SELECT COUNT(*) FROM avance_accion v WHERE v.accion_id = a.id) AS avances
             FROM accion_mejora a LEFT JOIN criterio_calidad c ON c.id = a.criterio_id
             LEFT JOIN usuario u ON u.id = a.responsable_id LEFT JOIN indicador_calidad i ON i.id = a.indicador_id"""


def _marcar(filas: list[dict]) -> list[dict]:
    hoy = date.today().isoformat()
    for f in filas:
        f["vencida"] = f["estado"] in ABIERTAS and f["plazo"] < hoy
        f["en_plazo"] = f["estado"] == "cumplida" and f["cumplida_en"] <= f["plazo"]
    return filas


def acciones(mid: int, estado: str = "", criterio: int | None = None, responsable: int | None = None) -> list[dict]:
    """estado: '' (todas), 'abiertas', 'vencidas' o uno de ESTADOS."""
    sql, p = _SELECT + " WHERE a.marco_id = ?", [mid]
    if criterio:
        sql += " AND a.criterio_id = ?"
        p.append(criterio)
    if responsable:
        sql += " AND a.responsable_id = ?"
        p.append(responsable)
    if estado in ESTADOS:
        sql += " AND a.estado = ?"
        p.append(estado)
    elif estado in ("abiertas", "vencidas"):
        sql += " AND a.estado IN ('pendiente', 'en_curso')"
    filas = _marcar(get_db().q(sql + """ ORDER BY a.estado IN ('cumplida', 'cancelada'), a.plazo,
                                       CASE a.prioridad WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, a.id""", p))
    return [f for f in filas if f["vencida"]] if estado == "vencidas" else filas


def obtener(aid: int) -> dict | None:
    f = get_db().q(_SELECT + " WHERE a.id = ?", [aid])
    if not f:
        return None
    a = _marcar(f)[0]
    a["lista_avances"] = get_db().q(
        """SELECT v.*, u.nombres || ' ' || u.apellidos AS por, e.titulo AS evidencia_titulo FROM avance_accion v
           LEFT JOIN usuario u ON u.id = v.registrado_por LEFT JOIN evidencia_calidad e ON e.id = v.evidencia_id
           WHERE v.accion_id = ? ORDER BY v.fecha DESC, v.id DESC""", [aid])
    a["recomendacion"] = (get_db().q("""SELECT r.texto, x.organismo, x.id AS evaluacion_id FROM recomendacion_externa r
                                        JOIN evaluacion_externa x ON x.id = r.evaluacion_id WHERE r.id = ?""",
                                     [a["recomendacion_id"]]) or [None])[0] if a["recomendacion_id"] else None
    return a


def resumen(mid: int) -> dict:
    todas = acciones(mid)
    con_plazo = [a for a in todas if a["estado"] == "cumplida" or (a["estado"] in ABIERTAS and a["vencida"])]
    return {"abiertas": sum(a["estado"] in ABIERTAS for a in todas), "vencidas": sum(a["vencida"] for a in todas),
            "cumplidas": sum(a["estado"] == "cumplida" for a in todas),
            "en_plazo": sum(a["en_plazo"] for a in todas), "con_plazo": len(con_plazo)}


def validar(d: dict, mid: int) -> tuple[dict, list[str]]:
    errores: list[str] = []
    x = {"titulo": _texto(d.get("titulo"), 200), "descripcion": _texto(d.get("descripcion")),
         "origen": d.get("origen") or "otro", "debilidad": _texto(d.get("debilidad")),
         "prioridad": d.get("prioridad") or "media"}
    if not x["titulo"]:
        errores.append("Indique la acción.")
    if x["origen"] not in ORIGENES:
        errores.append("Elija el origen.")
    if x["prioridad"] not in PRIORIDADES:
        errores.append("Elija la prioridad.")
    x["plazo"] = _fecha(d.get("plazo"), "el plazo", errores, obligatoria=True)

    def entero(clave, validos, texto):
        v = str(d.get(clave) or "").strip()
        if not v:
            return None
        if v.isdigit() and int(v) in validos:
            return int(v)
        errores.append(texto)
        return None
    x["criterio_id"] = entero("criterio_id", {c["id"] for c in evidencias.criterios_del_marco(mid)},
                              "Elija un criterio del marco.")
    x["responsable_id"] = entero("responsable_id", {u["id"] for u in responsables()}, "Elija un responsable de la lista.")
    x["indicador_id"] = entero("indicador_id", {i["id"] for i in indicadores_del_marco(mid)},
                               "Elija un indicador del marco.")
    x["autoevaluacion_id"] = entero("autoevaluacion_id", {a["id"] for a in ae.listar(mid)}, "Autoevaluación desconocida.")
    x["recomendacion_id"] = entero("recomendacion_id", {r["id"] for r in recomendaciones_del_marco(mid)},
                                   "Recomendación desconocida.")
    meta = str(d.get("meta") or "").strip().replace(",", ".")
    x["meta"] = None
    if meta:
        try:
            x["meta"] = float(meta)
        except ValueError:
            errores.append("La meta es un número.")
    if x["meta"] is not None and not x["indicador_id"]:
        errores.append("Una meta necesita un indicador.")
    if not x["responsable_id"] and "Elija un responsable de la lista." not in errores:
        errores.append("Indique el responsable.")
    return x, errores


CAMPOS = ("titulo", "descripcion", "origen", "debilidad", "prioridad", "plazo", "criterio_id", "responsable_id",
          "indicador_id", "meta", "autoevaluacion_id", "recomendacion_id")


def crear(mid: int, x: dict, uid: int) -> int:
    return get_db().t.accion_mejora.insert(marco_id=mid, creada_por=uid, **{k: x[k] for k in CAMPOS})["id"]


def actualizar(aid: int, x: dict):
    get_db().t.accion_mejora.update({k: x[k] for k in CAMPOS}, aid)


def cumplir(a: dict, fecha: str) -> list[str]:
    errores: list[str] = []
    f = _fecha(fecha, "la fecha en que se cumplió", errores, obligatoria=True)
    if not errores and f > date.today().isoformat():
        errores.append("La fecha en que se cumplió no puede ser futura.")
    if errores:
        return errores
    get_db().execute("""UPDATE accion_mejora SET estado = 'cumplida', cumplida_en = ?, motivo_cancelacion = NULL
                        WHERE id = ?""", [f, a["id"]])
    return []


def cancelar(a: dict, motivo: str) -> list[str]:
    motivo = _texto(motivo, 500)
    if not motivo:
        return ["Indique el motivo de la cancelación."]
    get_db().execute("""UPDATE accion_mejora SET estado = 'cancelada', motivo_cancelacion = ?, cumplida_en = NULL
                        WHERE id = ?""", [motivo, a["id"]])
    return []


def reabrir(a: dict):
    nuevo = "en_curso" if a["avances"] else "pendiente"
    get_db().execute("""UPDATE accion_mejora SET estado = ?, cumplida_en = NULL, motivo_cancelacion = NULL
                        WHERE id = ?""", [nuevo, a["id"]])


def eliminar(a: dict) -> bool:
    """Solo una acción sin avances (las demás se cancelan, con su motivo)."""
    if a["avances"]:
        return False
    get_db().execute("DELETE FROM accion_mejora WHERE id = ?", [a["id"]])
    return True


# --- Avances ----------------------------------------------------------------------------------------------------

def validar_avance(d: dict, mid: int) -> tuple[dict, list[str]]:
    errores: list[str] = []
    x = {"texto": _texto(d.get("texto")), "fecha": _fecha(d.get("fecha") or date.today().isoformat(), "la fecha",
                                                          errores, obligatoria=True)}
    if not x["texto"]:
        errores.append("Describa el avance.")
    if isinstance(x["fecha"], str) and not errores and x["fecha"] > date.today().isoformat():
        errores.append("La fecha del avance no puede ser futura.")
    p = str(d.get("porcentaje") or "").strip()
    x["porcentaje"] = None
    if p:
        if p.isdigit() and 0 <= int(p) <= 100:
            x["porcentaje"] = int(p)
        else:
            errores.append("El porcentaje va de 0 a 100.")
    e = str(d.get("evidencia_id") or "").strip()
    x["evidencia_id"] = None
    if e:
        if e.isdigit() and int(e) in {v["id"] for v in evidencias.listar(mid)}:
            x["evidencia_id"] = int(e)
        else:
            errores.append("Elija una evidencia del repositorio.")
    return x, errores


def registrar_avance(a: dict, x: dict, uid: int) -> int:
    with transaccion():
        vid = get_db().t.avance_accion.insert(accion_id=a["id"], registrado_por=uid, **x)["id"]
        if a["estado"] == "pendiente":
            get_db().execute("UPDATE accion_mejora SET estado = 'en_curso' WHERE id = ?", [a["id"]])
    return vid


def avance(vid: int) -> dict | None:
    f = get_db().q("SELECT * FROM avance_accion WHERE id = ?", [vid])
    return f[0] if f else None


def eliminar_avance(vid: int):
    get_db().execute("DELETE FROM avance_accion WHERE id = ?", [vid])


# --- Debilidades de la autoevaluación ---------------------------------------------------------------------------

def debilidades(aev: dict) -> list[dict]:
    """Las debilidades de la autoevaluación, una por línea de cada juicio, con las acciones que ya salieron de ellas."""
    js = ae.juicios(aev["id"])
    hechas: dict[tuple, list] = {}
    for a in get_db().q("""SELECT id, titulo, criterio_id, debilidad FROM accion_mejora WHERE autoevaluacion_id = ?""",
                        [aev["id"]]):
        hechas.setdefault((a["criterio_id"], (a["debilidad"] or "").strip()), []).append(a)
    res = []
    for c in evidencias.criterios_del_marco(aev["marco_id"]):
        j = js.get(c["id"])
        for linea in (j["debilidades"] or "").splitlines() if j else []:
            texto = linea.strip(" -•\t")
            if texto:
                res.append({"criterio": c, "texto": texto, "nivel": j["nivel_nombre"],
                            "acciones": hechas.get((c["id"], texto), [])})
    return res


# --- Evaluaciones externas --------------------------------------------------------------------------------------

def externas(mid: int) -> list[dict]:
    return get_db().q(
        """SELECT x.*, (SELECT COUNT(*) FROM recomendacion_externa r WHERE r.evaluacion_id = x.id) AS recomendaciones
           FROM evaluacion_externa x WHERE x.marco_id = ? ORDER BY COALESCE(x.fecha_dictamen, x.fecha_visita) DESC, x.id DESC""",
        [mid])


def externa(xid: int) -> dict | None:
    f = get_db().q("""SELECT x.*, e.titulo AS evidencia_titulo FROM evaluacion_externa x
                      LEFT JOIN evidencia_calidad e ON e.id = x.evidencia_id WHERE x.id = ?""", [xid])
    if not f:
        return None
    x = f[0]
    x["lista_recomendaciones"] = get_db().q(
        """SELECT r.*, c.codigo AS criterio_codigo, c.nombre AS criterio_nombre,
                  (SELECT COUNT(*) FROM accion_mejora a WHERE a.recomendacion_id = r.id) AS acciones
           FROM recomendacion_externa r LEFT JOIN criterio_calidad c ON c.id = r.criterio_id
           WHERE r.evaluacion_id = ? ORDER BY r.id""", [xid])
    return x


def recomendaciones_del_marco(mid: int) -> list[dict]:
    return get_db().q("""SELECT r.* FROM recomendacion_externa r JOIN evaluacion_externa x ON x.id = r.evaluacion_id
                         WHERE x.marco_id = ?""", [mid])


def recomendacion(rid: int) -> dict | None:
    f = get_db().q("""SELECT r.*, x.marco_id FROM recomendacion_externa r JOIN evaluacion_externa x
                      ON x.id = r.evaluacion_id WHERE r.id = ?""", [rid])
    return f[0] if f else None


def validar_externa(d: dict, mid: int) -> tuple[dict, list[str]]:
    errores: list[str] = []
    x = {"organismo": _texto(d.get("organismo"), 200), "tipo": d.get("tipo") or "acreditacion",
         "resultado": _texto(d.get("resultado"), 500), "nota": _texto(d.get("nota"))}
    if not x["organismo"]:
        errores.append("Indique el organismo evaluador.")
    if x["tipo"] not in TIPOS_EXTERNA:
        errores.append("Elija el tipo de evaluación.")
    for k, t in (("fecha_visita", "la fecha de la visita"), ("fecha_dictamen", "la fecha del dictamen"),
                 ("vigente_hasta", "la vigencia")):
        x[k] = _fecha(d.get(k), t, errores)
    e = str(d.get("evidencia_id") or "").strip()
    x["evidencia_id"] = None
    if e:
        if e.isdigit() and int(e) in {v["id"] for v in evidencias.listar(mid)}:
            x["evidencia_id"] = int(e)
        else:
            errores.append("Elija una evidencia del repositorio.")
    return x, errores


def crear_externa(mid: int, x: dict, uid: int) -> int:
    return get_db().t.evaluacion_externa.insert(marco_id=mid, creada_por=uid, **x)["id"]


def actualizar_externa(xid: int, x: dict):
    get_db().t.evaluacion_externa.update(x, xid)


def eliminar_externa(x: dict) -> bool:
    """Solo si ninguna de sus recomendaciones originó acciones."""
    if any(r["acciones"] for r in x["lista_recomendaciones"]):
        return False
    get_db().execute("DELETE FROM evaluacion_externa WHERE id = ?", [x["id"]])
    return True


def agregar_recomendaciones(xid: int, texto: str, criterio_id: int | None) -> int:
    """Una recomendación por línea; devuelve cuántas se agregaron."""
    n = 0
    for linea in (texto or "").splitlines():
        t = linea.strip(" -•\t")[:LARGO]
        if t:
            get_db().t.recomendacion_externa.insert(evaluacion_id=xid, texto=t, criterio_id=criterio_id)
            n += 1
    return n


def eliminar_recomendacion(r: dict) -> bool:
    if get_db().q("SELECT 1 FROM accion_mejora WHERE recomendacion_id = ? LIMIT 1", [r["id"]]):
        return False
    get_db().execute("DELETE FROM recomendacion_externa WHERE id = ?", [r["id"]])
    return True


# --- Indicadores del marco para elegir -----------------------------------------------------------------------------

def indicadores_del_marco(mid: int) -> list[dict]:
    return [i for d in marco.arbol(mid, inactivos=False) for c in d["criterios"] for i in c["indicadores"]]


# --- Avisos de vencimiento ------------------------------------------------------------------------------------------

def avisar_vencimientos(hoy: date | None = None) -> int:
    """Una vez por acción, plazo y umbral: 30 días antes al responsable; al vencer, al responsable y a la Dirección de
    Carrera de la unidad del marco. Devuelve cuántos avisos se registraron."""
    hoy = hoy or date.today()
    db, n = get_db(), 0
    filas = db.q("""SELECT a.*, m.unidad_id FROM accion_mejora a JOIN marco_calidad m ON m.id = a.marco_id
                     WHERE a.estado IN ('pendiente', 'en_curso') AND a.plazo <= ?""",
                 [(hoy + timedelta(days=DIAS_AVISO)).isoformat()])
    for a in filas:
        vencida = a["plazo"] < hoy.isoformat()
        clave = f"mejora:{a['id']}:{'vencida' if vencida else 'proxima'}:{a['plazo']}"
        if db.q("SELECT 1 FROM aviso_enviado WHERE clave = ?", [clave]):
            continue
        db.t.aviso_enviado.insert(clave=clave)
        url = f"/calidad/mejora/acciones/{a['id']}"
        plazo = f"{a['plazo'][8:10]}/{a['plazo'][5:7]}/{a['plazo'][:4]}"
        if vencida:
            asunto, texto = "Acción de mejora vencida", f"La acción «{a['titulo']}» venció el {plazo} sin cumplirse."
        else:
            asunto, texto = "Acción de mejora por vencer", f"La acción «{a['titulo']}» vence el {plazo}."
        destinatarios = {a["responsable_id"]} if a["responsable_id"] else set()
        if vencida:
            destinatarios |= {u["id"] for u in permisos.con_rol("direccion_carrera", a["unidad_id"])}
        for uid in destinatarios:
            notificaciones.avisar(usuarios.por_id(uid), asunto, texto + " Registre su avance o actualice su estado.", url)
            n += 1
    return n


# --- Exportación ----------------------------------------------------------------------------------------------

def a_xlsx(mid: int) -> bytes:
    filas = [{"titulo": a["titulo"], "criterio": a["criterio_codigo"] or "", "origen": ORIGENES[a["origen"]],
              "debilidad o recomendación": a["debilidad"] or "", "responsable": a["responsable"] or "",
              "plazo": a["plazo"], "prioridad": PRIORIDADES[a["prioridad"]], "estado": ESTADOS[a["estado"]],
              "vencida": "sí" if a["vencida"] else "", "cumplida el": a["cumplida_en"] or "",
              "en plazo": "sí" if a["en_plazo"] else "", "avance (%)": "" if a["porcentaje"] is None else a["porcentaje"],
              "indicador": a["indicador_codigo"] or "", "meta": "" if a["meta"] is None else a["meta"],
              "motivo de cancelación": a["motivo_cancelacion"] or ""} for a in acciones(mid)]
    avances = [{"accion": a["titulo"], "fecha": v["fecha"], "avance": v["texto"],
                "porcentaje": "" if v["porcentaje"] is None else v["porcentaje"], "evidencia": v["evidencia_titulo"] or "",
                "por": v["por"] or ""} for x in acciones(mid) if x["avances"] for a in [obtener(x["id"])]
               for v in a["lista_avances"]]
    ext = []
    for y in externas(mid):
        x = externa(y["id"])
        base = {"organismo": x["organismo"], "tipo": TIPOS_EXTERNA[x["tipo"]], "visita": x["fecha_visita"] or "",
                "dictamen": x["fecha_dictamen"] or "", "resultado": x["resultado"] or "",
                "vigente hasta": x["vigente_hasta"] or ""}
        for r in x["lista_recomendaciones"] or [{"texto": "", "criterio_codigo": ""}]:
            ext.append({**base, "recomendación": r["texto"], "criterio": r["criterio_codigo"] or ""})
    return exportar.a_xlsx({"Acciones": filas, "Avances": avances, "Evaluaciones externas": ext})
