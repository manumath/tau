"""Anexo de seguimiento estudiantil para la acreditación (PLAN §49 y §50, etapa 5): solo cifras agregadas, sin nombres ni
datos personales. Reúne cohortes, actividad estudiantil verificada, encuestas, tutoría, egresados y directorio y mentoría.

Las encuestas anónimas con menos de `encuestas.MIN_ANONIMO` respuestas no muestran promedios, igual que en su pantalla. Las
notas de tutoría nunca entran: solo cuántas reuniones y derivaciones hay."""
from datetime import date

from app.comun.db import get_db
from app.egresados import directorio, egresados
from app.estudiantil import actividad, cohortes, encuestas, tutoria


def ventana_por_omision() -> tuple[int, int]:
    hoy = date.today().year
    return hoy - 9, hoy


def _cohortes(desde: int, hasta: int) -> dict:
    ciclos = [cohortes.ordinal(a, t) for a in range(desde, hasta + 1) for t in ("I", "II")]
    filas = []
    for c in cohortes.resumen(ciclos):
        if not c["n"]:
            continue
        e = c["estados"]
        egresaron = e["egresado"] + e["titulado"]
        filas.append({"cohorte": c["texto"], "ingresaron": c["n"], "cursan": e["cursando"] + e["congelado"], "egresaron": egresaron,
                      "titulados": e["titulado"], "desertores": c["desertores"],
                      "tasa_egreso": cohortes.tasa(egresaron, c["n"]), "tasa_titulacion": cohortes.tasa(e["titulado"], c["n"]),
                      "tasa_desercion": cohortes.tasa(c["desertores"], c["n"])})
    return {"filas": filas, "totales": cohortes.indicadores([a for a in cohortes.alumnos() if desde <= a["cohorte_anio"] <= hasta])}


def _actividad(desde: int, hasta: int) -> dict:
    anios = list(range(desde, hasta + 1))
    por_anio = {a: actividad.resumen_verificadas(a, a) for a in anios}
    tipos = [t for t in actividad.TIPOS if any(por_anio[a].get(t) for a in anios)]
    return {"anios": anios, "tipos": tipos, "por_anio": por_anio,
            "total": sum(sum(v.values()) for v in por_anio.values()), "pendientes": actividad.n_pendientes()}


def _encuestas(desde: int, hasta: int) -> list[dict]:
    filas = []
    for e in encuestas.listar():
        anio = (e["abierta_en"] or "")[:4]
        if e["estado"] == "borrador" or not anio.isdigit() or not desde <= int(anio) <= hasta:
            continue
        r = encuestas.resultados(e["id"])
        medias = [p["promedio"] for p in r["preguntas"] if p["pregunta"]["tipo"] == "escala" and p["promedio"] is not None]
        filas.append({"titulo": e["titulo"], "tipo": encuestas.TIPOS[e["tipo"]], "publico": encuestas.PUBLICOS[e["publico"]],
                      "modalidad": "Anónima" if e["anonima"] else "Nominal", "estado": encuestas.ESTADOS[e["estado"]],
                      "anio": int(anio), "invitadas": r["invitadas"], "respondieron": r["n"], "tasa": r["tasa"],
                      "promedio_escalas": None if r["oculto"] or not medias else sum(medias) / len(medias),
                      "oculto": r["oculto"]})
    return sorted(filas, key=lambda f: (f["anio"], f["titulo"]))


def informe(desde: int, hasta: int) -> dict:
    return {"desde": desde, "hasta": hasta, "cohortes": _cohortes(desde, hasta), "actividad": _actividad(desde, hasta),
            "encuestas": _encuestas(desde, hasta), "tutoria": tutoria.indicadores(), "egresados": egresados.indicadores(),
            "seguimiento": egresados.estado_seguimiento(), "directorio": directorio.indicadores(),
            "estudiantes_con_cuenta": get_db().q("SELECT COUNT(*) n FROM cuenta_estudiante")[0]["n"]}


def _pct(x) -> str:
    return "" if x is None else f"{x * 100:.0f} %"


def filas_xlsx(i: dict) -> dict[str, list[dict]]:
    c, a, t, e = i["cohortes"], i["actividad"], i["tutoria"], i["egresados"]
    return {
        "Cohortes": [{"Cohorte": f["cohorte"], "Ingresaron": f["ingresaron"], "Cursan": f["cursan"], "Egresaron": f["egresaron"],
                      "Titulados": f["titulados"], "Desertores": f["desertores"], "Tasa de egreso": _pct(f["tasa_egreso"]),
                      "Tasa de titulación": _pct(f["tasa_titulacion"]), "Tasa de deserción": _pct(f["tasa_desercion"])}
                     for f in c["filas"]],
        "Actividad estudiantil": [{"Tipo": actividad.TIPOS[tp], **{str(an): a["por_anio"][an].get(tp, 0) for an in a["anios"]}}
                                  for tp in a["tipos"]],
        "Encuestas": [{"Encuesta": f["titulo"], "Tipo": f["tipo"], "Público": f["publico"], "Modalidad": f["modalidad"],
                       "Estado": f["estado"], "Año": f["anio"], "Invitadas": f["invitadas"], "Respondieron": f["respondieron"],
                       "Tasa de respuesta": _pct(f["tasa"]),
                       "Promedio de las preguntas de escala (1 a 5)": ("" if f["promedio_escalas"] is None else round(f["promedio_escalas"], 2)),
                       "Nota": f"Menos de {encuestas.MIN_ANONIMO} respuestas: resultados reservados" if f["oculto"] else ""}
                      for f in i["encuestas"]],
        "Tutoría": [{"Indicador": "Estudiantes que cursan", "Valor": t["cursando"]},
                    {"Indicador": "Con tutor asignado", "Valor": t["con_tutor"]}, {"Indicador": "Cobertura", "Valor": _pct(t["cobertura"])},
                    {"Indicador": "Tutores con estudiantes", "Valor": t["tutores"]},
                    {"Indicador": "Reuniones registradas", "Valor": t["reuniones"]},
                    {"Indicador": "Con tutor y sin reunión en 12 meses", "Valor": t["sin_reunion_12m"]},
                    *[{"Indicador": f"Reuniones en {an}", "Valor": n} for an, n in t["por_anio"].items()],
                    *[{"Indicador": f"Tema: {tm}", "Valor": n} for tm, n in t["temas"].items()],
                    *[{"Indicador": f"Derivación: {d}", "Valor": n} for d, n in t["derivaciones"].items()]],
        "Egresados": [{"Titulados en": f"{x['desde']}–{x['hasta']}", "Titulados": x["titulados"],
                       "Años hasta titularse": round(x["anios_medios"], 1), "Respondieron el seguimiento": x["respondieron"],
                       "Con empleo": _pct(x["empleo"]), "n (situación laboral)": x["n_situacion"], "En su área": _pct(x["en_el_area"]),
                       "Con posgrado": _pct(x["posgrado"]), "n (posgrado)": x["n_posgrado"],
                       "Utilidad de la formación (1 a 5)": "" if x["utilidad"] is None else round(x["utilidad"], 2),
                       "Satisfacción (1 a 5)": "" if x["satisfaccion"] is None else round(x["satisfaccion"], 2)} for x in e["trienios"]],
        "Seguimiento de egresados": [{"Hito": s["nombre"], "Invitados": s["invitados"], "Respondieron": s["respondidos"],
                                      "Omitidos": s["omitidos"]} for s in i["seguimiento"]],
        "Directorio y mentoría": [{"Indicador": "Egresados invitados al directorio", "Valor": i["directorio"]["invitados"]},
                                  {"Indicador": "Egresados que figuran", "Valor": i["directorio"]["visibles"]},
                                  {"Indicador": "Solicitudes de estudiantes", "Valor": i["directorio"]["solicitudes"]},
                                  {"Indicador": "Solicitudes aceptadas", "Valor": i["directorio"]["aceptadas"]},
                                  *[{"Indicador": f"Solicitudes de: {tp}", "Valor": n} for tp, n in i["directorio"]["por_tipo"].items()]],
    }
