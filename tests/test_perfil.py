import io

import pytest
from PIL import Image

from app.comun import academicos, fotos, usuarios, vinculos
from app.investigacion import msc, perfiles
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login


@pytest.fixture
def inv(client):
    """Cliente con sesión de la investigadora (contraseña ya definitiva)."""
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    client.uid = uid
    return client


def _imagen(formato="PNG", tam=(800, 600)):
    buf = io.BytesIO()
    Image.new("RGB", tam, (200, 30, 30)).save(buf, formato)
    return buf.getvalue()


# --- Catálogo MSC ------------------------------------------------------------

def test_catalogo_msc_cargado(app):
    n = {r["nivel"]: r["n"] for r in get_db().q("SELECT nivel, COUNT(*) n FROM msc GROUP BY nivel")}
    assert n[1] == 63 and n[2] > 500 and n[3] > 5000
    assert msc.por_codigo("11M06")["texto_plano"].startswith("zeta")


def test_busqueda_msc(app):
    assert msc.buscar("11")[0]["codigo"] == "11-XX"  # lo general primero
    assert "11M06" in [m["codigo"] for m in msc.buscar("zeta")]
    assert [m["codigo"] for m in msc.buscar("graph coloring")] == ["05C15"]
    assert "11-XX" not in [m["codigo"] for m in msc.buscar("11", excluir=("11-XX",))]
    assert msc.buscar("   ") == []


# --- Acceso ------------------------------------------------------------------

def test_perfil_requiere_cuenta_de_investigador(admin):
    assert admin.get("/perfil").status_code == 403


def test_pagina_de_perfil(inv):
    r = inv.get("/perfil")
    assert r.status_code == 200
    assert "Mi perfil" in r.text and "Emmy Noether" in r.text and "0 %" in r.text


# --- Edición en línea --------------------------------------------------------

def test_editar_datos_basicos(inv):
    r = inv.get("/perfil/datos/editar", headers=HX)
    assert r.text.lstrip().startswith("<div") and 'hx-put="/perfil/datos"' in r.text
    assert 'name="cargo"' not in r.text and 'name="unidad"' not in r.text  # se calculan, no se editan
    r = inv.put("/perfil/datos", headers=HX, data=dict(nombres="Amalie Emmy", apellidos="Noether"))
    assert "Amalie Emmy Noether" in r.text and "Sin grados registrados" in r.text
    assert 'id="perfil-completitud"' in r.text and 'hx-swap-oob="true"' in r.text
    p = perfiles.obtener(inv.uid)
    assert (p["nombres"], p["grado"], p["cargo"], p["unidad"]) == ("Amalie Emmy", None, None, "Carrera de Matemática")


def test_datos_invalidos_no_se_guardan(inv):
    r = inv.put("/perfil/datos", headers=HX, data=dict(nombres="", apellidos="Noether"))
    assert "obligatorios" in r.text
    assert perfiles.obtener(inv.uid)["nombres"] == "Emmy"


def test_identificadores_se_normalizan(inv):
    r = inv.put("/perfil/identificadores", headers=HX, data=dict(
        orcid="https://orcid.org/0000-0002-1825-0097", zbmath_id="Noether.Emmy",
        mr_id="MR123"))
    assert "https://orcid.org/0000-0002-1825-0097" in r.text
    p = perfiles.obtener(inv.uid)
    assert (p["orcid"], p["zbmath_id"], p["mr_id"]) == ("0000-0002-1825-0097", "noether.emmy", "123")


def test_identificador_invalido_muestra_error_en_su_campo(inv):
    r = inv.put("/perfil/identificadores", headers=HX,
                data=dict(orcid="0000-0002-1825-0098", mr_id="42"))
    assert "dígito verificador" in r.text and 'value="0000-0002-1825-0098"' in r.text
    assert perfiles.obtener(inv.uid)["mr_id"] is None  # nada se guarda si hay errores


def test_bio_con_latex_y_escapada(inv):
    bio = "Estudio $\\zeta(s)$.\n\n<script>alert(1)</script>"
    r = inv.put("/perfil/bio", headers=HX, data={"bio": bio})
    assert "$\\zeta(s)$" in r.text
    assert "<script>alert" not in r.text and "&lt;script&gt;" in r.text
    assert perfiles.obtener(inv.uid)["bio"] == bio


def test_vista_previa_de_bio(inv):
    r = inv.post("/perfil/bio/vista-previa", headers=HX, data={"bio": "Uno\n\nDos"})
    assert r.text.count("<p") == 2


def test_bio_demasiado_larga(inv):
    r = inv.put("/perfil/bio", headers=HX, data={"bio": "x" * (perfiles.LARGO_BIO + 1)})
    assert "admite hasta" in r.text


# --- Áreas MSC -----------------------------------------------------------------

def test_agregar_areas_la_primera_es_principal(inv):
    inv.post("/perfil/msc", headers=HX, data={"codigo": "11M06"})
    r = inv.post("/perfil/msc", headers=HX, data={"codigo": "11-XX"})
    assert "11M06" in r.text and "11-XX" in r.text
    principal = {a["codigo"]: a["principal"] for a in perfiles.areas(inv.uid)}
    assert principal == {"11M06": 1, "11-XX": 0}


def test_marcar_principal_y_quitar(inv):
    for c in ("11M06", "11-XX", "05C15"):
        perfiles.agregar_area(inv.uid, c)
    inv.post("/perfil/msc/05C15/principal", headers=HX)
    assert perfiles.areas(inv.uid)[0]["codigo"] == "05C15"
    inv.delete("/perfil/msc/05C15", headers=HX)
    areas = perfiles.areas(inv.uid)
    assert [a["codigo"] for a in areas] == ["11M06", "11-XX"] and areas[0]["principal"] == 1


def test_areas_invalidas_duplicadas_y_limite(inv):
    assert "inexistente" in inv.post("/perfil/msc", headers=HX, data={"codigo": "99Z99"}).text
    perfiles.agregar_area(inv.uid, "11M06")
    assert "ya está" in inv.post("/perfil/msc", headers=HX, data={"codigo": "11M06"}).text
    for m in msc.buscar("11", limite=perfiles.MAX_AREAS + 2):
        perfiles.agregar_area(inv.uid, m["codigo"])
    assert len(perfiles.areas(inv.uid)) == perfiles.MAX_AREAS


def test_autocompletar_msc_excluye_las_ya_elegidas(inv):
    perfiles.agregar_area(inv.uid, "11M06")
    r = inv.get("/perfil/msc/buscar", params={"q": "zeta"}, headers=HX)
    assert "11Mxx" in r.text and "11M06" not in r.text
    assert "Number theory ›" in r.text  # muestra la sección a la que pertenece
    assert "Sin resultados" in inv.get("/perfil/msc/buscar", params={"q": "qwertyuiop"}).text


# --- Foto --------------------------------------------------------------------

def test_subir_foto_la_normaliza(inv):
    r = inv.post("/perfil/foto", headers=HX, files={"foto": ("yo.png", _imagen(), "image/png")})
    assert "Cambiar foto" in r.text
    nombre = perfiles.obtener(inv.uid)["foto"]
    img = Image.open(fotos.ruta(nombre))
    assert img.format == "JPEG" and img.size == (fotos.LADO, fotos.LADO)

    r = inv.get(f"/fotos/{inv.uid}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"

    # Al reemplazarla se borra el archivo anterior.
    inv.post("/perfil/foto", headers=HX, files={"foto": ("b.jpg", _imagen("JPEG"), "image/jpeg")})
    assert not fotos.ruta(nombre).exists()


def test_foto_invalida(inv):
    r = inv.post("/perfil/foto", headers=HX, files={"foto": ("x.png", b"no soy imagen", "image/png")})
    assert "no es una imagen válida" in r.text
    assert perfiles.obtener(inv.uid)["foto"] is None


def test_quitar_foto(inv):
    inv.post("/perfil/foto", headers=HX, files={"foto": ("yo.png", _imagen(), "image/png")})
    nombre = perfiles.obtener(inv.uid)["foto"]
    inv.delete("/perfil/foto", headers=HX)
    assert perfiles.obtener(inv.uid)["foto"] is None and not fotos.ruta(nombre).exists()
    assert inv.get(f"/fotos/{inv.uid}").status_code == 404


def test_fotos_requieren_sesion(inv, app):
    inv.post("/perfil/foto", headers=HX, files={"foto": ("yo.png", _imagen(), "image/png")})
    inv.post("/logout")
    r = inv.get(f"/fotos/{inv.uid}", follow_redirects=False)
    assert r.status_code == 303


# --- Completitud y directorio ---------------------------------------------------

def test_completitud(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    assert perfiles.completitud(perfiles.obtener(uid), 0)[0] == 0
    academicos.agregar_grado(uid, {"nivel": "doctorado"})
    perfiles.actualizar_campos(uid, orcid="0000-0002-1825-0097")
    pct, faltan = perfiles.completitud(perfiles.obtener(uid), 1)
    assert pct == 50 and "ORCID" not in faltan and "áreas MSC" not in faltan


def test_directorio_busca_por_nombre_unidad_y_area_sin_tildes(inv):
    vinculos.agregar(inv.uid, "titular", "2015-01-01", carga={
        "horas": 128, "actividades": {"docencia": 64, "investigacion": 32, "extension": 32, "gestion": 0, "otras": 0},
        "detalles": {"extension": "Seminario de Álgebra"}})
    perfiles.agregar_area(inv.uid, "13E05")
    nombres = lambda q: [d["apellidos"] for d in perfiles.directorio(q)]  # noqa: E731
    assert nombres("") == ["Noether"]              # el admin sin perfil no aparece
    assert nombres("NOETHER") == ["Noether"]
    assert nombres("algebra") == ["Noether"]       # sin tilde encuentra «Álgebra»
    assert nombres("13E") == ["Noether"] and nombres("noetherian") == ["Noether"]
    assert nombres("topology") == []
    assert nombres("docente investigador") == ["Noether"]  # por el cargo calculado
    r = inv.get("/investigadores/resultados", params={"q": "13E"}, headers=HX)
    assert "Noether" in r.text and "13E05" in r.text


def test_directorio_oculta_cuentas_inactivas(inv):
    otro = usuarios.crear("otro@test.cl", "Alan", "Turing", "x" * 12)
    usuarios.set_activo(otro["id"], False)
    assert [d["apellidos"] for d in perfiles.directorio()] == ["Noether"]
    assert inv.get(f"/investigadores/{otro['id']}").status_code == 404


def test_perfil_de_otro_es_solo_lectura(inv):
    otro = usuarios.crear("otro@test.cl", "Alan", "Turing", "x" * 12)
    perfiles.actualizar_campos(otro["id"], orcid="0000-0002-1825-0097")
    r = inv.get(f"/investigadores/{otro['id']}")
    assert "Alan Turing" in r.text and "https://orcid.org/0000-0002-1825-0097" in r.text
    assert "Editar mi perfil" not in r.text and "hx-put" not in r.text
    assert "Editar mi perfil" in inv.get(f"/investigadores/{inv.uid}").text


def test_rutas_con_extension_no_saltan_la_autenticacion(client):
    r = client.get("/fotos/1.png", follow_redirects=False)
    assert r.status_code in (303, 404) and r.status_code != 200
    assert client.get("/investigadores", follow_redirects=False).status_code == 303
