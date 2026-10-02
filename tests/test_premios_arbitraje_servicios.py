"""Premios, arbitraje de artículos y prestación de servicios: registro como actividades y su lugar
en el anexo de I+D+i y en la Guía de Antecedentes (PLAN §40)."""
import io

from openpyxl import load_workbook

from app.acreditacion import anexo, guia_antecedentes as guia
from app.comun import personas, usuarios, vinculos
from app.comun.db import get_db
from app.investigacion import actividades, revistas
from tests.conftest import HX
from tests.test_actividades import inv  # noqa: F401  (fixture de los tests de esta página)


def _tipo(nombre):
    return str(get_db().q("SELECT id FROM tipo_actividad WHERE nombre = ?", [nombre])[0]["id"])


def _form(uid, tipo, **extra):
    base = dict(tipo_id=_tipo(tipo), titulo="Registro", fecha_inicio="2026-05-10", modalidad="presencial",
                ambito="internacional", participante=[f"i:{uid}"], rol=["expositor"])
    return {**base, **extra}


def _ultima(uid):
    return actividades.obtener(actividades.de_investigador(uid)[0]["id"])


def test_arbitraje_por_revista_y_anio(inv):  # noqa: F811
    revistas.crear({"titulo": "Journal of Algebra", "pais": "Estados Unidos"}, inv.uid, verificada=True)
    datos = _form(inv.uid, actividades.ARBITRAJE, titulo="Arbitraje", institucion="journal of algebra", anio="2025",
                  cantidad="3")
    r = inv.post("/actividades", headers=HX, data=datos)
    assert "Indique quién es revisor(a)" in r.text                     # el rol que corresponde al tipo
    assert "Indique cuántos artículos" in inv.post("/actividades", headers=HX,
                                                    data={**datos, "rol": ["revisor"], "cantidad": ""}).text
    inv.post("/actividades", headers=HX, data={**datos, "rol": ["revisor"]})
    a = _ultima(inv.uid)
    assert (a["fecha_inicio"], a["fecha_fin"], a["cantidad"]) == ("2025-01-01", "2025-12-31", 3)
    assert a["revista_id"] and actividades.fechas_texto(a) == "2025"   # del catálogo (sin distinguir mayúsculas)
    ficha = inv.get(f"/actividades/{a['id']}").text
    assert "Artículos arbitrados" in ficha and "En el catálogo de revistas" in ficha


def test_servicio_con_montos(inv):  # noqa: F811
    datos = _form(inv.uid, actividades.SERVICIO, titulo="Curso de estadística para el INE",
                  institucion="Instituto Nacional de Estadística", rol=["responsable"], monto="15 000", moneda="BOB",
                  financiamiento="externo", ingresos="3,5")
    assert "números enteros" in inv.post("/actividades", headers=HX, data=datos).text
    assert "Indique la moneda" in inv.post("/actividades", headers=HX,
                                           data={**datos, "ingresos": "3500", "moneda": ""}).text
    inv.post("/actividades", headers=HX, data={**datos, "ingresos": "3500"})
    a = _ultima(inv.uid)
    assert (a["monto"], a["moneda"], a["financiamiento"], a["ingresos"], a["cantidad"]) == (15000, "BOB", "externo",
                                                                                           3500, None)
    assert "15.000 BOB" in inv.get(f"/actividades/{a['id']}").text


def test_premio(inv):  # noqa: F811
    datos = _form(inv.uid, actividades.PREMIO, titulo="Premio Nacional de Matemática",
                  institucion="Sociedad Boliviana de Matemática", fecha_fin="2026-06-01", rol=["distinguido"],
                  monto="100", cantidad="2")
    inv.post("/actividades", headers=HX, data=datos)
    a = _ultima(inv.uid)
    # Un premio tiene una sola fecha; los campos de otros tipos no se guardan.
    assert (a["fecha_fin"], a["monto"], a["cantidad"]) == (None, None, None)


def test_campos_segun_el_tipo(inv):  # noqa: F811
    r = inv.get(f"/actividades/campos?tipo_id={_tipo(actividades.ARBITRAJE)}&fecha_inicio=2024-03-01&institucion=X")
    assert 'name="anio"' in r.text and "Artículos arbitrados" in r.text and ">Revista<" in r.text
    assert '<option value="2024" selected>' in r.text and 'value="X"' in r.text   # conserva lo escrito
    r = inv.get(f"/actividades/campos?tipo_id={_tipo(actividades.SERVICIO)}")
    assert 'name="monto"' in r.text and "Contraparte" in r.text
    assert "al menos una persona con el rol «Responsable»" in r.text
    r = inv.get(f"/actividades/campos?tipo_id={_tipo('Congreso')}")
    assert 'name="monto"' not in r.text and 'name="fecha_fin"' in r.text


def _registrar(uid, tipo, rol, **campos):
    d = dict(tipo_id=int(_tipo(tipo)), titulo=campos.pop("titulo", tipo), fecha_inicio=campos.pop("fecha_inicio"),
             fecha_fin=campos.pop("fecha_fin", None), modalidad="presencial", ambito="internacional", **campos)
    return actividades.guardar(d, [(f"i:{uid}", rol)], uid)


def test_anexo_y_guia(app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    vinculos.agregar(emmy, "titular", "2020-01-01")
    _registrar(emmy, actividades.PREMIO, "distinguido", titulo="Premio Nacional", institucion="SBM",
               fecha_inicio="2025-11-20")
    _registrar(emmy, actividades.ARBITRAJE, "revisor", institucion="Journal of Algebra", cantidad=3,
               fecha_inicio="2025-01-01", fecha_fin="2025-12-31")
    _registrar(emmy, actividades.ARBITRAJE, "revisor", institucion="Annals", cantidad=2,
               fecha_inicio="2025-01-01", fecha_fin="2025-12-31")
    estudiante = personas.crear_externo("Ana", "Quispe", "UMSA", "Bolivia", emmy)["id"]
    get_db().t.estudiante.insert(externo_id=estudiante, nivel="licenciatura", desde=2023)
    aid = _registrar(emmy, actividades.SERVICIO, "responsable", titulo="Curso para el INE", institucion="INE",
                     fecha_inicio="2025-04-01", monto=69600, moneda="BOB", financiamiento="externo", ingresos=6960)
    get_db().t.actividad_participante.insert(actividad_id=aid, orden=1, externo_id=estudiante, rol="asistente")

    a = anexo.anexo(2021, 2025)
    fila = {x["anio"]: x for x in a["anios"]}[2025]
    assert (fila["premios"], fila["arbitrajes"], fila["servicios"]) == (1, 5, 1)   # arbitrajes: artículos (3 + 2)
    d = anexo.detalle("arbitrajes", 2025, "2025-12-31")
    assert d["valor"] == 5 and len(d["registros"]) == 2

    guia_xlsx = load_workbook(io.BytesIO(guia.generar(ultimo=(2025, "II"), tipo_cambio=6.96)))
    acad = guia_xlsx[guia.H["academicos"]]
    r = next(r for r in range(7, 20) if acad[f"C{r}"].value == "Noether")
    assert acad[f"Z{r}"].value == "Premio Nacional, SBM (2025)"
    serv = guia_xlsx[guia.H["servicios"]]
    assert (serv["C8"].value, serv["F8"].value, serv["G8"].value, serv["H8"].value) == ("Curso para el INE", "INE", 1, 1)
    assert (serv["N8"].value, serv["O8"].value, serv["Q8"].value) == (None, 10000.0, 1000.0)   # USD, externo


def test_anexo_ya_no_los_da_por_ausentes(client):
    from tests.conftest import PASS_ADMIN, login
    login(client, "admin@test.cl", PASS_ADMIN)
    r = client.get("/informes/acreditacion")
    assert "Premios y distinciones" in r.text and "3.4.3" in r.text and "Prestación de servicios" in r.text
    assert "Premios y distinciones; arbitraje de artículos" not in r.text   # ya no en «Aún no registrado»
