"""Lo que el módulo de investigación aporta al menú, la búsqueda y el inicio (PLAN §73, etapa 2)."""
from datetime import date, timedelta

from app.comun import formato, permisos
from app.comun.componentes.bandeja import plural
from app.comun.db import get_db, patron_busqueda
from app.comun.menu import agenda_en_el_menu, contador, item
from app.investigacion import actividades, filiacion, institucionales, perfiles, productos, proyectos

G = "Investigación"


def menu(auth):
    puede = lambda accion: permisos.puede(auth, accion)  # noqa: E731
    items = []
    if auth["es_investigador"]:
        items += [(G, 10, item("actividades", "Actividades", "/actividades", "calendar-days")),
                  (G, 20, item("productos", "Productos", "/productos", "book-open"))]
    if auth["es_investigador"] or puede("ver_todos_los_proyectos"):
        items.append((G, 30, item("proyectos", "Proyectos", "/proyectos", "folder-kanban",
                                  contador("badge-pendientes", "/proyectos/pendientes/contador"))))
    items.append((G, 40, item("investigadores", "Investigadores", "/investigadores", "book-user")))
    if auth["es_investigador"]:
        items += [*agenda_en_el_menu(),
                  (G, 70, item("inv-acceso", "Acceso abierto", "/investigacion/acceso-abierto", "lock-open")),
                  (G, 80, item("inv-colaboraciones", "Mis colaboraciones", "/investigacion/coautores", "network"))]
    if puede("decidir_propuestas"):
        items.append((G, 90, item("propuestas", "Propuestas", "/admin/propuestas", "landmark",
                                  contador("badge-propuestas", "/admin/propuestas/contador"))))
    if puede("gestionar_catalogos"):
        items += [("Administración", 50, item("revistas", "Catálogo de revistas", "/admin/revistas", "library")),
                  ("Administración", 60, item("lineas", "Líneas de investigación", "/admin/lineas", "route")),
                  ("Administración", 70, item("catalogos", "Tipos e índices", "/admin/catalogos", "tags"))]
    return items


# --- Búsqueda ------------------------------------------------------------------------------------------------------

def _personas(q, auth, limite):
    return [{"texto": f"{p['nombres']} {p['apellidos']}", "href": f"/investigadores/{p['id']}",
             "detalle": " · ".join(x for x in (p.get("cargo"), p.get("unidad")) if x)}
            for p in perfiles.directorio(q)[:limite]]


def _productos(q, auth, limite):
    filas = get_db().q(
        """SELECT p.id, p.titulo, p.anio, t.nombre AS tipo FROM producto p JOIN tipo_producto t ON t.id = p.tipo_id
           WHERE sin_tildes(p.titulo) LIKE :p OR p.doi = lower(:q) OR p.arxiv_id = :q
           ORDER BY p.anio DESC, p.id DESC LIMIT :l""", {"p": patron_busqueda(q), "q": q.strip(), "l": limite})
    return [{"texto": f["titulo"], "href": f"/productos/{f['id']}", "detalle": f"{f['anio']} · {f['tipo']}"}
            for f in filas]


def _actividades(q, auth, limite):
    filas = get_db().q(
        """SELECT a.id FROM actividad a WHERE sin_tildes(a.titulo) LIKE :p OR sin_tildes(a.institucion) LIKE :p
           ORDER BY a.fecha_inicio DESC LIMIT :l""", {"p": patron_busqueda(q), "l": limite})
    res = []
    for f in filas:
        a = actividades.obtener(f["id"])
        res.append({"texto": a["titulo"], "href": f"/actividades/{a['id']}",
                    "detalle": f"{actividades.fechas_texto(a)} · {a['tipo']}"})
    return res


def _proyectos(q, auth, limite):
    filas = get_db().q(
        """SELECT id, nombre, codigo, estado FROM proyecto
           WHERE sin_tildes(nombre) LIKE :p OR codigo LIKE :p ORDER BY fecha_inicio DESC, id DESC""",
        {"p": patron_busqueda(q)})
    visibles = [f for f in filas if proyectos.puede_ver(f["id"], auth)][:limite]
    return [{"texto": f["nombre"], "href": f"/proyectos/{f['id']}",
             "detalle": " · ".join(x for x in (f["codigo"], proyectos.ESTADOS.get(f["estado"], "")) if x)}
            for f in visibles]


BUSQUEDA = [(10, "Personas", "users", _personas), (30, "Productos", "book-open", _productos),
            (40, "Actividades", "calendar-days", _actividades), (50, "Proyectos", "folder-kanban", _proyectos)]


# --- Inicio --------------------------------------------------------------------------------------------------------

def _mio(auth):
    """Lo que le toca a quien investiga: revisar, corregir y declarar."""
    if not auth["es_investigador"]:
        return []
    uid, items = auth["id"], []
    n = proyectos.n_pendientes_para(auth)
    if n:
        items.append((10, {"texto": f"{plural(n, 'pendiente')} por revisar en sus proyectos", "href": "/proyectos"}))
    condicionales = [x for x in proyectos.mis_propuestas(uid) if x["estado"] == "condicional"]
    if condicionales:
        items.append((20, {"texto": "Propuesta aceptada con condiciones: corríjala y reenvíela",
                           "href": f"/propuestas/{condicionales[0]['id']}", "detalle": condicionales[0]["nombre"]}))
    sin_fil = filiacion.pendientes(uid)
    if sin_fil:
        items.append((30, {"texto": f"{plural(sin_fil, 'publicación', 'publicaciones')} sin filiación declarada",
                           "href": "/productos?sin_filiacion=1"}))
    periodo = institucionales.periodo_abierto()
    if periodo is not None and institucionales.puede_proponer(auth):
        items.append((40, {"texto": f"Convocatoria de proyectos institucionales {institucionales.periodo_texto(periodo)} "
                                    f"abierta hasta el {institucionales.fecha_texto(institucionales.plazo(periodo)['cierra'])}",
                           "href": "/proyectos", "tono": "info"}))
    return items


def _instituto(auth):
    """Dirección del Instituto: el ciclo de vida de los proyectos institucionales."""
    if not permisos.puede(auth, "decidir_propuestas"):
        return []
    items = []
    n = institucionales.n_por_decidir()
    if n:
        items.append((10, {"texto": f"{plural(n, 'propuesta')} institucional{'es' if n != 1 else ''} por decidir",
                           "href": "/admin/propuestas"}))
    hoy = date.today()
    terminan = get_db().q(
        """SELECT id, nombre, fecha_fin FROM proyecto WHERE tipo = 'institucional' AND estado = 'vigente'
           AND fecha_fin BETWEEN ? AND ? ORDER BY fecha_fin""", [hoy.isoformat(), (hoy + timedelta(days=60)).isoformat()])
    if terminan:
        items.append((20, {"texto": f"{plural(len(terminan), 'proyecto')} institucional{'es' if len(terminan) != 1 else ''} "
                                    "termina en los próximos 60 días", "href": "/proyectos", "tono": "info",
                           "detalle": "; ".join(f"{p['nombre']} ({formato.fecha(p['fecha_fin'])})" for p in terminan[:3])}))
    sin_vinculo = get_db().q("""SELECT COUNT(*) n FROM aviso_carga WHERE tipo = 'desvinculado'
                                AND atendido_en IS NULL""")[0]["n"]
    if sin_vinculo:
        items.append((30, {"texto": f"{plural(sin_vinculo, 'participante')} con carga en proyectos quedó sin vínculo "
                                    "(lo atiende cada responsable)", "href": "/proyectos", "tono": "info"}))
    sin_filiacion = get_db().q(
        """SELECT COUNT(DISTINCT p.id) n FROM producto p JOIN producto_autor pa ON pa.producto_id = p.id
           WHERE pa.investigador_id IS NOT NULL AND pa.filiacion_instituto IS NULL
             AND p.revision IN ('indexado', 'arbitrado')""")[0]["n"]
    if sin_filiacion:
        items.append((40, {"texto": f"{plural(sin_filiacion, 'publicación', 'publicaciones')} sin filiación declarada: "
                                    "no cuentan en la memoria hasta que sus autores la declaren", "href": "/informes/memoria"}))
    return items


def inicio(auth):
    return [("mio", o, x) for o, x in _mio(auth)] + [("instituto", o, x) for o, x in _instituto(auth)]


def cifras(auth):
    """Para quien investiga: su producción del año, sus proyectos y su perfil."""
    if not auth["es_investigador"]:
        return []
    uid, anio = auth["id"], date.today().year
    del_anio = [p for p in productos.buscar(uid) if p["anio"] == anio]  # para contar basta año, revisión y estado
    mios = [p for p in proyectos.de_investigador(uid) if p["vigente"] and p["estado"] != "finalizado"]
    pct, _ = perfiles.completitud(perfiles.obtener(uid), len(perfiles.areas(uid)))
    return [(10, "Mi producción", [
        (len(del_anio), f"productos en {anio}", "/productos"),
        (sum(productos.cuenta_para_informe(p) for p in del_anio), "cuentan para el informe", "/productos?informe=1"),
        (len(mios), "proyectos vigentes", "/proyectos"),
        (f"{pct} %", "perfil completo", "/perfil")])]


# --- Tareas y lo que queda en curso (PLAN §73, etapa 3) -----------------------------------------------------------------

MANTENIMIENTO = [lambda: institucionales.mantenimiento()]    # vigencias de proyectos y recordatorios


def en_curso():
    res = []
    if institucionales.periodo_abierto() is not None:
        res.append("la convocatoria de proyectos institucionales está abierta")
    n = institucionales.n_por_decidir()
    if n:
        res.append(f"{n} propuesta(s) institucional(es) por decidir")
    return res


def historial(uid):
    """Los proyectos en que participó, en «Mi historial docente» (PLAN §68, etapa 6)."""
    filas = get_db().q(
        """SELECT p.id, p.nombre, p.estado, x.rol, x.fecha_desde, x.fecha_hasta FROM proyecto_participante x
           JOIN proyecto p ON p.id = x.proyecto_id WHERE x.investigador_id = ? ORDER BY x.fecha_desde DESC, p.nombre""", [uid])
    return [{"clave": "proyectos", "orden": 40, "titulo": "Proyectos de investigación e interacción social",
             "vacio": "No participó en proyectos.", "datos": filas,
             "filas": [{"texto": p["nombre"], "href": f"/proyectos/{p['id']}",
                        "detalle": f"{p['rol'].replace('_', ' ')} · {formato.fecha(p['fecha_desde'])}"
                                   + (f" a {formato.fecha(p['fecha_hasta'])}" if p["fecha_hasta"] else "")} for p in filas]}]

