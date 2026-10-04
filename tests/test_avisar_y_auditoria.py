"""«Avisar a los responsables» desde Calidad de datos y exportación de la auditoría (PLAN.md §48, paso 5)."""
import csv
import io

from starlette.testclient import TestClient

from app.acreditacion import calidad
from app.comun import permisos, unidades, usuarios, vinculos
from app.comun.db import auditar, get_db
from tests.conftest import HX, PASS_TEMP, login
from tests.test_vinculos import _producto, hoy  # noqa: F401


def _cliente(app, email, rol=None, unidad="CMAT"):
    uid = usuarios.por_email(email)["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    if rol:
        permisos.asignar(uid, rol, unidades.id_de(unidad))
    c = TestClient(app)
    login(c, email, PASS_TEMP)
    c.uid = uid
    return c


def _avisos(uid):
    return get_db().q("SELECT * FROM notificacion WHERE usuario_id = ? ORDER BY id", [uid])


def test_avisar_a_cada_responsable_una_vez(app, hoy):  # noqa: F811
    emmy = usuarios.por_email("inv@test.cl")["id"]
    vinculos.agregar(emmy, "titular", None)
    pid = _producto(emmy, "Anillos", 2026, 3)  # arbitrado, publicado, sin clasificación MSC
    c = {x["clave"]: x for x in calidad.revisar()}
    assert list(c["sin_grado"]["destinatarios"]) == [emmy] and list(c["sin_msc"]["destinatarios"]) == [emmy]
    assert calidad.avisar("sin_msc", por=0) == {"avisadas": 1, "ya_avisadas": 0}
    a = _avisos(emmy)[-1]
    assert a["asunto"].startswith("Calidad de datos: Publicaciones indexadas o arbitradas sin clasificación")
    assert "- Anillos (2026)" in a["texto"] and a["url"] == f"/productos/{pid}"   # un solo registro: a él
    assert calidad.avisar("sin_msc", por=0) == {"avisadas": 0, "ya_avisadas": 1}  # no se repite en 7 días
    assert calidad.avisar("sin_grado", por=emmy) == {"avisadas": 0, "ya_avisadas": 0}  # no se avisa a sí misma


def test_quien_puede_avisar(app, hoy):  # noqa: F811
    emmy = usuarios.por_email("inv@test.cl")["id"]
    vinculos.agregar(emmy, "titular", None)
    usuarios.crear("comite@test.cl", "Carla", "Comité", PASS_TEMP, es_investigador=False)
    usuarios.crear("carrera@test.cl", "Dora", "Directora", PASS_TEMP, es_investigador=False)
    comite = _cliente(app, "comite@test.cl", "comite_acreditacion", "UMSA")
    carrera = _cliente(app, "carrera@test.cl", "direccion_carrera")
    assert "Avisar a 1 persona" not in comite.get("/informes/calidad").text          # el Comité solo mira
    assert comite.post("/informes/calidad/sin_grado/avisar", headers=HX).status_code == 403
    assert "Avisar a 1 persona" in carrera.get("/informes/calidad").text
    assert carrera.post("/informes/calidad/oferta/avisar", headers=HX).status_code == 404   # la corrige la Carrera
    r = carrera.post("/informes/calidad/sin_grado/avisar", headers=HX)
    assert "Se avisó a 1 persona(s)." in r.text and len(_avisos(emmy)) == 1
    assert get_db().q("SELECT detalle FROM auditoria WHERE accion = 'avisar_calidad'")[0]["detalle"] == \
        "sin_grado: 1 avisada(s), 0 ya avisada(s)"


def test_exportar_auditoria(admin):
    aid = usuarios.por_email("admin@test.cl")["id"]
    auditar(aid, "editar_producto", "producto", 7, '=HYPERLINK("http://x")')
    auditar(aid, "eliminar_producto", "producto", 8, "Notas")
    get_db().execute("UPDATE auditoria SET fecha = '2025-01-15 12:00:00' WHERE detalle = 'Notas'")
    r = admin.get("/admin/auditoria/csv", params={"accion": "editar_producto"})
    assert r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
    filas = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert [(f["Acción"], f["Id del registro"]) for f in filas] == [("Editó producto", "7")]
    assert filas[0]["Detalle"].startswith("'=")                                   # fórmula neutralizada
    fechas = admin.get("/admin/auditoria/csv", params={"fecha_desde": "2025-01-01", "fecha_hasta": "2025-01-15"})
    assert [f["Detalle"] for f in csv.DictReader(io.StringIO(fechas.content.decode("utf-8-sig")))] == ["Notas"]
    vacio = admin.get("/admin/auditoria/csv", params={"q": "no-existe"}).content.decode("utf-8-sig")
    assert vacio.strip() == "Fecha (hora local),Persona,Acción,Código de acción,Registro,Id del registro,Detalle"
    assert get_db().q("SELECT count(*) AS n FROM auditoria WHERE accion = 'exportar_auditoria'")[0]["n"] == 3
    pagina = admin.get("/admin/auditoria", params={"fecha_desde": "2025-01-01", "fecha_hasta": "2025-01-31"}).text
    assert "Notas" in pagina and "HYPERLINK" not in pagina and 'href="/admin/auditoria/csv"' in pagina
