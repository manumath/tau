"""Convocatorias a auxiliaturas (PLAN §58, servicio 3), según el Reglamento General de Auxiliares Académicos de la UMSA
(Res. HCU 251/2021, mod. 437/2021 y 623/2021).

- La Dirección de Carrera o la Coordinación académica arma la convocatoria de una gestión: de **docencia** (materias de
  la oferta) o de **investigación** (proyectos; también la Dirección del Instituto). Requisitos (art. 8 y 12, más los de
  la Carrera), cada uno con cómo se acredita: documento, declaración o lo verifica el sistema.
- Cada ítem tiene un **tribunal de dos docentes y dos estudiantes** (decisión 1 del 7-nov-2026). Un postulante de la
  convocatoria no puede integrar un tribunal de ella (art. 8).
- Se publica solo con el **número de la resolución** del Consejo de Carrera (el PDF es opcional; decisión 5).
- Fases: postulación → habilitación → méritos (30, mín. 10) → escrito (35, mín. 17,5) → oral (35). Cada miembro
  califica; la nota es el promedio y hacen falta **al menos tres miembros** (decisión 4). Titular con 56 o más, por
  puntaje hasta cubrir las plazas; un empate en el corte queda «empate» hasta el examen de desempate (art. 19).
- Al cerrar una fase cada postulante ve su resultado y corren 24 horas para impugnar (art. 21). Las impugnaciones se
  presentan por escrito: TAU solo las registra (decisión 8), y no se cierra otra fase mientras haya alguna sin resolver.
"""
import random
from datetime import date, datetime, timedelta, timezone

from app.comun import estudiantes, formato, notificaciones, permisos, usuarios
from app.comun.db import AHORA, get_db, transaccion

MODALIDADES = {"docencia": "Docencia", "investigacion": "Investigación"}
ACREDITA = {"documento": "Documento", "declaracion": "Declaración jurada", "sistema": "Lo verifica el sistema"}
ESTADOS_CONV = {"borrador": "Borrador", "publicada": "Publicada", "concluida": "Concluida"}
FASES = ("habilitacion", "meritos", "escrito", "oral")
NOMBRE_FASE = {"postulacion": "Postulación", "habilitacion": "Habilitación", "meritos": "Méritos",
               "escrito": "Examen escrito", "oral": "Examen oral", "concluido": "Resultado"}
MAXIMO = {"habilitacion": 1, "meritos": 30, "escrito": 35, "oral": 35}
MINIMO = {"meritos": 10, "escrito": 17.5}
PUNTAJE_TITULAR = 56
QUORUM = 3                 # miembros que deben calificar cada fase (decisión 4 del 7-nov-2026)
HORAS_IMPUGNACION = 24     # art. 21
MAX_GESTIONES = 2          # art. 8: no más de dos gestiones en la misma materia
ESTADOS_POST = {"borrador": "Sin enviar", "enviada": "En concurso", "no_habilitada": "No habilitada",
                "eliminada": "No alcanzó el mínimo", "titular": "Auxiliar titular", "no_seleccionada": "No seleccionada",
                "empate": "Empate: examen de desempate"}
# Del reglamento (art. 8 y 12). La Carrera puede agregar los suyos.
REQUISITOS_REGLAMENTO = (
    ("Ser estudiante regular (matrícula vigente)", "documento"),
    ("Récord académico sellado: aprobó todas las materias del semestre de la materia y al menos una el periodo anterior",
     "documento"),
    ("Currículum documentado, con respaldos", "documento"),
    ("No haber sido auxiliar de la misma materia en dos gestiones", "sistema"),
    ("No tener título profesional", "declaracion"),
    ("Si es delegado al Consejo, tiene licencia durante el proceso", "declaracion"),
)


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


# --- Permisos -------------------------------------------------------------------------------------------------------

def puede_gestionar(auth: dict, modalidad: str | None = None) -> bool:
    if modalidad == "investigacion":
        return permisos.puede(auth, "gestionar_auxiliaturas_investigacion")
    if modalidad == "docencia":
        return permisos.puede(auth, "gestionar_auxiliaturas")
    return permisos.puede(auth, "gestionar_auxiliaturas") or permisos.puede(auth, "gestionar_auxiliaturas_investigacion")


def modalidades_de(auth: dict) -> list[str]:
    return [m for m in MODALIDADES if puede_gestionar(auth, m)]


# --- Días hábiles (lunes a viernes; los feriados no se descuentan) --------------------------------------------------

def habiles_entre(desde: date, hasta: date) -> int:
    """Días hábiles después de `desde` y hasta `hasta` inclusive."""
    n, d = 0, desde
    while d < hasta:
        d += timedelta(days=1)
        n += d.weekday() < 5
    return n


def sumar_habiles(desde: date, n: int) -> date:
    d = desde
    while n > 0:
        d += timedelta(days=1)
        n -= d.weekday() < 5
    return d


# --- Convocatorias -----------------------------------------------------------------------------------------------------

def gestiones() -> list[dict]:
    return get_db().q("SELECT * FROM gestion_academica ORDER BY anio DESC, fecha_inicio DESC")


def texto_gestion(g: dict | None) -> str:
    return f"{g['tipo']}-{g['anio']}" if g else ""


def obtener(cid: int) -> dict | None:
    filas = get_db().q("""SELECT c.*, g.anio, g.tipo AS gestion_tipo FROM convocatoria_auxiliatura c
                          JOIN gestion_academica g ON g.id = c.gestion_id WHERE c.id = ?""", [cid])
    return filas[0] if filas else None


def listar(auth: dict | None = None) -> list[dict]:
    filas = get_db().q("""SELECT c.*, g.anio, g.tipo AS gestion_tipo,
                                 (SELECT COUNT(*) FROM item_auxiliatura i WHERE i.convocatoria_id = c.id) AS n_items,
                                 (SELECT COUNT(*) FROM postulacion_auxiliatura p JOIN item_auxiliatura i ON i.id = p.item_id
                                    WHERE i.convocatoria_id = c.id AND p.estado <> 'borrador') AS n_post
                          FROM convocatoria_auxiliatura c JOIN gestion_academica g ON g.id = c.gestion_id
                          ORDER BY c.estado = 'concluida', g.anio DESC, c.id DESC""")
    return [c for c in filas if auth is None or puede_gestionar(auth, c["modalidad"])]


def validar(d: dict, modalidades: list[str]) -> tuple[dict, list[str]]:
    errores = []
    if d.get("modalidad") not in modalidades:
        errores.append("Elija la modalidad.")
    try:
        gid = int(d.get("gestion_id") or 0)
    except ValueError:
        gid = 0
    if not get_db().q("SELECT 1 FROM gestion_academica WHERE id = ?", [gid]):
        errores.append("Elija la gestión.")
    numero = 2 if str(d.get("numero")) == "2" else 1
    x = {"modalidad": d.get("modalidad"), "gestion_id": gid, "numero": numero,
         "titulo": (d.get("titulo") or "").strip()[:200],
         "publicacion": (d.get("publicacion") or "").strip() or None,
         "cierre": (d.get("cierre") or "").strip() or None, "examen": (d.get("examen") or "").strip() or None,
         "lugar": (d.get("lugar") or "").strip()[:200] or None, "resolucion": (d.get("resolucion") or "").strip()[:120] or None}
    if not x["titulo"]:
        errores.append("Escriba el título.")
    for campo, nombre in (("publicacion", "la publicación"), ("cierre", "el cierre"), ("examen", "el examen escrito")):
        if x[campo]:
            try:
                datetime.fromisoformat(x[campo])
            except ValueError:
                errores.append(f"La fecha de {nombre} no es válida.")
    if not errores and x["publicacion"] and x["cierre"] and x["cierre"][:10] < x["publicacion"][:10]:
        errores.append("El cierre de la recepción no puede ser anterior a la publicación.")
    if not errores and x["cierre"] and x["examen"] and x["examen"] < x["cierre"]:
        errores.append("El examen escrito debe ser después del cierre de la recepción.")
    return x, errores


def crear(x: dict, uid: int) -> int:
    with transaccion():
        cid = get_db().t.convocatoria_auxiliatura.insert(creado_por=uid, **x)["id"]
        for i, (texto, acredita) in enumerate(REQUISITOS_REGLAMENTO):
            get_db().t.requisito_auxiliatura.insert(convocatoria_id=cid, texto=texto, acredita=acredita, orden=i)
    return cid


def editar(cid: int, x: dict):
    get_db().t.convocatoria_auxiliatura.update(id=cid, **x)


def eliminar(cid: int):
    get_db().execute("DELETE FROM convocatoria_auxiliatura WHERE id = ? AND estado = 'borrador'", [cid])


def chequeo_fechas(c: dict) -> tuple[bool, str] | None:
    """Art. 10: 10 días hábiles entre la publicación y el examen escrito en la primera convocatoria; 5 en la segunda."""
    if not c["publicacion"] or not c["examen"]:
        return None
    pedidos = 10 if c["numero"] == 1 else 5
    n = habiles_entre(date.fromisoformat(c["publicacion"][:10]), date.fromisoformat(c["examen"][:10]))
    if n >= pedidos:
        return True, f"Hay {n} días hábiles entre la publicación y el examen escrito (el art. 10 pide {pedidos})."
    return False, f"Solo hay {n} días hábiles entre la publicación y el examen escrito; el art. 10 pide {pedidos}."


# --- Requisitos ---------------------------------------------------------------------------------------------------------

def requisitos(cid: int) -> list[dict]:
    return get_db().q("SELECT * FROM requisito_auxiliatura WHERE convocatoria_id = ? ORDER BY orden, id", [cid])


def agregar_requisito(cid: int, texto: str, acredita: str) -> list[str]:
    texto = (texto or "").strip()
    if not texto or acredita not in ("documento", "declaracion"):
        return ["Escriba el requisito y cómo se acredita."]
    orden = get_db().q("SELECT COALESCE(MAX(orden), 0) + 1 n FROM requisito_auxiliatura WHERE convocatoria_id = ?", [cid])[0]["n"]
    get_db().t.requisito_auxiliatura.insert(convocatoria_id=cid, texto=texto[:400], acredita=acredita, orden=orden)
    return []


def quitar_requisito(cid: int, rid: int):
    get_db().execute("DELETE FROM requisito_auxiliatura WHERE id = ? AND convocatoria_id = ?", [rid, cid])


# --- Ítems y tribunales --------------------------------------------------------------------------------------------------

def items(cid: int) -> list[dict]:
    filas = get_db().q("""SELECT i.*, (SELECT COUNT(*) FROM postulacion_auxiliatura p WHERE p.item_id = i.id
                                          AND p.estado <> 'borrador') AS n_post
                          FROM item_auxiliatura i WHERE i.convocatoria_id = ? ORDER BY i.titulo""", [cid])
    for i in filas:
        i["tribunal"] = tribunal(i["id"])
    return filas


def item(iid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM item_auxiliatura WHERE id = ?", [iid])
    if not filas:
        return None
    i = filas[0]
    i["tribunal"] = tribunal(iid)
    return i


def asignaturas_de_la_oferta(gestion_id: int) -> list[dict]:
    return get_db().q("""SELECT DISTINCT a.id, a.sigla, a.nombre FROM oferta o JOIN asignatura a ON a.id = o.asignatura_id
                         WHERE o.gestion_id = ? AND o.retirada_en IS NULL ORDER BY a.sigla""", [gestion_id])


def proyectos_vigentes() -> list[dict]:
    return get_db().q("SELECT id, nombre FROM proyecto WHERE estado <> 'finalizado' ORDER BY nombre")


def agregar_item(c: dict, d: dict) -> list[str]:
    try:
        plazas = int(d.get("plazas") or 1)
        horas = int(d.get("horas") or 40)
    except ValueError:
        return ["Plazas y horas deben ser números."]
    if not 1 <= plazas <= 20 or horas not in (20, 40):
        return ["Indique de 1 a 20 plazas y 20 o 40 horas al mes."]
    asignatura = proyecto = None
    if c["modalidad"] == "docencia":
        filas = [a for a in asignaturas_de_la_oferta(c["gestion_id"]) if str(a["id"]) == str(d.get("asignatura_id"))]
        if not filas:
            return ["Elija una materia de la oferta de la gestión."]
        asignatura, titulo = filas[0]["id"], f"{filas[0]['sigla']} {filas[0]['nombre']}"
    else:
        filas = [p for p in proyectos_vigentes() if str(p["id"]) == str(d.get("proyecto_id"))]
        titulo = (d.get("titulo") or "").strip()
        if filas:
            proyecto, titulo = filas[0]["id"], titulo or filas[0]["nombre"]
        if not titulo:
            return ["Elija el proyecto o escriba el nombre de la auxiliatura."]
    if any(i["titulo"] == titulo for i in items(c["id"])):
        return ["Ese ítem ya está en la convocatoria."]
    get_db().t.item_auxiliatura.insert(convocatoria_id=c["id"], asignatura_id=asignatura, proyecto_id=proyecto,
                                       titulo=titulo[:200], plazas=plazas, horas=horas)
    return []


def quitar_item(cid: int, iid: int):
    get_db().execute("DELETE FROM item_auxiliatura WHERE id = ? AND convocatoria_id = ?", [iid, cid])


def tribunal(iid: int) -> list[dict]:
    return get_db().q("""SELECT t.*, u.nombres, u.apellidos, u.email FROM tribunal_auxiliatura t
                         JOIN usuario u ON u.id = t.usuario_id WHERE t.item_id = ? ORDER BY t.tipo, u.apellidos""", [iid])


def docentes_elegibles() -> list[dict]:
    return [u for u in usuarios.listar() if u["activo"] and u["categoria"]]


def estudiantes_elegibles() -> list[dict]:
    """Estudiantes con cuenta activa (pueden integrar un tribunal: art. 16)."""
    return get_db().q("""SELECT u.id, u.nombres, u.apellidos, u.email FROM cuenta_estudiante c JOIN usuario u ON u.id = c.usuario_id
                         WHERE u.activo = 1 ORDER BY u.apellidos, u.nombres""")


def _postulantes_de_conv(cid: int) -> set[int]:
    """Cuentas de los postulantes (con la postulación enviada) de la convocatoria."""
    return {f["usuario_id"] for f in get_db().q(
        """SELECT c.usuario_id FROM postulacion_auxiliatura p JOIN item_auxiliatura i ON i.id = p.item_id
           JOIN cuenta_estudiante c ON c.externo_id = p.externo_id
           WHERE i.convocatoria_id = ? AND p.estado <> 'borrador'""", [cid])}


def fijar_tribunal(it: dict, docentes: list[int], estudiantes_: list[int]) -> list[str]:
    docentes, estudiantes_ = [d for d in docentes if d], [e for e in estudiantes_ if e]
    if len(set(docentes)) != 2 or len(set(estudiantes_)) != 2:
        return ["El tribunal es de dos docentes y dos estudiantes distintos."]
    if not set(docentes) <= {d["id"] for d in docentes_elegibles()}:
        return ["Los docentes deben tener vínculo vigente con la Carrera."]
    if not set(estudiantes_) <= {e["id"] for e in estudiantes_elegibles()}:
        return ["Los estudiantes deben tener cuenta en el sistema."]
    if set(estudiantes_) & _postulantes_de_conv(it["convocatoria_id"]):
        return ["Un postulante de esta convocatoria no puede integrar su tribunal (art. 8)."]
    with transaccion():
        get_db().execute("DELETE FROM tribunal_auxiliatura WHERE item_id = ?", [it["id"]])
        for u in docentes:
            get_db().t.tribunal_auxiliatura.insert(item_id=it["id"], usuario_id=u, tipo="docente")
        for u in estudiantes_:
            get_db().t.tribunal_auxiliatura.insert(item_id=it["id"], usuario_id=u, tipo="estudiante")
    return []


def es_miembro(iid: int, uid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM tribunal_auxiliatura WHERE item_id = ? AND usuario_id = ?", [iid, uid])
    return filas[0] if filas else None


def items_de_miembro(uid: int) -> list[dict]:
    filas = get_db().q("""SELECT i.*, c.titulo AS convocatoria, c.estado AS estado_conv, t.tipo AS mi_tipo
                          FROM tribunal_auxiliatura t JOIN item_auxiliatura i ON i.id = t.item_id
                          JOIN convocatoria_auxiliatura c ON c.id = i.convocatoria_id
                          WHERE t.usuario_id = ? AND c.estado <> 'borrador' ORDER BY i.fase = 'concluido', c.id DESC""", [uid])
    for i in filas:
        i["por_calificar"] = por_calificar(i, uid)
    return filas


def faltantes_publicar(c: dict) -> list[str]:
    f = []
    if not c["resolucion"]:
        f.append("el número de la resolución del Consejo de Carrera")
    if not (c["publicacion"] and c["cierre"] and c["examen"]):
        f.append("las fechas de publicación, cierre y examen escrito")
    its = items(c["id"])
    if not its:
        f.append("al menos un ítem")
    elif any(len(i["tribunal"]) < 4 for i in its):
        f.append("el tribunal completo de cada ítem")
    return f


def publicar(cid: int) -> list[str]:
    c = obtener(cid)
    if not c or c["estado"] != "borrador":
        return ["Solo se publica un borrador."]
    if (f := faltantes_publicar(c)):
        return ["Falta " + ", ".join(f) + "."]
    with transaccion():
        get_db().execute("UPDATE convocatoria_auxiliatura SET estado = 'publicada' WHERE id = ?", [cid])
        for u in get_db().q("""SELECT u.* FROM cuenta_estudiante c JOIN usuario u ON u.id = c.usuario_id WHERE u.activo = 1"""):
            notificaciones.avisar(u, f"Convocatoria: {c['titulo']}",
                                  f"Puede postular hasta el {formato.momento(c['cierre'])}.", "/estudiante/auxiliaturas")
        for it in items(cid):
            for m in it["tribunal"]:
                notificaciones.avisar(usuarios.por_id(m["usuario_id"]), f"Integra el tribunal de {it['titulo']}",
                                      f"Convocatoria «{c['titulo']}».", url_miembro(m["usuario_id"], it["id"]))
    return []


def url_miembro(uid: int, iid: int) -> str:
    return f"/estudiante/tribunal/{iid}" if estudiantes.cuenta_de(uid) else f"/servicios/auxiliaturas/item/{iid}"


def abiertas() -> list[dict]:
    """Convocatorias publicadas con la recepción abierta (para los estudiantes)."""
    filas = get_db().q("""SELECT c.*, g.anio, g.tipo AS gestion_tipo FROM convocatoria_auxiliatura c
                          JOIN gestion_academica g ON g.id = c.gestion_id
                          WHERE c.estado = 'publicada' AND c.cierre >= ? ORDER BY c.cierre""", [_ahora()])
    for c in filas:
        c["items"] = items(c["id"])
    return filas


# --- Postulaciones --------------------------------------------------------------------------------------------------------

def postulacion(pid: int) -> dict | None:
    filas = get_db().q("""SELECT p.*, i.titulo AS item_titulo, i.fase, i.asignatura_id, i.convocatoria_id, i.plazas, i.horas,
                                 c.titulo AS convocatoria, c.cierre, c.examen, c.lugar, c.estado AS estado_conv,
                                 pe.nombres, pe.apellidos
                          FROM postulacion_auxiliatura p JOIN item_auxiliatura i ON i.id = p.item_id
                          JOIN convocatoria_auxiliatura c ON c.id = i.convocatoria_id
                          JOIN persona_externa pe ON pe.id = p.externo_id WHERE p.id = ?""", [pid])
    return filas[0] if filas else None


def de_estudiante(externo_id: int) -> list[dict]:
    ids = get_db().q("SELECT id FROM postulacion_auxiliatura WHERE externo_id = ? ORDER BY id DESC", [externo_id])
    return [postulacion(f["id"]) for f in ids]


def postular(iid: int, externo_id: int) -> tuple[int | None, list[str]]:
    """Crea (o devuelve) la postulación en borrador del estudiante al ítem."""
    it = item(iid)
    c = obtener(it["convocatoria_id"]) if it else None
    if not c or c["estado"] != "publicada" or it["fase"] != "postulacion" or (c["cierre"] or "") < _ahora():
        return None, ["La recepción de postulaciones de este ítem no está abierta."]
    u = estudiantes.usuario_de(externo_id)
    if u and any(es_miembro(i["id"], u["id"]) for i in items(c["id"])):
        return None, ["Usted integra un tribunal de esta convocatoria: no puede postular a ella (art. 8)."]
    ya = get_db().q("SELECT id FROM postulacion_auxiliatura WHERE item_id = ? AND externo_id = ?", [iid, externo_id])
    if ya:
        return ya[0]["id"], []
    pid = get_db().t.postulacion_auxiliatura.insert(item_id=iid, externo_id=externo_id)["id"]
    return pid, []


def veces_auxiliar(externo_id: int, asignatura_id: int | None, excluir_conv: int | None = None) -> int:
    if not asignatura_id:
        return 0
    return get_db().q("""SELECT COUNT(DISTINCT c.gestion_id) n FROM postulacion_auxiliatura p
                         JOIN item_auxiliatura i ON i.id = p.item_id JOIN convocatoria_auxiliatura c ON c.id = i.convocatoria_id
                         WHERE p.externo_id = ? AND i.asignatura_id = ? AND p.estado = 'titular' AND c.id IS NOT ?""",
                      [externo_id, asignatura_id, excluir_conv])[0]["n"]


def _fila_requisito(pid: int, rid: int) -> dict:
    filas = get_db().q("SELECT * FROM postulacion_requisito WHERE postulacion_id = ? AND requisito_id = ?", [pid, rid])
    if filas:
        return filas[0]
    return get_db().t.postulacion_requisito.insert(postulacion_id=pid, requisito_id=rid)


def requisitos_de(p: dict) -> list[dict]:
    """Requisitos de la convocatoria con su estado para la postulación: cumplido, documentos y detalle."""
    from app.investigacion import adjuntos
    res = []
    for r in requisitos(p["convocatoria_id"]):
        fila = _fila_requisito(p["id"], r["id"])
        docs = adjuntos.listar("requisito_postulacion", fila["id"])
        if r["acredita"] == "documento":
            cumplido, detalle = bool(docs), (", ".join(d["nombre"] for d in docs) or "falta el documento")
        elif r["acredita"] == "declaracion":
            cumplido, detalle = bool(fila["declarado"]), ("declarado" if fila["declarado"] else "falta declarar")
        else:
            n = veces_auxiliar(p["externo_id"], p["asignatura_id"], p["convocatoria_id"])
            cumplido, detalle = n < MAX_GESTIONES, f"verificado por el sistema ({n} gestiones como auxiliar)"
        res.append({**r, "fila": fila["id"], "cumplido": cumplido, "detalle": detalle, "documentos": docs})
    return res


def declarar(pid: int, rid: int, valor: bool):
    fila = _fila_requisito(pid, rid)
    get_db().execute("UPDATE postulacion_requisito SET declarado = ? WHERE id = ?", [int(valor), fila["id"]])


def guardar_propuesta(pid: int, texto: str):
    get_db().execute("UPDATE postulacion_auxiliatura SET propuesta = ? WHERE id = ? AND estado = 'borrador'",
                     [(texto or "").strip()[:4000], pid])


def faltantes_envio(p: dict) -> list[str]:
    f = [r["texto"] for r in requisitos_de(p) if not r["cumplido"]]
    if not (p["propuesta"] or "").strip():
        f.append("Propuesta de trabajo")
    return f


def abierta(p: dict) -> bool:
    return p["estado_conv"] == "publicada" and p["fase"] == "postulacion" and (p["cierre"] or "") >= _ahora()


def enviar(pid: int) -> list[str]:
    p = postulacion(pid)
    if not p or p["estado"] != "borrador":
        return ["La postulación ya fue enviada."]
    if not abierta(p):
        return ["La recepción de postulaciones ya cerró."]
    if (f := faltantes_envio(p)):
        return ["Falta: " + "; ".join(f) + "."]
    get_db().execute(f"UPDATE postulacion_auxiliatura SET estado = 'enviada', enviada_en = {AHORA} WHERE id = ?", [pid])
    return []


def retirar(pid: int) -> list[str]:
    p = postulacion(pid)
    if not p or p["estado"] != "enviada" or not abierta(p):
        return ["Solo se retira una postulación enviada mientras la recepción está abierta."]
    get_db().execute("UPDATE postulacion_auxiliatura SET estado = 'borrador', enviada_en = NULL WHERE id = ?", [pid])
    return []


def eliminar_borrador(pid: int):
    from app.investigacion import adjuntos
    for f in get_db().q("SELECT id FROM postulacion_requisito WHERE postulacion_id = ?", [pid]):
        adjuntos.eliminar_de("requisito_postulacion", f["id"])
        get_db().execute("DELETE FROM adjunto WHERE entidad = 'requisito_postulacion' AND entidad_id = ?", [f["id"]])
    get_db().execute("DELETE FROM postulacion_auxiliatura WHERE id = ? AND estado = 'borrador'", [pid])


# --- Calificación ----------------------------------------------------------------------------------------------------------

def en_concurso(iid: int) -> list[dict]:
    return get_db().q("""SELECT p.*, pe.nombres, pe.apellidos FROM postulacion_auxiliatura p
                         JOIN persona_externa pe ON pe.id = p.externo_id
                         WHERE p.item_id = ? AND p.estado <> 'borrador' ORDER BY pe.apellidos, pe.nombres""", [iid])


def activos(iid: int) -> list[dict]:
    """Postulantes que siguen en la fase en curso."""
    return [p for p in en_concurso(iid) if p["estado"] == "enviada"]


def calificaciones(pid: int, fase: str) -> list[dict]:
    return get_db().q("SELECT * FROM calificacion_auxiliatura WHERE postulacion_id = ? AND fase = ?", [pid, fase])


def nota(pid: int, fase: str) -> float | None:
    cs = calificaciones(pid, fase)
    return round(sum(c["valor"] for c in cs) / len(cs), 2) if cs else None


def calificar(it: dict, uid: int, pid: int, valor, observacion: str = "") -> list[str]:
    fase = it["fase"]
    if fase not in FASES:
        return ["No hay una fase por calificar."]
    if not es_miembro(it["id"], uid):
        return ["Solo califican los miembros del tribunal."]
    if pid not in {p["id"] for p in activos(it["id"])}:
        return ["Ese postulante no está en esta fase."]
    try:
        v = float(str(valor).replace(",", "."))
    except ValueError:
        return ["Escriba un número."]
    if not 0 <= v <= MAXIMO[fase]:
        return [f"La nota va de 0 a {MAXIMO[fase]}."]
    get_db().execute(f"""INSERT INTO calificacion_auxiliatura (postulacion_id, fase, miembro_id, valor, observacion)
                         VALUES (?, ?, ?, ?, ?) ON CONFLICT (postulacion_id, fase, miembro_id)
                         DO UPDATE SET valor = excluded.valor, observacion = excluded.observacion, registrado_en = {AHORA}""",
                     [pid, fase, uid, v, (observacion or "").strip()[:1000] or None])
    return []


def por_calificar(it: dict, uid: int) -> int:
    if it["fase"] not in FASES:
        return 0
    return sum(1 for p in activos(it["id"])
               if not get_db().q("SELECT 1 FROM calificacion_auxiliatura WHERE postulacion_id = ? AND fase = ? AND miembro_id = ?",
                                 [p["id"], it["fase"], uid]))


def cierre_de(iid: int, fase: str) -> dict | None:
    filas = get_db().q("SELECT * FROM fase_auxiliatura WHERE item_id = ? AND fase = ?", [iid, fase])
    return filas[0] if filas else None


def impugnaciones(iid: int) -> list[dict]:
    return get_db().q("""SELECT m.*, pe.nombres, pe.apellidos FROM impugnacion_auxiliatura m
                         JOIN postulacion_auxiliatura p ON p.id = m.postulacion_id JOIN persona_externa pe ON pe.id = p.externo_id
                         WHERE p.item_id = ? ORDER BY m.id""", [iid])


def anterior(fase: str) -> str:
    orden = ("postulacion", *FASES)
    return orden[orden.index(fase) - 1]


def faltantes_cierre(it: dict, ahora: datetime | None = None) -> list[str]:
    fase = it["fase"]
    if fase == "postulacion":
        c = obtener(it["convocatoria_id"])
        return [] if (c["cierre"] or "9999") <= _ahora() else [f"La recepción cierra el {formato.momento(c['cierre'])}."]
    if fase not in FASES:
        return ["El concurso de este ítem ya concluyó."]
    f = []
    previo = cierre_de(it["id"], anterior(fase))
    ahora = ahora or datetime.now(timezone.utc).replace(tzinfo=None)
    if fase != "habilitacion" and previo and \
            datetime.fromisoformat(previo["cerrada_en"]) + timedelta(hours=HORAS_IMPUGNACION) > ahora:
        f.append("aún corren las 24 horas para impugnar la fase anterior")
    if any(not m["resolucion"] for m in impugnaciones(it["id"])):
        f.append("hay impugnaciones sin resolver")
    cortos = [p for p in activos(it["id"]) if len(calificaciones(p["id"], fase)) < QUORUM]
    if cortos:
        f.append(f"{len(cortos)} postulante(s) con menos de {QUORUM} calificaciones")
    return f


def cerrar_fase(it: dict, uid: int) -> list[str]:
    if (f := faltantes_cierre(it)):
        return ["No se puede cerrar: " + "; ".join(f) + "."]
    fase = it["fase"]
    orden = ("postulacion", *FASES, "concluido")
    siguiente = orden[orden.index(fase) + 1]
    with transaccion():
        get_db().t.fase_auxiliatura.insert(item_id=it["id"], fase=fase, cerrada_por=uid)
        if fase == "habilitacion":
            for p in activos(it["id"]):
                if (nota(p["id"], fase) or 0) <= 0.5:   # mayoría de «sí»; un empate no habilita
                    get_db().execute("UPDATE postulacion_auxiliatura SET estado = 'no_habilitada', fase_fin = ? WHERE id = ?",
                                     [fase, p["id"]])
        elif fase in MINIMO:
            for p in activos(it["id"]):
                if (nota(p["id"], fase) or 0) < MINIMO[fase]:
                    get_db().execute("UPDATE postulacion_auxiliatura SET estado = 'eliminada', fase_fin = ? WHERE id = ?",
                                     [fase, p["id"]])
        elif fase == "oral":
            _resultado(it)
        get_db().execute("UPDATE item_auxiliatura SET fase = ? WHERE id = ?", [siguiente, it["id"]])
        if fase != "postulacion":
            for p in en_concurso(it["id"]):
                if p["estado"] != "no_habilitada" or fase == "habilitacion":
                    notificaciones.avisar(estudiantes.usuario_de(p["externo_id"]),
                                          f"Resultado: {NOMBRE_FASE[fase]} · {it['titulo']}",
                                          f"Ya puede ver su resultado. Tiene {HORAS_IMPUGNACION} horas para impugnar por "
                                          "escrito ante la Dirección de Carrera.", f"/estudiante/auxiliaturas/{p['id']}")
        _concluir_si_corresponde(it["convocatoria_id"])
    return []


def total(pid: int) -> float:
    return round(sum(nota(pid, f) or 0 for f in ("meritos", "escrito", "oral")), 2)


def _resultado(it: dict):
    finalistas = sorted(activos(it["id"]), key=lambda p: total(p["id"]), reverse=True)
    aptos = [p for p in finalistas if total(p["id"]) >= PUNTAJE_TITULAR]
    for p in finalistas:
        get_db().execute("UPDATE postulacion_auxiliatura SET estado = 'no_seleccionada' WHERE id = ?", [p["id"]])
    if not aptos:
        return
    corte = total(aptos[min(it["plazas"], len(aptos)) - 1]["id"])
    arriba = [p for p in aptos if total(p["id"]) > corte]
    en_corte = [p for p in aptos if total(p["id"]) == corte]
    libres = it["plazas"] - len(arriba)
    for p in arriba:
        get_db().execute("UPDATE postulacion_auxiliatura SET estado = 'titular' WHERE id = ?", [p["id"]])
    estado = "titular" if len(en_corte) <= libres else "empate"
    for p in en_corte:
        get_db().execute("UPDATE postulacion_auxiliatura SET estado = ? WHERE id = ?", [estado, p["id"]])


def resolver_empate(it: dict, ganadores: list[int]) -> list[str]:
    empatados = {p["id"] for p in en_concurso(it["id"]) if p["estado"] == "empate"}
    titulares = sum(p["estado"] == "titular" for p in en_concurso(it["id"]))
    if not empatados:
        return ["No hay un empate por resolver."]
    if not set(ganadores) <= empatados or len(set(ganadores)) != it["plazas"] - titulares:
        return [f"Elija {it['plazas'] - titulares} ganador(es) del examen de desempate."]
    with transaccion():
        for pid in empatados:
            get_db().execute("UPDATE postulacion_auxiliatura SET estado = ? WHERE id = ?",
                             ["titular" if pid in ganadores else "no_seleccionada", pid])
        _concluir_si_corresponde(it["convocatoria_id"])
    return []


def _concluir_si_corresponde(cid: int):
    its = items(cid)
    if its and all(i["fase"] == "concluido" for i in its) and not any(
            p["estado"] == "empate" for i in its for p in en_concurso(i["id"])):
        get_db().execute("UPDATE convocatoria_auxiliatura SET estado = 'concluida' WHERE id = ?", [cid])


def sortear_tema(it: dict, temas: str) -> list[str]:
    lista = [t.strip() for t in (temas or "").splitlines() if t.strip()]
    if len(lista) < 2:
        return ["Escriba al menos dos temas, uno por línea."]
    get_db().execute("UPDATE item_auxiliatura SET tema_oral = ? WHERE id = ?", [random.choice(lista)[:300], it["id"]])
    return []


def registrar_impugnacion(it: dict, pid: int, fase: str, presentada_en: str, texto: str, uid: int) -> list[str]:
    if pid not in {p["id"] for p in en_concurso(it["id"])} or fase not in FASES or not cierre_de(it["id"], fase):
        return ["Elija el postulante y una fase ya cerrada."]
    if not (texto or "").strip() or not presentada_en:
        return ["Indique la fecha y el motivo de la impugnación."]
    get_db().t.impugnacion_auxiliatura.insert(postulacion_id=pid, fase=fase, presentada_en=presentada_en,
                                              texto=texto.strip()[:2000], registrada_por=uid)
    return []


def resolver_impugnacion(iid: int, mid: int, resolucion: str) -> list[str]:
    if not (resolucion or "").strip():
        return ["Escriba cómo se resolvió."]
    get_db().execute(f"""UPDATE impugnacion_auxiliatura SET resolucion = ?, resuelta_en = {AHORA}
                         WHERE id = ? AND postulacion_id IN (SELECT id FROM postulacion_auxiliatura WHERE item_id = ?)""",
                     [resolucion.strip()[:2000], mid, iid])
    return []


def puede_conducir(auth: dict, it: dict) -> bool:
    """Cierra fases, sortea el tema y registra impugnaciones: quien gestiona la convocatoria o un docente del tribunal."""
    c = obtener(it["convocatoria_id"])
    m = es_miembro(it["id"], auth["id"])
    return puede_gestionar(auth, c["modalidad"]) or bool(m and m["tipo"] == "docente")


def tabla(it: dict) -> list[dict]:
    """Una fila por postulante con las notas de cada fase (promedios), el total y su estado."""
    res = []
    for p in en_concurso(it["id"]):
        fila = {**p, "notas": {f: nota(p["id"], f) for f in FASES}, "n": {f: len(calificaciones(p["id"], f)) for f in FASES}}
        fila["total"] = total(p["id"]) if it["fase"] == "concluido" else None
        res.append(fila)
    return sorted(res, key=lambda r: (-(r["total"] or 0), r["apellidos"]))


def fases_publicadas(iid: int) -> set[str]:
    return {f["fase"] for f in get_db().q("SELECT fase FROM fase_auxiliatura WHERE item_id = ?", [iid])}


def hoy_texto(iso: str | None) -> str:
    return formato.momento(iso)
