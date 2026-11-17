"""Convenios de la Carrera con otras instituciones (PLAN §57, etapa 8; Política de Internacionalización de la UMSA:
alianzas). Cada convenio registra lo que se hizo con él (actividades con fecha); el indicador «Convenios con actividad
en el año» (`auto:convenios_activos`) cuenta los vigentes en el año con al menos una actividad."""
from datetime import date

from app.comun.db import get_db, transaccion

AMBITOS = {"nacional": "Nacional", "internacional": "Internacional"}
TIPOS = {"marco": "Marco", "especifico": "Específico"}


def _texto(v, largo=2000):
    return (v or "").strip()[:largo] or None


def _fecha(v, campo, errores, obligatoria=False):
    v = (v or "").strip()
    if not v:
        if obligatoria:
            errores.append(f"Indique {campo}.")
        return None
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        errores.append(f"Revise {campo}.")
        return v


def listar() -> list[dict]:
    hoy = date.today().isoformat()
    filas = get_db().q(
        """SELECT v.*, (SELECT COUNT(*) FROM actividad_convenio a WHERE a.convenio_id = v.id) AS actividades,
                  (SELECT MAX(fecha) FROM actividad_convenio a WHERE a.convenio_id = v.id) AS ultima
           FROM convenio v ORDER BY (v.vigente_hasta IS NOT NULL AND v.vigente_hasta < ?), v.contraparte""", [hoy])
    for f in filas:
        f["vigente"] = f["fecha_firma"] <= hoy and (f["vigente_hasta"] is None or f["vigente_hasta"] >= hoy)
    return filas


def obtener(vid: int) -> dict | None:
    f = get_db().q("""SELECT v.*, e.titulo AS evidencia_titulo FROM convenio v
                      LEFT JOIN evidencia_calidad e ON e.id = v.evidencia_id WHERE v.id = ?""", [vid])
    if not f:
        return None
    v = f[0]
    hoy = date.today().isoformat()
    v["vigente"] = v["fecha_firma"] <= hoy and (v["vigente_hasta"] is None or v["vigente_hasta"] >= hoy)
    v["lista_actividades"] = get_db().q(
        """SELECT a.*, u.nombres || ' ' || u.apellidos AS por FROM actividad_convenio a
           LEFT JOIN usuario u ON u.id = a.registrado_por WHERE a.convenio_id = ? ORDER BY a.fecha DESC, a.id DESC""", [vid])
    return v


def validar(d: dict, evidencias_validas: set[int]) -> tuple[dict, list[str]]:
    errores: list[str] = []
    x = {"contraparte": _texto(d.get("contraparte"), 300), "pais": _texto(d.get("pais"), 100),
         "ambito": d.get("ambito") or "", "tipo": d.get("tipo") or "", "objeto": _texto(d.get("objeto"))}
    if not x["contraparte"]:
        errores.append("Indique la institución contraparte.")
    if x["ambito"] not in AMBITOS:
        errores.append("Elija el ámbito.")
    if x["tipo"] not in TIPOS:
        errores.append("Elija el tipo de convenio.")
    x["fecha_firma"] = _fecha(d.get("fecha_firma"), "la fecha de firma", errores, obligatoria=True)
    x["vigente_hasta"] = _fecha(d.get("vigente_hasta"), "la fecha de término", errores)
    if not errores and x["vigente_hasta"] and x["vigente_hasta"] < x["fecha_firma"]:
        errores.append("La fecha de término no puede ser anterior a la firma.")
    e = str(d.get("evidencia_id") or "").strip()
    x["evidencia_id"] = int(e) if e.isdigit() and int(e) in evidencias_validas else None
    if e and x["evidencia_id"] is None:
        errores.append("Elija una evidencia del repositorio.")
    return x, errores


CAMPOS = ("contraparte", "pais", "ambito", "tipo", "objeto", "fecha_firma", "vigente_hasta", "evidencia_id")


def crear(x: dict, uid: int) -> int:
    return get_db().t.convenio.insert(registrado_por=uid, **{k: x[k] for k in CAMPOS})["id"]


def actualizar(vid: int, x: dict):
    get_db().t.convenio.update({k: x[k] for k in CAMPOS}, vid)


def eliminar(v: dict) -> bool:
    """Solo sin actividades (las actividades son la historia del convenio)."""
    if v["lista_actividades"]:
        return False
    get_db().execute("DELETE FROM convenio WHERE id = ?", [v["id"]])
    return True


def validar_actividad(d: dict) -> tuple[dict, list[str]]:
    errores: list[str] = []
    x = {"descripcion": _texto(d.get("descripcion")), "fecha": _fecha(d.get("fecha"), "la fecha", errores, obligatoria=True)}
    if not x["descripcion"]:
        errores.append("Describa la actividad.")
    if not errores and x["fecha"] > date.today().isoformat():
        errores.append("Registre la actividad cuando se haya realizado.")
    return x, errores


def agregar_actividad(vid: int, x: dict, uid: int) -> int:
    with transaccion():
        return get_db().t.actividad_convenio.insert(convenio_id=vid, registrado_por=uid, **x)["id"]


def actividad(aid: int) -> dict | None:
    f = get_db().q("SELECT * FROM actividad_convenio WHERE id = ?", [aid])
    return f[0] if f else None


def quitar_actividad(aid: int):
    get_db().execute("DELETE FROM actividad_convenio WHERE id = ?", [aid])
