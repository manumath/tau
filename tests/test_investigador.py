"""PLAN §69: servicios para el investigador (pendientes y calendario, acceso abierto, coautores)."""
from datetime import date, timedelta

from app.comun import config, usuarios, vinculos
from app.comun.db import get_db
from app.investigacion import mis_pendientes, productos, proyectos
from tests.conftest import HX, PASS_TEMP, login


def _emmy():
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    return uid


def _titular(uid):
    vinculos.agregar(uid, "titular", "2015-01-01", carga={"horas": 160, "detalles": {}, "actividades": {
        k: 0 for k in vinculos.ACTIVIDADES} | {"investigacion": 160}})


def _tipo(nombre="Artículo en revista"):
    return str(get_db().q("SELECT id FROM tipo_producto WHERE nombre = ?", [nombre])[0]["id"])


def _producto(autores, titulo="Anillos", anio="2026", estado="publicado", tipo="Artículo en revista", **extra):
    d, errores = productos.preparar(dict(tipo_id=_tipo(tipo), titulo=titulo, anio=anio, estado_publicacion=estado,
                                         revision="arbitrado", **extra), autores, [])
    assert not errores, errores
    return productos.guardar(d, autores, int(autores[0][2:]))


# --- Etapa 1: pendientes y calendario -----------------------------------------------------------------------------------

def test_sin_nada_hay_poco_que_hacer(app):
    uid = _emmy()
    p = mis_pendientes.pendientes(uid)
    assert [x["tipo"] for x in p] == ["perfil"]          # solo el perfil incompleto
    assert mis_pendientes.eventos(uid) == []
    assert mis_pendientes.pendientes(usuarios.por_email("admin@test.cl")["id"]) == []   # sin perfil de investigador


def test_pendientes_de_proyectos_y_productos(app):
    emmy = _emmy()
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP, debe_cambiar_pass=False)["id"]
    hoy = date.today()
    pid = proyectos.crear(dict(nombre="Anillos", estado="vigente", fecha_inicio=(hoy - timedelta(days=300)).isoformat(),
                               fecha_fin=(hoy + timedelta(days=20)).isoformat()), emmy, emmy)
    # Alan propone un producto al proyecto de Emmy: ella lo debe aprobar.
    prod = _producto([f"i:{alan}"], "Invariantes")
    get_db().t.producto_proyecto.insert(producto_id=prod, proyecto_id=pid, propuesto_por=alan)
    p = mis_pendientes.pendientes(emmy, hoy)
    titulos = [x["titulo"] for x in p]
    assert any("por aprobar en «Anillos»" in t for t in titulos) and any("Termina su proyecto «Anillos»" in t for t in titulos)
    assert all(x["tipo"] != "proyecto" for x in mis_pendientes.pendientes(alan, hoy))   # lo de Emmy no es de Alan
    # Un producto «enviado» sin novedades hace más de seis meses pregunta si ya se publicó.
    viejo = _producto([f"i:{emmy}"], "Grupos", estado="enviado")
    get_db().execute("UPDATE producto SET creado_en = ?, actualizado_en = NULL WHERE id = ?",
                     [(hoy - timedelta(days=200)).isoformat() + " 00:00:00", viejo])
    assert any(x["titulo"] == "¿Ya se publicó «Grupos»?" and x["href"] == f"/productos/{viejo}"
               for x in mis_pendientes.pendientes(emmy, hoy))
    # Lo que tiene fecha va antes que lo que no la tiene.
    con_fecha = [x["cuando"] is not None for x in mis_pendientes.pendientes(emmy, hoy)]
    assert con_fecha == sorted(con_fecha, reverse=True) and any(con_fecha) and not all(con_fecha)


def test_eventos_de_actividades_proyectos_y_convocatoria(app):
    emmy = _emmy()
    _titular(emmy)
    hoy = date.today()
    pid = proyectos.crear(dict(nombre="Anillos", estado="vigente", fecha_inicio="2020-01-01",
                               fecha_fin=(hoy + timedelta(days=15)).isoformat()), emmy, emmy)
    tipo = get_db().q("SELECT id FROM tipo_actividad LIMIT 1")[0]["id"]
    aid = get_db().t.actividad.insert(tipo_id=tipo, titulo="Congreso de Álgebra", fecha_inicio=(hoy + timedelta(days=9)).isoformat(),
                                      lugar="Cochabamba", creado_por=emmy)["id"]
    get_db().t.actividad_participante.insert(actividad_id=aid, orden=0, investigador_id=emmy, rol="expositor")
    ev = mis_pendientes.eventos(emmy, hoy, hoy + timedelta(days=60))
    tipos = {e["tipo"] for e in ev}
    assert {"actividad", "proyecto"} <= tipos
    e = next(e for e in ev if e["tipo"] == "actividad")
    assert e["titulo"] == "Congreso de Álgebra" and "Expositor" in e["detalle"] and e["href"] == f"/actividades/{aid}"
    assert pid and [x["fecha"] for x in ev] == sorted(x["fecha"] for x in ev)
    # Los titulares ven las fechas de la convocatoria de proyectos; los demás no.
    assert mis_pendientes.puede_proponer(emmy)
    ev = mis_pendientes.eventos(emmy, date(hoy.year, 1, 1), date(hoy.year + 1, 12, 31))
    assert any(e["tipo"] == "propuesta" and e["titulo"].startswith("Cierra la convocatoria") for e in ev)


def test_pantallas_del_investigador(client, app):
    emmy = _emmy()
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/investigacion/pendientes")
    assert r.status_code == 200 and "Mis pendientes de investigación" in r.text and "Complete su perfil" in r.text
    assert "Mi calendario de investigación" in client.get("/investigacion/calendario").text
    ics = client.get("/investigacion/calendario.ics")
    assert ics.status_code == 200 and ics.text.startswith("BEGIN:VCALENDAR") and "Calendario de investigación" in ics.text
    assert 'href="/pendientes"' in client.get("/").text and emmy                 # el menú lleva a los de toda la persona


def test_quien_no_investiga_no_entra(admin):
    for ruta in ("/investigacion/pendientes", "/investigacion/calendario", "/investigacion/calendario.ics"):
        assert admin.get(ruta, follow_redirects=False).status_code == 403


# --- Etapa 2: acceso abierto y datos ----------------------------------------------------------------------------------

def _declarar(pid, uid, **v):
    from app.investigacion import acceso_abierto as aa
    valores, errores = aa.validar(v)
    assert not errores, errores
    aa.guardar(pid, valores, uid)


def test_validar_la_declaracion():
    from app.investigacion import acceso_abierto as aa
    _, e = aa.validar({})
    assert e == ["Indique dónde se puede leer el texto."]
    assert "Falta el enlace donde se puede leer el texto." in aa.validar({"texto": "abierto"})[1]
    assert "Indique qué versión depositó." in aa.validar({"texto": "depositado", "enlace": "repo.umsa.bo/x"})[1]
    assert "Indique la fecha en que termina el embargo." in aa.validar({"texto": "embargo"})[1]
    assert "Falta el enlace de los datos o del código publicados." in aa.validar({"texto": "cerrado", "datos": "publicados"})[1]
    assert any("dirección web válida" in x for x in aa.validar({"texto": "abierto", "enlace": "no es una url"})[1])
    assert any("dirección web válida" in x for x in aa.validar({"texto": "abierto", "enlace": "javascript:alert(1)"})[1])
    v, e = aa.validar({"texto": "depositado", "enlace": "repo.umsa.bo/x", "version": "aceptada", "licencia": "cc_by",
                       "datos": "publicados", "datos_enlace": "https://zenodo.org/r/1", "nota": " ok "})
    assert not e and v["enlace"] == "https://repo.umsa.bo/x" and v["nota"] == "ok" and v["embargo_hasta"] is None
    # Lo que no corresponde al caso se descarta: un texto cerrado no guarda enlace, versión ni licencia.
    v, e = aa.validar({"texto": "cerrado", "enlace": "https://x.org", "version": "aceptada", "licencia": "cc_by"})
    assert not e and v["enlace"] is None and v["version"] is None and v["licencia"] is None


def test_declarar_cambiar_y_quitar(app):
    from app.investigacion import acceso_abierto as aa
    emmy = _emmy()
    pid = _producto([f"i:{emmy}"])
    assert aa.de_producto(pid) is None
    _declarar(pid, emmy, texto="abierto", enlace="https://revista.org/a", licencia="cc_by")
    a = aa.de_producto(pid)
    assert a["texto"] == "abierto" and a["declarado_por"] == emmy and a["actualizado_en"] is None
    assert aa.enlace_publico(a) == "https://revista.org/a"
    _declarar(pid, emmy, texto="cerrado", nota="El editor no lo permite")
    a = aa.de_producto(pid)
    assert a["texto"] == "cerrado" and a["enlace"] is None and a["actualizado_en"] and aa.enlace_publico(a) is None
    aa.quitar(pid, emmy)
    assert aa.de_producto(pid) is None
    acciones = [f["accion"] for f in get_db().q("SELECT accion FROM auditoria WHERE entidad = 'producto' ORDER BY id")]
    assert acciones[-3:] == ["declarar_acceso_abierto", "declarar_acceso_abierto", "quitar_acceso_abierto"]


def test_que_productos_se_piden_y_como_se_resumen(app):
    from app.investigacion import acceso_abierto as aa
    emmy = _emmy()
    hoy = date.today()
    a = _producto([f"i:{emmy}"], "Reciente", str(hoy.year))
    b = _producto([f"i:{emmy}"], "Antiguo", str(hoy.year - 9))
    c = _producto([f"i:{emmy}"], "Con embargo", str(hoy.year - 1))
    _producto([f"i:{emmy}"], "En preparación", str(hoy.year), estado="en_preparacion")
    _producto([f"i:{emmy}"], "Charla", str(hoy.year), tipo="Presentación")
    otro = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP, debe_cambiar_pass=False)["id"]
    _producto([f"i:{otro}"], "De Alan", str(hoy.year))
    assert [f["titulo"] for f in aa.de_investigador(emmy)] == ["Reciente", "Con embargo", "Antiguo"]
    # «Mis pendientes» pide solo los últimos cinco años; el antiguo se declara cuando quiera.
    assert {f["titulo"] for f in aa.sin_declarar(emmy, hoy)} == {"Reciente", "Con embargo"}
    _declarar(a, emmy, texto="abierto", enlace="https://revista.org/a", datos="publicados", datos_enlace="https://zenodo.org/r/1")
    _declarar(c, emmy, texto="embargo", embargo_hasta=(hoy - timedelta(days=1)).isoformat())
    _declarar(b, emmy, texto="no_aplica")
    r = aa.resumen(aa.de_investigador(emmy))
    assert (r["total"], r["abierto"], r["embargo"], r["no_aplica"], r["sin_declarar"], r["en_abierto"], r["datos_publicados"]) \
        == (3, 1, 1, 1, 0, 1, 1)
    assert [f["titulo"] for f in aa.de_investigador(emmy, "embargo")] == ["Con embargo"]
    assert [f["titulo"] for f in aa.de_investigador(emmy, "", str(hoy.year - 9))] == ["Antiguo"]
    # El embargo vencido es un pendiente con fecha, y su término entra en el calendario.
    p = mis_pendientes.pendientes(emmy, hoy)
    assert any(x["tipo"] == "acceso" and x["titulo"] == "Terminó el embargo de «Con embargo»" and x["href"] == f"/productos/{c}"
               for x in p)
    assert not any("Declare el acceso abierto" in x["titulo"] for x in p)
    assert any(e["tipo"] == "acceso" for e in mis_pendientes.eventos(emmy, hoy - timedelta(days=3), hoy + timedelta(days=3)))


def test_sugerencia_si_tiene_arxiv(app):
    from app.investigacion import acceso_abierto as aa
    assert aa.sugerencia({"arxiv_id": "2401.01234"}) == {"texto": "depositado", "enlace": "https://arxiv.org/abs/2401.01234"}
    assert aa.sugerencia({"arxiv_id": None}) == {}


def test_formulario_de_acceso_abierto(client, app):
    from app.investigacion import acceso_abierto as aa
    emmy = _emmy()
    pid = _producto([f"i:{emmy}"], arxiv_id="2401.01234")
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get(f"/productos/{pid}/acceso")
    assert r.status_code == 200 and "https://arxiv.org/abs/2401.01234" in r.text and "Quitar la declaración" not in r.text
    assert "Declarar" in client.get(f"/productos/{pid}").text and "Aún no se declaró" in client.get(f"/productos/{pid}").text
    # Con errores el formulario vuelve con lo escrito y no guarda nada.
    r = client.post(f"/productos/{pid}/acceso", headers=HX, data={"texto": "depositado", "enlace": "https://arxiv.org/abs/2401.01234"})
    assert "Indique qué versión depositó." in r.text and aa.de_producto(pid) is None
    r = client.post(f"/productos/{pid}/acceso", headers=HX, data={"texto": "depositado", "enlace": "https://arxiv.org/abs/2401.01234",
                                                                 "version": "preprint", "licencia": "cc_by"})
    assert r.status_code == 200 and r.headers["hx-trigger"] == "productos-cambiados" and aa.de_producto(pid)["version"] == "preprint"
    ficha = client.get(f"/productos/{pid}").text
    assert "Copia en un repositorio" in ficha and "Leer el texto" in ficha and "CC BY" in ficha
    assert "Quitar la declaración" in client.get(f"/productos/{pid}/acceso").text
    r = client.delete(f"/productos/{pid}/acceso", headers=HX)
    assert r.headers["hx-trigger"] == "productos-cambiados" and aa.de_producto(pid) is None


def test_solo_quien_firma_el_producto_declara(client, app):
    from app.investigacion import acceso_abierto as aa
    emmy = _emmy()
    pid = _producto([f"i:{emmy}"])
    charla = _producto([f"i:{emmy}"], "Charla", tipo="Presentación")
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP, debe_cambiar_pass=False)["id"]
    login(client, "alan@test.cl", PASS_TEMP)
    assert client.get(f"/productos/{pid}/acceso").status_code == 403
    assert client.post(f"/productos/{pid}/acceso", headers=HX, data={"texto": "abierto", "enlace": "https://x.org"}).status_code == 403
    assert client.delete(f"/productos/{pid}/acceso", headers=HX).status_code == 403 and alan
    assert aa.de_producto(pid) is None
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get(f"/productos/{charla}/acceso").status_code == 403         # una presentación no se deposita
    assert client.get("/productos/9999/acceso").status_code == 404


def test_pagina_de_acceso_abierto(client, app):
    emmy = _emmy()
    a = _producto([f"i:{emmy}"], "Anillos locales")
    _producto([f"i:{emmy}"], "Módulos planos")
    _declarar(a, emmy, texto="abierto", enlace="https://revista.org/a")
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/investigacion/acceso-abierto")
    assert r.status_code == 200 and "Anillos locales" in r.text and "Módulos planos" in r.text and "50 %" in r.text
    r = client.get("/investigacion/acceso-abierto?estado=sin_declarar")
    assert "Módulos planos" in r.text and "Anillos locales" not in r.text.split('id="lista-acceso"')[1]
    assert "/investigacion/acceso-abierto" in client.get("/").text


def test_la_pagina_de_acceso_abierto_es_de_investigadores(admin):
    assert admin.get("/investigacion/acceso-abierto", follow_redirects=False).status_code == 403


def test_el_perfil_publico_muestra_solo_lo_abierto(client, app):
    from app.investigacion import perfiles
    emmy = _emmy()
    perfiles.actualizar_campos(emmy, perfil_publico=1)
    abierto = _producto([f"i:{emmy}"], "Abierto", doi="10.1000/abierto")
    embargado = _producto([f"i:{emmy}"], "Embargado", doi="10.1000/embargado")
    cerrado = _producto([f"i:{emmy}"], "Cerrado", doi="10.1000/cerrado")
    _declarar(abierto, emmy, texto="depositado", enlace="https://repo.umsa.bo/abierto", version="aceptada")
    _declarar(embargado, emmy, texto="embargo", enlace="https://repo.umsa.bo/embargado", embargo_hasta="2099-01-01")
    _declarar(cerrado, emmy, texto="cerrado", nota="No lo permite el editor")
    pagina = client.get(f"/publico/investigadores/{emmy}").text
    assert "https://repo.umsa.bo/abierto" in pagina and "Texto en acceso abierto" in pagina
    assert "https://repo.umsa.bo/embargado" not in pagina and "No lo permite el editor" not in pagina
    assert pagina.count("Texto en acceso abierto") == 1 and 'rel="noopener noreferrer nofollow"' in pagina
    por_titulo = {p["titulo"]: p["acceso_abierto"] for p in client.get(f"/api/v1/investigadores/{emmy}").json()["productos"]}
    assert por_titulo == {"Abierto": "https://repo.umsa.bo/abierto", "Embargado": None, "Cerrado": None}
    assert {p["titulo"]: p["acceso_abierto"] for p in client.get("/api/v1/productos").json()}["Abierto"] == "https://repo.umsa.bo/abierto"
    assert embargado and cerrado


# --- Etapa 3: mis colaboraciones ---------------------------------------------------------------------------------------

def _red(app):
    """Emmy firma con Alan y con Weyl (de Estados Unidos) y comparte un proyecto con Alan y con Karen (sin país)."""
    from app.comun import personas
    emmy = _emmy()
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP, debe_cambiar_pass=False)["id"]
    weyl = personas.crear_externo("Hermann", "Weyl", "Institute for Advanced Study", "Estados Unidos", emmy)["id"]
    karen = personas.crear_externo("=Karen", "Uhlenbeck", "Universidad de Texas", None, emmy)["id"]
    p1 = _producto([f"i:{emmy}", f"i:{alan}", f"e:{weyl}"], "Álgebras de Lie", "2024")
    p2 = _producto([f"i:{emmy}", f"e:{weyl}"], "Grupos clásicos", "2025")
    _producto([f"i:{emmy}"], "Solo de Emmy", "2023")
    _producto([f"i:{alan}"], "Solo de Alan", "2024")
    pid = proyectos.crear(dict(nombre="Anillos", estado="vigente", fecha_inicio="2020-01-01"), emmy, emmy)
    assert proyectos.agregar_participante(pid, f"i:{alan}", "co_investigador") is None
    assert proyectos.agregar_participante(pid, f"e:{karen}", "colaborador") is None
    return dict(emmy=emmy, alan=alan, weyl=weyl, karen=karen, p1=p1, p2=p2, pid=pid)


def test_con_quien_colabora(app):
    from app.investigacion import coautores as co
    r = _red(app)
    lista = co.colaboradores(r["emmy"])
    # Weyl firmó dos productos; Alan, uno y un proyecto; Karen, solo el proyecto. Nadie se cuenta a sí mismo.
    assert [(c["apellidos"], c["n_productos"], c["n_proyectos"]) for c in lista] == \
        [("Weyl", 2, 0), ("Turing", 1, 1), ("Uhlenbeck", 0, 1)]
    weyl = lista[0]
    assert (weyl["primero"], weyl["ultimo"], weyl["pais"], weyl["interno"]) == (2024, 2025, "Estados Unidos", False)
    assert lista[1]["interno"] is True and lista[1]["pais"] == config.PAIS and lista[2]["primero"] is None
    assert all(c["ref"] != f"i:{r['emmy']}" for c in lista)
    # Cada uno ve solo lo suyo: Alan ve a Emmy, a Weyl (de un producto) y a Karen (del proyecto), no lo que Emmy hizo aparte.
    de_alan = {c["apellidos"] for c in co.colaboradores(r["alan"])}
    assert de_alan == {"Noether", "Weyl", "Uhlenbeck"}
    assert co.colaboradores(usuarios.por_email("admin@test.cl")["id"]) == []


def test_filtrar_por_años(app):
    from app.investigacion import coautores as co
    r = _red(app)
    solo_2025 = {c["apellidos"]: (c["n_productos"], c["n_proyectos"]) for c in co.colaboradores(r["emmy"], 2025, None)}
    assert solo_2025 == {"Weyl": (1, 0), "Turing": (0, 1), "Uhlenbeck": (0, 1)}   # el proyecto sigue vigente en 2025
    assert {c["apellidos"] for c in co.colaboradores(r["emmy"], None, 2019)} == set()
    assert [(c["apellidos"], c["n_productos"]) for c in co.colaboradores(r["emmy"], 2024, 2024)] == \
        [("Turing", 1), ("Weyl", 1), ("Uhlenbeck", 0)]
    antes = {c["apellidos"]: c["n_productos"] for c in co.colaboradores(r["emmy"], None, 2024)}
    assert antes["Weyl"] == 1 and antes["Turing"] == 1


def test_resumen_de_colaboraciones(app):
    from app.investigacion import coautores as co
    r = _red(app)
    s = co.resumen(co.colaboradores(r["emmy"]))
    assert (s["total"], s["internos"], s["externos"], s["extranjeros"], s["sin_pais"]) == (3, 1, 2, 1, 1)
    assert dict(s["paises"]) == {config.PAIS: 1, "Estados Unidos": 1, "Sin país registrado": 1}
    assert s["n_instituciones"] == 2 and s["n_paises_extranjeros"] == 1
    assert co.resumen([]) == {**co.resumen([]), "total": 0, "paises": [], "instituciones": []}


def test_lo_que_se_tiene_en_comun(app):
    from app.investigacion import coautores as co
    r = _red(app)
    d = co.compartidos(r["emmy"], f"e:{r['weyl']}")
    assert [p["titulo"] for p in d["lista_productos"]] == ["Grupos clásicos", "Álgebras de Lie"] and d["lista_proyectos"] == []
    d = co.compartidos(r["emmy"], f"i:{r['alan']}")
    assert [p["titulo"] for p in d["lista_productos"]] == ["Álgebras de Lie"] and [p["nombre"] for p in d["lista_proyectos"]] == ["Anillos"]
    assert co.compartidos(r["emmy"], "e:9999") is None and co.compartidos(r["alan"], f"e:{r['karen']}")


def test_pantallas_de_colaboraciones(client, app):
    r = _red(app)
    login(client, "inv@test.cl", PASS_TEMP)
    pagina = client.get("/investigacion/coautores").text
    assert "Mis colaboraciones" in pagina and "Weyl, Hermann" in pagina and "Estados Unidos" in pagina
    assert "A 1 coautor(es) externo(s) no se les registró el país" in pagina
    detalle = client.get(f"/investigacion/coautores?con=e:{r['weyl']}")
    assert detalle.status_code == 200 and "Grupos clásicos" in detalle.text and "Productos en común (2)" in detalle.text
    assert client.get("/investigacion/coautores?con=e:9999").status_code == 404
    assert client.get("/investigacion/coautores?desde=2025").text.count("Álgebras de Lie") == 0
    csv = client.get("/investigacion/coautores.csv?hasta=2024")
    assert csv.status_code == 200 and csv.headers["content-disposition"].endswith('colaboraciones-tau.csv"')
    cuerpo = csv.content.decode("utf-8-sig")
    assert cuerpo.startswith("Apellidos,Nombres,Institución,País,Tipo,Productos en común") and "Weyl,Hermann" in cuerpo
    assert "'=Karen" in cuerpo and ",=Karen" not in cuerpo     # una celda que empieza con «=» sale neutralizada
    assert "/investigacion/coautores" in client.get("/").text


def test_las_colaboraciones_son_de_investigadores(admin):
    for ruta in ("/investigacion/coautores", "/investigacion/coautores.csv"):
        assert admin.get(ruta, follow_redirects=False).status_code == 403
