"""Anexo de I+D+i para la acreditación ante IAC-CINDA.

Reúne, para una ventana de años (por omisión, los últimos 5: la evidencia que pide el criterio
3.6.3), los datos del portal ordenados por criterio, con un resumen año por año. Aplica las mismas
reglas que la memoria del instituto (vínculo en la fecha, filiación, catálogo de revistas) y, por
omisión, exige revista verificada, como corresponde a la acreditación.
"""
from datetime import date

from app import actividades, config, estudiantes, informes, paises, perfiles, proyectos, revistas, vinculos
from app.db import get_db

# Actividades por criterio (nombres del catálogo de tipos de actividad).
ESTANCIAS = ("Estancia o pasantía de investigación", "Visita de investigación")
EVENTOS = ("Congreso", "Seminario", "Taller / Workshop", "Escuela")
TRANSFERENCIA = ("Transferencia de conocimiento",)
DIVULGACION = ("Charla de divulgación",)
REDES = ("Participación en red de investigación",)
COMITES = ("Comité científico o editorial",)
JORNADA_COMPLETA = 40  # horas semanales
TIPOS_ARTICULO = (revistas.TIPO_ARTICULO, "Artículo en actas de congreso")


def ventana_por_omision() -> tuple[int, int]:
    hoy = date.today().year
    return hoy - 4, hoy


def _presentaciones(acts: list[dict]) -> list[dict]:
    """Eventos científicos en que alguien del instituto fue expositor(a) (3.6.3 i)."""
    res = []
    for a in acts:
        if a["tipo"] in EVENTOS and any(p["interno"] and p["rol"] == "expositor"
                                        for p in actividades.participantes(a["id"])):
            res.append(a)
    return res


def cuerpo_academico(anio: int, hasta: str) -> dict:
    """Personas vinculadas al 31 de diciembre del año (o a hoy, en el año en curso): por categoría,
    jornada total y jornada completa equivalente (JCE = horas / 40)."""
    corte = min(f"{anio}-12-31", hasta, date.today().isoformat())
    por_categoria, horas, sin_jornada, personas = {}, 0, 0, []
    for u in get_db().q("""SELECT DISTINCT u.id, u.nombres, u.apellidos FROM usuario u JOIN vinculo v ON v.usuario_id = u.id
                           ORDER BY u.apellidos, u.nombres"""):
        v = vinculos.vigente(u["id"], corte)
        if not v:
            continue
        nombre = perfiles.CATEGORIAS[v["categoria"]]
        por_categoria[nombre] = por_categoria.get(nombre, 0) + 1
        if v["jornada_horas"]:
            horas += v["jornada_horas"]
        else:
            sin_jornada += 1
        personas.append({**u, "categoria": nombre, "jornada": v["jornada_horas"]})
    return {"anio": anio, "corte": corte, "total": len(personas), "por_categoria": por_categoria, "horas": horas,
            "jce": round(horas / JORNADA_COMPLETA, 1), "sin_jornada": sin_jornada, "personas": personas}


def _internacional(a: dict) -> bool:
    return a.get("ambito") == "internacional"


def coautoria_internacional(prods: list[dict]) -> dict:
    """Coautoría internacional de los artículos: cuántos tienen al menos un coautor externo de otro
    país, cuántos tienen coautores externos, en cuántos se conoce el país de todos ellos (cobertura)
    y con qué países se colabora (IAC-CINDA 3.5.2 c)."""
    con_externos = con_pais = internacionales = 0
    por_pais = {}
    for p in prods:
        externos = [a for a in p["autores"] if not a["interno"] and a.get("id")]
        if not externos:
            continue
        con_externos += 1
        filas = get_db().q(f"SELECT pais FROM persona_externa WHERE id IN ({','.join('?' * len(externos))})",
                           [a["id"] for a in externos])
        lista = [paises.normalizar(f["pais"]) for f in filas]
        if all(lista):
            con_pais += 1
        extranjeros = sorted({x for x in lista if x and paises.es_extranjero(x, config.PAIS)})
        if extranjeros:
            internacionales += 1
            for x in extranjeros:
                por_pais[x] = por_pais.get(x, 0) + 1
    return {"internacionales": internacionales, "con_externos": con_externos, "con_pais": con_pais,
            "por_pais": dict(sorted(por_pais.items(), key=lambda x: (-x[1], x[0])))}


def anexo(desde_anio: int, hasta_anio: int, exigir_verificada: bool = True) -> dict:
    # Años completos (un producto de este año sin mes debe caber en la ventana); solo el cuerpo
    # académico se mira a la fecha de hoy.
    desde, hasta = f"{desde_anio}-01-01", f"{hasta_anio}-12-31"
    m = informes.memoria(desde=desde, hasta=hasta, exigir_verificada=exigir_verificada)
    prods = m["productos"]
    articulos = [p for p in prods if p["tipo"] in TIPOS_ARTICULO]
    libros = [p for p in prods if p["tipo"] in ("Libro", "Capítulo de libro")]
    tecnicos = informes.otros_resultados(desde, hasta, ("Patente", "Software", "Traducción"))
    acts = m["actividades"]
    presentaciones = _presentaciones(acts)
    por_tipo = lambda tipos: [a for a in acts if a["tipo"] in tipos]  # noqa: E731

    anios = []
    for anio in range(desde_anio, hasta_anio + 1):
        ma = informes.memoria(desde=f"{anio}-01-01", hasta=f"{anio}-12-31", exigir_verificada=exigir_verificada)
        rv = ma["revistas"]
        cuerpo = cuerpo_academico(anio, hasta)
        otros = informes.otros_resultados(f"{anio}-01-01", f"{anio}-12-31", ("Patente", "Software", "Traducción"))
        acts_a = ma["actividades"]
        anios.append({
            "anio": anio, "investigadores": cuerpo["total"], "jce": cuerpo["jce"],
            # Solo artículos: los libros y capítulos tienen su propia fila.
            "indexados": sum(p["revision"] == "indexado" for p in ma["productos"] if p["tipo"] in TIPOS_ARTICULO),
            "arbitrados": sum(p["revision"] == "arbitrado" for p in ma["productos"] if p["tipo"] in TIPOS_ARTICULO),
            "nacionales": rv["por_ambito"].get("Nacional", 0), "internacionales": rv["por_ambito"].get("Internacional", 0),
            "libros": sum(p["tipo"] in ("Libro", "Capítulo de libro") for p in ma["productos"]),
            "tecnicos": len(otros), "presentaciones": len(_presentaciones(acts_a)),
            "estancias": sum(a["tipo"] in ESTANCIAS for a in acts_a),
            "transferencia": sum(a["tipo"] in TRANSFERENCIA for a in acts_a),
            "redes": sum(a["tipo"] in REDES for a in acts_a), "proyectos": len(ma["proyectos"]),
            "tesis_defendidas": sum(x["estado"] == "defendida" for x in estudiantes.tesis(anio, anio)),
            "con_estudiantes": sum(bool(estudiantes.es_estudiante_ref(p["autores"], p["anio"])) for p in ma["productos"]),
            "coautoria_internacional": coautoria_internacional(
                [p for p in ma["productos"] if p["tipo"] in TIPOS_ARTICULO])["internacionales"],
            "proyectos_internacionales": sum(proyectos.ambito_efectivo(p) == "internacional" for p in ma["proyectos"]),
            "citas": ma["impacto"]["citas"]})

    proys = []
    for p in m["proyectos"]:
        internos = [x for x in proyectos.participantes(p["id"]) if x["interno"]]
        proys.append({**p, "n_internos": len(internos), "ambito_efectivo": proyectos.ambito_efectivo(p),
                      "contrapartes": proyectos.contrapartes(p["id"]),
                      "responsables": ", ".join(f"{x['nombres']} {x['apellidos']}" for x in internos
                                                if x["rol"] == "responsable")})
    return {
        "desde_anio": desde_anio, "hasta_anio": hasta_anio, "desde": desde, "hasta": hasta,
        "exige_verificada": exigir_verificada, "memoria": m, "anios": anios,
        "cuerpo": [cuerpo_academico(a, hasta) for a in range(desde_anio, hasta_anio + 1)],
        "articulos": articulos, "libros": libros, "tecnicos": tecnicos, "proyectos": proys,
        "presentaciones": presentaciones, "estancias": por_tipo(ESTANCIAS), "transferencia": por_tipo(TRANSFERENCIA),
        "divulgacion": por_tipo(DIVULGACION), "redes": por_tipo(REDES), "comites": por_tipo(COMITES),
        "movilidad_internacional": [a for a in por_tipo(ESTANCIAS) if _internacional(a)],
        "coautoria": coautoria_internacional(articulos),
        "estudiantes": estudiantes.indicadores(m),
    }
