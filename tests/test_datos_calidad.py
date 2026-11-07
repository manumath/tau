"""Datos que faltaban (PLAN §57, etapa 8): capacitación, convenios, impacto de interacción social, empleadores y encuestas
a académicos y empleadores, con los indicadores que ahora se calculan."""
from datetime import date

import pytest

from app.calidad import capacitacion, convenios, evidencias, impacto, indicadores, marco
from app.comun import permisos, unidades, usuarios, vinculos
from app.comun.db import get_db
from app.egresados import empleadores
from app.estudiantil import encuestas
from app.investigacion import proyectos
from tests.conftest import HX, login

CLAVE = "Clave-datos-calidad-1"
HOY = date.today()
ANIO = HOY.year


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def _valor(fuente, anio=ANIO):
    i = get_db().q("SELECT * FROM indicador_calidad WHERE fuente = ?", [f"auto:{fuente}"])[0]
    return indicadores.valores_del_anio(_marco()["id"], anio)[i["id"]]


def _evidencia(uid):
    x, _ = evidencias.validar({"titulo": "Informe", "url": "https://ejemplo.test/informe"}, _marco()["id"], "enlace")
    return evidencias.crear(_marco()["id"], "enlace", {**x, "criterios": []}, uid)


@pytest.fixture
def gente(app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    vinculos.agregar(emmy, "titular", "2015-01-01")
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", CLAVE, debe_cambiar_pass=False)["id"]
    vinculos.agregar(alan, "titular", "2015-01-01")
    return {"emmy": emmy, "alan": alan}


def test_migracion_pasa_los_indicadores_a_automaticos(app):
    fuentes = {f["codigo"]: f["fuente"] for f in get_db().q(
        "SELECT codigo, fuente FROM indicador_calidad WHERE codigo IN ('D2.4.a','D2.4.b','D4.3.a','D6.4.a','D7.4.a','D8.3.b')")}
    assert fuentes == {"D2.4.a": "auto:perfil_titulados", "D2.4.b": "auto:perfil_empleadores",
                       "D4.3.a": "auto:personal_capacitado", "D6.4.a": "auto:impacto_interaccion_social",
                       "D7.4.a": "auto:convenios_activos", "D8.3.b": "auto:satisfaccion_empleadores"}


def test_capacitacion(carrera, gente):
    r = carrera.post("/calidad/capacitacion", headers=HX,
                     data={"usuario_id": str(gente["emmy"]), "titulo": "Didáctica del cálculo", "area": "pedagogica",
                           "fecha_inicio": f"{ANIO}-01-10", "fecha_fin": f"{ANIO}-01-20", "horas": "40"})
    assert r.status_code == 200 and len(capacitacion.listar(ANIO)) == 1
    r = carrera.post("/calidad/capacitacion", headers=HX, data={"usuario_id": str(gente["emmy"]), "titulo": "x",
                                                                "area": "otra", "fecha_inicio": "2030-01-01",
                                                                "fecha_fin": "2030-01-02"})
    assert "cuando haya concluido" in r.text
    assert "Didáctica del cálculo" in carrera.get(f"/calidad/capacitacion?anio={ANIO}").text
    v = _valor("personal_capacitado")
    assert (v["valor"], v["n"]) == (50.0, 2)


def test_convenios(carrera, gente):
    carrera.post("/calidad/convenios", headers=HX, data={"contraparte": "Universidad Ejemplo", "ambito": "internacional",
                                                         "tipo": "marco", "fecha_firma": f"{ANIO - 1}-03-01"})
    carrera.post("/calidad/convenios", headers=HX, data={"contraparte": "Colegio Ejemplo", "ambito": "nacional",
                                                         "tipo": "especifico", "fecha_firma": f"{ANIO - 1}-03-01"})
    a, b = convenios.listar()
    assert a["vigente"] and b["vigente"]
    v = next(x for x in (a, b) if x["contraparte"] == "Universidad Ejemplo")
    carrera.post(f"/calidad/convenios/{v['id']}/actividades", headers=HX,
                 data={"fecha": HOY.isoformat(), "descripcion": "Estancia de investigación"})
    assert len(convenios.obtener(v["id"])["lista_actividades"]) == 1
    carrera.delete(f"/calidad/convenios/{v['id']}", headers=HX)
    assert convenios.obtener(v["id"]) is not None                       # con actividades no se elimina
    x = _valor("convenios_activos")
    assert (x["valor"], x["n"]) == (1, 2)


def test_impacto(client, carrera, gente):
    pid = proyectos.crear(dict(nombre="Olimpiadas", estado="vigente", fecha_inicio=f"{ANIO}-01-01"), gente["emmy"],
                          gente["emmy"], tipo="institucional", clase="interaccion_social")
    assert [p["id"] for p in impacto.proyectos()] == [pid]
    r = carrera.post(f"/calidad/impacto/{pid}", headers=HX, data={"beneficiarios": "120", "comprobado": "1",
                                                                  "descripcion": "Talleres en colegios."})
    assert "necesita su evidencia" in r.text
    eid = _evidencia(usuarios.por_email("admin@test.cl")["id"])
    carrera.post(f"/calidad/impacto/{pid}", headers=HX, data={"beneficiarios": "120", "comprobado": "1",
                                                              "descripcion": "Talleres en colegios.", "evidencia_id": str(eid)})
    assert impacto.proyecto(pid)["comprobado"] == 1
    assert _valor("impacto_interaccion_social")["valor"] == 100.0


def test_impacto_lo_registra_el_responsable(client, gente):
    pid = proyectos.crear(dict(nombre="Olimpiadas", estado="vigente", fecha_inicio=f"{ANIO}-01-01"), gente["alan"],
                          gente["alan"], tipo="institucional", clase="interaccion_social")
    login(client, "alan@test.cl", CLAVE)
    assert client.get(f"/calidad/impacto/{pid}").status_code == 200
    client.post(f"/calidad/impacto/{pid}", headers=HX, data={"beneficiarios": "30"})
    assert impacto.proyecto(pid)["beneficiarios"] == 30
    r = client.get("/calidad/impacto")                                  # sin rol: solo sus proyectos, desde el menú
    assert r.status_code == 200 and "Olimpiadas" in r.text and 'href="/calidad/impacto"' in r.text
    client.get("/logout")
    usuarios.crear("otro@test.cl", "Otro", "Docente", CLAVE, debe_cambiar_pass=False)
    login(client, "otro@test.cl", CLAVE)
    assert client.get("/calidad/impacto").status_code == 403
    assert client.get(f"/calidad/impacto/{pid}").status_code == 403
    assert client.post(f"/calidad/impacto/{pid}", data={"beneficiarios": "1"}).status_code == 403


def test_empleadores_y_encuestas(carrera, gente):
    r = carrera.post("/docencia/empleadores", headers=HX, data={"organizacion": "Banco Ejemplo", "sector": "privado",
                                                                "nombres": "Ana", "apellidos": "Pérez",
                                                                "email": "ana@banco.test"})
    assert r.status_code == 200
    r = carrera.post("/docencia/empleadores", headers=HX, data={"organizacion": "Otro", "sector": "privado", "nombres": "B",
                                                                "apellidos": "C", "email": "ANA@banco.test"})
    assert "Ya hay un empleador" in r.text
    for i in range(4):
        empleadores.crear(empleadores.validar({"organizacion": f"Empresa {i}", "sector": "otro", "nombres": "N",
                                               "apellidos": f"A{i}", "email": f"e{i}@ej.test"})[0], 1)
    m = empleadores.listar()[0]
    carrera.post(f"/docencia/empleadores/{m['id']}/activo", headers=HX)
    assert len(empleadores.listar(activos=True)) == 4
    # Encuesta a empleadores: va a los activos; con sus respuestas se calculan dos indicadores.
    eid = encuestas.crear_desde_plantilla("empleadores", 1)
    e = encuestas.obtener(eid)
    assert e["publico"] == "empleadores" and len(encuestas.destinatarios(e)[0]) == 4
    assert encuestas.abrir(eid, 1)[0] == 4
    qs = encuestas.preguntas(eid)
    for k, inv in enumerate(get_db().q("SELECT token FROM invitacion_encuesta WHERE encuesta_id = ?", [eid])):
        crudo = {q["id"]: [str(4 if k < 3 else 2)] if q["tipo"] == "escala" else ["si"] if q["tipo"] == "si_no"
                 else ["Más programación."] for q in qs}
        assert encuestas.responder(inv["token"], crudo) == []
    sat, perfil = _valor("satisfaccion_empleadores"), _valor("perfil_empleadores")
    assert (sat["valor"], sat["n"]) == (75.0, 4)
    assert perfil["valor"] == 3.5
    # Encuesta a académicos: va a los vinculados, con una ficha externa enlazada a su cuenta que se reutiliza.
    did = encuestas.crear_desde_plantilla("docentes", 1)
    gente_d, _ = encuestas.destinatarios(encuestas.obtener(did))
    assert len(gente_d) == 2
    assert encuestas.destinatarios(encuestas.obtener(did))[0] == gente_d
    assert get_db().q("SELECT COUNT(*) AS n FROM persona_externa WHERE usuario_id IS NOT NULL")[0]["n"] == 2


@pytest.fixture
def cuenta(app):
    def crear(email, rol, sigla):
        u = usuarios.crear(email, "Prueba", "Datos", CLAVE, debe_cambiar_pass=False, es_investigador=False)
        permisos.asignar(u["id"], rol, unidades.id_de(sigla))
        return u
    return crear


def test_permisos(client, cuenta, gente):
    cuenta("comision@test.cl", "comision_calidad", "UMSA")
    cuenta("datos@test.cl", "gestion_datos", "CMAT")
    login(client, "comision@test.cl", CLAVE)
    for url in ("/calidad/capacitacion", "/calidad/convenios", "/calidad/impacto"):
        assert client.get(url).status_code == 200, url
    assert client.post("/calidad/capacitacion", data={"titulo": "x"}).status_code == 403
    assert client.post("/calidad/convenios", data={"contraparte": "x"}).status_code == 403
    client.get("/logout")
    login(client, "datos@test.cl", CLAVE)
    assert client.get("/calidad/capacitacion/nueva").status_code == 200
    assert client.get("/calidad/convenios/nuevo").status_code == 403
