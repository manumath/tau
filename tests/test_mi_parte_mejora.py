"""«Mi parte del plan de mejora» (PLAN §72, etapa 6): pendientes, inicio, calendario y avance desde un modal."""
from datetime import date

from app.calidad import actividades_mejora as am
from app.calidad import cortes_mejora as cm
from app.calidad import marco, mejora
from app.comun import permisos, unidades, usuarios
from tests.conftest import HX, login

CLAVE = "Clave-resp-12345"


def _actividad():
    d = usuarios.por_email("admin@test.cl")
    permisos.asignar(d["id"], "direccion_carrera", unidades.id_de("CMAT"))
    r = usuarios.por_email("inv@test.cl")
    usuarios.cambiar_password(r["id"], CLAVE, temporal=False)
    mid = marco.de_unidad(unidades.id_de("CMAT"))["id"]
    x, _ = mejora.validar({"codigo": "A4", "titulo": "Retención", "plazo": "2027-12-31", "responsable_id": str(d["id"])}, mid)
    aid = mejora.crear(mid, x, d["id"])
    hoy = date.today()
    x, err = am.validar({"codigo": "4.2", "descripcion": "Taller de inducción\n\nRecursos humanos: docentes.",
                         "responsable_id": str(r["id"]), "plazo": date(hoy.year + 1, 3, 31).isoformat()}, mid)
    assert not err, err
    return r, am.crear(aid, x, d["id"])


def test_mis_pendientes_inicio_y_calendario(client):
    r, tid = _actividad()
    login(client, "inv@test.cl", CLAVE)
    pag = client.get("/investigacion/pendientes").text
    assert "Mi parte del plan de mejora" in pag and "Taller de inducción" in pag and "Recursos humanos" not in pag
    assert "1 actividad del plan de mejora a su cargo" in client.get("/").text
    hoy = date.today()
    ev = cm.eventos(r["id"], hoy, date(hoy.year + 1, 12, 31))
    assert any(e["titulo"].startswith("Vence la actividad 4.2") for e in ev)
    assert any(e["titulo"] == "Fin del trimestre: corte del plan de mejora" for e in ev)
    assert "Vence la actividad 4.2" in client.get("/investigacion/calendario?dias=180").text
    assert cm.eventos(usuarios.por_email("admin@test.cl")["id"], hoy, date(hoy.year + 1, 12, 31)) == []


def test_avance_desde_el_modal_vuelve_a_la_pantalla(client):
    r, tid = _actividad()
    login(client, "inv@test.cl", CLAVE)
    url = f"/calidad/mejora/actividades/{tid}"
    assert "Registrar avance" in client.get(f"{url}/avance?volver=/investigacion/pendientes", headers=HX).text
    resp = client.post(f"{url}/avances", headers=HX, data={"texto": "", "volver": "/investigacion/pendientes"})
    assert "Registrar avance" in resp.text and "hx-redirect" not in resp.headers          # error: vuelve el modal
    resp = client.post(f"{url}/avances", headers=HX, data={"texto": "Primer taller", "porcentaje": "25",
                                                           "volver": "/investigacion/pendientes"})
    assert resp.headers["hx-redirect"] == "/investigacion/pendientes"
    assert am.obtener(tid)["avance"] == 25
    resp = client.post(f"{url}/avances", headers=HX, data={"texto": "Otro", "volver": "//malo.example"})
    assert resp.headers["hx-redirect"] == url                                              # nunca a otro sitio
    # Quien no es responsable no abre el modal.
    client.post("/logout", headers=HX)
    usuarios.crear("otro@test.cl", "Otro", "Docente", "Clave-otro-12345", debe_cambiar_pass=False)
    login(client, "otro@test.cl", "Clave-otro-12345")
    assert client.get(f"{url}/avance", headers=HX).status_code == 403
