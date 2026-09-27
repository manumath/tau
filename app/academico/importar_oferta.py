"""Carga de la oferta de gestiones pasadas desde CSV (PLAN.md, sección 24, paso 3.3b).

Formato: una fila por docente de cada paralelo: `gestion` (I-2021, INV-2021, II-2021, VER-2021),
`sigla`, `paralelo` (vacío = A), `inscritos`, `email` del docente (vacío si el paralelo no tuvo
docente) y `rol` (titular o auxiliar; vacío = titular). Cada materia de un titular en un semestre
cuenta 32 h/mes de carga; los cursos de verano e invierno solo los dictan titulares.

- El archivo es la fuente para las gestiones que incluye: su oferta se **reemplaza** entera (así,
  volver a importar un archivo corregido no duplica nada). Las demás gestiones no cambian.
- Todo o nada por gestión: si alguna fila de una gestión tiene un error, esa gestión no se importa.
- Si la gestión aún no existe, se crean las del año (con las fechas por omisión).

Flujo en dos pasos, como las demás cargas: `leer` valida y agrupa sin cambiar nada; `aplicar`
importa las gestiones sin errores.
"""
import csv
import io

from app.academico import gestiones, oferta
from app.comun import usuarios
from app.comun.db import auditar, get_db, sin_tildes, transaccion
from app.comun.importar_usuarios import MAX_BYTES, _decodificar, _separador

MAX_FILAS = 5000
ALIAS = {
    "gestion": ("gestion", "periodo", "semestre"),
    "sigla": ("sigla", "codigo", "materia"),
    "paralelo": ("paralelo", "grupo"),
    "inscritos": ("inscritos", "estudiantes", "matriculados"),
    "email": ("email", "correo", "correo docente", "email docente", "docente"),
    "rol": ("rol",),
}
PLANTILLA = ("gestion,sigla,paralelo,inscritos,email,rol\n"
             "I-2021,MAT-111,A,45,emmy.noether@umsa.bo,titular\n"
             "I-2021,MAT-111,A,45,alan.turing@umsa.bo,auxiliar\n"
             "I-2021,MAT-112,A,40,,\n"
             "VER-2021,MAT-278,A,12,emmy.noether@umsa.bo,\n")


def leer(contenido: bytes) -> tuple[list[dict], list[str]]:
    """→ (gestiones, errores generales). Cada gestión: codigo, anio, tipo, existe, actuales (paralelos
    que se reemplazarán), paralelos (sigla, paralelo, inscritos, docentes), errores y avisos."""
    if len(contenido) > MAX_BYTES:
        return [], ["El archivo supera 1 MB."]
    texto = _decodificar(contenido)
    if not texto.strip():
        return [], ["El archivo está vacío."]
    lector = csv.reader(io.StringIO(texto), delimiter=_separador(texto))
    encabezados = [sin_tildes(h).strip().replace("﻿", "") for h in next(lector, [])]
    indice = {c: next((i for i, h in enumerate(encabezados) if h in alias), None) for c, alias in ALIAS.items()}
    faltan = [c for c in ("gestion", "sigla") if indice[c] is None]
    if faltan:
        return [], [f"Faltan columnas: {', '.join(faltan)}. La primera fila debe tener los encabezados "
                    "(gestion, sigla y, si quiere, paralelo, inscritos, email y rol)."]
    por_gestion, n = {}, 0
    for linea, registro in enumerate(lector, start=2):
        if not any(c.strip() for c in registro):
            continue
        n += 1
        if n > MAX_FILAS:
            return [], [f"Se procesan hasta {MAX_FILAS} filas; divida el archivo."]

        def celda(campo):
            i = indice[campo]
            return registro[i].strip() if i is not None and i < len(registro) else ""

        cod = celda("gestion").upper().replace(" ", "")
        tipo, _, anio = cod.rpartition("-")
        if tipo not in gestiones.TIPOS or not anio.isdigit() or not 2000 <= int(anio) <= 2100:
            por_gestion.setdefault("?", _gestion("?", None, None))["errores"].append(
                f"Fila {linea}: gestión «{celda('gestion')}» no válida (use I-2021, INV-2021, II-2021 o VER-2021).")
            continue
        g = por_gestion.setdefault(cod, _gestion(cod, int(anio), tipo))
        _fila(g, linea, celda)
    for g in por_gestion.values():
        if g["anio"] is not None:
            existente = gestiones.por_codigo(g["codigo"])
            g["existe"] = bool(existente)
            g["actuales"] = len(oferta.listar(existente["id"])) if existente else 0
            _avisos(g)
    if not por_gestion:
        return [], ["El archivo no tiene filas con datos."]
    return sorted(por_gestion.values(), key=lambda g: (g["anio"] or 0, list(gestiones.TIPOS).index(g["tipo"])
                                                      if g["tipo"] else 0)), []


def _gestion(codigo, anio, tipo):
    return {"codigo": codigo, "anio": anio, "tipo": tipo, "existe": False, "actuales": 0, "paralelos": {},
            "errores": [], "avisos": []}


def _fila(g, linea, celda):
    problemas = []
    sigla = celda("sigla").upper().replace(" ", "")
    fila = get_db().q("SELECT * FROM asignatura WHERE sigla = ?", [sigla])
    if not fila:
        problemas.append(f"la asignatura {sigla or '(vacía)'} no está en el catálogo")
    elif not fila[0]["de_la_carrera"]:
        problemas.append(f"{sigla} la dicta otra unidad")
    paralelo = (celda("paralelo") or "A").upper()
    if len(paralelo) > 3 or not paralelo.isalnum():
        problemas.append("paralelo no válido")
    inscritos = celda("inscritos")
    if inscritos and not inscritos.isdigit():
        problemas.append("inscritos debe ser un número")
    email, rol = celda("email").lower(), (celda("rol").lower() or "titular")
    persona = None
    if email:
        persona = usuarios.por_email(email)
        if not persona:
            problemas.append(f"no hay una persona registrada con el correo {email} (regístrela, aunque sea sin acceso)")
        if rol not in oferta.ROLES:
            problemas.append("rol no válido (titular o auxiliar)")
        elif persona and g["tipo"] in oferta.TEMPORADA and rol == "titular" and not oferta.es_titular(
                persona["id"], _referencia(g)):
            problemas.append(f"{email} no es docente titular de la Carrera: no puede dictar cursos de verano o invierno")
    if problemas:
        g["errores"].append(f"Fila {linea}: " + "; ".join(problemas) + ".")
        return
    clave = (sigla, paralelo)
    p = g["paralelos"].setdefault(clave, {"sigla": sigla, "asignatura_id": fila[0]["id"], "paralelo": paralelo,
                                          "inscritos": None, "docentes": []})
    if inscritos:
        if p["inscritos"] is not None and p["inscritos"] != int(inscritos):
            g["errores"].append(f"Fila {linea}: {sigla} {paralelo} tiene otro número de inscritos en una fila anterior.")
            return
        p["inscritos"] = int(inscritos)
    if persona:
        if any(d["usuario_id"] == persona["id"] for d in p["docentes"]):
            g["errores"].append(f"Fila {linea}: {email} figura dos veces en {sigla} {paralelo}.")
            return
        p["docentes"].append({"usuario_id": persona["id"], "email": email, "rol": rol})


def _referencia(g) -> dict:
    """La gestión existente o, si aún no existe, sus fechas por omisión (para mirar el vínculo)."""
    return gestiones.por_codigo(g["codigo"]) or {"fecha_inicio": gestiones.fechas_por_omision(g["anio"], g["tipo"])[0],
                                                 "tipo": g["tipo"]}


def _avisos(g):
    """Docentes sin vínculo con la Carrera al inicio de la gestión (se importa igual)."""
    referencia = _referencia(g)
    sin = sorted({d["email"] for p in g["paralelos"].values() for d in p["docentes"]
                  if oferta.sin_vinculo_con_la_carrera(d["usuario_id"], referencia)})
    if sin:
        g["avisos"].append("Sin vínculo con la Carrera en esa gestión: " + ", ".join(sin) + ".")


def aplicar(lista: list[dict], uid: int) -> int:
    """Reemplaza la oferta de las gestiones sin errores. → cuántas gestiones se importaron."""
    n = 0
    for g in lista:
        if g["errores"] or g["anio"] is None:
            continue
        with transaccion():
            gestiones.crear_anio(g["anio"])
            gid = gestiones.por_codigo(g["codigo"])["id"]
            get_db().execute("DELETE FROM oferta WHERE gestion_id = ?", [gid])
            for p in g["paralelos"].values():
                oid = get_db().t.oferta.insert(gestion_id=gid, asignatura_id=p["asignatura_id"], paralelo=p["paralelo"],
                                               inscritos=p["inscritos"], creado_por=uid)["id"]
                for d in p["docentes"]:
                    get_db().t.oferta_docente.insert(oferta_id=oid, usuario_id=d["usuario_id"], rol=d["rol"])
        auditar(uid, "importar_oferta", "gestion_academica", gid,
                f"{g['codigo']}: {len(g['paralelos'])} paralelo(s)")
        n += 1
    return n
