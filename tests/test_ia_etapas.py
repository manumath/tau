"""IA con criterio humano, etapas 0b a 4 (PLAN §59): pantallas y permisos, memoria e informe de proyecto, clasificación
de productos, resumen del perfil, síntesis de encuestas, evidencias y narrativa de la autoevaluación, medición del
piloto, sesgos y capacitación. Ninguna prueba sale a la red: `servicio._enviar` es un proveedor falso."""
from datetime import date

import pytest
from starlette.testclient import TestClient

from app.calidad import autoevaluacion as ae
from app.calidad import evidencias, indicadores, informes
from app.comun import config, permisos, unidades, usuarios, vinculos
from app.comun.db import get_db
from app.estudiantil import encuestas, importar
from app.ia import catalogo, medicion, servicio, textos
from app.investigacion import lineas, perfiles, productos, proyectos
from tests.conftest import HX, PASS_ADMIN, login
from tests.test_propuestas import entrar, fecha, gente  # noqa: F401

HOY = date.today().year


class _HiloInmediato:
    """En las pruebas, el trabajo «en segundo plano» corre en el acto."""
    def __init__(self, target, args=(), **kw):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def ia(app, monkeypatch):
    for nombre, valor in {"IA_LOCAL_URL": "http://local.test/v1", "IA_LOCAL_MODELO": "modelo-local",
                          "IA_EXT_URL": "https://externo.test/v1", "IA_EXT_MODELO": "modelo-externo",
                          "IA_EXT_CLAVE": "clave-de-prueba", "IA_EXT_ZDR": True}.items():
        monkeypatch.setattr(config, nombre, valor)
    llamadas, respuesta = [], {"texto": "Borrador."}

    def falso(url, cabeceras, datos, tiempo):
        llamadas.append({"url": url, "datos": datos, "usuario": datos["messages"][1]["content"]})
        return respuesta["texto"]
    monkeypatch.setattr(servicio, "_enviar", falso)
    monkeypatch.setattr(servicio.threading, "Thread", _HiloInmediato)
    admin = usuarios.por_email("admin@test.cl")["id"]
    pid, _ = servicio.crear_politica("Política de prueba.", admin)
    servicio.aprobar_politica(pid, admin)

    def activar(*claves):
        for clave in claves:
            assert servicio.activar(clave, admin, admin) is None
    return {"llamadas": llamadas, "respuesta": respuesta, "activar": activar, "admin": admin}


def _rol(uid, rol, sigla="CMAT"):
    permisos.asignar(uid, rol, unidades.instituto() if sigla == "IIMAT" else unidades.id_de(sigla))


def _decidir(client, uso_id, decision="aprobar", **datos):
    return client.post(f"/ia/uso/{uso_id}/decidir", headers=HX, data={"decision": decision, "volver": "/", **datos})


# --- Etapa 0b: pantallas y permisos ---------------------------------------------------------------------------------

def test_pantallas_por_rol(client, gente, ia):
    entrar(client, "emmy")
    r = client.get("/ia")
    assert r.status_code == 200 and "Uso de IA en TAU" in r.text and "Apagada" in r.text
    assert "Política de prueba." in r.text and "tutoría" in r.text      # vedados a la vista
    assert 'href="/ia"' in client.get("/").text                         # en el menú de todo el personal
    for ruta in ("/ia/admin", "/ia/usos", "/ia/sesgos"):
        assert client.get(ruta).status_code == 403, ruta
    assert client.post("/ia/admin/memoria_borrador/activar", data={"responsable_id": str(gente["emmy"])},
                       headers=HX).status_code == 403
    _rol(gente["alan"], "direccion_instituto", "IIMAT")
    entrar(client, "alan")
    assert client.get("/ia/usos").status_code == 200 and client.get("/ia/sesgos").status_code == 200
    assert client.get("/ia/admin").status_code == 403
    _rol(gente["admin"], "direccion_carrera")
    entrar(client, "admin")
    assert client.get("/ia/admin").status_code == 200
    assert "cifra por verificar" in client.get("/ia/guia").text


def test_administrar_politica_y_funciones(client, gente):
    _rol(gente["admin"], "direccion_carrera")
    entrar(client, "admin")
    client.post("/ia/admin/memoria_borrador/activar", data={"responsable_id": str(gente["alan"])}, headers=HX)
    assert not servicio.activa("memoria_borrador")                       # sin política aprobada no se activa
    r = client.get("/ia/admin/politica/nueva")
    assert "Decisión humana" in r.text                                   # se propone un borrador de política
    client.post("/ia/admin/politica", data={"texto": "1. La persona decide."}, headers=HX)
    pol = servicio.politicas()[0]
    assert not pol["vigente"]
    client.post(f"/ia/admin/politica/{pol['id']}/aprobar", headers=HX)
    assert servicio.politica_vigente()["texto"] == "1. La persona decide."
    client.post("/ia/admin/memoria_borrador/activar", data={"responsable_id": str(gente["alan"])}, headers=HX)
    assert servicio.estado_funcion("memoria_borrador")["responsable_id"] == gente["alan"]
    assert "Alan Turing" in client.get("/ia").text
    client.post("/ia/admin/memoria_borrador/apagar", headers=HX)
    assert not servicio.activa("memoria_borrador")


# --- Etapa 1a: memoria ----------------------------------------------------------------------------------------------

def test_memoria_cifras_desde_la_base_y_marca(client, gente, ia):
    ia["activar"]("memoria_borrador")
    _rol(gente["alan"], "direccion_instituto", "IIMAT")
    m = informes.memoria(anio=HOY)
    entidad = f"memoria:{m['desde']}_{m['hasta']}"
    ia["respuesta"]["texto"] = (f"Presentación\nEn {HOY} el Instituto publicó 42 artículos; en total, {{{{productos}}}} "
                                "productos y {{proyectos}} proyectos. {{inventado}}")
    entrar(client, "emmy")   # sin la Dirección del Instituto no puede pedirlo
    assert client.post(f"/informes/memoria/ia?anio={HOY}", headers=HX).status_code == 403
    assert servicio.ultimo("memoria_borrador", entidad) is None
    entrar(client, "alan")
    r = client.post(f"/informes/memoria/ia?anio={HOY}", headers=HX, data={"volver": f"/informes/memoria?anio={HOY}"})
    assert "Borrador generado con IA" in r.text
    uso = servicio.ultimo("memoria_borrador", entidad)
    # Ninguna cifra viene del modelo: los marcadores se reemplazan por los valores de la base y el resto se marca.
    assert uso["texto_generado"] == (f"Presentación\nEn {HOY} el Instituto publicó [cifra por verificar] artículos; en "
                                     f"total, {len(m['productos'])} productos y {len(m['proyectos'])} proyectos. "
                                     "[cifra por verificar]")
    enviado = ia["llamadas"][-1]["usuario"]
    assert "{{productos}}" in enviado and "[periodo.texto]" in enviado
    pagina = client.get(f"/informes/memoria?anio={HOY}").text
    assert "Elaborado con apoyo de IA" not in pagina                     # el borrador no entra al documento
    entrar(client, "emmy")
    assert _decidir(client, uso["id"], texto_final="Otro").status_code == 403
    entrar(client, "alan")
    final = uso["texto_generado"].replace("[cifra por verificar] artículos", "dos artículos")
    _decidir(client, uso["id"], texto_final=final, valoracion="4")
    uso = servicio.obtener(uso["id"])
    assert uso["estado"] == "editada" and uso["valoracion"] == 4 and 0 < uso["distancia_edicion"] < 1
    pagina = client.get(f"/informes/memoria?anio={HOY}").text
    assert "dos artículos" in pagina and "revisado por la Dirección del Instituto" in pagina


# --- Etapa 1b: informe de proyecto y piloto -------------------------------------------------------------------------

def test_informe_de_proyecto_solo_el_responsable(client, gente, ia):
    ia["activar"]("informe_proyecto_borrador")
    pid = proyectos.crear(dict(nombre="Grafos finitos", estado="vigente", descripcion="Coloración de grafos.",
                               fecha_inicio=f"{HOY}-01-01"), gente["emmy"], gente["emmy"])
    _rol(gente["alan"], "direccion_instituto", "IIMAT")      # ve el proyecto, pero no es su responsable
    entrar(client, "alan")
    r = client.post(f"/proyectos/{pid}/informe/ia?desde={HOY}&hasta={HOY}", headers=HX)
    assert "No tiene permiso" in r.text
    entrar(client, "emmy")
    ia["respuesta"]["texto"] = "El proyecto avanza: {{productos}} productos."
    client.post(f"/proyectos/{pid}/informe/ia?desde={HOY}&hasta={HOY}", headers=HX)
    uso = servicio.ultimo("informe_proyecto_borrador", catalogo.entidad_informe(pid, HOY, HOY))
    assert uso["texto_generado"] == "El proyecto avanza: 0 productos." and uso["entidad_id"] == pid
    assert "Coloración de grafos." in ia["llamadas"][-1]["usuario"]
    _decidir(client, uso["id"], texto_final=uso["texto_generado"])
    assert servicio.obtener(uso["id"])["estado"] == "aprobada"
    r = client.get(f"/proyectos/{pid}/informe?desde={HOY}&hasta={HOY}")
    assert "Síntesis del periodo" in r.text and "revisado por el responsable del proyecto" in r.text


def test_medicion_y_cierre_del_piloto(client, gente, ia):
    ia["activar"]("informe_proyecto_borrador")
    pid = proyectos.crear(dict(nombre="P", estado="vigente"), gente["emmy"], gente["emmy"])
    auth = {"id": gente["emmy"]}
    ent = catalogo.entidad_informe(pid, HOY, HOY)
    for decision in ("aprobar", "rechazar"):
        uid = servicio.generar("informe_proyecto_borrador", [("proyecto.nombre", "P")], auth, entidad_tipo=ent)
        assert servicio.decidir(uid, auth, decision, "Borrador.", valoracion="5") == []
    fila = next(x for x in medicion.piloto() if x["clave"] == "informe_proyecto_borrador")
    assert (fila["n"], fila["aprobada"], fila["rechazada"], fila["pct_aceptadas"], fila["valoracion"]) == (2, 1, 1, 50, 5)
    _rol(gente["admin"], "direccion_carrera")
    entrar(client, "admin")
    assert "Informe de avance" not in client.get("/ia/usos").text   # no muestra textos ni personas
    r = client.post("/ia/cierre", headers=HX, data={"clave": "informe_proyecto_borrador", "decision": "retirar",
                                                    "fundamento": "corto"})
    assert "Fundamente" in r.text and medicion.cierres() == []
    client.post("/ia/cierre", headers=HX, data={"clave": "informe_proyecto_borrador", "decision": "retirar",
                                                "fundamento": "La mitad de los borradores se descartó en el piloto."})
    assert medicion.cierres()[0]["decision"] == "retirar" and not servicio.activa("informe_proyecto_borrador")
    assert "La mitad de los borradores" in client.get("/ia/usos").text


# --- Etapa 2: clasificación de productos, resumen del perfil y sesgos -------------------------------------------------

def _producto(uid, titulo="Optimización en grafos"):
    tipo = get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Preprint'")[0]["id"]
    pid = get_db().t.producto.insert(tipo_id=tipo, titulo=titulo, anio=HOY, estado_publicacion="publicado",
                                     revision="sin_arbitraje", creado_por=uid, resumen="Un resumen.")["id"]
    get_db().t.producto_autor.insert(producto_id=pid, orden=1, investigador_id=uid)
    return pid


def test_clasificar_producto_solo_guarda_lo_confirmado(client, gente, ia):
    ia["activar"]("producto_clasificar")
    pid = _producto(gente["emmy"])
    v = [str(x["id"]) for x in lineas.vigentes()]
    ia["respuesta"]["texto"] = f"{v[0]}, 9999, {v[1]}, {v[0]}"
    entrar(client, "alan")    # no es autor: no puede
    assert client.post(f"/productos/{pid}/lineas/ia", headers=HX).status_code == 403
    entrar(client, "emmy")
    assert "Sugerir líneas con IA" in client.get(f"/productos/{pid}").text
    client.post(f"/productos/{pid}/lineas/ia", headers=HX)
    uso = servicio.ultimo("producto_clasificar", f"producto:{pid}")
    assert uso["texto_generado"] == f"{v[0]},{v[1]}" and uso["proveedor"] == "externo"   # datos públicos
    assert get_db().q("SELECT * FROM producto_linea") == []              # nada se guarda sin confirmar
    assert "Sugerida" in client.get(f"/productos/{pid}").text
    r = _decidir(client, uso["id"], elegido=[])
    assert "Marque al menos una opción" in r.text
    _decidir(client, uso["id"], elegido=[v[1]])
    assert servicio.obtener(uso["id"])["estado"] == "editada"
    assert [str(x["id"]) for x in lineas.directas_de_producto(pid)] == [v[1]]
    assert v[1] in [str(x["id"]) for x in lineas.de_registro("producto", pid)]
    assert lineas.en_uso(int(v[1]))
    client.delete(f"/productos/{pid}/lineas/{v[1]}", headers=HX)
    assert lineas.directas_de_producto(pid) == []


def test_reporte_de_sesgos(client, gente, ia):
    ia["activar"]("producto_clasificar")
    v = [str(x["id"]) for x in lineas.vigentes()]
    auth = {"id": gente["emmy"]}
    for i in range(6):
        pid = _producto(gente["emmy"], f"Producto {i}")
        ia["respuesta"]["texto"] = f"{v[0]}, {v[1]}"
        uid = servicio.generar("producto_clasificar", [("producto.titulo", "T")], auth, entidad_tipo=f"producto:{pid}",
                               entidad_id=pid, posproceso=catalogo.datos_clasificar(productos.obtener(pid))[1])
        servicio.decidir(uid, auth, "aprobar", v[0])          # la segunda línea siempre se descarta
    s = medicion.sesgos()
    assert s["total"] == 12 and s["pct"] == 50
    senal = {x["nombre"]: x["senal"] for x in s["por_linea"]}
    assert senal[lineas.obtener(int(v[1]))["nombre"]] and not senal[lineas.obtener(int(v[0]))["nombre"]]
    _rol(gente["alan"], "direccion_instituto", "IIMAT")
    entrar(client, "alan")
    assert "Revisar" in client.get("/ia/sesgos").text


def test_resumen_del_perfil_seudonimizado(client, gente, ia):
    ia["activar"]("cv_resumen")
    _producto(gente["emmy"], "Anillos noetherianos")
    ia["respuesta"]["texto"] = "[PERSONA_1] trabaja en álgebra conmutativa."
    entrar(client, "emmy")
    client.post("/perfil/bio/ia", headers=HX)
    enviado = ia["llamadas"][-1]
    assert "Noether" not in enviado["usuario"] and "Emmy" not in enviado["usuario"]
    assert "[PERSONA_1]" in enviado["usuario"] and "Anillos noetherianos" in enviado["usuario"]
    assert enviado["url"] == "https://externo.test/v1" and enviado["datos"]["provider"] == {"zdr": True}
    uso = servicio.ultimo("cv_resumen", f"investigador:{gente['emmy']}")
    assert uso["texto_generado"] == "Emmy Noether trabaja en álgebra conmutativa."
    assert perfiles.obtener(gente["emmy"])["bio"] in (None, "")          # sin aprobar no cambia el perfil
    _decidir(client, uso["id"], texto_final=uso["texto_generado"])
    assert perfiles.obtener(gente["emmy"])["bio"] == "Emmy Noether trabaja en álgebra conmutativa."
    assert "revisado por el propio investigador" in client.get("/perfil").text
    assert "revisado por el propio investigador" in client.get(f"/investigadores/{gente['emmy']}").text
    perfiles.actualizar_bio(gente["emmy"], "Lo reescribí yo.")
    assert "revisado por el propio investigador" not in client.get(f"/investigadores/{gente['emmy']}").text
    with pytest.raises(servicio.IABloqueada):    # nadie pide el resumen de otra persona
        servicio.generar("cv_resumen", catalogo.datos_cv(gente["emmy"]), {"id": gente["alan"]},
                         entidad_tipo=f"investigador:{gente['emmy']}")


# --- Etapa 3a: síntesis de respuestas abiertas ----------------------------------------------------------------------

def test_sintesis_de_respuestas_abiertas(app, ia):
    from tests.test_encuestas import _csv, _respuestas_validas, _tokens
    filas, errores = importar.leer(_csv(12).encode())
    assert errores == []
    importar.aplicar(filas, None)
    admin = usuarios.por_email("admin@test.cl")["id"]
    permisos.asignar(admin, "direccion_carrera", unidades.id_de("CMAT"))
    c = TestClient(app)
    login(c, "admin@test.cl", PASS_ADMIN)
    ia["activar"]("encuesta_sintesis")
    eid = encuestas.crear_desde_plantilla("satisfaccion", admin)
    encuestas.abrir(eid, admin)
    q = next(x for x in encuestas.preguntas(eid) if x["tipo"] == "texto")
    frase = "las aulas del tercer piso no tienen buena ventilación en verano"
    tokens = _tokens(eid)
    for i, t in enumerate(tokens[:9]):
        assert encuestas.responder(t, {**_respuestas_validas(eid), q["id"]: [f"Respuesta {i}: {frase}"]}) == []
    base = "/docencia/encuestas"
    assert "desde 10 respuestas (hay 9)" in c.get(f"{base}/{eid}/resultados").text
    assert c.post(f"{base}/{eid}/preguntas/{q['id']}/sintesis", headers=HX).status_code == 404
    assert encuestas.responder(tokens[9], {**_respuestas_validas(eid), q["id"]: [f"Otra: {frase}"]}) == []
    ia["respuesta"]["texto"] = f"Ventilación: varias respuestas dicen que {frase}."
    c.post(f"{base}/{eid}/preguntas/{q['id']}/sintesis", headers=HX)
    enviado = ia["llamadas"][-1]
    assert enviado["url"] == "http://local.test/v1"                      # solo el modelo local, aunque haya externo
    assert "e1@correo.bo" not in enviado["usuario"] and "9000001" not in enviado["usuario"]
    uso = servicio.ultimo("encuesta_sintesis", f"encuesta:{eid}:{q['id']}")
    assert uso["texto_generado"] == "Ventilación: varias respuestas dicen que [cita omitida]."
    _decidir(c, uso["id"], texto_final=uso["texto_generado"])
    assert "revisado por quien gestiona las encuestas" in c.get(f"{base}/{eid}/resultados").text


def test_textos_sin_citas_y_cifras():
    assert textos.sin_citas("Uno dos tres.", ["nada que ver"]) == "Uno dos tres."
    assert textos.cifras("Hubo 3,5 y {{n}} en 2026.", {"n": 7}, {"2026"}) == "Hubo [cifra por verificar] y 7 en 2026."


# --- Etapa 3b: evidencias y narrativa de la autoevaluación ------------------------------------------------------------

def test_evidencias_y_narrativa_de_un_criterio(carrera, gente, ia):
    from tests.test_autoevaluacion import _crear, _marco
    ia["activar"]("evidencia_sugerir", "autoevaluacion_borrador")
    a = _crear(carrera)
    aid = a["id"]
    c = evidencias.criterios_del_marco(_marco()["id"])[0]
    pid = _producto(gente["emmy"], "Libro de texto de cálculo")
    get_db().execute("UPDATE producto SET anio = ? WHERE id = ?", [a["desde_anio"], pid])
    url = f"/calidad/autoevaluaciones/{aid}/criterios/{c['id']}"
    ia["respuesta"]["texto"] = f"producto-{pid}, producto-99999"
    carrera.post(f"{url}/ia/evidencias", headers=HX)
    uso = servicio.ultimo("evidencia_sugerir", f"evidencias:{aid}:{c['id']}")
    assert uso["texto_generado"] == f"producto-{pid}"
    antes = len(evidencias.listar(a["marco_id"], c["id"]))
    _decidir(carrera, uso["id"], elegido=[f"producto-{pid}"])
    nuevas = evidencias.listar(a["marco_id"], c["id"])
    assert len(nuevas) == antes + 1
    e = next(x for x in nuevas if "Libro de texto" in x["titulo"])
    assert e["tipo"] == "enlace" and e["url"].endswith(f"/productos/{pid}")
    # Narrativa: solo el texto del juicio; el nivel queda como estaba (sin juzgar).
    ia["respuesta"]["texto"] = "Las evidencias muestran producción docente."
    carrera.post(f"{url}/ia/juicio", headers=HX)
    uso = servicio.ultimo("autoevaluacion_borrador", f"juicio:{aid}:{c['id']}")
    assert "Libro de texto de cálculo" in ia["llamadas"][-1]["usuario"]
    assert "Las evidencias muestran" not in carrera.get("/publico/indicadores").text
    _decidir(carrera, uso["id"], texto_final=uso["texto_generado"])
    j = ae.juicios(aid)[c["id"]]
    assert j["juicio"] == "Las evidencias muestran producción docente." and j["nivel"] is None
    assert "Las evidencias muestran" not in carrera.get("/publico/indicadores").text


# --- Etapa 4: capacitación en IA, CV y percepción ---------------------------------------------------------------------

def test_capacitacion_en_ia_en_el_cv_y_el_indicador(client, gente):
    vinculos.agregar(gente["emmy"], "titular", "2015-01-01")
    get_db().t.capacitacion.insert(usuario_id=gente["emmy"], titulo="Uso crítico de la IA generativa",
                                   area="ia_digital", horas=20, fecha_inicio=f"{HOY}-01-10", fecha_fin=f"{HOY}-02-10")
    r = indicadores.calcular("personal_capacitado_ia", HOY)
    assert r.valor is not None and r.valor > 0
    entrar(client, "emmy")
    cv = client.get(f"/informes/cv?desde={HOY}&hasta={HOY}").text
    assert "Capacitación" in cv and "Uso crítico de la IA generativa" in cv and "ia y competencias digitales" in cv


def test_plantilla_de_percepcion_de_la_ia(app):
    eid = encuestas.crear_desde_plantilla("percepcion_ia", None)
    e = encuestas.obtener(eid)
    assert e["anonima"] == 1 and e["publico"] == "docentes" and e["tipo"] == "otra"
