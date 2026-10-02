"""Coautores externos duplicados: detección y fusión sin perder registros."""
import pytest

from app.acreditacion import calidad
from app.comun import permisos, personas, usuarios
from app.comun.db import get_db
from app.investigacion import actividades, productos, proyectos
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login


def test_nombres_compatibles():
    assert personas.nombres_compatibles("H.", "Hermann")
    assert personas.nombres_compatibles("Hermann", "Hermann Klaus")
    assert personas.nombres_compatibles("H. K.", "Hermann Klaus")
    assert personas.nombres_compatibles("José", "jose")                 # sin tildes ni mayúsculas
    assert not personas.nombres_compatibles("Hermann", "Hans")
    assert not personas.nombres_compatibles("H. K.", "Hermann Ludwig")


@pytest.fixture
def externos(app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    weyl = personas.crear_externo("Hermann", "Weyl", "IAS", "Estados Unidos", emmy)["id"]
    h_weyl = personas.crear_externo("H.", "Weyl", None, None, emmy)["id"]
    hans = personas.crear_externo("Hans", "Weyl", "ETH", "Suiza", emmy)["id"]         # otra persona
    get_db().execute("UPDATE persona_externa SET orcid = '0000-0001-0000-0001' WHERE id = ?", [h_weyl])
    return {"emmy": emmy, "weyl": weyl, "h_weyl": h_weyl, "hans": hans}


def _producto(uid, titulo, autores):
    d, err = productos.preparar(dict(tipo_id=str(get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Preprint'")
                                                 [0]["id"]), titulo=titulo, anio="2026",
                                     estado_publicacion="publicado", revision="sin_arbitraje"), autores, [])
    assert not err, err
    return productos.guardar(d, autores, uid)


def test_detecta_y_fusiona_sin_duplicar(externos):
    e = externos
    pares = {frozenset((p["a"]["id"], p["b"]["id"])) for p in personas.posibles_duplicados()}
    # «H. Weyl» puede ser Hermann o Hans (se proponen ambos pares); Hermann y Hans no son la misma persona.
    assert pares == {frozenset((e["weyl"], e["h_weyl"])), frozenset((e["h_weyl"], e["hans"]))}
    # Ambas fichas en el mismo producto, y cada una en su propio registro.
    comun = _producto(e["emmy"], "Común", [f"i:{e['emmy']}", f"e:{e['weyl']}", f"e:{e['h_weyl']}"])
    solo_h = _producto(e["emmy"], "Solo H.", [f"i:{e['emmy']}", f"e:{e['h_weyl']}"])
    tipo = get_db().q("SELECT id FROM tipo_actividad WHERE nombre = 'Seminario'")[0]["id"]
    aid = actividades.guardar(dict(tipo_id=tipo, titulo="Seminario", fecha_inicio="2026-05-01", modalidad="presencial",
                                   ambito="local"), [(f"i:{e['emmy']}", "expositor"), (f"e:{e['h_weyl']}", "asistente")],
                              e["emmy"])
    pid = proyectos.crear(dict(nombre="Proyecto", estado="vigente"), e["emmy"], e["emmy"])
    assert proyectos.agregar_participante(pid, f"e:{e['weyl']}", "colaborador") is None
    assert proyectos.agregar_participante(pid, f"e:{e['h_weyl']}", "colaborador") is None
    get_db().t.estudiante.insert(externo_id=e["h_weyl"], nivel="doctorado", desde=2020)

    assert personas.fusionar(e["weyl"], e["h_weyl"]) is None
    assert get_db().q("SELECT 1 FROM persona_externa WHERE id = ?", [e["h_weyl"]]) == []
    autores = lambda pid_: [a["id"] for a in productos.obtener(pid_)["autores"] if not a["interno"]]  # noqa: E731
    assert autores(comun) == [e["weyl"]] and autores(solo_h) == [e["weyl"]]       # una sola vez
    assert [p["id"] for p in actividades.participantes(aid) if not p["interno"]] == [e["weyl"]]
    assert [p["id"] for p in proyectos.participantes(pid) if not p["interno"]] == [e["weyl"]]
    assert get_db().q("SELECT externo_id FROM estudiante")[0]["externo_id"] == e["weyl"]
    w = get_db().q("SELECT * FROM persona_externa WHERE id = ?", [e["weyl"]])[0]
    assert (w["institucion"], w["orcid"]) == ("IAS", "0000-0001-0000-0001")      # completa lo que faltaba
    assert personas.posibles_duplicados() == []      # Hermann (con el ORCID de «H.») y Hans: distintos


def test_no_fusiona_orcid_distintos(externos):
    get_db().execute("UPDATE persona_externa SET orcid = '0000-0009-9999-9999' WHERE id = ?", [externos["weyl"]])
    pares = {frozenset((p["a"]["id"], p["b"]["id"])) for p in personas.posibles_duplicados()}
    assert frozenset((externos["weyl"], externos["h_weyl"])) not in pares
    assert "ORCID distintos" in personas.fusionar(externos["weyl"], externos["h_weyl"])


def test_pantalla_permisos_y_calidad(client, externos):
    usuarios.cambiar_password(externos["emmy"], PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/personas/externos/duplicados").status_code == 403       # una investigadora no fusiona
    assert "Posibles duplicados" not in client.get("/personas/externos").text
    assert client.post("/personas/externos/fusionar", headers=HX,
                       data={"par": f"{externos['weyl']}-{externos['h_weyl']}", "conservar": str(externos["weyl"])}
                       ).status_code == 403
    client.post("/logout")
    login(client, "admin@test.cl", PASS_ADMIN)   # la cuenta admin de las pruebas tiene la Dirección del Instituto
    assert permisos.puede(usuarios.por_email("admin@test.cl"), "gestionar_personas_externas")
    r = client.get("/personas/externos/duplicados")
    assert r.status_code == 200 and "Mismo apellido y nombres compatibles" in r.text
    assert "Coautores externos posiblemente duplicados" in client.get("/informes/calidad").text
    assert next(c for c in calidad.revisar() if c["clave"] == "externos_duplicados")["n"] == 2
    par = f"{min(externos['weyl'], externos['h_weyl'])}-{max(externos['weyl'], externos['h_weyl'])}"
    r = client.post("/personas/externos/fusionar", headers=HX, data={"par": par, "conservar": str(externos["weyl"])})
    assert "Fusionadas: queda «Hermann Weyl»" in r.text
    assert client.post("/personas/externos/fusionar", headers=HX,
                       data={"par": par, "conservar": "999"}).status_code == 400
    assert get_db().q("SELECT accion FROM auditoria WHERE accion = 'fusionar_externos'")
