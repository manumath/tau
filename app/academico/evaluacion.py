"""Evaluación docente con transparencia (PLAN §68, etapa 5).

Una evaluación por gestión. La Dirección de Carrera la crea, la **anuncia** (el instrumento y las fechas quedan a la vista de
docentes y estudiantes, con al menos `ANTICIPACION_DIAS` de anticipación), la abre y la cierra. Responden los estudiantes inscritos en cada
paralelo (según la lista de curso), una vez y **de forma anónima**: la participación no se enlaza con la respuesta ni hay hora.

Reglas de transparencia:
- Los resultados de un docente solo se muestran desde `MIN_RESPUESTAS` respuestas (el mismo mínimo que las encuestas anónimas); el
  desglose por paralelo solo si todos sus paralelos lo alcanzan (si no, restar revelaría el que no llega).
- El docente ve sus resultados, agrega su contexto y ve **quién los consultó** (bitácora). La Dirección los ve por docente, no en
  lista, y cada consulta queda en la bitácora y en la auditoría.
- No hay respuestas abiertas. Los estudiantes reciben el retorno de lo que la Carrera hizo."""
import json
from datetime import date, timedelta

from app.academico import gestiones, listas, oferta
from app.comun import notificaciones
from app.comun.db import auditar, get_db, transaccion

MIN_RESPUESTAS = 5          # = app.estudiantil.encuestas.MIN_ANONIMO (lo vigila una prueba)
ANTICIPACION_DIAS = 7
ESTADOS = {"borrador": "Borrador", "anunciada": "Anunciada", "abierta": "Abierta", "cerrada": "Cerrada"}
ESCALA = ((1, "Totalmente en desacuerdo"), (2, "En desacuerdo"), (3, "Ni de acuerdo ni en desacuerdo"), (4, "De acuerdo"),
          (5, "Totalmente de acuerdo"))
CRITERIOS = (("dominio", "Demuestra dominio de la materia."),
             ("claridad", "Explica con claridad y ordena los temas."),
             ("programa", "Cumple el programa analítico publicado."),
             ("puntualidad", "Es puntual y cumple el horario de clases."),
             ("trato", "Trata con respeto a los estudiantes."),
             ("evaluacion", "Sus evaluaciones corresponden a lo enseñado y se entregan a tiempo."),
             ("consulta", "Atiende las consultas y está disponible."),
             ("aporte", "Sus clases me ayudaron a aprender."))
MAX_TEXTO = 2000


def hoy() -> date:
    return date.today()


def obtener(eid: int) -> dict | None:
    f = get_db().q("SELECT * FROM evaluacion_docente WHERE id = ?", [eid])
    if not f:
        return None
    e = f[0]
    e["criterios"] = [tuple(c) for c in json.loads(e["criterios"])]
    return e


def de_gestion(gid: int) -> dict | None:
    f = get_db().q("SELECT id FROM evaluacion_docente WHERE gestion_id = ?", [gid])
    return obtener(f[0]["id"]) if f else None


def listar() -> list[dict]:
    return [obtener(f["id"]) for f in get_db().q("""SELECT e.id FROM evaluacion_docente e JOIN gestion_academica g ON g.id = e.gestion_id
                                                    ORDER BY g.fecha_inicio DESC""")]


def estado(e: dict, fecha: date | None = None) -> str:
    """El estado vigente: una evaluación abierta cuya fecha de cierre pasó ya está cerrada."""
    if e["estado"] == "abierta" and e["cierra_el"] < (fecha or hoy()).isoformat():
        return "cerrada"
    return e["estado"]


def gestion_de(e: dict) -> dict:
    return gestiones.obtener(e["gestion_id"])


# --- Ciclo de vida (Dirección de Carrera) ----------------------------------------------------------------------------------

def crear(gid: int, abre_el: str, cierra_el: str, uid: int) -> tuple[int | None, list[str]]:
    g = gestiones.obtener(gid)
    if not g or g["tipo"] not in ("I", "II") or g["estado"] == "planificacion":
        return None, ["Elija un semestre (I o II) que ya esté activo o concluido."]
    if de_gestion(gid):
        return None, [f"{gestiones.codigo(g)} ya tiene su evaluación."]
    try:
        a, c = date.fromisoformat(abre_el), date.fromisoformat(cierra_el)
    except ValueError:
        return None, ["Indique las fechas de apertura y de cierre."]
    if c < a:
        return None, ["El cierre no puede ser antes de la apertura."]
    with transaccion():
        eid = get_db().t.evaluacion_docente.insert(gestion_id=gid, abre_el=abre_el, cierra_el=cierra_el, creada_por=uid,
                                                   criterios=json.dumps(CRITERIOS, ensure_ascii=False))["id"]
        auditar(uid, "crear_evaluacion_docente", "evaluacion_docente", eid, gestiones.codigo(g))
    return eid, []


def eliminar(eid: int, uid: int) -> list[str]:
    e = obtener(eid)
    if not e or e["estado"] != "borrador":
        return ["Solo se elimina una evaluación en borrador."]
    get_db().execute("DELETE FROM evaluacion_docente WHERE id = ?", [eid])
    auditar(uid, "eliminar_evaluacion_docente", "evaluacion_docente", eid, gestiones.codigo(gestion_de(e)))
    return []


def _docentes_de(gid: int) -> list[dict]:
    return get_db().q(
        """SELECT DISTINCT u.* FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id JOIN usuario u ON u.id = d.usuario_id
           WHERE o.gestion_id = ? AND d.rol = 'titular' AND o.retirada_en IS NULL""", [gid])


def anunciar(eid: int, uid: int) -> list[str]:
    """Hace público el instrumento y las fechas, y avisa a los docentes titulares de la gestión."""
    e = obtener(eid)
    if not e or e["estado"] != "borrador":
        return ["Solo se anuncia una evaluación en borrador."]
    g = gestion_de(e)
    with transaccion():
        get_db().execute("UPDATE evaluacion_docente SET estado = 'anunciada', anunciada_en = datetime('now') WHERE id = ?", [eid])
        auditar(uid, "anunciar_evaluacion_docente", "evaluacion_docente", eid, gestiones.codigo(g))
    for d in _docentes_de(g["id"]):
        notificaciones.avisar(d, f"Evaluación docente de {gestiones.codigo(g)}",
                              f"Se abrirá del {e['abre_el']} al {e['cierra_el']}. Vea el instrumento y cómo se usan los resultados.",
                              "/docencia/evaluacion")
    return []


def abrir(eid: int, uid: int) -> list[str]:
    e = obtener(eid)
    if not e or e["estado"] != "anunciada":
        return ["Solo se abre una evaluación anunciada."]
    anunciada = date.fromisoformat(e["anunciada_en"][:10])
    if hoy() < anunciada + timedelta(days=ANTICIPACION_DIAS):
        return [f"Debe pasar al menos {ANTICIPACION_DIAS} días desde el anuncio (hasta el "
                f"{(anunciada + timedelta(days=ANTICIPACION_DIAS)).isoformat()}): los docentes deben conocer el instrumento antes."]
    if e["cierra_el"] < hoy().isoformat():
        return ["La fecha de cierre ya pasó: corríjala antes de abrir."]
    g = gestion_de(e)
    with transaccion():
        get_db().execute("UPDATE evaluacion_docente SET estado = 'abierta', abierta_en = datetime('now') WHERE id = ?", [eid])
        auditar(uid, "abrir_evaluacion_docente", "evaluacion_docente", eid, gestiones.codigo(g))
    return []


def cerrar(eid: int, uid: int) -> list[str]:
    e = obtener(eid)
    if not e or estado(e) not in ("abierta", "cerrada") or e["estado"] == "cerrada":
        return ["Solo se cierra una evaluación abierta."]
    g = gestion_de(e)
    with transaccion():
        get_db().execute("UPDATE evaluacion_docente SET estado = 'cerrada', cerrada_en = datetime('now') WHERE id = ?", [eid])
        auditar(uid, "cerrar_evaluacion_docente", "evaluacion_docente", eid,
                f"{gestiones.codigo(g)}: {n_respuestas(eid)} respuestas")
    return []


def actualizar_fechas(eid: int, abre_el: str, cierra_el: str, uid: int) -> list[str]:
    e = obtener(eid)
    if not e or e["estado"] in ("abierta", "cerrada"):
        return ["Las fechas se cambian antes de abrir la evaluación."]
    try:
        if date.fromisoformat(cierra_el) < date.fromisoformat(abre_el):
            return ["El cierre no puede ser antes de la apertura."]
    except ValueError:
        return ["Indique las fechas de apertura y de cierre."]
    get_db().execute("UPDATE evaluacion_docente SET abre_el = ?, cierra_el = ? WHERE id = ?", [abre_el, cierra_el, eid])
    auditar(uid, "cambiar_fechas_evaluacion_docente", "evaluacion_docente", eid, f"{abre_el} a {cierra_el}")
    return []


def guardar_retorno(eid: int, texto: str) -> list[str]:
    e = obtener(eid)
    if not e or estado(e) != "cerrada":
        return ["El retorno se escribe cuando la evaluación está cerrada."]
    if len(texto or "") > MAX_TEXTO:
        return [f"El retorno admite hasta {MAX_TEXTO} caracteres."]
    get_db().execute("UPDATE evaluacion_docente SET retorno = ? WHERE id = ?", [(texto or "").strip() or None, eid])
    return []


def publicar_retorno(eid: int, uid: int) -> list[str]:
    e = obtener(eid)
    if not e or estado(e) != "cerrada" or not (e["retorno"] or "").strip():
        return ["Escriba el retorno de una evaluación cerrada antes de publicarlo."]
    get_db().execute("UPDATE evaluacion_docente SET retorno_publicado_en = datetime('now') WHERE id = ?", [eid])
    auditar(uid, "publicar_retorno_evaluacion_docente", "evaluacion_docente", eid, gestiones.codigo(gestion_de(e)))
    return []


def retirar_retorno(eid: int):
    get_db().execute("UPDATE evaluacion_docente SET retorno_publicado_en = NULL WHERE id = ?", [eid])


# --- Estudiantes ------------------------------------------------------------------------------------------------------------

def _ru(externo_id: int) -> str | None:
    f = get_db().q("""SELECT registro_universitario FROM estudiante WHERE externo_id = ? AND registro_universitario IS NOT NULL
                      ORDER BY id DESC LIMIT 1""", [externo_id])
    return f[0]["registro_universitario"] if f else None


def abierta(fecha: date | None = None) -> dict | None:
    """La evaluación abierta hoy (una por gestión; en la práctica, una a la vez)."""
    for e in listar():
        if estado(e, fecha) == "abierta" and e["abre_el"] <= (fecha or hoy()).isoformat():
            return e
    return None


def titulares(oid: int) -> list[dict]:
    return get_db().q("""SELECT DISTINCT u.id, u.nombres, u.apellidos FROM oferta_docente d JOIN usuario u ON u.id = d.usuario_id
                         WHERE d.oferta_id = ? AND d.rol = 'titular' ORDER BY u.apellidos""", [oid])


def por_evaluar(externo_id: int) -> tuple[dict | None, list[dict]]:
    """(evaluación abierta, paralelos del estudiante que aún no evaluó). Sin RU o sin lista, no hay paralelos."""
    e = abierta()
    ru = _ru(externo_id)
    if not e or not ru:
        return e, []
    hechos = {f["oferta_id"] for f in get_db().q(
        "SELECT oferta_id FROM evaluacion_participacion WHERE evaluacion_id = ? AND externo_id = ?", [e["id"], externo_id])}
    cursos = []
    for oid in listas.ofertas_de_ru(e["gestion_id"], ru):
        o = oferta.obtener(oid)
        cursos.append({"oferta_id": oid, "sigla": o["sigla"], "nombre": o["nombre"], "paralelo": o["paralelo"],
                       "docentes": ", ".join(f"{t['nombres']} {t['apellidos']}" for t in titulares(oid)),
                       "hecho": oid in hechos})
    return e, sorted(cursos, key=lambda c: (c["hecho"], c["sigla"]))


def puede_evaluar(externo_id: int, oid: int) -> tuple[dict | None, str | None]:
    """→ (evaluación, motivo por el que no puede). Debe estar inscrito (por su RU) y no haber evaluado ese paralelo."""
    e = abierta()
    o = oferta.obtener(oid)
    if not e or not o or o["gestion_id"] != e["gestion_id"]:
        return None, "Ese paralelo no tiene una evaluación abierta."
    if oid not in listas.ofertas_de_ru(e["gestion_id"], _ru(externo_id) or ""):
        return None, "Solo evalúan los estudiantes inscritos en el paralelo."
    if get_db().q("SELECT 1 FROM evaluacion_participacion WHERE evaluacion_id = ? AND oferta_id = ? AND externo_id = ?",
                  [e["id"], oid, externo_id]):
        return None, "Ya evaluó este paralelo."
    return e, None


def responder(externo_id: int, oid: int, crudo: dict[str, str]) -> list[str]:
    """Guarda la respuesta sin enlazarla con quien la dio. → errores."""
    e, motivo = puede_evaluar(externo_id, oid)
    if motivo:
        return [motivo]
    valores = {}
    for clave, _ in e["criterios"]:
        v = str(crudo.get(clave, "")).strip()
        if v not in ("1", "2", "3", "4", "5"):
            return ["Responda todas las afirmaciones."]
        valores[clave] = int(v)
    with transaccion():
        get_db().execute("INSERT INTO evaluacion_participacion (evaluacion_id, oferta_id, externo_id) VALUES (?, ?, ?)",
                         [e["id"], oid, externo_id])
        r = get_db().t.evaluacion_respuesta.insert(evaluacion_id=e["id"], oferta_id=oid)
        for clave, v in valores.items():
            get_db().execute("INSERT INTO evaluacion_valor (respuesta_id, criterio, valor) VALUES (?, ?, ?)", [r["id"], clave, v])
    return []


def retornos_publicados() -> list[dict]:
    """Retornos publicados de las evaluaciones (lo que la Carrera hizo; no depende de quién respondió)."""
    return [e for e in listar() if e["retorno_publicado_en"] and (e["retorno"] or "").strip()]


# --- Resultados -------------------------------------------------------------------------------------------------------------

def n_respuestas(eid: int, oid: int | None = None) -> int:
    return get_db().q(f"SELECT COUNT(*) n FROM evaluacion_respuesta WHERE evaluacion_id = ? {'AND oferta_id = ?' if oid else ''}",
                      [eid, *([oid] if oid else [])])[0]["n"]


def _agregar(eid: int, oids: list[int], criterios) -> dict:
    """Media y distribución por criterio de las respuestas de esos paralelos."""
    if not oids:
        return {"n": 0, "criterios": []}
    marcas = ",".join("?" for _ in oids)
    n = get_db().q(f"SELECT COUNT(*) n FROM evaluacion_respuesta WHERE evaluacion_id = ? AND oferta_id IN ({marcas})",
                   [eid, *oids])[0]["n"]
    res = []
    for clave, texto in criterios:
        filas = get_db().q(f"""SELECT v.valor, COUNT(*) c FROM evaluacion_valor v JOIN evaluacion_respuesta r ON r.id = v.respuesta_id
                               WHERE r.evaluacion_id = ? AND r.oferta_id IN ({marcas}) AND v.criterio = ? GROUP BY v.valor""",
                          [eid, *oids, clave])
        dist = {v: 0 for v, _ in ESCALA} | {f["valor"]: f["c"] for f in filas}
        total = sum(dist.values())
        res.append({"clave": clave, "texto": texto, "distribucion": dist,
                    "media": round(sum(v * c for v, c in dist.items()) / total, 2) if total else None})
    return {"n": n, "criterios": res}


def paralelos_de(eid: int, uid: int) -> list[dict]:
    e = obtener(eid)
    return get_db().q(
        """SELECT DISTINCT o.id AS oferta_id, a.sigla, a.nombre, o.paralelo FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id
           JOIN asignatura a ON a.id = o.asignatura_id WHERE d.usuario_id = ? AND d.rol = 'titular' AND o.gestion_id = ?
             AND o.retirada_en IS NULL ORDER BY a.sigla, o.paralelo""", [uid, e["gestion_id"]])


def resultados_de(eid: int, uid: int) -> dict | None:
    """Resultados de un docente en la evaluación, solo si está cerrada. {suficiente, n, criterios, paralelos}: sin las medias si hay
    menos de MIN_RESPUESTAS; el desglose por paralelo solo si todos sus paralelos llegan al mínimo."""
    e = obtener(eid)
    if not e or estado(e) != "cerrada":
        return None
    ps = paralelos_de(eid, uid)
    for p in ps:
        p["n"] = n_respuestas(eid, p["oferta_id"])
    total = _agregar(eid, [p["oferta_id"] for p in ps], e["criterios"])
    r = {"n": total["n"], "suficiente": total["n"] >= MIN_RESPUESTAS, "criterios": [], "paralelos": []}
    if not r["suficiente"]:
        return r
    r["criterios"] = total["criterios"]
    if len(ps) > 1 and all(p["n"] >= MIN_RESPUESTAS for p in ps):
        r["paralelos"] = [{**p, **_agregar(eid, [p["oferta_id"]], e["criterios"])} for p in ps]
    return r


def media_global(r: dict) -> float | None:
    medias = [c["media"] for c in r["criterios"] if c["media"] is not None]
    return round(sum(medias) / len(medias), 2) if r["suficiente"] and medias else None


def participacion(eid: int) -> list[dict]:
    """Para la Dirección: por docente, cuántas respuestas y cuántos inscritos hay (sin resultados)."""
    e = obtener(eid)
    filas = []
    for d in _docentes_de(e["gestion_id"]):
        ps = paralelos_de(eid, d["id"])
        n = sum(n_respuestas(eid, p["oferta_id"]) for p in ps)
        inscritos = sum(get_db().q("SELECT COUNT(*) n FROM lista_curso WHERE oferta_id = ?", [p["oferta_id"]])[0]["n"] for p in ps)
        filas.append({"id": d["id"], "nombres": d["nombres"], "apellidos": d["apellidos"], "paralelos": len(ps), "n": n,
                      "inscritos": inscritos or None, "suficiente": n >= MIN_RESPUESTAS})
    return sorted(filas, key=lambda f: (f["apellidos"], f["nombres"]))


# --- Contexto y bitácora ----------------------------------------------------------------------------------------------------

def contexto(eid: int, uid: int) -> str:
    f = get_db().q("SELECT texto FROM evaluacion_contexto WHERE evaluacion_id = ? AND usuario_id = ?", [eid, uid])
    return f[0]["texto"] if f else ""


def guardar_contexto(eid: int, uid: int, texto: str) -> list[str]:
    e = obtener(eid)
    if not e or estado(e) != "cerrada":
        return ["Puede agregar su contexto cuando la evaluación está cerrada."]
    texto = (texto or "").strip()
    if len(texto) > MAX_TEXTO:
        return [f"El contexto admite hasta {MAX_TEXTO} caracteres."]
    if not texto:
        get_db().execute("DELETE FROM evaluacion_contexto WHERE evaluacion_id = ? AND usuario_id = ?", [eid, uid])
    else:
        get_db().execute("""INSERT INTO evaluacion_contexto (evaluacion_id, usuario_id, texto) VALUES (?, ?, ?)
                            ON CONFLICT (evaluacion_id, usuario_id) DO UPDATE SET texto = excluded.texto,
                                actualizado_en = datetime('now')""", [eid, uid, texto])
    return []


def registrar_consulta(eid: int, docente_id: int, consultor_id: int):
    """Una consulta ajena a los resultados de un docente queda en su bitácora y en la auditoría."""
    if docente_id == consultor_id:
        return
    get_db().t.evaluacion_consulta.insert(evaluacion_id=eid, docente_id=docente_id, consultor_id=consultor_id)
    auditar(consultor_id, "ver_resultados_evaluacion_docente", "evaluacion_docente", eid, f"docente {docente_id}")


def consultas(eid: int, docente_id: int) -> list[dict]:
    return get_db().q("""SELECT c.consultada_en, u.nombres, u.apellidos FROM evaluacion_consulta c JOIN usuario u ON u.id = c.consultor_id
                         WHERE c.evaluacion_id = ? AND c.docente_id = ? ORDER BY c.id DESC""", [eid, docente_id])
