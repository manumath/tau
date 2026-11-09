"""Medición del piloto de IA (PLAN §59, etapas 1b y 2): resultados por función y año, decisiones de cierre y reporte de
sesgos de la clasificación de productos. Todo se calcula desde `ia_uso` e `ia_salida`; no mide a personas (principio 7):
no hay cifras por usuario."""
from datetime import datetime

from app.comun.db import auditar, get_db
from app.ia import servicio
from app.ia.funciones import obtener as funcion

DECISIONES_CIERRE = {"ampliar": "Ampliar", "ajustar": "Ajustar", "retirar": "Retirar"}
MIN_SESGO = 5          # mínimo de sugerencias para comparar una línea o un tipo
FACTOR_SESGO = 1.5     # se señala lo que se descarta 1,5 veces más que el promedio


def _horas(desde: str | None, hasta: str | None) -> float | None:
    if not desde or not hasta:
        return None
    return (datetime.fromisoformat(hasta) - datetime.fromisoformat(desde)).total_seconds() / 3600


def _promedio(valores):
    v = [x for x in valores if x is not None]
    return round(sum(v) / len(v), 2) if v else None


def piloto() -> list[dict]:
    """Por función y año: usos, aprobadas sin cambios, editadas, rechazadas, con error, horas hasta la decisión,
    distancia de edición media y valoración media."""
    grupos: dict[tuple[str, str], list[dict]] = {}
    for u in get_db().q("SELECT * FROM ia_uso ORDER BY funcion_clave, creado_en"):
        grupos.setdefault((u["funcion_clave"], u["creado_en"][:4]), []).append(u)
    res = []
    for (clave, anio), usos in sorted(grupos.items()):
        f = funcion(clave)
        cuenta = {e: sum(u["estado"] == e for u in usos) for e in ("aprobada", "editada", "rechazada", "error")}
        decididos = cuenta["aprobada"] + cuenta["editada"] + cuenta["rechazada"]
        res.append({"clave": clave, "nombre": f.nombre if f else clave, "anio": anio, "n": len(usos), **cuenta,
                    "decididos": decididos,
                    "pct_aceptadas": round(100 * (cuenta["aprobada"] + cuenta["editada"]) / decididos) if decididos else None,
                    "horas": _promedio(_horas(u["creado_en"], u["fecha_decision"]) for u in usos),
                    "distancia": _promedio(u["distancia_edicion"] for u in usos),
                    "valoracion": _promedio(u["valoracion"] for u in usos)})
    return res


def recientes(limite: int = 50) -> list[dict]:
    return get_db().q(
        """SELECT u.id, u.funcion_clave, u.creado_en, u.estado, u.proveedor, u.modelo, u.version_prompt, u.nivel_datos,
                  u.seudonimizado, u.valoracion, u.fecha_decision
           FROM ia_uso u ORDER BY u.id DESC LIMIT ?""", [limite])


# --- Cierre del piloto --------------------------------------------------------------------------------------------

def cierres() -> list[dict]:
    return get_db().q("""SELECT c.*, u.nombres || ' ' || u.apellidos AS por FROM ia_cierre c
                         JOIN usuario u ON u.id = c.decidido_por ORDER BY c.fecha DESC, c.id DESC""")


def cerrar(clave: str, decision: str, fundamento: str, uid: int) -> list[str]:
    """Decisión documentada de la Dirección de Carrera sobre una función piloto. «Retirar» la apaga."""
    errores = []
    if not funcion(clave):
        errores.append("Elija una función.")
    if decision not in DECISIONES_CIERRE:
        errores.append("Elija la decisión: ampliar, ajustar o retirar.")
    fundamento = (fundamento or "").strip()
    if len(fundamento) < 20:
        errores.append("Fundamente la decisión con los resultados del piloto (al menos una oración).")
    if errores:
        return errores
    cid = get_db().t.ia_cierre.insert(funcion_clave=clave, decision=decision, fundamento=fundamento[:4000],
                                      decidido_por=uid)["id"]
    auditar(uid, "ia_cierre", "ia_cierre", cid, f"{clave}: {decision}")
    if decision == "retirar":
        servicio.desactivar(clave, uid)
    return []


# --- Sesgos de la clasificación de productos ------------------------------------------------------------------------

def sesgos() -> dict:
    """Tasa de descarte de las sugerencias de `producto_clasificar`, por línea sugerida y por tipo de producto.
    Una sugerencia se descarta si la persona rechaza el borrador o desmarca esa línea. Se señala lo que se descarta
    claramente más que el promedio (≥ 1,5 veces, con al menos 5 sugerencias)."""
    usos = get_db().q(
        """SELECT u.estado, u.entidad_id, s.texto_generado, s.texto_final, t.nombre AS tipo
           FROM ia_uso u JOIN ia_salida s ON s.uso_id = u.id
           LEFT JOIN producto p ON p.id = u.entidad_id LEFT JOIN tipo_producto t ON t.id = p.tipo_id
           WHERE u.funcion_clave = 'producto_clasificar' AND u.estado IN ('aprobada', 'editada', 'rechazada')""")
    nombres = {str(x["id"]): x["nombre"] for x in get_db().q("SELECT id, nombre FROM linea_investigacion")}
    por_linea, por_tipo = {}, {}
    for u in usos:
        finales = set((u["texto_final"] or "").split(",")) if u["estado"] != "rechazada" else set()
        for lid in [x for x in (u["texto_generado"] or "").split(",") if x]:
            descartada = lid not in finales
            for clave, tabla in ((nombres.get(lid, f"Línea {lid}"), por_linea), (u["tipo"] or "Sin tipo", por_tipo)):
                t = tabla.setdefault(clave, {"n": 0, "descartadas": 0})
                t["n"] += 1
                t["descartadas"] += descartada
    total = sum(t["n"] for t in por_linea.values())
    descartadas = sum(t["descartadas"] for t in por_linea.values())
    tasa = descartadas / total if total else None

    def filas(tabla):
        res = []
        for clave, t in sorted(tabla.items(), key=lambda x: -x[1]["n"]):
            pct = t["descartadas"] / t["n"]
            res.append({"nombre": clave, **t, "pct": round(100 * pct),
                        "senal": bool(tasa is not None and t["n"] >= MIN_SESGO and pct >= FACTOR_SESGO * tasa
                                      and t["descartadas"] >= 2)})
        return res
    return {"total": total, "pct": round(100 * tasa) if tasa is not None else None,
            "por_linea": filas(por_linea), "por_tipo": filas(por_tipo)}
