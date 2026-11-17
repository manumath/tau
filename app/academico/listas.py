"""Lista de estudiantes por paralelo (PLAN §68, etapa 4).

La lista oficial la genera el sistema de notas (Kardex). Esta capa tiene **dos proveedores** con la misma salida, para que las
pantallas no cambien cuando exista la API:
- **csv** (hoy): la Dirección de Carrera o la Coordinación cargan el CSV de Kardex; queda en `lista_curso` como copia temporal, que
  se retira al concluir la gestión.
- **api** (mañana): con `TAU_LISTAS_URL` se consulta en el momento, con la clave `TAU_LISTAS_CLAVE`, y no se guarda nada.
  Contrato esperado: `GET {URL}/gestiones/{codigo}/cursos/{sigla}/{paralelo}/estudiantes` con `Authorization: Bearer …` y
  respuesta JSON `{"estudiantes": [{"ru", "apellidos", "nombres", "correo"}]}`.
Solo la ven los docentes (titular o auxiliar) de ese paralelo; cada consulta se audita. TAU no guarda notas ni asistencia."""
import json
import urllib.error
import urllib.parse
import urllib.request

from app.academico import gestiones, oferta
from app.comun import config
from app.comun.db import auditar, get_db, transaccion
from app.comun.importar_usuarios import leer_tabla

ALIAS = {"sigla": ("sigla", "codigo", "materia"), "paralelo": ("paralelo", "grupo"),
         "ru": ("ru", "registro", "registro universitario"), "apellidos": ("apellidos", "apellido"),
         "nombres": ("nombres", "nombre"), "correo": ("correo", "email", "correo electronico")}
PLANTILLA = ("sigla,paralelo,ru,apellidos,nombres,correo\n"
             "MAT-111,A,1111111,Apellido Uno,Nombre Uno,estudiante1@ejemplo.bo\n"
             "MAT-111,A,2222222,Apellido Dos,Nombre Dos,\n")
MAX_FILAS = 20000
MAX_ERRORES = 10


def usa_api() -> bool:
    return bool(config.LISTAS_URL)


def _pedir(url: str) -> bytes:
    """La única llamada de red; las pruebas la reemplazan. Falla con `OSError` o `ValueError`."""
    partes = urllib.parse.urlsplit(url)
    if partes.scheme != "https" and partes.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("La API de listas debe usar https.")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {config.LISTAS_CLAVE or ''}",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=config.LISTAS_TIEMPO_S) as r:     # noqa: S310 (esquema validado arriba)
        return r.read(5 * 1024 * 1024)


def _desde_api(g: dict, o: dict) -> dict:
    url = (f"{config.LISTAS_URL}/gestiones/{urllib.parse.quote(gestiones.codigo(g))}/cursos/"
           f"{urllib.parse.quote(o['sigla'])}/{urllib.parse.quote(o['paralelo'])}/estudiantes")
    try:
        datos = json.loads(_pedir(url))
        lista = [{"ru": str(e["ru"]), "apellidos": e["apellidos"], "nombres": e["nombres"], "correo": e.get("correo") or ""}
                 for e in datos["estudiantes"]]
    except (OSError, ValueError, KeyError, TypeError):      # sin red, respuesta ilegible o con otra forma: sin datos personales en el mensaje
        return {"origen": "api", "estudiantes": [], "cargada_en": None,
                "error": "El sistema de notas no respondió. Intente de nuevo en unos minutos."}
    return {"origen": "api", "estudiantes": sorted(lista, key=lambda e: (e["apellidos"], e["nombres"])), "cargada_en": None,
            "error": None}


def _desde_copia(oid: int) -> dict:
    filas = get_db().q("""SELECT ru, apellidos, nombres, correo, cargado_en FROM lista_curso WHERE oferta_id = ?
                          ORDER BY apellidos, nombres""", [oid])
    return {"origen": "csv", "estudiantes": filas, "cargada_en": max((f["cargado_en"] for f in filas), default=None),
            "error": None}


def lista(oid: int) -> dict | None:
    """{origen, estudiantes, cargada_en, error} del paralelo, por el proveedor que corresponda; None si no existe."""
    o = oferta.obtener(oid)
    g = gestiones.obtener(o["gestion_id"]) if o else None
    if not o or not g:
        return None
    return _desde_api(g, o) if usa_api() else _desde_copia(oid)


def puede_ver(uid: int, oid: int) -> bool:
    """Los docentes vigentes del paralelo (titular o auxiliar), en una gestión que no concluyó."""
    return bool(get_db().q(
        """SELECT 1 FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id JOIN gestion_academica g ON g.id = o.gestion_id
           WHERE d.usuario_id = ? AND o.id = ? AND d.hasta IS NULL AND o.retirada_en IS NULL AND g.estado <> 'concluida'""",
        [uid, oid]))


def cursos_de(uid: int) -> list[dict]:
    """Paralelos que la persona dicta en gestiones que no concluyeron, con cuántos estudiantes tiene la copia (si no hay API)."""
    filas = get_db().q(
        """SELECT o.id AS oferta_id, a.sigla, a.nombre, o.paralelo, d.rol, g.id AS gestion_id,
                  (SELECT COUNT(*) FROM lista_curso l WHERE l.oferta_id = o.id) AS cargados
           FROM oferta_docente d JOIN oferta o ON o.id = d.oferta_id JOIN asignatura a ON a.id = o.asignatura_id
           JOIN gestion_academica g ON g.id = o.gestion_id
           WHERE d.usuario_id = ? AND d.hasta IS NULL AND o.retirada_en IS NULL AND g.estado <> 'concluida'
           ORDER BY g.fecha_inicio, a.sigla, o.paralelo""", [uid])
    for f in filas:
        f["gestion"] = gestiones.codigo(gestiones.obtener(f["gestion_id"]))
    return filas


def consultar(uid: int, oid: int) -> dict | None:
    """La lista para su docente, con auditoría de la consulta. None si no puede verla."""
    if not puede_ver(uid, oid):
        return None
    r = lista(oid)
    if r:
        auditar(uid, "ver_lista_curso", "oferta", oid, f"{r['origen']}: {len(r['estudiantes'])} estudiantes")
    return r


def cargar(contenido: bytes, gid: int, uid: int) -> tuple[dict, list[str]]:
    """Carga el CSV de Kardex para una gestión (reemplaza la copia de cada paralelo que trae). Todo o nada por errores de
    fila; los paralelos que no están en la oferta se informan y se omiten. → (resumen, errores)."""
    g = gestiones.obtener(gid)
    if not g or g["estado"] == "concluida":
        return {}, ["Elija una gestión que no haya concluido."]
    if usa_api():
        return {}, ["Las listas se consultan al sistema de notas: no hace falta cargarlas."]
    filas, errores = leer_tabla(contenido, ALIAS, ("sigla", "ru", "apellidos", "nombres"), MAX_FILAS)
    if errores:
        return {}, errores
    por_curso = {(o["sigla"], o["paralelo"]): o["id"] for o in oferta.listar(gid)}
    nuevos: dict[int, dict[str, dict]] = {}
    omitidos: set[tuple[str, str]] = set()
    for linea, f in filas:
        clave = (f["sigla"].upper(), (f["paralelo"] or "A").upper())
        if not f["ru"] or not f["apellidos"] or not f["nombres"]:
            errores.append(f"Línea {linea}: faltan el RU, los apellidos o los nombres.")
        elif clave not in por_curso:
            omitidos.add(clave)
        else:
            nuevos.setdefault(por_curso[clave], {})[f["ru"]] = {**f, "correo": f["correo"] or None}
    if errores:
        return {}, errores[:MAX_ERRORES] + ([f"… y {len(errores) - MAX_ERRORES} más."] if len(errores) > MAX_ERRORES else [])
    with transaccion():
        for oid, estudiantes in nuevos.items():
            get_db().execute("DELETE FROM lista_curso WHERE oferta_id = ?", [oid])
            for e in estudiantes.values():
                get_db().execute("""INSERT INTO lista_curso (oferta_id, ru, apellidos, nombres, correo, cargado_por)
                                    VALUES (?, ?, ?, ?, ?, ?)""", [oid, e["ru"], e["apellidos"], e["nombres"], e["correo"], uid])
        total = sum(len(v) for v in nuevos.values())
        auditar(uid, "cargar_listas", "gestion_academica", gid,
                f"{gestiones.codigo(g)}: {total} estudiantes en {len(nuevos)} paralelo(s)")
    return {"paralelos": len(nuevos), "estudiantes": sum(len(v) for v in nuevos.values()),
            "omitidos": sorted(f"{s} {p}" for s, p in omitidos)}, []


def cargadas(gid: int) -> list[dict]:
    """Para quien carga: cada paralelo de la oferta con cuántos estudiantes tiene la copia (sin nombres)."""
    return get_db().q(
        """SELECT o.id AS oferta_id, a.sigla, a.nombre, o.paralelo, (SELECT COUNT(*) FROM lista_curso l WHERE l.oferta_id = o.id)
                  AS cargados, o.inscritos FROM oferta o JOIN asignatura a ON a.id = o.asignatura_id
           WHERE o.gestion_id = ? AND o.retirada_en IS NULL ORDER BY a.sigla, o.paralelo""", [gid])


def purgar(gid: int) -> int:
    """Retira las copias de la gestión (al concluir). → cuántas filas."""
    n = get_db().q("""SELECT COUNT(*) n FROM lista_curso WHERE oferta_id IN (SELECT id FROM oferta WHERE gestion_id = ?)""",
                   [gid])[0]["n"]
    get_db().execute("DELETE FROM lista_curso WHERE oferta_id IN (SELECT id FROM oferta WHERE gestion_id = ?)", [gid])
    return n


def ofertas_de_ru(gid: int, ru: str) -> list[int]:
    """Paralelos de la gestión en que el estudiante (por su RU) está inscrito según la lista de curso. Con la copia es una
    consulta; con la API, una llamada por paralelo (hasta que Kardex ofrezca una consulta por estudiante)."""
    if not ru:
        return []
    if usa_api():
        return [o["id"] for o in oferta.listar(gid) if any(e["ru"] == ru for e in lista(o["id"])["estudiantes"])]
    return [f["oferta_id"] for f in get_db().q(
        """SELECT l.oferta_id FROM lista_curso l JOIN oferta o ON o.id = l.oferta_id
           WHERE o.gestion_id = ? AND l.ru = ? AND o.retirada_en IS NULL""", [gid, ru])]
