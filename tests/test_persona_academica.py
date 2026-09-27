"""Fase 2, paso 4: la persona académica (grados, personas sin acceso, docentes)."""
import re
from datetime import date

import pytest

from app.comun import academicos, permisos, unidades, usuarios, vinculos
from app.comun.db import get_db
from app.investigacion import perfiles
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login


@pytest.fixture
def emmy(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    return uid


# --- Grados ------------------------------------------------------------------------------------------------

def test_grados_y_grado_principal(emmy):
    columnas = {c["name"] for c in get_db().q("PRAGMA table_info(investigador)")}
    assert "grado" not in columnas and "categoria" not in columnas  # ahora se calculan
    assert academicos.agregar_grado(emmy, {"nivel": "licenciatura", "titulo": "Licenciada en Matemática",
                                           "institucion": "UMSA", "pais": "bolivia", "anio": "2001"}) == []
    assert perfiles.obtener(emmy)["grado"] == "Licenciatura o título profesional"
    assert academicos.agregar_grado(emmy, {"nivel": "doctorado", "institucion": "Universidad de Chile",
                                           "pais": "Chile", "anio": 2010}) == []
    lista = academicos.grados(emmy)
    assert [g["nivel"] for g in lista] == ["doctorado", "licenciatura"]  # de mayor a menor
    assert lista[1]["pais"] == "Bolivia"  # país normalizado
    assert perfiles.obtener(emmy)["grado"] == "Doctorado"
    assert academicos.texto_grado(lista[0]) == "Doctorado · Universidad de Chile (Chile), 2010"
    assert academicos.agregar_grado(emmy, {"nivel": "emerito"}) == ["Elija el nivel del grado."]
    assert "El año debe estar" in academicos.agregar_grado(emmy, {"nivel": "otro", "anio": str(date.today().year + 1)})[0]
    otro = usuarios.crear("otro@test.cl", "Otra", "Persona", PASS_TEMP)["id"]
    assert academicos.quitar_grado(otro, lista[0]["id"]) is None  # no es suyo
    assert academicos.quitar_grado(emmy, lista[0]["id"])["nivel"] == "doctorado"


def test_grados_desde_mi_perfil(client, emmy):
    login(client, "inv@test.cl", PASS_TEMP)
    assert "Grados académicos" in client.get("/perfil").text
    r = client.post("/perfil/grados", headers=HX, data={"nivel": "maestria", "titulo": "Magíster en Matemática",
                                                        "institucion": "UMSA", "anio": "2005"})
    assert "Magíster en Matemática · UMSA, 2005" in r.text
    assert 'id="seccion-datos"' in r.text and 'id="perfil-completitud"' in r.text  # se actualizan fuera de banda
    r = client.post("/perfil/grados", headers=HX, data={"nivel": ""})
    assert "Elija el nivel del grado." in r.text
    gid = academicos.grados(emmy)[0]["id"]
    r = client.delete(f"/perfil/grados/{gid}", headers=HX)
    assert "Sin grados registrados." in r.text


# --- Personas sin acceso y docentes ----------------------------------------------------------------------

def test_persona_sin_acceso(admin, buzon):
    r = admin.post("/admin/usuarios", headers=HX, data={
        "nombres": "Gottlob", "apellidos": "Frege", "email": "frege@test.cl", "sin_acceso": "on"})
    assert "quedó registrada sin acceso" in r.text and "Sin acceso" in r.text
    u = usuarios.por_email("frege@test.cl")
    assert academicos.sin_acceso(u) and not u["debe_cambiar_pass"]
    assert not usuarios.con_perfil(u["id"])["es_investigador"] and not permisos.roles_vigentes(u["id"])
    # No puede ingresar ni habilitarse solo con «¿Olvidó su contraseña?».
    from starlette.testclient import TestClient
    import main
    anonimo = TestClient(main.app)
    assert "incorrectos" in login(anonimo, "frege@test.cl", "!").text
    buzon.clear()
    anonimo.post("/recuperar", headers=HX, data={"email": "frege@test.cl"})
    assert buzon == []
    # La administración le da acceso con una contraseña temporal.
    r = admin.post(f"/admin/usuarios/{u['id']}/restablecer", headers=HX)
    temporal = re.search(r'id="pass-temporal"[^>]*>([^<]+)<', r.text).group(1)
    assert not academicos.sin_acceso(usuarios.por_email("frege@test.cl"))
    assert login(anonimo, "frege@test.cl", temporal).headers["hx-redirect"] == "/cambiar-password"


def test_sin_acceso_no_puede_ser_administracion(admin):
    r = admin.post("/admin/usuarios", headers=HX, data={
        "nombres": "A", "apellidos": "B", "email": "ab@test.cl", "sin_acceso": "on", "es_admin": "on"})
    assert "no puede tener roles de administración" in r.text and not usuarios.por_email("ab@test.cl")


def test_docente_de_la_carrera_sin_perfil_de_investigacion(admin):
    """Un docente que no investiga: vínculo con la CMAT y ficha académica, sin «Mi perfil»."""
    admin.post("/admin/usuarios", headers=HX, data={
        "nombres": "Karl", "apellidos": "Weierstrass", "email": "kw@test.cl", "sin_acceso": "on"})
    kw = usuarios.por_email("kw@test.cl")["id"]
    cmat = unidades.id_de("CMAT")
    permisos.asignar(usuarios.por_email("admin@test.cl")["id"], "direccion_carrera", cmat)
    r = admin.post(f"/admin/usuarios/{kw}/vinculo/periodo", headers=HX,
                   data={"categoria": "titular", "desde": "2010-03-01", "jornada": "40", "unidad": str(cmat)})
    assert r.status_code == 200 and vinculos.vigente(kw, unidad=cmat)["jornada_horas"] == 40
    assert "CMAT: Titular" in admin.get("/admin/usuarios").text


def test_ficha_academica_segun_el_rol(client, emmy):
    ids = {}
    for clave, rol, sigla in (("datos", "gestion_datos", "CMAT"), ("comite", "comite_acreditacion", "UMSA"),
                              ("sistema", "administracion_sistema", "UMSA")):
        ids[clave] = usuarios.crear(f"{clave}@test.cl", clave, "Prueba", "Clave-ficha-1", debe_cambiar_pass=False,
                                    es_investigador=False)["id"]
        permisos.asignar(ids[clave], rol, unidades.id_de(sigla))

    def como(clave):
        client.post("/logout")
        login(client, f"{clave}@test.cl", "Clave-ficha-1")
    como("datos")
    assert "Ficha académica" in client.get("/admin/usuarios").text
    r = client.post(f"/admin/usuarios/{emmy}/grados", headers=HX, data={"nivel": "doctorado", "institucion": "UMSA"})
    assert "Doctorado · UMSA" in r.text
    assert get_db().q("SELECT accion FROM auditoria WHERE accion = 'agregar_grado'")
    como("sistema")  # ve la ficha (datos personales), pero no edita los grados
    r = client.get(f"/admin/usuarios/{emmy}/ficha")
    assert r.status_code == 200 and "Doctorado · UMSA" in r.text and 'hx-post' not in r.text.split("Grados")[1]
    assert client.post(f"/admin/usuarios/{emmy}/grados", headers=HX, data={"nivel": "otro"}).status_code == 403
    como("comite")
    assert client.get(f"/admin/usuarios/{emmy}/ficha").status_code == 403
