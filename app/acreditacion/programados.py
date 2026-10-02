"""Informes programados: se envían solos, en fechas fijas, a quienes tienen el rol en ese momento.

Cada envío es un aviso del centro de avisos (`notificaciones.avisar`): queda en la campana y llega
por correo según la preferencia de cada persona. El correo lleva las cifras clave y el enlace al
informe en el sistema (que pide iniciar sesión): los datos personales no viajan en el correo.

| Informe | Cuándo | A quién |
|---|---|---|
| Preparación del semestre | 4 semanas y 1 semana antes del inicio de cada semestre (I, II) | Dirección de Carrera y Coordinación académica |
| Carga docente | En las 3 semanas siguientes al inicio de cada semestre | Dirección de Carrera |
| Memoria anual | Del 10 de enero al 31 de marzo, la del año anterior | Dirección del Instituto |
| Calidad de datos | Una vez al mes (solo si hay algo que corregir) | Quienes ven el tablero de calidad |

La revisión corre con el mantenimiento horario (`main._mantenimiento`); `informe_programado`
registra cada envío para que salga una sola vez. Si en una ventana nadie usa el sistema, ese envío
no ocurre (no hay tareas programadas en el servidor). Decisiones: PLAN.md §39.
"""
import time
from datetime import date, timedelta

from app.academico import carga, gestiones, preparacion
from app.acreditacion import calidad, cuerpo_academico, informes
from app.comun import config, notificaciones, permisos
from app.comun.db import get_db

NOMBRES = {"preparacion": "Preparación del semestre", "carga": "Carga docente del semestre",
           "memoria": "Memoria anual del Instituto", "calidad": "Calidad de datos"}
ROLES = {"preparacion": ("direccion_carrera", "coordinacion_academica"), "carga": ("direccion_carrera",),
         "memoria": ("direccion_instituto",), "calidad": tuple(sorted(permisos.ACCIONES["ver_calidad_datos"]))}
_ultima_revision = 0.0


# --- Cuándo toca cada informe -------------------------------------------------------------------

def _inicio(anio: int, tipo: str) -> date:
    g = gestiones.por_codigo(f"{tipo}-{anio}")
    return date.fromisoformat(g["fecha_inicio"] if g else gestiones.fechas_por_omision(anio, tipo)[0])


def pendientes_de_hoy(hoy: date) -> list[tuple[str, str, dict]]:
    """[(informe, ocasión, datos)] que corresponden a la fecha, se hayan enviado o no."""
    res = []
    anio, tipo = preparacion.semestre_siguiente(hoy)
    faltan = (_inicio(anio, tipo) - hoy).days
    if 7 < faltan <= 28:
        res.append(("preparacion", f"{tipo}-{anio}:4 semanas", {"anio": anio, "tipo": tipo, "dias": faltan}))
    elif 0 < faltan <= 7:
        res.append(("preparacion", f"{tipo}-{anio}:1 semana", {"anio": anio, "tipo": tipo, "dias": faltan}))
    for g in gestiones.listar():
        if g["tipo"] in carga.SEMESTRES and 0 <= (hoy - date.fromisoformat(g["fecha_inicio"])).days <= 21:
            res.append(("carga", gestiones.codigo(g), {"gestion": g}))
    if date(hoy.year, 1, 10) <= hoy <= date(hoy.year, 3, 31):
        res.append(("memoria", str(hoy.year - 1), {"anio": hoy.year - 1}))
    res.append(("calidad", f"{hoy:%Y-%m}", {}))
    return res


def enviado(informe: str, ocasion: str) -> bool:
    return bool(get_db().q("SELECT 1 FROM informe_programado WHERE informe = ? AND ocasion = ?", [informe, ocasion]))


def ultimos(n: int = 20) -> list[dict]:
    return get_db().q("SELECT * FROM informe_programado ORDER BY enviado_en DESC LIMIT ?", [n])


# --- Contenido de cada informe ------------------------------------------------------------------
# Cada función devuelve (asunto, texto breve para la campana, cuerpo del correo, url) o None si no
# hay nada que avisar.

def _preparacion(d):
    est = preparacion.estado(d["anio"], d["tipo"])
    lineas = [f"{'✓' if e['listo'] else '·'} {e['titulo']}: {e['detalle']}" for e in est["etapas"]]
    falta = next((e for e in est["etapas"] if not e["listo"]), None)
    resumen = f"{est['hechas']} de {est['total']} etapas listas" + (f"; siguiente: {falta['falta']}" if falta else "")
    return (f"Preparación de {est['codigo']}: {est['hechas']} de {est['total']} etapas listas",
            f"El semestre empieza en {d['dias']} días. {resumen}.",
            f"El semestre {est['codigo']} empieza en {d['dias']} días. Así va su preparación:\n\n" + "\n".join(lineas)
            + ("\n\nEl semestre está listo." if not falta else "") + "\n\nEl detalle, con lo que falta en cada etapa:",
            f"/docencia/preparacion?semestre={est['codigo']}")


def _carga(d):
    g = d["gestion"]
    c = cuerpo_academico.carga_docente(g)
    t = c["total"]
    pct = f"{t['pct_investigacion']} %" if t["pct_investigacion"] is not None else "—"
    obs = t["con_avisos"]
    return (f"Carga docente de {gestiones.codigo(g)}",
            f"{t['personas']} personas, {t['jce']} JCE; {obs} con observaciones.",
            f"Empezó el semestre {gestiones.codigo(g)}. Su carga docente:\n\n"
            f"· Personas con vínculo o materias: {t['personas']}\n"
            f"· Jornadas completas equivalentes: {t['jce']}\n"
            f"· Carga en investigación: {pct}\n"
            f"· Inscripciones por JCE: {c['inscripciones_por_jce'] if c['inscripciones_por_jce'] is not None else '—'}\n"
            f"· Docentes con observaciones en su carga: {obs}\n\nEl informe completo:",
            f"/informes/carga-docente?gestion={g['id']}")


def _memoria(d):
    anio = d["anio"]
    m, prev = informes.memoria(anio), informes.memoria(anio - 1)

    def fila(texto, a, b):
        dif = a - b
        return f"· {texto}: {a} ({'+' if dif > 0 else ''}{dif} respecto de {anio - 1})" if dif else f"· {texto}: {a} (igual que en {anio - 1})"
    return (f"Memoria anual {anio} del Instituto",
            f"{m['n_indexados']} productos indexados, {m['n_arbitrados']} arbitrados, {len(m['actividades'])} actividades.",
            f"La memoria {anio} está lista para revisar y descargar:\n\n"
            + "\n".join([fila("Productos indexados", m["n_indexados"], prev["n_indexados"]),
                         fila("Productos arbitrados", m["n_arbitrados"], prev["n_arbitrados"]),
                         fila("Actividades", len(m["actividades"]), len(prev["actividades"])),
                         fila("Proyectos vigentes", len(m["proyectos"]), len(prev["proyectos"]))])
            + (f"\n\n{len(m['por_confirmar'])} producto(s) por confirmar no se cuentan hasta completar sus datos."
               if m["por_confirmar"] else "") + "\n\nLa memoria completa (y su XLSX):",
            f"/informes/memoria?anio={anio}")


def _calidad(d):
    r = calidad.resumen()
    if not r["registros"]:
        return None
    quien = "\n".join(f"· {calidad.QUIEN[q]}: {n}" for q, n in r["por_quien"].items() if n)
    return (f"Calidad de datos: {r['registros']} registros por completar",
            f"{r['con_observaciones']} de {r['chequeos']} revisiones con observaciones.",
            f"Antes de generar la memoria, el anexo o los informes de docencia, conviene completar "
            f"{r['registros']} registros ({r['con_observaciones']} de {r['chequeos']} revisiones con observaciones). "
            f"Les toca a:\n\n{quien}\n\nEl tablero, con enlaces para corregir cada uno:",
            "/informes/calidad")


CONTENIDO = {"preparacion": _preparacion, "carga": _carga, "memoria": _memoria, "calidad": _calidad}


# --- Envío ------------------------------------------------------------------------------------------

def destinatarios(informe: str) -> list[dict]:
    vistos = {}
    for rol in ROLES[informe]:
        for u in permisos.con_rol(rol):
            vistos.setdefault(u["id"], u)
    return list(vistos.values())


def revisar(hoy: date | None = None) -> list[tuple[str, str, int]]:
    """Envía los informes que tocan hoy y aún no salieron. → [(informe, ocasión, destinatarios)]."""
    hoy = hoy or date.today()
    enviados = []
    for informe, ocasion, datos in pendientes_de_hoy(hoy):
        if enviado(informe, ocasion):
            continue
        gente = destinatarios(informe)
        if not gente:
            continue          # sin nadie con el rol: se reintenta en la próxima revisión
        mensaje = CONTENIDO[informe](datos)
        if mensaje:
            asunto, texto, cuerpo, url = mensaje
            for u in gente:
                notificaciones.avisar(u, asunto, texto, url, cuerpo)
        get_db().t.informe_programado.insert(informe=informe, ocasion=ocasion,
                                             destinatarios=len(gente) if mensaje else 0)
        enviados.append((informe, ocasion, len(gente) if mensaje else 0))
    return enviados


def mantenimiento():
    """Lo llama el mantenimiento de main.py: a lo más una revisión por hora."""
    global _ultima_revision
    if not config.INFORMES_PROGRAMADOS or time.monotonic() - _ultima_revision < 3600:
        return
    _ultima_revision = time.monotonic()
    revisar()


def suyos(usuario: dict) -> list[str]:
    """Informes que recibe la persona por sus roles."""
    return [i for i, roles in ROLES.items() if any(permisos.tiene_rol(usuario, r) for r in roles)]


def proximos(hoy: date | None = None) -> list[tuple[str, date, str]]:
    """Próximas fechas de envío (para mostrarlas): [(informe, fecha, detalle)]."""
    hoy = hoy or date.today()
    anio, tipo = preparacion.semestre_siguiente(hoy)
    inicio = _inicio(anio, tipo)
    res = [("preparacion", d, f"{tipo}-{anio}") for d in (inicio - timedelta(days=28), inicio - timedelta(days=7)) if d >= hoy]
    res.append(("carga", inicio, f"{tipo}-{anio}"))
    memoria = date(hoy.year if hoy < date(hoy.year, 1, 10) else hoy.year + 1, 1, 10)
    res.append(("memoria", memoria, str(memoria.year - 1)))
    res.append(("calidad", date(hoy.year + (hoy.month == 12), hoy.month % 12 + 1, 1), "mensual"))
    return sorted(res, key=lambda x: x[1])
