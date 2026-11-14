"""«Mis pendientes» y «Mi calendario» del investigador (PLAN §69, etapa 1). No guardan nada: reúnen lo que ya tienen las
propuestas, los proyectos, los productos y el perfil, y solo de la propia persona (siempre `auth["id"]`).

Pendiente: {tipo, titulo, detalle, cuando (ISO o None), href}. Evento: {fecha, hora, titulo, tipo, detalle, href}."""
import calendar
from datetime import date, timedelta

from app.academico import docente
from app.comun.db import get_db
from app.investigacion import acceso_abierto, carga_proyectos, filiacion, institucionales, perfiles, productos, proyectos

TIPOS = {"propuesta": "Convocatoria", "proyecto": "Proyectos", "plan": "Plan del proyecto", "producto": "Productos",
         "perfil": "Perfil", "carga": "Carga horaria", "actividad": "Actividades", "evento": "Evento", "acceso": "Acceso abierto"}
DIAS_FIN_PROYECTO = 60      # avisa cuando un proyecto termina en menos de estos días
DIAS_SIN_NOVEDAD = 180      # un producto «enviado» o «aceptado» sin cambios en este tiempo: ¿ya se publicó?


def _pendiente(tipo: str, titulo: str, detalle: str = "", cuando: str | None = None, href: str | None = None) -> dict:
    return {"tipo": tipo, "titulo": titulo, "detalle": detalle, "cuando": (cuando or None) and cuando[:10], "href": href}


def _responsable_de(uid: int) -> list[dict]:
    """Proyectos vigentes de los que la persona es responsable o co-responsable (vigente en ellos)."""
    return [p for p in proyectos.de_investigador(uid)
            if p["vigente"] and p["estado"] == "vigente" and p["mi_rol"] in proyectos.ROLES_RESPONSABLES]


def puede_proponer(uid: int) -> bool:
    return institucionales.categoria(uid) in perfiles.CATEGORIAS_RESPONSABLES


# --- Pendientes ---------------------------------------------------------------------------------------------------------

def _propuestas(uid: int):
    periodo = institucionales.periodo_abierto()
    if periodo is None:
        return
    cierra = institucionales.plazo(periodo)["cierra"]
    for prop in institucionales.mis_propuestas(uid):
        if prop["periodo"] != periodo:
            continue
        if prop["estado"] == "borrador":
            yield _pendiente("propuesta", f"Envíe su propuesta «{prop['nombre']}»", "La convocatoria sigue abierta", cierra,
                             f"/propuestas/{prop['id']}")
        elif prop["estado"] == "condicional":
            yield _pendiente("propuesta", f"Responda a las condiciones de «{prop['nombre']}»",
                             "Corrija y vuelva a enviarla", cierra, f"/propuestas/{prop['id']}")
    for p in _responsable_de(uid):
        if institucionales.pendiente_de_continuidad(p) == periodo:
            yield _pendiente("propuesta", f"Proponga la continuidad de «{p['nombre']}»",
                             "El proyecto termina con esta convocatoria", cierra, f"/proyectos/{p['id']}")


def _proyectos(uid: int):
    for p in _responsable_de(uid):
        n_carga = carga_proyectos.n_pendientes(p["id"])
        n_registros = proyectos.n_pendientes(p["id"]) - n_carga
        if n_registros:
            yield _pendiente("proyecto", f"{n_registros} registro(s) por aprobar en «{p['nombre']}»",
                             "Productos y actividades que propusieron los participantes", None,
                             f"/proyectos/{p['id']}?tab=pendientes")
        if n_carga:
            yield _pendiente("carga", f"Carga horaria por atender en «{p['nombre']}»",
                             "Cambió el vínculo de un participante", None, f"/proyectos/{p['id']}?tab=pendientes")
        if p["tipo"] == "institucional":
            atrasadas = sum(f["estado"] == "atrasada" for per in institucionales.plan(p["id"]) for f in per["previstas"])
            if atrasadas:
                yield _pendiente("plan", f"{atrasadas} actividad(es) prevista(s) atrasada(s) en «{p['nombre']}»",
                                 "Enlace la actividad realizada o actualice el plan", None, f"/proyectos/{p['id']}?tab=plan")


def _fin_de_proyectos(uid: int, hoy: date):
    for p in proyectos.de_investigador(uid):
        if (p["vigente"] and p["estado"] == "vigente" and p["fecha_fin"]
                and hoy <= date.fromisoformat(p["fecha_fin"]) <= hoy + timedelta(days=DIAS_FIN_PROYECTO)):
            yield _pendiente("proyecto", f"Termina su proyecto «{p['nombre']}»", "Registre lo producido antes de que cierre",
                             p["fecha_fin"], f"/proyectos/{p['id']}")


def _productos(uid: int, hoy: date):
    n = filiacion.pendientes(uid)
    if n:
        yield _pendiente("producto", f"Declare su filiación en {n} producto(s)",
                         "Sin ella no cuentan para los informes del instituto", None, "/productos?sin_filiacion=1")
    limite = (hoy - timedelta(days=DIAS_SIN_NOVEDAD)).isoformat()
    for p in get_db().q(
            """SELECT p.id, p.titulo, p.estado_publicacion, COALESCE(p.actualizado_en, p.creado_en) AS ultimo
               FROM producto p JOIN producto_autor a ON a.producto_id = p.id AND a.investigador_id = ?
               WHERE p.estado_publicacion IN ('enviado', 'aceptado') AND COALESCE(p.actualizado_en, p.creado_en) < ?
               ORDER BY ultimo""", [uid, limite]):
        yield _pendiente("producto", f"¿Ya se publicó «{p['titulo']}»?",
                         f"Sigue como «{productos.ESTADOS[p['estado_publicacion']].lower()}» desde el {p['ultimo'][:10]}", None,
                         f"/productos/{p['id']}")
    for pre, pub in productos.preprints_sin_enlazar(uid=uid):
        yield _pendiente("producto", f"¿«{pre['titulo']}» ya salió publicado?",
                         f"Se parece a «{pub['titulo']}» ({pub['anio']}): enlácelo como su versión publicada", None,
                         f"/productos/{pre['id']}")


def _acceso(uid: int, hoy: date):
    for f in acceso_abierto.embargos_vencidos(uid, hoy):
        yield _pendiente("acceso", f"Terminó el embargo de «{f['titulo']}»", "¿Ya puede depositar una copia? Actualice la declaración",
                         f["embargo_hasta"], f"/productos/{f['id']}")
    n = len(acceso_abierto.sin_declarar(uid, hoy))
    if n:
        yield _pendiente("acceso", f"Declare el acceso abierto de {n} producto(s)",
                         "Dónde se puede leer el texto y si los datos están disponibles", None, "/investigacion/acceso-abierto")


def _perfil(uid: int):
    perfil = perfiles.obtener(uid)
    if not perfil:
        return
    pct, faltan = perfiles.completitud(perfil, len(perfiles.areas(uid)))
    if faltan:
        yield _pendiente("perfil", f"Complete su perfil ({pct} %)", "Falta: " + ", ".join(faltan), None, "/perfil")


FUENTES_PENDIENTES = (_propuestas, _proyectos, _perfil)


def pendientes(uid: int, hoy: date | None = None) -> list[dict]:
    """Lo que la persona debe hacer, lo que vence antes primero (y lo que no tiene fecha, después)."""
    hoy = hoy or date.today()
    todos = ([p for f in FUENTES_PENDIENTES for p in f(uid)] + list(_fin_de_proyectos(uid, hoy)) + list(_productos(uid, hoy))
             + list(_acceso(uid, hoy)))
    return sorted(todos, key=lambda p: (p["cuando"] is None, p["cuando"] or "", p["titulo"]))


def situacion(p: dict, hoy: date | None = None) -> str:
    """'vencido', 'proximo' (en los próximos 7 días) o 'normal'."""
    return docente.situacion(p, hoy)


# --- Calendario ---------------------------------------------------------------------------------------------------------

def _evento(iso: str | None, titulo: str, tipo: str, detalle: str = "", href: str | None = None) -> dict | None:
    if not iso:
        return None
    return {"fecha": iso[:10], "hora": iso[11:16] if len(iso) >= 16 else "", "titulo": titulo, "tipo": tipo,
            "detalle": detalle, "href": href}


def _eventos_convocatoria(uid: int):
    if not puede_proponer(uid):
        return
    periodo = institucionales.periodo_objetivo()
    p = institucionales.plazo(periodo)
    texto = institucionales.periodo_texto(periodo)
    yield _evento(p["abre"], f"Abre la convocatoria de proyectos {texto}", "propuesta", "", "/propuestas")
    yield _evento(p["cierra"], f"Cierra la convocatoria de proyectos {texto}", "propuesta", "Último día para enviar",
                  "/propuestas")


def _eventos_actividades(uid: int):
    from app.investigacion import actividades
    for a in get_db().q(
            """SELECT a.id, a.titulo, a.fecha_inicio, a.fecha_fin, a.lugar, a.pais, ap.rol FROM actividad a
               JOIN actividad_participante ap ON ap.actividad_id = a.id AND ap.investigador_id = ?""", [uid]):
        donde = ", ".join(x for x in (a["lugar"], a["pais"]) if x)
        yield _evento(a["fecha_inicio"], a["titulo"], "actividad",
                      " · ".join(x for x in (actividades.ROLES.get(a["rol"], ""), donde) if x), f"/actividades/{a['id']}")


def _eventos_proyectos(uid: int):
    for p in proyectos.de_investigador(uid):
        if not (p["vigente"] and p["estado"] == "vigente"):
            continue
        yield _evento(p["fecha_fin"], f"Termina el proyecto «{p['nombre']}»", "proyecto", "", f"/proyectos/{p['id']}")
        if p["mi_rol"] in proyectos.ROLES_RESPONSABLES and p["tipo"] == "institucional":
            for per in institucionales.plan(p["id"]):
                for f in per["previstas"]:
                    if f["estado"] != "realizada" and f["mes_previsto"]:
                        anio, mes = map(int, f["mes_previsto"].split("-"))
                        fin = f"{anio:04d}-{mes:02d}-{calendar.monthrange(anio, mes)[1]:02d}"
                        yield _evento(fin, f"Fin del mes previsto: {f['descripcion']}", "plan", p["nombre"],
                                      f"/proyectos/{p['id']}?tab=plan")


def _eventos_embargos(uid: int):
    for f in acceso_abierto.de_investigador(uid, "embargo"):
        yield _evento(f["embargo_hasta"], f"Termina el embargo de «{f['titulo']}»", "acceso",
                      "Puede depositar una copia en un repositorio", f"/productos/{f['id']}")


def eventos(uid: int, desde: date | None = None, hasta: date | None = None) -> list[dict]:
    """Las fechas de la persona entre `desde` y `hasta` (por omisión, de hoy a 120 días), en orden."""
    desde = desde or date.today()
    hasta = hasta or desde + timedelta(days=120)
    d, h = desde.isoformat(), hasta.isoformat()
    todos = [e for fuente in (_eventos_convocatoria(uid), _eventos_actividades(uid), _eventos_proyectos(uid),
                              _eventos_embargos(uid), docente.eventos_comunicados(uid)) for e in fuente if e]
    return sorted((e for e in todos if d <= e["fecha"] <= h), key=lambda e: (e["fecha"], e["hora"], e["titulo"]))

