"""Fase 2, paso 2: roles con alcance y vigencia, y el punto único de decisión `puede()`."""
from datetime import date, timedelta

import pytest

from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login


def _ids():
    return {s: unidades.id_de(s) for s in ("UMSA", "FCPN", "CMAT", "IIMAT")}


@pytest.fixture
def gente(app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    return {"admin": usuarios.por_email("admin@test.cl")["id"], "emmy": emmy}


def test_administradores_reciben_los_dos_roles(gente):
    """La transición: quien era administrador tiene Administración del sistema y Dirección del
    Instituto; `es_admin` se calcula de esos roles."""
    roles = {(r["rol"], r["sigla"]) for r in permisos.roles_vigentes(gente["admin"])}
    assert roles == {("administracion_sistema", "UMSA"), ("direccion_instituto", "IIMAT")}
    assert usuarios.por_id(gente["admin"])["es_admin"] == 1
    assert usuarios.con_perfil(gente["emmy"])["es_admin"] == 0
    columnas = {c["name"] for c in get_db().q("PRAGMA table_info(usuario)")}
    assert "es_admin" not in columnas  # la marca vieja ya no existe


def test_matriz_de_permisos(gente):
    u = _ids()
    emmy = gente["emmy"]
    casos = [  # rol asignado, unidad, acción, unidad consultada, ¿puede?
        ("direccion_carrera", "CMAT", "gestionar_vinculos", "CMAT", True),
        ("direccion_carrera", "CMAT", "gestionar_vinculos", "IIMAT", False),  # el IIMAT no es de la Carrera
        ("direccion_carrera", "CMAT", "decidir_propuestas", None, False),
        ("direccion_instituto", "IIMAT", "decidir_propuestas", "IIMAT", True),
        ("direccion_instituto", "IIMAT", "gestionar_vinculos", "CMAT", False),
        ("direccion_instituto", "IIMAT", "asignar_roles", None, False),
        ("comite_acreditacion", "UMSA", "ver_informes_institucionales", "CMAT", True),
        ("comite_acreditacion", "UMSA", "ver_informes_institucionales", "IIMAT", True),
        ("comite_acreditacion", "UMSA", "gestionar_vinculos", "IIMAT", False),  # solo mira
        ("gestion_datos", "CMAT", "gestionar_estudiantes", "CMAT", True),
        ("gestion_datos", "CMAT", "gestionar_estudiantes", "IIMAT", False),
        ("administracion_sistema", "UMSA", "asignar_roles", None, True),
        ("administracion_sistema", "UMSA", "decidir_propuestas", "IIMAT", False),  # no decide lo académico
    ]
    for rol, unidad, accion, consultada, esperado in casos:
        get_db().execute("DELETE FROM rol_asignado WHERE usuario_id = ?", [emmy])
        assert permisos.asignar(emmy, rol, u[unidad]) == []
        usuario = {"id": emmy}
        assert permisos.puede(usuario, accion, u[consultada] if consultada else None) is esperado, \
            (rol, accion, consultada)
    with pytest.raises(ValueError):
        permisos.puede({"id": emmy}, "accion_inventada")
    assert permisos.puede(None, "asignar_roles") is False


def test_asignar_valida(gente):
    u, emmy = _ids(), gente["emmy"]
    assert "se asigna en: IIMAT" in permisos.asignar(emmy, "direccion_instituto", u["CMAT"])[0]
    assert permisos.asignar(emmy, "rol_inventado", u["UMSA"]) == ["Rol no válido."]
    assert "anterior" in permisos.asignar(emmy, "direccion_carrera", u["CMAT"], "2026-05-01", "2026-01-01")[0]
    assert permisos.asignar(emmy, "direccion_carrera", u["CMAT"], "2024-01-01", "2024-12-31") == []
    assert "durante parte de ese periodo" in permisos.asignar(emmy, "direccion_carrera", u["CMAT"], "2024-06-01")[0]
    assert permisos.asignar(emmy, "direccion_carrera", u["CMAT"], "2025-01-01") == []  # otro periodo
    # Un rol que terminó o todavía no empieza no está vigente.
    assert [r["rol"] for r in permisos.roles_vigentes(emmy)] == ["direccion_carrera"]
    assert permisos.roles_vigentes(emmy, "2024-06-01")[0]["hasta"] == "2024-12-31"
    manana = (date.today() + timedelta(days=1)).isoformat()
    assert permisos.asignar(emmy, "comite_acreditacion", u["UMSA"], manana) == []
    assert not permisos.puede({"id": emmy}, "ver_todos_los_proyectos")


def test_nunca_sin_administracion_del_sistema(gente):
    a = next(r for r in permisos.roles_vigentes(gente["admin"]) if r["rol"] == "administracion_sistema")
    assert "única persona" in permisos.terminar(a["id"])[0]
    permisos.asignar(gente["emmy"], "administracion_sistema", unidades.id_de("UMSA"))
    assert permisos.terminar(a["id"]) == []
    assert not permisos.tiene_rol({"id": gente["admin"]}, "administracion_sistema")


def test_avisos_de_propuestas_a_la_direccion_del_instituto(gente):
    assert [x["id"] for x in permisos.con_rol("direccion_instituto")] == [gente["admin"]]
    assert permisos.con_rol("direccion_instituto", unidades.id_de("CMAT")) == []


def test_pantalla_de_roles(client, gente):
    login(client, "admin@test.cl", PASS_ADMIN)
    r = client.get("/admin/usuarios")
    assert "Adm. del sistema" in r.text and "Dir. Instituto" in r.text and f"/admin/usuarios/{gente['emmy']}/roles" in r.text
    r = client.get(f"/admin/usuarios/{gente['emmy']}/roles")
    assert "Qué puede hacer cada rol" in r.text and f'value="direccion_carrera:{unidades.id_de("CMAT")}"' in r.text
    r = client.post(f"/admin/usuarios/{gente['emmy']}/roles", headers=HX,
                    data={"rol_unidad": f"direccion_carrera:{unidades.id_de('CMAT')}", "nota": "Nota 12/2026"})
    assert "Nota 12/2026" in r.text and permisos.tiene_rol({"id": gente["emmy"]}, "direccion_carrera")
    auditoria = get_db().q("SELECT detalle FROM auditoria WHERE accion = 'asignar_rol'")[0]["detalle"]
    assert auditoria.startswith("Dirección de Carrera (CMAT)") and "Nota 12/2026" in auditoria
    r = client.post(f"/admin/usuarios/{gente['emmy']}/roles", headers=HX,
                    data={"rol_unidad": f"direccion_carrera:{unidades.id_de('IIMAT')}"})
    assert "se asigna en: CMAT" in r.text
    aid = next(x["id"] for x in permisos.historial(gente["emmy"]) if x["rol"] == "direccion_carrera")
    ayer = (date.today() - timedelta(days=1)).isoformat()
    get_db().execute("UPDATE rol_asignado SET desde = ? WHERE id = ?", [ayer, aid])
    client.post(f"/admin/usuarios/roles/{aid}/terminar", headers=HX)  # deja de regir hoy: último día, ayer
    assert not permisos.tiene_rol({"id": gente["emmy"]}, "direccion_carrera")
    assert permisos.obtener(aid)["hasta"] == ayer
    # Uno asignado hoy por error se anula.
    permisos.asignar(gente["emmy"], "coordinacion_academica", unidades.id_de("CMAT"))
    hoy_id = next(x["id"] for x in permisos.historial(gente["emmy"]) if x["rol"] == "coordinacion_academica")
    client.post(f"/admin/usuarios/roles/{hoy_id}/terminar", headers=HX)
    assert permisos.obtener(hoy_id) is None
    assert [x["accion"] for x in get_db().q("SELECT accion FROM auditoria WHERE accion LIKE '%_rol' ORDER BY id")] == [
        "asignar_rol", "terminar_rol", "terminar_rol"]


def test_solo_administracion_del_sistema_asigna_roles(client, gente):
    """La Dirección del Instituto (sin Administración del sistema) no ve ni usa la pantalla de roles."""
    admin = gente["admin"]
    permisos.asignar(gente["emmy"], "administracion_sistema", unidades.id_de("UMSA"))
    a = next(r for r in permisos.roles_vigentes(admin) if r["rol"] == "administracion_sistema")
    get_db().execute("UPDATE rol_asignado SET desde = ? WHERE id = ?", [(date.today() - timedelta(days=1)).isoformat(),
                                                                         a["id"]])
    assert permisos.terminar(a["id"], (date.today() - timedelta(days=1)).isoformat()) == []
    login(client, "admin@test.cl", PASS_ADMIN)
    assert "/roles" not in client.get("/admin/usuarios").text
    assert client.get(f"/admin/usuarios/{gente['emmy']}/roles").status_code == 403
    assert client.post(f"/admin/usuarios/{admin}/roles", headers=HX,
                       data={"rol_unidad": f"administracion_sistema:{unidades.id_de('UMSA')}"}).status_code == 403
