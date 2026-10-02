"""Preparación del semestre: etapas, avance y pantalla para la Dirección de Carrera."""
from datetime import date

from app.academico import gestiones, oferta, preparacion
from app.comun import usuarios, vinculos
from tests.conftest import PASS_TEMP, login
from tests.test_carga import _carga


def _etapas(est):
    return {e["clave"]: e for e in est["etapas"]}


def test_semestre_siguiente(app):
    assert preparacion.semestre_siguiente(date(2026, 10, 1)) == (2027, "I")       # sin gestiones: fechas por omisión
    assert preparacion.semestre_siguiente(date(2026, 5, 10)) == (2026, "II")
    gestiones.crear_anio(2027)
    gestiones.actualizar_fechas(gestiones.por_codigo("I-2027")["id"], "2027-03-01", "2027-07-10")
    assert preparacion.semestre_siguiente(date(2027, 2, 20)) == (2027, "I")       # aún no empieza (marzo)
    assert preparacion.semestres_elegibles(date(2027, 2, 20)) == [(2027, "II"), (2027, "I")]


def test_sin_gestion_solo_se_puede_crear(app):
    est = preparacion.estado(2030, "I")
    e = _etapas(est)
    assert (est["hechas"], est["total"]) == (0, 5)
    assert e["gestion"]["estado"] == "actual" and e["gestion"]["detalle"] == "Crear las gestiones de 2030"
    assert all(e[k]["estado"] == "pendiente" and e[k]["bloqueada"] for k in ("oferta", "contratos", "docentes", "carga"))


def test_avance_del_semestre(app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP)["id"]
    g = {x["tipo"]: x for x in gestiones.crear_anio(2027)}["I"]
    e = _etapas(preparacion.estado(2027, "I"))
    assert e["gestion"]["estado"] == "hecho" and e["oferta"]["estado"] == "actual"
    assert e["docentes"]["bloqueada"] and e["carga"]["bloqueada"]

    # Un contratado cuyo periodo terminó antes del semestre: por renovar.
    assert vinculos.agregar(alan, "contratado", "2026-02-01", "2026-12-31", carga=_carga(64, docencia=64)) == []
    # Emmy, titular con 64 h/mes de docencia (dos materias), y dos paralelos ofertados.
    assert vinculos.agregar(emmy, "titular", "2020-01-01", carga=_carga(64, docencia=64)) == []
    o1, _ = oferta.agregar(g["id"], "MAT-111", "A", "40", 1)
    oferta.agregar(g["id"], "MAT-112", "A", "", 1)
    assert oferta.asignar(o1, emmy, "titular") == []

    est = preparacion.estado(2027, "I")
    e = _etapas(est)
    assert e["oferta"]["estado"] == "hecho" and e["oferta"]["detalle"].startswith("2 paralelos")
    assert e["contratos"]["estado"] == "actual" and e["contratos"]["pendientes"] == ["Turing, Alan (terminó el 2026-12-31)"]
    assert (e["docentes"]["hechos"], e["docentes"]["total"], e["docentes"]["estado"]) == (1, 2, "pendiente")
    assert e["docentes"]["pendientes"][0].startswith("MAT-112")
    assert (e["contratos"]["falta"], e["docentes"]["falta"]) == ("renovar 1 contrato", "asignar titular a 1 paralelo")
    assert (e["carga"]["hechos"], e["carga"]["total"]) == (0, 1)               # Emmy: falta asignar 1 materia
    assert "Falta asignar 1 materia" in e["carga"]["pendientes"][0]
    assert est["hechas"] == 2

    # Se renueva el contrato, se asigna la otra materia y a Alan le asignan dos.
    assert vinculos.agregar(alan, "contratado", "2027-01-01", "2027-12-31", carga=_carga(64, docencia=64)) == []
    o2 = next(x["id"] for x in oferta.listar(g["id"]) if x["sigla"] == "MAT-112")
    assert oferta.asignar(o2, emmy, "titular") == []
    o3, _ = oferta.agregar(g["id"], "MAT-113", "A", "", 1)
    o4, _ = oferta.agregar(g["id"], "MAT-114", "A", "", 1)
    assert oferta.asignar(o3, alan, "titular") == [] and oferta.asignar(o4, alan, "titular") == []
    est = preparacion.estado(2027, "I")
    assert (est["hechas"], est["total"]) == (5, 5)
    assert all(x["estado"] == "hecho" for x in est["etapas"])


def test_pantalla_y_permisos(client, carrera):
    anio, tipo = preparacion.semestre_siguiente()          # el próximo semestre, sea cual sea la fecha de hoy
    gestiones.crear_anio(anio)
    codigo = f"{tipo}-{anio}"
    r = client.get(f"/docencia/preparacion?semestre={codigo}")
    assert r.status_code == 200 and f"Preparación de {codigo}" in r.text and "Preparación del semestre" in r.text
    assert f'aria-label="Etapas de la preparación de {codigo}"' in r.text
    assert 'href="/docencia/renovaciones?gestion=' in r.text   # cada etapa enlaza a donde se resuelve
    # Un semestre que no está entre los elegibles vuelve al próximo.
    assert "Preparación de" in client.get("/docencia/preparacion?semestre=X-1999").text
    # En el inicio, la Dirección de Carrera ve cuánto falta para el próximo semestre.
    assert "Siguiente: cargar la oferta." in client.get("/").text

    client.post("/logout")
    usuarios.cambiar_password(usuarios.por_email("inv@test.cl")["id"], PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/docencia/preparacion").status_code == 403
    assert "Preparación del semestre" not in client.get("/docencia/planes").text   # sin pestaña
