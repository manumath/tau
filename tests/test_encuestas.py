"""Motor de encuestas (PLAN §49, etapa 3): armado, apertura, invitaciones, respuesta con enlace, anonimato y permisos."""
import re

import pytest
from starlette.testclient import TestClient

from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from app.estudiantil import encuestas, importar
from app.estudiantil.plantillas_encuesta import PLANTILLAS
from tests.conftest import HX, PASS_ADMIN, login
from tests.test_cohortes import ENCABEZADO

BASE = "/docencia/encuestas"


def _csv(n=7):
    filas = [f"{9000000 + i},Nombre{i},Apellido{i},e{i}@correo.bo,mujer,,{2022 + i % 2}-I,,,,,,cursando,,,,,"
             for i in range(n)]
    filas.append("9100001,Sin,Correo,,mujer,,2022-I,,,,,,cursando,,,,,")
    filas.append("9100002,Ya,Titulada,titulada@correo.bo,mujer,,2019-I,,,,,,titulado,,2023-07-01,2023-12-01,tesis,")
    return ENCABEZADO + "\n".join(filas) + "\n"


@pytest.fixture
def datos(app):
    filas, errores = importar.leer(_csv().encode())
    assert errores == []
    importar.aplicar(filas, None)


def _uid(email):
    return usuarios.por_email(email)["id"]


@pytest.fixture
def direccion(app, datos):
    permisos.asignar(_uid("admin@test.cl"), "direccion_carrera", unidades.id_de("CMAT"))
    c = TestClient(app)
    assert login(c, "admin@test.cl", PASS_ADMIN).headers["hx-redirect"] == "/"
    return c


def _eid(clave="satisfaccion"):
    return encuestas.crear_desde_plantilla(clave, None)


def _tokens(eid):
    return [f["token"] for f in get_db().q("SELECT token FROM invitacion_encuesta WHERE encuesta_id = ? ORDER BY id", [eid])]


def _respuestas_validas(eid, **cambios):
    crudo = {}
    for q in encuestas.preguntas(eid):
        crudo[q["id"]] = {"escala": ["4"], "si_no": ["si"], "opcion": [q["opciones"][0] if q["opciones"] else ""],
                          "multiple": q["opciones"][:2], "texto": ["Más laboratorios"]}[q["tipo"]]
    return crudo


# --- Armado ----------------------------------------------------------------------------------------------------

def test_plantillas_son_validas(app):
    for clave, p in PLANTILLAS.items():
        eid = _eid(clave)
        e = encuestas.obtener(eid)
        assert e["estado"] == "borrador" and e["titulo"] == p["titulo"] and bool(e["anonima"]) == p["anonima"]
        assert len(encuestas.preguntas(eid)) == len(p["preguntas"])
    assert encuestas.obtener(_eid("bienestar"))["anonima"] == 1 and encuestas.obtener(_eid("egresados"))["anonima"] == 0


def test_validar_encuesta_y_preguntas(app):
    eid, errores = encuestas.crear({"titulo": "", "tipo": "x", "publico": "y"}, None)
    assert eid is None and len(errores) == 3
    eid, _ = encuestas.crear({"titulo": "Mía", "tipo": "otra", "publico": "estudiantes", "anonima": "1"}, None)
    assert encuestas.agregar_pregunta(eid, {"texto": "¿Color?", "tipo": "opcion", "opciones": "Rojo"}) == [
        "Escriba al menos dos opciones, una por línea."]
    assert encuestas.agregar_pregunta(eid, {"texto": "¿Color?", "tipo": "opcion", "opciones": "Rojo\nAzul",
                                            "obligatoria": "1"}) == []
    assert encuestas.preguntas(eid)[0]["opciones"] == ["Rojo", "Azul"]
    assert encuestas.actualizar(eid, {"titulo": "Mía", "tipo": "otra", "publico": "estudiantes", "cohorte_desde": "2025",
                                      "cohorte_hasta": "2020"}) == ["El año «desde» no puede ser posterior al «hasta»."]


def test_mover_preguntas(app):
    eid = _eid()
    ids = [q["id"] for q in encuestas.preguntas(eid)]
    assert encuestas.mover_pregunta(ids[1], -1) and [q["id"] for q in encuestas.preguntas(eid)][:2] == [ids[1], ids[0]]
    assert not encuestas.mover_pregunta(ids[1], -1)                      # ya es la primera


def test_no_se_abre_sin_preguntas_ni_sin_publico(datos):
    eid, _ = encuestas.crear({"titulo": "Vacía", "tipo": "otra", "publico": "estudiantes"}, None)
    assert encuestas.abrir(eid, None)[2] == ["Agregue al menos una pregunta antes de abrirla."]
    e2 = encuestas.crear_desde_plantilla("satisfaccion", None)
    get_db().execute("UPDATE encuesta SET cohorte_desde = 2010, cohorte_hasta = 2011 WHERE id = ?", [e2])
    assert "No hay a quién invitar" in encuestas.abrir(e2, None)[2][0]


# --- Apertura, envío y respuesta ----------------------------------------------------------------------------------

def test_abrir_invita_a_quien_cursa_y_tiene_correo(datos):
    eid = _eid()
    invitadas, sin_correo, errores = encuestas.abrir(eid, None)
    assert (invitadas, sin_correo, errores) == (7, 1, [])                # la titulada no es público; uno sin correo
    assert encuestas.obtener(eid)["estado"] == "abierta" and len(set(_tokens(eid))) == 7
    assert encuestas.agregar_pregunta(eid, {"texto": "x", "tipo": "texto"}) != []     # ya no se editan las preguntas
    assert encuestas.abrir(eid, None)[2] == ["Solo se puede abrir una encuesta en borrador."]


def test_el_publico_de_egresados_es_quien_egreso_o_se_titulo(datos):
    eid = _eid("egresados")
    assert encuestas.abrir(eid, None)[:2] == (1, 0)
    assert get_db().q("SELECT email FROM invitacion_encuesta")[0]["email"] == "titulada@correo.bo"


def test_filtro_por_cohorte(datos):
    eid = _eid()
    get_db().execute("UPDATE encuesta SET cohorte_desde = 2023, cohorte_hasta = 2023 WHERE id = ?", [eid])
    invitadas, _, _ = encuestas.abrir(eid, None)
    assert invitadas == 3 and {f["grupo"] for f in get_db().q("SELECT grupo FROM invitacion_encuesta")} == {2023}


def test_envio_por_lotes_y_recordatorios(datos, buzon):
    eid = _eid()
    encuestas.abrir(eid, None)
    assert encuestas.enviar(eid, None, lote=3) == {"enviados": 3, "quedan": 4}
    assert encuestas.enviar(eid, None, lote=10) == {"enviados": 4, "quedan": 0}
    assert len(buzon) == 7 and all("/encuesta/" in m.get_content() and "anónima" in m.get_content() for m in buzon)
    assert encuestas.enviar(eid, None) == {"enviados": 0, "quedan": 0}
    # Recordatorio: solo a quien no respondió; no se repite dentro de la semana.
    token = _tokens(eid)[0]
    assert encuestas.responder(token, _respuestas_validas(eid)) == []
    buzon.clear()
    assert encuestas.enviar(eid, None, recordatorio=True)["enviados"] == 6
    assert all("Recordatorio" in m["Subject"] for m in buzon)
    assert encuestas.enviar(eid, None, recordatorio=True)["enviados"] == 0


def test_responder_valida_y_consume_el_enlace(datos):
    eid = _eid()
    encuestas.abrir(eid, None)
    token = _tokens(eid)[0]
    qs = encuestas.preguntas(eid)
    # Falta una obligatoria y una escala fuera de rango.
    crudo = _respuestas_validas(eid)
    crudo.pop(qs[0]["id"])
    crudo[qs[1]["id"]] = ["9"]
    errores = encuestas.responder(token, crudo)
    assert any(qs[0]["texto"] in e for e in errores) and any("no válida" in e for e in errores)
    assert get_db().q("SELECT COUNT(*) n FROM respuesta")[0]["n"] == 0          # no se guardó nada a medias
    assert encuestas.responder(token, _respuestas_validas(eid)) == []
    assert encuestas.responder(token, _respuestas_validas(eid)) == ["Este enlace ya no sirve."]
    assert encuestas.resumen_invitaciones(eid)["respondidas"] == 1


def test_pagina_publica_con_el_enlace(client, datos):
    eid = _eid()
    encuestas.abrir(eid, None)
    token = _tokens(eid)[0]
    r = client.get(f"/encuesta/{token}")
    assert r.status_code == 200 and "Satisfacción estudiantil" in r.text and "anónima" in r.text
    assert client.get(f"/encuesta/{token}").status_code == 200                   # abrirlo no lo gasta
    assert "Enlace no válido" in client.get("/encuesta/inventado").text
    form = {f"p{q['id']}": "4" for q in encuestas.preguntas(eid) if q["tipo"] == "escala"}
    form.update({f"p{q['id']}": "si" for q in encuestas.preguntas(eid) if q["tipo"] == "si_no"})
    form.update({f"p{q['id']}": "Más laboratorios" for q in encuestas.preguntas(eid) if q["tipo"] == "texto"})
    r = client.post(f"/encuesta/{token}", data={**form, f"p{encuestas.preguntas(eid)[0]['id']}": ""})
    assert "Falta responder" in r.text
    r = client.post(f"/encuesta/{token}", data=form)
    assert "¡Gracias!" in r.text
    assert "Enlace no válido" in client.get(f"/encuesta/{token}").text
    assert get_db().q("SELECT token FROM invitacion_encuesta WHERE respondida_en IS NOT NULL")[0]["token"] is None


def test_cerrar_inutiliza_los_enlaces(datos):
    eid = _eid()
    encuestas.abrir(eid, None)
    token = _tokens(eid)[0]
    assert encuestas.cerrar(eid, None)
    assert encuestas.invitacion_vigente(token) is None and all(t is None for t in _tokens(eid))
    assert encuestas.enviar(eid, None) == {"enviados": 0, "quedan": 0}


def test_la_fecha_limite_cierra_el_enlace(datos):
    eid = _eid()
    encuestas.abrir(eid, None)
    token = _tokens(eid)[0]
    get_db().execute("UPDATE encuesta SET cierra_el = '2000-01-01' WHERE id = ?", [eid])
    assert encuestas.invitacion_vigente(token) is None


# --- Anonimato -----------------------------------------------------------------------------------------------------

def test_la_respuesta_anonima_no_se_puede_ligar_a_la_persona(datos):
    eid = _eid()
    encuestas.abrir(eid, None)
    for t in _tokens(eid)[:5]:
        assert encuestas.responder(t, _respuestas_validas(eid)) == []
    assert all(r["invitacion_id"] is None for r in get_db().q("SELECT invitacion_id FROM respuesta"))
    # Solo la fecha (sin hora), en la respuesta y en la invitación: no se pueden cruzar por la hora.
    assert all(len(r["enviada_en"]) == 10 for r in get_db().q("SELECT enviada_en FROM respuesta"))
    assert all(len(r["respondida_en"]) == 10 for r in get_db().q("SELECT respondida_en FROM invitacion_encuesta "
                                                                  "WHERE respondida_en IS NOT NULL"))
    assert encuestas.individuales(eid) == []


def test_no_hay_resultados_anonimos_con_pocas_respuestas(datos):
    eid = _eid()
    encuestas.abrir(eid, None)
    for t in _tokens(eid)[:4]:
        encuestas.responder(t, _respuestas_validas(eid))
    r = encuestas.resultados(eid)
    assert r["oculto"] and r["preguntas"] == [] and r["n"] == 4
    assert encuestas.csv_resultados(eid) is None
    encuestas.responder(_tokens(eid)[4], _respuestas_validas(eid))
    r = encuestas.resultados(eid)
    assert not r["oculto"] and r["n"] == 5 and r["tasa"] == pytest.approx(5 / 7)


def test_resultados_agregados_y_grupos_pequenos_ocultos(datos):
    eid = _eid()
    encuestas.abrir(eid, None)
    # 7 respuestas: cohortes 2022 (4 personas) y 2023 (3 personas). Ninguna llega a 5 por grupo.
    for t in _tokens(eid):
        encuestas.responder(t, _respuestas_validas(eid))
    r = encuestas.resultados(eid)
    escala = next(p for p in r["preguntas"] if p["pregunta"]["tipo"] == "escala")
    assert escala["promedio"] == 4 and escala["conteo"][4] == 7 and escala["por_grupo"] == {}
    texto = next(p for p in r["preguntas"] if p["pregunta"]["tipo"] == "texto")
    assert texto["textos"] == ["Más laboratorios"] * 7
    csv = encuestas.csv_resultados(eid)
    assert csv.startswith("pregunta,tipo,respuesta,n") and "4 (De acuerdo),7" in csv


def test_encuesta_nominal_enlaza_la_respuesta_con_la_persona(datos):
    eid = _eid("egresados")
    encuestas.abrir(eid, None)
    assert encuestas.responder(_tokens(eid)[0], _respuestas_validas(eid)) == []
    r = encuestas.resultados(eid)
    assert not r["oculto"] and r["n"] == 1                                       # nominal: se ve desde la primera
    ind = encuestas.individuales(eid)
    assert len(ind) == 1 and ind[0]["apellidos"] == "Titulada" and ind[0]["respuestas"][0][1]


# --- Pantallas y permisos ------------------------------------------------------------------------------------

def test_flujo_completo_de_la_direccion(direccion, buzon):
    r = direccion.get(BASE)
    assert r.status_code == 200 and "Nueva encuesta" in r.text
    r = direccion.post(BASE, data={"plantilla": "bienestar", "titulo": ""}, headers=HX)
    eid = int(r.headers["hx-redirect"].rsplit("/", 1)[1])
    r = direccion.get(f"{BASE}/{eid}")
    assert "Clima y bienestar estudiantil" in r.text and "se invitará a 7 persona(s)" in r.text and "Abrir la encuesta" in r.text
    r = direccion.post(f"{BASE}/{eid}/preguntas", data={"texto": "¿Algo más?", "tipo": "texto", "obligatoria": ""})
    assert encuestas.preguntas(eid)[-1]["texto"] == "¿Algo más?" and not encuestas.preguntas(eid)[-1]["obligatoria"]
    r = direccion.post(f"{BASE}/{eid}/preguntas", data={"texto": "", "tipo": "texto"})
    assert "Escriba la pregunta" in r.text
    direccion.post(f"{BASE}/{eid}/datos", data={"titulo": "Bienestar 2026", "tipo": "bienestar", "publico": "estudiantes",
                                                 "anonima": "on"})
    assert encuestas.obtener(eid)["titulo"] == "Bienestar 2026"
    direccion.post(f"{BASE}/{eid}/abrir", headers=HX)
    assert encuestas.obtener(eid)["estado"] == "abierta"
    r = direccion.get(f"{BASE}/{eid}")
    assert "0 respuesta(s) de 7 invitada(s)" in r.text and "Enviar invitaciones pendientes (7 de 7)" in r.text
    direccion.post(f"{BASE}/{eid}/enviar", headers=HX)
    assert len(buzon) == 7
    assert "0 respuesta(s)" in direccion.get(f"{BASE}/{eid}/resultados").text
    assert direccion.get(f"{BASE}/{eid}/resultados.csv").status_code == 404           # aún no hay resultados que mostrar
    direccion.post(f"{BASE}/{eid}/cerrar", headers=HX)
    assert encuestas.obtener(eid)["estado"] == "cerrada"
    assert get_db().q("SELECT COUNT(*) n FROM auditoria WHERE accion IN ('abrir_encuesta', 'enviar_encuesta', 'cerrar_encuesta')"
                      )[0]["n"] == 3


def test_resultados_en_pantalla_y_csv(direccion):
    eid = _eid()
    encuestas.abrir(eid, None)
    for t in _tokens(eid)[:5]:
        encuestas.responder(t, _respuestas_validas(eid))
    r = direccion.get(f"{BASE}/{eid}/resultados")
    assert "5 respuesta(s) de 7 invitada(s)" in r.text and "Promedio: 4,00 de 5" in r.text and "Más laboratorios" in r.text
    assert "Respuestas individuales" not in r.text
    csv = direccion.get(f"{BASE}/{eid}/resultados.csv")
    assert csv.status_code == 200 and "4 (De acuerdo),5" in csv.text


def test_solo_se_elimina_un_borrador(direccion):
    eid = _eid()
    direccion.post(f"{BASE}/{eid}/eliminar", headers=HX)
    assert encuestas.obtener(eid) is None
    eid = _eid()
    encuestas.abrir(eid, None)
    direccion.post(f"{BASE}/{eid}/eliminar", headers=HX)
    assert encuestas.obtener(eid) is not None


def test_el_comite_ve_resultados_pero_no_gestiona(app, datos):
    from app.comun import usuarios as u
    comite = u.crear("comite@test.cl", "Comité", "Prueba", "Clave-roles-1", debe_cambiar_pass=False, es_investigador=False)
    permisos.asignar(comite["id"], "comite_acreditacion", unidades.id_de("UMSA"))
    eid = _eid()
    encuestas.abrir(eid, None)
    c = TestClient(app)
    login(c, "comite@test.cl", "Clave-roles-1")
    assert c.get(f"{BASE}/{eid}").status_code == 200
    assert "Abrir la encuesta" not in c.get(f"{BASE}/{eid}").text and "Nueva encuesta" not in c.get(BASE).text
    for ruta in (f"{BASE}/{eid}/enviar", f"{BASE}/{eid}/cerrar", f"{BASE}/{eid}/recordar", f"{BASE}/{eid}/eliminar"):
        assert c.post(ruta, headers=HX).status_code == 403
    assert c.post(BASE, data={"plantilla": "bienestar"}, headers=HX).status_code == 403
    assert encuestas.obtener(eid)["estado"] == "abierta"


def test_otros_roles_no_entran(app, datos):
    eid = _eid()
    c = TestClient(app)
    from tests.conftest import PASS_TEMP
    usuarios.cambiar_password(_uid("inv@test.cl"), PASS_TEMP, temporal=False)
    login(c, "inv@test.cl", PASS_TEMP)
    for ruta in (BASE, f"{BASE}/{eid}", f"{BASE}/{eid}/resultados"):
        assert c.get(ruta).status_code == 403
    assert c.post(f"{BASE}/{eid}/abrir", headers=HX).status_code == 403


def test_el_token_no_aparece_en_el_registro(datos):
    from app.comun.registros import _TOKENS
    assert _TOKENS.sub(r"\1…", "/encuesta/abc123XYZ") == "/encuesta/…"
    assert re.fullmatch(r"[\w\-]{20,}", encuestas.__dict__["secrets"].token_urlsafe(24))
