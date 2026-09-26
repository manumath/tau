"""Catálogo de revistas, etapa R1: ISSN, indexación por año, administración y carga por CSV."""
import base64

import pytest

from app import importar_revistas, revistas
from app.db import get_db
from tests.conftest import HX, PASS_TEMP, login


def _indice(nombre):
    return get_db().q("SELECT id FROM indice WHERE nombre = ?", [nombre])[0]["id"]


@pytest.fixture
def admin_id(app):
    return get_db().q("SELECT id FROM usuario WHERE email = 'admin@test.cl'")[0]["id"]


@pytest.mark.parametrize("texto,esperado", [("0028-0836", "0028-0836"), ("00280836", "0028-0836"),
                                            ("ISSN 2049-3630", "2049-3630"), ("0000-006x", "0000-006X"),
                                            ("", None), (None, None)])
def test_normalizar_issn(texto, esperado):
    assert revistas.normalizar_issn(texto) == esperado


@pytest.mark.parametrize("texto", ["0028-0837", "1234", "abcd-efgh"])
def test_issn_invalido(texto):
    with pytest.raises(ValueError):
        revistas.normalizar_issn(texto)


def test_clasificacion_por_anio(admin_id):
    d, errores = revistas.validar({"titulo": "Revista A", "issn": "0028-0836", "pais": "Bolivia", "arbitrada": "1"})
    assert not errores
    rid = revistas.crear(d, admin_id)
    assert revistas.clasificacion(rid, 2024) is None  # pendiente: rige lo declarado
    revistas.verificar(rid, admin_id)
    assert revistas.agregar_indexacion(rid, {"indice_id": _indice("Scopus"), "desde": "2020", "hasta": "2023",
                                             "fuente": "Lista de Scopus"}, admin_id) == []
    assert revistas.agregar_indexacion(rid, {"indice_id": _indice("Latindex Catálogo"), "desde": "2015"}, admin_id) == []
    assert "Se superpone" in revistas.agregar_indexacion(rid, {"indice_id": _indice("Scopus"), "desde": "2022"}, admin_id)[0]
    c = revistas.clasificacion(rid, 2021)
    assert c["revision"] == "indexado" and [x["indice"] for x in c["indices"]] == ["Scopus", "Latindex Catálogo"]
    assert c["nacional"]
    # 2024: ya no está en Scopus; Latindex no cuenta como indexado → arbitrada.
    assert revistas.clasificacion(rid, 2024)["revision"] == "arbitrado"
    revistas.actualizar(rid, {"arbitrada": 0})
    assert revistas.clasificacion(rid, 2024)["revision"] == "sin_arbitraje"


def test_validaciones(admin_id):
    rid = revistas.crear(revistas.validar({"titulo": "A", "issn": "0028-0836"})[0], admin_id)
    _, errores = revistas.validar({"titulo": "", "issn": "0028-0836", "url": "ftp://x"})
    assert any("obligatorio" in e for e in errores) and any("Ya existe" in e for e in errores)
    assert any("http" in e for e in errores)
    assert revistas.validar({"titulo": "A", "issn": "0028-0836"}, rid)[1] == []  # la misma revista
    _, errores = revistas.validar_indexacion({"indice_id": "", "desde": "20", "hasta": "1900", "cuartil": "Q7"})
    assert len(errores) == 3


def test_administracion(admin):
    r = admin.post("/admin/revistas", headers=HX, data={"titulo": "Revista B", "issn": "2049-3630",
                                                        "pais": "Perú", "arbitrada": "1"})
    rid = int(r.headers["hx-redirect"].rsplit("/", 1)[1])
    assert revistas.obtener(rid)["estado"] == "pendiente"
    r = admin.post(f"/admin/revistas/{rid}/indexacion", headers=HX,
                   data={"indice_id": str(_indice("SciELO")), "desde": "2018", "fuente": "Portal SciELO",
                         "evidencia_url": "https://www.scielo.org/"})
    assert "SciELO" in r.text and "Portal SciELO" in r.text
    admin.post(f"/admin/revistas/{rid}/verificar", headers=HX, data={"verificada": "1"})
    assert revistas.obtener(rid)["estado"] == "verificada"
    assert "Revista B" in admin.get("/admin/revistas?q=2049").text
    assert "Revista B" not in admin.get("/admin/revistas/lista?estado=pendiente", headers=HX).text
    ficha = admin.get(f"/admin/revistas/{rid}").text
    assert "Verificada por la administración" in ficha and "evidencia" in ficha
    iid = revistas.indexaciones(rid)[0]["id"]
    admin.delete(f"/admin/revistas/{rid}/indexacion/{iid}", headers=HX)
    assert revistas.indexaciones(rid) == []
    admin.delete(f"/admin/revistas/{rid}", headers=HX)
    assert revistas.obtener(rid) is None


def test_solo_admin(client):
    usuarios_id = get_db().q("SELECT id FROM usuario WHERE email = 'inv@test.cl'")[0]["id"]
    get_db().execute("UPDATE usuario SET debe_cambiar_pass = 0 WHERE id = ?", [usuarios_id])
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/admin/revistas").status_code == 403


CSV = ("Título;ISSN;e-ISSN;País;Arbitrada;Acceso abierto;Índice;Desde;Hasta;Cuartil;Fuente;Evidencia\n"
       "Revista Boliviana;0028-0836;;Bolivia;sí;sí;SciELO;2019;;;SciELO Bolivia;https://www.scielo.org.bo/\n"
       "Revista Boliviana;0028-0836;;Bolivia;sí;sí;Latindex;2015;;;Latindex;\n"
       "Annals of Something;;2049-3630;Estados Unidos;sí;no;scopus;2010;;Q1;Scopus 2026;\n"
       "Annals of Something;;2049-3630;Estados Unidos;sí;no;WoS SCIE;2010;;Q2;JCR 2025;\n"
       "Mala;1234-5678;;;;;Scopus;dosmil;;;;\n"
       "Otra;;;;;;Índice inventado;2020;;;;\n")


def test_importar_csv(admin, admin_id):
    grupos, errores = importar_revistas.leer(CSV.encode())
    assert not errores and len(grupos) == 4
    g = {x["datos"]["titulo"]: x for x in grupos}
    assert [x["indice"] for x in g["Revista Boliviana"]["indexaciones"]] == ["SciELO", "Latindex Catálogo"]
    assert [x["indice"] for x in g["Annals of Something"]["indexaciones"]] == ["Scopus", "Web of Science (SCIE)"]
    assert any("ISSN no válido" in e for e in g["Mala"]["errores"])
    assert any("no reconocido" in e for e in g["Otra"]["errores"])
    # Una revista existente se completa (no se duplica).
    rid = revistas.crear({"titulo": "Revista Boliviana", "issn": "0028-0836"}, admin_id)
    admin.post("/admin/revistas/importar/confirmar", headers=HX, data={"contenido": base64.b64encode(CSV.encode()).decode()})
    r = revistas.obtener(rid)
    assert (r["pais"], r["acceso_abierto"], r["estado"]) == ("Bolivia", 1, "verificada")
    assert len(revistas.indexaciones(rid)) == 2
    annals = revistas.por_issn("2049-3630")
    assert annals and revistas.clasificacion(annals["id"], 2026)["revision"] == "indexado"
    assert get_db().q("SELECT COUNT(*) n FROM revista")[0]["n"] == 2
    # Cargar dos veces no duplica indexaciones.
    importar_revistas.aplicar(importar_revistas.leer(CSV.encode())[0], admin_id)
    assert len(revistas.indexaciones(rid)) == 2


def test_plantilla_se_lee(app):
    grupos, errores = importar_revistas.leer(importar_revistas.PLANTILLA.encode("utf-8-sig"))
    assert not errores and not grupos[0]["errores"]
