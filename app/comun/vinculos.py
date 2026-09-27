"""Historial de vínculo de cada investigador(a) con el instituto (categoría por periodo).

- Periodos sin superposición. fecha_inicio None = ingreso desconocido («desde siempre»);
  fecha_fin None = vigente.
- `investigador.categoria` es la categoría del vínculo vigente hoy: la mantiene
  `sincronizar_categoria` (tras cada cambio y en el mantenimiento horario, porque un periodo con
  fecha de término deja de estar vigente con el paso de los días).
- Los informes usan la categoría **a la fecha** de cada producto o actividad (`en_fecha`).
"""
import calendar
from datetime import date, timedelta

from app.investigacion import perfiles
from app.comun.db import get_db

INICIO_DESCONOCIDO = "0000-01-01"
SIN_FIN = "9999-12-31"


def hoy() -> date:
    return date.today()


def listar(uid: int) -> list[dict]:
    return get_db().q("""SELECT * FROM vinculo WHERE usuario_id = ?
                         ORDER BY COALESCE(fecha_inicio, ?), id""", [uid, INICIO_DESCONOCIDO])


def obtener(vid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM vinculo WHERE id = ?", [vid])
    return filas[0] if filas else None


def _cubre(v: dict, fecha: str) -> bool:
    return (v["fecha_inicio"] or INICIO_DESCONOCIDO) <= fecha <= (v["fecha_fin"] or SIN_FIN)


def vigente(uid: int, fecha: str | None = None) -> dict | None:
    fecha = fecha or hoy().isoformat()
    return next((v for v in listar(uid) if _cubre(v, fecha)), None)


def en_fecha(uid: int, anio: int, mes: int | None = None) -> tuple[str, str | None]:
    """¿Estaba vinculado en esa fecha? → ('si' | 'no' | 'dudoso', categoría).

    Con mes, se mira el mes completo. Sin mes, 'si' si un mismo periodo cubre todo el año;
    'dudoso' si algún periodo cubre solo parte del año; 'no' si ninguno lo toca."""
    if mes:
        desde, hasta = f"{anio}-{mes:02d}-01", f"{anio}-{mes:02d}-{calendar.monthrange(anio, mes)[1]:02d}"
    else:
        desde, hasta = f"{anio}-01-01", f"{anio}-12-31"
    return _en_rango(uid, desde, hasta)


def en_dia(uid: int, fecha: str) -> tuple[str, str | None]:
    return _en_rango(uid, fecha, fecha)


def _en_rango(uid, desde, hasta):
    parcial = None
    for v in listar(uid):
        ini, fin = v["fecha_inicio"] or INICIO_DESCONOCIDO, v["fecha_fin"] or SIN_FIN
        if ini <= desde and hasta <= fin:
            return "si", v["categoria"]
        if ini <= hasta and fin >= desde:
            parcial = parcial or v["categoria"]
    return ("dudoso", parcial) if parcial else ("no", None)


def sin_fecha_de_ingreso() -> list[dict]:
    """Investigadores cuyo primer periodo no tiene fecha de inicio (para advertir en informes)."""
    return get_db().q(
        """SELECT DISTINCT u.id, u.nombres, u.apellidos FROM vinculo v JOIN usuario u ON u.id = v.usuario_id
           WHERE v.fecha_inicio IS NULL ORDER BY u.apellidos, u.nombres""")


def resumen(uid: int) -> str | None:
    """«En el instituto desde 2019 · Titular desde 2023» (o None si no tiene vínculo vigente)."""
    actual = vigente(uid)
    if not actual:
        return None
    periodos = listar(uid)
    # Inicio del tramo continuo que termina en el periodo vigente.
    i = periodos.index(actual)
    inicio = actual["fecha_inicio"]
    while i > 0 and inicio and periodos[i - 1]["fecha_fin"] and \
            date.fromisoformat(periodos[i - 1]["fecha_fin"]) + timedelta(days=1) >= date.fromisoformat(inicio):
        i -= 1
        inicio = periodos[i]["fecha_inicio"]
    partes = [f"En el instituto desde {inicio[:4]}" if inicio else "En el instituto (fecha de ingreso sin registrar)"]
    if actual["fecha_inicio"] and actual["fecha_inicio"] != inicio:
        partes.append(f"{perfiles.CATEGORIAS[actual['categoria']]} desde {actual['fecha_inicio'][:4]}")
    else:
        partes.append(perfiles.CATEGORIAS[actual["categoria"]])
    return " · ".join(partes)


# --- Cambios ------------------------------------------------------------------------------------

def _fecha(valor) -> str | None:
    if not valor:
        return None
    return date.fromisoformat(str(valor)).isoformat()


def validar(uid: int, categoria: str, desde, hasta, jornada=None, excluir: int | None = None) -> list[str]:
    errores = []
    if categoria not in perfiles.CATEGORIAS:
        errores.append("Categoría no válida.")
    try:
        d, h = _fecha(desde), _fecha(hasta)
    except ValueError:
        return errores + ["Fechas no válidas."]
    if d and h and h < d:
        errores.append("La fecha de término no puede ser anterior a la de inicio.")
    if jornada not in (None, "") and not (str(jornada).isdigit() and 1 <= int(jornada) <= 60):
        errores.append("La jornada debe ser un número de horas semanales entre 1 y 60.")
    ini, fin = d or INICIO_DESCONOCIDO, h or SIN_FIN
    for v in listar(uid):
        if v["id"] == excluir:
            continue
        if ini <= (v["fecha_fin"] or SIN_FIN) and fin >= (v["fecha_inicio"] or INICIO_DESCONOCIDO):
            errores.append(f"Se superpone con el periodo {texto_periodo(v)} ({perfiles.CATEGORIAS[v['categoria']]}).")
            break
    return errores


def texto_periodo(v: dict) -> str:
    return f"{v['fecha_inicio'] or 'ingreso sin registrar'} a {v['fecha_fin'] or 'hoy'}"


def agregar(uid: int, categoria: str, desde=None, hasta=None, jornada=None, nota=None,
            creado_por: int | None = None) -> list[str]:
    errores = validar(uid, categoria, desde, hasta, jornada)
    if errores:
        return errores
    get_db().t.vinculo.insert(usuario_id=uid, categoria=categoria, fecha_inicio=_fecha(desde),
                              fecha_fin=_fecha(hasta), jornada_horas=int(jornada) if jornada else None,
                              nota=(nota or "").strip() or None, creado_por=creado_por)
    sincronizar_categoria(uid)
    return []


def editar(vid: int, categoria: str, desde, hasta, jornada=None, nota=None) -> list[str]:
    v = obtener(vid)
    if not v:
        return ["Periodo no encontrado."]
    errores = validar(v["usuario_id"], categoria, desde, hasta, jornada, excluir=vid)
    if errores:
        return errores
    get_db().execute("""UPDATE vinculo SET categoria = ?, fecha_inicio = ?, fecha_fin = ?, jornada_horas = ?,
                        nota = ? WHERE id = ?""",
                     [categoria, _fecha(desde), _fecha(hasta), int(jornada) if jornada else None,
                      (nota or "").strip() or None, vid])
    sincronizar_categoria(v["usuario_id"])
    return []


def eliminar(vid: int):
    v = obtener(vid)
    if v:
        get_db().execute("DELETE FROM vinculo WHERE id = ?", [vid])
        sincronizar_categoria(v["usuario_id"])


def cambiar_categoria(uid: int, categoria: str, desde, jornada=None, creado_por: int | None = None) -> list[str]:
    """Cierra el periodo vigente el día anterior a `desde` y abre uno nuevo con la categoría."""
    try:
        d = _fecha(desde)
    except ValueError:
        return ["Fecha no válida."]
    if not d:
        return ["Indique desde qué fecha rige la nueva categoría."]
    actual = vigente(uid, d) or vigente(uid)
    if actual:
        if actual["fecha_inicio"] and actual["fecha_inicio"] >= d:
            return ["La fecha debe ser posterior al inicio del periodo vigente."]
        if actual["fecha_fin"]:
            return ["El periodo que cubre esa fecha ya tiene término: edítelo o agregue un periodo."]
        cierre = (date.fromisoformat(d) - timedelta(days=1)).isoformat()
        get_db().execute("UPDATE vinculo SET fecha_fin = ? WHERE id = ?", [cierre, actual["id"]])
    errores = agregar(uid, categoria, d, None, jornada if jornada not in ("", None) else
                      (actual or {}).get("jornada_horas"), None, creado_por)
    if errores and actual:  # deshace el cierre
        get_db().execute("UPDATE vinculo SET fecha_fin = NULL WHERE id = ?", [actual["id"]])
    return errores


def terminar(uid: int, fecha) -> list[str]:
    """Pone fecha de término al periodo vigente."""
    try:
        f = _fecha(fecha)
    except ValueError:
        return ["Fecha no válida."]
    if not f:
        return ["Indique la fecha de término."]
    actual = vigente(uid) or vigente(uid, f)
    if not actual:
        return ["No tiene un vínculo vigente."]
    if actual["fecha_inicio"] and f < actual["fecha_inicio"]:
        return ["La fecha de término no puede ser anterior al inicio del periodo."]
    get_db().execute("UPDATE vinculo SET fecha_fin = ? WHERE id = ?", [f, actual["id"]])
    sincronizar_categoria(uid)
    return []


def reemplazar_historial(uid: int, periodos: list[dict], creado_por: int | None = None):
    """Reemplaza todo el historial de una persona (carga desde Recursos Humanos). Los periodos
    deben venir validados (ver importar_vinculos)."""
    db = get_db()
    with db.conn:
        db.execute("DELETE FROM vinculo WHERE usuario_id = ?", [uid])
        for p in periodos:
            db.t.vinculo.insert(usuario_id=uid, categoria=p["categoria"], fecha_inicio=p["desde"],
                                fecha_fin=p["hasta"], jornada_horas=p.get("jornada"), nota=p.get("nota"),
                                creado_por=creado_por)
    sincronizar_categoria(uid)


def sincronizar_categoria(uid: int | None = None):
    """investigador.categoria = categoría del vínculo vigente hoy (o de todos, sin uid)."""
    db = get_db()
    ids = [uid] if uid else [f["usuario_id"] for f in db.q("SELECT usuario_id FROM investigador")]
    for i in ids:
        v = vigente(i)
        cat = v["categoria"] if v else None
        db.execute("UPDATE investigador SET categoria = ? WHERE usuario_id = ? AND categoria IS NOT ?",
                   [cat, i, cat])
