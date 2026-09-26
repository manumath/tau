"""Estudiantes en la investigación: periodos de estudio de personas externas y su participación
en tesis, publicaciones, proyectos y actividades (IAC-CINDA 2.3.2, 2.3.4 y 3.6.1 d).

- Una persona era **estudiante** un año si ese año cae entre su ingreso y su egreso (o sigue
  cursando). Es **graduada** un año si egresó titulada antes de ese año.
- Tesis dirigida: producto del tipo «Tesis dirigida» con el tesista entre sus autores; los autores
  del instituto son quienes la dirigen. En curso = «en preparación»; defendida = «publicado».
"""
from app import config
from app.db import get_db, sin_tildes

NIVELES = {"licenciatura": "Licenciatura", "maestria": "Maestría", "doctorado": "Doctorado"}
TIPO_TESIS = "Tesis dirigida"


def programa_por_omision(nivel: str) -> str:
    return {"licenciatura": "Licenciatura en Matemática", "maestria": "Maestría en Matemática",
            "doctorado": "Doctorado en Matemática"}.get(nivel, "") + f" ({config.UNIVERSIDAD})"


def periodos(externo_id: int) -> list[dict]:
    return get_db().q("SELECT * FROM estudiante WHERE externo_id = ? ORDER BY desde, id", [externo_id])


def obtener_periodo(eid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM estudiante WHERE id = ?", [eid])
    return filas[0] if filas else None


def estudiante_en(externo_id: int, anio: int) -> dict | None:
    """Periodo de estudios que cubre el año (o None)."""
    return next((p for p in periodos(externo_id) if p["desde"] <= anio and (p["hasta"] is None or anio <= p["hasta"])),
                None)


def graduado_en(externo_id: int, anio: int) -> dict | None:
    """Periodo del que egresó titulado antes del año (o None)."""
    return next((p for p in reversed(periodos(externo_id)) if p["titulado"] and p["hasta"] is not None
                 and p["hasta"] < anio), None)


def etiqueta(externo_id: int, anio: int | None = None) -> str | None:
    """«Estudiante de maestría» / «Graduado(a) de licenciatura» (hoy, o en el año dado)."""
    from datetime import date
    anio = anio or date.today().year
    if (p := estudiante_en(externo_id, anio)):
        return f"Estudiante de {NIVELES[p['nivel']].lower()}"
    if (p := graduado_en(externo_id, anio)):
        return f"Graduado(a) de {NIVELES[p['nivel']].lower()}"
    return None


def validar(d: dict, externo_id: int, excluir: int | None = None) -> tuple[dict, list[str]]:
    errores = []
    nivel = d.get("nivel")
    if nivel not in NIVELES:
        errores.append("Elija el nivel.")
    desde, hasta = str(d.get("desde") or "").strip(), str(d.get("hasta") or "").strip()
    if not (desde.isdigit() and 1950 <= int(desde) <= 2100):
        errores.append("Indique el año de ingreso.")
    if hasta and not (hasta.isdigit() and 1950 <= int(hasta) <= 2100):
        errores.append("El año de egreso no es válido.")
    elif hasta and desde.isdigit() and int(hasta) < int(desde):
        errores.append("El egreso no puede ser anterior al ingreso.")
    titulado = str(d.get("titulado") or "") in ("1", "on", "true")
    if titulado and not hasta:
        errores.append("Para marcar la titulación, indique el año de egreso.")
    datos = {"nivel": nivel, "programa": (d.get("programa") or "").strip() or (programa_por_omision(nivel) if nivel in NIVELES else None),
             "del_programa": 0 if str(d.get("del_programa") or "1") in ("0", "") else 1,
             "desde": int(desde) if desde.isdigit() else None, "hasta": int(hasta) if hasta.isdigit() else None,
             "titulado": int(titulado)}
    if not errores:
        for p in periodos(externo_id):
            if p["id"] != excluir and p["nivel"] == nivel and p["desde"] <= (datos["hasta"] or 9999) \
                    and (p["hasta"] or 9999) >= datos["desde"]:
                errores.append(f"Ya tiene un periodo de {NIVELES[nivel].lower()} que se superpone ({p['desde']}–{p['hasta'] or 'hoy'}).")
    return datos, errores


def agregar(externo_id: int, d: dict, uid: int) -> list[str]:
    datos, errores = validar(d, externo_id)
    if not errores:
        get_db().t.estudiante.insert(externo_id=externo_id, registrado_por=uid, **datos)
    return errores


def editar(eid: int, d: dict) -> list[str]:
    p = obtener_periodo(eid)
    if not p:
        return ["Periodo no encontrado."]
    datos, errores = validar(d, p["externo_id"], excluir=eid)
    if not errores:
        get_db().t.estudiante.update(id=eid, **datos)
    return errores


def eliminar(eid: int):
    get_db().execute("DELETE FROM estudiante WHERE id = ?", [eid])


# --- Consultas -------------------------------------------------------------------------------------------------

def listar(texto: str = "", nivel: str = "", estado: str = "") -> list[dict]:
    """Personas con algún periodo de estudios. `estado`: 'cursando' | 'egresado'."""
    from datetime import date
    hoy = date.today().year
    patron = f"%{sin_tildes(texto.strip())}%"
    filas = get_db().q(
        """SELECT DISTINCT pe.* FROM persona_externa pe JOIN estudiante e ON e.externo_id = pe.id
           WHERE (:t = '' OR sin_tildes(pe.nombres || ' ' || pe.apellidos) LIKE :p
                  OR sin_tildes(pe.apellidos || ' ' || pe.nombres) LIKE :p)
             AND (:n = '' OR e.nivel = :n)
           ORDER BY sin_tildes(pe.apellidos), sin_tildes(pe.nombres)""", {"t": texto.strip(), "p": patron, "n": nivel})
    res = []
    for f in filas:
        ps = periodos(f["id"])
        cursando = any(p["desde"] <= hoy and (p["hasta"] is None or hoy <= p["hasta"]) for p in ps)
        if estado == "cursando" and not cursando or estado == "egresado" and cursando:
            continue
        res.append({**f, "periodos": ps, "cursando": cursando, "participacion": resumen_participacion(f["id"])})
    return res


def resumen_participacion(externo_id: int) -> dict:
    db = get_db()
    return {
        "tesis": db.q("""SELECT COUNT(*) n FROM producto_autor pa JOIN producto p ON p.id = pa.producto_id
                         JOIN tipo_producto t ON t.id = p.tipo_id WHERE pa.externo_id = ? AND t.nombre = ?""",
                      [externo_id, TIPO_TESIS])[0]["n"],
        "productos": db.q("""SELECT COUNT(*) n FROM producto_autor pa JOIN producto p ON p.id = pa.producto_id
                             JOIN tipo_producto t ON t.id = p.tipo_id WHERE pa.externo_id = ? AND t.nombre != ?""",
                          [externo_id, TIPO_TESIS])[0]["n"],
        "proyectos": db.q("SELECT COUNT(*) n FROM proyecto_participante WHERE externo_id = ?", [externo_id])[0]["n"],
        "actividades": db.q("SELECT COUNT(*) n FROM actividad_participante WHERE externo_id = ?", [externo_id])[0]["n"],
    }


def participacion(externo_id: int) -> dict:
    """Detalle para la ficha: tesis, productos, proyectos y actividades en que participa."""
    db = get_db()
    return {
        "productos": db.q("""SELECT p.id, p.titulo, p.anio, t.nombre AS tipo, p.estado_publicacion
                             FROM producto_autor pa JOIN producto p ON p.id = pa.producto_id
                             JOIN tipo_producto t ON t.id = p.tipo_id WHERE pa.externo_id = ?
                             ORDER BY p.anio DESC""", [externo_id]),
        "proyectos": db.q("""SELECT p.id, p.nombre, pp.rol, pp.fecha_desde, pp.fecha_hasta FROM proyecto_participante pp
                             JOIN proyecto p ON p.id = pp.proyecto_id WHERE pp.externo_id = ?
                             ORDER BY p.fecha_inicio DESC""", [externo_id]),
        "actividades": db.q("""SELECT a.id, a.titulo, a.fecha_inicio, ap.rol FROM actividad_participante ap
                               JOIN actividad a ON a.id = ap.actividad_id WHERE ap.externo_id = ?
                               ORDER BY a.fecha_inicio DESC""", [externo_id]),
    }


def es_estudiante_ref(autores: list[dict], anio: int) -> list[dict]:
    """Autores externos de un producto que eran estudiantes ese año."""
    return [a for a in autores if not a["interno"] and a.get("id") and estudiante_en(a["id"], anio)]


# --- Indicadores para informes (IAC-CINDA 2.3.2, 2.3.4, 3.6.1 d) ------------------------------------------------

def tesis(desde_anio: int, hasta_anio: int) -> list[dict]:
    """Tesis dirigidas del periodo con al menos un director del instituto vinculado en la fecha.
    Cada una: producto, tesistas (con nivel), directores y estado (defendida / en curso)."""
    from app import productos, vinculos
    res = []
    for f in get_db().q("""SELECT p.id FROM producto p JOIN tipo_producto t ON t.id = p.tipo_id
                           WHERE t.nombre = ? AND p.anio BETWEEN ? AND ? ORDER BY p.anio, p.id""",
                        [TIPO_TESIS, desde_anio, hasta_anio]):
        x = productos.obtener(f["id"])
        directores = [a for a in x["autores"] if a["interno"] and vinculos.en_fecha(a["id"], x["anio"], x["mes"])[0] == "si"]
        if not directores:
            continue
        tesistas = []
        for a in x["autores"]:
            if a["interno"] or not a.get("id"):
                continue
            p = estudiante_en(a["id"], x["anio"]) or (periodos(a["id"]) or [None])[-1]
            tesistas.append({**a, "nivel": p["nivel"] if p else None, "del_programa": bool(p and p["del_programa"])})
        res.append({"producto": x, "tesistas": tesistas, "directores": directores,
                    "estado": "defendida" if x["estado_publicacion"] == "publicado" else "en curso",
                    "nivel": next((t["nivel"] for t in tesistas if t["nivel"]), None)})
    return res


def indicadores(m: dict) -> dict:
    """Participación de estudiantes y graduados en lo que cuenta la memoria o el anexo `m`."""
    from app import actividades, proyectos
    a0, a1 = int(m["desde"][:4]), int(m["hasta"][:4])
    con_estudiantes = [p for p in m["productos"] if es_estudiante_ref(p["autores"], p["anio"])]
    con_graduados = [p for p in m["productos"]
                     if any(not a["interno"] and a.get("id") and graduado_en(a["id"], p["anio"]) for a in p["autores"])]
    proys = []
    for p in m["proyectos"]:
        ini = int((p["fecha_inicio"] or f"{a0}")[:4])
        fin = int((p["fecha_fin"] or f"{a1}")[:4])
        anios = range(max(ini, a0), min(fin, a1) + 1)
        est = [x for x in proyectos.participantes(p["id"]) if not x["interno"] and x.get("id")
               and any(estudiante_en(x["id"], y) for y in anios)]
        if est:
            proys.append({**p, "estudiantes": est})
    acts = []
    for a in m["actividades"]:
        anio = int(a["fecha_inicio"][:4])
        est = [x for x in actividades.participantes(a["id"]) if not x["interno"] and x.get("id") and estudiante_en(x["id"], anio)]
        if est:
            acts.append({**a, "estudiantes": est})
    t = tesis(a0, a1)
    por_nivel = {}
    for x in t:
        clave = (NIVELES.get(x["nivel"], "Nivel sin registrar"), x["estado"])
        por_nivel[clave] = por_nivel.get(clave, 0) + 1
    return {"tesis": t, "tesis_por_nivel": por_nivel, "productos": con_estudiantes, "graduados": con_graduados,
            "proyectos": proys, "actividades": acts}
