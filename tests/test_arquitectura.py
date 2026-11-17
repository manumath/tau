"""Dependencias entre paquetes de `app/` (PLAN §73, etapa 0): la línea base solo puede achicarse.

TAU se va a poder instalar con módulos apagados (docs/modularizacion-plan.md). Para eso, un paquete no debe apoyarse
en otro sin que quede declarado. Esta prueba recorre los `import` de `app/` y exige:

- `app/comun` no importa de ningún otro paquete ni de los agregadores (es la plataforma);
- ningún paquete importa de los agregadores (`inicio`, `busqueda`, `navegacion`, `manifiestos`), que solo usa `main.py`;
- todo cruce entre paquetes está en `CRUCES` (archivo → paquetes de los que importa), agrupados por su motivo. Eran 82
  el 15-nov-2026; cada etapa de la modularización quita los suyos.

Si esta prueba falla por un **cruce nuevo**: no lo agregue a la lista sin más. Lo normal es que el dato o la función
esté mal ubicado (lo común va a `app/comun`) o que haga falta un punto de extensión (el módulo aporta, el agregador
recorre). Agréguelo a `CRUCES` solo si es una dependencia real entre módulos y anótelo en el plan.
Si falla por un **cruce que ya no existe**: quite la entrada; así la lista no vuelve a crecer en silencio.
"""
import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
PAQUETES = ("comun", "investigacion", "informes", "academico", "calidad", "estudiantil", "egresados", "ia", "servicios")
# Archivos que juntan lo de varios paquetes (pantallas y el catálogo de módulos): pueden importar de todos, pero nadie
# importa de ellos.
AGREGADORES = ("inicio", "busqueda", "navegacion", "manifiestos", "instalacion")

# archivo (relativo a app/) → paquetes de los que importa, sin contar `comun` ni el propio.
CRUCES = {
    # El catálogo de módulos importa el manifiesto (`modulo.py`) de cada paquete: es su trabajo (PLAN §73, etapa 1).
    "instalacion.py": {"academico", "calidad"},     # la carga de una instancia usa los importadores de cada paquete (PLAN §74)
    "manifiestos.py": {"academico", "calidad", "egresados", "estudiantil", "ia", "informes", "investigacion", "servicios"},
    # Requisito declarado en el manifiesto: el módulo exige al otro (`requiere=` o `tambien=`), así que puede importarlo.
    # Informes de investigación → investigación; egresados → estudiantes; «Mi plan» → planes; la evaluación docente
    # tiene pantallas en dos paquetes; los informes de docencia y de estudiantes viven en `calidad`.
    "informes/anexo.py": {"academico", "investigacion"},
    "informes/calidad_datos.py": {"academico", "investigacion"},
    "informes/estudiantes.py": {"investigacion"},
    "informes/informes.py": {"calidad", "investigacion"},
    "informes/programados.py": {"academico", "calidad"},
    "informes/rutas/anexo.py": {"investigacion"},
    "informes/rutas/informes.py": {"calidad", "ia", "investigacion"},
    "egresados/egresados.py": {"estudiantil"},
    "egresados/rutas/egresados.py": {"estudiantil"},
    "estudiantil/mi_plan.py": {"academico"},
    "estudiantil/rutas/mi_plan.py": {"academico"},
    "estudiantil/rutas/evaluacion.py": {"academico"},
    "calidad/cuerpo_academico.py": {"academico", "informes"},
    "calidad/rutas/cuerpo_academico.py": {"academico"},
    "calidad/rutas/seguimiento_estudiantil.py": {"estudiantil"},
    "calidad/seguimiento_estudiantil.py": {"egresados", "estudiantil"},
    # Uso opcional de la IA: el botón desaparece solo con el módulo apagado (`ia.servicio.activa`). El catálogo de la IA
    # arma el contexto de cada función con datos de los otros módulos.
    "calidad/rutas/autoevaluacion.py": {"ia"},
    "estudiantil/rutas/encuestas.py": {"ia"},
    "investigacion/rutas/investigadores.py": {"ia"},
    "investigacion/rutas/perfil.py": {"ia"},
    "investigacion/rutas/productos/ficha.py": {"ia"},
    "investigacion/rutas/publico.py": {"ia"},
    "ia/catalogo.py": {"calidad", "investigacion"},
    # Calidad mide a los demás: sus indicadores, su ficha y sus listados leen datos de otros módulos sin exigirlos. Con uno
    # apagado, el indicador queda «sin fuente» (`indicadores.FUENTES`), no en cero.
    "calidad/indicadores.py": {"academico", "egresados", "estudiantil", "informes"},
    "calidad/ficha.py": {"academico", "estudiantil"},
    "calidad/listados.py": {"academico", "informes", "investigacion"},
    "calidad/capacitacion.py": {"informes"},
    "calidad/rutas/evidencias.py": {"informes"},
    "calidad/rutas/impacto.py": {"investigacion"},
    # Nudos que quedan (PLAN §73): no agregue otros.
    "investigacion/rutas/bibtex.py": {"informes"},
    "servicios/auxiliaturas.py": {"investigacion"},
    "servicios/oportunidades.py": {"investigacion"},
    "servicios/rutas/oportunidades.py": {"egresados"},
    "servicios/rutas/recursos.py": {"academico"},
}


def _destinos(arbol: ast.AST, paquete_propio: str) -> set[str]:
    """Primer nivel bajo `app` de cada import absoluto del archivo (también los que están dentro de una función)."""
    res = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            partes = nodo.module.split(".")
            if partes[0] != "app":
                continue
            # `from app import calidad, navegacion` nombra los paquetes en la lista; el resto, en el módulo.
            res.update(a.name for a in nodo.names) if len(partes) == 1 else res.add(partes[1])
        elif isinstance(nodo, ast.Import):
            res.update(a.name.split(".")[1] for a in nodo.names if a.name.startswith("app."))
    return {d for d in res if d in PAQUETES + AGREGADORES and d != paquete_propio}


def cruces() -> dict[str, set[str]]:
    """archivo → paquetes y agregadores ajenos de los que importa (con `comun` incluido como destino)."""
    res = {}
    for archivo in sorted(APP.rglob("*.py")):
        rel = archivo.relative_to(APP)
        propio = rel.parts[0] if len(rel.parts) > 1 else rel.stem
        destinos = _destinos(ast.parse(archivo.read_text(encoding="utf-8")), propio)
        if destinos:
            res[rel.as_posix()] = destinos
    return res


def test_comun_no_importa_de_otros_paquetes():
    culpables = {a: d for a, d in cruces().items() if a.startswith("comun/")}
    assert not culpables, f"app/comun es la plataforma y no importa de otros paquetes: {culpables}"


def test_nadie_importa_de_los_agregadores():
    culpables = {a: d & set(AGREGADORES) for a, d in cruces().items() if d & set(AGREGADORES)}
    assert not culpables, f"inicio, busqueda y navegacion solo los arma main.py: {culpables}"


def test_los_cruces_entre_paquetes_son_los_declarados():
    reales = {a: d - {"comun"} - set(AGREGADORES) for a, d in cruces().items()}
    reales = {a: d for a, d in reales.items() if d}
    nuevos = {a: sorted(d - CRUCES.get(a, set())) for a, d in reales.items() if d - CRUCES.get(a, set())}
    assert not nuevos, ("Cruce nuevo entre paquetes (vea el encabezado de esta prueba antes de agregarlo a CRUCES): "
                        f"{nuevos}")
    sobran = {a: sorted(d - reales.get(a, set())) for a, d in CRUCES.items() if d - reales.get(a, set())}
    assert not sobran, f"Estos cruces ya no existen: quítelos de CRUCES para que no vuelvan. {sobran}"


def test_la_revision_detecta_un_cruce():
    """La prueba no pasa en vacío: reconoce los import absolutos, con alias y dentro de una función."""
    codigo = ("from app.calidad import mejora\nimport app.servicios.grado as g\nfrom app import ia, comun\n"
              "def f():\n    from app.estudiantil.rutas import estudiante\n")
    assert _destinos(ast.parse(codigo), "academico") == {"calidad", "servicios", "ia", "comun", "estudiantil"}
    assert len(CRUCES) > 20 and "manifiestos.py" in cruces()
