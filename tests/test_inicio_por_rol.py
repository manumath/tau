"""Inicio según el rol (la bandeja «Pendientes», PLAN §54) y «Mi docencia» (evaluación de usabilidad, punto 1)."""
from app.academico import carga, gestiones, oferta
from app.comun import usuarios, vinculos
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login
from tests.test_vinculos import hoy  # noqa: F401
from tests.test_tutoria_directorio import mundo  # noqa: F401


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
    assert "Pendientes" in r.text and "Todo al día" in r.text and "Lo mío" not in r.text   # sin pendientes
    assert "Dirección de Carrera" not in r.text and "Dirección del Instituto" not in r.text
    assert "Mi producción" in r.text and 'href="/perfil"' in r.text                        # sus cifras, con enlace
    assert "Accesos" not in r.text                                                           # los da el menú
    gestiones.crear_anio(2026)
    vinculos.agregar(emmy, "titular", "2015-01-01", carga=_carga(64, docencia=64))
    r = client.get("/").text
    assert "Lo mío" in r and "0 materias · 64 h/mes contratadas" in r and "Todo al día" not in r


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
    assert "Dirección del Instituto" not in r.text   # la cuenta admin la tiene, pero sin pendientes no se muestra


def test_semestre_de_referencia(app):
    por = {g["tipo"]: g for g in gestiones.crear_anio(2026)}
    assert carga.semestre_de_referencia("2026-03-01")["id"] == por["I"]["id"]
    assert carga.semestre_de_referencia("2026-07-15")["id"] == por["II"]["id"]  # invierno: el próximo
    assert carga.semestre_de_referencia("2027-02-15")["id"] == por["II"]["id"]  # sin próximo: el último


def test_mi_docencia_requiere_sesion(client):
    assert client.get("/docencia/mia", headers=HX).headers.get("hx-redirect") == "/login"


def test_pendientes_de_estudiantes_y_fichas(app, mundo):  # noqa: F811
    """Tutor: tutorados sin reuniones. Dirección de Carrera: actividad estudiantil por verificar. Gestión de datos:
    académicos sin grado (PLAN §54)."""
    from datetime import date
    from app.estudiantil import actividad, tutoria
    from app.comun import permisos, unidades
    from tests.test_tutoria_directorio import _cliente, _externo, _uid
    ana, beto = _externo("8000001"), _externo("8000002")
    tutoria.asignar(ana, _uid("tutor1@test.cl"), None)
    tutoria.asignar(beto, _uid("tutor1@test.cl"), None)
    tutoria.registrar(beto, _uid("tutor1@test.cl"), {"fecha": date.today().isoformat(), "tema": "academico"})
    r = _cliente(app, "tutor1@test.cl").get("/").text
    assert "1 tutorado sin reuniones registradas" in r and "Ana Alumna" in r and "Beto" not in r.split("Estudiantes")[-1]
    actividad.crear(ana, {"tipo": "olimpiada", "titulo": "Olimpiada", "fecha_inicio": date.today().isoformat()})
    permisos.asignar(_uid("admin@test.cl"), "direccion_carrera", unidades.id_de("CMAT"))
    assert "1 actividad estudiantil por verificar" in _cliente(app, "admin@test.cl", PASS_ADMIN).get("/").text
    usuarios.crear("gema@test.cl", "Gema", "Gestión", CLAVE_GEMA, debe_cambiar_pass=False, es_investigador=False)
    permisos.asignar(_uid("gema@test.cl"), "gestion_datos", unidades.id_de("CMAT"))
    r = _cliente(app, "gema@test.cl", CLAVE_GEMA).get("/").text
    assert "Fichas académicas" in r and "sin grado registrado" in r and "Todo al día" not in r


CLAVE_GEMA = "Clave-gestion-1"
