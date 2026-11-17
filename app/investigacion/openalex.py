"""Consulta a OpenAlex (https://openalex.org): obras de un investigador por su ORCID y citas.

OpenAlex es abierto y gratuito; identifica al portal con el correo de contacto (`mailto`) y, si se
configura, con una clave. Sus atribuciones no son perfectas (p. ej., hay ORCID usados como relleno
por muchas personas): por eso nada se registra sin que el investigador lo confirme.
"""
import re

from app.comun import config, paises
from app.investigacion import productos
from app.investigacion.importacion import ErrorImportacion, _dividir_nombre, _get, _limpiar

CAMPOS = ("id,doi,title,publication_year,publication_date,type,primary_location,locations,authorships,"
          "cited_by_count,open_access,biblio,abstract_inverted_index")
LIMITE = 200  # obras por búsqueda (las más recientes)


def _params(extra: dict) -> dict:
    p = dict(extra)
    if config.CONTACTO:
        p["mailto"] = config.CONTACTO
    if config.OPENALEX_CLAVE:
        p["api_key"] = config.OPENALEX_CLAVE
    return p


def _consultar(ruta: str, params: dict) -> dict:
    r = _get(f"{config.OPENALEX_URL}{ruta}", _params(params))
    if r.status_code == 429:
        raise ErrorImportacion("OpenAlex limitó las consultas por ahora. Intente más tarde.")
    if r.status_code != 200:
        raise ErrorImportacion(f"OpenAlex respondió con un error ({r.status_code}). Intente más tarde.")
    return r.json()


def obras_por_orcid(orcid: str, desde: int, hasta: int) -> tuple[list[dict], int]:
    """→ (obras más recientes primero, hasta LIMITE; total que informa OpenAlex)."""
    datos = _consultar("/works", {"filter": f"author.orcid:{orcid},publication_year:{desde}-{hasta}",
                                  "sort": "publication_date:desc", "per-page": LIMITE, "select": CAMPOS})
    return datos.get("results", []), (datos.get("meta") or {}).get("count", 0)


def citas_por_doi(dois: list[str]) -> dict[str, tuple[int, str]]:
    """{doi: (citas, id OpenAlex)} para una lista de DOI (consultas de a 50)."""
    res = {}
    for i in range(0, len(dois), 50):
        lote = dois[i:i + 50]
        datos = _consultar("/works", {"filter": "doi:" + "|".join(lote), "per-page": 50,
                                      "select": "id,doi,cited_by_count"})
        for w in datos.get("results", []):
            if w.get("doi"):
                res[productos.normalizar_doi(w["doi"])] = (w.get("cited_by_count") or 0, _id(w))
    return res


# --- Conversión a un producto del portal ----------------------------------------------------------

def _id(w) -> str:
    return (w.get("id") or "").rsplit("/", 1)[-1]


def _resumen(indice: dict | None) -> str | None:
    """OpenAlex entrega el resumen como índice invertido {palabra: [posiciones]}."""
    if not indice:
        return None
    posiciones = sorted((p, palabra) for palabra, ps in indice.items() for p in ps)
    return _limpiar(" ".join(palabra for _, palabra in posiciones))


def _mes(fecha: str) -> int | None:
    """'2024-03-15' → 3. OpenAlex pone el 1 de enero cuando solo conoce el año: se toma como
    mes desconocido."""
    if len(fecha) < 10 or fecha[5:] == "01-01":
        return None
    return int(fecha[5:7])


def _arxiv(w) -> str | None:
    for loc in w.get("locations") or []:
        m = re.search(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:v\d+)?(?:\.pdf)?$", loc.get("landing_page_url") or "")
        if m:
            try:
                return productos.normalizar_arxiv(m.group(1))
            except ValueError:
                pass
    return None


# tipo de OpenAlex (y de la fuente) → tipo del portal; None = no se importa (con el motivo).
NO_SE_IMPORTA = {"dissertation": "tesis propia (no hay un tipo para ella)", "dataset": "conjunto de datos",
                 "erratum": "fe de erratas", "paratext": "material complementario", "peer-review": "revisión de pares",
                 "retraction": "retractación", "other": "tipo no reconocido"}


def tipo_portal(w) -> tuple[str | None, str | None]:
    """→ (tipo del portal, motivo si no se importa)."""
    t = w.get("type") or "other"
    fuente = ((w.get("primary_location") or {}).get("source") or {}).get("type")
    if t in NO_SE_IMPORTA:
        return None, NO_SE_IMPORTA[t]
    if t == "preprint" or fuente == "repository":
        return "Preprint", None
    if t == "book":
        return "Libro", None
    if t in ("book-chapter", "reference-entry"):
        return "Capítulo de libro", None
    if t == "report":
        return "Reporte de investigación", None
    if fuente == "conference":
        return "Artículo en actas de congreso", None
    return "Artículo en revista", None


def convertir(w: dict) -> dict:
    """Obra de OpenAlex → {openalex_id, tipo, motivo, datos (para productos.preparar), autores,
    issns, citas, acceso_abierto}."""
    tipo, motivo = tipo_portal(w)
    fuente = (w.get("primary_location") or {}).get("source") or {}
    medio = fuente.get("display_name")
    if medio and "arxiv" in medio.lower():
        medio = "arXiv"
    fecha = w.get("publication_date") or ""
    b = w.get("biblio") or {}
    paginas = "–".join(x for x in (b.get("first_page"), b.get("last_page")) if x) or None
    autores = []
    for a in w.get("authorships") or []:
        nombres, apellidos = _dividir_nombre((a.get("author") or {}).get("display_name") or a.get("raw_author_name") or "")
        afiliaciones = list(a.get("raw_affiliation_strings") or []) + [i.get("display_name") for i in a.get("institutions") or []]
        codigos = list(a.get("countries") or []) + [i.get("country_code") for i in a.get("institutions") or []]
        autores.append({"nombres": nombres, "apellidos": apellidos,
                        "orcid": ((a.get("author") or {}).get("orcid") or "").rsplit("/", 1)[-1] or None,
                        "afiliacion": "; ".join(x for x in afiliaciones if x) or None,
                        "pais": next((paises.por_codigo(c) for c in codigos if paises.por_codigo(c)), None)})
    try:
        doi = productos.normalizar_doi(w["doi"]) if w.get("doi") else None
    except ValueError:
        doi = None
    return {
        "openalex_id": _id(w), "tipo": tipo, "motivo": motivo,
        "datos": {"titulo": _limpiar(w.get("title")) or "(sin título)", "anio": w.get("publication_year"),
                  "mes": _mes(fecha),
                  "estado_publicacion": "publicado", "revision": "sin_arbitraje" if tipo == "Preprint" else "arbitrado",
                  "medio": medio, "volumen": b.get("volume"), "numero": b.get("issue"), "paginas": paginas,
                  "doi": doi, "arxiv_id": _arxiv(w), "url": None, "resumen": _resumen(w.get("abstract_inverted_index"))},
        "autores": autores, "issns": list(fuente.get("issn") or []) or ([fuente["issn_l"]] if fuente.get("issn_l") else []),
        "citas": w.get("cited_by_count") or 0, "acceso_abierto": (w.get("open_access") or {}).get("is_oa"),
    }
