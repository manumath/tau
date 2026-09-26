"""Carga del catálogo de revistas desde CSV (solo las revistas donde publica el instituto).

Una fila por revista e índice: `titulo`, `issn` o `eissn` y, opcionalmente, `pais`, `editorial`,
`arbitrada` y `acceso_abierto` (sí/no), `indice`, `desde`, `hasta`, `cuartil`, `fuente` y
`evidencia` (enlace). Las filas de una misma revista (mismo ISSN o, sin ISSN, mismo título) se
agrupan. Una revista existente se completa (no se borran sus datos) y se le agregan las
indexaciones nuevas. Lo cargado por la administración queda verificado.
"""
import csv
import io

from app import revistas
from app.db import auditar, get_db, sin_tildes
from app.importar_usuarios import MAX_BYTES, SI, NO, _decodificar, _separador

MAX_FILAS = 3000
ALIAS = {
    "titulo": ("titulo", "revista", "nombre", "titulo de la revista"),
    "issn": ("issn", "issn impreso", "print issn", "p-issn"),
    "eissn": ("eissn", "e-issn", "issn electronico", "electronic issn"),
    "pais": ("pais", "country"), "editorial": ("editorial", "publisher"),
    "arbitrada": ("arbitrada", "revision por pares", "peer review"),
    "acceso_abierto": ("acceso abierto", "acceso_abierto", "open access", "oa"),
    "indice": ("indice", "base", "base de datos", "index"),
    "desde": ("desde", "desde anio", "desde año", "inicio"), "hasta": ("hasta", "hasta anio", "hasta año", "fin"),
    "cuartil": ("cuartil", "quartile"), "fuente": ("fuente", "source"),
    "evidencia": ("evidencia", "enlace", "url evidencia", "evidencia_url"),
}
PLANTILLA = ("titulo,issn,eissn,pais,editorial,arbitrada,acceso_abierto,indice,desde,hasta,cuartil,fuente,evidencia\n"
             "Revista de ejemplo de Matemática,0028-0836,,Bolivia,Carrera de Matemática UMSA,sí,sí,SciELO,2019,,,"
             "Portal SciELO (consulta 09/2026),https://www.scielo.org/\n")


def _si_no(v):
    t = sin_tildes(v or "").strip()
    return 1 if t in SI - {""} else 0 if t in NO - {""} else None


def _indice(nombre: str, indices: list[dict]):
    """'Scopus', 'scie', 'WoS ESCI', 'zbMATH'… → fila de `indice` (o None si no se reconoce)."""
    t = sin_tildes(nombre or "").strip().lower()
    if not t:
        return None
    exactos = [i for i in indices if sin_tildes(i["nombre"]).lower() == t]
    if exactos:
        return exactos[0]
    palabras = set(t.replace("wos", "web of science").split())
    parecidos = [i for i in indices
                 if palabras <= set(sin_tildes(i["nombre"]).lower().replace("(", " ").replace(")", " ").split())]
    return parecidos[0] if len(parecidos) == 1 else None


def leer(contenido: bytes) -> tuple[list[dict], list[str]]:
    """→ (revistas agrupadas, errores generales). Cada una: clave, datos, existente, indexaciones,
    errores."""
    if len(contenido) > MAX_BYTES:
        return [], ["El archivo supera 1 MB."]
    texto = _decodificar(contenido)
    if not texto.strip():
        return [], ["El archivo está vacío."]
    lector = csv.reader(io.StringIO(texto), delimiter=_separador(texto))
    encabezados = [sin_tildes(h).strip().replace("﻿", "") for h in next(lector, [])]
    indice = {c: next((i for i, h in enumerate(encabezados) if h in alias), None) for c, alias in ALIAS.items()}
    if indice["titulo"] is None:
        return [], ["Falta la columna «titulo». La primera fila debe tener los encabezados."]
    catalogo = revistas.indices_catalogo()
    grupos = {}
    for linea, registro in enumerate(lector, start=2):
        if not any(c.strip() for c in registro):
            continue
        if linea > MAX_FILAS + 1:
            return [], [f"Se procesan hasta {MAX_FILAS} filas; divida el archivo."]

        def celda(campo):
            i = indice[campo]
            return registro[i].strip() if i is not None and i < len(registro) else ""

        datos, errores = revistas.validar({c: celda(c) for c in ("titulo", "issn", "eissn", "pais", "editorial")})
        datos["arbitrada"], datos["acceso_abierto"] = _si_no(celda("arbitrada")), _si_no(celda("acceso_abierto"))
        # «Ya existe» no es un error aquí: la revista existente se completa.
        errores = [e for e in errores if not e.startswith("Ya existe")]
        clave = datos.get("issn") or datos.get("eissn") or sin_tildes(datos["titulo"] or "").lower()
        g = grupos.setdefault(clave, {"clave": clave, "datos": datos, "indexaciones": [], "errores": []})
        g["errores"] += [f"Fila {linea}: {e}" for e in errores]
        if celda("indice"):
            ind = _indice(celda("indice"), catalogo)
            x, err = revistas.validar_indexacion({"indice_id": ind["id"] if ind else None, "desde": celda("desde"),
                                                 "hasta": celda("hasta"), "cuartil": celda("cuartil"),
                                                 "fuente": celda("fuente"), "evidencia_url": celda("evidencia")})
            if not ind:
                err = [f"índice «{celda('indice')}» no reconocido"] + [e for e in err if e != "Elija el índice."]
            if err:
                g["errores"].append(f"Fila {linea}: " + "; ".join(err))
            else:
                g["indexaciones"].append({**x, "indice": ind["nombre"]})
    if not grupos:
        return [], ["El archivo no tiene filas con datos."]
    for g in grupos.values():
        d = g["datos"]
        g["existente"] = revistas.por_issn(d.get("issn")) or revistas.por_issn(d.get("eissn")) or next(
            (r for r in get_db().q("SELECT * FROM revista WHERE sin_tildes(titulo) = sin_tildes(?)", [d["titulo"] or ""])),
            None)
    return list(grupos.values()), []


def aplicar(grupos: list[dict], admin_id: int) -> tuple[int, int, int]:
    """→ (revistas nuevas, revistas completadas, indexaciones agregadas). Omite las que tienen errores."""
    nuevas = completadas = n_idx = 0
    for g in grupos:
        if g["errores"]:
            continue
        d = {k: v for k, v in g["datos"].items() if v is not None}
        if g["existente"]:
            rid = g["existente"]["id"]
            faltan = {k: v for k, v in d.items() if g["existente"].get(k) in (None, "")}
            if faltan:
                revistas.actualizar(rid, faltan)
            revistas.verificar(rid, admin_id)
            completadas += 1
        else:
            rid = revistas.crear(d, admin_id, verificada=True)
            nuevas += 1
        for x in g["indexaciones"]:
            if not revistas.agregar_indexacion(rid, {k: v for k, v in x.items() if k != "indice"}, admin_id):
                n_idx += 1
        revistas.reclasificar(rid)
    if nuevas or completadas:
        auditar(admin_id, "importar_revistas", "revista", None,
                f"{nuevas} nueva(s), {completadas} completada(s), {n_idx} indexación(es)")
    return nuevas, completadas, n_idx
