"""Ficha de docente y acciones masivas de la Dirección de Carrera (punto 5 de la evaluación, PLAN.md §32)."""
import pytest

from app.academico import carga, gestiones, oferta
from app.comun import permisos, unidades, usuarios, vinculos
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login
from tests.test_vinculos import hoy  # noqa: F401


def _carga(horas, **acts):
    return {"horas": horas, "detalles": {}, "actividades": {k: acts.get(k, 0) for k in vinculos.ACTIVIDADES}}


@pytest.fixture
def base(app, hoy):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP, debe_cambiar_pass=False)["id"]
    vinculos.agregar(emmy, "titular", "2015-01-01", carga=_carga(128, docencia=64, investigacion=64))
    vinculos.agregar(alan, "contratado", "2026-02-01", "2026-06-30", carga=_carga(64, docencia=32, extension=32))
    g25 = {g["tipo"]: g for g in gestiones.crear_anio(2025)}
    g26 = {g["tipo"]: g for g in gestiones.crear_anio(2026)}
    return {"emmy": emmy, "alan": alan, "g25": g25, "g26": g26}


def test_copiar_la_oferta_del_anio_anterior(base):
    emmy, g25, g26 = base["emmy"], base["g25"], base["g26"]
    for sigla in ("MAT-111", "MAT-112"):
        oid, _ = oferta.agregar(g25["II"]["id"], sigla, "A", "40", 1)
        oferta.asignar(oid, emmy, "titular")
    oferta.agregar(g26["II"]["id"], "MAT-111", "A", "", 1)  # ya está: no se duplica
    assert oferta.mismo_semestre_anio_anterior(g26["II"])["id"] == g25["II"]["id"]
    r = oferta.copiar(g25["II"], g26["II"], True, 1)
    assert (r["paralelos"], r["docentes"]) == (1, 2)
    nueva = {o["sigla"]: o for o in oferta.listar(g26["II"]["id"])}
    assert nueva["MAT-112"]["inscritos"] is None and nueva["MAT-112"]["docentes"][0]["usuario_id"] == emmy
    assert oferta.copiar(g25["II"], g26["II"], True, 1) == {"paralelos": 0, "docentes": 0, "avisos": []}


def test_fijar_titular_reemplaza_y_respeta_la_temporada(base):
    emmy, alan, g26 = base["emmy"], base["alan"], base["g26"]
    oid, _ = oferta.agregar(g26["I"]["id"], "MAT-111", "A", "", 1)
    assert oferta.fijar_titular(oid, alan) == []
    oferta.asignar(oid, emmy, "auxiliar")
    assert oferta.fijar_titular(oid, emmy) == []  # pasa de auxiliar a titular; Alan sale
    assert [(d["usuario_id"], d["rol"]) for d in oferta.docentes(oid)] == [(emmy, "titular")]
    assert oferta.fijar_titular(oid, None) == [] and oferta.titular_de(oid) is None
    ver, _ = oferta.agregar(g26["VER"]["id"], "MAT-278", "A", "", 1)
    assert "titulares" in oferta.fijar_titular(ver, alan)[0]  # verano: solo titulares de la Carrera


def test_renovar_contratos(base):
    alan, g26 = base["alan"], base["g26"]
    assert [v["usuario_id"] for v in carga.candidatos_renovacion(g26["II"])] == [alan]
    vid = carga.candidatos_renovacion(g26["II"])[0]["id"]
    n, errores = carga.renovar([vid], g26["II"]["fecha_inicio"], g26["II"]["fecha_fin"], 1)
    assert (n, errores) == (1, [])
    nuevo = vinculos.listar(alan)[-1]
    assert (nuevo["categoria"], nuevo["fecha_inicio"], nuevo["horas_contratadas"], nuevo["carga_extension"]) == \
        ("contratado", "2026-08-01", 64, 32)
    assert carga.candidatos_renovacion(g26["II"]) == []  # ya renovado
    assert "Indique la fecha de término" in carga.renovar([vid], "2027-02-01", "", 1)[1][0]


def test_pantallas_y_permisos(client, base):
    emmy, alan, g26 = base["emmy"], base["alan"], base["g26"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get(f"/docencia/docentes/{emmy}", follow_redirects=False).headers["location"] == "/docencia/mia"
    assert client.get(f"/docencia/docentes/{alan}").status_code == 403
    assert client.get("/docencia/renovaciones").status_code == 403
    assert client.get(f"/docencia/oferta/{g26['II']['id']}/grilla").status_code == 403
    cmat = unidades.id_de("CMAT")
    permisos.asignar(emmy, "direccion_carrera", cmat)
    r = client.get(f"/docencia/docentes/{alan}")
    assert "Alan Turing" in r.text and "Vínculo y carga" in r.text and "Historial de vínculo" in r.text
    r = client.get(f"/docencia/renovaciones?gestion={g26['II']['id']}")
    assert "Turing, Alan" in r.text and "Renovar los marcados" in r.text
    vid = carga.candidatos_renovacion(g26["II"])[0]["id"]
    r = client.post(f"/docencia/renovaciones/{g26['II']['id']}", headers=HX,
                    data={"vinculo": str(vid), "desde": "2026-08-01", "hasta": "2026-12-31"})
    assert vinculos.vigente(alan, "2026-09-01")["fecha_fin"] == "2026-12-31"
    # Grilla: fijar titulares de varios paralelos a la vez.
    o1, _ = oferta.agregar(g26["II"]["id"], "MAT-111", "A", "", 1)
    o2, _ = oferta.agregar(g26["II"]["id"], "MAT-112", "A", "", 1)
    assert "Guardar la grilla" in client.get(f"/docencia/oferta/{g26['II']['id']}/grilla").text
    client.post(f"/docencia/oferta/{g26['II']['id']}/grilla", headers=HX,
                data={f"titular_{o1}": str(emmy), f"titular_{o2}": str(alan)})
    assert oferta.titular_de(o1)["usuario_id"] == emmy and oferta.titular_de(o2)["usuario_id"] == alan
    # Copiar del año anterior (modal y acción).
    oferta.agregar(base["g25"]["II"]["id"], "MAT-113", "A", "", 1)
    assert "Copiar la oferta de II-2025" in client.get(f"/docencia/oferta/{g26['II']['id']}/copiar", headers=HX).text
    client.post(f"/docencia/oferta/{g26['II']['id']}/copiar", headers=HX, data={"con_docentes": "1"})
    assert "MAT-113" in [o["sigla"] for o in oferta.listar(g26["II"]["id"])]
    acciones = {a["accion"] for a in get_db().q("SELECT accion FROM auditoria")}
    assert {"renovar_contratos", "grilla_docentes", "copiar_oferta"} <= acciones
