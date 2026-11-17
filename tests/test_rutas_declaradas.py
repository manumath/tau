"""Toda ruta declara quién puede usarla (PLAN §62, etapa 7).

Recorre las rutas de la aplicación y exige, para cada una, una de estas cosas:
- es pública (`auth.RUTAS_PUBLICAS`) o de `/admin` (la decide `auth.REGLAS_ADMIN` antes de llegar a la ruta);
- su función, o las que llama (hasta tres niveles dentro de `app.`), comprueba algo: un permiso (`puede`), que el dato
  es de quien pide (`auth["id"]`, la ficha del estudiante), o responde 403 o 404;
- o está en `TODO_EL_PERSONAL`, con el motivo por el que cualquier cuenta del personal puede usarla.

Si agrega una ruta y esta prueba falla: ponga el control en la ruta (lo normal) o, si de verdad es para todo el
personal, agréguela a la lista con su motivo. Las cuentas de estudiante no llegan a ninguna ruta fuera de
`auth.RUTAS_ESTUDIANTE` (lo vigila `tests/test_portal_estudiante.py`).
"""
import ast
import inspect
import re
import textwrap

from app.comun import auth

CONTROL = re.compile(r"puede\(|_puede\b|acceso_admin|status_code=403|\b40[34]\b|No autorizado|_no_autorizado\(|"
                     r"no_encontrado\(|cuenta_de\(|_requiere\(|es_tutor|solo_estudiante|auth\[.id.\]")

TODO_EL_PERSONAL = {  # ruta → motivo
    "/logout": "salir de la sesión propia",
    "/buscar/sugerencias": "búsqueda global; cada resultado lo filtra su propio módulo según quién busca",
    "/perfil/bio/vista-previa": "vista previa del texto que se está escribiendo; no lee datos guardados",
    "/productos/importar-bibtex": "formulario vacío; lo que se importa queda a nombre de quien lo envía",
    "/investigadores/resultados": "directorio de investigadores, público dentro del sistema",
    "/actividades/campos": "campos del formulario según el tipo elegido",
    "/productos/revistas": "sugerencias del catálogo de revistas",
    "/productos/msc/buscar": "sugerencias de la clasificación MSC",
    "/productos/msc/fila": "fila de formulario con un código MSC",
    "/personas/buscar": "sugerencias de coautores al cargar un producto",
    "/personas/fila": "fila de formulario con un coautor elegido",
    "/personas/externo/nuevo": "formulario vacío para un coautor externo",
    "/proyectos/pendientes/contador": "contador del menú: cuenta solo lo que esa persona debe revisar",
    "/informes/acreditacion{resto:path}": "dirección antigua: redirige a la nueva, que controla el acceso",
    "/docencia/oferta/plantilla": "plantilla CSV vacía",
    "/ia/guia": "guía de uso de la IA, para todo el personal",
}


def _original(endpoint):
    """FastHTML envuelve la función de la ruta: se busca la del paquete app en su clausura."""
    for celda in endpoint.__closure__ or ():
        f = celda.cell_contents
        if inspect.isfunction(f) and not f.__module__.startswith("fasthtml"):
            return f
    return endpoint


def _fuente(f, niveles=3, vistos=None) -> str:
    """Código de la función y de las funciones de app.* que llama, hasta `niveles` de profundidad."""
    vistos = set() if vistos is None else vistos
    if f in vistos:
        return ""
    vistos.add(f)
    try:
        src = textwrap.dedent(inspect.getsource(f))
    except (OSError, TypeError):
        return ""
    partes = [src]
    if niveles:
        for nodo in ast.walk(ast.parse(src)):
            if not isinstance(nodo, ast.Call):
                continue
            fn, obj = nodo.func, None
            if isinstance(fn, ast.Name):
                obj = f.__globals__.get(fn.id)
            elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                obj = getattr(f.__globals__.get(fn.value.id), fn.attr, None)
            if inspect.isfunction(obj) and obj.__module__.startswith("app."):
                partes.append(_fuente(obj, niveles - 1, vistos))
    return "\n".join(partes)


def _rutas(app):
    for r in app.routes:
        ruta, endpoint = getattr(r, "path", None), getattr(r, "endpoint", None)
        if ruta and endpoint and not ruta.startswith("/static"):
            yield ruta, _original(endpoint)


def _sin_control(app) -> set[str]:
    sin = set()
    for ruta, f in _rutas(app):
        if ruta.startswith("/admin") or any(re.fullmatch(p, ruta) for p in auth.RUTAS_PUBLICAS) \
                or any(re.fullmatch(p, ruta.replace("{", "x").replace("}", "")) for p in auth.RUTAS_PUBLICAS):
            continue
        if not CONTROL.search(_fuente(f)):
            sin.add(ruta)
    return sin


def test_toda_ruta_declara_quien_la_usa(app):
    sin = _sin_control(app) - TODO_EL_PERSONAL.keys()
    assert not sin, ("Rutas sin control de acceso reconocible. Compruebe el permiso en la ruta o, si son para todo el "
                     "personal, agréguelas a TODO_EL_PERSONAL con su motivo:\n" + "\n".join(sorted(sin)))


def test_la_lista_del_personal_no_tiene_rutas_de_mas(app):
    """Una ruta que ya no existe, o que ahora tiene control, sale de la lista (la lista no crece sola)."""
    existentes = {ruta for ruta, _ in _rutas(app)}
    assert not TODO_EL_PERSONAL.keys() - existentes, "rutas que ya no existen"
    assert not TODO_EL_PERSONAL.keys() - _sin_control(app), "rutas que ya tienen control propio"


def test_la_prueba_detecta_una_ruta_sin_control(app):
    """La prueba misma funciona: una ruta nueva sin control aparece."""
    from fasthtml.common import APIRouter
    rt = APIRouter()

    @rt("/ruta-de-prueba-sin-control")
    def get():
        return "datos"

    rt.to_app(app)
    assert "/ruta-de-prueba-sin-control" in _sin_control(app)
