"""Datos de los informes (CV, informe de proyecto, memoria anual) y exportación a CSV/XLSX.

Reglas:
- Un producto pertenece al periodo según su año; una actividad, según su fecha de inicio; un
  proyecto, si su vigencia se cruza con el periodo.
- La memoria anual del instituto cuenta solo los productos que «cuentan para el informe»
  (indexados o arbitrados, aceptados o publicados). Cada producto se cuenta una vez, aunque
  tenga varios autores del instituto.
"""
import csv
import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from app.investigacion import (actividades, filiacion, institucionales, lineas, perfiles, productos, proyectos,
                               revistas)
from app.comun import config, vinculos
from app.comun.db import get_db

# Categorías del CV, en orden de aparición. La primera que corresponde es la que se usa.
CATEGORIAS = [
    ("indexados", "Artículos en revistas indexadas"),
    ("arbitrados", "Artículos arbitrados"),
    ("libros", "Libros y capítulos de libro"),
    ("en_curso", "Trabajos enviados o en preparación"),
    ("reportes", "Reportes de investigación"),
    ("preprints", "Preprints"),
    ("presentaciones", "Presentaciones"),
    ("tesis", "Tesis dirigidas"),
    ("patentes", "Patentes"),
    ("traducciones", "Traducciones"),
    ("otros", "Otros productos"),
]


def categoria(p: dict) -> str:
    if p["tipo"] in ("Patente", "Traducción"):  # la solicitud en trámite también es patente
        return "patentes" if p["tipo"] == "Patente" else "traducciones"
    if p["tipo"] == "Tesis dirigida":  # en curso o defendida
        return "tesis"
    if p["estado_publicacion"] in ("enviado", "en_preparacion"):
        return "en_curso"
    if p["tipo"] in ("Libro", "Capítulo de libro"):
        return "libros"
    if p["revision"] == "indexado":
        return "indexados"
    if p["revision"] == "arbitrado":
        return "arbitrados"
    return {"Reporte de investigación": "reportes", "Preprint": "preprints",
            "Presentación": "presentaciones"}.get(p["tipo"], "otros")


def periodo_valido(desde: str, hasta: str) -> tuple[int, int]:
    """Normaliza el rango de años (por omisión, los últimos 5 años)."""
    actual = date.today().year
    d = int(desde) if str(desde).isdigit() else actual - 4
    h = int(hasta) if str(hasta).isdigit() else actual
    return (min(d, h), max(d, h))


def _en_periodo_actividad(a, desde, hasta):
    return desde <= int(a["fecha_inicio"][:4]) <= hasta


def _en_periodo_proyecto(p, desde, hasta):
    ini = int(p["fecha_inicio"][:4]) if p["fecha_inicio"] else 0
    fin = int(p["fecha_fin"][:4]) if p["fecha_fin"] else 9999
    return ini <= hasta and fin >= desde


# --- CV ----------------------------------------------------------------------------------------

def cv(uid: int, desde: int, hasta: int, solo_informe: bool = False, solo_filiacion: bool = False) -> dict:
    """CV personal: toda su producción del periodo (también la anterior a su ingreso). Con
    `solo_filiacion`, solo los productos que firmó con la filiación del instituto."""
    perfil = perfiles.obtener(uid)
    prods = [p for p in productos.de_investigador(uid) if desde <= p["anio"] <= hasta
             and productos.es_autor(p["id"], uid)]  # en el CV, solo aquello de lo que es autor
    if solo_informe:
        prods = [p for p in prods if productos.cuenta_para_informe(p)]
    if solo_filiacion:
        prods = [p for p in prods if any(a["interno"] and a["id"] == uid and a.get("filiacion") == 1
                                         for a in p["autores"])]
    grupos = {clave: [] for clave, _ in CATEGORIAS}
    for p in prods:
        grupos[categoria(p)].append(p)
    acts = [a for a in actividades.de_investigador(uid)
            if _en_periodo_actividad(a, desde, hasta) and a["mi_rol"]]
    por_tipo = {}
    for a in acts:
        por_tipo.setdefault(a["tipo"], []).append(a)
    proys = [p for p in proyectos.de_investigador(uid) if _en_periodo_proyecto(p, desde, hasta)]
    return {"perfil": perfil, "areas": perfiles.areas(uid), "grupos": grupos,
            "actividades": por_tipo, "proyectos": proys,
            "n_productos": len(prods), "n_informe": sum(productos.cuenta_para_informe(p) for p in prods),
            "n_actividades": len(acts)}


# --- Informe de proyecto ----------------------------------------------------------------------------

def informe_proyecto(pid: int, desde: int, hasta: int) -> dict:
    p = proyectos.obtener(pid)
    prods = []
    for v in proyectos.registros(pid, "producto"):
        x = productos.obtener(v["registro_id"])
        # Requisitos de los fondos: filiación IIMAT/UMSA y agradecimiento al proyecto.
        fil, agr = filiacion.estado_producto(x), v["agradece"]
        faltan = [t for ok, t in ((fil == 1, {0: "sin filiación del instituto", None: "filiación sin declarar"}.get(fil)),
                                  (agr == 1, {0: "no agradece al proyecto", None: "agradecimiento sin declarar"}.get(agr)))
                  if not ok]
        prods.append({**x, "filiacion_estado": fil, "agradece": agr, "requisitos_faltan": faltan})
    prods = sorted((x for x in prods if desde <= x["anio"] <= hasta), key=lambda x: (-x["anio"], x["titulo"]))
    acts = []
    participantes = {x["participante_id"]: x for x in proyectos.participantes(pid)}
    for v in proyectos.registros(pid, "actividad"):
        a = actividades.obtener(v["registro_id"])
        if _en_periodo_actividad(a, desde, hasta):
            acts.append({**a, "responsable": participantes.get(v["responsable_participante_id"])})
    acts.sort(key=lambda a: a["fecha_inicio"], reverse=True)
    return {"proyecto": p, "objetivos": proyectos.objetivos(pid),
            "participantes": proyectos.participantes(pid),
            "productos_informe": [x for x in prods if productos.cuenta_para_informe(x)],
            "productos_otros": [x for x in prods if not productos.cuenta_para_informe(x)],
            "n_cumplen": sum(not x["requisitos_faltan"] for x in prods if productos.cuenta_para_informe(x)),
            "actividades": acts,
            "plan": institucionales.plan(pid, desde, hasta) if p["tipo"] == "institucional" else []}


# --- Memoria anual ------------------------------------------------------------------------------------

MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]


def _fecha_corta(iso: str) -> str:
    return f"{int(iso[8:10])} {MESES_CORTOS[int(iso[5:7]) - 1]} {iso[:4]}"


def rango(anio=None, periodo=None, desde=None, hasta=None) -> dict:
    """Periodo de una memoria: año calendario, periodo oct–sep (año de inicio) o rango libre.
    → {'desde', 'hasta', 'titulo', 'nombre' (para archivos), 'params' (para URLs)}."""
    if periodo is not None:
        return {"desde": f"{periodo}-10-01", "hasta": f"{periodo + 1}-09-30", "params": {"periodo": periodo},
                "titulo": f"Memoria del periodo {periodo}–{periodo + 1} (octubre a septiembre)",
                "nombre": f"memoria-{periodo}-{periodo + 1}"}
    if desde and hasta:
        return {"desde": desde, "hasta": hasta, "params": {"desde": desde, "hasta": hasta},
                "titulo": f"Memoria del {_fecha_corta(desde)} al {_fecha_corta(hasta)}",
                "nombre": f"memoria-{desde}-a-{hasta}"}
    anio = anio or date.today().year
    return {"desde": f"{anio}-01-01", "hasta": f"{anio}-12-31", "params": {"anio": anio},
            "titulo": f"Memoria anual {anio}", "nombre": f"memoria-{anio}"}


def ubicar_producto(p: dict, desde: str, hasta: str) -> str:
    """'dentro', 'fuera' o 'dudoso' (sin mes y con el año solo en parte dentro del rango)."""
    if p.get("mes"):
        fecha = f"{p['anio']}-{p['mes']:02d}"
        return "dentro" if desde[:7] <= fecha <= hasta[:7] else "fuera"
    ini, fin = f"{p['anio']}-01-01", f"{p['anio']}-12-31"
    if desde <= ini and fin <= hasta:
        return "dentro"
    return "fuera" if fin < desde or ini > hasta else "dudoso"


def otros_resultados(desde: str, hasta: str, tipos=("Patente", "Traducción")) -> list[dict]:
    """Otros resultados de I+D+i (IAC-CINDA 3.6.3 d, e) de autores vinculados en la fecha."""
    marcas = ",".join("?" * len(tipos))
    res = []
    for f in get_db().q(f"""SELECT p.id FROM producto p JOIN tipo_producto t ON t.id = p.tipo_id
                            WHERE t.nombre IN ({marcas}) AND p.anio BETWEEN ? AND ?
                            ORDER BY t.nombre, p.anio""", [*tipos, int(desde[:4]), int(hasta[:4])]):
        x = productos.obtener(f["id"])
        if ubicar_producto(x, desde, hasta) == "dentro" and any(
                a["interno"] and vinculos.en_fecha(a["id"], x["anio"], x["mes"])[0] == "si" for a in x["autores"]):
            res.append(x)
    return res


def memoria(anio: int | None = None, *, periodo: int | None = None, desde: str | None = None,
            hasta: str | None = None, exigir_verificada: bool | None = None) -> dict:
    """Productos que cuentan, actividades con participación del instituto, proyectos vigentes y
    resúmenes por categoría y por investigador, en un año calendario, un periodo oct–sep o un
    rango de fechas.

    Los productos se ubican por año y mes de publicación. Uno sin mes cuyo año cae solo en parte
    dentro del rango (p. ej., 2026 en el periodo oct 2026 – sept 2027) no se cuenta: queda en
    `por_confirmar`, para completar su mes.

    Un autor o participante del instituto figura con un registro si tenía **vínculo** en su fecha
    (año y mes de publicación; inicio de la actividad), con la categoría de ese momento, y, en los
    productos, si **firmó con la filiación** del instituto (IIMAT/UMSA). Si era
    «Externo», además el registro debe estar aprobado en un proyecto institucional vigente en el
    periodo. Un registro cuenta si al menos una persona figura. Un producto que podría contar si se
    completa un dato (mes, vínculo parcial, filiación sin declarar) queda «por confirmar».
    """
    periodo_memoria = rango(anio, periodo, desde, hasta)
    exigir = config.EXIGIR_REVISTA_VERIFICADA if exigir_verificada is None else exigir_verificada
    desde, hasta = periodo_memoria["desde"], periodo_memoria["hasta"]
    ligados = {"producto": proyectos.ligados_a_institucionales("producto", desde, hasta),
               "actividad": proyectos.ligados_a_institucionales("actividad", desde, hasta)}
    # Autores sin ningún periodo de vínculo registrado (su producción no cuenta: se advierte).
    sin_vinculo = set()

    def situacion(uid, tipo, rid, estado_cat):
        """(estado, categoría a la fecha) de un autor o participante del instituto:
        'si' figura; 'dudoso' su vínculo cubre solo parte del año (producto sin mes); 'no'."""
        estado, cat = estado_cat
        if estado == "no" and not vinculos.listar(uid):
            sin_vinculo.add(uid)
        if estado == "si" and cat == "externo" and rid not in ligados[tipo]:
            return "no", cat
        return estado, cat

    ids = [f["id"] for f in get_db().q(
        """SELECT DISTINCT p.id FROM producto p JOIN producto_autor pa ON pa.producto_id = p.id
           WHERE p.anio BETWEEN ? AND ? AND pa.investigador_id IS NOT NULL
             AND p.revision IN ('indexado', 'arbitrado')
             AND p.estado_publicacion IN ('aceptado', 'publicado')
           ORDER BY p.revision, p.id""", [int(desde[:4]), int(hasta[:4])])]
    # Autores del instituto que figuran con cada producto: id → {usuario: categoría a la fecha}.
    internos_prod, prods, por_confirmar = {}, [], []
    for i in ids:
        x = productos.obtener(i)
        lugar = ubicar_producto(x, desde, hasta)
        if lugar == "fuera":
            continue
        estados = {a["id"]: (*situacion(a["id"], "producto", i, vinculos.en_fecha(a["id"], x["anio"], x["mes"])),
                             a.get("filiacion"))
                   for a in x["autores"] if a["interno"]}
        # Figura quien estaba vinculado en la fecha y firmó con la filiación del instituto.
        figuran = {u: c for u, (e, c, f) in estados.items() if e == "si" and f == 1}
        # Podría figurar si se completa un dato: el mes, el vínculo parcial o la filiación.
        posibles = [(e, f) for e, _, f in estados.values() if e in ("si", "dudoso") and f != 0]
        sin_verificar = (exigir and x["tipo"] == revistas.TIPO_ARTICULO
                         and not x["clasificacion_catalogo"])
        if lugar == "dentro" and figuran and not sin_verificar:
            internos_prod[i] = figuran
            prods.append(x)
        elif lugar == "dentro" and figuran:
            por_confirmar.append({**x, "motivo": "revista sin verificar en el catálogo"})
        elif figuran or posibles:
            motivos = []
            if lugar == "dudoso":
                motivos.append("sin mes de publicación")
            if not figuran and any(e == "dudoso" for e, _ in posibles):
                motivos.append("el vínculo del autor cubre solo parte del año: indique el mes")
            if not figuran and any(f is None for _, f in posibles):
                motivos.append("filiación sin declarar")
            por_confirmar.append({**x, "motivo": "; ".join(motivos)})
    prods.sort(key=lambda p: (p["revision"] != "indexado", p["tipo"], p["titulo"]))

    # Revistas de los artículos que cuentan: ámbito, acceso abierto, cuartil y origen del dato.
    articulos = [p for p in prods if p["tipo"] == revistas.TIPO_ARTICULO]
    por_ambito_revista, por_cuartil, n_abierto, n_declarados = {}, {}, 0, 0
    for p in articulos:
        p["detalle_revista"] = d = revistas.detalle(p)
        por_ambito_revista[d["ambito"]] = por_ambito_revista.get(d["ambito"], 0) + 1
        if d["cuartil"]:
            por_cuartil[d["cuartil"]] = por_cuartil.get(d["cuartil"], 0) + 1
        n_abierto += d["acceso_abierto"] == 1
        n_declarados += not p["clasificacion_catalogo"]
    con_citas = [p for p in prods if p.get("citas") is not None]
    impacto = {"citas": sum(p["citas"] for p in con_citas), "con_datos": len(con_citas), "productos": len(prods),
               "actualizadas": max((p["citas_actualizadas"] for p in con_citas if p.get("citas_actualizadas")), default=None)}
    revistas_memoria = {"articulos": len(articulos), "por_ambito": por_ambito_revista,
                        "por_cuartil": dict(sorted(por_cuartil.items())), "acceso_abierto": n_abierto,
                        "declarados": n_declarados, "catalogo": len(articulos) - n_declarados,
                        "exige_verificada": exigir, "politica": revistas.politica_indices()}

    otros = otros_resultados(desde, hasta)

    internos_act = {}
    for r in get_db().q(
            """SELECT DISTINCT a.id, a.fecha_inicio FROM actividad a
               JOIN actividad_participante ap ON ap.actividad_id = a.id
               WHERE a.fecha_inicio BETWEEN ? AND ? AND ap.investigador_id IS NOT NULL
               ORDER BY a.fecha_inicio""", [desde, hasta]):
        quienes = {}
        for x in actividades.participantes(r["id"]):
            if x["interno"]:
                e, c = situacion(x["id"], "actividad", r["id"], vinculos.en_dia(x["id"], r["fecha_inicio"]))
                if e == "si":
                    quienes[x["id"]] = c
        if quienes:
            internos_act[r["id"]] = quienes
    acts = [actividades.obtener(i) for i in internos_act]
    proys = [p for p in proyectos.todos() if p["estado"] != "formulacion"
             and (not p["fecha_inicio"] or p["fecha_inicio"] <= hasta) and (not p["fecha_fin"] or p["fecha_fin"] >= desde)]
    proys.sort(key=lambda p: p["tipo"] != "institucional")

    por_indice, por_tipo_act, por_ambito = {}, {}, {}
    for p in prods:
        for i in p["indices"]:
            por_indice[i["nombre"]] = por_indice.get(i["nombre"], 0) + 1
    for a in acts:
        por_tipo_act[a["tipo"]] = por_tipo_act.get(a["tipo"], 0) + 1
        por_ambito[a["ambito"]] = por_ambito.get(a["ambito"], 0) + 1

    # Quienes estuvieron vinculados en algún momento del periodo (aunque ya no lo estén), con su
    # categoría al final del periodo (o al término de su vínculo, si terminó antes).
    resumen = []
    for inv in get_db().q(
            """SELECT DISTINCT u.id, u.nombres, u.apellidos FROM usuario u JOIN vinculo v ON v.usuario_id = u.id
               WHERE (v.fecha_inicio IS NULL OR v.fecha_inicio <= ?) AND (v.fecha_fin IS NULL OR v.fecha_fin >= ?)
               ORDER BY sin_tildes(u.apellidos), sin_tildes(u.nombres)""", [hasta, desde]):
        periodos = [v for v in vinculos.listar(inv["id"])
                    if (v["fecha_inicio"] or "0000") <= hasta and (v["fecha_fin"] or "9999") >= desde]
        ultimo = periodos[-1]
        n_p = sum(inv["id"] in q for q in internos_prod.values())
        n_a = sum(inv["id"] in q for q in internos_act.values())
        # Los externos figuran solo si tienen algo ligado a un proyecto institucional.
        if ultimo["categoria"] != "externo" or n_p or n_a:
            resumen.append({**inv, "categoria": ultimo["categoria"], "productos": n_p, "actividades": n_a,
                            "hasta": ultimo["fecha_fin"] if ultimo["fecha_fin"] and ultimo["fecha_fin"] < hasta else None,
                            "ingreso_sin_fecha": any(not v["fecha_inicio"] for v in periodos)})

    # Por categoría: cada producto o actividad cuenta una vez por categoría (la de sus autores a la
    # fecha del registro), aunque tenga varias personas de esa categoría. Los investigadores se
    # cuentan con su categoría al final del periodo.
    por_categoria = {}
    for cat in perfiles.CATEGORIAS:
        n_inv = sum(x["categoria"] == cat for x in resumen)
        n_p = sum(cat in q.values() for q in internos_prod.values())
        n_a = sum(cat in q.values() for q in internos_act.values())
        if n_inv or n_p or n_a:
            por_categoria[perfiles.CATEGORIAS[cat]] = {"investigadores": n_inv, "productos": n_p, "actividades": n_a}
    avisos = []
    sin_fecha = [x for x in resumen if x["ingreso_sin_fecha"]]
    if sin_fecha:
        avisos.append("Sin fecha de ingreso registrada (se asume vinculación desde siempre): "
                      + ", ".join(f"{x['nombres']} {x['apellidos']}" for x in sin_fecha) + ".")
    if sin_vinculo:
        nombres = get_db().q(f"SELECT nombres, apellidos FROM usuario WHERE id IN ({','.join('?' * len(sin_vinculo))})"
                             " ORDER BY apellidos", list(sin_vinculo))
        avisos.append("Sin vínculo registrado (su producción no cuenta): "
                      + ", ".join(f"{x['nombres']} {x['apellidos']}" for x in nombres) + ".")
    return {**periodo_memoria, "anio": anio, "productos": prods, "otros_resultados": otros,
            "revistas": revistas_memoria, "impacto": impacto, "actividades": acts, "proyectos": proys,
            "por_confirmar": sorted(por_confirmar, key=lambda p: (p["anio"], p["titulo"])), "avisos": avisos,
            "n_indexados": sum(p["revision"] == "indexado" for p in prods),
            "n_arbitrados": sum(p["revision"] == "arbitrado" for p in prods),
            "por_indice": dict(sorted(por_indice.items(), key=lambda x: -x[1])),
            "por_tipo_actividad": dict(sorted(por_tipo_act.items(), key=lambda x: -x[1])),
            "por_ambito": por_ambito, "por_investigador": resumen, "por_categoria": por_categoria}


def anios_con_datos() -> list[int]:
    filas = get_db().q("""SELECT anio FROM producto UNION SELECT CAST(substr(fecha_inicio, 1, 4) AS INTEGER)
                          FROM actividad ORDER BY 1 DESC""")
    anios = [r["anio"] for r in filas if r["anio"]]
    return anios or [date.today().year]


# --- Exportación -------------------------------------------------------------------------------------------

def _autores_texto(p, solo_internos=False):
    return "; ".join(f"{a['apellidos']}, {a['nombres']}" for a in p["autores"]
                     if a["interno"] or not solo_internos)


def filas_productos(prods: list[dict]) -> list[dict]:
    filas = []
    for p in prods:
        r = revistas.detalle(p)
        filas.append({
            "Año": p["anio"], "Mes": p.get("mes") or "", "Tipo": p["tipo"], "Título": p["titulo"],
            "Autores": _autores_texto(p), "Autores del instituto": _autores_texto(p, solo_internos=True),
            "Revista / medio": p["medio"] or "", "Volumen": p["volumen"] or "", "Número": p["numero"] or "",
            "Páginas": p["paginas"] or "", "Revisión": productos.REVISIONES[p["revision"]],
            "Índices": ", ".join(i["nombre"] for i in p["indices"]),
            "Estado": productos.ESTADOS[p["estado_publicacion"]],
            "DOI": p["doi"] or "", "arXiv": p["arxiv_id"] or "",
            "Proyectos": ", ".join(v["proyecto"] for v in proyectos.vinculos_de("producto", p["id"])
                                   if v["estado"] == "aprobado"),
            "Líneas de investigación": lineas.nombres(lineas.de_registro("producto", p["id"])),
            # Revista y origen de la clasificación (transparencia del método).
            "Revista (catálogo)": r["revista"] or "", "ISSN": r["issn"] or "", "País de la revista": r["pais"] or "",
            "Ámbito": r["ambito"] or "", "Acceso abierto": {1: "Sí", 0: "No"}.get(r["acceso_abierto"], ""),
            "Mejor cuartil": r["cuartil"] or "", "Origen de la clasificación": r["origen"] or "",
            "Fuente de la indexación": r["fuentes"] or "",
            "Citas (OpenAlex)": p["citas"] if p.get("citas") is not None else "",
            "Citas actualizadas": p.get("citas_actualizadas") or "",
        })
    return filas


def filas_actividades(acts: list[dict]) -> list[dict]:
    filas = []
    for a in acts:
        parts = actividades.participantes(a["id"])
        filas.append({
            "Inicio": a["fecha_inicio"], "Término": a["fecha_fin"] or "", "Tipo": a["tipo"],
            "Título": a["titulo"], "Institución": a["institucion"] or "", "Lugar": a["lugar"] or "",
            "País": a["pais"] or "", "Ámbito": actividades.AMBITOS[a["ambito"]],
            "Modalidad": actividades.MODALIDADES[a["modalidad"]],
            "Participantes del instituto": "; ".join(
                f"{p['apellidos']}, {p['nombres']} ({actividades.ROLES[p['rol']]})" for p in parts if p["interno"]),
            "Líneas de investigación": lineas.nombres(lineas.de_registro("actividad", a["id"])),
        })
    return filas


def filas_proyectos(proys: list[dict]) -> list[dict]:
    return [{
        "Tipo": proyectos.TIPOS[p["tipo"]], "Código": p["codigo"] or "", "Nombre": p["nombre"],
        "Estado": proyectos.ESTADOS[p["estado"]],
        "Inicio": p["fecha_inicio"] or "", "Término": p["fecha_fin"] or "",
        "Financiamiento": p["fuente_financiamiento"] or "",
        "Monto": p["monto"] if p["monto"] is not None else "", "Moneda": p["moneda"],
        "Responsable": "; ".join(f"{r['apellidos']}, {r['nombres']}" for r in proyectos.responsables(p["id"])),
        "Ámbito": proyectos.AMBITOS.get(proyectos.ambito_efectivo(p), ""),
        "Líneas de investigación": lineas.nombres(lineas.de_proyecto(p["id"])),
        "Contrapartes": "; ".join(f"{c['institucion']} ({c['pais'] or '?'})" for c in proyectos.contrapartes(p["id"])),
        "Participantes vigentes": p.get("n_part", ""),
    } for p in proys]


def celda_segura(valor):
    """Evita la «inyección de fórmulas»: Excel ejecuta como fórmula un texto que empieza con
    = + - @ (y openpyxl lo guardaría como fórmula). Se antepone un apóstrofo."""
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + valor
    return valor


def a_csv(filas: list[dict]) -> bytes:
    """CSV en UTF-8 con BOM (Excel reconoce así las tildes)."""
    buf = io.StringIO()
    if filas:
        w = csv.DictWriter(buf, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows({k: celda_segura(v) for k, v in f.items()} for f in filas)
    return buf.getvalue().encode("utf-8-sig")


def a_xlsx(hojas: dict[str, list[dict]]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for nombre, filas in hojas.items():
        ws = wb.create_sheet(nombre[:31])
        if not filas:
            ws.append(["Sin datos"])
            continue
        columnas = list(filas[0])
        ws.append(columnas)
        for c in ws[1]:
            c.font = Font(bold=True)
        for f in filas:
            ws.append([celda_segura(f[c]) for c in columnas])
        for i, c in enumerate(columnas, start=1):
            ancho = max(len(str(c)), *(len(str(f[c])) for f in filas))
            ws.column_dimensions[get_column_letter(i)].width = min(60, max(10, ancho + 2))
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
