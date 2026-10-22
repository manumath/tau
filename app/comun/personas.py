"""Personas que figuran como autores o participantes: investigadores del instituto y externos.

En formularios y datos se identifican con una referencia de texto: 'i:<usuario_id>' para
investigadores e 'e:<persona_externa_id>' para externos. Los externos que llegan de una
importación y aún no existen viajan como 'n:<datos codificados>' y se registran recién al
guardar (`materializar`), para no dejar personas huérfanas si se cancela el formulario.
"""
import base64
import json

from app.comun import adscripcion, paises
from app.comun.db import get_db, sin_tildes, transaccion


def ref(investigador_id=None, externo_id=None) -> str:
    return f"i:{investigador_id}" if investigador_id else f"e:{externo_id}"


def parsear_ref(texto: str) -> tuple[str, int] | None:
    """'i:3' → ('i', 3). None si el formato no es válido (las 'n:' no tienen id todavía)."""
    tipo, _, num = (texto or "").partition(":")
    if tipo in ("i", "e") and num.isdigit():
        return tipo, int(num)
    return None


def ref_nueva(nombres: str, apellidos: str, afiliacion: str | None, pais: str | None = None) -> str:
    datos = json.dumps({"n": nombres, "a": apellidos, "f": afiliacion, "p": pais}, ensure_ascii=False)
    return "n:" + base64.urlsafe_b64encode(datos.encode()).decode()


def _datos_nueva(r: str) -> dict | None:
    try:
        d = json.loads(base64.urlsafe_b64decode(r[2:].encode()).decode())
        return {"nombres": str(d["n"])[:100], "apellidos": str(d["a"])[:100],
                "afiliacion": (str(d["f"])[:200] if d.get("f") else None),
                "pais": (str(d["p"])[:80] if d.get("p") else None)}
    except (ValueError, KeyError, TypeError):
        return None


def materializar(r: str, creado_por: int) -> str:
    """'n:…' → 'e:<id>' (reutiliza un externo con el mismo nombre si ya existe). Las demás
    referencias se devuelven tal cual."""
    if not (r or "").startswith("n:") or not (d := _datos_nueva(r)) or not d["apellidos"]:
        return r
    existente = externo_similar(d["nombres"], d["apellidos"])
    if existente:
        completar_pais(existente, d.get("pais") or paises.desde_texto(d["afiliacion"]))
    else:
        existente = crear_externo(d["nombres"] or "—", d["apellidos"], d["afiliacion"], d.get("pais"), creado_por)
    return f"e:{existente['id']}"


def completar_pais(externo: dict, pais: str | None):
    """Si al externo le falta el país y ahora se conoce, se completa (nunca se sobrescribe)."""
    if pais and not externo.get("pais"):
        get_db().execute("UPDATE persona_externa SET pais = ? WHERE id = ? AND (pais IS NULL OR pais = '')",
                         [paises.normalizar(pais), externo["id"]])


def columnas(r: str) -> dict:
    """Referencia → columnas investigador_id / externo_id."""
    tipo, num = parsear_ref(r)
    return {"investigador_id": num if tipo == "i" else None,
            "externo_id": num if tipo == "e" else None}


def por_ref(r: str) -> dict | None:
    """Datos para mostrar una persona: nombre, afiliación y si es interna."""
    return por_refs([r]).get(r)


def por_refs(refs) -> dict[str, dict]:
    """Varias personas a la vez (ref → datos; las que no existen no aparecen): una consulta por clase de
    persona, y la unidad de cada investigador se calcula una sola vez aunque figure en muchos registros."""
    res, internos, externos = {}, set(), set()
    for r in dict.fromkeys(refs):
        if (r or "").startswith("n:"):
            d = _datos_nueva(r)
            if d:
                res[r] = {**d, "id": None, "ref": r, "interno": False, "nueva": True}
        elif (p := parsear_ref(r)):
            (internos if p[0] == "i" else externos).add(p[1])
    for lote in _lotes(sorted(internos)):
        for f in get_db().q(f"""SELECT u.id, u.nombres, u.apellidos FROM usuario u JOIN investigador i ON i.usuario_id = u.id
                                WHERE u.id IN ({','.join('?' * len(lote))})""", lote):
            f["afiliacion"] = adscripcion.unidad(f["id"])
            res[f"i:{f['id']}"] = {**f, "ref": f"i:{f['id']}", "interno": True}
    for lote in _lotes(sorted(externos)):
        for f in get_db().q(f"""SELECT id, nombres, apellidos, institucion AS afiliacion FROM persona_externa
                                WHERE id IN ({','.join('?' * len(lote))})""", lote):
            res[f"e:{f['id']}"] = {**f, "ref": f"e:{f['id']}", "interno": False}
    return res


def _lotes(ids, tam=500):
    """De a `tam` (SQLite limita la cantidad de parámetros de una consulta)."""
    return [ids[i:i + tam] for i in range(0, len(ids), tam)]


def buscar(texto: str, excluir: set[str] = frozenset(), limite: int = 8) -> list[dict]:
    """Investigadores (primero) y externos cuyo nombre coincide; excluye referencias dadas."""
    patron = f"%{sin_tildes(texto.strip())}%"
    if len(texto.strip()) < 2:
        return []
    internos = get_db().q(
        """SELECT u.id, u.nombres, u.apellidos FROM usuario u
           JOIN investigador i ON i.usuario_id = u.id
           WHERE u.activo = 1 AND (sin_tildes(u.nombres || ' ' || u.apellidos) LIKE :p
                                   OR sin_tildes(u.apellidos || ' ' || u.nombres) LIKE :p)
           ORDER BY sin_tildes(u.apellidos) LIMIT :l""", {"p": patron, "l": limite})
    externos = get_db().q(
        """SELECT id, nombres, apellidos, institucion AS afiliacion FROM persona_externa
           WHERE usuario_id IS NULL AND (sin_tildes(nombres || ' ' || apellidos) LIKE :p
                                         OR sin_tildes(apellidos || ' ' || nombres) LIKE :p)
           ORDER BY sin_tildes(apellidos) LIMIT :l""", {"p": patron, "l": limite})
    res = [{**p, "afiliacion": adscripcion.unidad(p["id"]), "ref": f"i:{p['id']}", "interno": True}
           for p in internos]
    res += [{**p, "ref": f"e:{p['id']}", "interno": False} for p in externos]
    return [p for p in res if p["ref"] not in excluir][:limite]


def crear_externo(nombres: str, apellidos: str, institucion: str | None, pais: str | None,
                  creado_por: int) -> dict:
    """El país se normaliza («USA» → «Estados Unidos») y, si falta, se deduce de la institución."""
    institucion = (institucion or "").strip() or None
    pais = paises.normalizar(pais) or paises.desde_texto(institucion)
    return get_db().t.persona_externa.insert(
        nombres=nombres.strip(), apellidos=apellidos.strip(), institucion=institucion, pais=pais,
        creado_por=creado_por)


def externo_similar(nombres: str, apellidos: str) -> dict | None:
    """Externo ya registrado con el mismo nombre (ignora tildes y mayúsculas)."""
    filas = get_db().q(
        """SELECT * FROM persona_externa WHERE sin_tildes(nombres) = sin_tildes(?)
           AND sin_tildes(apellidos) = sin_tildes(?) LIMIT 1""", [nombres.strip(), apellidos.strip()])
    return filas[0] if filas else None


def nombre_cita(p: dict) -> str:
    """'Emmy Noether' → 'Noether, E.'; 'Carl Friedrich' → 'Gauss, C. F.'"""
    iniciales = " ".join(f"{n[0]}." for n in p["nombres"].replace("-", " ").split() if n)
    return f"{p['apellidos']}, {iniciales}"


# --- Coautores externos: país e institución (internacionalización) -----------------------------------------------

def externos(texto: str = "", solo_sin_pais: bool = False) -> list[dict]:
    """Personas externas (sin cuenta) con cuántos productos, actividades y proyectos tienen."""
    patron = f"%{sin_tildes(texto.strip())}%"
    return get_db().q(
        """SELECT pe.*,
                  (SELECT COUNT(*) FROM producto_autor x WHERE x.externo_id = pe.id) AS n_productos,
                  (SELECT COUNT(*) FROM actividad_participante x WHERE x.externo_id = pe.id) AS n_actividades,
                  (SELECT COUNT(*) FROM proyecto_participante x WHERE x.externo_id = pe.id) AS n_proyectos
           FROM persona_externa pe WHERE pe.usuario_id IS NULL
             AND (:t = '' OR sin_tildes(pe.nombres || ' ' || pe.apellidos) LIKE :p
                  OR sin_tildes(pe.apellidos || ' ' || pe.nombres) LIKE :p OR sin_tildes(pe.institucion) LIKE :p)
             AND (:s = 0 OR pe.pais IS NULL OR pe.pais = '')
           ORDER BY (pe.pais IS NULL OR pe.pais = '') DESC, n_productos DESC, sin_tildes(pe.apellidos) LIMIT 300""",
        {"t": texto.strip(), "p": patron, "s": int(solo_sin_pais)})


def actualizar_externo(eid: int, institucion: str | None, pais: str | None):
    get_db().execute("UPDATE persona_externa SET institucion = ?, pais = ? WHERE id = ?",
                     [(institucion or "").strip() or None, paises.normalizar(pais), eid])


def completar_paises() -> tuple[int, int]:
    """Normaliza los países escritos («USA» → «Estados Unidos») y deduce los que faltan desde la
    institución. → (normalizados, deducidos)."""
    normalizados = deducidos = 0
    for e in get_db().q("SELECT id, institucion, pais FROM persona_externa"):
        if e["pais"]:
            nuevo = paises.normalizar(e["pais"])
            if nuevo != e["pais"]:
                get_db().execute("UPDATE persona_externa SET pais = ? WHERE id = ?", [nuevo, e["id"]])
                normalizados += 1
        elif (nuevo := paises.desde_texto(e["institucion"])):
            get_db().execute("UPDATE persona_externa SET pais = ? WHERE id = ?", [nuevo, e["id"]])
            deducidos += 1
    return normalizados, deducidos


# --- Externos duplicados: detección y fusión -----------------------------------------------------------

def _tokens(nombres: str) -> list[str]:
    return [t for t in sin_tildes(nombres or "").lower().replace("-", " ").replace(".", " ").split() if t]


def nombres_compatibles(a: str, b: str) -> bool:
    """«H.» y «Hermann», «Hermann» y «Hermann Klaus», «H. K.» y «Hermann Klaus» son compatibles;
    «Hermann» y «Hans», no. Se comparan los nombres en orden: iguales, o uno es la inicial del otro."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    for x, y in zip(ta, tb):
        if x == y or (len(x) == 1 and y.startswith(x)) or (len(y) == 1 and x.startswith(y)):
            continue
        return False
    return True


def _resumen_externo(eid: int) -> dict:
    fila = get_db().q(
        """SELECT pe.*,
                  (SELECT COUNT(*) FROM producto_autor x WHERE x.externo_id = pe.id) AS n_productos,
                  (SELECT COUNT(*) FROM actividad_participante x WHERE x.externo_id = pe.id) AS n_actividades,
                  (SELECT COUNT(*) FROM proyecto_participante x WHERE x.externo_id = pe.id) AS n_proyectos,
                  (SELECT COUNT(*) FROM estudiante x WHERE x.externo_id = pe.id) AS n_estudiante
           FROM persona_externa pe WHERE pe.id = ?""", [eid])
    return fila[0] if fila else None


def posibles_duplicados() -> list[dict]:
    """Pares de externos (sin cuenta) que podrían ser la misma persona: mismo ORCID, o mismo apellido
    (sin tildes ni mayúsculas) con nombres compatibles. Dos ORCID distintos nunca se proponen.
    → [{'a', 'b', 'motivo'}] con el resumen de cada uno (lo más usado primero)."""
    gente = get_db().q("SELECT id, nombres, apellidos, orcid FROM persona_externa WHERE usuario_id IS NULL")
    por_apellido, pares = {}, {}
    for p in gente:
        por_apellido.setdefault(" ".join(_tokens(p["apellidos"])), []).append(p)
    por_orcid = {}
    for p in gente:
        if p["orcid"]:
            por_orcid.setdefault(p["orcid"].strip(), []).append(p)
    for lista in por_orcid.values():
        for i, a in enumerate(lista):
            for b in lista[i + 1:]:
                pares[(min(a["id"], b["id"]), max(a["id"], b["id"]))] = "Mismo ORCID"
    for lista in por_apellido.values():
        for i, a in enumerate(lista):
            for b in lista[i + 1:]:
                clave = (min(a["id"], b["id"]), max(a["id"], b["id"]))
                distintos = a["orcid"] and b["orcid"] and a["orcid"].strip() != b["orcid"].strip()
                if clave not in pares and not distintos and nombres_compatibles(a["nombres"], b["nombres"]):
                    pares[clave] = "Mismo apellido y nombres compatibles"
    res = []
    for (x, y), motivo in pares.items():
        a, b = _resumen_externo(x), _resumen_externo(y)
        uso = lambda e: e["n_productos"] + e["n_actividades"] + e["n_proyectos"] + e["n_estudiante"]  # noqa: E731
        if uso(b) > uso(a):
            a, b = b, a
        res.append({"a": a, "b": b, "motivo": motivo})
    return sorted(res, key=lambda r: (sin_tildes(r["a"]["apellidos"]).lower(), sin_tildes(r["a"]["nombres"]).lower()))


def fusionar(conservar: int, eliminar: int) -> str | None:
    """Une dos fichas de una misma persona externa: los productos, actividades, proyectos y periodos
    de estudiante de `eliminar` pasan a `conservar` (si ambas figuraban en el mismo registro, queda
    una vez), los datos que le falten a `conservar` se toman de `eliminar`, y `eliminar` se borra.
    → None, o el motivo por el que no se puede."""
    if conservar == eliminar:
        return "Elija dos personas distintas."
    a, b = _resumen_externo(conservar), _resumen_externo(eliminar)
    if not a or not b:
        return "Una de las personas ya no existe."
    if a["usuario_id"] or b["usuario_id"]:
        return "Solo se fusionan personas externas sin cuenta en el sistema."
    if a["orcid"] and b["orcid"] and a["orcid"].strip() != b["orcid"].strip():
        return "Tienen ORCID distintos: no son la misma persona."
    db = get_db()
    with transaccion():
        for tabla, registro in (("producto_autor", "producto_id"), ("actividad_participante", "actividad_id"),
                                ("proyecto_participante", "proyecto_id")):
            db.execute(f"""DELETE FROM {tabla} WHERE externo_id = :e AND {registro} IN (
                               SELECT {registro} FROM {tabla} WHERE externo_id = :c)""", {"e": eliminar, "c": conservar})
            db.execute(f"UPDATE {tabla} SET externo_id = ? WHERE externo_id = ?", [conservar, eliminar])
        db.execute("UPDATE estudiante SET externo_id = ? WHERE externo_id = ?", [conservar, eliminar])
        db.execute("""UPDATE persona_externa SET
                          institucion = COALESCE(NULLIF(institucion, ''), :i), pais = COALESCE(NULLIF(pais, ''), :p),
                          email = COALESCE(NULLIF(email, ''), :m), orcid = COALESCE(NULLIF(orcid, ''), :o)
                      WHERE id = :c""", {"i": b["institucion"], "p": b["pais"], "m": b["email"], "o": b["orcid"],
                                         "c": conservar})
        db.execute("DELETE FROM persona_externa WHERE id = ?", [eliminar])
    return None


# --- Externos que luego recibieron cuenta ------------------------------------------------------------

def sugerencias_de_cuenta() -> list[dict]:
    """Personas externas (sin cuenta vinculada) que podrían ser alguien que ya tiene cuenta: mismo
    ORCID, mismo correo, o mismo apellido con nombres compatibles. → [{'externo', 'usuario', 'motivo'}]."""
    cuentas = get_db().q("""SELECT u.id, u.nombres, u.apellidos, u.email, i.orcid FROM usuario u
                            LEFT JOIN investigador i ON i.usuario_id = u.id WHERE u.activo = 1""")
    por_apellido = {}
    for u in cuentas:
        por_apellido.setdefault(" ".join(_tokens(u["apellidos"])), []).append(u)
    res = []
    for e in get_db().q("SELECT id, nombres, apellidos, email, orcid FROM persona_externa WHERE usuario_id IS NULL"):
        for u in cuentas:
            motivo = None
            if e["orcid"] and u["orcid"] and e["orcid"].strip() == u["orcid"].strip():
                motivo = "Mismo ORCID"
            elif e["email"] and u["email"] and e["email"].strip().lower() == u["email"].strip().lower():
                motivo = "Mismo correo"
            elif (u in por_apellido.get(" ".join(_tokens(e["apellidos"])), [])
                  and not (e["orcid"] and u["orcid"] and e["orcid"].strip() != u["orcid"].strip())
                  and nombres_compatibles(e["nombres"], u["nombres"])):
                motivo = "Mismo apellido y nombres compatibles"
            if motivo:
                res.append({"externo": _resumen_externo(e["id"]), "usuario": u, "motivo": motivo})
    return sorted(res, key=lambda r: (sin_tildes(r["usuario"]["apellidos"]).lower(), r["externo"]["id"]))


def vincular_a_cuenta(externo_id: int, usuario_id: int) -> str | None:
    """La persona externa recibió cuenta: sus autorías y participaciones en actividades y proyectos
    pasan a la cuenta (si ya figuraba con la cuenta en el mismo registro, queda una vez). Si tiene
    periodos de estudiante, la ficha se conserva enlazada a la cuenta solo para guardarlos (decisión
    del 1-oct-2026, PLAN §42); si no, se borra. El ORCID pasa al perfil si este no lo tiene.
    → None, o el motivo por el que no se puede."""
    e = _resumen_externo(externo_id)
    u = get_db().q("SELECT id FROM usuario WHERE id = ?", [usuario_id])
    if not e or not u:
        return "La persona o la cuenta ya no existen."
    if e["usuario_id"]:
        return "Esa ficha ya está vinculada a una cuenta."
    db = get_db()
    with transaccion():
        for tabla, registro in (("producto_autor", "producto_id"), ("actividad_participante", "actividad_id"),
                                ("proyecto_participante", "proyecto_id")):
            db.execute(f"""DELETE FROM {tabla} WHERE externo_id = :e AND {registro} IN (
                               SELECT {registro} FROM {tabla} WHERE investigador_id = :u)""",
                       {"e": externo_id, "u": usuario_id})
            db.execute(f"UPDATE {tabla} SET investigador_id = ?, externo_id = NULL WHERE externo_id = ?",
                       [usuario_id, externo_id])
        if e["orcid"]:
            db.execute("""UPDATE investigador SET orcid = ? WHERE usuario_id = ? AND (orcid IS NULL OR orcid = '')""",
                       [e["orcid"].strip(), usuario_id])
        if e["n_estudiante"]:
            db.execute("UPDATE persona_externa SET usuario_id = ? WHERE id = ?", [usuario_id, externo_id])
        else:
            db.execute("DELETE FROM persona_externa WHERE id = ?", [externo_id])
    return None
