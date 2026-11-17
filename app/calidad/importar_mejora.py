"""Carga del plan de mejora desde CSV (PLAN §72, etapa 4).

Una fila por actividad, con las columnas de su acción repetidas (`calidad/plan-de-mejora.csv` de la instancia es el plan
de la Carrera). Los responsables del archivo son unidades en texto; la vista previa **propone** a la persona que hoy
ocupa ese cargo (Dirección de Carrera, Dirección del Instituto, Coordinación académica, Comisión de calidad) y, si no la
encuentra, deja la acción a cargo de quien carga el archivo. Las actividades cuyo indicador ya calcula el SIAC se
**proponen ligadas** a él («Ligar al indicador …»): la cifra del archivo queda como línea base en texto.

Flujo en dos pasos, como las demás cargas: `leer` valida sin cambiar nada; `aplicar` registra. Se omite toda acción cuyo
código ya está en el plan (cargar dos veces el mismo archivo no duplica nada).
"""
import calendar
import re

from app.calidad import actividades_mejora as am
from app.calidad import evidencias, mejora
from app.comun import permisos, unidades
from app.comun.db import sin_tildes, transaccion
from app.comun.importar_usuarios import MAX_BYTES, leer_tabla  # noqa: F401  (MAX_BYTES lo usa la ruta)

MAX_FILAS = 500
COLUMNAS = ("accion", "accion_titulo", "objetivo", "accion_responsable", "prioridad", "criterio", "actividad",
            "descripcion", "responsable", "presupuesto", "fuente", "recursos_humanos", "otros_recursos", "verificacion",
            "indicador", "linea_base", "meta", "difusion", "inicio", "fin")
ALIAS = {c: (c, c.replace("_", " ")) for c in COLUMNAS}
ALIAS["accion_titulo"] += ("titulo de la accion",)
ALIAS["fin"] += ("plazo",)
OBLIGATORIAS = ("accion", "accion_titulo", "descripcion", "fin")
PLANTILLA = ",".join(COLUMNAS) + "\n" + (
    "A1,Reducir la deserción del ciclo básico,Bajar la deserción al primer año,Comisión Académica,P1,,1.1,"
    "Acompañamiento en los dos primeros años,Comisión Académica,2.000,RP,Auxiliares de docencia,Material de apoyo,"
    "Comparación anual por cohorte,Deserción al primer año,21.7 % (cohortes 2017-2025),Menos de 21.7 % en 2028,"
    "Inducción de nuevos estudiantes,03/2027,12/2028\n")
PRIORIDADES = {"p1": "alta", "p2": "media", "p3": "baja", "alta": "alta", "media": "media", "baja": "baja"}
FUENTES = {"rp": "Recursos Propios", "tgn": "Recursos TGN"}

# Cargo en el texto del responsable → rol y unidad de quien hoy lo ocupa. Se mira solo la primera unidad («A / B»).
CARGOS = (("direccion del iimat", "direccion_instituto", "instituto"), ("iimat", "direccion_instituto", "instituto"),
          ("direccion del instituto", "direccion_instituto", "instituto"),
          ("direccion de carrera", "direccion_carrera", "carrera"), ("comision academica", "coordinacion_academica", "carrera"),
          ("coordinacion academica", "coordinacion_academica", "carrera"),
          ("comision de autoevaluacion", "comision_calidad", "universidad"),
          ("comision de calidad", "comision_calidad", "universidad"))
# Palabras del indicador o la línea base → nombre del indicador del marco que ya lo calcula. La primera que calza gana.
PISTAS = (("titulacion oportuna", "Titulación oportuna"), ("tiempo de graduacion", "Tiempo medio de titulación"),
          ("desercion al primer ano", "Retención al primer año"), ("desercion", "Deserción de la cohorte"),
          ("mujeres", "Mujeres entre los ingresantes"), ("tutor", "Cobertura de la tutoría"),
          ("jornada completa", "Jornadas completas equivalentes"), ("capacitados", "Personal capacitado"),
          ("empleadores", "Satisfacción de los empleadores"), ("movilidad", "Estudiantes en movilidad"),
          ("convenios", "Convenios con actividad en el año"),
          ("plan de desarrollo de la carrera", "Plan de desarrollo de la Carrera aprobado y vigente"),
          ("satisfaccion", "Satisfacción de los estudiantes con la docencia"))


def _mes(texto: str, fin: bool) -> str:
    """«03/2027» o «2027-03» → primer o último día del mes; lo demás pasa tal cual (lo valida `am.validar`)."""
    t = (texto or "").strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", t) or re.fullmatch(r"(\d{4})-(\d{1,2})", t)
    if not m:
        return t
    anio, mes = (int(m[2]), int(m[1])) if "/" in t else (int(m[1]), int(m[2]))
    if not 1 <= mes <= 12:
        return t
    return f"{anio:04d}-{mes:02d}-{calendar.monthrange(anio, mes)[1] if fin else 1:02d}"


def proponer_responsable(texto: str | None) -> dict | None:
    primera = sin_tildes((texto or "").split("/")[0]).strip()
    for clave, rol, tipo in CARGOS:
        if primera.startswith(clave):
            gente = permisos.con_rol(rol, unidades.de_tipo(tipo))
            return gente[0] if gente else None
    return None


def proponer_indicador(texto: str, inds: list[dict]) -> dict | None:
    t = sin_tildes(texto or "")
    por_nombre = {sin_tildes(i["nombre"]): i for i in inds}
    for pista, nombre in PISTAS:
        if pista in t and (i := por_nombre.get(sin_tildes(nombre))):
            return i
    return None


def _actividad(d: dict, mid: int, propuesto: dict | None) -> tuple[dict, list[str]]:
    recursos = "; ".join(x for x in (d["recursos_humanos"] and f"humanos: {d['recursos_humanos']}",
                                     d["otros_recursos"] and f"otros: {d['otros_recursos']}") if x)
    fuente = FUENTES.get(sin_tildes(d["fuente"]).strip(), d["fuente"])
    verificacion = ". ".join(x for x in (d["verificacion"].rstrip("."), d["indicador"] and f"Indicador: {d['indicador']}") if x)
    return am.validar({"codigo": d["actividad"], "descripcion": d["descripcion"] + (f"\n\nRecursos {recursos}." if recursos else ""),
                       "linea_base": d["linea_base"], "meta": d["meta"], "unidad_responsable": d["responsable"],
                       "responsable_id": str(propuesto["id"]) if propuesto else "", "inicio": _mes(d["inicio"], False),
                       "plazo": _mes(d["fin"], True), "presupuesto": d["presupuesto"], "fuente": fuente,
                       "verificacion": verificacion, "difusion": d["difusion"]}, mid)


def leer(contenido: bytes, mid: int, uid: int) -> tuple[list[dict], list[str]]:
    """→ (acciones, errores generales). Cada acción: codigo, datos (validados), responsable_texto, responsable (propuesto),
    estado ('nueva' | 'existe' | 'error'), mensajes y actividades (linea, codigo, datos, errores, indicador propuesto)."""
    filas, errores = leer_tabla(contenido, ALIAS, OBLIGATORIAS, MAX_FILAS)
    if errores:
        return [], errores
    existentes = {sin_tildes(a["codigo"]) for a in mejora.acciones(mid) if a.get("codigo")}
    criterios = {sin_tildes(c["codigo"]): c["id"] for c in evidencias.criterios_del_marco(mid)}
    inds = mejora.indicadores_del_marco(mid)
    acciones: dict[str, dict] = {}
    for linea, d in filas:
        clave = sin_tildes(d["accion"]).strip()
        if not clave:
            acciones.setdefault(f"línea {linea}", {"codigo": "", "estado": "error", "mensajes": [
                f"Línea {linea}: falta el código de la acción."], "actividades": [], "datos": {"titulo": d["accion_titulo"]}})
            continue
        if clave not in acciones:
            resp = proponer_responsable(d["accion_responsable"])
            acciones[clave] = {"codigo": d["accion"].strip(), "titulo": d["accion_titulo"], "objetivo": d["objetivo"],
                               "responsable_texto": d["accion_responsable"], "responsable": resp,
                               "prioridad": PRIORIDADES.get(sin_tildes(d["prioridad"]).strip(), ""),
                               "criterio": d["criterio"], "actividades": [], "mensajes": [],
                               "estado": "existe" if clave in existentes else "nueva"}
            if d["prioridad"] and not acciones[clave]["prioridad"]:
                acciones[clave]["mensajes"].append(f"Prioridad «{d['prioridad']}» desconocida: se usa P2.")
            if d["criterio"] and sin_tildes(d["criterio"]).strip() not in criterios:
                acciones[clave]["mensajes"].append(f"El criterio «{d['criterio']}» no está en el marco: queda sin criterio.")
        a = acciones[clave]
        prop = proponer_responsable(d["responsable"])
        x, errs = _actividad(d, mid, prop)
        ind = proponer_indicador(f"{d['indicador']} {d['linea_base']}", inds)
        a["actividades"].append({"linea": linea, "codigo": d["actividad"], "datos": x, "errores": errs,
                                 "responsable": prop, "indicador": ind})
    for a in acciones.values():
        if a["estado"] == "error":
            continue
        validas = [t for t in a["actividades"] if not t["errores"]]
        plazo = max((t["datos"]["plazo"] for t in validas), default="")
        x, errs = mejora.validar({"codigo": a["codigo"], "titulo": a["titulo"], "objetivo": a["objetivo"],
                                  "descripcion": f"Responsable según el plan: {a['responsable_texto']}."
                                  if a["responsable_texto"] else "",
                                  "prioridad": a["prioridad"] or "media", "plazo": plazo, "origen": "otro",
                                  "criterio_id": str(criterios.get(sin_tildes(a["criterio"] or "").strip(), "")),
                                  "responsable_id": str((a["responsable"] or {}).get("id") or uid)}, mid)
        a["datos"] = x
        if not validas:
            errs = errs + ["Ninguna actividad válida."]
        if errs and a["estado"] == "nueva":
            a["estado"] = "error"
            a["mensajes"] += [e for e in errs if e != "Indique el plazo." or validas]
    return list(acciones.values()), []


def aplicar(acciones: list[dict], mid: int, uid: int, ligar: set[str]) -> tuple[int, int]:
    """Registra las acciones nuevas y sus actividades sin errores. `ligar` = {"A4|4.2", …}: actividades que quedan ligadas
    al indicador propuesto. → (acciones, actividades) registradas."""
    n_acc = n_act = 0
    with transaccion():
        for a in acciones:
            if a["estado"] != "nueva":
                continue
            aid = mejora.crear(mid, a["datos"], uid)
            n_acc += 1
            for t in a["actividades"]:
                if t["errores"]:
                    continue
                x = dict(t["datos"])
                if t["indicador"] and f"{a['codigo']}|{t['codigo']}" in ligar:
                    x["indicador_id"] = t["indicador"]["id"]
                am.crear(aid, x, uid)
                n_act += 1
    return n_acc, n_act


def plan_de_la_carrera() -> bytes:
    """El archivo versionado del plan 2026–2030 (para la prueba y para cargarlo sin buscarlo)."""
    from app.comun import config
    return (config.INSTANCIA / "calidad" / "plan-de-mejora.csv").read_bytes()

