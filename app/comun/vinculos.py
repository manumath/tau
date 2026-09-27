"""Historial de vínculo de cada persona con una unidad (categoría y jornada por periodo).

- Cada vínculo es con una unidad (app.comun.unidades): el Instituto (IIMAT) o la Carrera (CMAT).
  Una persona puede tener ambos a la vez. Todas las funciones reciben `unidad` (id); sin ella,
  el Instituto, que es el vínculo que cuenta para los informes de investigación.
- Periodos sin superposición dentro de una misma unidad. fecha_inicio None = ingreso desconocido («desde siempre»);
  fecha_fin None = vigente.
- La categoría vigente de una persona es la de su vínculo vigente hoy con el Instituto; en SQL,
  `sql_categoria_vigente` (se calcula siempre: no hay copia que sincronizar).
- Los informes usan la categoría **a la fecha** de cada producto o actividad (`en_fecha`).
- Carga horaria contratada: cada periodo con la **Carrera** lleva la carga total (32, 64, 96, 128 o
  160 h/mes) y su distribución por actividad en múltiplos de 32 h/mes, que suma la carga total. La
  registra quien gestiona los vínculos de la Carrera (la Dirección de Carrera). Un cambio de carga
  es un periodo nuevo («Registrar cambio»). Ver app.academico.carga para la vista por semestre.
"""
import calendar
from datetime import date, timedelta

from app.comun import unidades
from app.comun.db import get_db, transaccion

# Categoría del vínculo (la asigna la administración con los datos de RR. HH.).
CATEGORIAS = {"titular": "Titular", "contratado": "Contratado(a)", "interino": "Interino(a)",
              "invitado": "Invitado(a)", "externo": "Externo(a)"}

# Carga horaria (h/mes, unidades de 32). Cada actividad es una columna carga_<clave> del vínculo.
UNIDAD_CARGA = 32
CARGAS = (32, 64, 96, 128, 160)
ACTIVIDADES = {"docencia": "Docencia", "investigacion": "Investigación", "extension": "Extensión y servicios",
               "gestion": "Gestión", "otras": "Otras"}

INICIO_DESCONOCIDO = "0000-01-01"
SIN_FIN = "9999-12-31"


def hoy() -> date:
    return date.today()


def _unidad(unidad: int | None) -> int:
    return unidad or unidades.instituto()


def listar(uid: int, unidad: int | None = None) -> list[dict]:
    return get_db().q("""SELECT * FROM vinculo WHERE usuario_id = ? AND unidad_id = ?
                         ORDER BY COALESCE(fecha_inicio, ?), id""", [uid, _unidad(unidad), INICIO_DESCONOCIDO])


def listar_todos(uid: int) -> list[dict]:
    """Periodos con todas las unidades, con la sigla de cada una."""
    return get_db().q("""SELECT v.*, u.sigla FROM vinculo v JOIN unidad u ON u.id = v.unidad_id
                         WHERE v.usuario_id = ? ORDER BY v.unidad_id, COALESCE(v.fecha_inicio, ?), v.id""",
                      [uid, INICIO_DESCONOCIDO])


def obtener(vid: int) -> dict | None:
    filas = get_db().q("SELECT * FROM vinculo WHERE id = ?", [vid])
    return filas[0] if filas else None


def _cubre(v: dict, fecha: str) -> bool:
    return (v["fecha_inicio"] or INICIO_DESCONOCIDO) <= fecha <= (v["fecha_fin"] or SIN_FIN)


def vigente(uid: int, fecha: str | None = None, unidad: int | None = None) -> dict | None:
    fecha = fecha or hoy().isoformat()
    return next((v for v in listar(uid, unidad) if _cubre(v, fecha)), None)


def en_fecha(uid: int, anio: int, mes: int | None = None, unidad: int | None = None) -> tuple[str, str | None]:
    """¿Estaba vinculado en esa fecha? → ('si' | 'no' | 'dudoso', categoría).

    Con mes, se mira el mes completo. Sin mes, 'si' si un mismo periodo cubre todo el año;
    'dudoso' si algún periodo cubre solo parte del año; 'no' si ninguno lo toca."""
    if mes:
        desde, hasta = f"{anio}-{mes:02d}-01", f"{anio}-{mes:02d}-{calendar.monthrange(anio, mes)[1]:02d}"
    else:
        desde, hasta = f"{anio}-01-01", f"{anio}-12-31"
    return _en_rango(uid, desde, hasta, unidad)


def en_dia(uid: int, fecha: str, unidad: int | None = None) -> tuple[str, str | None]:
    return _en_rango(uid, fecha, fecha, unidad)


def _en_rango(uid, desde, hasta, unidad=None):
    parcial = None
    for v in listar(uid, unidad):
        ini, fin = v["fecha_inicio"] or INICIO_DESCONOCIDO, v["fecha_fin"] or SIN_FIN
        if ini <= desde and hasta <= fin:
            return "si", v["categoria"]
        if ini <= hasta and fin >= desde:
            parcial = parcial or v["categoria"]
    return ("dudoso", parcial) if parcial else ("no", None)


def personas_en_rango(desde: str, hasta: str, unidad: int | None = None) -> list[dict]:
    """Personas con algún periodo de vínculo con la unidad que toque [desde, hasta]."""
    return get_db().q(
        """SELECT DISTINCT u.id, u.nombres, u.apellidos FROM usuario u JOIN vinculo v ON v.usuario_id = u.id
           WHERE v.unidad_id = ? AND (v.fecha_inicio IS NULL OR v.fecha_inicio <= ?)
             AND (v.fecha_fin IS NULL OR v.fecha_fin >= ?)
           ORDER BY sin_tildes(u.apellidos), sin_tildes(u.nombres)""", [_unidad(unidad), hasta, desde])


def sin_fecha_de_ingreso(unidad: int | None = None) -> list[dict]:
    """Personas cuyo primer periodo con la unidad no tiene fecha de inicio (para advertir en informes)."""
    return get_db().q(
        """SELECT DISTINCT u.id, u.nombres, u.apellidos FROM vinculo v JOIN usuario u ON u.id = v.usuario_id
           WHERE v.fecha_inicio IS NULL AND v.unidad_id = ? ORDER BY u.apellidos, u.nombres""", [_unidad(unidad)])


def resumen(uid: int) -> str | None:
    """«En el instituto desde 2019 · Titular desde 2023» (o None si no tiene vínculo vigente con el
    Instituto)."""
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
        partes.append(f"{CATEGORIAS[actual['categoria']]} desde {actual['fecha_inicio'][:4]}")
    else:
        partes.append(CATEGORIAS[actual["categoria"]])
    return " · ".join(partes)


# --- Cambios ------------------------------------------------------------------------------------

def _fecha(valor) -> str | None:
    if not valor:
        return None
    return date.fromisoformat(str(valor)).isoformat()


def validar(uid: int, categoria: str, desde, hasta, jornada=None, excluir: int | None = None,
            unidad: int | None = None) -> list[str]:
    errores = []
    if categoria not in CATEGORIAS:
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
    for v in listar(uid, unidad):
        if v["id"] == excluir:
            continue
        if ini <= (v["fecha_fin"] or SIN_FIN) and fin >= (v["fecha_inicio"] or INICIO_DESCONOCIDO):
            errores.append(f"Se superpone con el periodo {texto_periodo(v)} ({CATEGORIAS[v['categoria']]}).")
            break
    return errores


def _horas(valor) -> int | None | bool:
    """'' → None; '64' → 64; cualquier otra cosa → False."""
    v = str(valor if valor is not None else "").strip()
    return None if not v else (int(v) if v.isdigit() else False)


def leer_carga(datos: dict) -> dict | None:
    """Carga del formulario (horas, docencia, investigacion, extension, gestion, otras,
    carga_detalle) → {horas, actividades: {clave: h}, detalle}, o None si no se indicó nada."""
    horas = _horas(datos.get("horas"))
    acts = {k: _horas(datos.get(k)) for k in ACTIVIDADES}
    detalle = (datos.get("carga_detalle") or "").strip()[:300] or None
    if horas is None and not any(acts.values()) and not detalle:
        return None
    return {"horas": horas, "actividades": {k: (0 if h is None else h) for k, h in acts.items()}, "detalle": detalle}


def validar_carga(carga: dict | None, unidad: int | None) -> list[str]:
    if carga is None:
        return []
    if _unidad(unidad) != unidades.id_de(unidades.CARRERA):
        return ["La carga horaria se registra en el vínculo con la Carrera."]
    errores = []
    if carga["horas"] not in CARGAS:
        errores.append("La carga contratada es de 32, 64, 96, 128 o 160 h/mes.")
    acts = carga["actividades"]
    if any(h is False or h % UNIDAD_CARGA or h > CARGAS[-1] for h in acts.values()):
        errores.append("Cada actividad es múltiplo de 32 h/mes (0, 32, 64…).")
    elif carga["horas"] in CARGAS and sum(acts.values()) != carga["horas"]:
        errores.append(f"La distribución por actividad suma {sum(acts.values())} h/mes y debe sumar la carga "
                       f"contratada ({carga['horas']} h/mes).")
    return errores


def _columnas_carga(carga: dict | None) -> dict:
    if carga is None:
        return {"horas_contratadas": None, **{f"carga_{k}": 0 for k in ACTIVIDADES}, "carga_detalle": None}
    return {"horas_contratadas": carga["horas"], **{f"carga_{k}": h for k, h in carga["actividades"].items()},
            "carga_detalle": carga["detalle"]}


def carga_de(v: dict | None) -> dict | None:
    """La carga registrada en un periodo (None si no tiene)."""
    if not v or not v.get("horas_contratadas"):
        return None
    return {"horas": v["horas_contratadas"], "actividades": {k: v[f"carga_{k}"] for k in ACTIVIDADES},
            "detalle": v["carga_detalle"]}


def texto_carga(v: dict | None) -> str:
    """«128 h/mes: docencia 64, investigación 64» (vacío si el periodo no tiene carga)."""
    c = carga_de(v)
    if not c:
        return ""
    partes = [f"{ACTIVIDADES[k].split(' ')[0].lower()} {h}" for k, h in c["actividades"].items() if h]
    return f"{c['horas']} h/mes" + (": " + ", ".join(partes) if partes else "")


def texto_periodo(v: dict) -> str:
    return f"{v['fecha_inicio'] or 'ingreso sin registrar'} a {v['fecha_fin'] or 'hoy'}"


def agregar(uid: int, categoria: str, desde=None, hasta=None, jornada=None, nota=None,
            creado_por: int | None = None, unidad: int | None = None, carga: dict | None = None) -> list[str]:
    errores = validar(uid, categoria, desde, hasta, jornada, unidad=unidad) + validar_carga(carga, unidad)
    if errores:
        return errores
    get_db().t.vinculo.insert(usuario_id=uid, unidad_id=_unidad(unidad), categoria=categoria, fecha_inicio=_fecha(desde),
                              fecha_fin=_fecha(hasta), jornada_horas=int(jornada) if jornada else None,
                              nota=(nota or "").strip() or None, creado_por=creado_por, **_columnas_carga(carga))
    return []


def editar(vid: int, categoria: str, desde, hasta, jornada=None, nota=None, carga: dict | None = None) -> list[str]:
    """Corrige un periodo. Sin carga (None) el periodo queda sin carga registrada."""
    v = obtener(vid)
    if not v:
        return ["Periodo no encontrado."]
    errores = validar(v["usuario_id"], categoria, desde, hasta, jornada, excluir=vid, unidad=v["unidad_id"]) \
        + validar_carga(carga, v["unidad_id"])
    if errores:
        return errores
    # Sin jornada (ya no se pide en el formulario) se conserva la registrada: dato histórico de RR. HH.
    jornada = jornada if jornada not in (None, "") else v["jornada_horas"]
    columnas = _columnas_carga(carga)
    get_db().execute(f"""UPDATE vinculo SET categoria = ?, fecha_inicio = ?, fecha_fin = ?, jornada_horas = ?,
                         nota = ?, {", ".join(f"{c} = ?" for c in columnas)} WHERE id = ?""",
                     [categoria, _fecha(desde), _fecha(hasta), int(jornada) if jornada else None,
                      (nota or "").strip() or None, *columnas.values(), vid])
    return []


def eliminar(vid: int):
    v = obtener(vid)
    if v:
        get_db().execute("DELETE FROM vinculo WHERE id = ?", [vid])


def corregir_categoria_vigente(uid: int, categoria: str | None):
    """Corrige la categoría del vínculo vigente (o crea uno con ingreso desconocido). None quita el
    periodo vigente. Para un cambio con fecha (ascenso, término), use cambiar_categoria."""
    if categoria is not None and categoria not in CATEGORIAS:
        raise ValueError(f"Categoría no válida: {categoria}")
    actual = vigente(uid)
    if categoria is None:
        if actual:
            eliminar(actual["id"])
    elif actual:
        get_db().execute("UPDATE vinculo SET categoria = ? WHERE id = ?", [categoria, actual["id"]])
    else:
        agregar(uid, categoria)


def cambiar_categoria(uid: int, categoria: str, desde, jornada=None, creado_por: int | None = None,
                      unidad: int | None = None, carga: dict | None = None) -> list[str]:
    """Cierra el periodo vigente el día anterior a `desde` y abre uno nuevo con la categoría (y la
    carga, en la Carrera: un cambio de carga también es un periodo nuevo)."""
    try:
        d = _fecha(desde)
    except ValueError:
        return ["Fecha no válida."]
    if not d:
        return ["Indique desde qué fecha rige la nueva categoría."]
    actual = vigente(uid, d, unidad) or vigente(uid, unidad=unidad)
    if actual:
        if actual["fecha_inicio"] and actual["fecha_inicio"] >= d:
            return ["La fecha debe ser posterior al inicio del periodo vigente."]
        if actual["fecha_fin"]:
            return ["El periodo que cubre esa fecha ya tiene término: edítelo o agregue un periodo."]
        cierre = (date.fromisoformat(d) - timedelta(days=1)).isoformat()
        get_db().execute("UPDATE vinculo SET fecha_fin = ? WHERE id = ?", [cierre, actual["id"]])
    errores = agregar(uid, categoria, d, None, jornada if jornada not in ("", None) else
                      (actual or {}).get("jornada_horas"), None, creado_por, unidad, carga)
    if errores and actual:  # deshace el cierre
        get_db().execute("UPDATE vinculo SET fecha_fin = NULL WHERE id = ?", [actual["id"]])
    return errores


def terminar(uid: int, fecha, unidad: int | None = None) -> list[str]:
    """Pone fecha de término al periodo vigente."""
    try:
        f = _fecha(fecha)
    except ValueError:
        return ["Fecha no válida."]
    if not f:
        return ["Indique la fecha de término."]
    actual = vigente(uid, unidad=unidad) or vigente(uid, f, unidad)
    if not actual:
        return ["No tiene un vínculo vigente."]
    if actual["fecha_inicio"] and f < actual["fecha_inicio"]:
        return ["La fecha de término no puede ser anterior al inicio del periodo."]
    get_db().execute("UPDATE vinculo SET fecha_fin = ? WHERE id = ?", [f, actual["id"]])
    return []


def reemplazar_historial(uid: int, periodos: list[dict], creado_por: int | None = None,
                         unidad: int | None = None):
    """Reemplaza el historial de una persona con una unidad (carga desde Recursos Humanos). Los
    periodos deben venir validados (ver importar_vinculos)."""
    db = get_db()
    with transaccion():
        db.execute("DELETE FROM vinculo WHERE usuario_id = ? AND unidad_id = ?", [uid, _unidad(unidad)])
        for p in periodos:
            db.t.vinculo.insert(usuario_id=uid, unidad_id=_unidad(unidad), categoria=p["categoria"], fecha_inicio=p["desde"],
                                fecha_fin=p["hasta"], jornada_horas=p.get("jornada"), nota=p.get("nota"),
                                creado_por=creado_por)


def categoria_texto(categoria: str | None) -> str:
    return CATEGORIAS.get(categoria or "", "Sin categoría")


def sql_categoria_vigente(alias: str = "u") -> str:
    """Expresión SQL: categoría del vínculo vigente hoy con el Instituto de la fila `alias` de
    usuario (NULL si no tiene). «Hoy» es `hoy()`, igual que en `vigente` (una sola fuente)."""
    f = hoy().isoformat()  # una fecha ISO, nunca un dato del usuario
    return (f"(SELECT v.categoria FROM vinculo v WHERE v.usuario_id = {alias}.id AND v.unidad_id = "
            f"(SELECT id FROM unidad WHERE sigla = '{unidades.INSTITUTO}') "
            f"AND (v.fecha_inicio IS NULL OR v.fecha_inicio <= '{f}') AND (v.fecha_fin IS NULL OR v.fecha_fin >= '{f}') "
            f"ORDER BY v.fecha_inicio DESC LIMIT 1)")
