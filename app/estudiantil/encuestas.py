"""Motor de encuestas (PLAN §49 y §50): armar, abrir a un público, invitar por correo, responder con un enlace
personal sin cuenta y ver resultados agregados.

- **Anónimas:** la respuesta no se enlaza con la invitación y las fechas van sin hora. Solo se conoce el año de
  ingreso (`grupo`), y los resultados (totales y por grupo) se muestran únicamente con `MIN_ANONIMO` respuestas
  o más, para que nadie pueda deducir quién respondió qué.
- **Nominales:** la respuesta enlaza con su invitación (y con la persona).
- El enlace personal (`invitacion_encuesta.token`) solo existe mientras sirve: se borra al responder y al cerrar.
"""
import json
import secrets
from datetime import date

from app.comun import config, correo
from app.comun.db import AHORA, auditar, get_db, transaccion
from app.estudiantil.plantillas_encuesta import PLANTILLAS

TIPOS = {"satisfaccion": "Satisfacción estudiantil", "clima": "Clima y convivencia", "bienestar": "Bienestar",
         "abandono": "Causas de abandono", "egresados": "Seguimiento de egresados",
         "perfil_egreso": "Logro del perfil de egreso", "otra": "Otra"}
PUBLICOS = {"estudiantes": "Estudiantes que cursan", "egresados": "Egresados y titulados"}
TIPOS_PREGUNTA = {"escala": "Escala de 1 a 5", "si_no": "Sí o no", "opcion": "Una opción", "multiple": "Varias opciones",
                  "texto": "Texto libre"}
ESTADOS = {"borrador": "Borrador", "abierta": "Abierta", "cerrada": "Cerrada"}
ESCALA = ((1, "Totalmente en desacuerdo"), (2, "En desacuerdo"), (3, "Ni de acuerdo ni en desacuerdo"),
          (4, "De acuerdo"), (5, "Totalmente de acuerdo"))
HITOS = ("6m", "1a", "3a", "5a")      # seguimiento de egresados: encuestas continuas por hito (PLAN §50)
CLAVES = ("situacion", "sector", "primer_empleo", "utilidad", "posgrado", "ubicacion", "satisfaccion", "perfil")
MIN_ANONIMO = 5            # respuestas mínimas para mostrar resultados de una encuesta anónima (o de un grupo)
LOTE_CORREOS = 50          # correos por envío: el proveedor limita los envíos masivos
DIAS_ENTRE_RECORDATORIOS = 7
MAX_TEXTO = 2000


# --- Encuestas y preguntas -------------------------------------------------------------------------------------

def obtener(eid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM encuesta WHERE id = ?", [eid])
    return filas[0] if filas else None


def listar() -> list[dict]:
    filas = get_db().q("SELECT * FROM encuesta ORDER BY creada_en DESC, id DESC")
    for f in filas:
        f.update(resumen_invitaciones(f["id"]))
    return filas


def preguntas(eid: int) -> list[dict]:
    filas = get_db().q("SELECT * FROM pregunta WHERE encuesta_id = ? ORDER BY orden, id", [eid])
    for f in filas:
        f["opciones"] = json.loads(f["opciones"]) if f["opciones"] else []
    return filas


def validar(d: dict) -> tuple[dict, list[str]]:
    errores = []
    titulo = (d.get("titulo") or "").strip()
    if not titulo:
        errores.append("Escriba el título de la encuesta.")
    elif len(titulo) > 200:
        errores.append("El título es demasiado largo (200 caracteres como máximo).")
    tipo, publico = d.get("tipo"), d.get("publico")
    if tipo not in TIPOS:
        errores.append("Elija el tipo de encuesta.")
    if publico not in PUBLICOS:
        errores.append("Elija a quién va dirigida.")
    desde, hasta = (str(d.get("cohorte_desde") or "").strip(), str(d.get("cohorte_hasta") or "").strip())
    for v in (desde, hasta):
        if v and not (v.isdigit() and 1990 <= int(v) <= 2100):
            errores.append("Los años de ingreso del filtro no son válidos.")
            break
    if desde.isdigit() and hasta.isdigit() and int(desde) > int(hasta):
        errores.append("El año «desde» no puede ser posterior al «hasta».")
    cierra = (d.get("cierra_el") or "").strip()
    if cierra:
        try:
            date.fromisoformat(cierra)
        except ValueError:
            errores.append("La fecha límite no es válida.")
    return {"titulo": titulo, "descripcion": (d.get("descripcion") or "").strip()[:2000] or None, "tipo": tipo,
            "anonima": int(str(d.get("anonima") or "0") in ("1", "on", "true")), "publico": publico,
            "hito": d.get("hito") if d.get("hito") in HITOS else None,
            "cohorte_desde": int(desde) if desde.isdigit() else None,
            "cohorte_hasta": int(hasta) if hasta.isdigit() else None, "cierra_el": cierra or None}, errores


def crear(d: dict, uid: int | None) -> tuple[int | None, list[str]]:
    datos, errores = validar(d)
    if errores:
        return None, errores
    eid = get_db().t.encuesta.insert(creada_por=uid, **datos)["id"]
    auditar(uid, "crear_encuesta", "encuesta", eid, datos["titulo"])
    return eid, []


def crear_desde_plantilla(clave: str, uid: int | None, **cambios) -> int | None:
    """Borrador a partir de una plantilla; `cambios` (p. ej., título o hito) reemplaza datos de la plantilla."""
    p = PLANTILLAS.get(clave)
    if not p:
        return None
    with transaccion():
        eid, errores = crear({**{k: p[k] for k in ("titulo", "descripcion", "tipo", "publico")}, "anonima": int(p["anonima"]),
                              **cambios}, uid)
        assert not errores, errores
        for texto, tipo, opciones, *clave_pregunta in p["preguntas"]:
            agregar_pregunta(eid, {"texto": texto, "tipo": tipo, "opciones": "\n".join(opciones or []), "obligatoria": "1",
                                   "clave": clave_pregunta[0] if clave_pregunta else None})
    return eid


def actualizar(eid: int, d: dict) -> list[str]:
    e = obtener(eid)
    if not e or e["estado"] != "borrador":
        return ["Solo se puede editar una encuesta en borrador."]
    datos, errores = validar(d)
    datos.pop("hito")                       # el hito no se cambia después de crearla
    if not errores:
        get_db().t.encuesta.update(id=eid, **datos)
    return errores


def eliminar(eid: int) -> bool:
    e = obtener(eid)
    if not e or e["estado"] != "borrador":
        return False
    get_db().execute("DELETE FROM encuesta WHERE id = ?", [eid])
    return True


def validar_pregunta(d: dict) -> tuple[dict, list[str]]:
    errores = []
    texto, tipo = (d.get("texto") or "").strip(), d.get("tipo")
    if not texto:
        errores.append("Escriba la pregunta.")
    elif len(texto) > 500:
        errores.append("La pregunta es demasiado larga (500 caracteres como máximo).")
    if tipo not in TIPOS_PREGUNTA:
        errores.append("Elija el tipo de pregunta.")
    opciones = [o.strip() for o in (d.get("opciones") or "").splitlines() if o.strip()]
    if tipo in ("opcion", "multiple"):
        if len(opciones) < 2:
            errores.append("Escriba al menos dos opciones, una por línea.")
        elif len(set(opciones)) != len(opciones) or any(len(o) > 150 for o in opciones):
            errores.append("Las opciones deben ser distintas y breves.")
    else:
        opciones = []
    return {"texto": texto, "tipo": tipo, "opciones": json.dumps(opciones, ensure_ascii=False) if opciones else None,
            "obligatoria": int(str(d.get("obligatoria") or "0") in ("1", "on", "true")),
            "clave": d.get("clave") if d.get("clave") in CLAVES else None}, errores


def agregar_pregunta(eid: int, d: dict) -> list[str]:
    e = obtener(eid)
    if not e or e["estado"] != "borrador":
        return ["Solo se pueden cambiar las preguntas de una encuesta en borrador."]
    datos, errores = validar_pregunta(d)
    if not errores:
        orden = get_db().q("SELECT COALESCE(MAX(orden), 0) + 1 n FROM pregunta WHERE encuesta_id = ?", [eid])[0]["n"]
        get_db().t.pregunta.insert(encuesta_id=eid, orden=orden, **datos)
    return errores


def _pregunta_en_borrador(pid: int) -> dict | None:
    filas = get_db().q("""SELECT p.* FROM pregunta p JOIN encuesta e ON e.id = p.encuesta_id
                          WHERE p.id = ? AND e.estado = 'borrador'""", [pid])
    return filas[0] if filas else None


def eliminar_pregunta(pid: int) -> bool:
    if not _pregunta_en_borrador(pid):
        return False
    get_db().execute("DELETE FROM pregunta WHERE id = ?", [pid])
    return True


def mover_pregunta(pid: int, delta: int) -> bool:
    """Sube (-1) o baja (+1) una pregunta de una encuesta en borrador."""
    p = _pregunta_en_borrador(pid)
    if not p:
        return False
    lista = preguntas(p["encuesta_id"])
    i = next(i for i, x in enumerate(lista) if x["id"] == pid)
    j = i + delta
    if not 0 <= j < len(lista):
        return False
    lista[i], lista[j] = lista[j], lista[i]
    for orden, x in enumerate(lista, start=1):
        get_db().execute("UPDATE pregunta SET orden = ? WHERE id = ?", [orden, x["id"]])
    return True


# --- Público, apertura e invitaciones ---------------------------------------------------------------------------

def destinatarios(e: dict) -> tuple[list[dict], int]:
    """Personas a las que va dirigida (una por persona) y cuántas no tienen correo."""
    estados = ("cursando",) if e["publico"] == "estudiantes" else ("egresado", "titulado")
    filas = get_db().q(
        f"""SELECT pe.id AS externo_id, pe.email, MAX(es.cohorte_anio) AS grupo FROM estudiante es
            JOIN persona_externa pe ON pe.id = es.externo_id
            WHERE es.nivel = 'licenciatura' AND es.del_programa = 1 AND es.cohorte_anio IS NOT NULL
              AND es.estado IN ({",".join("?" * len(estados))})
              AND (? IS NULL OR es.cohorte_anio >= ?) AND (? IS NULL OR es.cohorte_anio <= ?)
            GROUP BY pe.id, pe.email ORDER BY pe.id""",
        [*estados, e["cohorte_desde"], e["cohorte_desde"], e["cohorte_hasta"], e["cohorte_hasta"]])
    con_correo = [f for f in filas if (f["email"] or "").strip()]
    return con_correo, len(filas) - len(con_correo)


def abrir(eid: int, uid: int | None) -> tuple[int, int, list[str]]:
    """Abre la encuesta y crea una invitación por persona. → (invitadas, sin correo, errores)."""
    e = obtener(eid)
    if not e or e["estado"] != "borrador":
        return 0, 0, ["Solo se puede abrir una encuesta en borrador."]
    if not preguntas(eid):
        return 0, 0, ["Agregue al menos una pregunta antes de abrirla."]
    if e["cierra_el"] and e["cierra_el"] < date.today().isoformat():
        return 0, 0, ["La fecha límite ya pasó: corríjala antes de abrir la encuesta."]
    if e["hito"]:        # seguimiento continuo: se abre sin invitar a nadie; las invitaciones salen al cumplirse el hito
        get_db().execute(f"UPDATE encuesta SET estado = 'abierta', abierta_en = {AHORA} WHERE id = ?", [eid])
        auditar(uid, "abrir_encuesta", "encuesta", eid, f"seguimiento {e['hito']}")
        return 0, 0, []
    gente, sin_correo = destinatarios(e)
    if not gente:
        return 0, sin_correo, ["No hay a quién invitar: ningún estudiante del público elegido tiene correo registrado."]
    with transaccion():
        for g in gente:
            get_db().t.invitacion_encuesta.insert(encuesta_id=eid, externo_id=g["externo_id"], email=g["email"].strip(),
                                                  grupo=g["grupo"], token=secrets.token_urlsafe(24))
        get_db().execute(f"UPDATE encuesta SET estado = 'abierta', abierta_en = {AHORA} WHERE id = ?", [eid])
    auditar(uid, "abrir_encuesta", "encuesta", eid, f"{len(gente)} invitada(s)")
    return len(gente), sin_correo, []


def invitar(eid: int, externo_id: int, email: str, grupo: int | None) -> dict | None:
    """Invita a una persona a una encuesta abierta y le envía el correo en el acto. None si ya estaba invitada."""
    e = obtener(eid)
    if not e or e["estado"] != "abierta" or not (email or "").strip() or get_db().q(
            "SELECT 1 FROM invitacion_encuesta WHERE encuesta_id = ? AND externo_id = ?", [eid, externo_id]):
        return None
    inv = get_db().t.invitacion_encuesta.insert(encuesta_id=eid, externo_id=externo_id, email=email.strip(), grupo=grupo,
                                                token=secrets.token_urlsafe(24))
    asunto, cuerpo = _correo(e, inv, False)
    correo.enviar(inv["email"], asunto, cuerpo)
    get_db().execute(f"UPDATE invitacion_encuesta SET enviada_en = {AHORA} WHERE id = ?", [inv["id"]])
    return inv


def resumen_invitaciones(eid: int) -> dict:
    f = get_db().q("""SELECT COUNT(*) AS invitadas, COUNT(enviada_en) AS enviadas, COUNT(respondida_en) AS respondidas
                      FROM invitacion_encuesta WHERE encuesta_id = ?""", [eid])[0]
    return {"invitadas": f["invitadas"], "enviadas": f["enviadas"], "respondidas": f["respondidas"],
            "por_enviar": f["invitadas"] - f["enviadas"]}


def enlace(token: str) -> str:
    return f"{config.URL_BASE}/encuesta/{token}"


def _correo(e: dict, inv: dict, recordatorio: bool) -> tuple[str, str]:
    asunto = ("Recordatorio: " if recordatorio else "") + f"{e['titulo']} · {config.NOMBRE_SISTEMA}"
    anonima = ("Es anónima: sus respuestas no se asocian con su nombre." if e["anonima"]
               else "Sus respuestas se asocian con su nombre.")
    limite = f"\nPuede responder hasta el {e['cierra_el']}." if e["cierra_el"] else ""
    cuerpo = (f"Hola:\n\n{'Le recordamos que sigue abierta' if recordatorio else 'Lo invitamos a responder'} la "
              f"encuesta «{e['titulo']}» de la Carrera de Matemática.\n{e['descripcion'] or ''}\n\n{anonima}{limite}\n\n"
              f"Responda aquí (el enlace es personal y sirve una sola vez):\n{enlace(inv['token'])}\n")
    return asunto, cuerpo


def enviar(eid: int, uid: int | None, recordatorio: bool = False, lote: int = LOTE_CORREOS) -> dict:
    """Envía hasta `lote` correos: a quienes aún no se invitó o, con `recordatorio`, a quienes no respondieron y no
    recibieron un recordatorio en los últimos 7 días. → enviados y cuántos quedan por enviar."""
    e = obtener(eid)
    if not e or e["estado"] != "abierta":
        return {"enviados": 0, "quedan": 0}
    if recordatorio:
        cond = f"""respondida_en IS NULL AND enviada_en IS NOT NULL AND (recordada_en IS NULL
                   OR recordada_en <= date('now', '-{DIAS_ENTRE_RECORDATORIOS} days'))"""
        marca = "recordada_en"
    else:
        cond, marca = "enviada_en IS NULL", "enviada_en"
    base = f"FROM invitacion_encuesta WHERE encuesta_id = ? AND token IS NOT NULL AND {cond}"
    enviados = 0
    for inv in get_db().q(f"SELECT * {base} ORDER BY id LIMIT ?", [eid, lote]):
        asunto, cuerpo = _correo(e, inv, recordatorio)
        correo.enviar(inv["email"], asunto, cuerpo)
        get_db().execute(f"UPDATE invitacion_encuesta SET {marca} = {AHORA} WHERE id = ?", [inv["id"]])
        if marca == "recordada_en":
            get_db().execute("UPDATE invitacion_encuesta SET enviada_en = COALESCE(enviada_en, recordada_en) WHERE id = ?",
                             [inv["id"]])
        enviados += 1
    quedan = get_db().q(f"SELECT COUNT(*) n {base}", [eid])[0]["n"]
    if enviados:
        auditar(uid, "recordar_encuesta" if recordatorio else "enviar_encuesta", "encuesta", eid, f"{enviados} correo(s)")
    return {"enviados": enviados, "quedan": quedan}


def cerrar(eid: int, uid: int | None) -> bool:
    e = obtener(eid)
    if not e or e["estado"] != "abierta":
        return False
    with transaccion():
        get_db().execute(f"UPDATE encuesta SET estado = 'cerrada', cerrada_en = {AHORA} WHERE id = ?", [eid])
        get_db().execute("UPDATE invitacion_encuesta SET token = NULL WHERE encuesta_id = ?", [eid])
    auditar(uid, "cerrar_encuesta", "encuesta", eid)
    return True


# --- Responder (sin cuenta, con el enlace personal) -------------------------------------------------------------

def invitacion_vigente(token: str) -> tuple[dict, dict] | None:
    """(invitación, encuesta) si el enlace sirve: la encuesta está abierta, no pasó su fecha límite y aún no se respondió."""
    if not token or len(token) > 100:
        return None
    filas = get_db().q("SELECT * FROM invitacion_encuesta WHERE token = ? AND respondida_en IS NULL", [token])
    if not filas:
        return None
    e = obtener(filas[0]["encuesta_id"])
    if not e or e["estado"] != "abierta" or (e["cierra_el"] and e["cierra_el"] < date.today().isoformat()):
        return None
    return filas[0], e


def validar_respuestas(qs: list[dict], crudo: dict[int, list[str]]) -> tuple[dict[int, list[str]], list[str]]:
    """Normaliza lo contestado a {pregunta_id: [valores]} y lista lo que falta o no es válido."""
    limpio, errores = {}, []
    for q in qs:
        vals = [v.strip() for v in crudo.get(q["id"], []) if v and v.strip()]
        if not vals:
            if q["obligatoria"]:
                errores.append(f"Falta responder: {q['texto']}")
            continue
        ok = True
        if q["tipo"] == "escala":
            ok = len(vals) == 1 and vals[0] in {str(n) for n, _ in ESCALA}
        elif q["tipo"] == "si_no":
            ok = len(vals) == 1 and vals[0] in ("si", "no")
        elif q["tipo"] == "opcion":
            ok = len(vals) == 1 and vals[0] in q["opciones"]
        elif q["tipo"] == "multiple":
            ok = set(vals) <= set(q["opciones"])
        elif q["tipo"] == "texto":
            vals = [vals[0][:MAX_TEXTO]]
        if not ok:
            errores.append(f"Respuesta no válida: {q['texto']}")
        else:
            limpio[q["id"]] = vals
    return limpio, errores


def responder(token: str, crudo: dict[int, list[str]]) -> list[str]:
    """Guarda la respuesta y consume el enlace. → errores (vacío si se guardó)."""
    v = invitacion_vigente(token)
    if not v:
        return ["Este enlace ya no sirve."]
    inv, e = v
    limpio, errores = validar_respuestas(preguntas(e["id"]), crudo)
    if errores:
        return errores
    db = get_db()
    # Anónimas: sin la invitación y con la fecha sin hora (no se puede cruzar con la hora de otras tablas).
    cuando = date.today().isoformat() if e["anonima"] else db.q(f"SELECT {AHORA} AS t")[0]["t"]
    with transaccion():
        resp = db.t.respuesta.insert(encuesta_id=e["id"], invitacion_id=None if e["anonima"] else inv["id"],
                                     grupo=inv["grupo"], enviada_en=cuando)
        for pid, vals in limpio.items():
            for val in vals:
                db.execute("INSERT INTO respuesta_item (respuesta_id, pregunta_id, valor) VALUES (?, ?, ?)",
                           [resp["id"], pid, val])
        db.execute("UPDATE invitacion_encuesta SET token = NULL, respondida_en = ? WHERE id = ?", [cuando, inv["id"]])
    return []


# --- Resultados ------------------------------------------------------------------------------------------------

def n_respuestas(eid: int) -> int:
    return get_db().q("SELECT COUNT(*) n FROM respuesta WHERE encuesta_id = ?", [eid])[0]["n"]


def resultados(eid: int) -> dict:
    """Resultados agregados. Una encuesta anónima con menos de `MIN_ANONIMO` respuestas no muestra nada (`oculto`);
    los grupos (año de ingreso) con menos de ese mínimo tampoco."""
    e = obtener(eid)
    n = n_respuestas(eid)
    inv = resumen_invitaciones(eid)
    base = {"encuesta": e, "n": n, "invitadas": inv["invitadas"], "enviadas": inv["enviadas"],
            "tasa": n / inv["invitadas"] if inv["invitadas"] else None, "minimo": MIN_ANONIMO,
            "oculto": bool(e["anonima"] and n < MIN_ANONIMO), "preguntas": []}
    if base["oculto"]:
        return base
    db = get_db()
    for q in preguntas(eid):
        items = db.q("""SELECT i.valor, r.grupo FROM respuesta_item i JOIN respuesta r ON r.id = i.respuesta_id
                        WHERE i.pregunta_id = ?""", [q["id"]])
        r = {"pregunta": q}
        if q["tipo"] == "escala":
            valores = [int(i["valor"]) for i in items]
            r.update(n=len(valores), promedio=sum(valores) / len(valores) if valores else None,
                     conteo={k: valores.count(k) for k, _ in ESCALA}, por_grupo=_por_grupo(items, e["anonima"]))
        elif q["tipo"] in ("si_no", "opcion", "multiple"):
            opciones = ["si", "no"] if q["tipo"] == "si_no" else q["opciones"]
            quienes = db.q("SELECT COUNT(DISTINCT respuesta_id) n FROM respuesta_item WHERE pregunta_id = ?", [q["id"]])[0]["n"]
            r.update(n=quienes, conteo={o: sum(1 for i in items if i["valor"] == o) for o in opciones})
        else:
            r.update(n=len(items), textos=sorted((i["valor"] for i in items), key=str.casefold))   # sin el orden de llegada
        base["preguntas"].append(r)
    return base


def _por_grupo(items: list[dict], anonima: bool) -> dict[int, float]:
    grupos: dict[int, list[int]] = {}
    for i in items:
        if i["grupo"] is not None:
            grupos.setdefault(i["grupo"], []).append(int(i["valor"]))
    return {g: sum(v) / len(v) for g, v in sorted(grupos.items()) if not anonima or len(v) >= MIN_ANONIMO}


def individuales(eid: int) -> list[dict]:
    """Respuestas una por una (solo encuestas nominales): persona y lo que contestó."""
    e = obtener(eid)
    if not e or e["anonima"]:
        return []
    qs = preguntas(eid)
    res = []
    for r in get_db().q("""SELECT r.id, r.enviada_en, pe.nombres, pe.apellidos FROM respuesta r
                           JOIN invitacion_encuesta inv ON inv.id = r.invitacion_id
                           JOIN persona_externa pe ON pe.id = inv.externo_id WHERE r.encuesta_id = ?
                           ORDER BY pe.apellidos, pe.nombres""", [eid]):
        por_pregunta: dict[int, list[str]] = {}
        for i in get_db().q("SELECT pregunta_id, valor FROM respuesta_item WHERE respuesta_id = ?", [r["id"]]):
            por_pregunta.setdefault(i["pregunta_id"], []).append(i["valor"])
        res.append({**r, "respuestas": [(q, por_pregunta.get(q["id"], [])) for q in qs]})
    return res


def texto_valor(q: dict, valor: str) -> str:
    if q["tipo"] == "escala":
        return f"{valor} ({dict(ESCALA)[int(valor)]})"
    if q["tipo"] == "si_no":
        return "Sí" if valor == "si" else "No"
    return valor


def csv_resultados(eid: int) -> str | None:
    """Resultados agregados en CSV (pregunta, respuesta, n). None si aún no se pueden mostrar."""
    import csv
    import io
    r = resultados(eid)
    if r["oculto"]:
        return None
    sal = io.StringIO()
    w = csv.writer(sal)
    w.writerow(["pregunta", "tipo", "respuesta", "n"])
    for p in r["preguntas"]:
        q = p["pregunta"]
        if q["tipo"] == "texto":
            continue
        for k, n in p["conteo"].items():
            w.writerow([q["texto"], TIPOS_PREGUNTA[q["tipo"]], texto_valor(q, str(k)), n])
    return sal.getvalue()
