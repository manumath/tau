import pytest

from app.investigacion import actividades
from app.comun import personas, usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login


@pytest.fixture
def inv(client):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    client.uid = uid
    return client


def _form(uid, **extra):
    tipo = get_db().q("SELECT id FROM tipo_actividad WHERE nombre = 'Congreso'")[0]["id"]
    base = dict(tipo_id=str(tipo), titulo="Congreso de Álgebra", fecha_inicio="2026-07-06",
                fecha_fin="2026-07-10", modalidad="presencial", ambito="internacional",
                lugar="Zúrich", pais="Suiza", participante=[f"i:{uid}"], rol=["expositor"])
    return {**base, **extra}


def test_crear_actividad_con_participantes_y_roles(inv):
    colega = usuarios.crear("alan@test.cl", "Alan", "Turing", "Clave-colega-1")
    weyl = personas.crear_externo("Hermann", "Weyl", "IAS", None, inv.uid)
    r = inv.post("/actividades", headers=HX, data=_form(
        inv.uid, participante=[f"i:{inv.uid}", f"e:{weyl['id']}", f"i:{colega['id']}"],
        rol=["organizador", "expositor", "asistente"]))
    assert "actividades-cambiadas" in r.headers["hx-trigger"]
    a = actividades.de_investigador(inv.uid)[0]
    assert a["mi_rol"] == "organizador" and a["n_part"] == 3
    assert [(p["apellidos"], p["rol"]) for p in actividades.participantes(a["id"])] == [
        ("Noether", "organizador"), ("Weyl", "expositor"), ("Turing", "asistente")]
    assert actividades.de_investigador(colega["id"])[0]["mi_rol"] == "asistente"


def test_validaciones(inv):
    r = inv.post("/actividades", headers=HX, data=_form(
        inv.uid, titulo="", fecha_inicio="2026-07-10", fecha_fin="2026-07-01", participante=[], rol=[]))
    assert "título es obligatorio" in r.text and "anterior a la de inicio" in r.text
    assert "al menos un participante" in r.text
    r = inv.post("/actividades", headers=HX, data=_form(
        inv.uid, participante=[f"i:{inv.uid}", f"i:{inv.uid}"], rol=["expositor", "asistente"]))
    assert "repetidos" in r.text


def test_fechas_texto():
    f = actividades.fechas_texto
    assert f({"fecha_inicio": "2026-03-02", "fecha_fin": None}) == "2 mar 2026"
    assert f({"fecha_inicio": "2026-03-02", "fecha_fin": "2026-03-06"}) == "2–6 mar 2026"
    assert f({"fecha_inicio": "2026-03-30", "fecha_fin": "2026-04-02"}) == "30 mar – 2 abr 2026"
    assert f({"fecha_inicio": "2025-12-30", "fecha_fin": "2026-01-02"}) == "30 dic 2025 – 2 ene 2026"


def test_filtros(inv):
    inv.post("/actividades", headers=HX, data=_form(inv.uid))
    inv.post("/actividades", headers=HX, data=_form(inv.uid, titulo="Seminario de lógica",
                                                     fecha_inicio="2025-05-01", fecha_fin=""))
    r = inv.get("/actividades/lista", headers=HX, params={"anio": "2025"})
    assert "Seminario de lógica" in r.text and "Congreso de Álgebra" not in r.text
    r = inv.get("/actividades/lista", headers=HX, params={"q": "ALGEBRA"})
    assert "Congreso de Álgebra" in r.text


def test_editar_y_eliminar(inv):
    inv.post("/actividades", headers=HX, data=_form(inv.uid))
    aid = actividades.de_investigador(inv.uid)[0]["id"]
    inv.put(f"/actividades/{aid}", headers=HX, data=_form(inv.uid, titulo="Congreso renombrado"))
    assert actividades.obtener(aid)["titulo"] == "Congreso renombrado"
    r = inv.delete(f"/actividades/{aid}?desde=ficha", headers=HX)
    assert r.headers["hx-redirect"] == "/actividades" and actividades.obtener(aid) is None


def test_ficha_muestra_presentaciones_vinculadas(inv):
    inv.post("/actividades", headers=HX, data=_form(inv.uid))
    aid = actividades.de_investigador(inv.uid)[0]["id"]
    tipo = get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Presentación'")[0]["id"]
    inv.post("/productos", headers=HX, data=dict(
        tipo_id=str(tipo), titulo="Mi charla", anio="2026", estado_publicacion="publicado",
        actividad_id=str(aid), autor=[f"i:{inv.uid}"]))
    r = inv.get(f"/actividades/{aid}")
    assert "Mi charla" in r.text and "Archivos adjuntos" in r.text


# --- Selector de personas ---------------------------------------------------------------

def test_buscar_personas_internas_y_externas_sin_tildes(inv):
    usuarios.crear("sofia@test.cl", "Sofía", "Kovalévskaya", "Clave-colega-1")
    personas.crear_externo("Sofia", "Kovalevskaya Externa", "Otra U.", None, inv.uid)
    r = inv.get("/personas/buscar", params={"campo": "autor", "q": "kovalev"})
    assert "Sofía Kovalévskaya" in r.text and "Kovalevskaya Externa" in r.text
    assert r.text.index("Kovalévskaya") < r.text.index("Kovalevskaya Externa")  # internos primero
    assert "como persona externa" in r.text
    r = inv.get("/personas/buscar", params={"campo": "autor", "q": "noether", "autor": [f"i:{inv.uid}"]})
    assert "Emmy Noether" not in r.text  # excluye a quien ya está en la lista


def test_crear_externo_reutiliza_si_ya_existe(inv):
    r = inv.post("/personas/externo", headers=HX, data=dict(
        campo="autor", ext_nombres="Hermann", ext_apellidos="Weyl", ext_institucion="IAS"))
    assert 'name="autor"' in r.text and "Hermann Weyl" in r.text
    inv.post("/personas/externo", headers=HX, data=dict(
        campo="autor", ext_nombres="hermann", ext_apellidos="WEYL"))
    assert get_db().q("SELECT COUNT(*) n FROM persona_externa")[0]["n"] == 1


def test_crear_externo_sin_apellido_reubica_el_error(inv):
    r = inv.post("/personas/externo", headers=HX, data=dict(campo="participante", ext_nombres="Solo"))
    assert "obligatorios" in r.text and r.headers["hx-retarget"] == "#resultados-participante"


def test_fila_de_participante_incluye_rol(inv):
    r = inv.get("/personas/fila", params={"campo": "participante", "ref": f"i:{inv.uid}"})
    assert 'name="participante"' in r.text and 'name="rol"' in r.text
    assert inv.get("/personas/fila", params={"campo": "otro", "ref": f"i:{inv.uid}"}).text == ""
