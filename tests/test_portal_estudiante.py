"""Portal del estudiante (PLAN §49, etapa 2): cuentas, ingreso por enlace, aislamiento, actividad y verificación."""
import re

import pytest
from starlette.testclient import TestClient

from app.comun import academicos, estudiantes, notificaciones, personas, usuarios
from app.comun.db import get_db
from app.estudiantil import actividad, importar
from tests.conftest import HX, PASS_ADMIN, login
from tests.test_cohortes import ENCABEZADO

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
CSV = ENCABEZADO + (
    "1111111,Sofía,Mamani,sofia@correo.bo,mujer,,2022-I,,,,,,cursando,,,,,\n"
    "2222222,Luis,Choque,luis@correo.bo,hombre,,2022-I,,,,,,cursando,,,,,\n"
    "3333333,Ana,Condori,,mujer,,2022-I,,,,,,cursando,,,,,\n"            # sin correo
    "4444444,Pedro,Quispe,inv@test.cl,hombre,,2022-I,,,,,,cursando,,,,,\n"  # correo de otra cuenta
    "5555555,Rosa,Flores,rosa@correo.bo,mujer,,2019-I,,,,,,retirado,2020-II,,,,academico\n")  # no cursa


@pytest.fixture
def estudiantes_cargados(app):
    filas, errores = importar.leer(CSV.encode())
    assert errores == [] and not [f["errores"] for f in filas if f["errores"]]
    importar.aplicar(filas, None)
    return estudiantes.crear_cuentas(None)


def _uid(email):
    return usuarios.por_email(email)["id"]


def _externo(ru):
    return get_db().q("SELECT externo_id FROM estudiante WHERE registro_universitario = ?", [ru])[0]["externo_id"]


def _ingresar(client, email, buzon):
    """Ingresa como estudiante con el enlace del correo (el cliente queda con la sesión)."""
    client.post("/logout")
    r = client.post("/acceso", data={"email": email}, headers=HX)
    assert "Si el correo corresponde a un estudiante registrado" in r.text
    enlace = re.search(r"/acceso/[\w\-]+", buzon[-1].get_content()).group(0)
    assert "Ingresar" in client.get(enlace).text
    r = client.post(enlace, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    return enlace


def _aceptar(client):
    client.post("/estudiante/consentimiento", follow_redirects=False)


@pytest.fixture
def sofia(client, estudiantes_cargados, buzon):
    _ingresar(client, "sofia@correo.bo", buzon)
    _aceptar(client)
    return client


def _form(**campos):
    return {"tipo": "ayudantia", "titulo": "Ayudantía de Cálculo I", "fecha_inicio": "2025-03-01", **campos}


# --- Cuentas ---------------------------------------------------------------------------------------------------

def test_crear_cuentas_solo_de_quien_cursa_y_tiene_correo(estudiantes_cargados):
    assert estudiantes_cargados == {"creadas": 2, "sin_correo": 1, "en_uso": 1}
    u = usuarios.por_email("sofia@correo.bo")
    assert academicos.sin_acceso(u) and estudiantes.cuenta_de(u["id"]) == _externo("1111111")
    assert usuarios.por_email("rosa@correo.bo") is None                 # retirada: sin cuenta
    assert estudiantes.crear_cuentas(None) == {"creadas": 0, "sin_correo": 1, "en_uso": 1}   # no se repite
    # Un investigador con el mismo correo no queda vinculado a la ficha de un estudiante.
    assert estudiantes.cuenta_de(_uid("inv@test.cl")) is None


# --- Ingreso por enlace ----------------------------------------------------------------------------------------

def test_ingreso_por_enlace_de_un_solo_uso(client, estudiantes_cargados, buzon):
    enlace = _ingresar(client, "sofia@correo.bo", buzon)
    assert client.get("/estudiante").status_code == 200
    client.post("/logout")
    assert "Enlace no válido" in client.get(enlace).text                 # ya se usó
    assert client.post(enlace, follow_redirects=False).status_code == 200


def test_abrir_el_enlace_no_lo_consume(client, estudiantes_cargados, buzon):
    client.post("/acceso", data={"email": "sofia@correo.bo"}, headers=HX)
    enlace = re.search(r"/acceso/[\w\-]+", buzon[-1].get_content()).group(0)
    for _ in range(3):                      # un programa de seguridad del correo lo abre antes que la persona
        assert "Ingresar" in client.get(enlace).text
    assert client.post(enlace, follow_redirects=False).status_code == 303


def test_el_enlace_no_revela_quien_esta_registrado(client, estudiantes_cargados, buzon):
    for email in ("nadie@correo.bo", "inv@test.cl", "rosa@correo.bo"):
        r = client.post("/acceso", data={"email": email}, headers=HX)
        assert "Si el correo corresponde a un estudiante registrado" in r.text
    assert buzon == []                                                   # ni investigadores ni quien no tiene cuenta


def test_limite_de_enlaces_por_hora(client, estudiantes_cargados, buzon):
    for _ in range(5):
        client.post("/acceso", data={"email": "sofia@correo.bo"}, headers=HX)
    assert len(buzon) == 3


def test_el_enlace_de_acceso_no_sirve_para_cambiar_la_contraseña(client, estudiantes_cargados, buzon):
    client.post("/acceso", data={"email": "sofia@correo.bo"}, headers=HX)
    token = re.search(r"/acceso/([\w\-]+)", buzon[-1].get_content()).group(1)
    assert "Enlace no válido" in client.get(f"/recuperar/{token}").text
    client.post(f"/recuperar/{token}", data={"nueva": "Clave-nueva-123", "confirmacion": "Clave-nueva-123"})
    assert login(client, "sofia@correo.bo", "Clave-nueva-123").headers.get("hx-redirect") is None


def test_una_cuenta_sin_contraseña_no_ingresa_por_login(client, estudiantes_cargados):
    r = login(client, "sofia@correo.bo", "SIN_ACCESO")
    assert "incorrectos" in r.text


# --- Aislamiento -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("ruta", ["/", "/investigadores", "/productos", "/proyectos", "/docencia/planes", "/docencia/cohortes",
                                  "/estudiantes", "/admin/usuarios", "/informes", "/buscar", "/perfil", "/mis-datos",
                                  "/cambiar-password", "/adjuntos/1"])
def test_el_estudiante_no_entra_al_area_del_personal(sofia, ruta):
    r = sofia.get(ruta, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/estudiante", ruta


def test_el_estudiante_solo_ve_su_navegacion(sofia):
    r = sofia.get("/estudiante")
    assert 'href="/estudiante"' in r.text and "Mi seguimiento" in r.text
    for tabu in ("/investigadores", "/docencia", "/admin", "/buscar", "/mis-datos", "/cambiar-password"):
        assert f'href="{tabu}' not in r.text, tabu


def test_quien_es_personal_y_estudiante_conserva_su_acceso(client, estudiantes_cargados):
    """Un investigador con ficha de estudiante (p. ej., cursa una maestría) no queda reducido al portal del estudiante."""
    inv = _uid("inv@test.cl")
    get_db().t.cuenta_estudiante.insert(externo_id=_externo("4444444"), usuario_id=inv)
    from tests.conftest import PASS_TEMP
    usuarios.cambiar_password(inv, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/productos", follow_redirects=False).status_code == 200
    assert client.get("/estudiante").status_code == 200


# --- Consentimiento ------------------------------------------------------------------------------------------------

def test_hay_que_aceptar_el_uso_de_datos_antes_de_registrar(client, estudiantes_cargados, buzon):
    _ingresar(client, "sofia@correo.bo", buzon)
    r = client.get("/estudiante")
    assert "Antes de empezar" in r.text and "No registra sus materias ni sus notas" in r.text
    assert client.post("/estudiante/actividades", data=_form()).status_code == 403
    assert client.get("/estudiante/actividades/nueva", headers=HX).status_code == 403
    _aceptar(client)
    r = client.get("/estudiante")
    assert "Mi actividad estudiantil" in r.text and "Cohorte 2022-I" in r.text and "RU 1111111" in r.text
    assert get_db().q("SELECT COUNT(*) n FROM auditoria WHERE accion = 'aceptar_consentimiento_estudiantil'")[0]["n"] == 1


# --- Actividad estudiantil ---------------------------------------------------------------------------------------

def test_registrar_actividad_con_evidencia(sofia):
    r = sofia.post("/estudiante/actividades", data=_form(institucion="UMSA"), headers=HX,
                   files={"archivo": ("certificado.png", PNG, "image/png")})
    assert "Ayudantía de Cálculo I" in r.text and "Por verificar" in r.text and "certificado.png" in r.text
    a = actividad.listar(_externo("1111111"))[0]
    assert a["estado"] == "pendiente" and a["institucion"] == "UMSA" and len(a["evidencias"]) == 1
    adj = a["evidencias"][0]
    r = sofia.get(f"/estudiante/evidencia/{adj['id']}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.headers["cache-control"] == "private, no-store"


def test_validaciones_de_la_actividad(sofia):
    r = sofia.post("/estudiante/actividades", data=_form(titulo="", tipo="", fecha_inicio="2099-01-01"), headers=HX)
    assert "Escriba un título" in r.text and "Elija el tipo" in r.text and "no puede ser futura" in r.text
    r = sofia.post("/estudiante/actividades", data=_form(), headers=HX,
                   files={"archivo": ("malo.exe", b"MZ\x00\x00 programa", "application/octet-stream")})
    assert "debe ser un archivo PDF, PNG o JPG" in r.text
    assert actividad.listar(_externo("1111111")) == []                  # no se creó nada a medias
    r = sofia.post("/estudiante/actividades", data=_form(fecha_fin="2025-01-01"), headers=HX)
    assert "anterior al inicio" in r.text


def test_corregir_devuelve_la_actividad_a_por_verificar(sofia, client):
    sofia.post("/estudiante/actividades", data=_form(), headers=HX)
    a = actividad.listar(_externo("1111111"))[0]
    assert actividad.verificar(a["id"], _uid("admin@test.cl"))
    r = sofia.post(f"/estudiante/actividades/{a['id']}", data=_form(titulo="Ayudantía de Cálculo II"), headers=HX)
    assert "Cálculo II" in r.text
    assert actividad.obtener(a["id"])["estado"] == "pendiente"


def test_solo_la_dueña_ve_y_toca_su_actividad(client, estudiantes_cargados, buzon):
    _ingresar(client, "sofia@correo.bo", buzon)
    _aceptar(client)
    client.post("/estudiante/actividades", data=_form(), headers=HX, files={"archivo": ("c.png", PNG, "image/png")})
    a = actividad.listar(_externo("1111111"))[0]
    adj = a["evidencias"][0]
    otro = TestClient(client.app)
    _ingresar(otro, "luis@correo.bo", buzon)
    _aceptar(otro)
    assert "Ayudantía de Cálculo I" not in otro.get("/estudiante").text
    assert otro.get(f"/estudiante/actividades/{a['id']}/editar", headers=HX).status_code == 404
    assert otro.post(f"/estudiante/actividades/{a['id']}", data=_form(titulo="Robada"), headers=HX).status_code == 404
    assert otro.delete(f"/estudiante/actividades/{a['id']}", headers=HX).status_code == 404
    assert otro.get(f"/estudiante/evidencia/{adj['id']}").status_code == 404
    assert otro.delete(f"/estudiante/evidencia/{adj['id']}", headers=HX).status_code == 404
    assert actividad.obtener(a["id"])["titulo"] == "Ayudantía de Cálculo I"


def test_eliminar_actividad_borra_su_evidencia(sofia):
    from app.investigacion import adjuntos
    sofia.post("/estudiante/actividades", data=_form(), headers=HX, files={"archivo": ("c.png", PNG, "image/png")})
    a = actividad.listar(_externo("1111111"))[0]
    archivo = adjuntos.ruta(a["evidencias"][0])
    assert archivo.exists()
    r = sofia.delete(f"/estudiante/actividades/{a['id']}", headers=HX)
    assert "Aún no registró actividades" in r.text
    assert not archivo.exists() and get_db().q("SELECT COUNT(*) n FROM adjunto")[0]["n"] == 0


def test_quitar_evidencia_devuelve_a_por_verificar(sofia):
    sofia.post("/estudiante/actividades", data=_form(), headers=HX, files={"archivo": ("c.png", PNG, "image/png")})
    a = actividad.listar(_externo("1111111"))[0]
    actividad.verificar(a["id"], _uid("admin@test.cl"))
    sofia.delete(f"/estudiante/evidencia/{a['evidencias'][0]['id']}", headers=HX)
    assert actividad.obtener(a["id"])["estado"] == "pendiente" and actividad.obtener(a["id"])["evidencias"] == []


def test_la_participacion_en_la_investigacion_se_muestra_sin_enlaces(client, estudiantes_cargados, buzon):
    ext = _externo("1111111")
    get_db().execute("INSERT INTO producto (tipo_id, titulo, anio, estado_publicacion, revision, creado_por) "
                     "SELECT id, 'Anillos de invariantes', 2026, 'publicado', 'sin_arbitraje', ? FROM tipo_producto "
                     "WHERE nombre = 'Tesis dirigida'", [_uid("admin@test.cl")])
    pid = get_db().q("SELECT id FROM producto")[0]["id"]
    get_db().execute("INSERT INTO producto_autor (producto_id, externo_id, orden) VALUES (?, ?, 1)", [pid, ext])
    _ingresar(client, "sofia@correo.bo", buzon)
    _aceptar(client)
    r = client.get("/estudiante")
    assert "Anillos de invariantes" in r.text and f'href="/productos/{pid}"' not in r.text


# --- Verificación por la Dirección de Carrera -------------------------------------------------------------

def _pendiente(estudiante_client, **campos):
    estudiante_client.post("/estudiante/actividades", data=_form(**campos), headers=HX,
                           files={"archivo": ("c.png", PNG, "image/png")})
    return actividad.listar(_externo("1111111"))[0]


def test_la_direccion_verifica_y_el_estudiante_recibe_un_aviso(sofia, app):
    a = _pendiente(sofia)
    direccion = TestClient(app)
    assert login(direccion, "admin@test.cl", PASS_ADMIN).headers["hx-redirect"] == "/"
    from app.comun import permisos, unidades
    permisos.asignar(_uid("admin@test.cl"), "direccion_carrera", unidades.id_de("CMAT"))
    r = direccion.get("/docencia/cohortes/actividades")
    assert "Choque" not in r.text and "Mamani, Sofía" in r.text and "Ayudantía de Cálculo I" in r.text
    assert f'/docencia/cohortes/actividades/evidencia/{a["evidencias"][0]["id"]}' in r.text
    assert direccion.get(f"/docencia/cohortes/actividades/evidencia/{a['evidencias'][0]['id']}").status_code == 200
    assert "Actividades por verificar (1)" in direccion.get("/docencia/cohortes").text
    r = direccion.post(f"/docencia/cohortes/actividades/{a['id']}/verificar", headers=HX)
    assert "No hay actividades por verificar" in r.text
    assert actividad.obtener(a["id"])["estado"] == "verificada"
    avisos = notificaciones.recientes(_uid("sofia@correo.bo"))
    assert [x["asunto"] for x in avisos] == ["Su actividad fue verificada"] and avisos[0]["url"] == "/estudiante"
    assert "Verificada" in sofia.get("/estudiante").text


def test_observar_pide_un_texto_y_avisa(sofia, app):
    a = _pendiente(sofia)
    from app.comun import permisos, unidades
    permisos.asignar(_uid("admin@test.cl"), "direccion_carrera", unidades.id_de("CMAT"))
    direccion = TestClient(app)
    login(direccion, "admin@test.cl", PASS_ADMIN)
    r = direccion.post(f"/docencia/cohortes/actividades/{a['id']}/observar", data={"observacion": " "}, headers=HX)
    assert "Escriba qué debe corregir" in r.text and actividad.obtener(a["id"])["estado"] == "pendiente"
    direccion.post(f"/docencia/cohortes/actividades/{a['id']}/observar", data={"observacion": "Falta la fecha de fin"},
                   headers=HX)
    assert actividad.obtener(a["id"])["estado"] == "observada"
    r = sofia.get("/estudiante")
    assert "Con observaciones" in r.text and "Falta la fecha de fin" in r.text
    assert notificaciones.recientes(_uid("sofia@correo.bo"))[0]["asunto"] == "Su actividad tiene observaciones"
    # Ya no está por verificar: no se puede verificar otra vez.
    assert actividad.verificar(a["id"], _uid("admin@test.cl")) is False


def test_el_estudiante_no_verifica_ni_entra_a_la_cola(sofia):
    a = _pendiente(sofia)
    r = sofia.post(f"/docencia/cohortes/actividades/{a['id']}/verificar", headers=HX, follow_redirects=False)
    assert r.headers["hx-redirect"] == "/estudiante"
    assert actividad.obtener(a["id"])["estado"] == "pendiente"


def test_dar_acceso_desde_el_tablero(app, carrera):
    filas, _ = importar.leer(CSV.encode())
    importar.aplicar(filas, None)
    r = carrera.post("/docencia/cohortes/accesos", headers=HX, follow_redirects=False)
    assert r.headers["hx-redirect"] == "/docencia/cohortes"
    assert usuarios.por_email("luis@correo.bo") and get_db().q("SELECT COUNT(*) n FROM cuenta_estudiante")[0]["n"] == 2
    assert get_db().q("SELECT detalle FROM auditoria WHERE accion = 'crear_cuentas_estudiantes'")[0]["detalle"] == "2 cuenta(s)"


def test_personas_con_cuenta_siguen_siendo_externas_para_los_selectores(estudiantes_cargados):
    """Tener cuenta de estudiante no la saca de los selectores de tesistas y coautores."""
    ext = _externo("1111111")
    assert get_db().q("SELECT usuario_id FROM persona_externa WHERE id = ?", [ext])[0]["usuario_id"] is None
    assert personas.por_ref(f"e:{ext}")["nombres"] == "Sofía"
