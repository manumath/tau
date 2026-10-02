"""Estudiantes en la investigación: tesis e indicadores de participación para el anexo de I+D+i
(IAC-CINDA 2.3.2, 2.3.4 y 3.6.1 d). Los periodos de estudio de cada persona están en
app.comun.estudiantes."""
from app.comun import vinculos
from app.comun.db import get_db
from app.comun.estudiantes import (NIVELES, TIPO_TESIS, es_estudiante_ref, estudiante_de, estudiante_en, ficha,
                                   graduado_de, periodos)
from app.investigacion import actividades, productos, proyectos


def tesis(desde_anio: int, hasta_anio: int) -> list[dict]:
    """Tesis dirigidas del periodo con al menos un director del instituto vinculado en la fecha.
    Cada una: producto, tesistas (con nivel), directores y estado (defendida / en curso)."""
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
            # Tesistas: los demás autores (externos o, si luego recibieron cuenta, con su ficha de estudiante).
            f = ficha(a)
            if a in directores or not f:
                continue
            p = estudiante_en(f, x["anio"]) or (periodos(f) or [None])[-1]
            tesistas.append({**a, "nivel": p["nivel"] if p else None, "del_programa": bool(p and p["del_programa"])})
        res.append({"producto": x, "tesistas": tesistas, "directores": directores,
                    "estado": "defendida" if x["estado_publicacion"] == "publicado" else "en curso",
                    "nivel": next((t["nivel"] for t in tesistas if t["nivel"]), None)})
    return res


def indicadores(m: dict) -> dict:
    """Participación de estudiantes y graduados en lo que cuenta la memoria o el anexo `m`."""
    a0, a1 = int(m["desde"][:4]), int(m["hasta"][:4])
    con_estudiantes = [p for p in m["productos"] if es_estudiante_ref(p["autores"], p["anio"])]
    con_graduados = [p for p in m["productos"]
                     if any(graduado_de(a, p["anio"]) for a in p["autores"])]
    proys = []
    for p in m["proyectos"]:
        ini = int((p["fecha_inicio"] or f"{a0}")[:4])
        fin = int((p["fecha_fin"] or f"{a1}")[:4])
        anios = range(max(ini, a0), min(fin, a1) + 1)
        est = [x for x in proyectos.participantes(p["id"]) if any(estudiante_de(x, y) for y in anios)]
        if est:
            proys.append({**p, "estudiantes": est})
    acts = []
    for a in m["actividades"]:
        anio = int(a["fecha_inicio"][:4])
        est = [x for x in actividades.participantes(a["id"]) if estudiante_de(x, anio)]
        if est:
            acts.append({**a, "estudiantes": est})
    t = tesis(a0, a1)
    por_nivel = {}
    for x in t:
        clave = (NIVELES.get(x["nivel"], "Nivel sin registrar"), x["estado"])
        por_nivel[clave] = por_nivel.get(clave, 0) + 1
    return {"tesis": t, "tesis_por_nivel": por_nivel, "productos": con_estudiantes, "graduados": con_graduados,
            "proyectos": proys, "actividades": acts}
