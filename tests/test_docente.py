"""PLAN §68: servicios para el docente (pendientes, calendario…)."""
from datetime import date, timedelta

from app.academico import docente
from app.comun import usuarios, vinculos
from app.comun.db import get_db
from app.estudiantil import tutoria
from tests.conftest import HX, PASS_TEMP, login
from tests.test_portal_estudiante import _externo, estudiantes_cargados, sofia  # noqa: F401
from tests.test_servicios_estudiante import _docente


def test_sin_nada_no_es_docente_ni_tiene_pendientes(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    assert not docente.es_docente({"id": uid}) and docente.pendientes(uid) == [] and docente.eventos(uid) == []


def test_pendientes_de_tutoria_temas_y_vinculo(sofia):
    from app.servicios import temas
    ext = _externo("1111111")
    doc = _docente()
    assert docente.es_docente({"id": doc["id"]})
    assert tutoria.asignar(ext, doc["id"], None) == []
    assert tutoria.solicitar(ext, "academico", "Quisiera hablar") == []
    tid, _ = temas.crear({"titulo": "Grafos", "cupos": "1", "modalidad": "tesis"}, doc)
    temas.cambiar_estado(tid, "publicado", doc)
    assert temas.solicitar(tid, ext, "Me interesa") == []
    p = docente.pendientes(doc["id"])
    assert {x["tipo"] for x in p} == {"tutoria", "tema"} and all(x["href"] for x in p)
    # Un periodo de vínculo que termina pronto también se avisa (y entra en el calendario).
    hoy = date.today()
    get_db().execute("UPDATE vinculo SET fecha_fin = ? WHERE usuario_id = ?", [(hoy + timedelta(days=10)).isoformat(), doc["id"]])
    assert [x["tipo"] for x in docente.pendientes(doc["id"], hoy) if x["tipo"] == "vinculo"] == ["vinculo"]
    assert any(e["tipo"] == "vinculo" for e in docente.eventos(doc["id"], hoy, hoy + timedelta(days=30)))
    # Una solicitud atendida deja de ser pendiente; lo de otra persona nunca aparece.
    assert docente.pendientes(usuarios.por_email("admin@test.cl")["id"]) == []


def test_situacion_segun_la_fecha():
    hoy = date(2026, 11, 13)
    f = lambda d: {"cuando": d}  # noqa: E731
    assert docente.situacion(f(None), hoy) == "normal" and docente.situacion(f("2026-11-12"), hoy) == "vencido"
    assert docente.situacion(f("2026-11-20"), hoy) == "proximo" and docente.situacion(f("2026-11-21"), hoy) == "normal"


def test_pantallas_del_docente(client, sofia):
    doc = _docente()
    client.post("/logout")
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/docencia/pendientes")
    assert r.status_code == 200 and "Mis pendientes" in r.text and "No tiene nada pendiente" in r.text
    assert "Mi calendario" in client.get("/docencia/calendario").text
    ics = client.get("/docencia/calendario.ics")
    assert ics.status_code == 200 and ics.text.startswith("BEGIN:VCALENDAR") and "Calendario docente" in ics.text
    assert "/docencia/pendientes" in client.get("/docencia/mia").text and doc


def test_un_estudiante_no_entra(sofia):
    assert sofia.get("/docencia/pendientes", follow_redirects=False).status_code in (303, 403)
