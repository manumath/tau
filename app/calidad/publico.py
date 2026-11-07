"""Página pública de indicadores (PLAN §57, etapa 9; decisión 6 del 7-nov-2026): rendición de cuentas sin sesión.

Qué se publica: solo los indicadores activos que la Dirección de Carrera marcó como públicos en el marco, y solo en los
años que cerró (sus cifras ya no cambian). De cada cifra, el valor, la base (n), la meta y el semáforo; de cada indicador,
su fórmula. Nunca el detalle de la cifra (puede nombrar personas) ni una cifra calculada sobre menos de `MIN_BASE`
personas o casos: en un grupo tan pequeño, una tasa deja reconocer a alguien.
"""
from app.calidad import indicadores, marco
from app.comun import unidades

MIN_BASE = 5


def marco_publico() -> dict | None:
    """El marco vigente de la Carrera (por ahora, el único que se publica)."""
    return marco.de_unidad(unidades.id_de("CMAT"))


def datos() -> dict | None:
    """Dimensiones con sus indicadores públicos y sus cifras en los últimos años cerrados (los de la ventana del marco)."""
    m = marco_publico()
    if not m:
        return None
    anios = sorted(indicadores.cierres(m["id"]))[-m["ventana_anios"]:]
    valores = {a: indicadores.valores_del_anio(m["id"], a) for a in anios}
    dims = []
    for d in marco.arbol(m["id"], inactivos=False):
        inds = [i for c in d["criterios"] for i in c["indicadores"] if i["publico"]]
        for i in inds:
            i["cifras"] = {a: _celda(valores[a].get(i["id"])) for a in anios}
        if inds:
            dims.append({**d, "indicadores": inds})
    return {"marco": m, "unidad": unidades.obtener(m["unidad_id"]), "anios": anios, "dimensiones": dims}


def _celda(x: dict | None) -> dict:
    """La cifra sin su detalle; oculta si la base es menor que MIN_BASE."""
    if not x or x["valor"] is None:
        return {"valor": None, "n": None, "meta": x["meta"] if x else None, "estado": "sin_dato", "oculta": False,
                "origen": "cierre", "detalle": ""}
    if x["n"] is not None and x["n"] < MIN_BASE:
        return {"valor": None, "n": None, "meta": x["meta"], "estado": "sin_dato", "oculta": True, "origen": "cierre",
                "detalle": ""}
    return {"valor": x["valor"], "n": x["n"], "meta": x["meta"], "estado": x["estado"], "oculta": False,
            "origen": "cierre", "detalle": ""}
