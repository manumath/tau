"""Acceso abierto y datos de cada producto (PLAN §69, etapa 2).

Es una **declaración propia** de quienes firman el producto: dónde se puede leer el texto y si los datos o el código están
disponibles. TAU no verifica los enlaces ni obliga a nada. Un producto sin fila en `producto_acceso` está «sin declarar»."""
from datetime import date

from app.comun import personas
from app.comun.db import AHORA, auditar, get_db
from app.investigacion import identificadores, productos

TEXTOS = {"abierto": "Abierto en el sitio de la revista", "depositado": "Copia en un repositorio",
          "embargo": "En embargo", "cerrado": "Sin acceso abierto", "no_aplica": "No aplica"}
CON_ENLACE = ("abierto", "depositado")
VERSIONES = {"preprint": "Preprint (antes de la revisión)", "aceptada": "Versión aceptada por la revista",
             "publicada": "Versión publicada por el editor"}
LICENCIAS = {"cc_by": "CC BY", "cc_by_sa": "CC BY-SA", "cc_by_nc": "CC BY-NC", "cc_by_nc_sa": "CC BY-NC-SA",
             "cc_by_nd": "CC BY-ND", "cc_by_nc_nd": "CC BY-NC-ND", "cc0": "CC0 (dominio público)", "otra": "Otra licencia",
             "sin_licencia": "Sin licencia"}
DATOS = {"publicados": "Datos o código publicados", "a_pedido": "Disponibles a pedido",
         "reservados": "No se pueden compartir", "no_hay": "No hay datos ni código"}
TONOS = {"abierto": "verde", "depositado": "verde", "embargo": "ambar", "cerrado": "gris", "no_aplica": "gris", None: "ambar"}
ESTADOS_QUE_APLICAN = ("aceptado", "publicado")
TIPOS_SIN_TEXTO = ("Presentación", "Tesis dirigida", "Patente")       # no son textos que se depositen
ANIOS_A_DECLARAR = 5                # «Mis pendientes» pide declarar lo de este año y los cuatro anteriores
LARGO_NOTA = 500
FILTROS = {"": "Todos", "sin_declarar": "Sin declarar", **TEXTOS}


def de_producto(pid: int) -> dict | None:
    fila = get_db().q("SELECT * FROM producto_acceso WHERE producto_id = ?", [pid])
    return fila[0] if fila else None


def aplica(p: dict) -> bool:
    """¿Se le pide declarar el acceso? Aceptado o publicado y de un tipo que se deposita."""
    return p["estado_publicacion"] in ESTADOS_QUE_APLICAN and p["tipo"] not in TIPOS_SIN_TEXTO


def _url(valor: str, etiqueta: str) -> tuple[str | None, str | None]:
    valor = (valor or "").strip()
    if not valor:
        return None, None
    try:
        return identificadores.normalizar_url(valor), None
    except ValueError:
        return None, f"{etiqueta}: ingrese una dirección web válida (p. ej. https://repositorio.umsa.bo/…)."


def sugerencia(p: dict) -> dict:
    """Valores con que se abre el formulario de un producto sin declarar: si tiene arXiv, su copia ya está en un repositorio."""
    if p.get("arxiv_id"):
        return {"texto": "depositado", "enlace": f"https://arxiv.org/abs/{p['arxiv_id']}"}
    return {}


def validar(d: dict) -> tuple[dict, list[str]]:
    """→ (valores para guardar, errores). `d` trae los campos del formulario, ya sin espacios sobrantes."""
    errores = []
    texto = d.get("texto") or ""
    if texto not in TEXTOS:
        errores.append("Indique dónde se puede leer el texto.")
    v = {"texto": texto, "version": None, "enlace": None, "licencia": None, "embargo_hasta": None, "datos": None,
         "datos_enlace": None, "nota": (d.get("nota") or "").strip() or None}
    if v["nota"] and len(v["nota"]) > LARGO_NOTA:
        errores.append(f"La nota admite hasta {LARGO_NOTA} caracteres.")
    if texto in CON_ENLACE or texto == "embargo":
        v["enlace"], error = _url(d.get("enlace"), "El enlace del texto")
        if error:
            errores.append(error)
        elif texto in CON_ENLACE and not v["enlace"]:
            errores.append("Falta el enlace donde se puede leer el texto.")
    if texto in CON_ENLACE:
        v["licencia"] = d.get("licencia") if d.get("licencia") in LICENCIAS else None
    if texto == "depositado":
        if d.get("version") not in VERSIONES:
            errores.append("Indique qué versión depositó.")
        else:
            v["version"] = d["version"]
    if texto == "embargo":
        try:
            v["embargo_hasta"] = date.fromisoformat(d.get("embargo_hasta") or "").isoformat()
        except ValueError:
            errores.append("Indique la fecha en que termina el embargo.")
    dato = d.get("datos") or ""
    if dato:
        if dato not in DATOS:
            errores.append("Elija una opción válida para los datos.")
        else:
            v["datos"] = dato
    if v["datos"] == "publicados":
        v["datos_enlace"], error = _url(d.get("datos_enlace"), "El enlace de los datos")
        if error:
            errores.append(error)
        elif not v["datos_enlace"]:
            errores.append("Falta el enlace de los datos o del código publicados.")
    return v, errores


def guardar(pid: int, valores: dict, uid: int):
    db = get_db()
    if de_producto(pid):
        db.t.producto_acceso.update(producto_id=pid, **valores)
        db.execute(f"UPDATE producto_acceso SET actualizado_en = {AHORA}, declarado_por = ? WHERE producto_id = ?", [uid, pid])
    else:
        db.t.producto_acceso.insert(producto_id=pid, declarado_por=uid, **valores)
    auditar(uid, "declarar_acceso_abierto", "producto", pid, f"{valores['texto']}; datos: {valores['datos'] or 'sin declarar'}")


def quitar(pid: int, uid: int):
    get_db().execute("DELETE FROM producto_acceso WHERE producto_id = ?", [pid])
    auditar(uid, "quitar_acceso_abierto", "producto", pid)


def enlace_publico(a: dict | None) -> str | None:
    """Dirección donde cualquiera puede leer el texto, si el autor la declaró como abierta o depositada."""
    return a["enlace"] if a and a["texto"] in CON_ENLACE and a["enlace"] else None


def enlaces_publicos(ids) -> dict[int, str]:
    """producto_id → dirección del texto abierto, solo de los productos cuyo autor lo declaró abierto o depositado."""
    res = {}
    for lote in personas._lotes(list(ids)):
        for f in get_db().q(f"""SELECT producto_id, enlace FROM producto_acceso WHERE texto IN ('abierto', 'depositado')
                                AND enlace IS NOT NULL AND producto_id IN ({','.join('?' * len(lote))})""", lote):
            res[f["producto_id"]] = f["enlace"]
    return res


def con_acceso(lista: list[dict]) -> list[dict]:
    """Agrega `acceso_abierto` (la dirección o None) a cada producto de la lista."""
    enlaces = enlaces_publicos(p["id"] for p in lista)
    return [{**p, "acceso_abierto": enlaces.get(p["id"])} for p in lista]


def embargo_vencido(a: dict | None, hoy: date | None = None) -> bool:
    return bool(a and a["texto"] == "embargo" and a["embargo_hasta"] and a["embargo_hasta"] <= (hoy or date.today()).isoformat())


# --- Consultas de la persona ------------------------------------------------------------------------------------------

def de_investigador(uid: int, estado: str = "", anio: str = "") -> list[dict]:
    """Sus productos aceptados o publicados que se depositan, con su declaración (`texto` es None si falta), los
    más recientes primero y los sin declarar antes dentro de cada año. `estado`: uno de FILTROS."""
    marcas = ",".join("?" * len(TIPOS_SIN_TEXTO))
    filas = get_db().q(
        f"""SELECT p.id, p.titulo, p.anio, p.doi, p.arxiv_id, t.nombre AS tipo, p.estado_publicacion,
                   a.texto, a.version, a.enlace, a.licencia, a.embargo_hasta, a.datos, a.datos_enlace, a.nota
            FROM producto p JOIN tipo_producto t ON t.id = p.tipo_id
            JOIN producto_autor pa ON pa.producto_id = p.id AND pa.investigador_id = ?
            LEFT JOIN producto_acceso a ON a.producto_id = p.id
            WHERE p.estado_publicacion IN ('aceptado', 'publicado') AND t.nombre NOT IN ({marcas})
            ORDER BY p.anio DESC, a.texto IS NOT NULL, p.titulo""", [uid, *TIPOS_SIN_TEXTO])
    return filtrar(filas, estado, anio)


def filtrar(filas: list[dict], estado: str = "", anio: str = "") -> list[dict]:
    """Las filas de `de_investigador` con la situación y el año pedidos (sin volver a consultar)."""
    if estado == "sin_declarar":
        filas = [f for f in filas if f["texto"] is None]
    elif estado in TEXTOS:
        filas = [f for f in filas if f["texto"] == estado]
    if anio.isdigit():
        filas = [f for f in filas if f["anio"] == int(anio)]
    return filas


def anios_de(uid: int, filas: list[dict] | None = None) -> list[int]:
    return sorted({f["anio"] for f in (de_investigador(uid) if filas is None else filas)}, reverse=True)


def sin_declarar(uid: int, hoy: date | None = None) -> list[dict]:
    """Lo que «Mis pendientes» le pide declarar: sin declaración y de los últimos años."""
    desde = (hoy or date.today()).year - ANIOS_A_DECLARAR + 1
    return [f for f in de_investigador(uid, "sin_declarar") if f["anio"] >= desde]


def embargos_vencidos(uid: int, hoy: date | None = None) -> list[dict]:
    return [f for f in de_investigador(uid, "embargo") if embargo_vencido(f, hoy)]


def resumen(lista: list[dict]) -> dict:
    """Cuántos productos hay por situación del texto y cuántos tienen los datos publicados."""
    r = {"total": len(lista), "sin_declarar": sum(f["texto"] is None for f in lista),
         "datos_publicados": sum(f["datos"] == "publicados" for f in lista)}
    for clave in TEXTOS:
        r[clave] = sum(f["texto"] == clave for f in lista)
    r["en_abierto"] = r["abierto"] + r["depositado"]
    return r


def puede_declarar(p: dict | None, uid: int) -> bool:
    return bool(p) and productos.puede_editar(p, uid)
