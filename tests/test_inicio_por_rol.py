"""Inicio según el rol («Para hoy») y «Mi docencia» (evaluación de usabilidad, punto 1)."""
from app.academico import carga, gestiones, oferta
from app.comun import usuarios, vinculos
from tests.conftest import HX, PASS_TEMP, login
from tests.test_vinculos import hoy  # noqa: F401


def _carga(horas, **acts):
    return {"horas": horas, "detalles": {}, "actividades": {k: acts.get(k, 0) for k in vinculos.ACTIVIDADES}}


def _emmy(client):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    return emmy


def test_mi_docencia(client, hoy):
    emmy = _emmy(client)
    # Sin vínculo ni materias: la sección abre en los planes y no hay pestaña «Mi docencia».
    assert client.get("/docencia", follow_redirects=False).headers["location"] == "/docencia/planes"
    assert "Mi docencia" not in client.get("/docencia/planes").text
    por = {g["tipo"]: g for g in gestiones.crear_anio(2026)}
    vinculos.agregar(emmy, "titular", "2015-01-01", carga=_carga(128, docencia=64, investigacion=64))
    oid, _ = oferta.agregar(por["II"]["id"], "MAT-111", "A", "40", 1)
    oferta.asignar(oid, emmy, "titular")
    assert client.get("/docencia", follow_redirects=False).headers["location"] == "/docencia/mia"
    r = client.get("/docencia/mia")
    assert "Mi docencia" in r.text and "MAT-111" in r.text and "128" in r.text and "Investigación" in r.text
    assert "Falta asignar 1 materia" in r.text  # docencia prevista 64, asignada 32
    assert '<progress value="32" max="64"' in r.text  # barra de docencia asignada respecto de la prevista
    assert "Historial de vínculo" in r.text


def test_inicio_de_la_investigadora(client, hoy):
    emmy = _emmy(client)
    r = client.get("/")
    assert "Para hoy" in r.text and "Lo mío" in r.text and "Nada pendiente" in r.text
    assert "Dirección de Carrera" not in r.text and "Dirección del Instituto" not in r.text
    gestiones.crear_anio(2026)
    vinculos.agregar(emmy, "titular", "2015-01-01", carga=_carga(64, docencia=64))
    assert "0 materias · 64 h/mes contratadas" in client.get("/").text


def test_inicio_de_la_direccion_de_carrera(carrera, hoy):
    admin = carrera
    por = {g["tipo"]: g for g in gestiones.crear_anio(2026)}
    oferta.agregar(por["II"]["id"], "MAT-111", "A", "", 1)
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP)["id"]
    vinculos.agregar(alan, "contratado", "2026-08-01", "2026-10-10")        # vence en menos de 30 días
    ramanujan = usuarios.crear("r@test.cl", "Srinivasa", "Ramanujan", PASS_TEMP)["id"]
    vinculos.agregar(ramanujan, "invitado", "2026-03-01", "2026-12-31")     # invitado: sin carga es normal
    r = admin.get("/")
    assert "Dirección de Carrera" in r.text and "1 materia sin docente titular en II-2026" in r.text
    assert "1 vínculo termina en los próximos 30 días" in r.text and "Alan Turing (2026-10-10)" in r.text
    assert "1 docente con vínculo vigente sin carga contratada" in r.text  # Alan, no Ramanujan
    assert [x["apellidos"] for x in carga.vigentes_sin_carga()] == ["Turing"]
    assert carga.resumen(ramanujan, por["II"])["avisos"] == []
    # Con el periodo siguiente ya registrado, deja de avisar que vence.
    vinculos.agregar(alan, "contratado", "2026-10-11", "2026-12-31")
    assert carga.contratos_por_vencer(30) == []
    assert "Dirección del Instituto" in r.text  # la cuenta admin también la tiene


def test_semestre_de_referencia(app):
    por = {g["tipo"]: g for g in gestiones.crear_anio(2026)}
    assert carga.semestre_de_referencia("2026-03-01")["id"] == por["I"]["id"]
    assert carga.semestre_de_referencia("2026-07-15")["id"] == por["II"]["id"]  # invierno: el próximo
    assert carga.semestre_de_referencia("2027-02-15")["id"] == por["II"]["id"]  # sin próximo: el último


def test_mi_docencia_requiere_sesion(client):
    assert client.get("/docencia/mia", headers=HX).headers.get("hx-redirect") == "/login"
