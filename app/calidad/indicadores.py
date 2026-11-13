"""Cifras de los indicadores del marco de calidad (PLAN §57, etapa 3): registro de cálculos automáticos, valores
manuales, tablero con metas y semáforo, cierres anuales e instantáneas diarias.

- **Cálculos automáticos** (`CALCULOS`): `clave → función(calculadora, año) → Resultado(valor, n, detalle)`. Reutilizan
  los cálculos de los informes (memoria, informe de I+D+i, cuerpo académico, cohortes, egresados, tutoría…), con una
  `Calculadora` que guarda lo que ya calculó para no repetir la memoria de un año. Las cifras son del año calendario;
  la del año en curso es parcial.
- Los **«a hoy»** (`solo_actual`) solo se pueden medir en el presente (cobertura de la tutoría, observaciones pendientes):
  el mantenimiento guarda una vez al día la cifra del año en curso en `valor_automatico`, y para un año pasado se usa la
  última que se guardó en él.
- Los **manuales** se registran por año (`valor_indicador`).
- Un año **cerrado** (`cierre_calidad`) muestra las cifras y metas congeladas al cerrarlo.
"""
import time
from dataclasses import dataclass
from datetime import date
from functools import cached_property

from app.academico import gestiones
from app.calidad import anexo, calidad_datos, cuerpo_academico, informes, marco
from app.calidad import estudiantes as ind_estudiantes
from app.comun import vinculos
from app.comun.db import get_db, transaccion
from app.egresados import egresados
from app.estudiantil import actividad, cohortes, encuestas, tutoria

DURACION_CICLOS, MARGEN_CICLOS = 10, 2   # licenciatura de 10 semestres; «oportuna» = hasta 2 ciclos más
PLAZO_DESERCION = 6   # deserción de la cohorte en sus primeros 3 años (decisión del 7-nov-2026)
SATISFECHO = 4                            # en la escala de 1 a 5, «de acuerdo» o más


@dataclass
class Resultado:
    valor: float | None
    n: int | None = None
    detalle: str = ""


def _pct(parte, total):
    return round(100 * parte / total, 1) if total else None


def _variacion(actual: int, anterior: int) -> Resultado:
    if not anterior:
        return Resultado(None, actual, f"{actual} este año; el año anterior no hubo, no se puede calcular la variación.")
    return Resultado(round(100 * (actual - anterior) / anterior, 1), actual, f"{actual} este año frente a {anterior} "
                                                                             "el anterior.")


class _Anio:
    """Lo que se calcula una vez por año (memoria, cuerpo académico)."""

    def __init__(self, anio: int):
        self.anio = anio
        self.corte = min(f"{anio}-12-31", date.today().isoformat())

    @cached_property
    def anexo(self):
        return anexo.registros_del_anio(self.anio, date.today().isoformat())

    @property
    def regs(self):
        return self.anexo[1]

    @property
    def memoria(self):
        return self.anexo[2]

    @cached_property
    def cuerpo_personas(self):
        return anexo.cuerpo_academico(self.anio, date.today().isoformat())["personas"]

    @cached_property
    def cuerpo(self):
        return cuerpo_academico.indicadores_anio(self.anio)

    @cached_property
    def articulos(self):
        return [p for p in self.memoria["productos"] if p["tipo"] in anexo.TIPOS_ARTICULO]

    @cached_property
    def estudiantes_en_proyectos(self) -> int:
        part = ind_estudiantes.indicadores(self.memoria)["proyectos"]
        return len({x["ref"] for p in part for x in p["estudiantes"]})

    @cached_property
    def semestre(self):
        return cuerpo_academico._semestre_del_anio(self.anio, self.corte)


class Calculadora:
    def __init__(self, ventana: int = 5, marco_id: int | None = None):
        self.ventana = ventana
        self.marco_id = marco_id
        self._anios: dict[int, _Anio] = {}

    def anio(self, a: int) -> _Anio:
        if a not in self._anios:
            self._anios[a] = _Anio(a)
        return self._anios[a]

    @cached_property
    def alumnos(self):
        return cohortes.alumnos()

    @cached_property
    def actual(self) -> int:
        return cohortes.ordinal(*cohortes.ciclo_actual())

    @cached_property
    def egresados(self):
        return egresados.titulados(), egresados.ultimas_respuestas()


# --- Docencia y gestión ---------------------------------------------------------------------------------------

def _paralelos(c, a):
    s = c.anio(a).semestre
    if not s:
        return Resultado(None, None, "No hay un semestre registrado en el año.")
    i = cuerpo_academico.inscripciones(s["id"])
    return Resultado(_pct(i["paralelos"] - i["sin_docente"], i["paralelos"]), i["paralelos"],
                     f"{gestiones.codigo(s)}: {i['paralelos'] - i['sin_docente']} de {i['paralelos']} paralelos con "
                     "docente titular.")


def _inscritos_por_paralelo(c, a):
    s = c.anio(a).semestre
    if not s:
        return Resultado(None, None, "No hay un semestre registrado en el año.")
    i = cuerpo_academico.inscripciones(s["id"])
    valor = round(i["inscritos"] / i["paralelos"], 1) if i["paralelos"] else None
    return Resultado(valor, i["paralelos"], f"{gestiones.codigo(s)}: {i['inscritos']} inscripciones en {i['paralelos']} "
                                            f"paralelos ({i['sin_dato']} sin dato de inscritos).")


def _revisiones(c, a):
    r = calidad_datos.resumen()
    return Resultado(r["registros"], r["chequeos"], f"{r['registros']} registros por revisar en {r['con_observaciones']} "
                                                    "revisiones.")


def _planes_licenciatura(a):
    return get_db().q(
        """SELECT p.nombre, p.vigente_desde, pr.nombre AS programa FROM plan_estudios p
           JOIN programa pr ON pr.id = p.programa_id WHERE pr.nivel = 'licenciatura' AND p.estado <> 'elaboracion'
             AND p.vigente_desde <= ? AND (p.vigente_hasta IS NULL OR p.vigente_hasta >= ?)""", [a, a])


def _antiguedad_plan(c, a):
    planes = _planes_licenciatura(a)
    if not planes:
        return Resultado(None, 0, "No hay planes de licenciatura vigentes en el año.")
    return Resultado(max(a - p["vigente_desde"] for p in planes), len(planes),
                     "; ".join(f"{p['programa']}: {p['nombre']} (desde {p['vigente_desde']})" for p in planes))


def _observaciones_plan(c, a):
    n = get_db().q("SELECT COUNT(*) n FROM observacion_plan WHERE estado = 'pendiente'")[0]["n"]
    return Resultado(n, None, f"{n} observaciones de los planes de estudio sin resolver.")


# --- Estudiantes (cohortes de la licenciatura) ----------------------------------------------------------------

def _ingresantes(c, a):
    g = [e for e in c.alumnos if e["cohorte_anio"] == a]
    return Resultado(len(g), len(g), "Cohortes I y II del año.")


def _ingresantes_mujeres(c, a):
    g = [e for e in c.alumnos if e["cohorte_anio"] == a]
    m = sum(e["sexo"] == "mujer" for e in g)
    return Resultado(_pct(m, len(g)), len(g), f"{m} mujeres de {len(g)} ingresantes.")


def _retencion(c, a):
    g = [e for e in c.alumnos if e["cohorte_anio"] == a - 1]
    medibles = [e for e in g if e["ingreso"] + 2 <= c.actual]
    if not medibles:
        return Resultado(None, 0, f"Aún no se puede medir la cohorte {a - 1}.")
    r = sum(cohortes.matriculado(e, e["ingreso"] + 2, c.actual) for e in medibles)
    return Resultado(_pct(r, len(medibles)), len(medibles),
                     f"Cohortes {a - 1}: {r} de {len(medibles)} siguen matriculados un año después de ingresar.")


def _cohorte_desercion(a):
    return a - (PLAZO_DESERCION + cohortes.CICLOS_SIN_VOLVER) // 2


def _desercion_cohorte(c, a, grupo=None):
    """Desertores en los primeros PLAZO_DESERCION ciclos e ingresantes de las cohortes cuya cifra queda firme en el año:
    el plazo más los ciclos que se esperan a un congelado (cohortes I y II de cuatro años antes)."""
    firme = PLAZO_DESERCION + cohortes.CICLOS_SIN_VOLVER
    ciclos = (cohortes.ordinal(a, "I"), cohortes.ordinal(a, "II"))
    g = [e for e in (grupo if grupo is not None else c.alumnos)
         if e["ingreso"] + firme in ciclos and e["ingreso"] + firme <= c.actual]
    d = sum(cohortes.desertor(e, c.actual) and e["ultimo"] is not None and e["ultimo"] < e["ingreso"] + PLAZO_DESERCION
            for e in g)
    return d, len(g)


def _desercion(c, a):
    d, n = _desercion_cohorte(c, a)
    if not n:
        return Resultado(None, 0, f"No hay ingresantes de la cohorte {_cohorte_desercion(a)}, o su cifra aún no es firme.")
    return Resultado(_pct(d, n), n, f"Cohorte {_cohorte_desercion(a)}: {d} de {n} ingresantes la dejaron en sus primeros "
                                    f"{PLAZO_DESERCION // 2} años (retirados, o congelados que no volvieron en los "
                                    f"{cohortes.CICLOS_SIN_VOLVER} ciclos siguientes).")


def _brecha_desercion(c, a):
    dm, nm = _desercion_cohorte(c, a, [e for e in c.alumnos if e["sexo"] == "mujer"])
    dh, nh = _desercion_cohorte(c, a, [e for e in c.alumnos if e["sexo"] == "hombre"])
    if not nm or not nh:
        return Resultado(None, nm + nh, f"Hace falta al menos una mujer y un hombre en la cohorte {_cohorte_desercion(a)}.")
    # La base es el grupo más pequeño: con pocas mujeres o pocos hombres, la brecha deja reconocer a alguien.
    return Resultado(round(100 * dm / nm - 100 * dh / nh, 1), min(nm, nh),
                     f"Mujeres: {dm} de {nm}; hombres: {dh} de {nh} (n = el grupo más pequeño).")


def _cobertura_tutoria(c, a):
    t = tutoria.indicadores()
    return Resultado(_pct(t["con_tutor"], t["cursando"]), t["cursando"],
                     f"{t['con_tutor']} de {t['cursando']} estudiantes cursando con tutor asignado.")


def _actividad_estudiantil(c, a):
    r = actividad.resumen_verificadas(a, a)
    return Resultado(sum(r.values()), None, "; ".join(f"{k}: {v}" for k, v in r.items()) or "Ninguna verificada.")


def _estudiantes_en_proyectos(c, a):
    return _variacion(c.anio(a).estudiantes_en_proyectos, c.anio(a - 1).estudiantes_en_proyectos)


def _titulacion_oportuna(c, a):
    plazo = DURACION_CICLOS + MARGEN_CICLOS - 1
    ciclos = (cohortes.ordinal(a, "I"), cohortes.ordinal(a, "II"))
    g = [e for e in c.alumnos if e["ingreso"] + plazo in ciclos and e["ingreso"] + plazo <= c.actual]
    if not g:
        return Resultado(None, 0, "No hay cohortes cuyo plazo de titulación oportuna venza en el año.")
    t = sum(e["titulacion"] is not None and e["titulacion"] <= e["ingreso"] + plazo for e in g)
    return Resultado(_pct(t, len(g)), len(g), f"{t} de {len(g)} ingresantes de las cohortes cuyo plazo "
                                              f"({DURACION_CICLOS} semestres más {MARGEN_CICLOS}) vence en el año.")


def _tiempo_titulacion(c, a):
    ciclos = (cohortes.ordinal(a, "I"), cohortes.ordinal(a, "II"))
    t = [(e["titulacion"] - e["ingreso"]) / 2 for e in c.alumnos if e["titulacion"] in ciclos]
    return Resultado(round(sum(t) / len(t), 1) if t else None, len(t), f"{len(t)} titulados en el año.")


# --- Cuerpo académico ------------------------------------------------------------------------------------------

def _cuerpo(clave, texto):
    def f(c, a):
        x = c.anio(a).cuerpo
        return Resultado(x[clave], x["total"], f"{texto}; {x['total']} académicos vinculados al {x['corte']}.")
    return f


def _inscripciones_por_jce(c, a):
    x = c.anio(a).cuerpo
    return Resultado(x["inscripciones_por_jce"], x["inscripciones"],
                     f"{x['inscripciones'] or 0} inscripciones ({x['semestre'] or 'sin semestre'}) y {x['jce']} JCE.")


def _pct_60(c, a):
    x = c.anio(a).cuerpo
    con_dato = x["total"] - x["tramos"]["Sin dato"]
    m = x["tramos"]["60 años o más"]
    return Resultado(_pct(m, con_dato), con_dato, f"{m} de {con_dato} académicos con fecha de nacimiento registrada "
                                                  f"({x['tramos']['Sin dato']} sin el dato).")


def _retencion_doctores(c, a):
    y = c.anio(a)
    cuerpo = anexo.cuerpo_academico(a, date.today().isoformat())
    doctores = [p for p in cuerpo["personas"] if cuerpo_academico._grado_hasta(p["id"], a) == "doctorado"]
    hace3 = f"{int(y.corte[:4]) - 3}{y.corte[4:]}"
    r = sum(vinculos.vigente(p["id"], hace3) is not None for p in doctores)
    return Resultado(_pct(r, len(doctores)), len(doctores),
                     f"{r} de {len(doctores)} doctores vinculados ya lo estaban tres años antes ({hace3}).")


# --- Investigación, vinculación e internacionalización ----------------------------------------------------------

def _conteo(clave, texto):
    def f(c, a):
        n = len(c.anio(a).regs[clave])
        return Resultado(n, None, f"{n} {texto} en el año.")
    return f


def _variacion_indexados(c, a):
    return _variacion(len(c.anio(a).regs["indexados"]), len(c.anio(a - 1).regs["indexados"]))


def _indexados_por_jce(c, a):
    y = c.anio(a)
    n, jce = len(y.regs["indexados"]), y.anexo[0]["jce"]
    return Resultado(round(n / jce, 2) if jce else None, n, f"{n} artículos indexados y {jce} JCE.")


def _citas(c, a):
    desde = a - c.ventana + 1
    m = informes.memoria(desde=f"{desde}-01-01", hasta=f"{a}-12-31", exigir_verificada=True)
    return Resultado(m["impacto"]["citas"], len(m["productos"]),
                     f"Citas según OpenAlex de los {len(m['productos'])} productos que cuentan entre {desde} y {a}.")


def _productos_con_estudiantes(c, a):
    y = c.anio(a)
    n, total = len(y.regs["con_estudiantes"]), len(y.memoria["productos"])
    return Resultado(_pct(n, total), total, f"{n} de {total} productos con un estudiante entre los autores.")


def _propiedad_intelectual(c, a):
    def n(y):
        return sum(p["tipo"] in ("Patente", "Software") for p in c.anio(y).regs["tecnicos"])
    return _variacion(n(a), n(a - 1))


def _proyectos(clase):
    def f(c, a):
        ps = [p for p in c.anio(a).regs["proyectos"]
              if (p.get("clase") == "interaccion_social") == (clase == "interaccion_social")]
        return Resultado(len(ps), None, f"{len(ps)} proyectos vigentes en algún momento del año.")
    return f


def _transferencia_divulgacion(c, a):
    def n(y):
        return sum(x["tipo"] in anexo.TRANSFERENCIA + anexo.DIVULGACION for x in c.anio(y).memoria["actividades"])
    return _variacion(n(a), n(a - 1))


def _coautoria(c, a):
    arts = c.anio(a).articulos
    co = anexo.coautoria_internacional(arts)
    return Resultado(_pct(len(co["lista"]), len(arts)), len(arts),
                     f"{len(co['lista'])} de {len(arts)} artículos; se conoce el país de todos los coautores externos en "
                     f"{co['con_pais']} de {co['con_externos']} artículos con coautores externos.")


# --- Egresados y encuestas ---------------------------------------------------------------------------------------

def _egresados_del_anio(c, a, clave):
    gente, resp = c.egresados
    del_anio = [g for g in gente if g["fecha_titulacion"][:4] == str(a)]
    vals = [resp[g["externo_id"]][clave] for g in del_anio if clave in resp.get(g["externo_id"], {})]
    return del_anio, vals


def _egresados(clave, cumple, texto):
    def f(c, a):
        del_anio, vals = _egresados_del_anio(c, a, clave)
        si = sum(cumple(v) for v in vals)
        return Resultado(_pct(si, len(vals)), len(vals), f"{si} de {len(vals)} respuestas de los {len(del_anio)} titulados "
                                                         f"en el año ({texto}; su respuesta más reciente).")
    return f


def _tasa_respuesta(c, a):
    f = get_db().q(
        """SELECT COUNT(DISTINCT e.id) AS encuestas,
                  (SELECT COUNT(*) FROM invitacion_encuesta i JOIN encuesta x ON x.id = i.encuesta_id
                   WHERE substr(x.abierta_en, 1, 4) = :a) AS invitaciones,
                  (SELECT COUNT(*) FROM respuesta r JOIN encuesta x ON x.id = r.encuesta_id
                   WHERE substr(x.abierta_en, 1, 4) = :a) AS respuestas
           FROM encuesta e WHERE substr(e.abierta_en, 1, 4) = :a""", {"a": str(a)})[0]
    return Resultado(_pct(f["respuestas"], f["invitaciones"]), f["invitaciones"],
                     f"{f['respuestas']} respuestas a {f['invitaciones']} invitaciones en {f['encuestas']} encuestas "
                     "abiertas en el año.")


def _autoevaluacion_vigente(c, a):
    f = get_db().q(
        """SELECT nombre, substr(concluida_en, 1, 10) AS fecha FROM autoevaluacion WHERE estado = 'concluida'
             AND (:m IS NULL OR marco_id = :m) AND CAST(substr(concluida_en, 1, 4) AS INTEGER) BETWEEN :d AND :a
           ORDER BY concluida_en DESC LIMIT 1""", {"m": c.marco_id, "d": a - c.ventana + 1, "a": a})
    if not f:
        return Resultado(0, None, f"Ninguna autoevaluación concluida entre {a - c.ventana + 1} y {a}.")
    return Resultado(1, None, f"«{f[0]['nombre']}», concluida el {f[0]['fecha']}.")


def _acciones_cumplidas(c, a):
    hoy = date.today().isoformat()
    f = get_db().q(
        """SELECT COUNT(*) AS n, COALESCE(SUM(estado = 'cumplida' AND cumplida_en <= plazo), 0) AS en_plazo
           FROM accion_mejora WHERE estado != 'cancelada' AND (:m IS NULL OR marco_id = :m)
             AND substr(plazo, 1, 4) = :a AND (plazo < :hoy OR estado = 'cumplida')""",
        {"m": c.marco_id, "a": str(a), "hoy": hoy})[0]
    return Resultado(_pct(f["en_plazo"], f["n"]), f["n"], f"{f['en_plazo']} de {f['n']} acciones con plazo en el año "
                                                          "(ya vencido, o cumplidas) se cumplieron a tiempo.")


# --- Datos de la etapa 8: encuestas a empleadores, capacitación, convenios e impacto --------------------------------

def _items_de_encuestas(a, donde: str, clave: str | None) -> tuple[list[int], int, int]:
    """Valores de escala de las encuestas abiertas en el año que cumplen `donde` (y de las preguntas con `clave`, si se
    indica). Una encuesta anónima con menos de `MIN_ANONIMO` respuestas no cuenta. → (valores, respuestas, omitidas)."""
    vals, n, omitidas = [], 0, 0
    for e in get_db().q(f"SELECT id, anonima FROM encuesta WHERE substr(abierta_en, 1, 4) = ? AND {donde}", [str(a)]):
        resp = encuestas.n_respuestas(e["id"])
        if e["anonima"] and resp < encuestas.MIN_ANONIMO:
            omitidas += 1
            continue
        n += resp
        vals += [int(f["valor"]) for f in get_db().q(
            """SELECT i.valor FROM respuesta_item i JOIN pregunta p ON p.id = i.pregunta_id
               WHERE p.encuesta_id = ? AND p.tipo = 'escala' AND (? IS NULL OR p.clave = ?)""", [e["id"], clave, clave])]
    return vals, n, omitidas


def _nota_omitidas(omitidas: int) -> str:
    return (f" No cuentan {omitidas} encuesta(s) anónima(s) con menos de {encuestas.MIN_ANONIMO} respuestas."
            if omitidas else "")


def _promedio_encuesta(donde, clave, texto):
    def f(c, a):
        vals, n, omit = _items_de_encuestas(a, donde, clave)
        prom = round(sum(vals) / len(vals), 2) if vals else None
        return Resultado(prom, n, f"Promedio de {len(vals)} valoraciones (1 a 5) en {n} respuestas a {texto} abiertas en "
                                  f"el año.{_nota_omitidas(omit)}")
    return f


def _satisfaccion_empleadores(c, a):
    vals, n, omit = _items_de_encuestas(a, "publico = 'empleadores'", "satisfaccion")
    si = sum(v >= SATISFECHO for v in vals)
    return Resultado(_pct(si, len(vals)), len(vals), f"{si} de {len(vals)} respuestas de acuerdo o totalmente de acuerdo, "
                                                     f"en encuestas a empleadores abiertas en el año.{_nota_omitidas(omit)}")


def _personal_capacitado(c, a):
    personas = c.anio(a).cuerpo_personas
    con = {f["usuario_id"] for f in get_db().q("SELECT usuario_id FROM capacitacion WHERE substr(fecha_fin, 1, 4) = ?",
                                               [str(a)])}
    si = sum(p["id"] in con for p in personas)
    return Resultado(_pct(si, len(personas)), len(personas),
                     f"{si} de {len(personas)} académicos vinculados concluyeron al menos una capacitación en el año.")


def _personal_capacitado_ia(c, a):
    """Como «Personal capacitado», solo con capacitaciones del área «IA y competencias digitales» (PLAN §59)."""
    personas = c.anio(a).cuerpo_personas
    con = {f["usuario_id"] for f in get_db().q(
        "SELECT usuario_id FROM capacitacion WHERE area = 'ia_digital' AND substr(fecha_fin, 1, 4) = ?", [str(a)])}
    si = sum(p["id"] in con for p in personas)
    return Resultado(_pct(si, len(personas)), len(personas),
                     f"{si} de {len(personas)} académicos vinculados concluyeron una capacitación en IA y "
                     "competencias digitales en el año.")


def _convenios_activos(c, a):
    f = get_db().q(
        """SELECT COUNT(*) AS vigentes,
                  COALESCE(SUM(EXISTS (SELECT 1 FROM actividad_convenio x WHERE x.convenio_id = v.id
                                         AND substr(x.fecha, 1, 4) = :a)), 0) AS activos
           FROM convenio v WHERE v.fecha_firma <= :a || '-12-31'
             AND (v.vigente_hasta IS NULL OR v.vigente_hasta >= :a || '-01-01')""", {"a": str(a)})[0]
    return Resultado(f["activos"], f["vigentes"], f"{f['activos']} de {f['vigentes']} convenios vigentes en el año "
                                                  "registraron alguna actividad.")


def _impacto_interaccion_social(c, a):
    ps = [p for p in c.anio(a).regs["proyectos"] if p.get("clase") == "interaccion_social"]
    con = {f["proyecto_id"] for f in get_db().q("SELECT proyecto_id FROM impacto_proyecto WHERE comprobado = 1")}
    si = sum(p["id"] in con for p in ps)
    return Resultado(_pct(si, len(ps)), len(ps), f"{si} de {len(ps)} proyectos de interacción social vigentes en el año "
                                                 "tienen impacto comprobado (con su evidencia).")


@dataclass
class Calculo:
    fn: object = None
    solo_actual: bool = False
    pendiente: str = ""          # por qué aún no se calcula


CALCULOS = {
    "paralelos_con_docente": Calculo(_paralelos),
    "revisiones_calidad_datos": Calculo(_revisiones, solo_actual=True),
    "antiguedad_plan": Calculo(_antiguedad_plan),
    "observaciones_plan": Calculo(_observaciones_plan, solo_actual=True),
    "inscritos_por_paralelo": Calculo(_inscritos_por_paralelo),
    "ingresantes": Calculo(_ingresantes),
    "ingresantes_mujeres": Calculo(_ingresantes_mujeres),
    "retencion_primer_anio": Calculo(_retencion),
    "desercion": Calculo(_desercion),
    "cobertura_tutoria": Calculo(_cobertura_tutoria, solo_actual=True),
    "brecha_desercion_genero": Calculo(_brecha_desercion),
    "variacion_estudiantes_en_proyectos": Calculo(_estudiantes_en_proyectos),
    "actividad_estudiantil": Calculo(_actividad_estudiantil),
    "jce": Calculo(_cuerpo("jce", "Carga contratada / 160")),
    "inscripciones_por_jce": Calculo(_inscripciones_por_jce),
    "pct_doctorado": Calculo(_cuerpo("pct_doctores", "Con doctorado")),
    "pct_posgrado": Calculo(_cuerpo("pct_posgrado", "Con maestría o doctorado")),
    "pct_carga_investigacion": Calculo(_cuerpo("pct_investigacion", "Horas de investigación / horas contratadas")),
    "pct_60_o_mas": Calculo(_pct_60),
    "retencion_doctores": Calculo(_retencion_doctores),
    "proyectos_vigentes": Calculo(_proyectos("investigacion")),
    "pct_con_proyecto": Calculo(_cuerpo("pct_con_proyecto", "Con proyecto vigente")),
    "articulos_indexados": Calculo(_conteo("indexados", "artículos indexados que cuentan")),
    "variacion_indexados": Calculo(_variacion_indexados),
    "indexados_por_jce": Calculo(_indexados_por_jce),
    "citas": Calculo(_citas),
    "tesis_defendidas": Calculo(_conteo("tesis_defendidas", "tesis defendidas")),
    "productos_con_estudiantes": Calculo(_productos_con_estudiantes),
    "variacion_propiedad_intelectual": Calculo(_propiedad_intelectual),
    "transferencia": Calculo(_conteo("transferencia", "actividades de transferencia")),
    "proyectos_interaccion_social": Calculo(_proyectos("interaccion_social")),
    "variacion_transferencia_divulgacion": Calculo(_transferencia_divulgacion),
    "servicios": Calculo(_conteo("servicios", "servicios prestados")),
    "pct_coautoria_internacional": Calculo(_coautoria),
    "redes": Calculo(_conteo("redes", "participaciones en redes")),
    "estancias": Calculo(_conteo("estancias", "estancias y visitas de investigación")),
    "titulacion_oportuna": Calculo(_titulacion_oportuna),
    "tiempo_titulacion": Calculo(_tiempo_titulacion),
    "empleabilidad": Calculo(_egresados("situacion", lambda v: v in egresados.EN_EL_AREA, "trabaja en su área")),
    "continuidad_posgrado": Calculo(_egresados("posgrado", lambda v: v in egresados.POSGRADO, "cursó o cursa un posgrado")),
    "satisfaccion_egresados": Calculo(_egresados("satisfaccion", lambda v: int(v) >= SATISFECHO,
                                                 "de acuerdo o totalmente de acuerdo")),
    "tasa_respuesta_encuestas": Calculo(_tasa_respuesta),
    "autoevaluacion_vigente": Calculo(_autoevaluacion_vigente),
    "acciones_cumplidas": Calculo(_acciones_cumplidas),
    "perfil_titulados": Calculo(_promedio_encuesta("tipo = 'perfil_egreso' AND publico = 'egresados'", None,
                                                   "encuestas de logro del perfil de egreso a titulados")),
    "perfil_empleadores": Calculo(_promedio_encuesta("publico = 'empleadores'", "perfil", "encuestas a empleadores")),
    "satisfaccion_empleadores": Calculo(_satisfaccion_empleadores),
    "personal_capacitado": Calculo(_personal_capacitado),
    "personal_capacitado_ia": Calculo(_personal_capacitado_ia),
    "convenios_activos": Calculo(_convenios_activos),
    "impacto_interaccion_social": Calculo(_impacto_interaccion_social),
    "cumplimiento_objetivos": Calculo(),   # lo arma el tablero con las demás cifras del año
}


def calcular(clave: str, anio: int, calc: Calculadora | None = None) -> Resultado:
    k = CALCULOS[clave]
    if k.pendiente or not k.fn:
        return Resultado(None, None, k.pendiente)
    return k.fn(calc or Calculadora(), anio)


# --- Valores manuales -----------------------------------------------------------------------------------------

def manuales(iid: int) -> dict[int, dict]:
    return {f["anio"]: f for f in get_db().q("SELECT * FROM valor_indicador WHERE indicador_id = ? ORDER BY anio", [iid])}


def validar_valor(anio: str, valor: str, n: str = "", fuente: str = "", nota: str = "") -> tuple[dict, list[str]]:
    x, errores = marco.validar_meta(anio, valor, nota, que="cifra")
    x["fuente"] = (fuente or "").strip() or None
    n = (n or "").strip()
    x["n"] = None
    if n:
        if n.isdigit():
            x["n"] = int(n)
        else:
            errores.append("La base (n) es un número entero.")
    return x, errores


def registrar(iid: int, x: dict, uid: int):
    get_db().execute(
        """INSERT INTO valor_indicador (indicador_id, anio, valor, n, fuente, nota, registrado_por) VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (indicador_id, anio) DO UPDATE SET valor = excluded.valor, n = excluded.n, fuente = excluded.fuente,
             nota = excluded.nota, registrado_por = excluded.registrado_por, registrado_en = datetime('now')""",
        [iid, x["anio"], x["valor"], x["n"], x["fuente"], x["nota"], uid])


def quitar(iid: int, anio: int):
    get_db().execute("DELETE FROM valor_indicador WHERE indicador_id = ? AND anio = ?", [iid, anio])


# --- Tablero ----------------------------------------------------------------------------------------------------

def cierres(mid: int) -> dict[int, dict]:
    return {f["anio"]: f for f in get_db().q(
        """SELECT c.*, u.nombres || ' ' || u.apellidos AS por FROM cierre_calidad c
           LEFT JOIN usuario u ON u.id = c.cerrado_por WHERE c.marco_id = ? ORDER BY c.anio""", [mid])}


def estado(valor, meta, sentido) -> str:
    """Semáforo: cumple, no_cumple, sin_meta, informativo o sin_dato."""
    if sentido == "informativo":
        return "informativo"
    if valor is None:
        return "sin_dato"
    if meta is None:
        return "sin_meta"
    return "cumple" if (valor >= meta if sentido == "mayor" else valor <= meta) else "no_cumple"


def _indicadores(mid: int) -> list[dict]:
    return [i for d in marco.arbol(mid, inactivos=False) for c in d["criterios"] for i in c["indicadores"]]


def _celda(valor, n, detalle, meta, origen, sentido):
    return {"valor": valor, "n": n, "detalle": detalle, "meta": meta, "origen": origen,
            "estado": estado(valor, meta, sentido)}


def _vivo(i: dict, anio: int, calc: Calculadora, hoy: int) -> dict:
    meta = next((m["valor"] for m in i["metas"] if m["anio"] == anio), None)
    if i["fuente"] == "manual":
        v = manuales(i["id"]).get(anio)
        return _celda(v and v["valor"], v and v["n"], (v and (v["fuente"] or v["nota"])) or "", meta,
                      "manual" if v else None, i["sentido"])
    clave = i["fuente"][5:]
    k = CALCULOS.get(clave)
    if k is None:
        return _celda(None, None, "Fuente desconocida.", meta, None, i["sentido"])
    if k.solo_actual and anio < hoy:
        g = get_db().q("SELECT * FROM valor_automatico WHERE indicador_id = ? AND anio = ?", [i["id"], anio])
        if not g:
            return _celda(None, None, "Esta cifra solo se mide «a hoy» y el sistema no la guardó en ese año.", meta,
                          None, i["sentido"])
        return _celda(g[0]["valor"], g[0]["n"], g[0]["detalle"] or "", meta, "instantanea", i["sentido"])
    if k.solo_actual and anio > hoy:
        return _celda(None, None, "", meta, None, i["sentido"])
    r = calcular(clave, anio, calc)
    return _celda(r.valor, r.n, r.detalle, meta, "calculado" if r.valor is not None else None, i["sentido"])


def _cumplimiento(celdas: dict[int, dict], excluir: int) -> Resultado:
    evaluados = [c for iid, c in celdas.items() if iid != excluir and c["estado"] in ("cumple", "no_cumple")]
    si = sum(c["estado"] == "cumple" for c in evaluados)
    return Resultado(_pct(si, len(evaluados)), len(evaluados), f"{si} de {len(evaluados)} indicadores con meta y cifra "
                                                               "la cumplen.")


def valores_del_anio(mid: int, anio: int, calc: Calculadora | None = None) -> dict[int, dict]:
    """Cifra, n, detalle, meta y semáforo de cada indicador activo en el año (congelados si el año está cerrado)."""
    inds = _indicadores(mid)
    cierre = cierres(mid).get(anio)
    if cierre:
        guardados = {f["indicador_id"]: f for f in get_db().q("SELECT * FROM valor_cierre WHERE cierre_id = ?",
                                                              [cierre["id"]])}
        return {i["id"]: _celda(g["valor"], g["n"], g["detalle"] or "", g["meta"], "cierre", i["sentido"])
                if (g := guardados.get(i["id"])) else _celda(None, None, "No estaba en el marco al cerrar el año.", None,
                                                            None, i["sentido"])
                for i in inds}
    calc = calc or Calculadora(marco.obtener(mid)["ventana_anios"], mid)
    hoy = date.today().year
    res = {i["id"]: _vivo(i, anio, calc, hoy) for i in inds}
    for i in inds:
        if i["fuente"] == "auto:cumplimiento_objetivos":
            r = _cumplimiento(res, i["id"])
            res[i["id"]] = _celda(r.valor, r.n, r.detalle, res[i["id"]]["meta"], "calculado", i["sentido"])
    return res


def serie(i: dict, anios: list[int]) -> dict[int, dict]:
    """Las cifras de un indicador (activo o no) en los años; solo calcula ese indicador, salvo el cumplimiento de
    las metas, que depende de los demás."""
    if i["fuente"] == "auto:cumplimiento_objetivos":
        return {a: valores_del_anio(i["marco_id"], a).get(i["id"]) or _celda(None, None, "", None, None, i["sentido"])
                for a in anios}
    calc = Calculadora(marco.obtener(i["marco_id"])["ventana_anios"], i["marco_id"])
    hoy, cerrados = date.today().year, cierres(i["marco_id"])
    res = {}
    for a in anios:
        if a in cerrados:
            g = get_db().q("SELECT * FROM valor_cierre WHERE cierre_id = ? AND indicador_id = ?",
                           [cerrados[a]["id"], i["id"]])
            res[a] = (_celda(g[0]["valor"], g[0]["n"], g[0]["detalle"] or "", g[0]["meta"], "cierre", i["sentido"]) if g
                      else _celda(None, None, "No estaba en el marco al cerrar el año.", None, None, i["sentido"]))
        else:
            res[a] = _vivo(i, a, calc, hoy)
    return res


def anios_de(m: dict, hasta: int | None = None) -> list[int]:
    """Los años de la ventana de evidencia del marco que terminan en `hasta` (por omisión, el año en curso)."""
    hasta = hasta or date.today().year
    return list(range(hasta - m["ventana_anios"] + 1, hasta + 1))


def tablero(mid: int, desde: int, hasta: int) -> dict:
    """El marco (solo indicadores activos) con las cifras de cada año de la ventana."""
    calc = Calculadora(marco.obtener(mid)["ventana_anios"], mid)
    anios = list(range(desde, hasta + 1))
    por_anio = {a: valores_del_anio(mid, a, calc) for a in anios}
    arbol = marco.arbol(mid, inactivos=False)
    for d in arbol:
        for c in d["criterios"]:
            for i in c["indicadores"]:
                i["celdas"] = {a: por_anio[a][i["id"]] for a in anios}
                i["ultima"] = next((i["celdas"][a] for a in reversed(anios) if i["celdas"][a]["valor"] is not None), None)
    estados = [i["ultima"]["estado"] if i["ultima"] else "sin_dato"
               for d in arbol for c in d["criterios"] for i in c["indicadores"]]
    return {"anios": anios, "arbol": arbol, "cierres": cierres(mid),
            "conteo": {e: estados.count(e) for e in ("cumple", "no_cumple", "sin_meta", "informativo", "sin_dato")}}


def a_xlsx(mid: int, t: dict) -> bytes:
    from app.comun import exportar
    filas = []
    for d in t["arbol"]:
        for c in d["criterios"]:
            for i in c["indicadores"]:
                f = {"dimension": d["codigo"], "criterio": c["codigo"], "codigo": i["codigo"], "indicador": i["nombre"],
                     "unidad": i["unidad_medida"] or "", "lectura": marco.SENTIDOS[i["sentido"]]}
                for a in t["anios"]:
                    x = i["celdas"][a]
                    f[f"{a}"] = "" if x["valor"] is None else x["valor"]
                    f[f"n {a}"] = "" if x["n"] is None else x["n"]
                    f[f"meta {a}"] = "" if x["meta"] is None else x["meta"]
                    f[f"estado {a}"] = ESTADOS[x["estado"]]
                filas.append(f)
    metodo = [{"codigo": i["codigo"], "indicador": i["nombre"], "formula": i["formula"] or "",
               "fuente": marco.fuente_texto(i["fuente"]), "frecuencia": marco.FRECUENCIAS[i["frecuencia"]],
               "responsable": i["responsable"] or ""}
              for d in t["arbol"] for c in d["criterios"] for i in c["indicadores"]]
    detalle = [{"codigo": i["codigo"], "anio": a, "origen": ORIGENES.get(i["celdas"][a]["origen"], ""),
                "detalle": i["celdas"][a]["detalle"]}
               for d in t["arbol"] for c in d["criterios"] for i in c["indicadores"] for a in t["anios"]
               if i["celdas"][a]["detalle"]]
    cierres_ = [{"anio": a, "cerrado_en (UTC)": x["cerrado_en"], "por": x["por"] or "", "nota": x["nota"] or ""}
                for a, x in t["cierres"].items()]
    return exportar.a_xlsx({"Indicadores": filas, "Detalle": detalle, "Método": metodo, "Cierres": cierres_})


ESTADOS = {"cumple": "Cumple la meta", "no_cumple": "No cumple la meta", "sin_meta": "Sin meta",
           "informativo": "Informativo", "sin_dato": "Sin dato"}
ORIGENES = {"calculado": "Calculado por el sistema", "manual": "Registrado a mano",
            "instantanea": "Guardado por el sistema durante el año", "cierre": "Congelado al cerrar el año"}


# --- Cierres e instantáneas ------------------------------------------------------------------------------------

def cerrar(mid: int, anio: int, uid: int, nota: str = "") -> int | None:
    """Congela las cifras y metas del año. Solo un año ya terminado y aún no cerrado (→ None si no se puede)."""
    if anio >= date.today().year or anio in cierres(mid):
        return None
    valores = valores_del_anio(mid, anio)
    with transaccion():
        cid = get_db().t.cierre_calidad.insert(marco_id=mid, anio=anio, cerrado_por=uid, nota=nota.strip() or None)["id"]
        for iid, x in valores.items():
            get_db().t.valor_cierre.insert(cierre_id=cid, indicador_id=iid, valor=x["valor"], n=x["n"],
                                           detalle=x["detalle"] or None, meta=x["meta"])
    return cid


def reabrir(mid: int, anio: int) -> bool:
    c = cierres(mid).get(anio)
    if not c:
        return False
    get_db().execute("DELETE FROM cierre_calidad WHERE id = ?", [c["id"]])
    return True


def guardar_instantaneas() -> int:
    """Guarda la cifra del año en curso de los indicadores activos «a hoy» de todos los marcos. → cuántos."""
    anio, calc, n = date.today().year, Calculadora(), 0
    claves = [k for k, v in CALCULOS.items() if v.solo_actual]
    filas = get_db().q(
        f"""SELECT id, fuente FROM indicador_calidad WHERE activo = 1
            AND fuente IN ({','.join('?' * len(claves))})""", [f"auto:{k}" for k in claves])
    for f in filas:
        r = calcular(f["fuente"][5:], anio, calc)
        get_db().execute(
            """INSERT INTO valor_automatico (indicador_id, anio, valor, n, detalle) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (indicador_id, anio) DO UPDATE SET valor = excluded.valor, n = excluded.n,
                 detalle = excluded.detalle, calculado_en = datetime('now')""",
            [f["id"], anio, r.valor, r.n, r.detalle])
        n += 1
    return n


_ultima_instantanea: float | None = None


def mantenimiento():
    """Lo llama el mantenimiento de main.py (que ya impide dos a la vez): a lo más una instantánea por día."""
    global _ultima_instantanea
    if _ultima_instantanea is not None and time.monotonic() - _ultima_instantanea < 24 * 3600:
        return
    _ultima_instantanea = time.monotonic()
    guardar_instantaneas()
