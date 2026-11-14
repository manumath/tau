"""Convocatorias a auxiliaturas (PLAN §58, servicio 3; adecuadas en el §70), según el Reglamento Específico de Auxiliares
Académicos del Pregrado de la UMSA (Res. HCU 424/2023, modificada por la 364/2025). Dejó sin efecto el Reglamento General (Res. HCU
251/2021, mod. 437/2021 y 623/2021) con que se hicieron las primeras convocatorias: cada una guarda su `reglamento` y conserva sus reglas.

- La Dirección de Carrera o la Coordinación académica arma la convocatoria de un **semestre regular** (gestión I o II; no hay
  auxiliaturas de temporada) de **docencia** (materias de la oferta) o de **investigación** (proyectos; también la Dirección del
  Instituto). Requisitos, cada uno con cómo se acredita: documento, declaración o lo verifica el sistema.
- Cada ítem tiene un **tribunal de dos docentes y dos estudiantes** (decisión 1 del 7-nov-2026). Un postulante de la
  convocatoria no puede integrar un tribunal de ella.
- Se publica solo con el **número de la resolución** del Consejo de Carrera (el PDF es opcional; decisión 5).
- Fases: postulación → habilitación → méritos (30) → escrito (35) → oral (35). Los mínimos dependen del reglamento (ver `REGLAS`).
  Cada miembro califica; la nota es el promedio y hacen falta **al menos tres miembros** (decisión 4). Titular con 56 o más, por
  puntaje hasta cubrir las plazas; un empate en el corte queda «empate» hasta el examen de desempate.
- Al cerrar una fase cada postulante ve su resultado y corren 24 horas para impugnar. Las impugnaciones se presentan por escrito:
  TAU solo las registra (decisión 8), y no se cierra otra fase mientras haya alguna sin resolver.
"""
import random
from datetime import date, datetime, timedelta, timezone

from app.comun import estudiantes, formato, notificaciones, permisos, usuarios
from app.comun.db import AHORA, get_db, transaccion
from app.servicios import rubricas

MODALIDADES = {"docencia": "Docencia", "investigacion": "Investigación", "interaccion_social": "Interacción social",
               "beca_tesis": "Beca Tesis (investigación)"}
CON_PROYECTO = ("investigacion", "interaccion_social", "beca_tesis")    # sus ítems son proyectos, no materias de la oferta
ACREDITA = {"documento": "Documento", "declaracion": "Declaración jurada", "sistema": "Lo verifica el sistema"}
ESTADOS_CONV = {"borrador": "Borrador", "publicada": "Publicada", "concluida": "Concluida"}
FASES = ("habilitacion", "meritos", "escrito", "oral")
NOMBRE_FASE = {"postulacion": "Postulación", "habilitacion": "Habilitación", "meritos": "Méritos",
               "escrito": "Examen escrito", "oral": "Examen oral", "concluido": "Resultado"}
MAXIMO = {"habilitacion": 1, "meritos": 30, "escrito": 35, "oral": 35}
PUNTAJE_TITULAR = 56
QUORUM = 3                 # miembros que deben calificar cada fase (decisión 4 del 7-nov-2026)
HORAS_IMPUGNACION = 24     # impugnar al cierre de cada fase (art. 21 del reglamento de 2023)
MAX_GESTIONES = 2          # art. 10, f): no más de dos gestiones en la misma materia, proyecto o programa
MAX_MATERIAS = 2           # art. 10, g): como máximo dos materias por convocatoria
HORAS_SEGUNDA = 72         # arts. 13 y 14: la segunda convocatoria sale hasta 72 horas después de los resultados de la primera
GESTIONES_CONVOCABLES = ("I", "II")     # las auxiliaturas son de los semestres regulares, no de INV ni VER (decisión del 14-nov-2026)

REGLAMENTO_ANTERIOR = "hcu_251_2021"
REGLAMENTO_VIGENTE = "hcu_424_2023"
REGLAMENTOS = {REGLAMENTO_ANTERIOR: "Reglamento General de Auxiliares Académicos (Res. HCU 251/2021, mod. 437/2021 y 623/2021)",
               REGLAMENTO_VIGENTE: "Reglamento Específico de Auxiliares Académicos del Pregrado (Res. HCU 424/2023, mod. 364/2025)"}
# Reglas que cambian de un reglamento a otro. Una convocatoria usa siempre las del reglamento con que se hizo.
REGLAS = {
    REGLAMENTO_ANTERIOR: {"minimo": {"meritos": 10, "escrito": 17.5}, "plazo": "publicacion_examen", "dias_primera": 10, "dias_segunda": 5},
    REGLAMENTO_VIGENTE: {"minimo": {"meritos": 5, "escrito": 18}, "plazo": "publicacion_cierre", "dias_primera": 10, "dias_segunda": 5},
}
ESTADOS_POST = {"borrador": "Sin enviar", "enviada": "En concurso", "no_habilitada": "No habilitada",
                "eliminada": "No alcanzó el mínimo", "titular": "Auxiliar titular", "no_seleccionada": "No seleccionada",
                "empate": "Empate: examen de desempate"}
def requisitos_reglamento(modalidad: str) -> list[tuple[str, str, int, str | None]]:
    """Requisitos que una convocatoria nueva trae precargados (reglamento de 2023: art. 23, documentos, y art. 10, condiciones):
    (texto, cómo se acredita, opcional, clave de lo que verifica el sistema). La Carrera puede agregar los suyos (art. 10, p)."""
    beca = modalidad == "beca_tesis"
    pedidos = [
        ("Nota dirigida a la Dirección de Carrera", "documento", 0, None),
        ("Fotocopia del carnet de identidad", "documento", 0, None),
        ("Récord académico impreso, con sello de Kardex o de la Dirección de Carrera", "documento", 0, None),
        ("Certificado de Kardex con la fecha y la gestión de conclusión de estudios" +
         ("" if beca else " (solo egresados, que pueden postular durante los dos años siguientes)"), "documento", 0 if beca else 1, None),
        ("Currículum vitae documentado, con respaldos", "documento", 0, None),
        ("Carta de compromiso de cumplimiento de la carga horaria y las funciones asignadas", "documento", 0, None),
    ]
    if beca:
        pedidos.append(("Proyecto de investigación aprobado por el Consejo de Carrera y homologado por el Consejo Facultativo",
                        "documento", 0, None))
    else:
        pedidos.append(("Declaro ser estudiante regular de la Universidad, haber aprobado al menos una asignatura el periodo anterior "
                        "y la totalidad de las del periodo de la materia a la que postulo (según el plan de mi Carrera de origen)",
                        "declaracion", 0, None))
    pedidos += [
        ("Declaro no tener título profesional de ningún nivel (las auxiliaturas son solo para estudiantes de pregrado)", "declaracion", 0, None),
        ("Declaro no haber sido auxiliar más de dos gestiones en la misma materia, proyecto o programa (ni más de dos gestiones o cuatro "
         "semestres si lo fui en otras carreras)", "declaracion", 0, None),
        ("Si soy delegado estudiantil ante un Consejo, tengo licencia mientras dura el proceso y no integro la comisión", "declaracion", 0, None),
        ("Presento mis documentos foliados y en el orden establecido, en sobre cerrado", "declaracion", 0, None),
        ("No haber sido auxiliar de esta materia o proyecto en dos gestiones (lo verifica el sistema con sus registros)", "sistema", 0, "gestiones"),
        ("No postular a más de dos materias en esta convocatoria (lo verifica el sistema)", "sistema", 0, "materias"),
    ]
    return pedidos


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


# --- Permisos -------------------------------------------------------------------------------------------------------

def puede_gestionar(auth: dict, modalidad: str | None = None) -> bool:
    if modalidad in CON_PROYECTO:      # también las de interacción social y Beca Tesis las gestiona la Dirección del Instituto
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
    """Gestiones en que se puede convocar: los semestres regulares (I y II), no las temporadas."""
    marcas = ",".join("?" * len(GESTIONES_CONVOCABLES))
    return get_db().q(f"SELECT * FROM gestion_academica WHERE tipo IN ({marcas}) ORDER BY anio DESC, fecha_inicio DESC",
                      list(GESTIONES_CONVOCABLES))


def reglas(c: dict | None) -> dict:
    """Las reglas del reglamento con que se hizo la convocatoria (las nuevas, el de 2023)."""
    return REGLAS[(c or {}).get("reglamento") or REGLAMENTO_VIGENTE]


def reglas_de_item(it: dict) -> dict:
    return reglas(obtener(it["convocatoria_id"]))


def minimo(it: dict, fase: str) -> float | None:
    """Nota mínima de la fase para seguir en el concurso (None si la fase no tiene)."""
    return reglas_de_item(it)["minimo"].get(fase)


def reglamento_texto(c: dict) -> str:
    return REGLAMENTOS[c.get("reglamento") or REGLAMENTO_VIGENTE]


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
    gestion = get_db().q("SELECT tipo FROM gestion_academica WHERE id = ?", [gid])
    if not gestion:
        errores.append("Elija la gestión.")
    elif gestion[0]["tipo"] not in GESTIONES_CONVOCABLES:
        errores.append("Las auxiliaturas se convocan para los semestres I y II, no para los periodos de temporada.")
    numero = 2 if str(d.get("numero")) == "2" else 1
    x = {"modalidad": d.get("modalidad"), "gestion_id": gid, "numero": numero,
         "titulo": (d.get("titulo") or "").strip()[:200],
         "publicacion": (d.get("publicacion") or "").strip() or None,
         "cierre": (d.get("cierre") or "").strip() or None, "examen": (d.get("examen") or "").strip() or None,
         "lugar": (d.get("lugar") or "").strip()[:200] or None, "resolucion": (d.get("resolucion") or "").strip()[:120] or None,
         "resolucion_hcf": (d.get("resolucion_hcf") or "").strip()[:120] or None,
         "recepcion_lugar": (d.get("recepcion_lugar") or "").strip()[:200] or None,
         "recepcion_horario": (d.get("recepcion_horario") or "").strip()[:120] or None}
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
        cid = get_db().t.convocatoria_auxiliatura.insert(creado_por=uid, reglamento=REGLAMENTO_VIGENTE, **x)["id"]
        for i, (texto, acredita, opcional, clave) in enumerate(requisitos_reglamento(x["modalidad"])):
            get_db().t.requisito_auxiliatura.insert(convocatoria_id=cid, texto=texto, acredita=acredita, opcional=opcional,
                                                    clave=clave, orden=i)
    return cid


def editar(cid: int, x: dict):
    get_db().t.convocatoria_auxiliatura.update(id=cid, **x)


def eliminar(cid: int):
    get_db().execute("DELETE FROM convocatoria_auxiliatura WHERE id = ? AND estado = 'borrador'", [cid])


def chequeo_fechas(c: dict) -> tuple[bool, str] | None:
    """Plazo mínimo para presentar los documentos. Reglamento de 2023 (art. 24): 10 días hábiles desde la publicación en la primera
    convocatoria y 5 en la segunda, hasta el cierre de la recepción. El de 2021 lo contaba hasta el examen escrito."""
    r = reglas(c)
    destino = "examen" if r["plazo"] == "publicacion_examen" else "cierre"
    if not c["publicacion"] or not c[destino]:
        return None
    pedidos = r["dias_primera"] if c["numero"] == 1 else r["dias_segunda"]
    n = habiles_entre(date.fromisoformat(c["publicacion"][:10]), date.fromisoformat(c[destino][:10]))
    hasta, art = ("el examen escrito", "10") if destino == "examen" else ("el cierre de la recepción", "24")
    if n >= pedidos:
        return True, f"Hay {n} días hábiles entre la publicación y {hasta} (el art. {art} pide {pedidos})."
    return False, f"Solo hay {n} días hábiles entre la publicación y {hasta}; el art. {art} pide {pedidos}."


def _semana(d: date, desde: int, hasta: int, mes: int, anio: int) -> bool:
    return d.year == anio and d.month == mes and desde <= d.day <= hasta


def chequeo_calendario(c: dict) -> tuple[bool, str] | None:
    """Calendario de publicación del art. 12 del reglamento de 2023 (régimen semestral). Solo advierte; «semana» se cuenta por
    días del mes (1.ª: del 1 al 7; 2.ª: del 8 al 14). Una carrera que emite una sola convocatoria para los dos semestres publica
    la primera semana de noviembre."""
    if (c.get("reglamento") or REGLAMENTO_VIGENTE) != REGLAMENTO_VIGENTE or not c["publicacion"]:
        return None
    g = get_db().q("SELECT anio, tipo FROM gestion_academica WHERE id = ?", [c["gestion_id"]])
    if not g or g[0]["tipo"] not in GESTIONES_CONVOCABLES:
        return None
    anio, tipo, d = g[0]["anio"], g[0]["tipo"], date.fromisoformat(c["publicacion"][:10])
    if tipo == "I":
        previstas = {1: ("la 2.ª semana de noviembre", (8, 14, 11, anio - 1)), 2: ("la 1.ª semana de diciembre", (1, 7, 12, anio - 1))}
    else:
        previstas = {1: ("la 2.ª semana de mayo", (8, 14, 5, anio)), 2: ("la 2.ª semana de junio", (8, 14, 6, anio))}
    texto, ventana = previstas[c["numero"]]
    unica = c["numero"] == 1 and _semana(d, 1, 7, 11, anio - 1)
    if _semana(d, *ventana) or unica:
        return True, f"La publicación cae en la fecha que pide el art. 12 ({texto}{', o la 1.ª de noviembre si es una sola convocatoria' if unica else ''})."
    return False, (f"El art. 12 pide publicar la {'primera' if c['numero'] == 1 else 'segunda'} convocatoria en {texto} "
                   "(o, si es una sola para los dos semestres, en la 1.ª semana de noviembre).")


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


def proyectos_vigentes(modalidad: str = "investigacion") -> list[dict]:
    """Proyectos en que se puede convocar: los de interacción social para esa modalidad y los de investigación (o individuales,
    sin clase) para las demás."""
    filtro = "clase = 'interaccion_social'" if modalidad == "interaccion_social" else "(clase IS NULL OR clase <> 'interaccion_social')"
    return get_db().q(f"SELECT id, nombre FROM proyecto WHERE estado <> 'finalizado' AND {filtro} ORDER BY nombre")


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
        filas = [p for p in proyectos_vigentes(c["modalidad"]) if str(p["id"]) == str(d.get("proyecto_id"))]
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
    """Estudiantes con cuenta activa (pueden integrar un tribunal)."""
    return get_db().q("""SELECT u.id, u.nombres, u.apellidos, u.email FROM cuenta_estudiante c JOIN usuario u ON u.id = c.usuario_id
                         WHERE u.activo = 1 ORDER BY u.apellidos, u.nombres""")


def _postulantes_de_conv(cid: int) -> set[int]:
    """Cuentas de los postulantes (con la postulación enviada) de la convocatoria."""
    return {f["usuario_id"] for f in get_db().q(
        """SELECT c.usuario_id FROM postulacion_auxiliatura p JOIN item_auxiliatura i ON i.id = p.item_id
           JOIN cuenta_estudiante c ON c.externo_id = p.externo_id
           WHERE i.convocatoria_id = ? AND p.estado <> 'borrador'""", [cid])}


COMISION_TEXTO = {
    "docencia": "Un docente titular responsable de la materia y otro docente titular del área, y dos estudiantes que aprobaron la materia con "
                "los mejores promedios, designados en instancias de cogobierno (art. 15, a).",
    "investigacion": "Dos docentes investigadores titulares y dos estudiantes que aprobaron la materia afín con los mejores promedios, "
                     "designados en instancias de cogobierno (art. 15, b).",
    "interaccion_social": "El responsable del proyecto (o jefe de prácticas o laboratorio) y un docente titular relacionado con su "
                          "especialidad, y dos estudiantes que aprobaron la materia afín con los mejores promedios (art. 15, c).",
}
COMISION_TEXTO["beca_tesis"] = COMISION_TEXTO["investigacion"]


def _titulares_de_la_materia(c: dict, it: dict) -> set[int]:
    """Docentes titulares de la materia del ítem en la gestión (los de sus paralelos, con la asignación vigente)."""
    if not it.get("asignatura_id"):
        return set()
    return {f["usuario_id"] for f in get_db().q(
        """SELECT DISTINCT d.usuario_id FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id
           WHERE o.gestion_id = ? AND o.asignatura_id = ? AND d.rol = 'titular' AND d.hasta IS NULL AND o.retirada_en IS NULL""",
        [c["gestion_id"], it["asignatura_id"]])}


def revisar_comision(c: dict, it: dict, docentes: list[int]) -> tuple[list[str], list[str]]:
    """Reglas del art. 15 (reglamento de 2023) para los dos docentes de la comisión: (errores, avisos). Un aviso es algo que todavía no se
    puede comprobar (la materia aún no tiene titular asignado, el ítem no tiene proyecto)."""
    if (c.get("reglamento") or REGLAMENTO_VIGENTE) != REGLAMENTO_VIGENTE:
        return [], []
    errores, avisos = [], []
    perfiles = [usuarios.con_perfil(u) for u in docentes]
    if any(not x or x["categoria"] != "titular" for x in perfiles):
        errores.append("Los dos docentes de la comisión deben ser titulares (art. 15).")
    if c["modalidad"] == "docencia":
        titulares = _titulares_de_la_materia(c, it)
        if not titulares:
            avisos.append("La materia aún no tiene un docente titular asignado en la gestión: no se pudo comprobar que la comisión "
                          "incluya a su responsable (art. 15, a).")
        elif not set(docentes) & titulares:
            errores.append("Uno de los dos docentes debe ser el titular responsable de la materia en la gestión (art. 15, a).")
    elif c["modalidad"] in ("investigacion", "beca_tesis"):
        if any(not x or not x["es_investigador"] for x in perfiles):
            errores.append("Los dos docentes deben ser investigadores titulares (art. 15, b).")
    elif c["modalidad"] == "interaccion_social":
        if not it.get("proyecto_id"):
            avisos.append("El ítem no tiene proyecto: no se pudo comprobar que la comisión incluya a su responsable (art. 15, c).")
        else:
            from app.investigacion import proyectos
            if not any(proyectos.rol_de(it["proyecto_id"], u) in proyectos.ROLES_RESPONSABLES for u in docentes):
                errores.append("Uno de los dos docentes debe ser el responsable del proyecto (art. 15, c).")
    return errores, avisos


def avisos_comision(it: dict) -> list[str]:
    """Lo que aún no se puede comprobar de la comisión ya designada."""
    docentes = [m["usuario_id"] for m in it["tribunal"] if m["tipo"] == "docente"]
    return revisar_comision(obtener(it["convocatoria_id"]), it, docentes)[1] if len(docentes) == 2 else []


def guardar_resolucion_comision(cid: int, hcc: str, hcf: str):
    get_db().execute("UPDATE convocatoria_auxiliatura SET comision_resolucion = ?, comision_resolucion_hcf = ? WHERE id = ?",
                     [(hcc or "").strip()[:120] or None, (hcf or "").strip()[:120] or None, cid])


def fijar_tribunal(it: dict, docentes: list[int], estudiantes_: list[int]) -> list[str]:
    docentes, estudiantes_ = [d for d in docentes if d], [e for e in estudiantes_ if e]
    if len(set(docentes)) != 2 or len(set(estudiantes_)) != 2:
        return ["El tribunal es de dos docentes y dos estudiantes distintos."]
    if not set(docentes) <= {d["id"] for d in docentes_elegibles()}:
        return ["Los docentes deben tener vínculo vigente con la Carrera."]
    if (errores := revisar_comision(obtener(it["convocatoria_id"]), it, docentes)[0]):
        return errores
    if not set(estudiantes_) <= {e["id"] for e in estudiantes_elegibles()}:
        return ["Los estudiantes deben tener cuenta en el sistema."]
    if set(estudiantes_) & _postulantes_de_conv(it["convocatoria_id"]):
        return ["Un postulante de esta convocatoria no puede integrar su tribunal."]
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
    if (c.get("reglamento") or REGLAMENTO_VIGENTE) == REGLAMENTO_VIGENTE and not (c["recepcion_lugar"] and c["recepcion_horario"]):
        f.append("el lugar y el horario de recepción de los documentos (art. 11)")
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
    filas = get_db().q("""SELECT p.*, i.titulo AS item_titulo, i.fase, i.asignatura_id, i.proyecto_id, i.convocatoria_id, i.plazas, i.horas,
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
        return None, ["Usted integra un tribunal de esta convocatoria: no puede postular a ella."]
    ya = get_db().q("SELECT id FROM postulacion_auxiliatura WHERE item_id = ? AND externo_id = ?", [iid, externo_id])
    if ya:
        return ya[0]["id"], []
    pid = get_db().t.postulacion_auxiliatura.insert(item_id=iid, externo_id=externo_id)["id"]
    return pid, []


def veces_auxiliar(externo_id: int, asignatura_id: int | None, excluir_conv: int | None = None, proyecto_id: int | None = None) -> int:
    """Gestiones en que fue auxiliar titular de la misma materia o del mismo proyecto (art. 10, f)."""
    if not asignatura_id and not proyecto_id:
        return 0
    return get_db().q("""SELECT COUNT(DISTINCT c.gestion_id) n FROM postulacion_auxiliatura p
                         JOIN item_auxiliatura i ON i.id = p.item_id JOIN convocatoria_auxiliatura c ON c.id = i.convocatoria_id
                         WHERE p.externo_id = ? AND p.estado = 'titular' AND c.id IS NOT ?
                           AND (i.asignatura_id = ? OR i.proyecto_id = ?)""",
                      [externo_id, excluir_conv, asignatura_id, proyecto_id])[0]["n"]


def otras_postulaciones(externo_id: int, convocatoria_id: int, excluir_pid: int) -> int:
    """Postulaciones ya enviadas por la persona a otros ítems de la misma convocatoria (art. 10, g: como máximo dos materias)."""
    return get_db().q("""SELECT COUNT(*) n FROM postulacion_auxiliatura p JOIN item_auxiliatura i ON i.id = p.item_id
                         WHERE p.externo_id = ? AND i.convocatoria_id = ? AND p.id <> ? AND p.estado <> 'borrador'""",
                      [externo_id, convocatoria_id, excluir_pid])[0]["n"]


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
        elif r.get("clave") == "materias":
            n = otras_postulaciones(p["externo_id"], p["convocatoria_id"], p["id"]) + 1
            cumplido, detalle = n <= MAX_MATERIAS, f"verificado por el sistema ({n} materia(s) en esta convocatoria)"
        else:
            n = veces_auxiliar(p["externo_id"], p["asignatura_id"], p["convocatoria_id"], p["proyecto_id"])
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
    f = [r["texto"] for r in requisitos_de(p) if not r["cumplido"] and not r["opcional"]]
    if not (p["propuesta"] or "").strip():
        f.append("Plan de trabajo")
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
    _guardar_nota(pid, fase, uid, v, observacion)
    return []


def _guardar_nota(pid: int, fase: str, uid: int, valor: float, observacion: str = ""):
    get_db().execute(f"""INSERT INTO calificacion_auxiliatura (postulacion_id, fase, miembro_id, valor, observacion)
                         VALUES (?, ?, ?, ?, ?) ON CONFLICT (postulacion_id, fase, miembro_id)
                         DO UPDATE SET valor = excluded.valor, observacion = excluded.observacion, registrado_en = {AHORA}""",
                     [pid, fase, uid, valor, (observacion or "").strip()[:1000] or None])


def usa_formularios(c: dict | None) -> bool:
    """¿Los méritos y el examen oral se califican con los formularios del reglamento de 2023 (detalle por línea o criterio)?"""
    return (c or {}).get("reglamento") == REGLAMENTO_VIGENTE


def detalle(pid: int, fase: str, uid: int) -> dict[str, float]:
    """Lo que un miembro anotó en el formulario de méritos o en la rúbrica del oral de un postulante: clave → cantidad."""
    return {f["clave"]: f["cantidad"] for f in get_db().q(
        "SELECT clave, cantidad FROM calificacion_detalle WHERE postulacion_id = ? AND fase = ? AND miembro_id = ?", [pid, fase, uid])}


def puntaje_detalle(c: dict, fase: str, entradas: dict[str, float]) -> float:
    return rubricas.calcular_meritos(c["modalidad"], entradas)["total"] if fase == "meritos" else rubricas.calcular_oral(entradas)


def calificar_detalle(it: dict, uid: int, pid: int, crudo: dict, observacion: str = "") -> list[str]:
    """Califica un postulante en méritos (formularios 2-1, 2-2 o 2-3) o en el examen oral (formulario 4) con el detalle por línea o criterio;
    la calificación del miembro es la suma (con los topes del formulario) y entra al promedio de la fase como cualquier otra."""
    c, fase = obtener(it["convocatoria_id"]), it["fase"]
    if not usa_formularios(c) or fase not in ("meritos", "oral"):
        return ["Esta fase no se califica con un formulario."]
    if not es_miembro(it["id"], uid):
        return ["Solo califican los miembros del tribunal."]
    if pid not in {p["id"] for p in activos(it["id"])}:
        return ["Ese postulante no está en esta fase."]
    cantidades, errores = (rubricas.validar_meritos(c["modalidad"], crudo) if fase == "meritos" else rubricas.validar_oral(crudo))
    if errores:
        return errores
    with transaccion():
        get_db().execute("DELETE FROM calificacion_detalle WHERE postulacion_id = ? AND fase = ? AND miembro_id = ?", [pid, fase, uid])
        for clave, cantidad in cantidades.items():
            get_db().t.calificacion_detalle.insert(postulacion_id=pid, fase=fase, miembro_id=uid, clave=clave, cantidad=cantidad)
        _guardar_nota(pid, fase, uid, puntaje_detalle(c, fase, cantidades), observacion)
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
        f = [] if (c["cierre"] or "9999") <= _ahora() else [f"La recepción cierra el {formato.momento(c['cierre'])}."]
        if c["reglamento"] == REGLAMENTO_VIGENTE and not c["comision_resolucion"]:
            f.append("falta el número de la resolución del Consejo de Carrera que designa la comisión (art. 15)")
        return f
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
    if fase == "postulacion" and not activos(it["id"]):
        siguiente = "concluido"         # ítem desierto: sin postulantes no hay fases que calificar (art. 13)
    with transaccion():
        get_db().t.fase_auxiliatura.insert(item_id=it["id"], fase=fase, cerrada_por=uid)
        if fase == "habilitacion":
            for p in activos(it["id"]):
                if (nota(p["id"], fase) or 0) <= 0.5:   # mayoría de «sí»; un empate no habilita
                    get_db().execute("UPDATE postulacion_auxiliatura SET estado = 'no_habilitada', fase_fin = ? WHERE id = ?",
                                     [fase, p["id"]])
        elif minimo(it, fase) is not None:
            for p in activos(it["id"]):
                if (nota(p["id"], fase) or 0) < minimo(it, fase):
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


# --- Segunda convocatoria (arts. 13 y 14) ------------------------------------------------------------------------------------

def sin_cubrir(it: dict) -> int:
    """Plazas del ítem que ningún titular ocupó: las que pasan a la segunda convocatoria."""
    return max(it["plazas"] - sum(p["estado"] == "titular" for p in en_concurso(it["id"])), 0)


def segunda_de(cid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM convocatoria_auxiliatura WHERE primera_id = ?", [cid])
    return filas[0] if filas else None


def puede_generar_segunda(c: dict) -> bool:
    """Una primera convocatoria concluida con plazas sin cubrir (ítems desiertos o sin postulantes que alcanzaran la nota) y sin
    segunda todavía."""
    return (c["numero"] == 1 and c["estado"] == "concluida" and not segunda_de(c["id"])
            and any(sin_cubrir(i) for i in items(c["id"])))


def resultados_publicados_en(cid: int) -> datetime | None:
    """Cuándo se cerró la última fase de la convocatoria (UTC): desde ahí corren las 72 horas de la segunda."""
    fila = get_db().q("""SELECT MAX(f.cerrada_en) cuando FROM fase_auxiliatura f JOIN item_auxiliatura i ON i.id = f.item_id
                         WHERE i.convocatoria_id = ?""", [cid])
    return datetime.fromisoformat(fila[0]["cuando"]) if fila and fila[0]["cuando"] else None


def chequeo_segunda(c: dict) -> tuple[bool, str] | None:
    """Arts. 13 y 14: la segunda convocatoria se publica hasta 72 horas después de los resultados de la primera. Solo advierte."""
    if not c.get("primera_id"):
        return None
    desde = resultados_publicados_en(c["primera_id"])
    if not desde:
        return None
    limite = (desde + timedelta(hours=HORAS_SEGUNDA)).date()
    if not c["publicacion"]:
        return False, f"La segunda convocatoria debe publicarse hasta el {formato.fecha(limite.isoformat())} (72 horas después de los resultados de la primera)."
    if date.fromisoformat(c["publicacion"][:10]) <= limite:
        return True, f"Se publica dentro de las 72 horas que dan los arts. 13 y 14 (hasta el {formato.fecha(limite.isoformat())})."
    return False, (f"Pasaron más de 72 horas desde los resultados de la primera convocatoria (hasta el {formato.fecha(limite.isoformat())}): "
                   "los arts. 13 y 14 piden publicar la segunda dentro de ese plazo.")


def generar_segunda(cid: int, uid: int) -> tuple[int | None, list[str]]:
    """Arma, como borrador, la segunda convocatoria con las plazas que la primera no cubrió: mismos requisitos, lugar de recepción y
    tribunal. Hay que darle fechas y la resolución del Consejo de Carrera antes de publicarla."""
    c = obtener(cid)
    if not c or not puede_generar_segunda(c):
        return None, ["Solo se genera la segunda convocatoria de una primera ya concluida que dejó plazas sin cubrir."]
    db = get_db()
    with transaccion():
        nuevo = db.t.convocatoria_auxiliatura.insert(
            gestion_id=c["gestion_id"], modalidad=c["modalidad"], numero=2, titulo=f"{c['titulo']}, segunda convocatoria"[:200],
            lugar=c["lugar"], recepcion_lugar=c["recepcion_lugar"], recepcion_horario=c["recepcion_horario"], reglamento=c["reglamento"],
            primera_id=cid, creado_por=uid)["id"]
        for r in requisitos(cid):
            db.t.requisito_auxiliatura.insert(convocatoria_id=nuevo, texto=r["texto"], acredita=r["acredita"], orden=r["orden"],
                                              opcional=r["opcional"], clave=r["clave"])
        for it in items(cid):
            faltan = sin_cubrir(it)
            if not faltan:
                continue
            iid = db.t.item_auxiliatura.insert(convocatoria_id=nuevo, asignatura_id=it["asignatura_id"], proyecto_id=it["proyecto_id"],
                                               titulo=it["titulo"], plazas=faltan, horas=it["horas"])["id"]
            for m in it["tribunal"]:
                db.t.tribunal_auxiliatura.insert(item_id=iid, usuario_id=m["usuario_id"], tipo=m["tipo"])
    return nuevo, []


TEMAS_ORAL = 5      # art. 18, b): la comisión propone cinco temas y se sortea uno


def sortear_tema(it: dict, temas: str) -> list[str]:
    """Sortea el tema del examen oral, que disertan todos los postulantes. Con el reglamento de 2023 la comisión propone cinco temas y
    el sorteo no se repite; con el de 2021, al menos dos."""
    lista = [t.strip() for t in (temas or "").splitlines() if t.strip()]
    nuevo = usa_formularios(obtener(it["convocatoria_id"]))
    if nuevo and it["tema_oral"]:
        return ["El tema del examen oral ya se sorteó."]
    if nuevo and len(lista) != TEMAS_ORAL:
        return [f"La comisión debe proponer cinco temas, uno por línea (art. 18, b); escribió {len(lista)}."]
    if len(lista) < 2:
        return ["Escriba al menos dos temas, uno por línea."]
    get_db().execute(f"UPDATE item_auxiliatura SET tema_oral = ?, temas_oral = ?, tema_oral_en = {AHORA} WHERE id = ?",
                     [random.choice(lista)[:300], "\n".join(lista), it["id"]])
    return []


def fijar_orden_oral(it: dict, filas: list[tuple[int, str, str]]) -> list[str]:
    """Orden y hora en que cada postulante diserta el tema sorteado (formulario 3). `filas`: (postulación, orden, hora 'HH:MM')."""
    activos_ = {p["id"] for p in activos(it["id"])}
    ordenes, valores = [], []
    for pid, orden, hora in filas:
        if str(orden).strip() == "" and not str(hora).strip():
            continue
        if pid not in activos_ or not str(orden).strip().isdigit() or int(orden) < 1:
            return ["Indique un orden (1, 2, 3…) para cada postulante que participa."]
        hora = str(hora or "").strip()
        if hora and not (len(hora) == 5 and hora[2] == ":" and hora[:2].isdigit() and hora[3:].isdigit()
                         and int(hora[:2]) < 24 and int(hora[3:]) < 60):
            return ["La hora va como HH:MM."]
        ordenes.append(int(orden))
        valores.append((pid, int(orden), hora or None))
    if len(set(ordenes)) != len(ordenes):
        return ["Dos postulantes no pueden tener el mismo orden."]
    with transaccion():
        get_db().execute("UPDATE postulacion_auxiliatura SET orden_oral = NULL, hora_oral = NULL WHERE item_id = ?", [it["id"]])
        for pid, orden, hora in valores:
            get_db().execute("UPDATE postulacion_auxiliatura SET orden_oral = ?, hora_oral = ? WHERE id = ?", [orden, hora, pid])
    return []


def _local(utc: str) -> datetime:
    """Marca de tiempo de SQLite en UTC → hora local (la de los exámenes, que se escriben en hora local)."""
    return datetime.fromisoformat(str(utc)).replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


def avisos_plazos(it: dict) -> list[str]:
    """Plazos del reglamento de 2023 que ya se pasaron en este ítem (solo advierten; nada se bloquea)."""
    c = obtener(it["convocatoria_id"])
    if not usa_formularios(c):
        return []
    avisos = []
    examen = datetime.fromisoformat(c["examen"]) if c["examen"] else None
    meritos, escrito, oral = (cierre_de(it["id"], f) for f in ("meritos", "escrito", "oral"))
    if examen and meritos and _local(meritos["cerrada_en"]) > examen:
        avisos.append("Los resultados de méritos debían publicarse antes del examen escrito (art. 18).")
    if examen and escrito and _local(escrito["cerrada_en"]) > examen + timedelta(hours=24):
        avisos.append("Los resultados del examen escrito debían publicarse dentro de las 24 horas siguientes al examen (art. 18, a).")
    if it["tema_oral_en"] and oral and _local(oral["cerrada_en"]) > _local(it["tema_oral_en"]) + timedelta(hours=24):
        avisos.append("El examen oral debía rendirse dentro de las 24 horas posteriores al sorteo del tema (art. 18, b).")
    if oral and any(p["estado"] == "empate" for p in en_concurso(it["id"])):
        limite = _local(oral["cerrada_en"]) + timedelta(hours=48)
        avisos.append(f"El examen de desempate debe rendirse dentro de las 48 horas de publicados los resultados: hasta el "
                      f"{formato.fecha(limite.date().isoformat())}, {limite:%H:%M} (art. 20).")
    return avisos


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
