"""Líneas de investigación institucionales: catálogo con vigencia, propuestas, proyectos y perfiles."""
from app.investigacion import institucionales as inst
from app.investigacion import lineas, proyectos
from app.comun.db import get_db
from tests.conftest import HX
from tests.test_propuestas import COMPLETA, _crear, _enviada, entrar, fecha, gente  # noqa: F401


def _id(nombre):
    return get_db().q("SELECT id FROM linea_investigacion WHERE nombre = ?", [nombre])[0]["id"]


def _area(nombre):
    return get_db().q("SELECT id FROM area_investigacion WHERE nombre = ?", [nombre])[0]["id"]


def test_catalogo_inicial(app):
    # Catálogo oficial por áreas (migración 0060); las líneas anteriores que coinciden conservan su nombre y las que no
    # figuran en él quedan al final, sin área, hasta que la Dirección del Instituto decida.
    assert [a["nombre"] for a in lineas.areas()] == ["Álgebra", "Geometría y Topología", "Análisis", "Matemática Aplicada",
                                                     "Educación Matemática"]
    assert [(x["area"], x["nombre"]) for x in lineas.todas()] == [
        ("Álgebra", "Estructuras Algebraicas Ordenadas"), ("Álgebra", "Grupos finitos"),
        ("Álgebra", "Problemas inversos de autovalores"),
        ("Geometría y Topología", "Teoría geométrica de control"),
        ("Geometría y Topología", "Topologías finitas y aplicaciones a otras áreas científicas"),
        ("Geometría y Topología", "Geometría diferencial"),
        ("Análisis", "Teoría de distribuciones en el contexto de las EDP"), ("Análisis", "Teoría ergódica"),
        ("Análisis", "Análisis intervalar"),
        ("Matemática Aplicada", "Optimización Matemática"), ("Matemática Aplicada", "Matemática aplicada y análisis de datos"),
        ("Matemática Aplicada", "Teoría de control. Modelos aplicados a la biología"),
        ("Matemática Aplicada", "Sistemas Dinámicos"),
        ("Matemática Aplicada", "Teoría de grafos finitos y aplicaciones a otras áreas científicas"),
        ("Educación Matemática", "Educación matemática: Teoría de la Respuesta al Ítem"),
        (None, "Teoría de Control"), (None, "Modelos Matemáticos y Computación"),
        (None, "Áreas Fundamentales Complementarias")]
    assert len(lineas.vigentes()) == 18


def test_vigencia_y_catalogo(app):
    algebra = str(_area("Álgebra"))
    d, errores = lineas.validar({"nombre": "Teoría de control", "area_id": algebra, "vigente_desde": "", "vigente_hasta": ""})
    assert errores == ["Ya existe una línea con ese nombre."]
    assert lineas.validar({"nombre": "Lógica", "area_id": ""})[1] == ["Elija el área de la línea."]
    assert lineas.validar({"nombre": "Lógica", "area_id": "999"})[1] == ["Elija un área de la lista."]
    d, errores = lineas.validar({"nombre": "Lógica", "area_id": algebra, "vigente_desde": "2027-01-01",
                                 "vigente_hasta": "2026-01-01"})
    assert "anterior a su inicio" in errores[0]
    d, errores = lineas.validar({"nombre": "Lógica", "area_id": algebra, "descripcion": "", "vigente_desde": "2027-01-01",
                                 "vigente_hasta": ""})
    lid = lineas.crear(d, None)
    x = lineas.obtener(lid)
    assert (lineas.estado(x, "2026-12-31"), lineas.estado(x, "2027-01-01")) == ("proxima", "vigente")
    assert lineas.cerrar(lid, "2026-06-01") and lineas.cerrar(lid, "2028-12-31") is None
    assert lineas.estado(lineas.obtener(lid), "2029-01-01") == "cerrada"
    lineas.reabrir(lid)
    assert lineas.obtener(lid)["vigente_hasta"] is None
    # Se ordena dentro de su área: al final del Álgebra, y sube un puesto.
    del_algebra = [x["id"] for x in lineas.todas() if x["area"] == "Álgebra"]
    assert del_algebra[-1] == lid
    lineas.mover(lid, -1)
    assert [x["id"] for x in lineas.todas() if x["area"] == "Álgebra"] == [*del_algebra[:-2], lid, del_algebra[-2]]
    assert lineas.eliminar(lid) is None and lineas.obtener(lid) is None


def test_propuesta_exige_lineas_vigentes_en_el_periodo(client, gente, fecha):
    entrar(client, "emmy")
    prop = _crear(client)
    control = _id("Teoría de Control")
    lineas.cerrar(control, "2026-09-30")  # deja de regir antes del periodo 2026–2027
    r = client.put(f"/propuestas/{prop}", headers=HX, data={**COMPLETA, "linea": [str(control)]})
    assert "Líneas que no rigen en el periodo 2026–2027: Teoría de Control." in r.text
    assert inst.obtener(prop)["lineas"] == []  # no se guardó nada
    sin = {k: v for k, v in COMPLETA.items() if k != "linea"}
    r = client.post(f"/propuestas/{prop}/enviar", headers=HX, data=sin)
    assert "al menos una línea de investigación" in r.text
    assert inst.obtener(prop)["estado"] == "borrador"

    # Una línea elegida que luego deja de regir queda guardada, pero impide el envío.
    optim = _id("Optimización Matemática")
    client.put(f"/propuestas/{prop}", headers=HX, data={**COMPLETA, "linea": [str(optim)]})
    lineas.cerrar(optim, "2026-09-15")
    r = client.post(f"/propuestas/{prop}/enviar", headers=HX, data={**COMPLETA, "linea": [str(optim)]})
    assert "quitar las líneas que no rigen en el periodo (Optimización Matemática)" in r.text
    assert "ya no rige: desmárquela" in r.text


def test_lineas_pasan_al_proyecto_y_a_la_continuidad(client, gente, fecha):
    prop = _enviada(client, fecha)
    p = inst.obtener(prop)
    assert [x["nombre"] for x in p["lineas"]] == ["Estructuras Algebraicas Ordenadas",
                                                  "Modelos Matemáticos y Computación"]
    assert "Modelos Matemáticos y Computación" in p["copia_enviada"]
    assert "Líneas de investigación" in inst.hojas_convocatoria(2026)["Propuestas"][0]
    entrar(client, "admin")
    client.post(f"/propuestas/{prop}/decidir", headers=HX, data={"decision": "aceptada"})
    pid = p["proyecto_id"]
    assert [x["id"] for x in lineas.de_proyecto(pid)] == [2, 4]

    # En el proyecto institucional las líneas no se editan: vienen de la propuesta.
    entrar(client, "emmy")
    r = client.get(f"/proyectos/{pid}")
    assert "Vienen de la propuesta aceptada" in r.text and "Estructuras Algebraicas Ordenadas" in r.text
    assert client.put(f"/proyectos/{pid}/lineas", headers=HX, data={"linea": ["1"]}).status_code == 403

    # La continuidad precarga solo las que siguen vigentes en el nuevo periodo.
    lineas.cerrar(4, "2027-09-30")
    fecha("2027-09-02")
    client.post(f"/proyectos/{pid}/continuidad", headers=HX)
    cont = inst.de_proyecto_y_periodo(pid, 2027)
    assert [x["id"] for x in cont["lineas"]] == [2]


def test_proyecto_individual(client, gente):
    entrar(client, "emmy")
    r = client.post("/proyectos", headers=HX, data={"nombre": "Sistemas caóticos", "estado": "vigente"})
    pid = int(r.headers["hx-redirect"].rsplit("/", 1)[1])
    assert "Sin líneas de investigación registradas." in client.get(f"/proyectos/{pid}").text
    r = client.put(f"/proyectos/{pid}/lineas", headers=HX, data={"linea": ["1", "5"]})
    assert "Sistemas Dinámicos" in r.text and [x["id"] for x in lineas.de_proyecto(pid)] == [5, 1]  # por área
    lineas.cerrar(3, "2020-01-01")
    r = client.put(f"/proyectos/{pid}/lineas", headers=HX, data={"linea": ["1", "3"]})
    assert "Solo puede adscribirse a líneas vigentes: Teoría de Control." in r.text
    # Un participante que no es responsable no las cambia.
    proyectos.agregar_participante(pid, f"i:{gente['alan']}", "co_investigador", False)
    entrar(client, "alan")
    assert client.put(f"/proyectos/{pid}/lineas", headers=HX, data={"linea": ["2"]}).status_code == 403


def test_perfil_y_directorio(client, gente):
    entrar(client, "emmy")
    r = client.put("/perfil/lineas", headers=HX, data={"linea": ["1", "2"]})
    assert "Sistemas Dinámicos" in r.text
    lineas.cerrar(2, "2020-01-01")
    # Una línea cerrada se conserva (marcada) hasta que el investigador la quita, pero no se vuelve a agregar.
    assert "ya no rige" in client.get("/perfil/lineas").text
    assert client.put("/perfil/lineas", headers=HX, data={"linea": ["1", "2"]}).status_code == 200
    assert [x["id"] for x in lineas.de_investigador(gente["emmy"])] == [2, 1]  # Álgebra antes que Matemática Aplicada
    client.put("/perfil/lineas", headers=HX, data={"linea": ["1"]})
    r = client.put("/perfil/lineas", headers=HX, data={"linea": ["1", "2"]})
    assert "Solo puede adscribirse a líneas vigentes" in r.text
    # Sin marcar ninguna: se adscribe a ninguna (es opcional).
    client.put("/perfil/lineas", headers=HX, data={})
    assert lineas.de_investigador(gente["emmy"]) == []
    client.put("/perfil/lineas", headers=HX, data={"linea": ["1"]})
    assert "Sistemas Dinámicos" in client.get(f"/investigadores/{gente['emmy']}").text


def test_administracion(client, gente):
    entrar(client, "emmy")
    assert client.get("/admin/lineas").status_code == 403
    entrar(client, "admin")
    assert "Estructuras Algebraicas Ordenadas" in client.get("/admin/lineas").text
    algebra = str(_area("Álgebra"))
    r = client.post("/admin/lineas", headers=HX, data={"nombre": "Lógica Matemática", "vigente_desde": "2026-01-01",
                                                       "area_id": algebra})
    assert r.headers.get("hx-redirect") == "/admin/lineas"
    lid = _id("Lógica Matemática")
    r = client.post("/admin/lineas", headers=HX, data={"nombre": "lógica matemática", "area_id": algebra})
    assert "Ya existe una línea con ese nombre." in r.text
    client.put(f"/admin/lineas/{lid}", headers=HX, data={"nombre": "Lógica y Fundamentos", "vigente_desde": "2026-01-01",
                                                         "area_id": algebra})
    assert lineas.obtener(lid)["nombre"] == "Lógica y Fundamentos"
    client.post(f"/admin/lineas/{lid}/cerrar", headers=HX, data={"fecha": "2026-12-31"})
    assert lineas.obtener(lid)["vigente_hasta"] == "2026-12-31"
    # Una línea en uso no se elimina.
    lineas.adscribir_investigador(gente["emmy"], [1])
    client.delete("/admin/lineas/1", headers=HX)
    assert lineas.obtener(1)
    assert "Emmy Noether" in client.get("/admin/lineas/1").text
    client.delete(f"/admin/lineas/{lid}", headers=HX)
    assert lineas.obtener(lid) is None


def test_productos_y_actividades_heredan_la_linea_del_proyecto(client, app):
    from app.informes import informes
    from app.investigacion import productos
    from app.comun import vinculos
    from tests.conftest import PASS_TEMP, login
    uid = get_db().q("SELECT id FROM usuario WHERE email = 'inv@test.cl'")[0]["id"]
    vinculos.agregar(uid, "titular", "2015-01-01")
    uno = proyectos.crear(dict(nombre="Uno", estado="vigente"), uid, uid)
    dos = proyectos.crear(dict(nombre="Dos", estado="vigente"), uid, uid)
    lineas.fijar_proyecto(uno, [1, 3])
    lineas.fijar_proyecto(dos, [3, 5])
    tipo = get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Preprint'")[0]["id"]
    pid = get_db().t.producto.insert(tipo_id=tipo, titulo="P", anio=2025, estado_publicacion="publicado",
                                     revision="sin_arbitraje", creado_por=uid)["id"]
    get_db().t.producto_proyecto.insert(producto_id=pid, proyecto_id=uno, estado="aprobado", propuesto_por=uid)
    get_db().t.producto_proyecto.insert(producto_id=pid, proyecto_id=dos, estado="pendiente", propuesto_por=uid)
    assert [x["id"] for x in lineas.de_registro("producto", pid)] == [1, 3]  # lo pendiente no cuenta
    get_db().execute("UPDATE producto_proyecto SET estado = 'aprobado' WHERE proyecto_id = ?", [dos])
    assert [x["id"] for x in lineas.de_registro("producto", pid)] == [5, 1, 3]  # sin repetir, por área
    fila = informes.filas_productos([productos.obtener(pid)])[0]
    assert fila["Líneas de investigación"] == "Optimización Matemática; Sistemas Dinámicos; Teoría de Control"
    assert lineas.de_registro("actividad", 999) == []
    get_db().t.producto_autor.insert(producto_id=pid, orden=1, investigador_id=uid)
    from app.comun import usuarios
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert "Optimización Matemática" in client.get(f"/productos/{pid}").text


def test_areas_y_proyectos_desde_la_linea(client, gente):
    """La Dirección del Instituto mantiene las áreas y adscribe o quita proyectos vigentes desde la ficha de la línea."""
    entrar(client, "emmy")
    assert client.post("/admin/lineas/areas", headers=HX, data={"nombre": "Lógica"}).status_code == 403
    entrar(client, "admin")  # tiene la Dirección del Instituto en estas pruebas
    r = client.post("/admin/lineas/areas", headers=HX, data={"nombre": "Lógica"})
    assert r.headers.get("hx-redirect") == "/admin/lineas"
    logica = _area("Lógica")
    assert "Ya existe un área" in client.post("/admin/lineas/areas", headers=HX, data={"nombre": "lógica"}).text
    client.post(f"/admin/lineas/areas/{logica}/subir", headers=HX)
    assert [a["nombre"] for a in lineas.areas()][-2:] == ["Lógica", "Educación Matemática"]
    client.post(f"/admin/lineas/areas/{logica}", headers=HX, data={"nombre": "Lógica matemática"})
    assert lineas.area(logica)["nombre"] == "Lógica matemática"
    # Un área con líneas no se elimina; sin líneas, sí.
    client.put("/admin/lineas/3", headers=HX, data={"nombre": "Teoría de Control", "area_id": str(logica)})
    client.delete(f"/admin/lineas/areas/{logica}", headers=HX)
    assert lineas.area(logica)
    client.put("/admin/lineas/3", headers=HX, data={"nombre": "Teoría de Control", "area_id": str(_area("Análisis"))})
    client.delete(f"/admin/lineas/areas/{logica}", headers=HX)
    assert lineas.area(logica) is None
    assert "Sin área" in client.get("/admin/lineas").text  # quedan dos líneas anteriores sin área

    pid = proyectos.crear(dict(nombre="Dinámicas de Control", estado="vigente"), gente["emmy"], gente["emmy"])
    grafos = _id("Teoría de grafos finitos y aplicaciones a otras áreas científicas")
    assert "Dinámicas de Control" in client.get(f"/admin/lineas/{grafos}").text  # se ofrece para agregar
    client.post(f"/admin/lineas/{grafos}/proyectos", headers=HX, data={"proyecto_id": str(pid)})
    assert [x["id"] for x in lineas.de_proyecto(pid)] == [grafos]
    assert lineas.agregar_proyecto(grafos, pid) == "Elija un proyecto vigente que aún no esté en la línea."
    lineas.cerrar(grafos, "2020-01-01")
    assert lineas.agregar_proyecto(grafos, pid) == "Solo se pueden adscribir proyectos a una línea vigente."
    client.post(f"/admin/lineas/{grafos}/proyectos/{pid}/quitar", headers=HX)
    assert lineas.de_proyecto(pid) == []
