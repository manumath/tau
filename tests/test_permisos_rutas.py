"""Fase 2, paso 3: cada rol, por separado, frente a las pantallas y el menú (matriz de rutas)."""
import pytest

from app.comun import permisos, unidades, usuarios
from app.comun.auth import acceso_admin
from tests.conftest import login

CLAVE = "Clave-roles-1"
PERSONAS = {  # clave → (rol, sigla de la unidad)
    "sistema": ("administracion_sistema", "UMSA"),
    "instituto": ("direccion_instituto", "IIMAT"),
    "carrera": ("direccion_carrera", "CMAT"),
    "comite": ("comite_acreditacion", "UMSA"),
    "datos_cmat": ("gestion_datos", "CMAT"),
    "investigador": (None, None),
}


@pytest.fixture
def cuentas(app):
    ids = {}
    for clave, (rol, sigla) in PERSONAS.items():
        u = usuarios.crear(f"{clave}@test.cl", clave.capitalize(), "Prueba", CLAVE, debe_cambiar_pass=False,
                           es_investigador=rol is None)
        if rol:
            assert permisos.asignar(u["id"], rol, unidades.id_de(sigla)) == []
        ids[clave] = u["id"]
    return ids


def _como(client, clave):
    client.post("/logout")
    assert login(client, f"{clave}@test.cl", CLAVE).headers["hx-redirect"] == "/"
    return client


RUTAS = {  # ruta → quienes reciben 200 (el resto, 403)
    "/admin/usuarios": {"sistema", "instituto", "carrera", "datos_cmat"},
    "/admin/usuarios/nuevo": {"sistema"},
    "/admin/usuarios/importar": {"sistema"},
    "/admin/usuarios/historial": {"carrera"},
    "/admin/auditoria": {"sistema"},
    "/admin/revistas": {"instituto"},
    "/admin/lineas": {"instituto"},
    "/admin/propuestas": {"instituto"},
    "/informes/memoria?anio=2025": {"instituto", "comite"},
    "/informes/acreditacion?desde=2022&hasta=2026": {"instituto", "comite"},
    "/informes/guia-antecedentes": {"instituto", "carrera", "comite"},
    "/docencia/preparacion": {"carrera"},
    "/docencia/cohortes": {"carrera", "datos_cmat", "comite"},
    "/docencia/cohortes/importar": {"carrera", "datos_cmat"},
    "/docencia/cohortes/plantilla": {"carrera", "datos_cmat"},
    "/docencia/cohortes/actividades": {"carrera"},
    "/docencia/encuestas": {"carrera", "datos_cmat", "comite"},
    "/docencia/egresados": {"carrera", "datos_cmat", "comite"},
    "/docencia/egresados/titular": {"carrera"},
    "/personas/externos/duplicados": {"instituto", "datos_cmat"},
}


@pytest.mark.parametrize("clave", list(PERSONAS))
def test_rutas_por_rol(client, cuentas, clave):
    _como(client, clave)
    for ruta, permitidos in RUTAS.items():
        codigo = client.get(ruta).status_code
        esperado = 200 if clave in permitidos else 403
        assert codigo == esperado, (clave, ruta, codigo)
    # Roles: solo Administración del sistema.
    assert client.get(f"/admin/usuarios/{cuentas['investigador']}/roles").status_code == (
        200 if clave == "sistema" else 403)


def test_vinculo_solo_la_direccion_de_carrera(client, cuentas):
    """Categoría y vínculo (cambios, término, carga): solo la Dirección de Carrera."""
    inv = cuentas["investigador"]
    for clave in ("instituto", "carrera", "datos_cmat", "sistema"):
        _como(client, clave)
        assert (client.get(f"/admin/usuarios/{inv}/vinculo").status_code == 200) is (clave == "carrera"), clave
        r = client.get("/admin/usuarios")
        assert ('hx-get="/admin/usuarios/{}/vinculo"'.format(inv) in r.text) is (clave == "carrera"), clave


def test_menu_y_botones_segun_el_rol(client, cuentas):
    r = _como(client, "sistema").get("/admin/usuarios")
    assert "Auditoría" in r.text and "Catálogo de revistas" not in r.text and ">Propuestas<" not in r.text
    assert "Nuevo usuario" in r.text and "Importar historial" not in r.text and "/roles" in r.text
    r = _como(client, "instituto").get("/admin/usuarios")
    assert "Catálogo de revistas" in r.text and "Auditoría" not in r.text
    assert "Nuevo usuario" not in r.text and "Importar historial" not in r.text and "/roles" not in r.text
    assert "Restablecer contraseña" not in r.text  # las acciones de cuenta son de Administración del sistema
    r = _como(client, "comite").get("/")
    assert 'href="/informes"' in r.text and 'href="/admin/usuarios"' not in r.text
    assert _como(client, "comite").get("/informes").status_code == 200
    r = _como(client, "investigador").get("/")
    assert 'href="/admin' not in r.text


def test_rutas_admin_no_previstas_se_deniegan(cuentas):
    """Una ruta /admin nueva que nadie agregó a REGLAS_ADMIN queda cerrada para todos."""
    for clave in PERSONAS:
        assert acceso_admin({"id": cuentas[clave]}, "/admin/informe-nuevo") is False
    assert acceso_admin({"id": cuentas["sistema"]}, "/admin/auditoria") is True


def test_toda_ruta_admin_tiene_regla(app):
    """Cada ruta /admin registrada está cubierta por REGLAS_ADMIN (si no, quedaría cerrada para todos)."""
    import re

    from app.comun.auth import REGLAS_ADMIN
    ejemplo = {"uid": "5", "vid": "7", "aid": "3", "rid": "2", "lid": "4", "iid": "9", "periodo": "2026"}
    sin_regla = []
    for r in app.routes:
        ruta = getattr(r, "path", "")
        if not ruta.startswith("/admin"):
            continue
        concreta = re.sub(r"\{(\w+)(:[^}]*)?\}", lambda m: ejemplo.get(m.group(1), "x"), ruta)
        if not any(re.fullmatch(p, concreta) for p, _ in REGLAS_ADMIN):
            sin_regla.append(ruta)
    assert sin_regla == []
