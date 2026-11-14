"""Cortes de seguimiento del plan de mejora (PLAN §72, etapa 5).

- Un corte es **trimestral** (lo suele hacer la Comisión de calidad), **anual** (Dirección de Carrera) o **bienal** (para la
  instancia universitaria de evaluación). Lo abren, comentan y cierran quienes registran juicios de la autoevaluación
  (`registrar_juicios_calidad`: Dirección de Carrera y Comisión de calidad); lo ven quienes ven el plan.
- **Abrir congela** cada actividad a la fecha del corte (estado, avance, semáforo, último avance) con los textos copiados:
  el informe se puede volver a imprimir igual años después aunque las actividades cambien.
- Lo que **pide atención** va primero: vencidas, en riesgo y sin avance desde el corte anterior. La Comisión comenta eso;
  el resto se informa con su último avance.
- **Cerrar** guarda el informe del corte (XLSX) como evidencia del marco. Un corte cerrado no cambia; uno abierto se borra.
- Un solo corte abierto por marco a la vez.
"""
from datetime import date, timedelta

from app.calidad import actividades_mejora as am
from app.calidad import evidencias, marco, mejora
from app.comun import exportar, formato, notificaciones, usuarios
from app.comun.db import get_db, marca_tiempo, transaccion

TIPOS = {"trimestral": "Trimestral", "anual": "Anual", "bienal": "Bienal"}
ATENCION = {"vencida": "Vencida", "en_riesgo": "En riesgo", "sin_avance": "Sin avance desde el corte anterior"}
DIAS_AVISO_CORTE = 15
INDICADOR_DEL_PLAN = "Acciones del plan de mejora cumplidas en plazo"


def puede_registrar(auth, m) -> bool:
    return marco.puede(auth, "registrar_juicios_calidad", m)


def listar(mid: int) -> list[dict]:
    return get_db().q(
        """SELECT c.*, (SELECT COUNT(*) FROM corte_actividad x WHERE x.corte_id = c.id) AS actividades,
                  (SELECT COUNT(*) FROM corte_actividad x WHERE x.corte_id = c.id AND x.atencion IS NOT NULL) AS atencion,
                  (SELECT COUNT(*) FROM corte_actividad x WHERE x.corte_id = c.id AND x.atencion IS NOT NULL
                                                         AND x.comentario IS NULL) AS sin_comentar
           FROM corte_mejora c WHERE c.marco_id = ? ORDER BY c.fecha DESC, c.id DESC""", [mid])


def obtener(cid: int) -> dict | None:
    f = get_db().q("""SELECT c.*, a.nombres || ' ' || a.apellidos AS abrio, z.nombres || ' ' || z.apellidos AS cerro
                      FROM corte_mejora c LEFT JOIN usuario a ON a.id = c.abierto_por
                      LEFT JOIN usuario z ON z.id = c.cerrado_por WHERE c.id = ?""", [cid])
    return f[0] if f else None


def abierto(mid: int) -> dict | None:
    f = get_db().q("SELECT * FROM corte_mejora WHERE marco_id = ? AND estado = 'abierto'", [mid])
    return f[0] if f else None


def anterior(c: dict) -> dict | None:
    """El último corte cerrado anterior a este (por fecha)."""
    f = get_db().q("""SELECT * FROM corte_mejora WHERE marco_id = ? AND estado = 'cerrado' AND id <> ? AND fecha <= ?
                      ORDER BY fecha DESC, id DESC LIMIT 1""", [c["marco_id"], c["id"] or 0, c["fecha"]])
    return f[0] if f else None


def items(cid: int) -> list[dict]:
    """Actividades del corte: primero las que piden atención (vencidas, en riesgo, sin avance), luego por código."""
    filas = get_db().q("""SELECT x.*, u.nombres || ' ' || u.apellidos AS comento FROM corte_actividad x
                          LEFT JOIN usuario u ON u.id = x.comentado_por WHERE x.corte_id = ?""", [cid])
    orden = {"vencida": 0, "en_riesgo": 1, "sin_avance": 2, None: 3}
    return sorted(filas, key=lambda x: (orden[x["atencion"]], am._clave_codigo(x["accion_codigo"]),
                                        am._clave_codigo(x["codigo"])))


def _atencion(t: dict, previo: dict | None) -> str | None:
    if t["estado"] not in am.ABIERTAS:
        return None
    if t["semaforo"] in ("vencida", "en_riesgo"):
        return t["semaforo"]
    desde = previo["fecha"] if previo else None
    if desde and (not t["ultimo_avance"] or t["ultimo_avance"] <= desde):
        return "sin_avance"
    return None


def abrir(mid: int, tipo: str, fecha: str, uid: int, hoy: date | None = None) -> tuple[int | None, list[str]]:
    hoy = hoy or date.today()
    errores = []
    if tipo not in TIPOS:
        errores.append("Elija el tipo de corte.")
    try:
        f = date.fromisoformat(fecha or "")
    except ValueError:
        f = None
        errores.append("Indique la fecha del corte.")
    if f and f > hoy:
        errores.append("La fecha del corte no puede ser futura.")
    if abierto(mid):
        errores.append("Ya hay un corte abierto: ciérrelo antes de abrir otro.")
    acts = am.de_marco(mid, f or hoy) if not errores else []
    if not errores and not acts:
        errores.append("El plan aún no tiene actividades.")
    if errores:
        return None, errores
    with transaccion():
        cid = get_db().t.corte_mejora.insert(marco_id=mid, tipo=tipo, fecha=f.isoformat(), abierto_por=uid)["id"]
        previo = anterior({"id": cid, "marco_id": mid, "fecha": f.isoformat()})
        for t in acts:
            get_db().t.corte_actividad.insert(
                corte_id=cid, actividad_id=t["id"], accion_codigo=t["accion_codigo"], accion_titulo=t["accion_titulo"],
                prioridad=t["prioridad"], codigo=t["codigo"], descripcion=t["descripcion"],
                responsable=t["responsable"] or t["unidad_responsable"], plazo=t["plazo"], estado=t["estado"],
                avance=t["avance"], semaforo=t["semaforo"], ultimo_avance=t["ultimo_avance"],
                ultimo_texto=_ultimo_texto(t["id"]), atencion=_atencion(t, previo))
    return cid, []


def _ultimo_texto(tid: int) -> str | None:
    f = get_db().q("SELECT texto FROM avance_accion WHERE actividad_id = ? ORDER BY fecha DESC, id DESC LIMIT 1", [tid])
    return f[0]["texto"] if f else None


def comentar(c: dict, item_id: int, texto: str, uid: int) -> list[str]:
    if c["estado"] != "abierto":
        return ["El corte ya está cerrado."]
    if not get_db().q("SELECT 1 FROM corte_actividad WHERE id = ? AND corte_id = ?", [item_id, c["id"]]):
        return ["Esa actividad no está en el corte."]
    texto = (texto or "").strip()[:2000] or None
    get_db().t.corte_actividad.update({"comentario": texto, "comentado_por": uid if texto else None,
                                       "comentado_en": marca_tiempo() if texto else None}, item_id)
    return []


def resumen(cid: int) -> dict:
    """Cifras por semáforo y por prioridad, y las del corte anterior para comparar."""
    def cifras(i):
        return {"semaforo": {s: sum(x["semaforo"] == s for x in i) for s in am.SEMAFOROS},
                "prioridad": {p: sum(x["prioridad"] == p for x in i) for p in mejora.PRIORIDADES},
                "avance": round(sum(x["avance"] or 0 for x in i if x["estado"] != "cancelada")
                                / max(1, sum(x["estado"] != "cancelada" for x in i)))}
    c = obtener(cid)
    previo = anterior(c)
    return {"actual": cifras(items(cid)), "anterior": cifras(items(previo["id"])) if previo else None, "previo": previo}


def reprogramaciones_del_periodo(c: dict) -> list[dict]:
    previo = anterior(c)
    desde = previo["fecha"] if previo else "0000-00-00"
    return get_db().q(
        """SELECT r.*, t.codigo, t.descripcion, a.codigo AS accion_codigo FROM reprogramacion_mejora r
           JOIN actividad_mejora t ON t.id = r.actividad_id JOIN accion_mejora a ON a.id = t.accion_id
           WHERE a.marco_id = ? AND substr(r.solicitada_en, 1, 10) > ? AND substr(r.solicitada_en, 1, 10) <= ?
           ORDER BY r.solicitada_en""", [c["marco_id"], desde, c["fecha"]])


def a_xlsx(cid: int) -> bytes:
    c = obtener(cid)
    r = resumen(cid)
    filas = [{"acción": x["accion_codigo"] or "", "título de la acción": x["accion_titulo"],
              "prioridad": am.PRIORIDAD_P[x["prioridad"]], "actividad": x["codigo"] or "", "descripción": x["descripcion"],
              "responsable": x["responsable"] or "", "plazo": x["plazo"], "estado": am.ESTADOS[x["estado"]],
              "avance (%)": "" if x["avance"] is None else x["avance"], "semáforo": am.SEMAFOROS[x["semaforo"]],
              "último avance": x["ultimo_avance"] or "", "qué se hizo": x["ultimo_texto"] or "",
              "pide atención": ATENCION.get(x["atencion"], ""), "comentario": x["comentario"] or ""} for x in items(cid)]
    cifras = [{"cifra": am.SEMAFOROS[s], "este corte": n,
               "corte anterior": r["anterior"]["semaforo"][s] if r["anterior"] else ""}
              for s, n in r["actual"]["semaforo"].items()]
    cifras += [{"cifra": f"Prioridad {am.PRIORIDAD_P[p]}", "este corte": n,
                "corte anterior": r["anterior"]["prioridad"][p] if r["anterior"] else ""}
               for p, n in r["actual"]["prioridad"].items()]
    cifras.append({"cifra": "Avance promedio (%)", "este corte": r["actual"]["avance"],
                   "corte anterior": r["anterior"]["avance"] if r["anterior"] else ""})
    reps = [{"actividad": f"{x['accion_codigo'] or ''} {x['codigo'] or ''}".strip(), "descripción": x["descripcion"],
             "plazo anterior": x["plazo_anterior"], "plazo nuevo": x["plazo_nuevo"], "causa": x["causa"],
             "estado": am.ESTADOS_REPROGRAMACION[x["estado"]]} for x in reprogramaciones_del_periodo(c)]
    datos = [{"dato": "Corte", "valor": f"{TIPOS[c['tipo']]} al {c['fecha']}"},
             {"dato": "Conclusión", "valor": c["conclusion"] or ""}]
    return exportar.a_xlsx({"Corte": datos, "Resumen": cifras, "Actividades": filas, "Reprogramaciones": reps})


def criterio_propuesto(mid: int) -> int | None:
    """Criterio del marco donde va el informe del corte: el del indicador del plan de mejora, si existe."""
    return next((i["criterio_id"] for i in mejora.indicadores_del_marco(mid) if i["nombre"] == INDICADOR_DEL_PLAN), None)


def cerrar(c: dict, conclusion: str, criterio_id: str, uid: int) -> list[str]:
    if c["estado"] != "abierto":
        return ["El corte ya está cerrado."]
    validos = {x["id"] for x in evidencias.criterios_del_marco(c["marco_id"])}
    cr = int(criterio_id) if str(criterio_id).isdigit() and int(criterio_id) in validos else None
    if cr is None:
        return ["Elija el criterio del marco al que se agrega el informe como evidencia."]
    with transaccion():
        get_db().t.corte_mejora.update({"conclusion": (conclusion or "").strip()[:4000] or None}, c["id"])
        nombre = f"corte-{c['tipo']}-{c['fecha']}.xlsx"
        eid = evidencias.crear(c["marco_id"], "informe",
                               {"titulo": f"Plan de mejora: corte {c['tipo']} al {formato.fecha(c['fecha'])}",
                                "descripcion": "Informe de seguimiento del plan de mejora generado al cerrar el corte.",
                                "fecha": c["fecha"], "vigente_hasta": None, "url": None, "criterios": [cr]},
                               uid, nombre, a_xlsx(c["id"]), "corte_mejora", f"corte {c['id']}")
        get_db().t.corte_mejora.update({"estado": "cerrado", "cerrado_por": uid, "cerrado_en": marca_tiempo(),
                                        "evidencia_id": eid}, c["id"])
    return []


def eliminar(c: dict) -> bool:
    if c["estado"] != "abierto":
        return False
    get_db().t.corte_mejora.delete(c["id"])
    return True


# --- Avisos (mantenimiento diario) ----------------------------------------------------------------------------------------

def fin_de_trimestre(hoy: date) -> date:
    mes = ((hoy.month - 1) // 3 + 1) * 3
    return (date(hoy.year + (mes == 12), 1 if mes == 12 else mes + 1, 1)) - timedelta(days=1)


def avisar(hoy: date | None = None) -> int:
    """Una vez por actividad, plazo y umbral: al responsable, 30 y 7 días antes del plazo; y, 15 días antes del fin de
    cada trimestre (cuando suele hacerse el corte), si su actividad abierta no tiene avance desde el último corte."""
    hoy = hoy or date.today()
    db, n = get_db(), 0

    def una_vez(clave, uid, asunto, texto, url):
        nonlocal n
        if not uid or db.q("SELECT 1 FROM aviso_enviado WHERE clave = ?", [clave]):
            return
        db.t.aviso_enviado.insert(clave=clave)
        notificaciones.avisar(usuarios.por_id(uid), asunto, texto, url)
        n += 1
    filas = db.q("""SELECT t.*, a.marco_id FROM actividad_mejora t JOIN accion_mejora a ON a.id = t.accion_id
                    WHERE t.estado IN ('pendiente', 'en_curso') AND t.responsable_id IS NOT NULL""")
    fin = fin_de_trimestre(hoy)
    for t in filas:
        url = f"/calidad/mejora/actividades/{t['id']}"
        nombre = f"{t['codigo'] + ' ' if t['codigo'] else ''}«{t['descripcion'][:80]}»"
        dias = (date.fromisoformat(t["plazo"]) - hoy).days
        for umbral in (30, 7):
            if 0 <= dias <= umbral:
                una_vez(f"actividad:{t['id']}:{umbral}:{t['plazo']}", t["responsable_id"], "Actividad del plan por vencer",
                        f"La actividad {nombre} vence en {dias} día(s). Registre su avance o pida una reprogramación.", url)
                break
        if 0 <= (fin - hoy).days <= DIAS_AVISO_CORTE:
            ultimo = db.q("SELECT MAX(fecha) f FROM corte_mejora WHERE marco_id = ? AND estado = 'cerrado'",
                          [t["marco_id"]])[0]["f"]
            avance = db.q("SELECT MAX(fecha) f FROM avance_accion WHERE actividad_id = ?", [t["id"]])[0]["f"]
            if ultimo and (not avance or avance <= ultimo):
                una_vez(f"actividad:{t['id']}:corte:{fin}", t["responsable_id"], "Corte del plan de mejora",
                        f"El {fin.day}/{fin.month}/{fin.year} cierra el trimestre y la actividad {nombre} no tiene avances "
                        "desde el último corte. Regístrelo antes, con su evidencia.", url)
    return n


# --- Calendario personal (PLAN §72, etapa 6) -----------------------------------------------------------------------------

def eventos(uid: int, desde: date, hasta: date) -> list[dict]:
    """Los plazos de las actividades abiertas a cargo de la persona y, si tiene alguna, el fin de cada trimestre (cuando
    suele hacerse el corte). Mismo formato que los demás calendarios: {fecha, hora, titulo, tipo, detalle, href}."""
    acts = am.de_responsable(uid)
    if not acts:
        return []
    salida = [{"fecha": t["plazo"], "hora": "", "tipo": "mejora", "href": f"/calidad/mejora/actividades/{t['id']}",
               "titulo": f"Vence la actividad {t['codigo'] + ' ' if t['codigo'] else ''}del plan de mejora",
               "detalle": am.titulo(t["descripcion"])[:100]} for t in acts]
    f = fin_de_trimestre(desde)
    while f <= hasta:
        salida.append({"fecha": f.isoformat(), "hora": "", "tipo": "mejora", "href": "/calidad/mejora",
                       "titulo": "Fin del trimestre: corte del plan de mejora",
                       "detalle": "Registre antes el avance de sus actividades"})
        f = fin_de_trimestre(f + timedelta(days=1))
    d, h = desde.isoformat(), hasta.isoformat()
    return [e for e in salida if d <= e["fecha"] <= h]
