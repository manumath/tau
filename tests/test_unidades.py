"""Fase 2, paso 1: unidades (UMSA › FCPN › CMAT › IIMAT) y vínculo por unidad."""
import base64

import pytest

from app.comun import importar_vinculos, permisos, unidades, usuarios, vinculos
from app.comun.db import get_db
from app.investigacion import perfiles
from tests.conftest import HX
from tests.test_vinculos import _producto, emmy, hoy  # noqa: F401
from app.acreditacion import informes


def test_jerarquia(app):
    iimat, cmat = unidades.id_de("IIMAT"), unidades.id_de("CMAT")
    assert [u["sigla"] for u in unidades.superiores(iimat)] == ["IIMAT", "CMAT", "FCPN", "UMSA"]
    assert set(unidades.contenidas(unidades.id_de("FCPN"))) == {unidades.id_de("FCPN"), cmat, iimat}
    assert [u["sigla"] for u in unidades.con_vinculo()] == ["IIMAT", "CMAT"]
    assert unidades.instituto() == iimat
    with pytest.raises(ValueError):
        unidades.id_de("FACULTAD-X")


def test_vinculos_simultaneos_con_la_carrera_y_el_instituto(emmy, hoy):
    cmat = unidades.id_de("CMAT")
    assert vinculos.agregar(emmy, "titular", "2020-01-01", jornada=20) == []
    assert vinculos.agregar(emmy, "titular", "2010-03-01", jornada=20, unidad=cmat) == []  # se superponen: otra unidad
    assert "Se superpone" in vinculos.agregar(emmy, "interino", "2012-01-01", "2013-01-01", unidad=cmat)[0]
    assert vinculos.vigente(emmy)["unidad_id"] == unidades.instituto()
    assert vinculos.vigente(emmy, unidad=cmat)["fecha_inicio"] == "2010-03-01"
    assert [v["sigla"] for v in vinculos.listar_todos(emmy)] == ["CMAT", "IIMAT"]  # orden de la jerarquía
    # Cambiar de categoría o terminar en la Carrera no toca el Instituto.
    assert vinculos.terminar(emmy, "2026-06-30", unidad=cmat) == []
    assert vinculos.vigente(emmy, unidad=cmat) is None and vinculos.vigente(emmy)
    assert perfiles.obtener(emmy)["categoria"] == "titular"


def test_solo_el_vinculo_con_el_instituto_cuenta_para_investigacion(emmy, hoy):
    """Una docente de la Carrera sin vínculo con el IIMAT: su producción no entra en la memoria."""
    vinculos.agregar(emmy, "titular", "2010-01-01", unidad=unidades.id_de("CMAT"))
    _producto(emmy, "Solo de la Carrera", 2024)
    assert vinculos.en_fecha(emmy, 2024) == ("no", None)
    assert vinculos.en_fecha(emmy, 2024, unidad=unidades.id_de("CMAT")) == ("si", "titular")
    assert perfiles.obtener(emmy)["categoria"] is None  # la categoría del perfil es la del Instituto
    assert "Solo de la Carrera" not in [p["titulo"] for p in informes.memoria(2024)["productos"]]


def test_migracion_asigna_el_instituto(app):
    columnas = {c["name"]: c for c in get_db().q("PRAGMA table_info(vinculo)")}
    assert columnas["unidad_id"]["notnull"] == 1


HISTORIAL = ("email;unidad;categoria;desde;hasta;jornada;nota\n"
             "inv@test.cl;;titular;2019-01-01;;40;\n"          # sin unidad: el Instituto
             "inv@test.cl;cmat;titular;2015-03-01;;20;Docente\n"
             "inv@test.cl;FCPN;titular;2015-03-01;;;\n")


def test_importar_historial_por_unidad(admin, emmy, hoy):
    cmat = unidades.id_de("CMAT")
    # Sin un rol en la Carrera, las filas de la CMAT se rechazan.
    r = admin.post("/admin/usuarios/historial/revisar", headers=HX,
                   files={"archivo": ("h.csv", HISTORIAL.encode(), "text/csv")})
    assert "No puede gestionar los vínculos de CMAT." in r.text and "Actualizar 1 persona(s)" in r.text
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", cmat)
    vinculos.agregar(emmy, "invitado", "2018-01-01", "2018-12-31")  # Instituto: se reemplaza
    vinculos.agregar(emmy, "interino", "2011-01-01", "2011-12-31", unidad=cmat)  # Carrera: se reemplaza
    personas, errores = importar_vinculos.leer(HISTORIAL.encode())
    assert not errores
    p = {(x["email"], x["unidad"]): x for x in personas}
    assert p[("inv@test.cl", "IIMAT")]["actuales"] == 1 and p[("inv@test.cl", "CMAT")]["actuales"] == 1
    assert "Unidad no válida: FCPN" in p[("inv@test.cl", "FCPN")]["errores"][0]
    r = admin.post("/admin/usuarios/historial/revisar", headers=HX,
                   files={"archivo": ("h.csv", HISTORIAL.encode(), "text/csv")})
    assert "Actualizar 2 persona(s)" in r.text and "CMAT" in r.text
    admin.post("/admin/usuarios/historial/confirmar", headers=HX,
               data={"contenido": base64.b64encode(HISTORIAL.encode()).decode()})
    assert [(v["categoria"], v["fecha_inicio"]) for v in vinculos.listar(emmy)] == [("titular", "2019-01-01")]
    assert [(v["categoria"], v["nota"]) for v in vinculos.listar(emmy, cmat)] == [("titular", "Docente")]


def test_pantalla_de_vinculos_por_unidad(admin, emmy, hoy):
    cmat = unidades.id_de("CMAT")
    # Solo con Dirección del Instituto: ve el IIMAT y no la CMAT.
    r = admin.get(f"/admin/usuarios/{emmy}/vinculo")
    assert "Carrera de Matemática (CMAT)" not in r.text
    assert admin.get(f"/admin/usuarios/{emmy}/vinculo?unidad={cmat}").status_code == 403
    assert admin.post(f"/admin/usuarios/{emmy}/vinculo/periodo", headers=HX,
                      data={"categoria": "titular", "desde": "2012-03-01", "unidad": str(cmat)}).status_code == 403
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", cmat)
    r = admin.get(f"/admin/usuarios/{emmy}/vinculo")
    assert "Carrera de Matemática (CMAT)" in r.text and 'name="unidad" value="4"' in r.text
    r = admin.get(f"/admin/usuarios/{emmy}/vinculo?unidad={cmat}")
    assert f'name="unidad" value="{cmat}"' in r.text
    r = admin.post(f"/admin/usuarios/{emmy}/vinculo/periodo", headers=HX,
                   data={"categoria": "titular", "desde": "2012-03-01", "jornada": "20", "unidad": str(cmat)})
    assert "2012-03-01" in r.text
    assert vinculos.vigente(emmy, unidad=cmat)["jornada_horas"] == 20 and vinculos.vigente(emmy) is None
    assert get_db().q("SELECT detalle FROM auditoria WHERE accion = 'agregar_vinculo'")[0]["detalle"].startswith("CMAT:")
    # Una unidad que no admite vínculo se rechaza.
    assert admin.post(f"/admin/usuarios/{emmy}/vinculo/periodo", headers=HX,
                      data={"categoria": "titular", "desde": "2020-01-01",
                            "unidad": str(unidades.id_de("UMSA"))}).status_code == 403
