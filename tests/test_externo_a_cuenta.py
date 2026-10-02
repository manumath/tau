"""Una persona externa que luego recibe cuenta: sugerencias y vinculación sin perder registros (PLAN §42)."""
from app.acreditacion import calidad
from app.acreditacion import estudiantes as ind_estudiantes
from app.comun import estudiantes, personas, usuarios, vinculos
from app.comun.db import get_db
from app.investigacion import actividades, productos, proyectos
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login


def _producto(uid, titulo, autores, tipo="Preprint", anio="2024"):
    d, err = productos.preparar(dict(tipo_id=str(get_db().q("SELECT id FROM tipo_producto WHERE nombre = ?", [tipo])
                                                 [0]["id"]), titulo=titulo, anio=anio, estado_publicacion="publicado",
                                     revision="sin_arbitraje"), autores, [])
    assert not err, err
    return productos.guardar(d, autores, uid)


def _escenario():
    emmy = usuarios.por_email("inv@test.cl")["id"]
    ana_ext = personas.crear_externo("Ana", "Quispe", "UMSA", "Bolivia", emmy)["id"]
    get_db().execute("UPDATE persona_externa SET orcid = '0000-0002-0000-0002' WHERE id = ?", [ana_ext])
    get_db().t.estudiante.insert(externo_id=ana_ext, nivel="licenciatura", desde=2022, hasta=2025, titulado=1)
    ana = usuarios.crear("ana@test.cl", "Ana María", "Quispe", PASS_TEMP)["id"]       # ahora es docente
    return emmy, ana_ext, ana


def test_sugerencias(app):
    emmy, ana_ext, ana = _escenario()
    s = personas.sugerencias_de_cuenta()
    assert [(x["externo"]["id"], x["usuario"]["id"], x["motivo"]) for x in s] == [
        (ana_ext, ana, "Mismo apellido y nombres compatibles")]
    get_db().execute("UPDATE investigador SET orcid = '0000-0002-0000-0002' WHERE usuario_id = ?", [ana])
    assert personas.sugerencias_de_cuenta()[0]["motivo"] == "Mismo ORCID"
    get_db().execute("UPDATE investigador SET orcid = '0000-0009-0000-0009' WHERE usuario_id = ?", [ana])
    assert personas.sugerencias_de_cuenta() == []                       # ORCID distintos: otra persona
    assert next(c for c in calidad.revisar() if c["clave"] == "externos_con_cuenta")["n"] == 0


def test_vincular_sin_perder_registros_ni_su_historia_de_estudiante(app):
    emmy, ana_ext, ana = _escenario()
    assert vinculos.agregar(emmy, "titular", "2020-01-01") == []       # dirige la tesis estando vinculada
    tesis = _producto(emmy, "Tesis de Ana", [f"e:{ana_ext}", f"i:{emmy}"], tipo=estudiantes.TIPO_TESIS, anio="2024")
    comun = _producto(emmy, "Común", [f"i:{emmy}", f"e:{ana_ext}", f"i:{ana}"])        # figura dos veces
    tipo = get_db().q("SELECT id FROM tipo_actividad WHERE nombre = 'Seminario'")[0]["id"]
    aid = actividades.guardar(dict(tipo_id=tipo, titulo="Seminario", fecha_inicio="2024-05-01", modalidad="presencial",
                                   ambito="local"), [(f"i:{emmy}", "expositor"), (f"e:{ana_ext}", "asistente")], emmy)
    pid = proyectos.crear(dict(nombre="Proyecto", estado="vigente"), emmy, emmy)
    assert proyectos.agregar_participante(pid, f"e:{ana_ext}", "tesista") is None

    assert personas.vincular_a_cuenta(ana_ext, ana) is None
    internos = lambda p: [a["id"] for a in productos.obtener(p)["autores"] if a["interno"]]  # noqa: E731
    assert internos(comun) == [emmy, ana] and len(productos.obtener(comun)["autores"]) == 2   # una sola vez
    assert ana in internos(tesis)
    assert [p["id"] for p in actividades.participantes(aid) if p["interno"]] == [emmy, ana]
    assert any(p["interno"] and p["id"] == ana and p["rol"] == "tesista" for p in proyectos.participantes(pid))
    # La ficha queda enlazada (guarda sus periodos de estudiante) y ya no aparece entre los externos.
    ficha = get_db().q("SELECT * FROM persona_externa WHERE id = ?", [ana_ext])[0]
    assert ficha["usuario_id"] == ana and all(e["id"] != ana_ext for e in personas.externos())
    assert get_db().q("SELECT orcid FROM investigador WHERE usuario_id = ?", [ana])[0]["orcid"] == "0000-0002-0000-0002"
    # Su historia de estudiante sigue contando: la tesis y los productos de cuando era estudiante.
    yo = {"id": ana, "interno": True}
    assert estudiantes.estudiante_de(yo, 2024)["nivel"] == "licenciatura" and estudiantes.graduado_de(yo, 2026)
    assert estudiantes.es_estudiante_ref(productos.obtener(comun)["autores"], 2024)
    t = next(x for x in ind_estudiantes.tesis(2024, 2024) if x["producto"]["id"] == tesis)
    assert [x["id"] for x in t["tesistas"]] == [ana] and t["nivel"] == "licenciatura"
    assert "ya está vinculada" in personas.vincular_a_cuenta(ana_ext, ana)
    assert personas.sugerencias_de_cuenta() == []


def test_sin_periodos_de_estudiante_la_ficha_se_borra(app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    ext = personas.crear_externo("Alan", "Turing", "Princeton", None, emmy)["id"]
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP)["id"]
    _producto(emmy, "Máquinas", [f"i:{emmy}", f"e:{ext}"])
    assert personas.vincular_a_cuenta(ext, alan) is None
    assert get_db().q("SELECT 1 FROM persona_externa WHERE id = ?", [ext]) == []


def test_pantalla_y_permisos(client, app):
    emmy, ana_ext, ana = _escenario()
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.post("/personas/externos/vincular", headers=HX,
                       data={"externo": ana_ext, "usuario": ana}).status_code == 403
    assert client.get(f"/personas/externos/{ana_ext}/vincular").status_code == 403
    assert "Vincular a una cuenta" not in client.get("/personas/externos?todos=1").text
    client.post("/logout")
    login(client, "admin@test.cl", PASS_ADMIN)
    r = client.get("/personas/externos/duplicados")
    assert "Ya tienen cuenta en el sistema" in r.text and "Vincular a esta cuenta" in r.text
    assert "Vincular a una cuenta" in client.get("/personas/externos?todos=1").text
    modal = client.get(f"/personas/externos/{ana_ext}/vincular").text
    assert modal.index("Quispe, Ana María") < modal.index("Noether, Emmy")     # primero las del mismo apellido
    r = client.post("/personas/externos/vincular", headers=HX, data={"externo": ana_ext, "usuario": ana})
    assert "sus registros ahora son de Ana María Quispe" in r.text
    assert get_db().q("SELECT 1 FROM auditoria WHERE accion = 'vincular_externo'")
