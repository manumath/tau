"""Resultado y designación de los auxiliares (PLAN §70, etapa 5), según el Reglamento Específico de Auxiliares Académicos del Pregrado
(Res. HCU 424/2023, mod. 364/2025). Solo para convocatorias hechas con ese reglamento.

- **Invitados (arts. 6 y 13):** la asignatura que no se cubrió tras dos convocatorias consecutivas pasa a invitación: primero quienes obtuvieron
  de 51 a 55 puntos en la segunda convocatoria (por puntaje) y, si no aceptan, los mejores estudiantes de la materia, que da Kardex (TAU solo
  registra a quién se invitó, con su nota, y qué respondió).
- **Designaciones (arts. 23, 25 y 26):** un auxiliar titular o invitado por plaza. De los ganadores se reciben, en 72 horas, el certificado de
  no tener deudas, el de no tener proceso ejecutoriado y el registro en el SIGEP; el memorándum rige desde el 1 o el 15 de un mes.
- **Informe final (art. 22):** en 10 días de concluido el proceso, la comisión lo entrega al Consejo de Carrera, que emite la resolución de
  resultados; la Facultad la homologa. **Documentación (art. 27):** seis documentos que la Dirección entrega a Bienestar Social.

Los plazos solo advierten: nada se bloquea. TAU no guarda notas de Kardex: los «mejores estudiantes» los certifica Kardex y aquí solo se anota."""
from datetime import date, datetime, timedelta, timezone

from app.comun import formato, notificaciones
from app.comun.db import AHORA, get_db, transaccion
from app.servicios import auxiliaturas as aux

INVITADO_DESDE = 51                 # art. 6, b): de 51 a 55 puntos
PLAZO_DOCUMENTOS_HORAS = 72         # art. 23: documentos de los ganadores
PLAZO_INFORME_DIAS = 10             # art. 22
PLAZO_DOCUMENTACION_DIAS = 15       # art. 27
CATEGORIAS = {"titular": "Auxiliar titular", "invitado": "Auxiliar invitado"}
ORIGENES = {"postulante": "Postulante con 51 a 55 puntos", "mejor_estudiante": "Mejor estudiante de la materia"}
ESTADOS_INVITACION = {"pendiente": "Pendiente", "aceptada": "Aceptada", "rechazada": "No aceptó"}
DOCUMENTOS_GANADORES = {"cert_deudas": "Certificación de no tener deudas económicas con la Carrera y la Facultad",
                        "cert_procesos": "Certificado de la sala de procesos de no tener proceso ejecutoriado",
                        "sigep": "Registro de beneficiario en el SIGEP"}
DOCUMENTACION = {"res_hcf_convocatoria": "Resolución del Consejo Facultativo que aprueba la convocatoria",
                 "res_hcc_nomina": "Resolución del Consejo de Carrera que aprueba la nómina de ganadores",
                 "res_hcf_homologacion": "Resolución del Consejo Facultativo que homologa la del Consejo de Carrera",
                 "memorandums": "Memorándums de designación", "formularios": "Formularios de evaluación",
                 "requisitos": "Requisitos de admisión"}


def aplica(c: dict | None) -> bool:
    return aux.usa_formularios(c)


def _local(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


def concluido_en(cid: int) -> datetime | None:
    """Cuándo concluyó el proceso (hora local): el cierre de la última fase de la convocatoria."""
    utc = aux.resultados_publicados_en(cid)
    return _local(utc) if utc else None


def _fecha_valida(texto: str | None) -> tuple[str | None, bool]:
    texto = (texto or "").strip()
    if not texto:
        return None, True
    try:
        return date.fromisoformat(texto).isoformat(), True
    except ValueError:
        return None, False


# --- Invitaciones (arts. 6 y 13) -------------------------------------------------------------------------------------------------

def invitaciones(iid: int) -> list[dict]:
    return get_db().q("""SELECT v.*, pe.nombres, pe.apellidos, e.registro_universitario AS ru FROM invitacion_auxiliatura v
                         JOIN persona_externa pe ON pe.id = v.externo_id LEFT JOIN estudiante e ON e.externo_id = v.externo_id
                         WHERE v.item_id = ? ORDER BY v.orden""", [iid])


def cubiertas(it: dict) -> int:
    """Plazas ocupadas: los titulares del concurso y los invitados que aceptaron."""
    t = sum(p["estado"] == "titular" for p in aux.en_concurso(it["id"]))
    return t + get_db().q("SELECT COUNT(*) n FROM invitacion_auxiliatura WHERE item_id = ? AND estado = 'aceptada'", [it["id"]])[0]["n"]


def puede_invitar(it: dict) -> bool:
    """El ítem concluyó en una segunda convocatoria (dos consecutivas) y aún tiene plazas sin cubrir."""
    c = aux.obtener(it["convocatoria_id"])
    return (aplica(c) and c["numero"] == 2 and it["fase"] == "concluido" and cubiertas(it) < it["plazas"]
            and not any(p["estado"] == "empate" for p in aux.en_concurso(it["id"])))


def candidatos(it: dict) -> list[dict]:
    """Postulantes de este ítem que obtuvieron de 51 a 55 puntos, por puntaje."""
    res = []
    for p in aux.en_concurso(it["id"]):
        total = aux.total(p["id"])
        if p["estado"] == "no_seleccionada" and INVITADO_DESDE <= total < aux.PUNTAJE_TITULAR:
            res.append({**p, "total": total})
    return sorted(res, key=lambda p: (-p["total"], p["apellidos"], p["nombres"]))


def _por_invitar(it: dict) -> list[dict]:
    ya = {v["externo_id"] for v in invitaciones(it["id"])}
    return [p for p in candidatos(it) if p["externo_id"] not in ya]


def _siguiente_orden(iid: int) -> int:
    return get_db().q("SELECT COALESCE(MAX(orden), 0) + 1 n FROM invitacion_auxiliatura WHERE item_id = ?", [iid])[0]["n"]


def _avisar(externo_id: int, asunto: str, texto: str):
    from app.comun import estudiantes
    notificaciones.avisar(estudiantes.usuario_de(externo_id), asunto, texto, "/estudiante/auxiliaturas")


def generar_invitaciones(it: dict, uid: int) -> list[str]:
    """Invita, por puntaje, a quienes obtuvieron de 51 a 55 puntos en la segunda convocatoria."""
    if not puede_invitar(it):
        return ["Solo se invita en una segunda convocatoria concluida que dejó plazas sin cubrir."]
    nuevos = _por_invitar(it)
    if not nuevos:
        return ["No hay postulantes con 51 a 55 puntos por invitar."]
    with transaccion():
        for p in nuevos:
            get_db().t.invitacion_auxiliatura.insert(item_id=it["id"], externo_id=p["externo_id"], origen="postulante",
                                                     orden=_siguiente_orden(it["id"]), puntaje=p["total"], registrada_por=uid)
    for p in nuevos:
        _avisar(p["externo_id"], f"Invitación a ser auxiliar: {it['titulo']}",
                f"Obtuvo {formato.numero(p['total'])} puntos en el concurso: puede aceptar o no la invitación.")
    return []


def invitar_mejor_estudiante(it: dict, ru: str, nota: str, uid: int) -> list[str]:
    """Registra la invitación a un mejor estudiante de la materia (lo da Kardex). Solo cuando ya se invitó a los de 51 a 55 puntos y
    ninguno aceptó ni queda pendiente (art. 6, b)."""
    if not puede_invitar(it):
        return ["Solo se invita en una segunda convocatoria concluida que dejó plazas sin cubrir."]
    if _por_invitar(it) or any(v["estado"] == "pendiente" and v["origen"] == "postulante" for v in invitaciones(it["id"])):
        return ["Primero se invita a quienes obtuvieron de 51 a 55 puntos; a los mejores estudiantes se les invita si ellos no aceptan."]
    est = get_db().q("""SELECT e.externo_id, pe.nombres, pe.apellidos FROM estudiante e JOIN persona_externa pe ON pe.id = e.externo_id
                        WHERE e.registro_universitario = ?""", [(ru or "").strip()])
    if not est:
        return ["No hay un estudiante con ese registro universitario."]
    ext = est[0]["externo_id"]
    if get_db().q("SELECT 1 FROM invitacion_auxiliatura WHERE item_id = ? AND externo_id = ?", [it["id"], ext]):
        return ["Ya se invitó a ese estudiante."]
    if get_db().q("SELECT 1 FROM tribunal_auxiliatura t JOIN cuenta_estudiante c ON c.usuario_id = t.usuario_id "
                  "WHERE t.item_id = ? AND c.externo_id = ?", [it["id"], ext]):
        return ["Quien integra la comisión de este ítem no puede ser invitado."]
    get_db().t.invitacion_auxiliatura.insert(item_id=it["id"], externo_id=ext, origen="mejor_estudiante", orden=_siguiente_orden(it["id"]),
                                             nota=(nota or "").strip()[:300] or None, registrada_por=uid)
    _avisar(ext, f"Invitación a ser auxiliar: {it['titulo']}", "Por su rendimiento en la materia, la Carrera lo invita: puede aceptar o no.")
    return []


def invitacion(vid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM invitacion_auxiliatura WHERE id = ?", [vid])
    return filas[0] if filas else None


def responder_invitacion(vid: int, acepta: bool) -> list[str]:
    v = invitacion(vid)
    if not v or v["estado"] != "pendiente":
        return ["La invitación ya se respondió."]
    it = aux.item(v["item_id"])
    if acepta and cubiertas(it) >= it["plazas"]:
        return ["Las plazas de este ítem ya están cubiertas."]
    with transaccion():
        get_db().execute(f"UPDATE invitacion_auxiliatura SET estado = ?, respondida_en = {AHORA} WHERE id = ?",
                         ["aceptada" if acepta else "rechazada", vid])
        if acepta:
            _crear_designacion(it["id"], v["externo_id"], "invitado", invitacion_id=vid)
    return []


def invitaciones_de(externo_id: int) -> list[dict]:
    """Invitaciones pendientes de un estudiante, con el ítem y la convocatoria."""
    return get_db().q("""SELECT v.*, i.titulo AS item_titulo, i.horas, c.titulo AS convocatoria FROM invitacion_auxiliatura v
                         JOIN item_auxiliatura i ON i.id = v.item_id JOIN convocatoria_auxiliatura c ON c.id = i.convocatoria_id
                         WHERE v.externo_id = ? AND v.estado = 'pendiente' ORDER BY v.id""", [externo_id])


# --- Designaciones (arts. 23, 25 y 26) -------------------------------------------------------------------------------------------

def _crear_designacion(iid: int, externo_id: int, categoria: str, postulacion_id: int | None = None, invitacion_id: int | None = None):
    if get_db().q("SELECT 1 FROM designacion_auxiliatura WHERE item_id = ? AND externo_id = ?", [iid, externo_id]):
        return
    get_db().t.designacion_auxiliatura.insert(item_id=iid, externo_id=externo_id, categoria=categoria,
                                              postulacion_id=postulacion_id, invitacion_id=invitacion_id)


def asegurar_designaciones(cid: int):
    """Crea la designación de cada titular de la convocatoria que aún no la tenga (las de los invitados nacen al aceptar). La
    llama `auxiliaturas` al cerrar una fase o resolver un empate, dentro de su transacción: ninguna pantalla escribe al abrirse."""
    if not aplica(aux.obtener(cid)):
        return
    for it in aux.items(cid):
        if it["fase"] != "concluido":
            continue
        for p in aux.en_concurso(it["id"]):
            if p["estado"] == "titular":
                _crear_designacion(it["id"], p["externo_id"], "titular", postulacion_id=p["id"])


def designaciones(cid: int) -> list[dict]:
    filas = get_db().q("""SELECT d.*, pe.nombres, pe.apellidos, i.titulo AS item_titulo, i.horas FROM designacion_auxiliatura d
                          JOIN persona_externa pe ON pe.id = d.externo_id JOIN item_auxiliatura i ON i.id = d.item_id
                          WHERE i.convocatoria_id = ? ORDER BY i.titulo, d.categoria, pe.apellidos, pe.nombres""", [cid])
    for d in filas:
        d["faltan"] = [t for k, t in DOCUMENTOS_GANADORES.items() if not d[k]]
    return filas


def designacion(did: int) -> dict | None:
    filas = get_db().q("""SELECT d.*, i.convocatoria_id FROM designacion_auxiliatura d JOIN item_auxiliatura i ON i.id = d.item_id
                          WHERE d.id = ?""", [did])
    return filas[0] if filas else None


def de_estudiante(externo_id: int) -> list[dict]:
    filas = get_db().q("""SELECT d.*, i.titulo AS item_titulo, i.horas, c.titulo AS convocatoria, c.id AS convocatoria_id
                         FROM designacion_auxiliatura d JOIN item_auxiliatura i ON i.id = d.item_id
                         JOIN convocatoria_auxiliatura c ON c.id = i.convocatoria_id WHERE d.externo_id = ? ORDER BY d.id DESC""",
                      [externo_id])
    for d in filas:
        d["faltan"] = [t for k, t in DOCUMENTOS_GANADORES.items() if not d[k]]
    return filas


def limite_documentos(cid: int) -> datetime | None:
    """Hasta cuándo se reciben los documentos de los ganadores: 72 horas desde que concluyó el proceso."""
    fin = concluido_en(cid)
    return fin + timedelta(hours=PLAZO_DOCUMENTOS_HORAS) if fin else None


def documentos_vencidos(cid: int, ahora: datetime | None = None) -> bool:
    limite = limite_documentos(cid)
    return bool(limite and (ahora or datetime.now()) > limite)


def guardar_designacion(did: int, datos: dict) -> list[str]:
    """Documentos recibidos de un ganador (fechas) y su memorándum. El memorándum rige desde el 1 o el 15 de un mes (art. 25)."""
    d = designacion(did)
    if not d:
        return ["No se encontró la designación."]
    valores, errores = {}, []
    for campo in ("cert_deudas", "cert_procesos", "sigep", "memorandum_fecha", "inicio", "fin"):
        valor, ok = _fecha_valida(datos.get(campo))
        if not ok:
            errores.append("Las fechas van como AAAA-MM-DD.")
            break
        valores[campo] = valor
    valores["memorandum"] = (datos.get("memorandum") or "").strip()[:120] or None
    if not errores and valores["inicio"] and date.fromisoformat(valores["inicio"]).day not in (1, 15):
        errores.append("El memorándum rige desde el 1 o el 15 de un mes: las nominaciones en otra fecha no entran en la planilla (art. 25).")
    if not errores and valores["inicio"] and valores["fin"] and valores["fin"] < valores["inicio"]:
        errores.append("El fin de la designación no puede ser anterior al inicio.")
    if errores:
        return list(dict.fromkeys(errores))
    get_db().execute("""UPDATE designacion_auxiliatura SET cert_deudas = :cert_deudas, cert_procesos = :cert_procesos, sigep = :sigep,
                        memorandum = :memorandum, memorandum_fecha = :memorandum_fecha, inicio = :inicio, fin = :fin WHERE id = :id""",
                     {**valores, "id": did})
    return []


# --- Informe final y resoluciones (art. 22) --------------------------------------------------------------------------------------

def limite_informe(cid: int) -> date | None:
    fin = concluido_en(cid)
    return (fin + timedelta(days=PLAZO_INFORME_DIAS)).date() if fin else None


def aviso_informe(c: dict) -> tuple[bool, str] | None:
    """Si la comisión entregó su informe final dentro de los 10 días de concluido el proceso (solo advierte)."""
    limite = limite_informe(c["id"])
    if not limite:
        return None
    if c["informe_final_en"]:
        a_tiempo = date.fromisoformat(c["informe_final_en"]) <= limite
        return a_tiempo, (f"Informe final entregado el {formato.fecha(c['informe_final_en'])}"
                          + (" dentro del plazo" if a_tiempo else f", después del plazo de 10 días (hasta el {formato.fecha(limite.isoformat())}; art. 22)") + ".")
    vencido = date.today() > limite
    return (not vencido), (f"El informe final de la comisión debe entregarse al Consejo de Carrera hasta el {formato.fecha(limite.isoformat())} "
                           f"(10 días de concluido el proceso; art. 22)" + (": el plazo pasó." if vencido else "."))


def guardar_informe(cid: int, informe_en: str, hcc: str, hcf: str) -> list[str]:
    fecha_, ok = _fecha_valida(informe_en)
    if not ok:
        return ["La fecha del informe va como AAAA-MM-DD."]
    get_db().execute("""UPDATE convocatoria_auxiliatura SET informe_final_en = ?, resolucion_resultados = ?, resolucion_resultados_hcf = ?
                        WHERE id = ?""", [fecha_, (hcc or "").strip()[:120] or None, (hcf or "").strip()[:120] or None, cid])
    return []


# --- Documentación para Bienestar Social (art. 27) -------------------------------------------------------------------------------

def documentacion(cid: int) -> dict[str, str]:
    return {f["clave"]: f["entregada_en"] for f in get_db().q(
        "SELECT clave, entregada_en FROM documentacion_auxiliatura WHERE convocatoria_id = ?", [cid])}


def limite_documentacion(cid: int) -> date | None:
    """Quince días después del último memorándum emitido (art. 27)."""
    fila = get_db().q("""SELECT MAX(d.memorandum_fecha) f FROM designacion_auxiliatura d JOIN item_auxiliatura i ON i.id = d.item_id
                         WHERE i.convocatoria_id = ?""", [cid])
    return date.fromisoformat(fila[0]["f"]) + timedelta(days=PLAZO_DOCUMENTACION_DIAS) if fila and fila[0]["f"] else None


def guardar_documentacion(cid: int, fechas: dict, uid: int) -> list[str]:
    nuevas = {}
    for clave in DOCUMENTACION:
        valor, ok = _fecha_valida(fechas.get(clave))
        if not ok:
            return ["Las fechas van como AAAA-MM-DD."]
        if valor:
            nuevas[clave] = valor
    with transaccion():
        get_db().execute("DELETE FROM documentacion_auxiliatura WHERE convocatoria_id = ?", [cid])
        for clave, valor in nuevas.items():
            get_db().t.documentacion_auxiliatura.insert(convocatoria_id=cid, clave=clave, entregada_en=valor, registrada_por=uid)
    return []
