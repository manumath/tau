"""Ficha estadística de la Carrera (PLAN §57, etapa 7) y exportación por correspondencia.

La ficha reúne, por año o por semestre, las cifras que suelen pedir los formularios de antecedentes de cualquier proceso
de evaluación: cuerpo académico (vinculados, JCE, grados, categorías y tramos de edad), oferta (paralelos e
inscripciones), admisión por cohorte y trayectoria de cada cohorte, más las cifras del tablero de indicadores.

Cada cifra tiene una **clave** estable (`valores`). Una **correspondencia** es un CSV *privado* (no se versiona ni se guarda
en el sistema) con columnas `hoja,celda,clave` que dice en qué celda de una plantilla XLSX ajena va cada clave; `llenar`
escribe esas celdas con `xlsx_plantilla`, sin tocar lo demás de la plantilla. El sistema no trae ninguna correspondencia.
"""
import csv
import io
import re
import zipfile
from datetime import date

from lxml import etree

from app.academico import gestiones
from app.calidad import cuerpo_academico, indicadores, listados
from app.calidad import marco as marco_calidad
from app.comun import exportar
from app.comun.xlsx_plantilla import Plantilla
from app.estudiantil import cohortes, rendimiento

CAMPOS_ADMISION = {"vacantes": "Vacantes ofertadas", "postulantes": "Postulantes", "ingresantes": "Ingresantes",
                   "cobertura": "Cobertura de las vacantes (%)", "ordinaria": "Admisión ordinaria", "especial": "Admisión especial",
                   "hombres": "Hombres", "mujeres": "Mujeres", "otra_ciudad": "De otra ciudad",
                   "extranjeros": "Extranjeros", "publico": "De colegio público", "privado": "De colegio privado"}
CAMPOS_COHORTE = {"ingresantes": "Ingresantes", "matriculados_al_anio": "Matriculados al año de ingresar",
                  "cursando": "Cursando hoy", "egresados": "Egresados", "titulados": "Titulados",
                  "desertores": "Desertores", "desercion_academica": "Deserción por motivo académico"}
CAMPOS_ACADEMICOS = {"total": "Académicos vinculados", "jce": "JCE", "doctores": "Con doctorado",
                     "posgrado": "Con maestría o doctorado", "sin_grado": "Sin grado registrado",
                     "con_proyecto": "Con proyecto vigente"}
_CLAVE = re.compile(r"^[a-z_]+(\.[^.\s]+)+$")
_CELDA = re.compile(r"^[A-Z]{1,3}[1-9]\d{0,6}$")
MAX_FILAS = 5_000


def _slug(texto: str) -> str:
    t = texto.lower()
    for a, b in zip("áéíóúñ ", "aeioun_"):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9_]", "", t)


def _semestres(anios_: list[int]) -> list[tuple[int, str]]:
    actual = cohortes.ordinal(*cohortes.ciclo_actual())
    return [(a, t) for a in anios_ for t in ("I", "II") if cohortes.ordinal(a, t) <= actual]


def datos(marco: dict, hasta: int | None = None) -> dict:
    """Todas las secciones de la ficha para los años de la ventana del marco que terminan en `hasta`."""
    anios_ = indicadores.anios_de(marco, hasta or date.today().year)
    sems = _semestres(anios_)
    todos = cohortes.alumnos()
    actual = cohortes.ordinal(*cohortes.ciclo_actual())
    academicos_ = [cuerpo_academico.indicadores_anio(a) for a in anios_]
    oferta = []
    for a, t in sems:
        g = gestiones.por_codigo(f"{t}-{a}")
        ins = cuerpo_academico.inscripciones(g["id"]) if g else None
        oferta.append({"semestre": f"{t}-{a}", "paralelos": ins["paralelos"] if ins else None,
                       "inscripciones": ins["inscritos"] if ins else None})
    admision, trayectoria = [], []
    vac = {(f["anio"], f["ciclo"]): f for f in rendimiento.vacantes()}
    for a, t in sems:
        o = cohortes.ordinal(a, t)
        grupo = [e for e in todos if e["ingreso"] == o]
        ad = cohortes.admision(o, todos)
        v = vac.get((a, t)) or {}
        admision.append({"semestre": f"{t}-{a}", "ingresantes": len(grupo), "vacantes": v.get("vacantes"),
                         "postulantes": v.get("postulantes"), "cobertura": v.get("cobertura"),
                         **{k: ad[k] for k in CAMPOS_ADMISION if k in ad},
                         "tramos": dict(zip([n for _, n in cohortes.TRAMOS_EDAD], ad["tramos"]))})
        r = cohortes.resumen([o, o + 2], todos)[0] if o + 2 <= actual else None
        trayectoria.append({
            "semestre": f"{t}-{a}", "ingresantes": len(grupo),
            "matriculados_al_anio": r["matricula"][1] if r and grupo else None,
            "cursando": sum(e["estado"] == "cursando" for e in grupo),
            "egresados": sum(e["egreso"] is not None for e in grupo),
            "titulados": sum(e["titulacion"] is not None for e in grupo),
            "desertores": sum(cohortes.desertor(e, actual) for e in grupo),
            "desercion_academica": sum(cohortes.desertor(e, actual) and e["motivo_retiro"] == "academico" for e in grupo)})
    tablero = {a: indicadores.valores_del_anio(marco["id"], a) for a in anios_}
    inds = [i for d in marco_calidad.arbol(marco["id"], inactivos=False) for c in d["criterios"] for i in c["indicadores"]]
    return {"anios": anios_, "semestres": [f"{t}-{a}" for a, t in sems], "academicos": academicos_, "oferta": oferta,
            "admision": admision, "trayectoria": trayectoria, "indicadores": inds, "tablero": tablero,
            "listados": listados.todos(anios_, date.today().isoformat())}


def valores(d: dict) -> dict[str, object]:
    """Las cifras de la ficha con su clave estable, en el orden en que se muestran (lo que lee una correspondencia)."""
    v: dict[str, object] = {}
    for x in d["academicos"]:
        a = x["anio"]
        for k in CAMPOS_ACADEMICOS:
            v[f"academicos.{k}.{a}"] = x[k]
        for cat, n in x["por_categoria"].items():
            v[f"academicos.categoria.{_slug(cat)}.{a}"] = n
        for tramo, n in x["tramos"].items():
            v[f"academicos.edad.{_slug(tramo)}.{a}"] = n
    for x in d["oferta"]:
        v[f"oferta.paralelos.{x['semestre']}"] = x["paralelos"]
        v[f"oferta.inscripciones.{x['semestre']}"] = x["inscripciones"]
    for x in d["admision"]:
        for k in CAMPOS_ADMISION:
            v[f"admision.{k}.{x['semestre']}"] = x[k]
        for tramo, n in x["tramos"].items():
            v[f"admision.edad.{_slug(tramo)}.{x['semestre']}"] = n
    for x in d["trayectoria"]:
        for k in CAMPOS_COHORTE:
            v[f"cohorte.{k}.{x['semestre']}"] = x[k]
    for i in d["indicadores"]:
        for a in d["anios"]:
            r = d["tablero"][a].get(i["id"])
            v[f"indicador.{i['codigo']}.{a}"] = r["valor"] if r else None
    v.update(listados.valores(d.get("listados") or {}))
    return v


def nombre_de(clave: str) -> str:
    """Descripción legible de una clave (hoja «Claves» del XLSX)."""
    partes = clave.split(".")
    if partes[0] == "listado" and len(partes) == 3:
        columnas = listados.COLUMNAS_PLAN if partes[1].startswith(("asignaturas_", "electivas_")) else \
            listados.COLUMNAS.get(partes[1], {})
        return f"Listado {partes[1].replace('_', ' ')}: {columnas.get(partes[2], partes[2])} (una fila por registro)"
    seccion, periodo = partes[0], partes[-1]
    nombres = {"academicos": CAMPOS_ACADEMICOS, "admision": CAMPOS_ADMISION, "cohorte": CAMPOS_COHORTE,
               "oferta": {"paralelos": "Paralelos", "inscripciones": "Inscripciones"}}.get(seccion, {})
    medio = ".".join(partes[1:-1])
    if medio.startswith("categoria."):
        texto = f"Categoría {medio.split('.', 1)[1]}"
    elif medio.startswith("edad."):
        texto = f"Edad {medio.split('.', 1)[1].replace('_', ' ')}"
    else:
        texto = nombres.get(medio, medio)
    return f"{texto} ({periodo})"


def a_xlsx(d: dict) -> bytes:
    acad = [{"Año": x["anio"], "Al": x["corte"], **{t: x[k] for k, t in CAMPOS_ACADEMICOS.items()},
             **{f"Categoría: {c}": n for c, n in x["por_categoria"].items()},
             **{f"Edad: {t}": n for t, n in x["tramos"].items()}} for x in d["academicos"]]
    oferta = [{"Semestre": x["semestre"], "Paralelos": x["paralelos"], "Inscripciones": x["inscripciones"]}
              for x in d["oferta"]]
    adm = [{"Cohorte": x["semestre"], **{t: x[k] for k, t in CAMPOS_ADMISION.items()},
            **{f"Edad al ingresar: {t}": n for t, n in x["tramos"].items()}} for x in d["admision"]]
    tray = [{"Cohorte": x["semestre"], **{t: x[k] for k, t in CAMPOS_COHORTE.items()}} for x in d["trayectoria"]]
    inds = [{"Código": i["codigo"], "Indicador": i["nombre"], "Unidad": i["unidad_medida"] or "",
             **{str(a): (d["tablero"][a].get(i["id"]) or {}).get("valor") for a in d["anios"]}} for i in d["indicadores"]]
    claves = [{"clave": k, "descripción": nombre_de(k) if not k.startswith("indicador.") else k,
               "valor": f"{len(val)} fila(s)" if isinstance(val, list) else val}
              for k, val in valores(d).items()]
    return exportar.a_xlsx({"Cuerpo académico": acad, "Oferta": oferta, "Admisión": adm, "Cohortes": tray,
                            "Indicadores": inds, "Claves": claves})


# --- Exportación por correspondencia -----------------------------------------------------------------------------------

def leer_correspondencia(contenido: bytes) -> tuple[list[dict], list[str]]:
    """Filas `hoja,celda,clave` del CSV (UTF-8, con o sin BOM; coma o punto y coma). Devuelve (filas, errores)."""
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], ["La correspondencia debe ser un CSV en UTF-8."]
    try:
        dialecto = csv.Sniffer().sniff(texto.splitlines()[0] if texto else "", delimiters=",;")
    except csv.Error:
        dialecto = csv.excel
    lector = csv.DictReader(io.StringIO(texto), dialect=dialecto)
    if not lector.fieldnames or {"hoja", "celda", "clave"} - {c.strip().lower() for c in lector.fieldnames}:
        return [], ["La correspondencia necesita las columnas hoja, celda y clave."]
    filas, errores = [], []
    for n, f in enumerate(lector, start=2):
        f = {(k or "").strip().lower(): (v or "").strip() for k, v in f.items()}
        if not any(f.values()):
            continue
        if n > MAX_FILAS:
            errores.append(f"La correspondencia tiene más de {MAX_FILAS} filas.")
            break
        celda = f["celda"].upper().replace("$", "")
        if not f["hoja"] or not _CELDA.match(celda) or not _CLAVE.match(f["clave"]):
            errores.append(f"Fila {n}: hoja, celda (p. ej., B7) y clave (p. ej., academicos.total.2025) son obligatorias.")
            continue
        filas.append({"fila": n, "hoja": f["hoja"], "celda": celda, "clave": f["clave"]})
    return filas, errores


def llenar(plantilla: bytes, filas: list[dict], vals: dict[str, object]) -> tuple[bytes | None, list[str], int]:
    """Escribe en la plantilla cada clave en su celda. Una clave sin dato deja la celda vacía. Devuelve
    (contenido, errores, celdas escritas); con errores no se genera nada."""
    try:
        x = Plantilla(plantilla)
        hojas = set(x.hojas)
    except (zipfile.BadZipFile, KeyError, etree.XMLSyntaxError):
        return None, ["La plantilla no es un archivo XLSX válido."], 0
    errores = []
    for f in filas:
        if f["hoja"] not in hojas:
            errores.append(f"Fila {f['fila']}: la plantilla no tiene la hoja «{f['hoja']}».")
        elif f["clave"] not in vals:
            errores.append(f"Fila {f['fila']}: clave desconocida «{f['clave']}» (vea la hoja «Claves» de la ficha).")
    if errores:
        return None, errores[:20] + ([f"… y {len(errores) - 20} más."] if len(errores) > 20 else []), 0
    n = 0
    for f in filas:
        v = vals[f["clave"]]
        if isinstance(v, list):  # un listado: una celda por fila, hacia abajo desde la indicada
            col, fila = re.match(r"([A-Z]+)(\d+)", f["celda"]).groups()
            for i, w in enumerate(v):
                x.escribir(f["hoja"], f"{col}{int(fila) + i}", w)
                n += w is not None
        else:
            x.escribir(f["hoja"], f["celda"], v)
            n += v is not None
    return x.guardar(), [], n

