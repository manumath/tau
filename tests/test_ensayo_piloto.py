"""Correcciones del ensayo sintético del piloto (PLAN §72, etapa 11): cifras de cohortes y vacantes, privacidad de las
encuestas por pregunta, evidencias que sube el responsable de una actividad, el pie con la privacidad y fechas legibles."""
import re

from app.calidad import actividades_mejora as am
from app.calidad import evidencias, indicadores
from app.comun import usuarios
from app.comun.db import get_db
from app.estudiantil import cohortes, encuestas, importar
from app.estudiantil import rendimiento as rd
from tests.conftest import HX, PASS_ADMIN, login
from tests.test_actividades_mejora import _accion, _actividad, _gente
from tests.test_encuestas import _eid, _respuestas_validas, _tokens, datos  # noqa: F401
from tests.test_evidencias_calidad import PDF

ISO = re.compile(r"\b20\d\d-\d\d-\d\d\b")


# --- Cohortes y vacantes ------------------------------------------------------------------------------------------------

def _alumno(estado, ultimo=None):
    return {"ingreso": cohortes.ordinal(2022, "II"), "estado": estado, "ultimo": ultimo, "motivo_retiro": None,
            "egreso": None, "titulacion": None}


def test_un_congelado_que_no_volvio_no_cuenta_como_cursante(app):
    actual = cohortes.ordinal(*cohortes.ciclo_actual())
    grupo = [_alumno("cursando"), _alumno("congelado", ultimo=cohortes.ordinal(2023, "II")),   # ya es desertor
             _alumno("congelado", ultimo=actual)]                                             # todavía puede volver
    c = cohortes.resumen([cohortes.ordinal(2022, "II")], grupo)[0]
    assert c["n"] == 3 and c["desertores"] == 1 and c["cursan"] == 2
    assert c["cursan"] + c["desertores"] == c["n"]                     # cada estudiante en una sola situación


def test_admision_sin_cohorte_cargada_no_es_cobertura_cero(app):
    filas, errores = importar.leer(b"ru,nombres,apellidos,cohorte,estado\n1000001,Ana,Uno,2025-I,cursando\n")
    assert errores == []
    importar.aplicar(filas, None)
    rd.guardar_vacantes({"anio": "2025", "ciclo": "I", "vacantes": "4"}, None)
    rd.guardar_vacantes({"anio": "2025", "ciclo": "II", "vacantes": "60", "postulantes": "70"}, None)
    v = rd.vacantes_de(2025, "II")
    assert v["admitidos"] is None and v["cobertura"] is None              # «sin cohorte», no 0 %
    r = indicadores.CALCULOS["cobertura_vacantes"].fn(None, 2025)
    assert r.valor == 25.0 and r.n == 4                                  # solo la admisión con su cohorte
    rd.guardar_vacantes({"anio": "2026", "ciclo": "I", "vacantes": "10"}, None)
    r = indicadores.CALCULOS["cobertura_vacantes"].fn(None, 2026)
    assert r.valor is None and "Faltan las cohortes" in r.detalle


# --- Encuestas anónimas: también por pregunta -----------------------------------------------------------------------------

def test_pregunta_anonima_con_pocas_respuestas_no_se_muestra(datos):  # noqa: F811
    eid = _eid()
    q = next(q for q in encuestas.preguntas(eid) if q["tipo"] == "si_no")
    get_db().execute("UPDATE pregunta SET obligatoria = 0 WHERE id = ?", [q["id"]])
    encuestas.abrir(eid, None)
    for i, t in enumerate(_tokens(eid)[:6]):
        respuestas = _respuestas_validas(eid)
        if i >= 2:
            respuestas.pop(q["id"])                                       # solo 2 personas la responden
        assert encuestas.responder(t, respuestas) == []
    r = encuestas.resultados(eid)
    assert not r["oculto"] and r["n"] == 6
    p = next(p for p in r["preguntas"] if p["pregunta"]["id"] == q["id"])
    assert p["oculta"] and p["n"] == 2 and p["conteo"] == {}
    assert q["texto"] not in encuestas.csv_resultados(eid)
    otra = next(p for p in r["preguntas"] if p["pregunta"]["tipo"] == "escala")
    assert not otra.get("oculta") and otra["n"] == 6


# --- Evidencias del responsable de una actividad (decisión del 15-nov-2026, opción A) ---------------------------------------

def _responsable_con_sesion(client):
    d, r = _gente()
    a = _accion(d["id"])
    t = _actividad(a, r["id"])
    otra = evidencias.crear(a["marco_id"], "enlace", {"titulo": "Reglamento ajeno", "descripcion": None, "fecha": None,
                                                     "vigente_hasta": None, "url": "https://ejemplo.test/r",
                                                     "criterios": []}, d["id"])
    clave = "Clave-resp-12345"
    usuarios.cambiar_password(r["id"], clave, temporal=False)
    login(client, "inv@test.cl", clave)
    return t, otra


def test_el_responsable_adjunta_la_evidencia_en_su_avance(client):
    """Opción A (decisión del 15-nov-2026): el archivo va en el mismo formulario del avance y el sistema lo registra en el
    repositorio, ligado a la actividad."""
    t, otra = _responsable_con_sesion(client)
    url = f"/calidad/mejora/actividades/{t['id']}"
    assert client.get("/calidad/evidencias").status_code == 403          # el repositorio sigue cerrado para él
    pagina = client.get(url).text
    assert 'name="archivo"' in pagina and 'hx-encoding="multipart/form-data"' in pagina
    assert "Reglamento ajeno" not in pagina                              # no le ofrece evidencias ajenas
    # Un archivo que no es de los formatos admitidos: error, y no se registra nada.
    r = client.post(f"{url}/avances", headers=HX, data={"texto": "Segundo taller", "porcentaje": "50"},
                    files={"archivo": ("notas.txt", b"hola", "text/plain")})
    assert "Evidencia: Solo se admiten archivos" in r.text and evidencias.de_actividad(t["id"]) == []
    client.post(f"{url}/avances", headers=HX, data={"texto": "Segundo taller con 40 estudiantes", "porcentaje": "50",
                                                    "volver": "/docencia/pendientes"},
                files={"archivo": ("asistencia.pdf", PDF, "application/pdf")})
    [e] = evidencias.de_actividad(t["id"])
    assert e["actividad_id"] == t["id"] and e["criterios"] == [] and e["nombre_archivo"] == "asistencia.pdf"
    assert "Segundo taller con 40 estudiantes" in e["titulo"] and "4.1" in e["titulo"]
    av = am.obtener(t["id"])["lista_avances"][0]
    assert av["evidencia_id"] == e["id"] and av["porcentaje"] == 50
    # Ve su evidencia y la descarga, pero no la ajena ni puede editarla.
    assert client.get(f"/calidad/evidencias/{e['id']}").status_code == 200
    assert client.get(f"/calidad/evidencias/{e['id']}/archivo").status_code == 200
    assert client.get(f"/calidad/evidencias/{otra}").status_code == 403
    assert client.get(f"/calidad/evidencias/{e['id']}/editar", headers=HX).status_code == 403
    # En el avance siguiente puede volver a elegir la suya, nunca una ajena escribiendo su número.
    assert "Segundo taller con 40 estudiantes" in client.get(url).text
    r = client.post(f"{url}/avances", headers=HX, data={"texto": "x", "evidencia_id": str(otra)})
    assert "Elija una evidencia de la lista." in r.text


def test_otra_persona_no_adjunta_evidencias_a_una_actividad_ajena(app, client):
    d, r = _gente()
    t = _actividad(_accion(d["id"]), r["id"])
    usuarios.crear("otro@test.cl", "Otro", "Docente", "Clave-otro-12345", debe_cambiar_pass=False)
    login(client, "otro@test.cl", "Clave-otro-12345")
    r = client.post(f"/calidad/mejora/actividades/{t['id']}/avances", headers=HX, data={"texto": "x"},
                    files={"archivo": ("a.pdf", PDF, "application/pdf")})
    assert r.status_code == 403 and evidencias.de_actividad(t["id"]) == []


def test_la_direccion_elige_del_repositorio_entero(carrera):
    d, r = _gente()
    a = _accion(d["id"])
    t = _actividad(a, r["id"])
    evidencias.crear(a["marco_id"], "enlace", {"titulo": "Acta del consejo", "descripcion": None, "fecha": None,
                                             "vigente_hasta": None, "url": "https://ejemplo.test/a", "criterios": []},
                     d["id"])
    assert "Acta del consejo" in carrera.get(f"/calidad/mejora/actividades/{t['id']}").text


# --- Pie de página y fechas -------------------------------------------------------------------------------------------------

def test_cada_pagina_enlaza_la_privacidad(client):
    login(client, "admin@test.cl", PASS_ADMIN)
    assert 'href="/publico/privacidad"' in client.get("/").text


def test_aviso_de_la_evaluacion_docente_sin_fechas_iso(app):
    from tests.test_docente import _evaluacion_abierta
    doc, _oid, _g, _eid_ = _evaluacion_abierta()
    aviso = get_db().q("SELECT * FROM notificacion WHERE usuario_id = ? AND asunto LIKE 'Evaluación docente%'", [doc["id"]])[0]
    assert "Estará abierta del" in aviso["texto"] and not ISO.search(aviso["texto"])
