"""Filiación y pertenencia, etapa E1: historial de vínculo con el instituto."""
import base64
from datetime import date

import pytest

from app.investigacion import actividades, perfiles, productos
from app import importar_usuarios, importar_vinculos, usuarios, vinculos
from app.acreditacion import informes
from app.db import get_db
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login


@pytest.fixture
def emmy(app):
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    return uid


@pytest.fixture
def hoy(monkeypatch):
    def fijar(iso):
        monkeypatch.setattr(vinculos, "hoy", lambda: date.fromisoformat(iso))
    fijar("2026-09-25")
    return fijar


def _producto(uid, titulo, anio, mes=None):
    tipo = get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Artículo en revista'")[0]["id"]
    d, errores = productos.preparar(dict(tipo_id=str(tipo), titulo=titulo, anio=str(anio), mes=str(mes or ""),
                                         estado_publicacion="publicado", revision="arbitrado"), [f"i:{uid}"], [])
    assert not errores
    return productos.guardar(d, [f"i:{uid}"], uid, filiaciones=[1])


# --- Modelo ------------------------------------------------------------------------------------------

def test_periodos_y_superposicion(emmy, hoy):
    assert vinculos.agregar(emmy, "contratado", "2018-03-01", "2021-12-31", 40) == []
    assert vinculos.agregar(emmy, "titular", "2022-01-01") == []
    assert "Se superpone" in vinculos.agregar(emmy, "interino", "2021-06-01", "2022-02-01")[0]
    assert "anterior a la de inicio" in vinculos.agregar(emmy, "interino", "2010-02-01", "2010-01-01")[0]
    assert "Categoría no válida" in vinculos.agregar(emmy, "emerito", "2000-01-01", "2000-12-31")[0]
    assert vinculos.vigente(emmy)["categoria"] == "titular"
    assert perfiles.obtener(emmy)["categoria"] == "titular"  # se sincroniza la categoría actual
    assert vinculos.en_fecha(emmy, 2019, 5) == ("si", "contratado")
    assert vinculos.en_fecha(emmy, 2017) == ("no", None)
    assert vinculos.en_fecha(emmy, 2018) == ("dudoso", "contratado")  # desde marzo
    assert vinculos.en_fecha(emmy, 2023) == ("si", "titular")
    assert vinculos.en_dia(emmy, "2021-12-31") == ("si", "contratado")
    assert vinculos.resumen(emmy) == "En el instituto desde 2018 · Titular desde 2022"


def test_cambio_de_categoria_y_termino(emmy, hoy):
    vinculos.agregar(emmy, "interino", "2024-02-01", jornada=20)
    assert vinculos.cambiar_categoria(emmy, "contratado", "2024-01-01") == [
        "La fecha debe ser posterior al inicio del periodo vigente."]
    assert vinculos.cambiar_categoria(emmy, "contratado", "2025-03-01") == []
    periodos = vinculos.listar(emmy)
    assert [(v["categoria"], v["fecha_inicio"], v["fecha_fin"], v["jornada_horas"]) for v in periodos] == [
        ("interino", "2024-02-01", "2025-02-28", 20), ("contratado", "2025-03-01", None, 20)]
    assert vinculos.terminar(emmy, "2026-06-30") == []
    assert vinculos.vigente(emmy) is None and perfiles.obtener(emmy)["categoria"] is None
    assert vinculos.resumen(emmy) is None


def test_termino_futuro_deja_de_estar_vigente_con_el_tiempo(emmy, hoy):
    vinculos.agregar(emmy, "invitado", "2026-01-01", "2026-12-31")
    assert perfiles.obtener(emmy)["categoria"] == "invitado"
    hoy("2027-01-02")
    vinculos.sincronizar_categoria()
    assert perfiles.obtener(emmy)["categoria"] is None


def test_cuenta_nueva_con_categoria_y_fecha_de_ingreso(app, hoy):
    uid = usuarios.crear("a@test.cl", "Ana", "Uno", PASS_TEMP, categoria="titular", fecha_ingreso="2020-03-01")["id"]
    assert [(v["categoria"], v["fecha_inicio"]) for v in vinculos.listar(uid)] == [("titular", "2020-03-01")]
    # La corrección de categoría (sin fecha) cambia el periodo vigente, no agrega otro.
    perfiles.cambiar_categoria(uid, "contratado")
    assert [(v["categoria"], v["fecha_inicio"]) for v in vinculos.listar(uid)] == [("contratado", "2020-03-01")]


# --- Administración ------------------------------------------------------------------------------------

def test_ventana_de_vinculo(admin, emmy, hoy):
    r = admin.get(f"/admin/usuarios/{emmy}/vinculo", headers=HX)
    assert "Sin periodos registrados" in r.text and "Agregar un periodo" in r.text
    r = admin.post(f"/admin/usuarios/{emmy}/vinculo/periodo", headers=HX,
                   data={"categoria": "contratado", "desde": "2019-03-01", "jornada": "40", "nota": "Contrato 1"})
    assert "Contratado(a)" in r.text and "vigente" in r.text and 'hx-swap-oob="true"' in r.text
    r = admin.post(f"/admin/usuarios/{emmy}/vinculo/cambio", headers=HX, data={"categoria": "titular", "desde": "2023-01-01"})
    assert [v["categoria"] for v in vinculos.listar(emmy)] == ["contratado", "titular"]
    r = admin.post(f"/admin/usuarios/{emmy}/vinculo/periodo", headers=HX,
                   data={"categoria": "invitado", "desde": "2020-01-01", "hasta": "2020-06-30"})
    assert "Se superpone" in r.text and 'value="2020-06-30"' in r.text  # conserva lo escrito
    v = vinculos.listar(emmy)[0]
    admin.put(f"/admin/usuarios/vinculo/{v['id']}", headers=HX,
              data={"categoria": "contratado", "desde": "2019-04-01", "hasta": "2022-12-31", "jornada": "40"})
    assert vinculos.listar(emmy)[0]["fecha_inicio"] == "2019-04-01"
    admin.post(f"/admin/usuarios/{emmy}/vinculo/termino", headers=HX, data={"fecha": "2026-08-31"})
    assert vinculos.vigente(emmy) is None
    admin.delete(f"/admin/usuarios/vinculo/{v['id']}", headers=HX)
    assert len(vinculos.listar(emmy)) == 1
    acciones = {f["accion"] for f in get_db().q("SELECT accion FROM auditoria")}
    assert {"agregar_vinculo", "cambiar_categoria", "corregir_vinculo", "terminar_vinculo", "eliminar_vinculo"} <= acciones


def test_solo_admin_gestiona_vinculos(client, emmy):
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get(f"/admin/usuarios/{emmy}/vinculo", headers=HX).status_code == 403
    assert client.post(f"/admin/usuarios/{emmy}/vinculo/periodo", headers=HX,
                       data={"categoria": "titular", "desde": "2020-01-01"}).status_code == 403


def test_desactivar_pregunta_por_el_vinculo(admin, emmy, hoy):
    vinculos.agregar(emmy, "titular", "2019-01-01")
    fila = admin.get("/admin/usuarios").text
    assert f"/admin/usuarios/{emmy}/desactivar" in fila
    assert "Terminar también su vínculo" in admin.get(f"/admin/usuarios/{emmy}/desactivar", headers=HX).text
    r = admin.post(f"/admin/usuarios/{emmy}/activo", headers=HX, data={"termina": "si", "fecha": "2018-01-01"})
    assert r.headers["hx-retarget"] == "#modal" and "anterior al inicio" in r.text
    assert usuarios.por_id(emmy)["activo"]
    admin.post(f"/admin/usuarios/{emmy}/activo", headers=HX, data={"termina": "si", "fecha": "2026-09-30"})
    assert not usuarios.por_id(emmy)["activo"] and vinculos.listar(emmy)[0]["fecha_fin"] == "2026-09-30"
    # Reactivar no cambia el vínculo; desactivar sin terminarlo tampoco.
    admin.post(f"/admin/usuarios/{emmy}/activo", headers=HX)
    vinculos.editar(vinculos.listar(emmy)[0]["id"], "titular", "2019-01-01", None)
    admin.post(f"/admin/usuarios/{emmy}/activo", headers=HX, data={"termina": "no"})
    assert not usuarios.por_id(emmy)["activo"] and vinculos.vigente(emmy)


def test_alta_con_fecha_de_ingreso(admin, hoy):
    admin.post("/admin/usuarios", headers=HX, data={"nombres": "Carl", "apellidos": "Gauss", "email": "g@test.cl",
                                                    "es_investigador": "on", "categoria": "interino",
                                                    "fecha_ingreso": "2025-08-01"})
    uid = usuarios.por_email("g@test.cl")["id"]
    assert vinculos.listar(uid)[0]["fecha_inicio"] == "2025-08-01"


# --- CSV ----------------------------------------------------------------------------------------------------

HISTORIAL = ("Correo;Categoría;Fecha de ingreso;Término;Jornada;Nota\n"
             "inv@test.cl;contratada;01/03/2018;31/12/2021;40;Contrato\n"
             "inv@test.cl;titular;2022-01-01;;40;Res. 345/2021\n"
             "otro@test.cl;titular;2020-01-01;;;\n"
             "alan@test.cl;interino;2020-01-01;2021-01-01;;\n"
             "alan@test.cl;contratado;2020-06-01;;;\n"
             "alan@test.cl;emérito;31/02/2020;;99;\n")


def test_leer_historial(emmy):
    usuarios.crear("alan@test.cl", "Alan", "Turing", PASS_TEMP)
    personas, errores = importar_vinculos.leer(HISTORIAL.encode())
    assert not errores
    p = {x["email"]: x for x in personas}
    assert p["inv@test.cl"]["errores"] == [] and [x["desde"] for x in p["inv@test.cl"]["periodos"]] == [
        "2018-03-01", "2022-01-01"]
    assert "No hay una cuenta" in p["otro@test.cl"]["errores"][0]
    assert any("categoría no válida" in e and "fecha no válida" in e and "jornada" in e for e in p["alan@test.cl"]["errores"])
    assert any("se superponen" in e for e in p["alan@test.cl"]["errores"])


def test_importar_historial_reemplaza(admin, emmy, hoy):
    vinculos.agregar(emmy, "invitado")  # lo que había: se reemplaza
    contenido = base64.b64encode(HISTORIAL.encode()).decode()
    r = admin.post("/admin/usuarios/historial/revisar", headers=HX,
                   files={"archivo": ("h.csv", HISTORIAL.encode(), "text/csv")})
    assert "Reemplaza 1 periodo(s) actual(es)" in r.text and "Actualizar 1 persona(s)" in r.text
    admin.post("/admin/usuarios/historial/confirmar", headers=HX, data={"contenido": contenido})
    assert [(v["categoria"], v["fecha_inicio"], v["fecha_fin"], v["nota"]) for v in vinculos.listar(emmy)] == [
        ("contratado", "2018-03-01", "2021-12-31", "Contrato"), ("titular", "2022-01-01", None, "Res. 345/2021")]
    assert perfiles.obtener(emmy)["categoria"] == "titular"


def test_csv_de_cuentas_con_fecha_de_ingreso(app, hoy):
    filas, _ = importar_usuarios.leer(b"email,nombres,apellidos,categoria,fecha de ingreso\n"
                                      b"a@test.cl,Ana,Uno,titular,15/03/2021\nb@test.cl,Bea,Dos,titular,ayer\n")
    assert filas[0]["fecha_ingreso"] == "2021-03-15" and filas[1]["estado"] == "error"
    importar_usuarios.crear(filas, False, usuarios.por_email("admin@test.cl")["id"], None)
    assert vinculos.listar(usuarios.por_email("a@test.cl")["id"])[0]["fecha_inicio"] == "2021-03-15"


# --- Informes -------------------------------------------------------------------------------------------------

def test_memoria_cuenta_solo_con_vinculo_en_la_fecha(emmy, hoy):
    vinculos.agregar(emmy, "contratado", "2025-03-01", "2025-12-31")
    vinculos.agregar(emmy, "titular", "2026-01-01")
    _producto(emmy, "Antes del ingreso", 2025, 1)
    _producto(emmy, "Contratada", 2025, 6)
    _producto(emmy, "Sin mes, año parcial", 2025)
    _producto(emmy, "Titular", 2026, 2)
    tipo = get_db().q("SELECT id FROM tipo_actividad ORDER BY orden LIMIT 1")[0]["id"]
    for titulo, fecha in (("Charla previa", "2025-02-10"), ("Charla", "2025-04-10")):
        actividades.guardar(dict(tipo_id=tipo, titulo=titulo, fecha_inicio=fecha, fecha_fin=None,
                                 modalidad="presencial", ambito="nacional"), [(f"i:{emmy}", "expositor")], emmy)

    m = informes.memoria(2025)
    assert [p["titulo"] for p in m["productos"]] == ["Contratada"]
    assert [(p["titulo"], p["motivo"]) for p in m["por_confirmar"]] == [
        ("Sin mes, año parcial", "el vínculo del autor cubre solo parte del año: indique el mes")]
    assert [a["titulo"] for a in m["actividades"]] == ["Charla"]
    assert m["por_categoria"]["Contratado(a)"]["productos"] == 1
    # Categoría a la fecha: el producto de 2026 cuenta como de titular.
    m26 = informes.memoria(2026)
    assert m26["por_categoria"]["Titular"]["productos"] == 1 and "Contratado(a)" not in m26["por_categoria"]
    # Producción anterior al ingreso: sigue en el perfil y el CV.
    assert "Antes del ingreso" in {p["titulo"] for p in productos.de_investigador(emmy)}


def test_memoria_incluye_a_quienes_ya_no_estan_y_advierte(emmy, hoy):
    vinculos.agregar(emmy, "titular", "2024-01-01", "2026-06-30")
    _producto(emmy, "Último artículo", 2026, 5)
    sin = usuarios.crear("s@test.cl", "Sin", "Vínculo", PASS_TEMP)["id"]
    _producto(sin, "De alguien sin vínculo", 2026, 5)
    nuevo = usuarios.crear("n@test.cl", "Nuevo", "Sinfecha", PASS_TEMP, categoria="invitado")["id"]
    assert vinculos.listar(nuevo)[0]["fecha_inicio"] is None

    m = informes.memoria(2026)
    assert [p["titulo"] for p in m["productos"]] == ["Último artículo"]
    fila = next(x for x in m["por_investigador"] if x["apellidos"] == "Noether")
    assert (fila["productos"], fila["hasta"]) == (1, "2026-06-30")
    assert any("Sin fecha de ingreso" in a and "Nuevo Sinfecha" in a for a in m["avisos"])
    assert any("Sin vínculo registrado" in a and "Sin Vínculo" in a for a in m["avisos"])


def test_perfil_muestra_el_vinculo(client, emmy, hoy):
    vinculos.agregar(emmy, "titular", "2019-05-01")
    login(client, "inv@test.cl", PASS_TEMP)
    assert "En el instituto desde 2019" in client.get("/perfil").text
    login(client, "admin@test.cl", PASS_ADMIN)
