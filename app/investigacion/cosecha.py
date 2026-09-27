"""Carga de la producción de un investigador desde OpenAlex (por su ORCID) y actualización de citas.

Flujo: `candidatos` consulta OpenAlex y clasifica cada obra (nueva, ya registrada, descartada o que
no se importa); el investigador elige y `registrar` crea los productos. Los autores se reconocen
como en la importación por DOI (ORCID o nombre); el investigador se reconoce siempre por su ORCID.
La revista se busca en el catálogo por ISSN o título y, si no está, se agrega como pendiente. La
filiación IIMAT/UMSA se marca si la afiliación publicada la menciona.
"""
import re
from datetime import date

from app.investigacion import filiacion, importacion, openalex, perfiles, productos, revistas
from app.comun import personas
from app.comun.db import auditar, get_db, sin_tildes


def _normal(titulo: str) -> str:
    return re.sub(r"[^a-z0-9]", "", sin_tildes(titulo or ""))


def existente(c: dict) -> dict | None:
    """Producto ya registrado que corresponde a la obra: por id de OpenAlex, DOI, arXiv o título y año."""
    fila = get_db().q("SELECT id FROM producto WHERE openalex_id = ?", [c["openalex_id"]])
    if fila:
        return productos.obtener(fila[0]["id"])
    d = c["datos"]
    otro = productos.existente(d.get("doi"), d.get("arxiv_id"))
    if otro:
        return otro
    if d.get("anio"):
        for f in get_db().q("SELECT id, titulo FROM producto WHERE anio = ?", [d["anio"]]):
            if _normal(f["titulo"]) == _normal(d["titulo"]):
                return productos.obtener(f["id"])
    return None


def descartadas(uid: int) -> set[str]:
    return {f["openalex_id"] for f in get_db().q("SELECT openalex_id FROM cosecha_descartada WHERE usuario_id = ?", [uid])}


def candidatos(uid: int, desde: int, hasta: int) -> dict:
    """→ {orcid, total, lista, avisos}. Cada elemento de `lista`: la obra convertida más `estado`
    ('nueva' | 'registrada' | 'descartada' | 'no_aplica'), `existente` y `soy_autor`."""
    perfil = perfiles.obtener(uid)
    orcid = (perfil or {}).get("orcid")
    if not orcid:
        raise importacion.ErrorImportacion("Registre su ORCID en «Mi perfil» para buscar su producción en OpenAlex.")
    obras, total = openalex.obras_por_orcid(orcid, desde, hasta)
    ya = descartadas(uid)
    lista = []
    for w in obras:
        c = openalex.convertir(w)
        otro = existente(c)
        c["existente"] = {"id": otro["id"], "titulo": otro["titulo"]} if otro else None
        c["soy_autor"] = bool(otro and productos.es_autor(otro["id"], uid))
        c["estado"] = ("registrada" if otro else "no_aplica" if not c["tipo"]
                       else "descartada" if c["openalex_id"] in ya else "nueva")
        lista.append(c)
    avisos = []
    if total > len(obras):
        avisos.append(f"OpenAlex informa {total} obras en esos años; se muestran las {len(obras)} más recientes. "
                      "Acote los años para ver las demás.")
    if total > 40 * (hasta - desde + 1):  # más de 40 obras por año es inusual para una sola persona
        avisos.append("Son muchas obras para una sola persona: revise que el ORCID de su perfil sea el suyo (algunos "
                      "ORCID de ejemplo los usan muchas personas y OpenAlex les atribuye obras ajenas).")
    return {"orcid": orcid, "total": total, "lista": lista, "avisos": avisos}


def _revista(c: dict, uid: int) -> int | None:
    """Revista del catálogo del artículo; si no está, se agrega como pendiente de verificar."""
    medio = c["datos"].get("medio")
    r = revistas.coincidir(c["issns"], medio)
    if r:
        return r["id"]
    if not medio:
        return None
    issns = []
    for i in c["issns"]:
        try:
            issns.append(revistas.normalizar_issn(i))
        except ValueError:
            pass
    datos, errores = revistas.validar({"titulo": medio, "issn": issns[0] if issns else None,
                                       "eissn": issns[1] if len(issns) > 1 else None})
    if errores:
        datos, errores = revistas.validar({"titulo": medio})
    if errores:
        return None
    rid = revistas.crear(datos, uid)
    auditar(uid, "proponer_revista", "revista", rid, f"{medio} (OpenAlex)")
    return rid


def registrar(uid: int, seleccion: list[dict]) -> tuple[int, list[str]]:
    """Crea los productos elegidos. → (creados, mensajes de lo que no se pudo registrar)."""
    orcid = (perfiles.obtener(uid) or {}).get("orcid")
    creados, mensajes = 0, []
    for c in seleccion:
        titulo = c["datos"]["titulo"]
        if not c.get("tipo") or existente(c):
            continue
        # Autores: el investigador se reconoce por su ORCID; los demás, como en la importación por DOI.
        refs, resumen = importacion.resolver_autores(c["autores"])
        if len(refs) == len(c["autores"]):  # misma posición que en OpenAlex
            for i, a in enumerate(c["autores"]):
                if orcid and a.get("orcid") == orcid and f"i:{uid}" not in refs:
                    refs[i] = f"i:{uid}"
        if f"i:{uid}" not in refs:
            mensajes.append(f"«{titulo}»: no se encontró su nombre entre los autores; regístrelo a mano.")
            continue
        filiaciones = [resumen["filiacion"].get(r) for r in refs]
        propia = next((a for a, r in zip(c["autores"], refs) if r == f"i:{uid}"), None)
        if propia and filiacion.detecta(propia.get("afiliacion")):
            filiaciones[refs.index(f"i:{uid}")] = "1"
        tipo = c["tipo"]
        datos = {**c["datos"], "tipo_id": str(importacion._id_tipo(tipo)),
                 "anio": str(c["datos"]["anio"] or ""), "mes": str(c["datos"].get("mes") or "")}
        if tipo == revistas.TIPO_ARTICULO:
            datos["revista_id"] = _revista(c, uid)
        d, errores = productos.preparar(datos, refs, [])
        if errores:
            mensajes.append(f"«{titulo}»: " + " ".join(errores))
            continue
        refs = [personas.materializar(r, uid) for r in refs]
        pid = productos.guardar(d, refs, uid, filiaciones=filiaciones)
        get_db().execute("""UPDATE producto SET openalex_id = ?, citas = ?, citas_actualizadas = date('now', 'localtime')
                            WHERE id = ?""", [c["openalex_id"], c["citas"], pid])
        creados += 1
    if creados:
        auditar(uid, "cargar_openalex", "producto", None, f"{creados} producto(s)")
    return creados, mensajes


def descartar(uid: int, openalex_id: str, titulo: str | None = None):
    get_db().execute("""INSERT OR IGNORE INTO cosecha_descartada (usuario_id, openalex_id, titulo) VALUES (?, ?, ?)""",
                     [uid, openalex_id, titulo])


def restaurar(uid: int, openalex_id: str):
    get_db().execute("DELETE FROM cosecha_descartada WHERE usuario_id = ? AND openalex_id = ?", [uid, openalex_id])


def actualizar_citas() -> tuple[int, int]:
    """Consulta en OpenAlex las citas de todos los productos con DOI. → (consultados, actualizados)."""
    filas = get_db().q("SELECT id, doi FROM producto WHERE doi IS NOT NULL")
    if not filas:
        return 0, 0
    citas = openalex.citas_por_doi([f["doi"] for f in filas])
    actualizados = 0
    for f in filas:
        if f["doi"] in citas:
            n, oid = citas[f["doi"]]
            # El id de OpenAlex solo se fija si ningún otro producto lo tiene (evita choques del índice único).
            get_db().execute("""UPDATE producto SET citas = ?, citas_actualizadas = date('now', 'localtime'),
                                openalex_id = COALESCE(openalex_id, CASE WHEN NOT EXISTS
                                    (SELECT 1 FROM producto x WHERE x.openalex_id = ?) THEN ? END)
                                WHERE id = ?""", [n, oid, oid, f["id"]])
            actualizados += 1
    return len(filas), actualizados


def anios_por_omision() -> tuple[int, int]:
    """Los últimos 5 años (la ventana de evidencia de IAC-CINDA)."""
    hoy = date.today().year
    return hoy - 4, hoy
