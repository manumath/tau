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

from app import actividades, perfiles, productos, proyectos
from app.db import get_db

# Categorías del CV, en orden de aparición. La primera que corresponde es la que se usa.
CATEGORIAS = [
    ("indexados", "Artículos en revistas indexadas"),
    ("arbitrados", "Artículos arbitrados"),
    ("libros", "Libros y capítulos de libro"),
    ("en_curso", "Trabajos enviados o en preparación"),
    ("reportes", "Reportes de investigación"),
    ("preprints", "Preprints"),
    ("presentaciones", "Presentaciones"),
    ("otros", "Otros productos"),
]


def categoria(p: dict) -> str:
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

def cv(uid: int, desde: int, hasta: int, solo_informe: bool = False) -> dict:
    perfil = perfiles.obtener(uid)
    prods = [p for p in productos.de_investigador(uid) if desde <= p["anio"] <= hasta
             and productos.es_autor(p["id"], uid)]  # en el CV, solo aquello de lo que es autor
    if solo_informe:
        prods = [p for p in prods if productos.cuenta_para_informe(p)]
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
    prods = [productos.obtener(v["registro_id"]) for v in proyectos.registros(pid, "producto")]
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
            "actividades": acts}


# --- Memoria anual ------------------------------------------------------------------------------------

def memoria(anio: int) -> dict:
    """Productos que cuentan (del año), actividades con participación del instituto, proyectos
    vigentes en el año y un resumen por investigador."""
    ids = [r["id"] for r in get_db().q(
        """SELECT DISTINCT p.id FROM producto p JOIN producto_autor pa ON pa.producto_id = p.id
           WHERE p.anio = ? AND pa.investigador_id IS NOT NULL
             AND p.revision IN ('indexado', 'arbitrado')
             AND p.estado_publicacion IN ('aceptado', 'publicado')
           ORDER BY p.revision, p.id""", [anio])]
    prods = [productos.obtener(i) for i in ids]
    prods.sort(key=lambda p: (p["revision"] != "indexado", p["tipo"], p["titulo"]))
    acts = [actividades.obtener(r["id"]) for r in get_db().q(
        """SELECT DISTINCT a.id FROM actividad a JOIN actividad_participante ap ON ap.actividad_id = a.id
           WHERE substr(a.fecha_inicio, 1, 4) = ? AND ap.investigador_id IS NOT NULL
           ORDER BY a.fecha_inicio""", [str(anio)])]
    proys = [p for p in proyectos.todos() if _en_periodo_proyecto(p, anio, anio) and p["estado"] != "formulacion"]

    por_indice, por_tipo_act, por_ambito = {}, {}, {}
    for p in prods:
        for i in p["indices"]:
            por_indice[i["nombre"]] = por_indice.get(i["nombre"], 0) + 1
    for a in acts:
        por_tipo_act[a["tipo"]] = por_tipo_act.get(a["tipo"], 0) + 1
        por_ambito[a["ambito"]] = por_ambito.get(a["ambito"], 0) + 1

    investigadores = get_db().q(
        """SELECT u.id, u.nombres, u.apellidos FROM usuario u JOIN investigador i ON i.usuario_id = u.id
           WHERE u.activo = 1 ORDER BY sin_tildes(u.apellidos), sin_tildes(u.nombres)""")
    resumen = []
    for inv in investigadores:
        n_p = sum(any(a["interno"] and a["id"] == inv["id"] for a in p["autores"]) for p in prods)
        n_a = get_db().q("""SELECT COUNT(DISTINCT a.id) n FROM actividad a JOIN actividad_participante ap
                            ON ap.actividad_id = a.id WHERE ap.investigador_id = ?
                            AND substr(a.fecha_inicio, 1, 4) = ?""", [inv["id"], str(anio)])[0]["n"]
        resumen.append({**inv, "productos": n_p, "actividades": n_a})
    return {"anio": anio, "productos": prods, "actividades": acts, "proyectos": proys,
            "n_indexados": sum(p["revision"] == "indexado" for p in prods),
            "n_arbitrados": sum(p["revision"] == "arbitrado" for p in prods),
            "por_indice": dict(sorted(por_indice.items(), key=lambda x: -x[1])),
            "por_tipo_actividad": dict(sorted(por_tipo_act.items(), key=lambda x: -x[1])),
            "por_ambito": por_ambito, "por_investigador": resumen}


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
    return [{
        "Año": p["anio"], "Tipo": p["tipo"], "Título": p["titulo"], "Autores": _autores_texto(p),
        "Autores del instituto": _autores_texto(p, solo_internos=True),
        "Revista / medio": p["medio"] or "", "Volumen": p["volumen"] or "", "Número": p["numero"] or "",
        "Páginas": p["paginas"] or "", "Revisión": productos.REVISIONES[p["revision"]],
        "Índices": ", ".join(i["nombre"] for i in p["indices"]),
        "Estado": productos.ESTADOS[p["estado_publicacion"]],
        "DOI": p["doi"] or "", "arXiv": p["arxiv_id"] or "",
        "Proyectos": ", ".join(v["proyecto"] for v in proyectos.vinculos_de("producto", p["id"])
                               if v["estado"] == "aprobado"),
    } for p in prods]


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
        })
    return filas


def filas_proyectos(proys: list[dict]) -> list[dict]:
    return [{
        "Código": p["codigo"] or "", "Nombre": p["nombre"], "Estado": proyectos.ESTADOS[p["estado"]],
        "Inicio": p["fecha_inicio"] or "", "Término": p["fecha_fin"] or "",
        "Financiamiento": p["fuente_financiamiento"] or "",
        "Monto": p["monto"] if p["monto"] is not None else "", "Moneda": p["moneda"],
        "Responsable": "; ".join(f"{r['apellidos']}, {r['nombres']}" for r in proyectos.responsables(p["id"])),
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
