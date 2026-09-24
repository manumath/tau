"""Normalización, validación y enlaces de los identificadores de autor.

Cada `normalizar_*` acepta el identificador o la URL de su perfil y devuelve la forma
canónica que se guarda, o lanza ValueError con un mensaje para el usuario.
"""
import re
from urllib.parse import parse_qs, urlparse


def _sin_prefijo(valor: str, *patrones: str) -> str:
    v = valor.strip()
    for p in patrones:
        v = re.sub(p, "", v, flags=re.IGNORECASE)
    return v.strip().strip("/")


def digito_control_orcid(base15: str) -> str:
    """Dígito verificador ISO 7064 MOD 11-2 de los primeros 15 dígitos."""
    total = 0
    for d in base15:
        total = (total + int(d)) * 2
    resultado = (12 - total % 11) % 11
    return "X" if resultado == 10 else str(resultado)


def normalizar_orcid(valor: str) -> str:
    v = _sin_prefijo(valor, r"^https?://", r"^(www\.)?orcid\.org/").upper().replace(" ", "")
    digitos = v.replace("-", "")
    if not re.fullmatch(r"\d{15}[\dX]", digitos):
        raise ValueError("El ORCID tiene la forma 0000-0002-1825-0097.")
    if digito_control_orcid(digitos[:15]) != digitos[15]:
        raise ValueError("El ORCID no es válido (falla el dígito verificador). Revise si hay un error de tipeo.")
    return "-".join(digitos[i:i + 4] for i in range(0, 16, 4))


def normalizar_mr(valor: str) -> str:
    v = valor.strip()
    if m := re.search(r"MRAuthorID/(\d+)", v, re.IGNORECASE) or re.search(r"[?&]mrauthid=(\d+)", v, re.I):
        return m.group(1)
    v = re.sub(r"^MR\s*", "", v, flags=re.IGNORECASE)
    if not re.fullmatch(r"\d{1,8}", v):
        raise ValueError("El MR Author ID es un número (lo encuentra en su perfil de MathSciNet).")
    return v


def normalizar_zbmath(valor: str) -> str:
    v = valor.strip()
    if "zbmath.org" in v.lower():
        u = urlparse(v if "://" in v else f"https://{v}")
        q = parse_qs(u.query).get("q", [""])[0]
        v = q.removeprefix("ai:") if q else u.path.rstrip("/").split("/")[-1]
    v = v.removeprefix("ai:").strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9'\-]*\.[a-z0-9'\-.]+", v):
        raise ValueError("El identificador de zbMATH tiene la forma apellido.nombre (p. ej. noether.emmy).")
    return v


def normalizar_arxiv(valor: str) -> str:
    v = _sin_prefijo(valor, r"^https?://", r"^(www\.)?arxiv\.org/a/").lower()
    v = re.sub(r"\.(html|atom|json)$", "", v)
    if not re.fullmatch(r"[a-z][a-z'\-]*_[a-z]_\d+", v):
        raise ValueError("El identificador de autor de arXiv tiene la forma apellido_i_1 (p. ej. turing_a_1).")
    return v


def normalizar_scholar(valor: str) -> str:
    v = valor.strip()
    u = urlparse(v if "://" in v else f"https://{v}")
    usuario = parse_qs(u.query).get("user", [""])[0]
    if "scholar.google" in u.netloc and usuario:
        return f"https://scholar.google.com/citations?user={usuario}"
    if re.fullmatch(r"[\w-]{12}", v):
        return f"https://scholar.google.com/citations?user={v}"
    raise ValueError("Pegue la URL de su perfil de Google Scholar (contiene «user=…»).")


def normalizar_url(valor: str) -> str:
    v = valor.strip()
    if not re.match(r"^https?://", v, re.IGNORECASE):
        v = f"https://{v}"
    u = urlparse(v)
    if not u.netloc or "." not in u.netloc or " " in v:
        raise ValueError("Ingrese una dirección web válida (p. ej. https://www.instituto.cl/~usuario).")
    return v


# campo → (etiqueta, normalizador, función que arma el enlace, ejemplo)
IDENTIFICADORES = {
    "orcid": ("ORCID", normalizar_orcid, lambda v: f"https://orcid.org/{v}", "0000-0002-1825-0097"),
    "mr_id": ("MathSciNet (MR Author ID)", normalizar_mr,
              lambda v: f"https://mathscinet.ams.org/mathscinet/MRAuthorID/{v}", "123456"),
    "zbmath_id": ("zbMATH Open", normalizar_zbmath,
                  lambda v: f"https://zbmath.org/authors/{v}", "noether.emmy"),
    "arxiv_id": ("arXiv", normalizar_arxiv, lambda v: f"https://arxiv.org/a/{v}", "turing_a_1"),
    "scholar_url": ("Google Scholar", normalizar_scholar, lambda v: v,
                    "https://scholar.google.com/citations?user=…"),
    "pagina_web": ("Página web", normalizar_url, lambda v: v, "https://…"),
}


def normalizar_todos(datos: dict) -> tuple[dict, dict]:
    """Devuelve (valores normalizados, errores por campo). Vacío → None (se borra)."""
    valores, errores = {}, {}
    for campo, (_, normalizar, _, _) in IDENTIFICADORES.items():
        crudo = (datos.get(campo) or "").strip()
        if not crudo:
            valores[campo] = None
            continue
        try:
            valores[campo] = normalizar(crudo)
        except ValueError as e:
            valores[campo] = crudo
            errores[campo] = str(e)
    return valores, errores
