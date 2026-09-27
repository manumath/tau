"""La persona académica (PLAN.md, sección 23): datos que son de la persona y no de su
investigación. Sirven a la Carrera y al Instituto por igual.

- La persona es la fila de `usuario`; la cuenta de acceso es opcional: una persona **sin acceso**
  (p. ej., un docente que no usa el portal) tiene `pass_hash = SIN_ACCESO`, que nunca coincide con
  ninguna contraseña. Se le habilita el acceso con «Restablecer contraseña» o una invitación.
- Grados académicos: varios por persona, con título, institución, país y año (hoja 10 de la Guía).
  El «grado» que se muestra en perfiles y directorios es el de mayor nivel.
- Fecha de nacimiento (hoja 11): la registra y la ve Administración del sistema (permiso
  `ver_datos_personales`) y la propia persona, sin editarla. Los informes usan `tramo_edad`, nunca
  la fecha. No aparece en perfiles públicos, API, exportaciones ni en el detalle de la auditoría.
"""
from datetime import date

from app.comun import paises
from app.comun.db import AHORA, get_db

SIN_ACCESO = "!"

# nivel → (nombre, orden: menor = más alto)
NIVELES = {
    "doctorado": ("Doctorado", 1),
    "maestria": ("Magíster", 2),
    "especialidad": ("Especialidad", 3),
    "licenciatura": ("Licenciatura o título profesional", 4),
    "tecnico": ("Técnico superior", 5),
    "otro": ("Otro", 6),
}
LARGO_TEXTO = 300


def sin_acceso(u: dict) -> bool:
    return u.get("pass_hash") == SIN_ACCESO


# --- Grados --------------------------------------------------------------------------------------------

def _orden_sql(columna: str) -> str:
    return "CASE " + columna + " " + " ".join(f"WHEN '{k}' THEN {v[1]}" for k, v in NIVELES.items()) + " END"


def grados(uid: int) -> list[dict]:
    filas = get_db().q(f"""SELECT * FROM grado_academico WHERE usuario_id = ?
                           ORDER BY {_orden_sql('nivel')}, anio DESC, id""", [uid])
    for f in filas:
        f["nivel_texto"] = NIVELES[f["nivel"]][0]
    return filas


def sql_grado_principal(alias: str = "u") -> str:
    """Expresión SQL: nombre del grado de mayor nivel de la fila `alias` de usuario (NULL si no tiene)."""
    nombres = " ".join(f"WHEN '{k}' THEN '{v[0]}'" for k, v in NIVELES.items())
    return (f"(SELECT CASE g.nivel {nombres} END FROM grado_academico g WHERE g.usuario_id = {alias}.id "
            f"ORDER BY {_orden_sql('g.nivel')} LIMIT 1)")


def texto_grado(g: dict) -> str:
    """«Doctor en Matemáticas · Universidad de Chile (Chile), 2012»."""
    partes = [g.get("titulo") or NIVELES[g["nivel"]][0]]
    lugar = g.get("institucion") or ""
    if g.get("pais"):
        lugar = f"{lugar} ({g['pais']})" if lugar else g["pais"]
    detalle = ", ".join(x for x in (lugar, str(g["anio"]) if g.get("anio") else "") if x)
    return " · ".join([partes[0], detalle]) if detalle else partes[0]


def validar_grado(d: dict) -> tuple[dict, list[str]]:
    d = {k: (v or "").strip() if isinstance(v, str) else v for k, v in d.items()}
    errores = []
    if d.get("nivel") not in NIVELES:
        errores.append("Elija el nivel del grado.")
    if any(len(d.get(k) or "") > LARGO_TEXTO for k in ("titulo", "institucion", "pais")):
        errores.append(f"Título, institución y país admiten hasta {LARGO_TEXTO} caracteres.")
    anio = d.get("anio")
    if anio not in (None, ""):
        if not str(anio).isdigit() or not 1940 <= int(anio) <= date.today().year:
            errores.append(f"El año debe estar entre 1940 y {date.today().year}.")
        else:
            anio = int(anio)
    limpio = {"nivel": d.get("nivel"), "titulo": d.get("titulo") or None, "institucion": d.get("institucion") or None,
              "pais": paises.normalizar(d.get("pais")), "anio": anio or None}
    return limpio, errores


def agregar_grado(uid: int, datos: dict) -> list[str]:
    d, errores = validar_grado(datos)
    if errores:
        return errores
    get_db().t.grado_academico.insert(usuario_id=uid, **d)
    return []


def quitar_grado(uid: int, gid: int) -> dict | None:
    """Quita el grado si es de esa persona. → el grado quitado (o None)."""
    filas = get_db().q("SELECT * FROM grado_academico WHERE id = ? AND usuario_id = ?", [gid, uid])
    if filas:
        get_db().execute("DELETE FROM grado_academico WHERE id = ?", [gid])
    return filas[0] if filas else None


# --- Datos personales ------------------------------------------------------------------------------------

EDAD_MINIMA, EDAD_MAXIMA = 18, 100
# (desde, hasta, nombre) en años cumplidos; None = sin límite.
TRAMOS_EDAD = [(None, 29, "Hasta 29 años"), (30, 39, "30 a 39 años"), (40, 49, "40 a 49 años"),
               (50, 59, "50 a 59 años"), (60, None, "60 años o más")]


def fecha_nacimiento(uid: int) -> str | None:
    filas = get_db().q("SELECT fecha_nacimiento FROM datos_personales WHERE usuario_id = ?", [uid])
    return filas[0]["fecha_nacimiento"] if filas else None


def fijar_fecha_nacimiento(uid: int, fecha: str | None, por: int | None = None) -> list[str]:
    """Registra o corrige la fecha (None o vacía la borra)."""
    if fecha:
        try:
            d = date.fromisoformat(fecha)
        except ValueError:
            return ["Indique una fecha válida."]
        if not EDAD_MINIMA <= edad(d.isoformat()) <= EDAD_MAXIMA:
            return [f"La fecha no corresponde a una edad entre {EDAD_MINIMA} y {EDAD_MAXIMA} años."]
        fecha = d.isoformat()
    get_db().execute(f"""INSERT INTO datos_personales (usuario_id, fecha_nacimiento, actualizado_por)
                         VALUES (?, ?, ?)
                         ON CONFLICT (usuario_id) DO UPDATE SET fecha_nacimiento = excluded.fecha_nacimiento,
                         actualizado_por = excluded.actualizado_por, actualizado_en = {AHORA}""",
                     [uid, fecha or None, por])
    return []


def edad(nacimiento: str, a_fecha: str | None = None) -> int:
    n = date.fromisoformat(nacimiento)
    f = date.fromisoformat(a_fecha) if a_fecha else date.today()
    return f.year - n.year - ((f.month, f.day) < (n.month, n.day))


def tramo_edad(uid: int, a_fecha: str | None = None) -> str | None:
    """Tramo de edad de la persona a la fecha (None si no hay fecha de nacimiento registrada)."""
    nacimiento = fecha_nacimiento(uid)
    if not nacimiento:
        return None
    anios = edad(nacimiento, a_fecha)
    return next(nombre for desde, hasta, nombre in TRAMOS_EDAD
                if (desde is None or anios >= desde) and (hasta is None or anios <= hasta))
