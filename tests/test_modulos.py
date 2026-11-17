"""Módulos del sistema (PLAN §73, etapa 1): registro, compuerta de rutas, permisos, perfiles y panel.

Las demás pruebas corren con todos los módulos activos (`TAU_PERFIL=completo` en conftest.py); aquí se apagan.
"""
import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import main
from app import manifiestos
from app.comun import config, modulos, permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_ADMIN, login

manifiestos.registrar()   # para parametrizar por módulo al recolectar las pruebas
CLAVES = [m.clave for m in modulos.todos()]


def _solo(*activos):
    """Deja activos solo esos módulos (sin mirar requisitos: las pruebas arman el estado que quieren)."""
    get_db().execute("UPDATE modulo SET activo = 0")
    for clave in activos:
        get_db().execute("UPDATE modulo SET activo = 1 WHERE clave = ?", [clave])
    modulos._olvidar()


def _apagar(*claves):
    _solo(*[c for c in CLAVES if c not in claves])


def _concreta(ruta: str) -> str:
    return re.sub(r"\{(\w+)(:[^}]*)?\}", "1", ruta)


def _rutas_de(app, clave):
    return [r for r in app.routes if clave in getattr(r, "modulos", ())]


# --- Registro ------------------------------------------------------------------------------------------------------

def test_toda_accion_tiene_duenio(app):
    """Cada acción de permisos es de un módulo o de la plataforma: una sin dueño seguiría viva con todo apagado."""
    assert [a for a in permisos.ACCIONES if modulos.de_accion(a) is None] == []
    declaradas = {a for m in [*modulos.todos(), modulos._registro[modulos.PLATAFORMA]] for a in m.acciones}
    assert declaradas - set(permisos.ACCIONES) == set(), "un manifiesto nombra una acción que no existe"


def test_toda_ruta_tiene_duenio(app):
    """`marcar_rutas` impide arrancar con una ruta sin dueño; aquí, que todas quedaron anotadas y que cada módulo
    tiene pantallas."""
    assert [r.path for r in app.routes if getattr(r, "endpoint", None) and not hasattr(r, "modulos")] == []
    assert [c for c in CLAVES if not _rutas_de(app, c)] == []
    por_ruta = {r.path: r.modulos for r in app.routes if hasattr(r, "modulos")}
    assert por_ruta["/login"] == () and por_ruta["/admin/modulos"] == () and por_ruta["/salud"] == ()
    assert por_ruta["/publico/privacidad"] == () and por_ruta["/publico"] == ()
    assert por_ruta["/fotos/{uid}"] == ()                              # las fotos las muestran todos los módulos
    assert por_ruta["/adjuntos/{adj_id}"] == ("investigacion",)        # adjuntos de productos y actividades
    assert por_ruta["/publico/investigadores"] == ("investigacion",)
    assert por_ruta["/estudiante/plan"] == ("estudiantes", "planes")
    assert por_ruta["/informes/cuerpo-academico"] == ("oferta",)     # vive en calidad, es de docencia


def test_una_ruta_sin_duenio_impide_arrancar(app, monkeypatch):
    monkeypatch.setattr(modulos, "_registro", {k: v for k, v in modulos._registro.items() if k != "ia"})
    with pytest.raises(RuntimeError, match="ningún módulo declara"):
        modulos.marcar_rutas(app)
    monkeypatch.undo()
    modulos.marcar_rutas(app)


def test_requisitos_y_perfiles_son_coherentes(app):
    for m in modulos.todos():
        assert all(modulos.obtener(r) for r in m.requiere), m.clave
        assert m.clave not in modulos._requisitos(m.clave), f"{m.clave} se requiere a sí mismo"
        assert all(modulos.obtener(c) for extra in m.tambien.values() for c in extra), m.clave
    for perfil, claves in modulos.PERFILES.items():
        assert all(modulos.obtener(c) for c in claves or ()), perfil


# --- Compuerta -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("clave", CLAVES)
def test_modulo_apagado_da_404_en_todas_sus_rutas(app, clave):
    """Sin sesión y con sesión de administración: ninguna ruta del módulo responde, tampoco las públicas."""
    _apagar(clave)
    anonimo, admin = TestClient(app), TestClient(app)
    login(admin, "admin@test.cl", PASS_ADMIN)
    rutas = _rutas_de(app, clave)
    assert rutas
    abiertas = []
    for r in rutas:
        metodo = "GET" if "GET" in r.methods else sorted(r.methods)[0]
        for cliente in (anonimo, admin):
            resp = cliente.request(metodo, _concreta(r.path), follow_redirects=False)
            if resp.status_code != 404:
                abiertas.append((metodo, r.path, resp.status_code))
    assert abiertas == []


def test_las_publicas_y_la_api_tambien_se_cierran(client):
    assert client.get("/publico/investigadores").status_code == 200
    assert client.get("/api/v1/investigadores").status_code == 200
    _apagar("investigacion")
    assert client.get("/publico/investigadores").status_code == 404
    assert client.get("/api/v1/investigadores").status_code == 404
    assert client.get("/publico/privacidad").status_code == 200      # la privacidad es de la plataforma
    _apagar("encuestas")
    assert client.get("/encuesta/un-enlace-cualquiera").status_code == 404
    _apagar()
    assert client.get("/publico/investigadores").status_code == 200  # reactivar devuelve todo


def test_una_pantalla_que_necesita_dos_modulos(client):
    usuarios.crear("est@test.cl", "Eva", "Estudiante", "Clave-larga-123", es_investigador=False, debe_cambiar_pass=False)
    _apagar("planes", "oferta", "evaluacion_docente", "auxiliaturas")
    assert client.get("/estudiante/plan", follow_redirects=False).status_code == 404
    assert client.get("/estudiante", follow_redirects=False).status_code != 404   # el portal sigue (pide ingresar)


def test_los_permisos_de_un_modulo_apagado_no_los_tiene_nadie(app):
    admin = usuarios.por_email("admin@test.cl")
    permisos.asignar(admin["id"], "direccion_carrera", unidades.id_de("CMAT"))
    assert permisos.puede(usuarios.por_email("admin@test.cl"), "gestionar_oferta")
    _apagar("oferta", "evaluacion_docente", "auxiliaturas")
    u = usuarios.por_email("admin@test.cl")
    assert not permisos.puede(u, "gestionar_oferta")
    assert permisos.puede(u, "gestionar_vinculos") and permisos.puede(u, "gestionar_modulos")   # la plataforma, siempre


def _enlaces_del_menu(app, cliente, email):
    from app import navegacion
    u = usuarios.con_perfil(usuarios.por_email(email)["id"])
    u["roles"] = permisos.roles_vigentes(u["id"])
    u["solo_estudiante"], u["es_tutor"] = False, False
    return [i["href"] for _, items in navegacion.menu(u) for i in items]


@pytest.mark.parametrize("activos", [(), modulos.PERFILES["instituto"], modulos.PERFILES["carrera"]])
def test_el_sistema_se_recorre_con_modulos_apagados(app, admin, activos):
    """Con el perfil mínimo (nada), el de instituto y el de carrera: la plataforma responde y ningún enlace del menú
    lleva a un 404, para quien tiene todos los roles."""
    uid = usuarios.por_email("admin@test.cl")["id"]
    for rol, sigla in (("direccion_carrera", "CMAT"), ("direccion_instituto", "IIMAT"), ("coordinacion_academica", "CMAT")):
        permisos.asignar(uid, rol, unidades.id_de(sigla))
    _solo(*activos)
    for ruta in ("/", "/admin/usuarios", "/admin/modulos", "/admin/auditoria", "/avisos", "/buscar?q=ada", "/mis-datos"):
        assert admin.get(ruta).status_code == 200, ruta
    enlaces = _enlaces_del_menu(app, admin, "admin@test.cl")
    assert "/admin/modulos" in enlaces
    rotos = [h for h in enlaces if admin.get(h, follow_redirects=False).status_code == 404]
    assert rotos == []
    if not activos:
        assert not any(h.startswith(("/docencia", "/calidad", "/servicios", "/productos")) for h in enlaces)


# --- Estado, perfiles y migración ------------------------------------------------------------------------------------

def test_una_base_nueva_arranca_con_el_perfil(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PERFIL", "minimo")
    main.create_app(tmp_path / "minima.db")
    assert [c for c in CLAVES if modulos.activo(c)] == ["comunicados"]
    monkeypatch.setattr(config, "PERFIL", "carrera")
    main.create_app(tmp_path / "carrera.db")
    assert {c for c in CLAVES if modulos.activo(c)} == {"planes", "oferta", "estudiantes", "comunicados"}
    main.create_app(tmp_path / "minima.db")          # el perfil no toca una base que ya tiene sus módulos
    assert [c for c in CLAVES if modulos.activo(c)] == ["comunicados"]
    monkeypatch.setattr(config, "PERFIL", "inventado")
    with pytest.raises(ValueError, match="Perfil desconocido"):
        main.create_app(tmp_path / "otra.db")


def test_un_modulo_nuevo_entra_apagado(app):
    get_db().execute("DELETE FROM modulo WHERE clave = 'ia'")
    modulos._olvidar()
    modulos.sembrar("completo")
    assert not modulos.activo("ia") and modulos.activo("investigacion")


def test_activar_trae_sus_requisitos_y_apagar_respeta_a_quien_depende(app):
    uid = usuarios.por_email("admin@test.cl")["id"]
    _solo()
    errores, cambiaron = modulos.cambiar("auxiliaturas", True, uid)
    assert errores == [] and cambiaron == ["Planes de estudio", "Oferta y asignación docente", "Seguimiento estudiantil",
                                           "Auxiliaturas"]
    errores, cambiaron = modulos.cambiar("planes", False, uid)
    assert cambiaron == [] and "Oferta y asignación docente" in errores[0] and modulos.activo("planes")
    assert modulos.cambiar("auxiliaturas", False, uid) == ([], ["Auxiliaturas"])
    assert modulos.cambiar("auxiliaturas", False, uid) == ([], [])       # ya estaba apagado
    assert modulos.cambiar("inventado", True, uid)[0] == ["Módulo desconocido."]
    acciones = [f["accion"] for f in get_db().q("SELECT accion FROM auditoria WHERE entidad = 'modulo' ORDER BY id")]
    assert acciones == ["activar_modulo"] * 4 + ["apagar_modulo"]


# --- Panel ---------------------------------------------------------------------------------------------------------

def test_panel_de_modulos(admin):
    pagina = admin.get("/admin/modulos")
    assert pagina.status_code == 200 and "17 de 17 módulos activos" in pagina.text
    assert "Auxiliaturas" in pagina.text and "Requiere: Oferta y asignación docente, Seguimiento estudiantil." in pagina.text
    assert admin.post("/admin/modulos/mejora/apagar", headers=HX).headers["hx-redirect"] == "/admin/modulos"
    assert not modulos.activo("mejora") and "16 de 17" in admin.get("/admin/modulos").text
    admin.post("/admin/modulos/calidad/apagar", headers=HX)
    admin.post("/admin/modulos/mejora/activar", headers=HX)             # activa también Aseguramiento de la calidad
    assert modulos.activo("mejora") and modulos.activo("calidad")
    admin.post("/admin/modulos/calidad/apagar", headers=HX)             # lo necesita el plan de mejora: no se apaga
    assert modulos.activo("calidad")
    assert admin.post("/admin/modulos/inventado/activar", headers=HX).status_code == 404


def test_panel_solo_para_la_administracion_del_sistema(client):
    assert login(client, "inv@test.cl", "Temp-clave-123").status_code == 200
    usuarios.cambiar_password(usuarios.por_email("inv@test.cl")["id"], "Otra-clave-1234", temporal=False)
    login(client, "inv@test.cl", "Otra-clave-1234")
    assert client.get("/admin/modulos").status_code == 403
    assert client.post("/admin/modulos/ia/apagar", headers=HX).status_code == 403
    assert modulos.activo("ia")


# --- Puntos de extensión (etapa 2): menú, búsqueda e inicio ---------------------------------------------------------

def test_los_aportes_son_solo_de_los_modulos_activos(app):
    from app import busqueda
    assert [t for _, t, _, _ in busqueda.grupos_activos()] == ["Personas", "Cuentas", "Productos", "Actividades",
                                                               "Proyectos", "Asignaturas"]
    _apagar("investigacion", "informes")
    assert [t for _, t, _, _ in busqueda.grupos_activos()] == ["Cuentas", "Asignaturas"]
    _solo()
    assert [t for _, t, _, _ in busqueda.grupos_activos()] == ["Cuentas"]
    assert len(modulos.aportes("menu")) == 1 and len(modulos.aportes("inicio")) == 1    # solo la plataforma


def test_la_busqueda_no_devuelve_lo_de_un_modulo_apagado(admin):
    from app import busqueda
    u = usuarios.con_perfil(usuarios.por_email("admin@test.cl")["id"])
    assert "Personas" in [g["titulo"] for g in busqueda.buscar("noether", u, 5)]
    _apagar("investigacion", "informes")
    grupos = busqueda.buscar("noether", u, 5)
    # Sin Investigación no hay «Personas»; la cuenta de la investigadora sale en «Cuentas» para quien las administra.
    assert [g["titulo"] for g in grupos] == ["Cuentas"] and grupos[0]["items"][0]["texto"] == "Emmy Noether"
    assert "/investigadores/" not in admin.get("/buscar?q=noether").text


def test_el_inicio_no_muestra_lo_de_un_modulo_apagado(admin):
    uid = usuarios.por_email("admin@test.cl")["id"]
    permisos.asignar(uid, "direccion_instituto", unidades.id_de("IIMAT"))
    con_todo = admin.get("/").text
    assert "Aseguramiento de la Calidad" in con_todo and 'href="/informes/memoria"' in con_todo
    _apagar("informes")          # las cifras del cuerpo académico las aporta ese módulo
    sin = admin.get("/").text
    assert "Aseguramiento de la Calidad" not in sin and "/informes/memoria" not in sin
    _solo()
    vacio = admin.get("/")           # sin módulos, la Administración ve por dónde empezar
    assert vacio.status_code == 200 and "Primeros pasos" in vacio.text and "Elija los módulos" in vacio.text


def test_los_agregadores_no_importan_de_ningun_paquete():
    """Menú, búsqueda e inicio solo recorren aportes: si vuelven a importar un paquete, se rehace el nudo."""
    from tests.test_arquitectura import cruces
    reales = cruces()
    assert [a for a in ("navegacion.py", "busqueda.py", "inicio.py") if reales.get(a, set()) - {"comun"}] == []


def test_todo_aporte_declara_un_punto_que_existe(app):
    for m in modulos._registro.values():
        assert set(m.aportes) <= set(modulos.PUNTOS), m.clave
    with pytest.raises(ValueError, match="punto que no existe"):
        modulos.registrar(modulos.Modulo("x", "X", "x", area="Transversal", aportes={"inventado": lambda a: []}))


# --- Etapa 3: pendientes, calendarios, tareas, privacidad y aviso al apagar ----------------------------------------

def test_pendientes_y_calendarios_solo_de_modulos_activos(app):
    from app.comun import calendario, privacidad
    con = {(m.clave, p) for m in modulos._registro.values() for p in m.aportes if modulos.activo(m.clave)}
    assert {("oferta", "pendientes"), ("grado", "eventos"), ("mejora", "bloque_pendientes")} <= con
    assert len(modulos.aportes("eventos")) >= 8 and len(modulos.aportes("mantenimiento")) == 6
    _solo("comunicados")
    assert len(modulos.aportes("eventos")) == 1 and len(modulos.aportes("pendientes")) == 1   # los de comunicados
    assert modulos.aportes("mantenimiento") == [] and calendario.bloques({"id": 1}, "/") == []
    uid = usuarios.por_email("inv@test.cl")["id"]
    assert calendario.pendientes_de("docente", uid) == [] and calendario.eventos_de("investigador", uid) == []
    # Cada tratamiento de datos personales es de un módulo, y la página de privacidad muestra solo los activos.
    declarados = [c for m in modulos._registro.values() for c in m.privacidad]
    assert sorted(declarados) == sorted(privacidad.TRATAMIENTOS)
    assert modulos.tratamientos_activos() == set()
    _apagar()
    assert modulos.tratamientos_activos() == set(privacidad.TRATAMIENTOS)


def test_la_pagina_de_privacidad_sigue_a_los_modulos(client):
    assert "Evaluación docente" in client.get("/publico/privacidad").text
    _apagar("evaluacion_docente")
    pagina = client.get("/publico/privacidad")
    assert pagina.status_code == 200 and 'id="evaluacion_docente"' not in pagina.text and 'id="estudiantes"' in pagina.text


def test_el_panel_avisa_lo_que_queda_en_curso(admin):
    assert modulos.en_curso("encuestas") == [] and modulos.en_curso("inventado") == []
    get_db().execute("INSERT INTO encuesta (titulo, tipo, anonima, publico, estado) "
                     "VALUES ('Clima', 'satisfaccion', 1, 'estudiantes', 'abierta')")
    assert modulos.en_curso("encuestas") == ["1 encuesta(s) abierta(s): sus enlaces dejarán de responder"]
    assert "En curso: 1 encuesta(s) abierta(s)" in admin.get("/admin/modulos").text
    _apagar("egresados")                      # ya nadie necesita las encuestas: aparece el botón, con el aviso
    assert "Ahora tiene en curso: 1 encuesta(s)" in admin.get("/admin/modulos").text
    for m in modulos.todos():                 # ninguna consulta de «en curso» falla sobre una base recién creada
        assert isinstance(modulos.en_curso(m.clave), list)


# --- Etapa 4: nudos de código ---------------------------------------------------------------------------------------

def test_las_paginas_publicas_siguen_a_los_modulos(client):
    assert client.get("/publico", follow_redirects=False).headers["location"] == "/publico/investigadores"
    assert 'href="/publico/indicadores"' in client.get("/publico/privacidad").text
    _apagar("investigacion", "informes")
    assert client.get("/publico", follow_redirects=False).headers["location"] == "/publico/indicadores"
    _solo()
    assert client.get("/publico", follow_redirects=False).headers["location"] == "/publico/privacidad"
    pagina = client.get("/publico/privacidad").text
    assert "/publico/investigadores" not in pagina and "/publico/indicadores" not in pagina


def test_con_la_ia_apagada_ninguna_funcion_esta_activa(app):
    from app.ia import servicio
    get_db().execute("UPDATE ia_funcion SET activa = 1")
    claves = [f["clave"] for f in get_db().q("SELECT clave FROM ia_funcion")]
    if claves:
        assert servicio.activa(claves[0])
        _apagar("ia")
        assert not any(servicio.activa(c) for c in claves)
    _apagar("ia")
    assert not servicio.activa("cualquiera")


def test_la_ficha_del_estudiante_sale_de_la_plataforma(app):
    from app.comun import estudiantes
    uid = usuarios.por_email("inv@test.cl")["id"]
    ficha, respuesta = estudiantes.requiere({"id": uid})
    assert ficha is None and respuesta.status_code == 403        # la cuenta no es de estudiante


# --- Etapa 5: una instalación nueva, de punta a punta ----------------------------------------------------------------

def test_instalacion_nueva_con_el_perfil_minimo(tmp_path, monkeypatch):
    """Otra unidad instala TAU: base nueva, perfil mínimo, primera cuenta, y de ahí activa lo que necesita."""
    monkeypatch.setattr(config, "PERFIL", "minimo")
    nueva = TestClient(main.create_app(tmp_path / "otra-unidad.db"))
    usuarios.crear("admin@otra.test", "Ana", "Admin", PASS_ADMIN, es_admin=True, es_investigador=False,
                   debe_cambiar_pass=False)
    assert login(nueva, "admin@otra.test", PASS_ADMIN).headers["hx-redirect"] == "/"
    inicio = nueva.get("/").text
    assert "Primeros pasos" in inicio and "Hoy hay 1 de 17 activos" in inicio and "Cree las cuentas" in inicio
    assert "Asigne el rol de Dirección de Carrera" in inicio
    assert nueva.get("/productos").status_code == 404 and nueva.get("/docencia/planes").status_code == 404
    assert nueva.get("/servicios/comunicados").status_code == 200          # lo único activo del perfil mínimo
    # Activa las auxiliaturas: llegan con sus requisitos y sus pantallas responden.
    nueva.post("/admin/modulos/auxiliaturas/activar", headers=HX)
    assert {c for c in CLAVES if modulos.activo(c)} == {"comunicados", "auxiliaturas", "oferta", "planes", "estudiantes"}
    assert nueva.get("/docencia/planes").status_code == 200 and nueva.get("/productos").status_code == 404
    usuarios.crear("otra@otra.test", "Olga", "Docente", PASS_ADMIN, debe_cambiar_pass=False)
    assert "Primeros pasos" not in nueva.get("/").text                     # ya hay módulos y cuentas


# --- Etapa 6: roles y unidades por tipo, sin siglas fijas ------------------------------------------------------------

def test_otra_carrera_pone_sus_siglas_y_todo_sigue(admin):
    """Una carrera distinta renombra sus unidades: los roles se asignan por tipo de unidad y las pantallas responden."""
    assert unidades.carrera() == unidades.id_de("CMAT") and unidades.instituto() == unidades.id_de("IIMAT")
    assert unidades.configurar("carrera", "INF", "Carrera de Informática") == []
    assert unidades.configurar("instituto", "III", "Instituto de Investigaciones en Informática") == []
    assert unidades.configurar("universidad", "UDEMO", "Universidad de Demostración") == []
    assert unidades.configurar("carrera", "III", "Otra") == ["La sigla «III» ya es de otra unidad."]
    assert unidades.configurar("departamento", "X", "Y")[0].startswith("Tipo de unidad desconocido")
    with pytest.raises(ValueError):
        unidades.id_de("CMAT")                                   # la sigla anterior ya no existe
    assert unidades.id_de("INF") == unidades.carrera()
    uid = usuarios.por_email("admin@test.cl")["id"]
    assert permisos.asignar(uid, "direccion_carrera", unidades.carrera()) == []
    assert permisos.asignar(uid, "gestion_datos", unidades.instituto()) == []      # la del Instituto ya la tiene
    assert permisos.asignar(uid, "direccion_carrera", unidades.instituto()) == ["Dirección de Carrera se asigna en: INF."]
    assert [u["sigla"] for u in permisos.unidades_de("gestion_datos")] == ["INF", "III"]
    u = usuarios.por_email("admin@test.cl")
    assert permisos.puede(u, "gestionar_vinculos", unidades.carrera()) and permisos.puede(u, "decidir_propuestas")
    nuevo = usuarios.crear("otro@test.cl", "Otro", "Admin", PASS_ADMIN, es_admin=True, es_investigador=False,
                           debe_cambiar_pass=False)
    assert permisos.puede(usuarios.por_email("otro@test.cl"), "administrar_cuentas"), nuevo   # rol en la universidad
    for ruta in ("/", "/admin/usuarios", "/calidad/marco", "/docencia/planes", "/docencia/carga", "/informes",
                 "/calidad/mejora", "/admin/propuestas"):
        assert admin.get(ruta).status_code == 200, ruta
    assert "Dirección de Carrera · INF" in admin.get(f"/admin/usuarios/{uid}/roles").text


def test_ningun_archivo_de_app_busca_una_unidad_por_su_sigla():
    """Las siglas CMAT, IIMAT y UMSA son datos de una instalación: el código pregunta por el tipo de unidad."""
    import re
    raiz = Path(main.__file__).parent / "app"
    patron = re.compile(r"""id_de\(\s*["'](CMAT|IIMAT|UMSA|FCPN)["']""")
    assert [str(f.relative_to(raiz)) for f in raiz.rglob("*.py") if patron.search(f.read_text(encoding="utf-8"))] == []


# --- Mejoras posteriores (PLAN §73): informes en su paquete e indicadores «sin fuente» ---------------------------------

def test_los_informes_de_investigacion_tienen_su_paquete(app):
    por_ruta = {r.path: r.modulos for r in app.routes if hasattr(r, "modulos")}
    assert por_ruta["/informes"] == ("informes",) and por_ruta["/informes/memoria"] == ("informes",)
    assert por_ruta["/informes/calidad"] == ("informes",) and por_ruta["/calidad/marco"] == ("calidad",)
    origen = {r.path: modulos._original(r.endpoint).__module__ for r in app.routes if getattr(r, "endpoint", None)}
    assert origen["/informes/memoria"].startswith("app.informes.") and origen["/calidad/marco"].startswith("app.calidad.")


def test_un_indicador_sin_su_modulo_queda_sin_fuente(app):
    from app.calidad import indicadores
    declarados = {c for claves in indicadores.FUENTES.values() for c in claves} | set(indicadores.DE_LA_PLATAFORMA)
    assert declarados == set(indicadores.CALCULOS), "todo cálculo declara de qué módulos salen sus datos (FUENTES)"
    assert all(modulos.obtener(m) for ms in indicadores.FUENTES for m in ms)
    anio = 2026
    assert indicadores.sin_fuente("ingresantes") == "" and "Sin fuente" not in indicadores.calcular("ingresantes", anio).detalle
    _apagar("estudiantes", "encuestas", "tutoria_apoyo", "egresados", "evaluacion_docente", "auxiliaturas", "grado",
            "oportunidades")
    r = indicadores.calcular("ingresantes", anio)
    assert r.valor is None and r.detalle.startswith("Sin fuente: el módulo «Seguimiento estudiantil» no está activo")
    assert indicadores.calcular("empleabilidad", anio).valor is None
    assert "Sin fuente" not in indicadores.calcular("jce", anio).detalle      # los vínculos son de la plataforma


def test_el_historial_docente_sigue_a_los_modulos(app):
    from app.academico import historial
    uid = usuarios.por_email("inv@test.cl")["id"]
    assert [s["clave"] for s in historial.secciones(uid)] == ["tutor", "tribunal", "auxiliaturas", "proyectos", "tutorados"]
    assert set(historial.historial(uid)) == {"materias", "tutor", "tribunal", "auxiliaturas", "proyectos", "tutorados"}
    _apagar("grado", "auxiliaturas")
    assert [s["clave"] for s in historial.secciones(uid)] == ["proyectos", "tutorados"]
    assert historial.historial(uid)["tutor"] == [] and historial.elegibles(uid) == []     # sin sus módulos, vacío
    assert historial.verificar("TAU-0000000000") is None


def test_los_nombres_salen_de_las_unidades_y_se_editan_en_administracion(admin, monkeypatch):
    assert config.NOMBRE_CARRERA == "Carrera de Matemática" and "IIMAT" in config.FILIACIONES
    assert admin.get("/admin/unidades").status_code == 200
    r = admin.post("/admin/unidades/carrera", data={"sigla": "INF", "nombre": "Carrera de Informática"}, headers=HX)
    assert r.headers["hx-redirect"] == "/admin/unidades"
    assert config.NOMBRE_CARRERA == "Carrera de Informática" and unidades.id_de("INF") == unidades.carrera()
    assert config.NOMBRE_COMPLETO.endswith("de la Carrera de Informática") and "INF" in config.FILIACIONES
    assert "Carrera de Informática" in admin.get("/publico/privacidad").text       # el pie de las páginas públicas
    assert get_db().q("SELECT 1 FROM auditoria WHERE accion = 'configurar_unidad'")
    admin.post("/admin/unidades/carrera", data={"sigla": "IIMAT", "nombre": "Repetida"}, headers=HX)   # sigla de otra unidad
    assert config.NOMBRE_CARRERA == "Carrera de Informática"
    assert admin.post("/admin/unidades/departamento", data={"sigla": "X", "nombre": "Y"}, headers=HX).status_code == 404
    monkeypatch.setenv("TAU_CARRERA", "Carrera del Entorno")       # la variable, si está, manda sobre la tabla
    assert config.NOMBRE_CARRERA == "Carrera del Entorno"


def test_pendientes_y_calendario_de_toda_la_persona(client):
    """Una sola pantalla de pendientes y una de calendario: juntan la docencia y la investigación sin repetir."""
    from app.comun.rutas import agenda
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, "Otra-clave-1234", temporal=False)
    login(client, "inv@test.cl", "Otra-clave-1234")
    pagina = client.get("/pendientes")
    assert pagina.status_code == 200 and "Mis pendientes" in pagina.text and "Complete su perfil" in pagina.text
    assert client.get("/calendario?dias=180").status_code == 200
    ics = client.get("/calendario.ics")
    assert ics.status_code == 200 and ics.text.startswith("BEGIN:VCALENDAR")
    auth = {"id": uid, "es_investigador": True}
    from datetime import date, timedelta
    hoy = date.today()
    lista = agenda.eventos(auth, hoy, hoy + timedelta(days=365))
    assert len({(e["fecha"], e["hora"], e["titulo"], e["href"]) for e in lista}) == len(lista)     # sin repetidos
    solo_docencia = agenda.pendientes({"id": uid, "es_investigador": False}, hoy)
    assert not any(p["tipo"] == "perfil" for p in solo_docencia)                # lo de investigación, solo al investigador
    menu = client.get("/").text
    assert menu.count('href="/pendientes"') >= 1 and "/investigacion/pendientes" not in menu


def test_manifiesto_web_publico_y_con_los_nombres_de_la_instalacion(client):
    r = client.get("/manifest.webmanifest")                      # sin sesión: lo pide el navegador antes de ingresar
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/manifest+json")
    m = r.json()
    assert m["short_name"] == config.NOMBRE_SISTEMA and m["name"] == config.NOMBRE_COMPLETO and m["start_url"] == "/"
    for icono in m["icons"]:
        assert client.get(icono["src"]).status_code == 200
    login_html = client.get("/login").text
    assert 'rel="manifest"' in login_html and 'rel="apple-touch-icon"' in login_html and 'name="theme-color"' in login_html
    assert 'id="migas"' not in login_html                        # las migas son de las páginas con sesión

