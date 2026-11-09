"""Las funciones de IA de TAU (PLAN §59, etapas 1 a 3) y los datos que recibe cada una.

Aquí se arma, en un solo lugar, lo que se envía al modelo: cada dato lleva su origen (`clasificacion`). Las pantallas
llaman a `datos_<función>` y a `servicio.generar`; nunca arman el contexto por su cuenta. Así se puede auditar qué ve
la IA leyendo este archivo.

Ninguna función decide sobre personas (principio 7): redactan borradores o sugieren opciones que una persona aprueba,
corrige o descarta.
"""
import random
import re
from datetime import date

from app.comun import config, permisos
from app.comun.db import auditar, get_db
from app.ia import textos
from app.ia.clasificacion import INTERNO, PERSONAL, PUBLICO
from app.ia.funciones import Funcion, registrar

MAX_LINEAS_SUGERIDAS = 3
MAX_EVIDENCIAS_SUGERIDAS = 8
MIN_RESPUESTAS_SINTESIS = 10     # la síntesis de respuestas abiertas exige 10 (las encuestas muestran desde 5)


def _numero(entidad: str | None, prefijo: str, pos: int = 1) -> int | None:
    """El número en la posición `pos` de «prefijo:1:2…»."""
    partes = (entidad or "").split(":")
    if len(partes) <= pos or partes[0] != prefijo or not partes[pos].isdigit():
        return None
    return int(partes[pos])


def _rol(rol):
    return lambda auth, entidad=None: permisos.tiene_rol(auth, rol)


def _rol_aprueba(rol):
    return lambda auth, uso: permisos.tiene_rol(auth, rol)


def _permitidos(datos: list[tuple[str, str]], anios=()) -> set[str]:
    """Números que el modelo puede repetir: los que ya están en los datos (un año en un título) y los años del periodo."""
    res = {str(a) for a in anios}
    for _, valor in datos:
        res |= textos.numeros(valor)
    return res


def _marcadores(valores: dict[str, int], descripciones: dict[str, str]) -> tuple[str, str]:
    """Origen y texto que explican al modelo los marcadores de cifras disponibles (sin sus valores)."""
    return ("marcadores.texto", "\n".join(f"{{{{{k}}}}}: {descripciones[k]}" for k in valores))


# --- 1a · Memoria anual del Instituto -----------------------------------------------------------------------------

def _puede_aprobar_memoria(auth, uso):
    return permisos.tiene_rol(auth, "direccion_instituto")


MEMORIA = registrar(Funcion(
    clave="memoria_borrador", nombre="Borrador de la presentación de la memoria", modulo="informes",
    descripcion="Redacta la presentación y la síntesis por línea de la memoria del Instituto.",
    nivel_max=INTERNO, revisor="la Dirección del Instituto", puede_pedir=_rol("direccion_instituto"),
    puede_aprobar=_puede_aprobar_memoria, max_tokens=1800,
    datos="Títulos de los productos que cuentan, nombres y descripciones de los proyectos, actividades y líneas. "
          "Las cifras no salen del modelo: se insertan desde la base."))

_DESC_MEMORIA = {"productos": "productos que cuentan en el periodo", "indexados": "productos indexados",
                 "arbitrados": "productos arbitrados", "actividades": "actividades con participación del Instituto",
                 "proyectos": "proyectos vigentes en el periodo"}


def datos_memoria(m: dict) -> tuple[list[tuple[str, str]], callable]:
    valores = {"productos": len(m["productos"]), "indexados": m["n_indexados"], "arbitrados": m["n_arbitrados"],
               "actividades": len(m["actividades"]), "proyectos": len(m["proyectos"])}
    datos = [("periodo.texto", m.get("titulo") or f"{m['desde']} a {m['hasta']}"), _marcadores(valores, _DESC_MEMORIA)]
    datos += [("linea_investigacion.nombre", x["nombre"]) for x in get_db().q(
        "SELECT DISTINCT l.nombre FROM linea_investigacion l JOIN proyecto_linea pl ON pl.linea_id = l.id")]
    datos += [("producto.titulo", p["titulo"]) for p in m["productos"][:80]]
    for p in m["proyectos"][:40]:
        datos.append(("proyecto.nombre", p["nombre"]))
        if p.get("descripcion"):
            datos.append(("proyecto.descripcion", p["descripcion"][:600]))
    datos += [("actividad.titulo", a["titulo"]) for a in m["actividades"][:60]]
    permitidos = _permitidos(datos, range(int(m["desde"][:4]), int(m["hasta"][:4]) + 1))
    return datos, lambda t: textos.cifras(t, valores, permitidos)


# --- 1b · Informe de un proyecto ---------------------------------------------------------------------------------

def _responsable(auth, entidad=None):
    from app.investigacion import proyectos
    pid = _numero(entidad, "informe_proyecto")
    return bool(pid) and auth["id"] in {r["id"] for r in proyectos.responsables(pid) if r.get("interno")}


INFORME_PROYECTO = registrar(Funcion(
    clave="informe_proyecto_borrador", nombre="Borrador de la síntesis del informe de proyecto", modulo="informes",
    descripcion="Redacta la síntesis del avance de un proyecto en el periodo del informe.",
    nivel_max=INTERNO, revisor="el responsable del proyecto", puede_pedir=_responsable, max_tokens=1200,
    datos="Nombre, descripción y objetivos del proyecto; títulos de sus productos y actividades del periodo. "
          "Las cifras se insertan desde la base."))

_DESC_PROYECTO = {"productos": "productos del proyecto en el periodo", "actividades": "actividades del periodo",
                  "objetivos": "objetivos del proyecto"}


def entidad_informe(pid: int, desde: int, hasta: int) -> str:
    return f"informe_proyecto:{pid}:{desde}-{hasta}"


def datos_informe_proyecto(d: dict, desde: int, hasta: int) -> tuple[list[tuple[str, str]], callable]:
    p = d["proyecto"]
    prods = d["productos_informe"] + d["productos_otros"]
    valores = {"productos": len(prods), "actividades": len(d["actividades"]), "objetivos": len(d["objetivos"])}
    datos = [("periodo.texto", f"{desde} a {hasta}" if desde != hasta else str(desde)),
             _marcadores(valores, _DESC_PROYECTO), ("proyecto.nombre", p["nombre"])]
    if p.get("descripcion"):
        datos.append(("proyecto.descripcion", p["descripcion"][:1500]))
    datos += [("proyecto.objetivos", o["texto"]) for o in d["objetivos"]]
    datos += [("producto.titulo", x["titulo"]) for x in prods[:40]]
    datos += [("actividad.titulo", a["titulo"]) for a in d["actividades"][:40]]
    permitidos = _permitidos(datos, range(desde, hasta + 1))
    return datos, lambda t: textos.cifras(t, valores, permitidos)


# --- 2 · Clasificación de productos en las líneas oficiales -------------------------------------------------------

def _editor_producto(auth, entidad=None):
    from app.investigacion import productos
    pid = _numero(entidad, "producto")
    p = productos.obtener(pid) if pid else None
    return bool(p) and productos.puede_editar(p, auth["id"])


def _lineas_vigentes() -> dict[str, dict]:
    from app.investigacion import lineas
    return {str(x["id"]): x for x in lineas.vigentes()}


def _opciones_lineas(uso):
    """Todas las líneas vigentes; las sugeridas primero (la pantalla las marca)."""
    vig = _lineas_vigentes()
    sugeridas = [v for v in (uso.get("texto_generado") or "").split(",") if v in vig]
    resto = [k for k in vig if k not in sugeridas]
    return [(k, vig[k]["nombre"], None) for k in sugeridas + resto]


def _guardar_lineas(uso, texto):
    pid = uso["entidad_id"]
    elegidas = [int(v) for v in texto.split(",") if v.strip().isdigit()]
    for lid in elegidas:
        get_db().execute("INSERT OR IGNORE INTO producto_linea (producto_id, linea_id, asignado_por) VALUES (?, ?, ?)",
                         [pid, lid, uso["revisor_id"]])
    auditar(uso["revisor_id"], "asignar_lineas_producto", "producto", pid, texto)


CLASIFICAR = registrar(Funcion(
    clave="producto_clasificar", nombre="Sugerencia de líneas de investigación de un producto", modulo="productos",
    descripcion="Sugiere a qué líneas oficiales corresponde un producto; el investigador marca las que acepta.",
    nivel_max=PUBLICO, revisor="el investigador", puede_pedir=_editor_producto, al_aprobar=_guardar_lineas,
    opciones=_opciones_lineas, max_tokens=200,
    datos="Título, resumen y revista del producto y el catálogo de líneas vigentes (datos públicos)."))


def datos_clasificar(p: dict) -> tuple[list[tuple[str, str]], callable]:
    from app.investigacion import lineas
    vig = lineas.vigentes()
    datos = [("producto.titulo", p["titulo"])]
    if p.get("resumen"):
        datos.append(("producto.resumen", p["resumen"][:2500]))
    if p.get("medio"):
        datos.append(("producto.revista", p["medio"]))
    datos.append(("linea_investigacion.nombre", "\n".join(f"{x['id']}. {x['nombre']}" for x in vig)))
    validos = [str(x["id"]) for x in vig]

    def elegir(texto):
        vistos = []
        for n in re.findall(r"\d+", texto):
            if n in validos and n not in vistos:
                vistos.append(n)
        return ",".join(vistos[:MAX_LINEAS_SUGERIDAS])
    return datos, elegir


# --- 2 · Resumen del CV (perfil público) ---------------------------------------------------------------------------

def _propio_investigador(auth, entidad=None):
    return entidad == f"investigador:{auth['id']}"


def _guardar_bio(uso, texto):
    from app.investigacion import perfiles
    perfiles.actualizar_bio(uso["usuario_id"], texto)
    auditar(uso["revisor_id"], "editar_bio", "investigador", uso["usuario_id"], "resumen con apoyo de IA")


CV = registrar(Funcion(
    clave="cv_resumen", nombre="Borrador del resumen del perfil", modulo="perfil",
    descripcion="Redacta el resumen del perfil público a partir de la producción del propio investigador.",
    nivel_max=PERSONAL, revisor="el propio investigador", puede_pedir=_propio_investigador, al_aprobar=_guardar_bio,
    seudonimizar=True, max_tokens=600,
    datos="Nombre (reemplazado por un seudónimo antes de enviarse), resumen actual, títulos de sus productos y "
          "proyectos, áreas MSC y líneas."))


def datos_cv(uid: int) -> list[tuple[str, str]]:
    from app.investigacion import perfiles
    p = perfiles.obtener(uid)
    datos = [("persona.nombre", f"{p['nombres']} {p['apellidos']}")]
    if p.get("bio"):
        datos.append(("investigador.bio", p["bio"]))
    datos += [("msc.texto", f"{a['codigo']} {a.get('texto_plano') or a.get('texto') or ''}".strip())
              for a in perfiles.areas(uid)]
    datos += [("linea_investigacion.nombre", x["nombre"]) for x in get_db().q(
        """SELECT l.nombre FROM investigador_linea x JOIN linea_investigacion l ON l.id = x.linea_id
           WHERE x.usuario_id = ?""", [uid])]
    datos += [("producto.titulo", x["titulo"]) for x in get_db().q(
        """SELECT p.titulo FROM producto p JOIN producto_autor pa ON pa.producto_id = p.id
           WHERE pa.investigador_id = ? ORDER BY p.anio DESC LIMIT 40""", [uid])]
    datos += [("proyecto.nombre", x["nombre"]) for x in get_db().q(
        """SELECT DISTINCT p.nombre FROM proyecto p JOIN proyecto_participante pp ON pp.proyecto_id = p.id
           WHERE pp.investigador_id = ? LIMIT 20""", [uid])]
    return datos


# --- 3a · Síntesis de respuestas abiertas de una encuesta ----------------------------------------------------------

def _gestiona_encuestas(auth, entidad=None):
    from app.comun import vinculos
    return permisos.puede(auth, "gestionar_encuestas", vinculos.carrera())


def _aprueba_encuestas(auth, uso):
    return _gestiona_encuestas(auth)


SINTESIS = registrar(Funcion(
    clave="encuesta_sintesis", nombre="Síntesis de respuestas abiertas", modulo="encuestas",
    descripcion="Agrupa en temas las respuestas a una pregunta abierta (con 10 respuestas o más).",
    nivel_max=PERSONAL, revisor="quien gestiona las encuestas", puede_pedir=_gestiona_encuestas,
    puede_aprobar=_aprueba_encuestas, externa=False, max_tokens=1200,
    datos="El texto de la pregunta y las respuestas abiertas, mezcladas y sin ningún dato de quién respondió ni "
          "cuándo. Solo con el modelo local. La síntesis no reproduce frases textuales."))


def datos_sintesis(pregunta: str, respuestas: list[str]) -> tuple[list[tuple[str, str]], callable]:
    """Las respuestas van juntas, en orden aleatorio, sin metadatos (ni invitación, ni hora, ni cohorte)."""
    mezcla = [r.strip() for r in respuestas if r and r.strip()]
    random.shuffle(mezcla)
    datos = [("pregunta.texto", pregunta),
             ("encuesta.respuestas_agregadas", "\n".join(f"- {r[:1000]}" for r in mezcla))]
    return datos, lambda t: textos.sin_citas(t, mezcla)


# --- 3b · Evidencias y narrativa de la autoevaluación --------------------------------------------------------------

def _comision(auth, entidad=None):
    from app.calidad import autoevaluacion as ae, marco
    prefijo = (entidad or "").split(":")[0]
    aid = _numero(entidad, prefijo) if prefijo in ("evidencias", "juicio") else None
    a = ae.obtener(aid) if aid else None
    return bool(a) and a["estado"] == "en_curso" and marco.puede(auth, "registrar_juicios_calidad",
                                                                 marco.obtener(a["marco_id"]))


def _comision_aprueba(auth, uso):
    return _comision(auth, uso["entidad_tipo"])


def candidatos_evidencia(a: dict) -> dict[str, dict]:
    """Registros de TAU del periodo de la autoevaluación que pueden servir de evidencia: clave → {titulo, ruta}."""
    desde, hasta = a["desde_anio"], a["hasta_anio"]
    res = {}
    for x in get_db().q("""SELECT id, titulo, anio FROM producto WHERE anio BETWEEN ? AND ?
                           ORDER BY anio DESC, id DESC LIMIT 60""", [desde, hasta]):
        res[f"producto-{x['id']}"] = {"titulo": f"Producto: {x['titulo']} ({x['anio']})", "ruta": f"/productos/{x['id']}"}
    for x in get_db().q("""SELECT id, nombre FROM proyecto WHERE estado != 'formulacion'
                           AND (fecha_inicio IS NULL OR substr(fecha_inicio, 1, 4) <= ?)
                           AND (fecha_fin IS NULL OR substr(fecha_fin, 1, 4) >= ?) ORDER BY id DESC LIMIT 40""",
                        [str(hasta), str(desde)]):
        res[f"proyecto-{x['id']}"] = {"titulo": f"Proyecto: {x['nombre']}", "ruta": f"/proyectos/{x['id']}"}
    for x in get_db().q("""SELECT id, titulo, substr(fecha_inicio, 1, 4) AS anio FROM actividad
                           WHERE substr(fecha_inicio, 1, 4) BETWEEN ? AND ? ORDER BY fecha_inicio DESC LIMIT 60""",
                        [str(desde), str(hasta)]):
        res[f"actividad-{x['id']}"] = {"titulo": f"Actividad: {x['titulo']} ({x['anio']})",
                                       "ruta": f"/actividades/{x['id']}"}
    return res


def _autoevaluacion_de(uso) -> dict | None:
    from app.calidad import autoevaluacion as ae
    aid = _numero(uso["entidad_tipo"], "evidencias")
    return ae.obtener(aid) if aid else None


def _opciones_evidencias(uso):
    a = _autoevaluacion_de(uso)
    cand = candidatos_evidencia(a) if a else {}
    return [(k, cand[k]["titulo"], cand[k]["ruta"]) for k in (uso.get("texto_generado") or "").split(",") if k in cand]


def _crear_evidencias(uso, texto):
    from app.calidad import evidencias
    a = _autoevaluacion_de(uso)
    cand = candidatos_evidencia(a)
    cid = _numero(uso["entidad_tipo"], "evidencias", 2)
    for k in texto.split(","):
        if k in cand:
            x = {"titulo": cand[k]["titulo"][:200], "fecha": date.today().isoformat(), "vigente_hasta": None,
                 "url": config.URL_BASE.rstrip("/") + cand[k]["ruta"], "criterios": [cid],
                 "descripcion": "Registro de TAU sugerido con apoyo de IA y aceptado por la Comisión de calidad."}
            eid = evidencias.crear(a["marco_id"], "enlace", x, uso["revisor_id"])
            auditar(uso["revisor_id"], "crear_evidencia", "evidencia_calidad", eid, f"sugerida por IA: {k}")


EVIDENCIAS = registrar(Funcion(
    clave="evidencia_sugerir", nombre="Sugerencia de evidencias para un criterio", modulo="autoevaluacion",
    descripcion="Sugiere registros de TAU (productos, proyectos, actividades) que podrían respaldar un criterio; la "
                "Comisión acepta o descarta cada uno.",
    nivel_max=INTERNO, revisor="la Comisión de calidad", puede_pedir=_comision, puede_aprobar=_comision_aprueba,
    al_aprobar=_crear_evidencias, opciones=_opciones_evidencias, max_tokens=300,
    datos="El texto del criterio y los títulos de los productos, proyectos y actividades del periodo evaluado."))


def datos_evidencias(a: dict, criterio: dict) -> tuple[list[tuple[str, str]], callable]:
    cand = candidatos_evidencia(a)
    datos = [("criterio_calidad.texto", _texto_criterio(criterio)),
             ("evidencia_calidad.titulo", "\n".join(f"{k}: {v['titulo']}" for k, v in cand.items()))]

    def elegir(texto):
        vistos = []
        for k in re.findall(r"(?:producto|proyecto|actividad)-\d+", texto):
            if k in cand and k not in vistos:
                vistos.append(k)
        return ",".join(vistos[:MAX_EVIDENCIAS_SUGERIDAS])
    return datos, elegir


def _texto_criterio(c: dict) -> str:
    return " ".join(str(c[k]) for k in ("codigo", "nombre", "descripcion") if c.get(k))


def _guardar_narrativa(uso, texto):
    from app.calidad import autoevaluacion as ae
    aid, cid = _numero(uso["entidad_tipo"], "juicio"), _numero(uso["entidad_tipo"], "juicio", 2)
    j = ae.juicios(aid).get(cid) or {}
    x = {k: j.get(k) for k in ("nivel", "nivel_nombre", "fortalezas", "debilidades")} | {"juicio": texto}
    ae.guardar_juicio(aid, cid, x, uso["revisor_id"])


NARRATIVA = registrar(Funcion(
    clave="autoevaluacion_borrador", nombre="Borrador de la narrativa de un criterio", modulo="autoevaluacion",
    descripcion="Redacta el texto del juicio de un criterio a partir de sus evidencias. El nivel de logro lo asigna "
                "la Comisión; la IA no lo propone.",
    nivel_max=INTERNO, revisor="la Comisión de calidad", puede_pedir=_comision, puede_aprobar=_comision_aprueba,
    al_aprobar=_guardar_narrativa, max_tokens=1200,
    datos="El texto del criterio, los títulos de sus evidencias y las fortalezas y debilidades ya registradas."))


def datos_narrativa(criterio: dict, evidencias: list[dict], juicio: dict | None) -> tuple[list, callable]:
    datos = [("criterio_calidad.texto", _texto_criterio(criterio))]
    datos += [("evidencia_calidad.titulo", e["titulo"]) for e in evidencias]
    for k in ("fortalezas", "debilidades"):
        if juicio and juicio.get(k):
            datos.append((f"juicio_criterio.{k}", juicio[k]))
    permitidos = _permitidos(datos)
    return datos, lambda t: textos.cifras(t, {}, permitidos)
