"""Egresados de la Carrera (PLAN §50, etapa 4).

- **Transición:** quien se titula (`estudiante.estado = 'titulado'`, con fecha de titulación) pasa a ser egresado; no hay una
  tabla aparte, se deduce. `titular` registra la titulación de un estudiante a mano; también llega por el CSV de cohortes.
- **Seguimiento programado:** a los 6 meses, 1, 3 y 5 años de titularse el egresado recibe una invitación a la encuesta
  de ese hito (`encuesta.hito`, abierta en continuo). Si al activar el seguimiento ya pasaron varios hitos, se invita solo
  al último y los anteriores quedan «omitidos». La revisión corre con el mantenimiento horario (`main._mantenimiento`).
- **Indicadores:** titulados y tiempo hasta titularse por trienio, modalidades, y empleabilidad, posgrado, utilidad y
  satisfacción según la última respuesta de cada egresado, siempre con el n. Los trienios terminan en el año actual.
"""
import calendar
import time
from datetime import date

from app.comun import config
from app.comun.db import auditar, get_db, transaccion
from app.estudiantil import cohortes, encuestas

HITOS = {"6m": ("6 meses", 6), "1a": ("1 año", 12), "3a": ("3 años", 36), "5a": ("5 años", 60)}
# Respuestas que cuentan como cada indicador (según el texto de las opciones de la plantilla de egresados).
EMPLEO = {"Trabajo en mi área", "Trabajo en otra área", "Trabajo y estudio"}
EN_EL_AREA = {"Trabajo en mi área"}
POSGRADO = {"Sí, en Bolivia", "Sí, en el extranjero"}
_ultima_revision = 0.0


def sumar_meses(fecha_iso: str, meses: int) -> date:
    d = date.fromisoformat(fecha_iso)
    m = d.month - 1 + meses
    anio, mes = d.year + m // 12, m % 12 + 1
    return date(anio, mes, min(d.day, calendar.monthrange(anio, mes)[1]))


def fecha_hito(fecha_titulacion: str, hito: str) -> date:
    return sumar_meses(fecha_titulacion, HITOS[hito][1])


def hitos_vencidos(fecha_titulacion: str, hoy: date) -> list[str]:
    """Hitos cuya fecha ya llegó, del más antiguo al más reciente."""
    return [h for h in HITOS if fecha_hito(fecha_titulacion, h) <= hoy]


# --- Titulación ----------------------------------------------------------------------------------------------------

def titulados() -> list[dict]:
    """Egresados titulados (licenciatura del programa propio), con su persona y el estado de su seguimiento."""
    filas = get_db().q(
        """SELECT es.id AS estudiante_id, es.cohorte_anio, es.cohorte_ciclo, es.fecha_egreso, es.fecha_titulacion,
                  es.modalidad_titulacion, pe.id AS externo_id, pe.nombres, pe.apellidos, pe.email
           FROM estudiante es JOIN persona_externa pe ON pe.id = es.externo_id
           WHERE es.nivel = 'licenciatura' AND es.del_programa = 1 AND es.cohorte_anio IS NOT NULL
             AND es.estado = 'titulado' AND es.fecha_titulacion IS NOT NULL
           ORDER BY es.fecha_titulacion DESC, pe.apellidos, pe.nombres""")
    seg = {}
    for s in get_db().q("""SELECT sg.externo_id, sg.hito, sg.estado, inv.respondida_en FROM seguimiento_egresado sg
                           LEFT JOIN invitacion_encuesta inv ON inv.encuesta_id = sg.encuesta_id AND inv.externo_id = sg.externo_id"""):
        seg.setdefault(s["externo_id"], {})[s["hito"]] = "respondido" if s["respondida_en"] else s["estado"]
    for f in filas:
        f["seguimiento"] = seg.get(f["externo_id"], {})
    return filas


def candidatos_titulacion() -> list[dict]:
    """Estudiantes de la licenciatura que aún no se titulan (para registrar su titulación)."""
    return get_db().q(
        """SELECT es.id, es.cohorte_anio, es.cohorte_ciclo, es.estado, pe.nombres, pe.apellidos FROM estudiante es
           JOIN persona_externa pe ON pe.id = es.externo_id
           WHERE es.nivel = 'licenciatura' AND es.del_programa = 1 AND es.cohorte_anio IS NOT NULL
             AND es.estado IN ('cursando', 'egresado') ORDER BY pe.apellidos, pe.nombres""")


def titular(estudiante_id: int, d: dict, uid: int | None) -> list[str]:
    """Registra la titulación de un estudiante: pasa a «titulado» y entra al seguimiento de egresados."""
    filas = get_db().q("SELECT * FROM estudiante WHERE id = ? AND nivel = 'licenciatura' AND cohorte_anio IS NOT NULL",
                       [estudiante_id])
    if not filas or filas[0]["estado"] not in ("cursando", "egresado"):
        return ["Ese estudiante no se puede titular: ya está titulado, retirado o congelado."]
    e = filas[0]
    errores = []
    f_tit, f_egr = (d.get("fecha_titulacion") or "").strip(), (d.get("fecha_egreso") or "").strip() or None
    modalidad = d.get("modalidad") or None
    try:
        tit = date.fromisoformat(f_tit)
        if tit > date.today():
            errores.append("La fecha de titulación no puede ser futura.")
    except ValueError:
        errores.append("Indique la fecha de titulación.")
        tit = None
    f_egr = f_egr or f_tit or None
    try:
        egr = date.fromisoformat(f_egr) if f_egr else None
    except ValueError:
        errores.append("La fecha de egreso no es válida.")
        egr = None
    if tit and egr and egr > tit:
        errores.append("El egreso no puede ser posterior a la titulación.")
    if egr and cohortes.ordinal(*cohortes.ciclo_de(egr.isoformat())) < cohortes.ordinal(e["cohorte_anio"], e["cohorte_ciclo"]):
        errores.append("El egreso es anterior al ingreso.")
    if modalidad and modalidad not in cohortes.MODALIDADES:
        errores.append("La modalidad de titulación no es válida.")
    if errores:
        return errores
    ult = cohortes.ciclo_de(egr.isoformat())
    get_db().execute(
        """UPDATE estudiante SET estado = 'titulado', titulado = 1, fecha_titulacion = ?, fecha_egreso = ?,
           modalidad_titulacion = ?, ultimo_anio = ?, ultimo_ciclo = ?, hasta = ?, motivo_retiro = NULL WHERE id = ?""",
        [tit.isoformat(), egr.isoformat(), modalidad, ult[0], ult[1], egr.year, estudiante_id])
    auditar(uid, "titular_estudiante", "estudiante", estudiante_id, tit.isoformat())
    return []


# --- Seguimiento programado ------------------------------------------------------------------------------------

def encuesta_de_hito(hito: str) -> dict | None:
    filas = get_db().q("SELECT * FROM encuesta WHERE hito = ? AND estado = 'abierta'", [hito])
    return filas[0] if filas else None


def hitos_sin_encuesta() -> list[str]:
    return [h for h in HITOS if not encuesta_de_hito(h)]


def activar_seguimiento(uid: int | None) -> int:
    """Crea y abre la encuesta de cada hito que no tenga una abierta (a partir de la plantilla de egresados). → cuántas."""
    creadas = 0
    for h in hitos_sin_encuesta():
        with transaccion():
            eid = encuestas.crear_desde_plantilla("egresados", uid, hito=h,
                                                  titulo=f"Seguimiento de egresados: {HITOS[h][0]} después de titularse")
            _, _, errores = encuestas.abrir(eid, uid)
            assert not errores, errores
        creadas += 1
    return creadas


def programar(hoy: date | None = None, lote: int = encuestas.LOTE_CORREOS, uid: int | None = None) -> dict:
    """Invita a los egresados a la encuesta del último hito que cumplieron (si aún no se les invitó) y deja los hitos
    anteriores como omitidos. Hasta `lote` invitaciones por revisión. → invitados, omitidos y sin correo."""
    hoy = hoy or date.today()
    abiertas = {h: encuesta_de_hito(h) for h in HITOS}
    invitados = omitidos = sin_correo = 0
    for g in titulados():
        vencidos = hitos_vencidos(g["fecha_titulacion"], hoy)
        if not vencidos:
            continue
        ultimo = vencidos[-1]
        hechos = g["seguimiento"]
        if ultimo in hechos or not abiertas[ultimo]:
            continue
        if not (g["email"] or "").strip():
            sin_correo += 1
            continue
        if invitados >= lote:
            break
        inv = encuestas.invitar(abiertas[ultimo]["id"], g["externo_id"], g["email"], g["cohorte_anio"])
        with transaccion():
            for h in vencidos[:-1]:
                if h not in hechos:
                    get_db().t.seguimiento_egresado.insert(externo_id=g["externo_id"], hito=h, encuesta_id=None, estado="omitido",
                                                           programado_para=fecha_hito(g["fecha_titulacion"], h).isoformat())
                    omitidos += 1
            get_db().t.seguimiento_egresado.insert(
                externo_id=g["externo_id"], hito=ultimo, encuesta_id=abiertas[ultimo]["id"], estado="invitado",
                programado_para=fecha_hito(g["fecha_titulacion"], ultimo).isoformat())
        invitados += bool(inv)
    if invitados:
        auditar(uid, "invitar_seguimiento_egresados", "encuesta", None, f"{invitados} invitación(es)")
    return {"invitados": invitados, "omitidos": omitidos, "sin_correo": sin_correo}


def mantenimiento():
    """Lo llama el mantenimiento de main.py: a lo más una revisión por hora."""
    global _ultima_revision
    if not config.INFORMES_PROGRAMADOS or time.monotonic() - _ultima_revision < 3600:
        return
    _ultima_revision = time.monotonic()
    programar()


def estado_seguimiento(hoy: date | None = None) -> list[dict]:
    """Por hito: invitados, respondidos, omitidos y cuántos corresponde invitar hoy."""
    hoy = hoy or date.today()
    gente = titulados()
    filas = []
    for h, (nombre, _) in HITOS.items():
        e = encuesta_de_hito(h)
        sg = [x for g in gente for hh, x in g["seguimiento"].items() if hh == h]
        pendientes = sum(1 for g in gente if (v := hitos_vencidos(g["fecha_titulacion"], hoy)) and v[-1] == h
                         and h not in g["seguimiento"] and (g["email"] or "").strip())
        filas.append({"hito": h, "nombre": nombre, "encuesta": e, "invitados": sum(x in ("invitado", "respondido") for x in sg),
                      "respondidos": sum(x == "respondido" for x in sg), "omitidos": sum(x == "omitido" for x in sg),
                      "pendientes": pendientes if e else 0})
    return filas


# --- Indicadores -----------------------------------------------------------------------------------------------

def trienio(anio: int, fin: int) -> tuple[int, int]:
    """Trienio (desde, hasta) que contiene al año, con trienios que terminan en `fin`."""
    k = (fin - anio) // 3
    return fin - 3 * k - 2, fin - 3 * k


def _ultimas_respuestas() -> dict[int, dict[str, str]]:
    """Por egresado, lo que contestó por clave (de su respuesta más reciente a cada pregunta con clave)."""
    res: dict[int, dict[str, tuple[int, str]]] = {}
    for f in get_db().q(
            """SELECT inv.externo_id, p.clave, i.valor, r.id AS rid FROM respuesta r
               JOIN invitacion_encuesta inv ON inv.id = r.invitacion_id JOIN encuesta e ON e.id = r.encuesta_id
               JOIN respuesta_item i ON i.respuesta_id = r.id JOIN pregunta p ON p.id = i.pregunta_id
               WHERE e.hito IS NOT NULL AND p.clave IS NOT NULL ORDER BY r.id"""):
        res.setdefault(f["externo_id"], {})[f["clave"]] = (f["rid"], f["valor"])
    return {k: {c: v for c, (_, v) in d.items()} for k, d in res.items()}


def _pct(parte: int, total: int) -> float | None:
    return parte / total if total else None


def indicadores(hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    gente = titulados()
    respuestas = _ultimas_respuestas()
    por: dict[tuple[int, int], list[dict]] = {}
    for g in gente:
        por.setdefault(trienio(int(g["fecha_titulacion"][:4]), hoy.year), []).append(g)
    filas = []
    for (desde, hasta), grupo in sorted(por.items(), reverse=True):
        resp = [respuestas[g["externo_id"]] for g in grupo if g["externo_id"] in respuestas]
        sit = [r["situacion"] for r in resp if "situacion" in r]
        pos = [r["posgrado"] for r in resp if "posgrado" in r]
        util = [int(r["utilidad"]) for r in resp if "utilidad" in r]
        sat = [int(r["satisfaccion"]) for r in resp if "satisfaccion" in r]
        anios = [(cohortes.ordinal(*cohortes.ciclo_de(g["fecha_titulacion"])) -
                  cohortes.ordinal(g["cohorte_anio"], g["cohorte_ciclo"])) / 2 for g in grupo]
        filas.append({
            "desde": desde, "hasta": hasta, "titulados": len(grupo), "anios_medios": sum(anios) / len(anios),
            "respondieron": len(resp), "tasa_respuesta": _pct(len(resp), len(grupo)),
            "n_situacion": len(sit), "empleo": _pct(sum(s in EMPLEO for s in sit), len(sit)),
            "en_el_area": _pct(sum(s in EN_EL_AREA for s in sit), len(sit)),
            "n_posgrado": len(pos), "posgrado": _pct(sum(p in POSGRADO for p in pos), len(pos)),
            "utilidad": sum(util) / len(util) if util else None, "satisfaccion": sum(sat) / len(sat) if sat else None})
    modalidades = {m: sum(g["modalidad_titulacion"] == m for g in gente) for m in cohortes.MODALIDADES}
    modalidades["sin dato"] = sum(g["modalidad_titulacion"] is None for g in gente)
    return {"total": len(gente), "trienios": filas, "modalidades": {k: v for k, v in modalidades.items() if v},
            "respondieron": sum(1 for g in gente if g["externo_id"] in respuestas),
            "anios_medios": sum(f["anios_medios"] * f["titulados"] for f in filas) / len(gente) if gente else None}
