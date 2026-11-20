"""Instalación desde cero (PLAN §74): el esquema base no trae datos de ninguna unidad y una instancia los carga."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import main
from app.comun import config, modulos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import PASS_ADMIN, _init_db_real, login

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLO = RAIZ / "instancias" / "ejemplo"


def _instalar(db: Path, instancia: Path = EJEMPLO, *extra) -> subprocess.CompletedProcess:
    """En otro proceso, como lo corre quien instala (y porque la carga abre la base con sqlite3)."""
    entorno = {k: v for k, v in os.environ.items() if k != "TAU_PERFIL"}      # el perfil lo decide la instancia
    return subprocess.run([sys.executable, "scripts/instalar.py", "--db", str(db), "--instancia", str(instancia), *extra],
                          cwd=RAIZ, capture_output=True, text=True, env=entorno)


def test_el_esquema_base_no_trae_datos_de_ninguna_unidad(tmp_path):
    _init_db_real(tmp_path / "vacia.db")                 # sin la plantilla de las pruebas: solo migrations/
    db = get_db()
    assert [(u["tipo"], u["sigla"]) for u in db.q("SELECT tipo, sigla FROM unidad ORDER BY id")] == [
        ("universidad", "UNIV"), ("facultad", "FAC"), ("carrera", "CARR"), ("instituto", "INST")]
    for tabla in ("plan_estudios", "asignatura", "marco_calidad", "linea_investigacion", "area_investigacion", "msc",
                  "usuario", "modulo"):
        assert db.q(f"SELECT COUNT(*) n FROM {tabla}")[0]["n"] == 0, tabla
    assert db.q("SELECT COUNT(*) n FROM tipo_producto")[0]["n"] > 0     # los datos de referencia sí vienen
    assert [p.name for p in config.MIGRACIONES.glob("0*")] == ["0001-esquema.sql"]


def test_instalar_la_instancia_de_ejemplo_y_usar_el_sistema(tmp_path):
    db = tmp_path / "ejemplo.db"
    r = _instalar(db)
    assert r.returncode == 0, r.stderr
    assert "planes de estudio" in r.stdout and "crear_admin" in r.stdout
    app = TestClient(main.create_app(db))
    assert unidades.obtener(unidades.carrera())["nombre"] == "Carrera de Ejemplo" and config.NOMBRE_CARRERA == "Carrera de Ejemplo"
    assert config.UNIVERSIDAD == "Universidad de Demostración"
    assert {c for c in (m.clave for m in modulos.todos()) if modulos.activo(c)} == {
        "investigacion", "informes", "planes", "oferta", "estudiantes", "comunicados"}     # perfil de su instancia.toml
    plan = get_db().q("SELECT * FROM plan_estudios")
    assert len(plan) == 1 and plan[0]["estado"] == "vigente" and plan[0]["duracion_semestres"] == 4
    assert get_db().q("SELECT COUNT(*) n FROM observacion_plan")[0]["n"] == 0             # la malla de ejemplo cuadra
    assert get_db().q("SELECT COUNT(*) n FROM indicador_calidad")[0]["n"] == 9
    usuarios.crear("admin@ejemplo.test", "Ana", "Admin", PASS_ADMIN, es_admin=True, es_investigador=False,
                   debe_cambiar_pass=False)
    assert login(app, "admin@ejemplo.test", PASS_ADMIN).headers["hx-redirect"] == "/"
    for ruta in ("/", "/admin/unidades", "/admin/modulos", "/docencia/planes", "/docencia/planes/1", "/publico/privacidad"):
        assert app.get(ruta).status_code == 200, ruta
    assert "Carrera de Ejemplo" in app.get("/admin/unidades").text
    assert app.get("/calidad/marco").status_code == 404                # ese módulo no está en su perfil
    # Sobre una base con cuentas no se vuelve a cargar una instancia.
    get_db().conn.close()
    otra = _instalar(db)
    assert otra.returncode != 0 and "ya tiene cuentas" in (otra.stderr + otra.stdout)


def test_el_perfil_se_puede_imponer_al_instalar(tmp_path):
    db = tmp_path / "minima.db"
    assert _instalar(db, EJEMPLO, "--perfil", "minimo").returncode == 0
    con = sqlite3.connect(db)
    assert [f[0] for f in con.execute("SELECT clave FROM modulo WHERE activo = 1")] == ["comunicados"]
    con.close()


def test_una_base_de_otra_version_no_arranca(app, tmp_path):
    """P. ej., una base anterior al esquema base: su número de esquema es mayor que el del código."""
    get_db().execute("UPDATE _meta SET version = 96")
    with pytest.raises(RuntimeError, match="es de otra versión del sistema"):
        _init_db_real(tmp_path / "test.db")


def test_ningun_texto_de_app_nombra_a_una_unidad():
    """Los nombres y las siglas de una universidad, una carrera o un instituto son de la instancia: en `app/` no hay
    textos que los nombren (los comentarios y la documentación del código pueden contar de dónde viene una regla)."""
    import ast
    import re
    propios = re.compile(r"UMSA|FCPN|IIMAT|CMAT|Carrera de Matem|San Andrés|umsa\.bo|Investigación Matemática")
    # El reglamento de auxiliaturas que implementa ese módulo es una resolución del HCU de la UMSA: se cita por su nombre.
    permitidos = {"servicios/auxiliaturas.py", "servicios/rutas/auxiliaturas.py", "servicios/rutas/designaciones.py",
                  "servicios/rutas/formularios.py", "servicios/rubricas.py", "servicios/designaciones.py"}
    hallados = []
    for archivo in sorted((RAIZ / "app").rglob("*.py")):
        rel = archivo.relative_to(RAIZ / "app").as_posix()
        if rel in permitidos:
            continue
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        documentacion = {id(n.body[0].value) for n in ast.walk(arbol)
                         if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body
                         and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in documentacion \
                    and propios.search(nodo.value):
                hallados.append(f"{rel}:{nodo.lineno}: {nodo.value[:60]!r}")
    for instruccion in sorted((RAIZ / "app" / "ia" / "instrucciones").rglob("*.md")):
        if propios.search(instruccion.read_text(encoding="utf-8")):
            hallados.append(str(instruccion.relative_to(RAIZ)))
    assert hallados == []


def test_las_instrucciones_de_la_ia_llevan_los_nombres_de_la_instalacion(app):
    from app.ia import servicio
    _, texto = servicio.instrucciones("memoria_borrador")
    assert config.NOMBRE_INSTITUTO in texto and config.NOMBRE_CARRERA in texto and "{" not in texto.split("\n")[0]


def test_las_variables_viejas_se_avisan(tmp_path):
    """Hasta el 17-nov-2026 se llamaban PORTAL_*: una instalación que aún las tenga no se queda mal configurada en silencio."""
    r = subprocess.run([sys.executable, "-c", "from app.comun import config; print(config.NOMBRE_SISTEMA)"], cwd=RAIZ,
                       capture_output=True, text=True, env={**os.environ, "PORTAL_SECRET_KEY": "x", "PORTAL_DB": "y"})
    assert "PORTAL_DB, PORTAL_SECRET_KEY" in r.stdout and "TAU_" in r.stdout
    sin = subprocess.run([sys.executable, "-c", "from app.comun import config"], cwd=RAIZ, capture_output=True, text=True,
                         env={k: v for k, v in os.environ.items() if not k.startswith("PORTAL_")})
    assert "AVISO" not in sin.stdout
