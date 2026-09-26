"""Importación de productos desde Crossref (por DOI) y arXiv (por identificador).

`importar(texto)` detecta el tipo de identificador (acepta también URLs), consulta la fuente y
devuelve un dict con los datos listos para el formulario de producto, los autores tal como
vienen en la fuente y avisos para el usuario. No guarda nada: el investigador revisa y confirma.

`resolver_autores` convierte los autores importados en referencias del selector: reconoce a
los investigadores del instituto (por ORCID o por nombre), reutiliza externos ya registrados y
deja los demás como referencias provisionales 'n:' que se registran al guardar.
"""
import html
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote

import httpx2

from app import config, paises, personas, productos, revistas
from app.db import get_db, sin_tildes

TIMEOUT = 10
CROSSREF = "https://api.crossref.org/works/"
ARXIV = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom",
      "os": "http://a9.com/-/spec/opensearch/1.1/"}
# Tipo de Crossref → tipo de producto del portal.
TIPOS_CROSSREF = {
    "journal-article": "Artículo en revista", "proceedings-article": "Artículo en actas de congreso",
    "book": "Libro", "monograph": "Libro", "edited-book": "Libro", "reference-book": "Libro",
    "book-chapter": "Capítulo de libro", "book-section": "Capítulo de libro", "book-part": "Capítulo de libro",
    "posted-content": "Preprint", "report": "Reporte de investigación",
}


class ErrorImportacion(Exception):
    """Error con un mensaje apto para mostrar al usuario."""


# --- Detección del identificador ---------------------------------------------------------------

def detectar(texto: str) -> tuple[str, str]:
    """→ ('doi', '10.xxxx/…') o ('arxiv', '2401.01234'). Los DOI de arXiv (10.48550/arXiv.…)
    se tratan como arXiv, que trae más información (resumen, versión)."""
    t = texto.strip()
    if not t:
        raise ErrorImportacion("Pegue un DOI o un identificador de arXiv.")
    if m := re.search(r"10\.48550/arxiv\.(.+)$", t, re.I):
        t = m.group(1)
    try:
        return "arxiv", productos.normalizar_arxiv(t)
    except ValueError:
        pass
    try:
        return "doi", productos.normalizar_doi(t)
    except ValueError:
        raise ErrorImportacion("No reconozco el identificador. Use un DOI (10.1234/abcd, o la URL "
                               "https://doi.org/…) o un arXiv (2401.01234, o la URL de arxiv.org).")


# --- Acceso HTTP (aislado para poder simularlo en los tests) --------------------------------------

def _get(url: str, params: dict | None = None) -> httpx2.Response:
    agente = "PortalInvestigacion/1.0" + (f" (mailto:{config.CONTACTO})" if config.CONTACTO else "")
    try:
        return httpx2.get(url, params=params, timeout=TIMEOUT, follow_redirects=True,
                          headers={"User-Agent": agente})
    except httpx2.TimeoutException:
        raise ErrorImportacion("El servicio tardó demasiado en responder. Intente de nuevo en un momento.")
    except httpx2.HTTPError:
        raise ErrorImportacion("No se pudo conectar con el servicio. Revise la conexión e intente de nuevo.")


# --- Utilidades de texto ---------------------------------------------------------------------------

def _limpiar(texto: str | None) -> str | None:
    """Quita etiquetas (JATS/HTML/MathML), decodifica entidades y normaliza espacios."""
    if not texto:
        return None
    t = re.sub(r"<[^>]+>", " ", texto)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"^(Abstract|Resumen)[.:]?\s+", "", t, flags=re.I) or None


def _id_tipo(nombre: str) -> int:
    filas = get_db().q("SELECT id FROM tipo_producto WHERE nombre = ?", [nombre])
    return filas[0]["id"] if filas else productos.tipos()[0]["id"]


def _dividir_nombre(completo: str) -> tuple[str, str]:
    """'Ashish Vaswani' → ('Ashish', 'Vaswani'). Las partículas (van, de, von…) van al apellido."""
    partes = completo.split()
    if len(partes) == 1:
        return "", partes[0]
    corte = len(partes) - 1
    while corte > 1 and partes[corte - 1].lower() in {"van", "von", "der", "de", "del", "la", "da", "di", "le"}:
        corte -= 1
    return " ".join(partes[:corte]), " ".join(partes[corte:])


# --- Crossref ----------------------------------------------------------------------------------------

def desde_crossref(doi: str) -> dict:
    r = _get(CROSSREF + quote(doi, safe="/"))
    if r.status_code == 404:
        raise ErrorImportacion(f"Crossref no tiene registro del DOI {doi}. Revise que esté bien escrito "
                               "(algunos DOI, como los de DataCite, no están en Crossref).")
    if r.status_code != 200:
        raise ErrorImportacion(f"Crossref respondió con un error ({r.status_code}). Intente más tarde.")
    m = r.json()["message"]
    tipo = TIPOS_CROSSREF.get(m.get("type"), "Artículo en revista")
    anio = mes = None
    for clave in ("published-print", "published-online", "issued", "published"):
        partes = (m.get(clave) or {}).get("date-parts") or [[None]]
        if partes[0] and partes[0][0]:
            anio = partes[0][0]
            mes = partes[0][1] if len(partes[0]) > 1 and 1 <= (partes[0][1] or 0) <= 12 else None
            break
    autores = []
    for a in m.get("author", []):
        if a.get("family"):
            autores.append({"nombres": a.get("given") or "", "apellidos": a["family"],
                            "orcid": (a.get("ORCID") or "").rsplit("/", 1)[-1] or None,
                            "afiliacion": ((a.get("affiliation") or [{}])[0] or {}).get("name")})
        elif a.get("name"):  # autoría institucional
            autores.append({"nombres": "", "apellidos": a["name"], "orcid": None, "afiliacion": None})
    medio = (m.get("container-title") or [None])[0]
    if tipo == "Libro" and not medio:
        medio = m.get("publisher")
    avisos, revista = [], {}
    if tipo == "Artículo en revista":
        # La revista se reconoce en el catálogo por ISSN (impreso o electrónico) o por el título.
        issns = {x.get("type"): x.get("value") for x in m.get("issn-type") or []}
        encontrada = revistas.coincidir([issns.get("print"), issns.get("electronic"), *(m.get("ISSN") or [])],
                                        _limpiar(medio))
        if encontrada:
            revista = {"revista_id": encontrada["id"]}
            avisos.append(f"Revista reconocida en el catálogo: «{encontrada['titulo']}»"
                          + (" (verificada: la clasificación se toma del catálogo)." if encontrada["estado"] == "verificada"
                             else " (pendiente de verificar: indique el nivel de revisión y los índices)."))
        else:
            revista = {"revista_nueva_titulo": _limpiar(medio), "revista_nueva_issn": issns.get("print"),
                       "revista_nueva_eissn": issns.get("electronic")}
            avisos.append("La revista no está en el catálogo: se propondrá al guardar. Indique el nivel de "
                          "revisión y los índices (Crossref no informa si está indexada).")
    elif tipo in ("Artículo en actas de congreso", "Capítulo de libro", "Libro"):
        avisos.append("Crossref no informa si la publicación está indexada: indique el nivel de revisión y "
                      "los índices antes de guardar.")
    return {
        "fuente": "Crossref",
        "datos": {
            "tipo_id": _id_tipo(tipo), "titulo": _limpiar((m.get("title") or [""])[0]),
            "anio": anio, "mes": mes, "estado_publicacion": "publicado",
            "revision": "arbitrado" if tipo != "Preprint" else "sin_arbitraje",
            "medio": _limpiar(medio), "volumen": m.get("volume"), "numero": m.get("issue"),
            "paginas": (m.get("page") or "").replace("-", "–") or None,
            "doi": doi, "arxiv_id": None, "url": None, "resumen": _limpiar(m.get("abstract")),
            **revista,
        },
        "autores": autores, "avisos": avisos, "doi_publicado": None,
    }


# --- arXiv -----------------------------------------------------------------------------------------------

# arXiv pide no más de una consulta cada 3 s y responde 406/429/503 cuando se excede.
ARXIV_LIMITADO = {406, 429, 503}
ARXIV_ESPERA = 3


def desde_arxiv(arxiv_id: str) -> dict:
    params = {"id_list": arxiv_id, "max_results": 1}
    r = _get(ARXIV, params)
    if r.status_code in ARXIV_LIMITADO:
        time.sleep(ARXIV_ESPERA)  # un reintento; más sería hacer esperar demasiado al usuario
        r = _get(ARXIV, params)
    if r.status_code in ARXIV_LIMITADO:
        raise ErrorImportacion("arXiv está limitando las consultas en este momento. Espere unos "
                               "segundos e intente de nuevo.")
    if r.status_code != 200:
        raise ErrorImportacion(f"arXiv respondió con un error ({r.status_code}). Intente más tarde.")
    try:
        raiz = ET.fromstring(r.content)
    except ET.ParseError:
        raise ErrorImportacion("arXiv devolvió una respuesta que no se pudo leer.")
    entrada = raiz.find("a:entry", NS)
    if entrada is None or "api/errors" in (entrada.findtext("a:id", "", NS)) \
            or not entrada.findtext("a:title", "", NS).strip():
        raise ErrorImportacion(f"arXiv no tiene el artículo {arxiv_id}. Revise el identificador.")

    def texto(ruta):
        return re.sub(r"\s+", " ", entrada.findtext(ruta, "", NS)).strip() or None

    autores = []
    for a in entrada.findall("a:author", NS):
        nombres, apellidos = _dividir_nombre(a.findtext("a:name", "", NS).strip())
        autores.append({"nombres": nombres, "apellidos": apellidos, "orcid": None,
                        "afiliacion": a.findtext("arxiv:affiliation", None, NS)})
    doi = texto("arxiv:doi")
    referencia = texto("arxiv:journal_ref")
    avisos = []
    if doi or referencia:
        avisos.append("Este preprint ya tiene versión publicada"
                      + (f" ({referencia})" if referencia else "") + ". Si corresponde, importe esa "
                      "versión por DOI: quedará como artículo, con el arXiv asociado.")
    return {
        "fuente": "arXiv",
        "datos": {
            "tipo_id": _id_tipo("Preprint"), "titulo": texto("a:title"),
            "anio": int((texto("a:published") or "0000")[:4]) or None,
            "mes": int((texto("a:published") or "0000-00")[5:7] or 0) or None,
            "estado_publicacion": "publicado", "revision": "sin_arbitraje",
            "medio": "arXiv" + (f" [{c}]" if (c := entrada.find("arxiv:primary_category", NS)) is not None
                                and (c := c.get("term")) else ""),
            "volumen": None, "numero": None, "paginas": None, "doi": None, "arxiv_id": arxiv_id,
            "url": None, "resumen": texto("a:summary"),
        },
        "autores": autores, "avisos": avisos, "doi_publicado": doi,
    }


def importar(texto: str, arxiv_asociado: str | None = None) -> dict:
    """Consulta la fuente que corresponda. `arxiv_asociado` se agrega a lo importado por DOI
    (caso «importar la versión publicada de este preprint»)."""
    tipo, ident = detectar(texto)
    res = desde_arxiv(ident) if tipo == "arxiv" else desde_crossref(ident)
    if arxiv_asociado and tipo == "doi":
        res["datos"]["arxiv_id"] = productos.normalizar_arxiv(arxiv_asociado)
    if not res["datos"]["titulo"]:
        raise ErrorImportacion("El registro encontrado no tiene título; ingréselo a mano.")
    return res


# --- Autores ----------------------------------------------------------------------------------------------

def _investigadores():
    return get_db().q("""SELECT u.id, u.nombres, u.apellidos, i.orcid FROM usuario u
                         JOIN investigador i ON i.usuario_id = u.id WHERE u.activo = 1""")


def _coincide(autor: dict, inv: dict) -> bool:
    """Mismo apellido (completo o el primero de los dos) y misma inicial del nombre."""
    fam = sin_tildes(autor["apellidos"]).replace("-", " ").strip()
    apellidos = sin_tildes(inv["apellidos"]).replace("-", " ").strip()
    if fam not in (apellidos, apellidos.split()[0] if apellidos else ""):
        return False
    ini_a = sin_tildes(autor["nombres"])[:1]
    return not ini_a or ini_a == sin_tildes(inv["nombres"])[:1]


def resolver_autores(autores: list[dict]) -> tuple[list[str], dict]:
    """→ (referencias en orden, resumen {'internos': [...], 'existentes': [...], 'nuevos': [...],
    'filiacion': {ref: '1'}}). 'filiacion' marca a los autores del instituto cuya afiliación
    publicada menciona al instituto o a la UMSA (ver app.filiacion.detecta)."""
    from app.filiacion import detecta
    investigadores = _investigadores()
    refs, resumen = [], {"internos": [], "existentes": [], "nuevos": [], "filiacion": {}}
    for a in autores:
        nombre = f"{a['nombres']} {a['apellidos']}".strip()
        por_orcid = [i for i in investigadores if a.get("orcid") and i["orcid"] == a["orcid"]]
        por_nombre = [i for i in investigadores if _coincide(a, i)]
        candidato = por_orcid or (por_nombre if len(por_nombre) == 1 else [])
        if candidato:
            r = f"i:{candidato[0]['id']}"
            if r not in refs:
                refs.append(r)
                resumen["internos"].append(nombre)
                if detecta(a.get("afiliacion")):
                    resumen["filiacion"][r] = "1"
            continue
        existente = personas.externo_similar(a["nombres"] or "", a["apellidos"])
        if existente:
            personas.completar_pais(existente, a.get("pais") or paises.desde_texto(a.get("afiliacion")))
            resumen["existentes"].append(nombre)
            refs.append(f"e:{existente['id']}")
        else:
            # Se registrará al guardar el producto (ver personas.materializar).
            resumen["nuevos"].append(nombre)
            refs.append(personas.ref_nueva(a["nombres"], a["apellidos"], a.get("afiliacion"),
                                           a.get("pais") or paises.desde_texto(a.get("afiliacion"))))
    return refs, resumen
