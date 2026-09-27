"""Importación y exportación de productos en BibTeX.

Importar: `leer(texto)` interpreta el .bib (acentos LaTeX → Unicode; las fórmulas $…$ se
conservan) y clasifica cada entrada como 'nueva', 'duplicada' (mismo DOI, arXiv, o mismo título
y año que un producto existente) o 'error'. No guarda nada: `crear` da de alta las elegidas.

Exportar: `exportar(productos)` genera un .bib en UTF-8 (biber y BibTeX modernos lo aceptan).
"""
import logging
import re

import bibtexparser
from bibtexparser import middlewares as mw

from app.investigacion import importacion, productos, revistas
from app.comun import config, personas
from app.comun.db import get_db, sin_tildes

MAX_BYTES = 2 * 1024 * 1024
MAX_ENTRADAS = 300

# Tipo de entrada BibTeX → tipo de producto del portal.
TIPOS = {
    "article": "Artículo en revista", "inproceedings": "Artículo en actas de congreso",
    "conference": "Artículo en actas de congreso", "proceedings": "Libro", "book": "Libro",
    "incollection": "Capítulo de libro", "inbook": "Capítulo de libro", "techreport": "Reporte de investigación",
    "report": "Reporte de investigación", "unpublished": "Preprint", "software": "Software",
}
# Tipo del portal → (tipo BibTeX, campo donde va el «medio»).
TIPOS_EXPORTAR = {
    "Artículo en revista": ("article", "journal"), "Artículo en actas de congreso": ("inproceedings", "booktitle"),
    "Libro": ("book", "publisher"), "Capítulo de libro": ("incollection", "booktitle"),
    "Reporte de investigación": ("techreport", "institution"), "Preprint": ("misc", "howpublished"),
    "Presentación": ("misc", "howpublished"), "Software": ("misc", "howpublished"),
    "Tesis dirigida": ("misc", "howpublished"),
}
NOTAS_ESTADO = {"aceptado": "Aceptado", "enviado": "Enviado", "en_preparacion": "En preparación"}


# --- Lectura -------------------------------------------------------------------------------------

def _campo(e, *nombres):
    for n in nombres:
        f = e.fields_dict.get(n) or e.fields_dict.get(n.lower()) or e.fields_dict.get(n.capitalize())
        if f is not None and str(f.value).strip():
            return f.value if not isinstance(f.value, str) else re.sub(r"\s+", " ", f.value).strip()
    return None


def _autores(e) -> list[dict]:
    lista = _campo(e, "author") or _campo(e, "editor") or []
    res = []
    for n in lista:
        if isinstance(n, str):
            nombres, apellidos = importacion._dividir_nombre(n)
        else:
            nombres = " ".join(n.first)
            apellidos = " ".join([*n.von, *n.last]) + ("" if not n.jr else ", " + " ".join(n.jr))
        if apellidos.strip():
            res.append({"nombres": nombres.strip(), "apellidos": apellidos.strip(), "orcid": None, "afiliacion": None})
    return res


def _estado(e, tipo_bib) -> str:
    texto = sin_tildes(" ".join(str(_campo(e, x) or "") for x in ("pubstate", "note", "journal")))
    if re.search(r"accepted|in press|to appear|forthcoming|aceptado", texto):
        return "aceptado"
    if re.search(r"submitted|enviado|under review", texto):
        return "enviado"
    return "en_preparacion" if tipo_bib == "unpublished" else "publicado"


def _arxiv(e) -> str | None:
    """Identificador arXiv desde eprint (+ archivePrefix), un campo arxiv, o una URL o «journal»
    que lo mencionen (Google Scholar exporta «arXiv preprint arXiv:2401.01234»)."""
    prefijo = sin_tildes(str(_campo(e, "archivePrefix", "eprinttype") or ""))
    eprint = _campo(e, "eprint")
    if eprint and (not prefijo or "arxiv" in prefijo):
        candidato = str(eprint)
    elif _campo(e, "arxiv"):
        candidato = str(_campo(e, "arxiv"))
    else:
        candidato = next((str(v) for v in (_campo(e, "journal"), _campo(e, "url"))
                          if v and "arxiv" in str(v).lower()), None)
    if not candidato:
        return None
    m = re.search(r"(\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})", candidato)
    try:
        return productos.normalizar_arxiv(m.group(1)) if m else None
    except ValueError:
        return None


def _anio(e):
    texto = str(_campo(e, "year") or _campo(e, "date") or "")
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", texto)
    return m.group(1) if m else ""


_MESES_BIB = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
                                          "oct", "nov", "dec"), start=1)}


def _mes(e):
    """Campo month (jan, January, 3, «mar.») o la fecha ISO de date; "" si no hay."""
    texto = str(_campo(e, "month") or "").strip().lower()
    if texto.isdigit() and 1 <= int(texto) <= 12:
        return str(int(texto))
    if texto[:3] in _MESES_BIB:
        return str(_MESES_BIB[texto[:3]])
    m = re.match(r"\d{4}-(\d{2})", str(_campo(e, "date") or ""))
    return str(int(m.group(1))) if m and 1 <= int(m.group(1)) <= 12 else ""


def _a_producto(e) -> dict:
    tipo_bib = e.entry_type.lower()
    avisos = []
    arxiv = _arxiv(e)
    nombre_tipo = TIPOS.get(tipo_bib)
    if tipo_bib == "misc":
        nombre_tipo = "Preprint" if arxiv else None
    if nombre_tipo is None:
        return {"clave": e.key, "tipo_bib": tipo_bib, "autores": _autores(e),
                "datos": {"titulo": _campo(e, "title") or "", "anio": _anio(e)},  # solo para mostrar
                "errores": [f"Tipo @{tipo_bib} sin equivalente en el sistema: regístrelo a mano."], "avisos": []}
    tipo = get_db().q("SELECT id, admite_revision FROM tipo_producto WHERE nombre = ?", [nombre_tipo])[0]
    if tipo_bib == "article" and arxiv and not _campo(e, "doi") and "arxiv" in sin_tildes(str(_campo(e, "journal") or "")):
        tipo = get_db().q("SELECT id, admite_revision FROM tipo_producto WHERE nombre = 'Preprint'")[0]
    medio = _campo(e, "journal", "booktitle", "publisher", "institution", "school", "howpublished")
    doi = _campo(e, "doi")
    # Artículos: revista del catálogo por ISSN o título (sin crearla: se vincula después si falta).
    revista = revistas.coincidir([_campo(e, "issn")], medio) if nombre_tipo == revistas.TIPO_ARTICULO else None
    datos = {
        "tipo_id": str(tipo["id"]), "titulo": _campo(e, "title") or "", "anio": _anio(e), "mes": _mes(e),
        "revista_id": revista["id"] if revista else None,
        "estado_publicacion": _estado(e, tipo_bib),
        "revision": "arbitrado" if tipo["admite_revision"] else "sin_arbitraje",
        "medio": medio, "volumen": _campo(e, "volume"), "numero": _campo(e, "number", "issue"),
        "paginas": (str(_campo(e, "pages") or "").replace("--", "–") or None),
        "doi": doi, "arxiv_id": arxiv, "url": _campo(e, "url"), "resumen": _campo(e, "abstract"),
        "actividad_id": None,
    }
    if tipo["admite_revision"]:
        avisos.append("Se importa como arbitrado: si es indexado, indíquelo luego con sus índices.")
    return {"clave": e.key, "tipo_bib": tipo_bib, "datos": datos, "autores": _autores(e), "errores": [],
            "avisos": avisos}


def _mismo_titulo(titulo: str, anio: str) -> dict | None:
    if not titulo or not anio.isdigit():
        return None
    normal = re.sub(r"[^a-z0-9]", "", sin_tildes(titulo))
    for f in get_db().q("SELECT id, titulo FROM producto WHERE anio = ?", [int(anio)]):
        if re.sub(r"[^a-z0-9]", "", sin_tildes(f["titulo"])) == normal:
            return productos.obtener(f["id"])
    return None


def leer(texto: str) -> tuple[list[dict], list[str]]:
    """→ (entradas clasificadas, errores generales). Cada entrada: clave, tipo_bib, datos (para
    productos.preparar), autores, estado ('nueva' | 'duplicada' | 'error'), errores, avisos y,
    si está duplicada, `existente` (el producto ya registrado)."""
    if len(texto.encode()) > MAX_BYTES:
        return [], ["El archivo supera 2 MB."]
    registro = logging.getLogger("bibtexparser")
    nivel = registro.level
    registro.setLevel(logging.ERROR + 10)  # los errores de sintaxis se informan al usuario, no en el log
    try:
        biblioteca = bibtexparser.parse_string(texto, append_middleware=[
            mw.LatexDecodingMiddleware(), mw.SeparateCoAuthors(), mw.SplitNameParts()])
    finally:
        registro.setLevel(nivel)
    generales = []
    if biblioteca.failed_blocks:
        generales.append(f"{len(biblioteca.failed_blocks)} entrada(s) con errores de sintaxis no se pudieron "
                         "leer (p. ej. una llave sin cerrar): "
                         + ", ".join(b.raw.strip().split(",")[0][:40] for b in biblioteca.failed_blocks[:5]))
    if not biblioteca.entries:
        return [], generales or ["No se encontraron entradas BibTeX (@article{…}, @book{…}, …)."]
    if len(biblioteca.entries) > MAX_ENTRADAS:
        generales.append(f"Se procesan las primeras {MAX_ENTRADAS} entradas; divida el archivo.")

    entradas, claves = [], set()
    for e in biblioteca.entries[:MAX_ENTRADAS]:
        x = _a_producto(e)
        if e.key in claves:
            x["errores"].append("Clave repetida en el archivo.")
        claves.add(e.key)
        if not x["errores"]:
            refs = [personas.ref_nueva(a["nombres"], a["apellidos"], None) for a in x["autores"]]
            _, errores = productos.preparar(dict(x["datos"]), refs, [])
            ya = next((err for err in errores if err.startswith("Ya existe")), None)
            x["errores"] = [err for err in errores if not err.startswith("Ya existe")]
            d = x["datos"]
            try:
                doi = productos.normalizar_doi(d["doi"]) if d["doi"] else None
            except ValueError:
                doi = None
            x["existente"] = productos.existente(doi, d["arxiv_id"]) if ya else _mismo_titulo(d["titulo"], d["anio"])
        x["estado"] = "error" if x["errores"] else ("duplicada" if x.get("existente") else "nueva")
        entradas.append(x)
    return entradas, generales


def crear(entradas: list[dict], claves: set[str], usuario_id: int) -> list[int]:
    """Crea los productos de las entradas 'nuevas' cuyas claves se eligieron."""
    creados = []
    for x in entradas:
        if x["estado"] != "nueva" or x["clave"] not in claves:
            continue
        refs, _ = importacion.resolver_autores(x["autores"])
        d, errores = productos.preparar(dict(x["datos"]), refs, [])
        if errores:  # p. ej. otro usuario lo registró entre la vista previa y la confirmación
            continue
        refs = [personas.materializar(r, usuario_id) for r in refs]
        creados.append(productos.guardar(d, refs, usuario_id))
    return creados


# --- Exportación ------------------------------------------------------------------------------------

def _escapar(texto: str) -> str:
    """Escapa & % # fuera de las fórmulas $…$ (dentro de ellas se dejan tal cual)."""
    partes = re.split(r"(\$[^$]*\$)", texto)
    return "".join(p if p.startswith("$") and p.endswith("$") and len(p) > 1
                   else re.sub(r"(?<!\\)([&%#])", r"\\\1", p) for p in partes)


def _clave(p: dict, usadas: set[str]) -> str:
    base = re.sub(r"[^A-Za-z]", "", sin_tildes(p["autores"][0]["apellidos"]).title()) if p["autores"] else "Anon"
    base = f"{base or 'Anon'}{p['anio']}"
    clave, sufijo = base, 0
    while clave in usadas:
        clave = base + "abcdefghijklmnopqrstuvwxyz"[sufijo % 26] * (sufijo // 26 + 1)
        sufijo += 1
    usadas.add(clave)
    return clave


def entrada(p: dict, usadas: set[str]) -> str:
    tipo_bib, campo_medio = TIPOS_EXPORTAR.get(p["tipo"], ("misc", "howpublished"))
    campos = [("author", " and ".join(f"{a['apellidos']}, {a['nombres']}" if a["nombres"] else a["apellidos"]
                                      for a in p["autores"])),
              ("title", p["titulo"]),
              (campo_medio, p["medio"]),
              ("year", str(p["anio"])), ("month", str(p["mes"]) if p.get("mes") else None),
              ("volume", p["volumen"]), ("number", p["numero"]),
              ("pages", (p["paginas"] or "").replace("–", "--") or None),
              ("doi", p["doi"]),
              ("issn", (p.get("revista") or {}).get("issn") or (p.get("revista") or {}).get("eissn"))]
    if p["arxiv_id"]:
        campos += [("eprint", p["arxiv_id"]), ("archiveprefix", "arXiv")]
    campos += [("url", p["url"]), ("note", NOTAS_ESTADO.get(p["estado_publicacion"]))]
    if p["tipo"] in ("Presentación", "Software", "Tesis dirigida"):
        campos.append(("type", p["tipo"]))
    def valor(k, v):
        if k in ("doi", "url", "eprint"):
            return f"{{{v}}}"
        # Título con doble llave: conserva las mayúsculas tal como están (nombres propios,
        # sustantivos en alemán…) aunque el estilo bibliográfico pase los títulos a minúsculas.
        return f"{{{{{_escapar(str(v))}}}}}" if k == "title" else f"{{{_escapar(str(v))}}}"
    lineas = [f"  {k} = {valor(k, v)}," for k, v in campos if v]
    return f"@{tipo_bib}{{{_clave(p, usadas)},\n" + "\n".join(lineas) + "\n}\n"


def exportar(lista: list[dict]) -> str:
    usadas: set[str] = set()
    cabecera = (f"% Exportado de {config.NOMBRE_COMPLETO}. Codificación UTF-8.\n"
                f"% {len(lista)} entrada(s).\n\n")
    return cabecera + "\n".join(entrada(p, usadas) for p in lista)
