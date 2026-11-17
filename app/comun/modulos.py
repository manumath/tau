"""Módulos del sistema (PLAN §73, etapa 1): qué funciones están activas en esta instalación.

TAU sirve a unidades distintas: una instala solo lo que necesita y la Administración del sistema activa el resto en
Administración → Módulos. Aquí está el registro (qué módulos hay y qué es de cada uno), el estado (tabla `modulo`) y la
**compuerta**: una ruta de un módulo apagado responde 404, también si es pública.

- Cada paquete declara sus módulos en `app/<paquete>/modulo.py` (un `Modulo` por función del sistema) y `main.py` los
  registra. Un módulo no es un paquete de Python: es una lista de archivos de rutas y de acciones de permisos.
- La **plataforma** (cuentas, roles, unidades, vínculos, avisos, auditoría) no se apaga: se declara igual, con la clave
  `PLATAFORMA`, para que toda ruta y toda acción tengan dueño.
- **Apagar oculta y nunca borra**: las tablas existen siempre y, al reactivar, todo vuelve como estaba.
- Tres defensas: la compuerta (`compuerta`), los permisos (`permisos.puede` niega las acciones de un módulo apagado) y
  el menú (`direccion_activa`). Este archivo no importa de otros paquetes.
"""
import inspect
import time
from dataclasses import dataclass, field

from fasthtml.common import Beforeware, Response

from app.comun import db
from app.comun.db import auditar, get_db, marca_tiempo, transaccion

PLATAFORMA = "plataforma"
AREAS = ("Investigación", "Docencia", "Estudiantes", "Servicios", "Calidad", "Transversal")


@dataclass(frozen=True)
class Modulo:
    clave: str
    nombre: str
    descripcion: str                       # una frase para el panel: qué gana la unidad al activarlo
    area: str = ""
    requiere: tuple[str, ...] = ()         # módulos que deben estar activos para activar este
    rutas: tuple[str, ...] = ()            # módulos de Python con sus rutas (vale como prefijo: cubre sus submódulos)
    acciones: tuple[str, ...] = ()         # acciones de permisos.ACCIONES que son suyas
    # archivo de rutas → otros módulos que además deben estar activos para esas pantallas (sin ser requisito del módulo)
    tambien: dict = field(default_factory=dict)
    # Lo que el módulo aporta a las pantallas que juntan cosas de varios (punto de extensión → función o lista): ver
    # PUNTOS. Los agregadores recorren `aportes(punto)` y así no importan de ningún paquete.
    aportes: dict = field(default_factory=dict)
    privacidad: tuple[str, ...] = ()       # claves de privacidad.TRATAMIENTOS: datos personales que trata este módulo


# Conjunto inicial de una instalación nueva (TAU_PERFIL); después manda el panel. «completo» son todos.
PERFILES = {
    "minimo": ("comunicados",),
    "instituto": ("investigacion", "informes", "comunicados"),
    "carrera": ("planes", "oferta", "estudiantes", "comunicados"),
    "carrera_instituto": ("investigacion", "informes", "planes", "oferta", "estudiantes", "comunicados"),
    "completo": None,
}

# Puntos de extensión (PLAN §73, etapa 2) y qué entrega cada aporte:
#   menu, menu_estudiante  f(auth) → [(grupo, orden, ítem de app.comun.menu.item)]
#   busqueda               [(orden, título, icono, f(q, auth, límite) → [{texto, href, detalle}])]
#   inicio                 f(auth) → [(sección, orden, {texto, href, tono, detalle})]   pendientes de la bandeja
#   cifras                 f(auth) → [(orden, título, [(valor, texto, href)])]          fila de cifras del inicio
#   pendientes             f(ámbito, quién, hoy) → pendientes (app.comun.calendario.pendiente)    «Mis pendientes»
#   eventos                f(ámbito, quién, desde, hasta) → eventos (app.comun.calendario.evento)  «Mi calendario»
#   bloque_pendientes      f(auth, volver) → un bloque sobre la lista de pendientes, o ""
#   mantenimiento          [tareas periódicas sin argumentos]   (main._correr_mantenimiento)
#   en_curso               f() → ["2 convocatorias publicadas", …]   lo que el panel avisa antes de apagar el módulo
#   historial              f(uid) → secciones de «Mi historial docente» (academico.historial.secciones)
#   certificados           f(uid) → certificados que la persona puede emitir (app.comun.certificados.cert)
#   titulares_de_certificados  f() → ids de las personas que pueden tener alguno (para verificar un código)
PUNTOS = ("menu", "menu_estudiante", "busqueda", "inicio", "cifras", "pendientes", "eventos", "bloque_pendientes",
          "mantenimiento", "en_curso", "historial", "certificados", "titulares_de_certificados")

_registro: dict[str, Modulo] = {}
_por_accion: dict[str, str] = {}


def registrar(*modulos: Modulo):
    """Agrega módulos al registro. Repetir el mismo es inocuo (cada prueba vuelve a crear la aplicación)."""
    for m in modulos:
        if _registro.get(m.clave, m) != m:
            raise ValueError(f"Dos módulos con la clave «{m.clave}».")
        if m.clave != PLATAFORMA and m.area not in AREAS:
            raise ValueError(f"El módulo «{m.clave}» no tiene un área válida.")
        if set(m.aportes) - set(PUNTOS):
            raise ValueError(f"El módulo «{m.clave}» aporta a un punto que no existe: {set(m.aportes) - set(PUNTOS)}.")
        for accion in m.acciones:
            if _por_accion.setdefault(accion, m.clave) != m.clave:
                raise ValueError(f"La acción «{accion}» está en dos módulos: {_por_accion[accion]} y {m.clave}.")
        _registro[m.clave] = m
    _direcciones.clear()


def todos() -> list[Modulo]:
    """Los módulos que se pueden activar y apagar (sin la plataforma), por área y nombre."""
    return sorted((m for m in _registro.values() if m.clave != PLATAFORMA),
                  key=lambda m: (AREAS.index(m.area), m.nombre))


def obtener(clave: str) -> Modulo | None:
    m = _registro.get(clave)
    return m if m and m.clave != PLATAFORMA else None


def de_accion(accion: str) -> str | None:
    """Clave del módulo dueño de la acción (PLATAFORMA si es de la plataforma; None si nadie la declaró)."""
    return _por_accion.get(accion)


def de_python(nombre: str) -> tuple[str, ...] | None:
    """Módulos que deben estar activos para una ruta definida en ese módulo de Python: () si es de la plataforma y
    None si ningún manifiesto lo declara. Gana el prefijo más largo (`app.comun.rutas.piloto` antes que `app.comun`)."""
    if not nombre.startswith(("app.", "main")):
        return ()   # rutas de FastHTML (archivos estáticos)
    mejor, largo = None, -1
    for m in _registro.values():
        for prefijo in m.rutas:
            if (nombre == prefijo or nombre.startswith(prefijo + ".")) and len(prefijo) > largo:
                mejor, largo = m, len(prefijo)
    if mejor is None:
        return None
    if mejor.clave == PLATAFORMA:
        return ()
    extra = next((v for k, v in mejor.tambien.items() if nombre == k or nombre.startswith(k + ".")), ())
    return (mejor.clave, *extra)


# --- Estado ------------------------------------------------------------------------------------------------

_estado: dict[str, tuple[float, dict]] = {}   # base de datos → (cuándo se leyó, {clave: activo})
VIGENCIA_S = 10   # lo que tarda en verse un cambio hecho por otro proceso (un script); el propio lo ve en el acto


def _leer() -> dict:
    base = str(db._ruta)
    guardado = _estado.get(base)
    if guardado and time.monotonic() - guardado[0] < VIGENCIA_S:
        return guardado[1]
    estado = {f["clave"]: bool(f["activo"]) for f in get_db().q("SELECT clave, activo FROM modulo")}
    _estado[base] = (time.monotonic(), estado)
    return estado


def _olvidar():
    _estado.pop(str(db._ruta), None)


def activo(clave: str) -> bool:
    """¿Está activo? La plataforma, siempre; un módulo sin fila en la tabla, no."""
    return clave == PLATAFORMA or _leer().get(clave, False)


def accion_activa(accion: str) -> bool:
    """¿El módulo dueño de la acción está activo? Una acción sin dueño cuenta como de la plataforma (lo vigila
    tests/test_modulos.py)."""
    return activo(_por_accion.get(accion, PLATAFORMA))


def sembrar(perfil: str = "minimo"):
    """Deja una fila por módulo registrado. En una base nueva (tabla vacía), activa los del perfil con sus requisitos;
    en una que ya tiene filas, un módulo nuevo entra apagado: lo activa la Administración."""
    if perfil not in PERFILES:
        raise ValueError(f"Perfil desconocido: {perfil} (use {', '.join(PERFILES)}).")
    claves = [m.clave for m in todos()]
    existentes = {f["clave"] for f in get_db().q("SELECT clave FROM modulo")}
    if existentes >= set(claves):
        return
    del_perfil = set(claves if PERFILES[perfil] is None else PERFILES[perfil]) if not existentes else set()
    activos = {r for c in del_perfil if c in _registro for r in (c, *_requisitos(c))}
    with transaccion():
        for clave in claves:
            if clave not in existentes:
                get_db().t.modulo.insert(clave=clave, activo=int(clave in activos))
    _olvidar()


def _requisitos(clave: str) -> list[str]:
    """Todos los módulos que `clave` necesita, directos e indirectos, en el orden en que hay que activarlos."""
    orden = []

    def visitar(c):
        for r in _registro[c].requiere:
            if r not in orden:
                visitar(r)
                orden.append(r)
    visitar(clave)
    return orden


def faltan_para(clave: str) -> list[Modulo]:
    """Requisitos de `clave` que hoy están apagados (se activan con él)."""
    return [_registro[r] for r in _requisitos(clave) if not activo(r)]


def dependientes_activos(clave: str) -> list[Modulo]:
    """Módulos activos que necesitan a `clave`: mientras existan, no se puede apagar."""
    return [m for m in todos() if m.clave != clave and activo(m.clave) and clave in _requisitos(m.clave)]


def cambiar(clave: str, activar: bool, usuario_id: int | None) -> tuple[list[str], list[str]]:
    """Activa (con sus requisitos) o apaga un módulo. → (errores, nombres de los módulos que cambiaron)."""
    m = obtener(clave)
    if not m:
        return ["Módulo desconocido."], []
    if activar:
        cambian = [r for r in faltan_para(clave)] + ([m] if not activo(clave) else [])
    else:
        if (dep := dependientes_activos(clave)):
            return [f"No se puede apagar: lo necesitan {', '.join(d.nombre for d in dep)}. Apague antes esos módulos."], []
        cambian = [m] if activo(clave) else []
    with transaccion():
        for c in cambian:
            get_db().execute("UPDATE modulo SET activo = ?, cambiado_por = ?, cambiado_en = ? WHERE clave = ?",
                             [int(activar), usuario_id, marca_tiempo(), c.clave])
            auditar(usuario_id, "activar_modulo" if activar else "apagar_modulo", "modulo", None, c.nombre)
    _olvidar()
    return [], [c.nombre for c in cambian]


def estado() -> list[dict]:
    """Para el panel: cada módulo con su estado, quién lo cambió y cuándo."""
    filas = {f["clave"]: f for f in get_db().q(
        """SELECT m.*, u.nombres || ' ' || u.apellidos AS cambiado_por_nombre
           FROM modulo m LEFT JOIN usuario u ON u.id = m.cambiado_por""")}
    return [{"modulo": m, "activo": bool(filas.get(m.clave, {}).get("activo")),
             "cambiado_en": filas.get(m.clave, {}).get("cambiado_en"),
             "cambiado_por": filas.get(m.clave, {}).get("cambiado_por_nombre")} for m in todos()]


def aportes(punto: str) -> list:
    """Lo que aportan a ese punto de extensión la plataforma y los módulos **activos**, en el orden del registro."""
    return [m.aportes[punto] for m in _registro.values() if punto in m.aportes and activo(m.clave)]


def en_curso(clave: str) -> list[str]:
    """Lo que el módulo tiene en marcha (una convocatoria publicada, una encuesta abierta): se avisa antes de apagarlo."""
    m = _registro.get(clave)
    return list(m.aportes["en_curso"]()) if m and "en_curso" in m.aportes else []


def tratamientos_activos() -> set[str]:
    """Claves de privacidad.TRATAMIENTOS de la plataforma y de los módulos activos."""
    return {c for m in _registro.values() if activo(m.clave) for c in m.privacidad}


# --- Compuerta ---------------------------------------------------------------------------------------------

_direcciones: dict[str, tuple[str, ...]] = {}   # dirección sin consulta → módulos que exige (se llena al preguntar)
_rutas: list = []                               # (expresión de la ruta, módulos) de la aplicación en marcha


def _original(endpoint):
    """FastHTML envuelve la función de la ruta: se busca la del paquete `app` en su clausura."""
    for celda in getattr(endpoint, "__closure__", None) or ():
        try:
            f = celda.cell_contents
        except ValueError:
            continue
        if inspect.isfunction(f) and not f.__module__.startswith(("fasthtml", "starlette")):
            return f
    return endpoint


def marcar_rutas(app):
    """Anota en cada ruta de la aplicación los módulos que exige (`ruta.modulos`). Una ruta sin dueño es un error al
    arrancar: así ninguna pantalla nueva queda fuera de la compuerta por olvido."""
    _rutas.clear()
    _direcciones.clear()
    sin_duenio = []
    for ruta in app.routes:
        endpoint = getattr(ruta, "endpoint", None)
        if endpoint is None:   # montajes (archivos estáticos)
            continue
        claves = de_python(_original(endpoint).__module__)
        if claves is None:
            sin_duenio.append(f"{ruta.path} ({_original(endpoint).__module__})")
            continue
        ruta.modulos = claves
        _rutas.append((ruta.path_regex, claves))
    if sin_duenio:
        raise RuntimeError("Rutas que ningún módulo declara (agregue su archivo al manifiesto de su paquete, "
                           f"app/<paquete>/modulo.py): {sin_duenio}")


def _compuerta(req):
    claves = getattr(req.scope.get("route"), "modulos", ())
    if any(not activo(c) for c in claves):
        return Response("No encontrado", status_code=404)


# Sin rutas excluidas y la primera de la cadena: también cierra las públicas (/publico, /api/v1, /encuesta/…).
compuerta = Beforeware(_compuerta)


def direccion_activa(href: str) -> bool:
    """¿Lleva a una pantalla de un módulo activo? Para no mostrar enlaces que darían 404 (menú, inicio).
    Una dirección que no es del sistema (otro sitio, un ancla) cuenta como activa."""
    camino = href.split("?")[0].split("#")[0]
    if camino not in _direcciones:
        _direcciones[camino] = next((claves for expresion, claves in _rutas if expresion.match(camino)), ())
    return all(activo(c) for c in _direcciones[camino])
