"""Unidades (UMSA › FCPN › CMAT › IIMAT) y vínculo con una sola dependencia (la Carrera)."""
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
    assert unidades.instituto() == iimat and vinculos.carrera() == cmat
    with pytest.raises(ValueError):
        unidades.id_de("FACULTAD-X")


def test_dependencia_unica(emmy, hoy):
    """Un solo historial por persona, con la Carrera (el Instituto forma parte de ella)."""
    assert vinculos.agregar(emmy, "titular", "2020-01-01", jornada=20) == []
    assert "Se superpone" in vinculos.agregar(emmy, "interino", "2019-06-01", "2020-06-30")[0]
    assert vinculos.vigente(emmy)["unidad_id"] == unidades.id_de("CMAT")
    assert perfiles.obtener(emmy)["categoria"] == "titular"
    # Ese mismo vínculo define qué producción cuenta en los informes de investigación.
    _producto(emmy, "Con vínculo", 2024)
    assert vinculos.en_fecha(emmy, 2024) == ("si", "titular")
    assert "Con vínculo" in [p["titulo"] for p in informes.memoria(2024)["productos"]]
    assert vinculos.terminar(emmy, "2026-06-30") == [] and vinculos.vigente(emmy) is None


def test_migracion_une_los_periodos(app):
    """0032: los periodos con el Instituto pasan a la Carrera, salvo los que se superponen con uno de
    la Carrera (manda el de la Carrera)."""
    from pathlib import Path as P
    db = get_db()
    iimat, cmat = unidades.id_de("IIMAT"), unidades.id_de("CMAT")
    emmy = usuarios.por_email("inv@test.cl")["id"]
    for unidad, desde, hasta in ((iimat, "2015-01-01", "2017-12-31"), (iimat, "2018-01-01", None),
                                 (cmat, "2019-03-01", None)):
        db.t.vinculo.insert(usuario_id=emmy, unidad_id=unidad, categoria="titular", fecha_inicio=desde, fecha_fin=hasta)
    sql = (P(__file__).parent.parent / "migrations" / "0032-vinculo-unico.sql").read_text()
    db.conn.execute(sql)  # apsw ejecuta todas las sentencias del script
    assert [(v["fecha_inicio"], v["unidad_id"]) for v in vinculos.listar(emmy)] == [
        ("2015-01-01", cmat), ("2019-03-01", cmat)]


HISTORIAL = ("email;unidad;categoria;desde;hasta;jornada;nota\n"
             "inv@test.cl;IIMAT;contratado;2015-03-01;2018-12-31;40;\n"   # la unidad se ignora
             "inv@test.cl;cmat;titular;2019-01-01;;20;Docente\n")


def test_importar_historial(admin, emmy, hoy):
    # Solo la Dirección de Carrera importa historiales.
    assert admin.post("/admin/usuarios/historial/revisar", headers=HX,
                      files={"archivo": ("h.csv", HISTORIAL.encode(), "text/csv")}).status_code == 403
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    vinculos.agregar(emmy, "invitado", "2011-01-01", "2011-12-31")  # se reemplaza
    personas, errores = importar_vinculos.leer(HISTORIAL.encode())
    assert not errores and len(personas) == 1 and personas[0]["actuales"] == 1
    r = admin.post("/admin/usuarios/historial/revisar", headers=HX,
                   files={"archivo": ("h.csv", HISTORIAL.encode(), "text/csv")})
    assert "Actualizar 1 persona(s)" in r.text
    admin.post("/admin/usuarios/historial/confirmar", headers=HX,
               data={"contenido": base64.b64encode(HISTORIAL.encode()).decode()})
    assert [(v["categoria"], v["fecha_inicio"], v["nota"]) for v in vinculos.listar(emmy)] == [
        ("contratado", "2015-03-01", None), ("titular", "2019-01-01", "Docente")]


def test_pantalla_de_vinculo_solo_para_la_direccion_de_carrera(admin, emmy, hoy):
    # Administración del sistema y Dirección del Instituto (roles de la cuenta admin) no definen vínculos.
    assert admin.get(f"/admin/usuarios/{emmy}/vinculo").status_code == 403
    assert admin.post(f"/admin/usuarios/{emmy}/vinculo/periodo", headers=HX,
                      data={"categoria": "titular", "desde": "2012-03-01"}).status_code == 403
    assert "Categoría (si es investigador o docente)" not in admin.get("/admin/usuarios/nuevo").text
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", unidades.id_de("CMAT"))
    r = admin.get(f"/admin/usuarios/{emmy}/vinculo")
    assert "Carga horaria contratada" in r.text and "Instituto de Investigación Matemática (IIMAT)" not in r.text
    r = admin.post(f"/admin/usuarios/{emmy}/vinculo/periodo", headers=HX,
                   data={"categoria": "titular", "desde": "2012-03-01", "jornada": "20"})
    assert "2012-03-01" in r.text and vinculos.vigente(emmy)["jornada_horas"] == 20
    assert "Categoría (si es investigador o docente)" in admin.get("/admin/usuarios/nuevo").text
