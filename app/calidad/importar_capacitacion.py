"""Carga de capacitaciones desde CSV (PLAN §61).

Formato: una fila por persona y capacitación con `email`, `titulo`, `area` (disciplinar, pedagógica, investigación,
gestión, ia_digital u otra; también por su nombre) y, si se tienen, `institucion` y `horas`. Las fechas van en
`fecha_inicio` y `fecha_fin` (AAAA-MM-DD o DD/MM/AAAA); si solo se conoce el año, la columna `anio` basta y la
capacitación se registra como concluida el 31 de diciembre de ese año, o hoy si es el año en curso (cuenta en ese año,
que es lo que miden los indicadores). Se omite lo que ya está registrado (misma persona, nombre y fecha de término).

Flujo en dos pasos: `leer` valida sin cambiar nada; `aplicar` registra las filas sin errores.
"""
from datetime import date

from app.calidad import capacitacion
from app.comun import usuarios
from app.comun.db import auditar, get_db, sin_tildes
from app.comun.importar_usuarios import MAX_BYTES, _fecha, leer_tabla  # noqa: F401  (MAX_BYTES lo usa la ruta)

MAX_FILAS = 2000
ALIAS = {
    "email": ("email", "correo", "e-mail", "mail", "correo electronico", "correo institucional"),
    "titulo": ("titulo", "nombre", "capacitacion", "curso", "nombre de la capacitacion"),
    "institucion": ("institucion", "entidad", "institucion responsable"),
    "area": ("area",),
    "horas": ("horas",),
    "fecha_inicio": ("fecha inicio", "fecha de inicio", "inicio", "fecha_inicio", "desde"),
    "fecha_fin": ("fecha fin", "fecha de termino", "termino", "fin", "fecha_fin", "hasta", "concluyo"),
    "anio": ("anio", "ano"),
}
PLANTILLA = ("email,titulo,institucion,area,horas,fecha_inicio,fecha_fin,anio\n"
             "emmy.noether@universidad.example,Taller de escritura científica,Instituto de Investigación,investigacion,"
             "10,2025-05-05,2025-05-09,\n"
             "emmy.noether@universidad.example,Diplomado en educación superior,Universidad,pedagogica,800,,,2024\n")
_AREAS = {**{k: k for k in capacitacion.AREAS},
          **{sin_tildes(v.split(" (")[0]): k for k, v in capacitacion.AREAS.items()},
          "pedagogica o didactica": "pedagogica", "didactica": "pedagogica", "ia": "ia_digital"}


def leer(contenido: bytes) -> tuple[list[dict], list[str]]:
    """→ (filas, errores generales). Cada fila: linea, email, nombre, datos (validados), estado ('nueva' | 'existe' |
    'error') y mensaje."""
    filas, errores = leer_tabla(contenido, ALIAS, ("email", "titulo", "area"), MAX_FILAS)
    if errores:
        return [], errores
    validas = {p["id"] for p in capacitacion.personas()}
    res = []
    for linea, f in filas:
        u = usuarios.por_email(f["email"].lower())
        r = {"linea": linea, "email": f["email"].lower(), "nombre": f"{u['apellidos']}, {u['nombres']}" if u else "",
             "titulo": f["titulo"], "estado": "error", "mensaje": "", "datos": None}
        res.append(r)
        if not u:
            r["mensaje"] = "No hay una persona registrada con ese correo."
            continue
        if u["id"] not in validas:
            r["mensaje"] = "La persona no tiene vínculo con la Carrera."
            continue
        inicio, fin = _fecha(f["fecha_inicio"]), _fecha(f["fecha_fin"])
        anio = f["anio"]
        if not inicio and not fin and anio.isdigit() and 1950 <= int(anio) <= 2100:
            inicio = fin = min(f"{anio}-12-31", date.today().isoformat())
        elif inicio and not fin:
            fin = inicio
        elif fin and not inicio:
            inicio = fin
        if inicio is False or fin is False:
            r["mensaje"] = "Fecha no válida (use AAAA-MM-DD o DD/MM/AAAA)."
            continue
        d, problemas = capacitacion.validar(
            {"usuario_id": u["id"], "titulo": f["titulo"], "institucion": f["institucion"],
             "area": _AREAS.get(sin_tildes(f["area"]).strip(), ""), "horas": f["horas"],
             "fecha_inicio": inicio or "", "fecha_fin": fin or "", "evidencia_id": ""}, set())
        if problemas:
            r["mensaje"] = " ".join(problemas)
            continue
        r["datos"] = d
        if get_db().q("SELECT 1 FROM capacitacion WHERE usuario_id = ? AND lower(titulo) = lower(?) AND fecha_fin = ?",
                      [u["id"], d["titulo"], d["fecha_fin"]]) or any(
                x["datos"] == d for x in res[:-1] if x["estado"] == "nueva"):
            r["estado"], r["mensaje"] = "existe", "Ya está registrada; se omite."
        else:
            r["estado"] = "nueva"
    return res, []


def aplicar(filas: list[dict], uid: int) -> int:
    n = 0
    for f in filas:
        if f["estado"] == "nueva":
            capacitacion.crear(f["datos"], uid)
            n += 1
    if n:
        auditar(uid, "importar_capacitacion", "capacitacion", None, f"{n} capacitación(es)")
    return n
