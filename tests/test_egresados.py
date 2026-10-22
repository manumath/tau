"""Egresados (PLAN §50, etapa 4): titulación, seguimiento programado a los hitos e indicadores."""
from datetime import date

import pytest
from starlette.testclient import TestClient

from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from app.egresados import egresados
from app.estudiantil import cohortes, encuestas, importar
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login
from tests.test_cohortes import ENCABEZADO

HOY = date(2026, 10, 21)


def _hace(meses: int) -> str:
    return egresados.sumar_meses(HOY.isoformat(), -meses).isoformat()


def _cargar(*filas):
    filas, errores = importar.leer((ENCABEZADO + "\n".join(filas) + "\n").encode())
    assert errores == [] and not [f["errores"] for f in filas if f["errores"]], [f["errores"] for f in filas]
    importar.aplicar(filas, None)


def _titulado(ru, nombre, meses, email=True, cohorte="2018-I"):
    f = _hace(meses)
    return (f"{ru},{nombre},Egresada,{nombre.lower()}@correo.bo" if email else f"{ru},{nombre},Egresada,") + \
        f",mujer,,{cohorte},,,,,,titulado,,{f},{f},tesis,"


@pytest.fixture
def grupo(app):
    """A: titulada hace 7 meses (hito de 6 meses); B: hace 14 (1 año; el de 6 meses se omite); C: hace 3 (ninguno);
    D: hace 70 (5 años; se omiten 3); E: hace 8 meses, sin correo."""
    _cargar(_titulado("9000001", "Ana", 7), _titulado("9000002", "Bea", 14), _titulado("9000003", "Cora", 3),
            _titulado("9000004", "Dina", 70, cohorte="2014-I"), _titulado("9000005", "Eva", 8, email=False))


def _responder(token, **por_clave):
    inv = get_db().q("SELECT * FROM invitacion_encuesta WHERE token = ?", [token])[0]
    crudo = {}
    for q in encuestas.preguntas(inv["encuesta_id"]):
        v = por_clave.get(q["clave"])
        crudo[q["id"]] = [v] if v else {"escala": ["4"], "opcion": [q["opciones"][0] if q["opciones"] else ""],
                                       "texto": ["Madrid, España"]}[q["tipo"]]
    assert encuestas.responder(token, crudo) == []


def _token_de(ru):
    return get_db().q("""SELECT inv.token FROM invitacion_encuesta inv JOIN estudiante es ON es.externo_id = inv.externo_id
                         WHERE es.registro_universitario = ?""", [ru])[0]["token"]


# --- Hitos ---------------------------------------------------------------------------------------------------

def test_fechas_de_los_hitos():
    assert egresados.sumar_meses("2025-08-31", 6).isoformat() == "2026-02-28"           # fin de mes
    assert egresados.sumar_meses("2024-02-29", 12).isoformat() == "2025-02-28"
    assert egresados.fecha_hito("2020-03-15", "5a").isoformat() == "2025-03-15"
    assert egresados.hitos_vencidos("2026-04-21", HOY) == ["6m"]
    assert egresados.hitos_vencidos("2026-04-22", HOY) == []
    assert egresados.hitos_vencidos("2021-10-21", HOY) == ["6m", "1a", "3a", "5a"]


# --- Titulación ----------------------------------------------------------------------------------------------------

def test_titular_pasa_al_estudiante_a_egresado(app):
    _cargar("9000010,Lia,Cursa,lia@correo.bo,mujer,,2021-I,,,,,,cursando,,,,,")
    est = get_db().q("SELECT id FROM estudiante")[0]["id"]
    assert [c["id"] for c in egresados.candidatos_titulacion()] == [est]
    assert egresados.titular(est, {"fecha_titulacion": "2099-01-01"}, None) == ["La fecha de titulación no puede ser futura."]
    assert egresados.titular(est, {"fecha_titulacion": "2019-01-01"}, None) == ["El egreso es anterior al ingreso."]
    assert egresados.titular(est, {"fecha_titulacion": "2025-12-10", "fecha_egreso": "2025-12-20"}, None) == [
        "El egreso no puede ser posterior a la titulación."]
    assert egresados.titular(est, {"fecha_titulacion": "2025-12-10", "modalidad": "tesis"}, None) == []
    e = get_db().q("SELECT * FROM estudiante WHERE id = ?", [est])[0]
    assert (e["estado"], e["titulado"], e["fecha_egreso"], e["ultimo_anio"], e["ultimo_ciclo"], e["hasta"]) == (
        "titulado", 1, "2025-12-10", 2025, "II", 2025)
    assert [g["nombres"] for g in egresados.titulados()] == ["Lia"] and egresados.candidatos_titulacion() == []
    assert egresados.titular(est, {"fecha_titulacion": "2025-12-10"}, None)[0].startswith("Ese estudiante no se puede titular")
    ciclo = {c["texto"]: c for c in cohortes.resumen(cohortes.cohortes_hasta((2026, "II"), 20))}["2021-I"]
    assert ciclo["estados"]["titulado"] == 1                                            # también cuenta en el tablero


# --- Seguimiento ---------------------------------------------------------------------------------------------------

def test_activar_crea_y_abre_una_encuesta_por_hito(grupo):
    assert egresados.hitos_sin_encuesta() == list(egresados.HITOS)
    assert egresados.activar_seguimiento(None) == 4 and egresados.activar_seguimiento(None) == 0
    for h in egresados.HITOS:
        e = egresados.encuesta_de_hito(h)
        assert e["estado"] == "abierta" and e["anonima"] == 0 and e["publico"] == "egresados"
        assert egresados.HITOS[h][0] in e["titulo"]
        assert get_db().q("SELECT COUNT(*) n FROM invitacion_encuesta WHERE encuesta_id = ?", [e["id"]])[0]["n"] == 0
    claves = {q["clave"] for q in encuestas.preguntas(egresados.encuesta_de_hito("1a")["id"])}
    assert {"situacion", "posgrado", "utilidad", "satisfaccion"} <= claves
    # El hito no se cambia al editar.
    e = egresados.encuesta_de_hito("1a")
    assert encuestas.actualizar(e["id"], {"titulo": "x"}) == ["Solo se puede editar una encuesta en borrador."]


def test_programar_invita_al_ultimo_hito_y_omite_los_anteriores(grupo, buzon):
    assert egresados.programar(HOY)["invitados"] == 0                    # sin encuestas activas no se invita a nadie
    assert get_db().q("SELECT COUNT(*) n FROM seguimiento_egresado")[0]["n"] == 0
    egresados.activar_seguimiento(None)
    r = egresados.programar(HOY)
    assert r == {"invitados": 3, "omitidos": 4, "sin_correo": 1}          # A (6m), B (1a; omite 6m), D (5a; omite 3)
    assert len(buzon) == 3 and all("/encuesta/" in m.get_content() for m in buzon)
    por_ru = {g["apellidos"] + g["nombres"]: g["seguimiento"] for g in egresados.titulados()}
    assert por_ru["EgresadaAna"] == {"6m": "invitado"}
    assert por_ru["EgresadaBea"] == {"6m": "omitido", "1a": "invitado"}
    assert por_ru["EgresadaDina"] == {"6m": "omitido", "1a": "omitido", "3a": "omitido", "5a": "invitado"}
    assert por_ru["EgresadaCora"] == {} and por_ru["EgresadaEva"] == {}
    assert egresados.programar(HOY) == {"invitados": 0, "omitidos": 0, "sin_correo": 1}      # no se repite


def test_al_cumplir_el_siguiente_hito_se_vuelve_a_invitar(grupo, buzon):
    egresados.activar_seguimiento(None)
    egresados.programar(HOY)
    buzon.clear()
    r = egresados.programar(date(2027, 5, 1))                            # Ana cumple 1 año; Cora, 6 meses
    assert r["invitados"] == 2 and r["sin_correo"] == 1                  # Ana (1 año) y Cora (6 meses); Bea aún no cumple 3
    assert {x["seguimiento"].get("1a") for x in egresados.titulados() if x["nombres"] == "Ana"} == {"invitado"}
    assert {x["seguimiento"].get("6m") for x in egresados.titulados() if x["nombres"] == "Cora"} == {"invitado"}


def test_programar_respeta_el_lote(grupo, buzon):
    egresados.activar_seguimiento(None)
    assert egresados.programar(HOY, lote=2)["invitados"] == 2
    assert egresados.programar(HOY, lote=2)["invitados"] == 1


def test_el_estado_del_seguimiento_y_las_respuestas(grupo):
    egresados.activar_seguimiento(None)
    antes = {e["hito"]: e for e in egresados.estado_seguimiento(HOY)}
    assert (antes["6m"]["pendientes"], antes["1a"]["pendientes"], antes["5a"]["pendientes"], antes["3a"]["pendientes"]) == (1, 1, 1, 0)
    egresados.programar(HOY)
    _responder(_token_de("9000001"), situacion="Trabajo en mi área")
    d = {e["hito"]: e for e in egresados.estado_seguimiento(HOY)}
    assert (d["6m"]["invitados"], d["6m"]["respondidos"], d["6m"]["pendientes"]) == (1, 1, 0)
    assert (d["6m"]["omitidos"], d["1a"]["omitidos"], d["3a"]["omitidos"]) == (2, 1, 1)
    ana = next(g for g in egresados.titulados() if g["nombres"] == "Ana")
    assert ana["seguimiento"] == {"6m": "respondido"}


def test_cerrada_la_encuesta_del_hito_no_se_invita(grupo):
    egresados.activar_seguimiento(None)
    encuestas.cerrar(egresados.encuesta_de_hito("6m")["id"], None)
    assert egresados.programar(HOY)["invitados"] == 2 and egresados.hitos_sin_encuesta() == ["6m"]


# --- Indicadores -----------------------------------------------------------------------------------------------------

def test_indicadores_por_trienio_con_su_n(grupo):
    egresados.activar_seguimiento(None)
    egresados.programar(HOY)
    _responder(_token_de("9000001"), situacion="Trabajo en mi área", posgrado="No", utilidad="5", satisfaccion="4")
    _responder(_token_de("9000002"), situacion="Busco trabajo", posgrado="Sí, en Bolivia", utilidad="3", satisfaccion="2")
    _responder(_token_de("9000004"), situacion="Estudio un posgrado", posgrado="Sí, en el extranjero", utilidad="4",
               satisfaccion="3")
    ind = egresados.indicadores(HOY)
    assert ind["total"] == 5 and ind["respondieron"] == 3
    t = {(x["desde"], x["hasta"]): x for x in ind["trienios"]}
    reciente = t[(2024, 2026)]                                        # Ana (7 m), Bea (14 m), Cora (3 m), Eva (8 m)
    assert reciente["titulados"] == 4 and reciente["respondieron"] == 2 and reciente["n_situacion"] == 2
    assert reciente["empleo"] == 0.5 and reciente["en_el_area"] == 0.5 and reciente["posgrado"] == 0.5
    assert reciente["utilidad"] == 4 and reciente["satisfaccion"] == 3
    antiguo = t[(2018, 2020)]                                         # Dina (70 m: abril de 2020)
    assert antiguo["titulados"] == 1 and antiguo["empleo"] == 0 and antiguo["posgrado"] == 1
    assert ind["modalidades"] == {"tesis": 5}
    # Dina: cohorte 2014-I; se tituló hace 70 meses (diciembre de 2020, ciclo 2020-II): 13 ciclos = 6,5 años.
    assert antiguo["anios_medios"] == 6.5


def test_la_ultima_respuesta_de_cada_egresado_es_la_que_cuenta(grupo):
    egresados.activar_seguimiento(None)
    egresados.programar(HOY)
    _responder(_token_de("9000001"), situacion="Busco trabajo", posgrado="No")
    egresados.programar(date(2027, 5, 1))                              # Ana cumple 1 año y responde otra vez
    inv = get_db().q("""SELECT inv.token FROM invitacion_encuesta inv JOIN encuesta e ON e.id = inv.encuesta_id
                        JOIN estudiante es ON es.externo_id = inv.externo_id
                        WHERE es.registro_universitario = '9000001' AND e.hito = '1a'""")[0]["token"]
    _responder(inv, situacion="Trabajo en otra área", posgrado="No")
    t = egresados.indicadores(HOY)["trienios"][0]
    assert t["n_situacion"] == 1 and t["empleo"] == 1.0                  # una persona, su respuesta más reciente


# --- Pantallas y permisos ------------------------------------------------------------------------------------------

@pytest.fixture
def direccion(app, grupo):
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    c = TestClient(app)
    login(c, "admin@test.cl", PASS_ADMIN)
    return c


def test_pantalla_y_acciones_de_la_direccion(direccion, buzon):
    r = direccion.get("/docencia/egresados")
    assert r.status_code == 200 and "Egresados titulados (5)" in r.text and "Activar el seguimiento" in r.text
    assert 'href="/docencia/egresados"' in r.text
    direccion.post("/docencia/egresados/seguimiento/activar", headers=HX)
    assert egresados.hitos_sin_encuesta() == []
    r = direccion.get("/docencia/egresados")
    assert "Activar el seguimiento" not in r.text and "Invitar ahora a quienes corresponde (3)" in r.text
    direccion.post("/docencia/egresados/seguimiento/invitar", headers=HX)
    assert len(buzon) == 3
    r = direccion.get("/docencia/egresados")
    assert "Invitado(a)" in r.text and "Omitido" in r.text and "Invitar ahora" not in r.text


def test_registrar_titulacion_desde_la_pantalla(direccion):
    _cargar("9000020,Lia,Cursa,lia@correo.bo,mujer,,2021-I,,,,,,cursando,,,,,")
    r = direccion.get("/docencia/egresados/titular", headers=HX)
    assert "Cursa, Lia" in r.text
    est = get_db().q("SELECT id FROM estudiante WHERE registro_universitario = '9000020'")[0]["id"]
    r = direccion.post("/docencia/egresados/titular", headers=HX, data={"estudiante_id": str(est), "fecha_titulacion": "2099-01-01"})
    assert "no puede ser futura" in r.text
    r = direccion.post("/docencia/egresados/titular", headers=HX, data={"estudiante_id": str(est), "fecha_titulacion": "2026-01-10",
                                                                        "modalidad": "excelencia"})
    assert r.headers["hx-redirect"] == "/docencia/egresados"
    assert "Cursa, Lia" not in direccion.get("/docencia/egresados/titular", headers=HX).text
    assert get_db().q("SELECT COUNT(*) n FROM auditoria WHERE accion = 'titular_estudiante'")[0]["n"] == 1


def test_el_comite_ve_indicadores_pero_no_la_lista_ni_gestiona(app, grupo):
    c = usuarios.crear("comite@test.cl", "Comité", "Prueba", "Clave-roles-1", debe_cambiar_pass=False, es_investigador=False)
    permisos.asignar(c["id"], "comite_acreditacion", unidades.id_de("UMSA"))
    cl = TestClient(app)
    login(cl, "comite@test.cl", "Clave-roles-1")
    r = cl.get("/docencia/egresados")
    assert r.status_code == 200 and "Indicadores por trienio" in r.text
    assert "Egresado" in r.text and "Egresada, Ana" not in r.text and "Registrar titulación" not in r.text
    assert "Activar el seguimiento" not in r.text
    for ruta in ("/docencia/egresados/seguimiento/activar", "/docencia/egresados/seguimiento/invitar"):
        assert cl.post(ruta, headers=HX).status_code == 403
    assert cl.get("/docencia/egresados/titular", headers=HX).status_code == 403
    assert egresados.hitos_sin_encuesta() == list(egresados.HITOS)


def test_un_investigador_no_entra(app, grupo):
    usuarios.cambiar_password(usuarios.por_email("inv@test.cl")["id"], PASS_TEMP, temporal=False)
    c = TestClient(app)
    login(c, "inv@test.cl", PASS_TEMP)
    assert c.get("/docencia/egresados").status_code == 403
