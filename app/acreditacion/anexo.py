"""Anexo de I+D+i para la acreditación ante IAC-CINDA.

Reúne, para una ventana de años (por omisión, los últimos 5: la evidencia que pide el criterio
3.6.3), los datos del portal ordenados por criterio, con un resumen año por año. Aplica las mismas
reglas que la memoria del instituto (vínculo en la fecha, filiación, catálogo de revistas) y, por
omisión, exige revista verificada, como corresponde a la acreditación.
"""
from datetime import date

from app.investigacion import actividades, perfiles, proyectos, revistas
from app.academico import carga
from app.acreditacion import estudiantes as ind_estudiantes
from app.comun import config, estudiantes, paises, vinculos
from app.acreditacion import informes
from app.comun.db import get_db

# Actividades por criterio (nombres del catálogo de tipos de actividad).
ESTANCIAS = ("Estancia o pasantía de investigación", "Visita de investigación")
EVENTOS = ("Congreso", "Seminario", "Taller / Workshop", "Escuela")
TRANSFERENCIA = ("Transferencia de conocimiento",)
DIVULGACION = ("Charla de divulgación",)
REDES = ("Participación en red de investigación",)
COMITES = ("Comité científico o editorial",)
JORNADA_COMPLETA = 160  # h/mes: tiempo completo (5 cargas de 32 h/mes)
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
    carga total y jornada completa equivalente (JCE = h/mes / 160).

    La carga es la contratada del semestre (app.academico.carga); para años sin carga registrada, la
    jornada del vínculo (dato de RR. HH. en h/semana) × 4."""
    corte = min(f"{anio}-12-31", hasta, date.today().isoformat())
    por_categoria, horas, sin_jornada, personas = {}, 0, 0, []
    for u in vinculos.personas_en_rango("0000-01-01", corte):
        v = vinculos.vigente(u["id"], corte)
        if not v:
            continue
        nombre = perfiles.CATEGORIAS[v["categoria"]]
        por_categoria[nombre] = por_categoria.get(nombre, 0) + 1
        h = carga.contratada_en(u["id"], corte) or (v["jornada_horas"] * 4 if v["jornada_horas"] else None)
        if h:
            horas += h
        else:
            sin_jornada += 1
        personas.append({**u, "categoria": nombre, "jornada": h})
    return {"anio": anio, "corte": corte, "total": len(personas), "por_categoria": por_categoria, "horas": horas,
            "jce": round(horas / JORNADA_COMPLETA, 1), "sin_jornada": sin_jornada, "personas": personas}


def _internacional(a: dict) -> bool:
    return a.get("ambito") == "internacional"


def coautoria_internacional(prods: list[dict]) -> dict:
    """Coautoría internacional de los artículos: cuántos tienen al menos un coautor externo de otro
    país, cuántos tienen coautores externos, en cuántos se conoce el país de todos ellos (cobertura)
    y con qué países se colabora (IAC-CINDA 3.5.2 c)."""
    con_externos = con_pais = internacionales = 0
    por_pais, lista_int = {}, []
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
            lista_int.append({**p, "paises": extranjeros})
            for x in extranjeros:
                por_pais[x] = por_pais.get(x, 0) + 1
    return {"internacionales": internacionales, "con_externos": con_externos, "con_pais": con_pais,
            "por_pais": dict(sorted(por_pais.items(), key=lambda x: (-x[1], x[0]))), "lista": lista_int}


# Indicadores del resumen por año: clave → (nombre, clase de registro, de dónde sale la cifra). La
# clase dice cómo se listan los registros en la trazabilidad (/informes/acreditacion/detalle).
INDICADORES = {
    "investigadores": ("Investigadores", "persona", "Personas con vínculo vigente con la Carrera al 31 de diciembre "
                       "(o a hoy, en el año en curso)."),
    "jce": ("JCE (160 h/mes)", "persona", "Suma de la carga contratada en h/mes de las personas vinculadas al 31 de "
            "diciembre, dividida entre 160; sin carga registrada, la jornada del vínculo × 4. Se listan las personas "
            "que aportan horas."),
    "indexados": ("Artículos indexados", "producto", "Artículos (en revista o en actas) indexados que cuentan en la "
                  "memoria del año."),
    "arbitrados": ("Artículos arbitrados", "producto", "Artículos (en revista o en actas) arbitrados que cuentan en "
                   "la memoria del año."),
    "nacionales": ("En revistas nacionales", "producto", "Artículos en revista que cuentan, con revista de ámbito "
                   "nacional."),
    "internacionales": ("En revistas internacionales", "producto", "Artículos en revista que cuentan, con revista "
                        "de ámbito internacional."),
    "libros": ("Libros y capítulos", "producto", "Libros y capítulos arbitrados o indexados que cuentan en la memoria."),
    "tecnicos": ("Patentes, software, traducciones", "producto", "Patentes, software y traducciones de autores "
                 "vinculados en la fecha."),
    "presentaciones": ("Presentaciones", "actividad", "Congresos, seminarios, talleres y escuelas en que alguien del "
                       "instituto fue expositor(a)."),
    "estancias": ("Estancias", "actividad", "Estancias, pasantías y visitas de investigación."),
    "transferencia": ("Transferencia", "actividad", "Actividades de transferencia de conocimiento."),
    "redes": ("Redes", "actividad", "Participación en redes de investigación."),
    "proyectos": ("Proyectos vigentes", "proyecto", "Proyectos (salvo en formulación) cuyo periodo se cruza con el año."),
    "tesis_defendidas": ("Tesis defendidas", "producto", "Tesis publicadas en el año con al menos un director del "
                         "instituto vinculado en la fecha."),
    "con_estudiantes": ("Productos con estudiantes", "producto", "Productos que cuentan con al menos un coautor que "
                        "era estudiante en el año de publicación."),
    "coautoria_internacional": ("Artículos con coautoría internacional", "producto", "Artículos que cuentan con al "
                                "menos un coautor externo de otro país."),
    "proyectos_internacionales": ("Proyectos internacionales", "proyecto", "Proyectos vigentes con contrapartes o "
                                  "financiamiento de otros países (o ámbito internacional declarado)."),
    "citas": ("Citas", "producto", "Suma de las citas según OpenAlex de los productos que cuentan en el año. Se "
              "listan los productos con citas."),
}


def registros_del_anio(anio: int, hasta: str, exigir_verificada: bool = True) -> tuple[dict, dict, dict]:
    """(cuerpo académico, registros de cada indicador del resumen, memoria del año). La cifra de
    cada indicador es la cantidad de sus registros, salvo JCE y citas, que suman."""
    ma = informes.memoria(desde=f"{anio}-01-01", hasta=f"{anio}-12-31", exigir_verificada=exigir_verificada)
    cuerpo = cuerpo_academico(anio, hasta)
    prods, acts = ma["productos"], ma["actividades"]
    # Solo artículos: los libros y capítulos tienen su propia fila.
    arts = [p for p in prods if p["tipo"] in TIPOS_ARTICULO]
    ambito = lambda a: [p for p in prods if (p.get("detalle_revista") or {}).get("ambito") == a]  # noqa: E731
    regs = {
        "investigadores": cuerpo["personas"], "jce": [p for p in cuerpo["personas"] if p["jornada"]],
        "indexados": [p for p in arts if p["revision"] == "indexado"],
        "arbitrados": [p for p in arts if p["revision"] == "arbitrado"],
        "nacionales": ambito("Nacional"), "internacionales": ambito("Internacional"),
        "libros": [p for p in prods if p["tipo"] in ("Libro", "Capítulo de libro")],
        "tecnicos": informes.otros_resultados(f"{anio}-01-01", f"{anio}-12-31", ("Patente", "Software", "Traducción")),
        "presentaciones": _presentaciones(acts),
        "estancias": [a for a in acts if a["tipo"] in ESTANCIAS],
        "transferencia": [a for a in acts if a["tipo"] in TRANSFERENCIA],
        "redes": [a for a in acts if a["tipo"] in REDES],
        "proyectos": ma["proyectos"],
        "tesis_defendidas": [t["producto"] for t in ind_estudiantes.tesis(anio, anio) if t["estado"] == "defendida"],
        "con_estudiantes": [p for p in prods if estudiantes.es_estudiante_ref(p["autores"], p["anio"])],
        "coautoria_internacional": coautoria_internacional(arts)["lista"],
        "proyectos_internacionales": [p for p in ma["proyectos"] if proyectos.ambito_efectivo(p) == "internacional"],
        "citas": sorted((p for p in prods if p.get("citas")), key=lambda p: -p["citas"]),
    }
    return cuerpo, regs, ma


def detalle(indicador: str, anio: int, hasta: str, exigir_verificada: bool = True, categoria: str = "") -> dict | None:
    """Trazabilidad: los registros que componen la cifra de un indicador en un año del anexo."""
    if indicador not in INDICADORES:
        return None
    nombre, clase, regla = INDICADORES[indicador]
    cuerpo, regs, ma = registros_del_anio(anio, hasta, exigir_verificada)
    lista = regs[indicador]
    valor = {"jce": cuerpo["jce"], "citas": ma["impacto"]["citas"]}.get(indicador, len(lista))
    if categoria and clase == "persona":
        lista = [p for p in lista if p["categoria"] == categoria]
        valor = len(lista)
    return {"indicador": indicador, "nombre": nombre, "clase": clase, "regla": regla, "anio": anio,
            "categoria": categoria, "valor": valor, "registros": lista}


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
        cuerpo, regs, ma = registros_del_anio(anio, hasta, exigir_verificada)
        anios.append({"anio": anio, **{k: len(v) for k, v in regs.items()}, "jce": cuerpo["jce"],
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
        "estudiantes": ind_estudiantes.indicadores(m),
    }
