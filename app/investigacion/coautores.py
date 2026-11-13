"""Colaboraciones de un investigador (PLAN §69, etapa 3): con quién firmó productos y con quién compartió proyectos. Todo se
deriva de lo que ya está registrado —no guarda nada— y es solo de la propia persona (`auth["id"]`). De cada persona se muestran
únicamente los datos que ya se ven en los productos y proyectos: nombre, institución y país."""
from app.comun import config, paises, personas
from app.comun.db import get_db, sin_tildes
from app.investigacion import productos


def _anios(desde: int | None, hasta: int | None, col: str) -> tuple[str, list]:
    cond, params = [], []
    if desde:
        cond.append(f"{col} >= ?")
        params.append(desde)
    if hasta:
        cond.append(f"{col} <= ?")
        params.append(hasta)
    return (" AND " + " AND ".join(cond)) if cond else "", params


def _ref(f: dict) -> str:
    return personas.ref(f["investigador_id"], f["externo_id"])


def _de_productos(uid: int, desde, hasta) -> list[dict]:
    filtro, params = _anios(desde, hasta, "p.anio")
    return get_db().q(
        f"""SELECT o.investigador_id, o.externo_id, p.id AS producto_id, p.anio FROM producto_autor yo
            JOIN producto p ON p.id = yo.producto_id JOIN producto_autor o ON o.producto_id = p.id AND o.orden != yo.orden
            WHERE yo.investigador_id = ? AND COALESCE(o.investigador_id, 0) != ?{filtro}""", [uid, uid, *params])


def _de_proyectos(uid: int, desde, hasta) -> list[dict]:
    cond, params = "", []
    if desde:
        cond += " AND COALESCE(substr(pr.fecha_fin, 1, 4), '9999') >= ?"
        params.append(str(desde))
    if hasta:
        cond += " AND COALESCE(substr(pr.fecha_inicio, 1, 4), '0000') <= ?"
        params.append(str(hasta))
    return get_db().q(
        f"""SELECT o.investigador_id, o.externo_id, pr.id AS proyecto_id FROM proyecto_participante yo
            JOIN proyecto pr ON pr.id = yo.proyecto_id JOIN proyecto_participante o ON o.proyecto_id = pr.id AND o.id != yo.id
            WHERE yo.investigador_id = ? AND COALESCE(o.investigador_id, 0) != ?{cond}""", [uid, uid, *params])


def _paises_de(externos: set[int]) -> dict[int, str | None]:
    res = {}
    for lote in personas._lotes(sorted(externos)):
        for f in get_db().q(f"SELECT id, pais FROM persona_externa WHERE id IN ({','.join('?' * len(lote))})", lote):
            res[f["id"]] = f["pais"]
    return res


def colaboradores(uid: int, desde: int | None = None, hasta: int | None = None) -> list[dict]:
    """Quienes firmaron productos o participaron en proyectos con la persona (entre los años dados, si se piden), los de más
    colaboración primero. Cada uno: ref, nombres, apellidos, institucion, pais, interno, n_productos, n_proyectos, primero,
    ultimo (años de sus productos en común) y los ids de esos productos y proyectos."""
    acum: dict[str, dict] = {}
    for f in _de_productos(uid, desde, hasta):
        a = acum.setdefault(_ref(f), {"productos": set(), "proyectos": set(), "anios": set()})
        a["productos"].add(f["producto_id"])
        a["anios"].add(f["anio"])
    for f in _de_proyectos(uid, desde, hasta):
        acum.setdefault(_ref(f), {"productos": set(), "proyectos": set(), "anios": set()})["proyectos"].add(f["proyecto_id"])
    gente = personas.por_refs(acum)
    pais = _paises_de({int(r[2:]) for r in acum if r.startswith("e:")})
    res = []
    for r, a in acum.items():
        p = gente.get(r)
        if not p:
            continue
        res.append({"ref": r, "nombres": p["nombres"], "apellidos": p["apellidos"], "institucion": p.get("afiliacion") or "",
                    "pais": (pais.get(p["id"]) or "") if not p["interno"] else config.PAIS, "interno": bool(p["interno"]),
                    "n_productos": len(a["productos"]), "n_proyectos": len(a["proyectos"]),
                    "primero": min(a["anios"]) if a["anios"] else None, "ultimo": max(a["anios"]) if a["anios"] else None,
                    "productos": sorted(a["productos"]), "proyectos": sorted(a["proyectos"])})
    return sorted(res, key=lambda c: (-(c["n_productos"] + c["n_proyectos"]), -c["n_productos"],
                                      sin_tildes(c["apellidos"]), sin_tildes(c["nombres"])))


def resumen(lista: list[dict]) -> dict:
    """Totales y distribución por país e institución de una lista de `colaboradores`. Los países cuentan personas (no
    productos); las instituciones son solo las de los externos; «sin país» son los externos a quienes aún no se les registró."""
    externos = [c for c in lista if not c["interno"]]
    por_pais: dict[str, int] = {}
    por_institucion: dict[str, int] = {}
    for c in lista:
        por_pais[c["pais"] or "Sin país registrado"] = por_pais.get(c["pais"] or "Sin país registrado", 0) + 1
        if c["institucion"] and not c["interno"]:       # la unidad de un colega del instituto no es otra institución
            por_institucion[c["institucion"]] = por_institucion.get(c["institucion"], 0) + 1
    extranjeros = [c for c in lista if paises.es_extranjero(c["pais"], config.PAIS)]
    ordenar = lambda d: sorted(d.items(), key=lambda kv: (-kv[1], sin_tildes(kv[0])))  # noqa: E731
    return {"total": len(lista), "internos": len(lista) - len(externos), "externos": len(externos),
            "extranjeros": len(extranjeros), "sin_pais": sum(not c["pais"] for c in externos),
            "paises": ordenar(por_pais), "instituciones": ordenar(por_institucion)[:10],
            "n_instituciones": len(por_institucion), "n_paises_extranjeros": len({c["pais"] for c in extranjeros})}


def compartidos(uid: int, ref: str, desde: int | None = None, hasta: int | None = None) -> dict | None:
    """Lo que la persona tiene en común con `ref`: sus productos (completos) y proyectos. None si no hay nada en común."""
    c = next((c for c in colaboradores(uid, desde, hasta) if c["ref"] == ref), None)
    if not c:
        return None
    marcas = ",".join("?" * len(c["proyectos"]))
    proyectos = get_db().q(f"SELECT id, nombre, tipo, estado FROM proyecto WHERE id IN ({marcas}) ORDER BY fecha_inicio DESC, nombre",
                           c["proyectos"]) if c["proyectos"] else []
    lista = sorted(productos.obtener_varios(c["productos"]), key=lambda p: (-p["anio"], p["titulo"]))
    return {**c, "lista_productos": lista, "lista_proyectos": proyectos}


def filas_csv(lista: list[dict]) -> list[dict]:
    return [{"Apellidos": c["apellidos"], "Nombres": c["nombres"], "Institución": c["institucion"], "País": c["pais"],
             "Tipo": "Del instituto" if c["interno"] else "Externo", "Productos en común": c["n_productos"],
             "Proyectos en común": c["n_proyectos"], "Primer año": c["primero"] or "", "Último año": c["ultimo"] or ""}
            for c in lista]
