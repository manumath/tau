import re

import pytest

from app.investigacion import actividades, productos, proyectos
from app.comun import personas, usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login

CLAVE = "Clave-colega-1"


@pytest.fixture
def gente(app):
    """Responsable (Emmy), participante (Alan) y ajena (Sofía), con contraseñas definitivas."""
    emmy = usuarios.por_email("inv@test.cl")
    usuarios.cambiar_password(emmy["id"], PASS_TEMP, temporal=False)
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", CLAVE, debe_cambiar_pass=False)
    sofia = usuarios.crear("sofia@test.cl", "Sofía", "Kovalévskaya", CLAVE, debe_cambiar_pass=False)
    admin = usuarios.por_email("admin@test.cl")
    return {"emmy": emmy["id"], "alan": alan["id"], "sofia": sofia["id"], "admin": admin["id"]}


@pytest.fixture
def proyecto(gente):
    pid = proyectos.crear(dict(nombre="Álgebra y computación", codigo="F-1", estado="vigente",
                               fecha_inicio="2026-01-01"), gente["emmy"], gente["admin"])
    proyectos.agregar_participante(pid, f"i:{gente['alan']}", "co_investigador", True)
    return pid


def entrar(client, quien):
    client.post("/logout")
    email = {"emmy": "inv@test.cl", "alan": "alan@test.cl", "sofia": "sofia@test.cl",
             "admin": "admin@test.cl"}[quien]
    clave = {"emmy": PASS_TEMP, "admin": PASS_ADMIN}.get(quien, CLAVE)
    assert login(client, email, clave).headers["hx-redirect"] == "/"
    return client


def _producto(uid, titulo="Invariantes", **extra):
    tipo = get_db().q("SELECT id FROM tipo_producto WHERE nombre = 'Artículo en revista'")[0]["id"]
    return dict(tipo_id=str(tipo), titulo=titulo, anio="2026", estado_publicacion="publicado",
                revision="arbitrado", autor=[f"i:{uid}"], **extra)


def _pid_producto(titulo):
    return get_db().q("SELECT id FROM producto WHERE titulo = ?", [titulo])[0]["id"]


# --- Creación y acceso ---------------------------------------------------------------------------

def test_investigador_crea_proyecto_individual_y_queda_responsable(client, gente):
    entrar(client, "alan")
    assert "Nuevo proyecto individual" in client.get("/proyectos").text
    r = client.post("/proyectos", headers=HX, data=dict(nombre="Nuevo", estado="vigente",
                                                         responsable_id=str(gente["emmy"])))
    pid = int(r.headers["hx-redirect"].rsplit("/", 1)[1])
    # El responsable es quien lo crea (se ignora cualquier otro valor enviado).
    assert proyectos.rol_de(pid, gente["alan"]) == "responsable"
    assert proyectos.rol_de(pid, gente["emmy"]) is None
    assert proyectos.obtener(pid)["tipo"] == "individual"


def test_admin_sin_perfil_de_investigador_no_crea_proyectos(client, gente):
    entrar(client, "admin")
    assert "Nuevo proyecto" not in client.get("/proyectos").text
    assert client.get("/proyectos/nuevo", headers=HX).status_code == 403
    assert client.post("/proyectos", headers=HX, data=dict(nombre="X", estado="vigente")).status_code == 403


def test_validacion_de_proyecto(client, gente):
    entrar(client, "emmy")
    r = client.post("/proyectos", headers=HX, data=dict(nombre="", estado="vigente", monto="12,5 millones",
                                                         fecha_inicio="2026-05-01", fecha_fin="2026-01-01"))
    for texto in ("obligatorio", "número entero", "anterior"):
        assert texto in r.text


def test_solo_participantes_ven_el_proyecto(client, proyecto):
    entrar(client, "sofia")
    assert "no participa" in client.get(f"/proyectos/{proyecto}").text
    assert client.get(f"/proyectos/{proyecto}/tab/participantes", headers=HX).status_code == 404
    entrar(client, "alan")
    r = client.get(f"/proyectos/{proyecto}")
    assert "Álgebra y computación" in r.text and "Pendientes" not in r.text  # no es responsable
    entrar(client, "admin")
    r = client.get(f"/proyectos/{proyecto}")
    # La administración lo ve, pero no lo gestiona: sin bandeja ni edición; sí puede reasignar.
    assert "Álgebra y computación" in r.text and "Pendientes" not in r.text
    assert "Reasignar responsable" in r.text


def test_admin_no_gestiona_proyectos(client, gente, proyecto):
    entrar(client, "admin")
    assert client.get(f"/proyectos/{proyecto}/datos/editar", headers=HX).status_code == 403
    assert client.post(f"/proyectos/{proyecto}/participantes", headers=HX,
                       data={"ref": f"i:{gente['sofia']}"}).status_code == 403
    assert client.post(f"/proyectos/{proyecto}/objetivos", headers=HX, data={"texto": "x"}).status_code == 403


def test_reasignar_responsable(client, gente, proyecto):
    entrar(client, "emmy")
    assert "Reasignar responsable" not in client.get(f"/proyectos/{proyecto}").text
    assert client.post(f"/proyectos/{proyecto}/responsable", headers=HX,
                       data={"nuevo": gente["alan"]}).status_code == 403
    entrar(client, "admin")
    r = client.post(f"/proyectos/{proyecto}/responsable", headers=HX, data={"nuevo": ""})
    assert "Seleccione al nuevo responsable" in r.text
    # Alan ya participa: pasa a responsable; Emmy sigue como co-investigadora.
    r = client.post(f"/proyectos/{proyecto}/responsable", headers=HX,
                    data={"nuevo": gente["alan"], "anterior": "co_investigador"})
    assert r.headers["hx-redirect"] == f"/proyectos/{proyecto}?tab=participantes"
    assert proyectos.rol_de(proyecto, gente["alan"]) == "responsable"
    assert proyectos.rol_de(proyecto, gente["emmy"]) == "co_investigador"
    # Sofía no participa: entra como responsable y Alan queda dado de baja.
    client.post(f"/proyectos/{proyecto}/responsable", headers=HX,
                data={"nuevo": gente["sofia"], "anterior": "baja"})
    assert proyectos.rol_de(proyecto, gente["sofia"]) == "responsable"
    alan = next(x for x in proyectos.participantes(proyecto) if x["interno"] and x["id"] == gente["alan"])
    assert alan["rol"] == "co_investigador" and alan["fecha_hasta"] is not None  # hoy es su último día
    assert [r["apellidos"] for r in proyectos.responsables(proyecto)] == ["Kovalévskaya"]
    assert get_db().q("SELECT COUNT(*) n FROM auditoria WHERE accion = 'reasignar_responsable'")[0]["n"] == 2


def test_listado_de_admin_filtra_por_tipo(client, gente, proyecto):
    inst = proyectos.crear(dict(nombre="Proyecto institucional", estado="vigente"), gente["sofia"],
                           gente["sofia"], tipo="institucional")
    entrar(client, "admin")
    todos = client.get("/proyectos").text
    assert "Álgebra y computación" in todos and "Proyecto institucional" in todos
    solo = client.get("/proyectos?tipo=institucional").text
    assert "Proyecto institucional" in solo and "Álgebra y computación" not in solo
    assert proyectos.obtener(inst)["tipo"] == "institucional"
    with pytest.raises(ValueError):
        proyectos.crear(dict(nombre="X", estado="vigente"), gente["sofia"], gente["sofia"], tipo="otro")


def test_pestanas_fijan_la_url(client, proyecto):
    entrar(client, "emmy")
    r = client.get(f"/proyectos/{proyecto}/tab/participantes", headers=HX)
    assert r.headers["hx-replace-url"] == f"/proyectos/{proyecto}?tab=participantes"
    assert "Alan Turing" in r.text


# --- Participantes ---------------------------------------------------------------------------------

def test_responsable_gestiona_participantes_pero_no_asigna_responsables(client, gente, proyecto):
    entrar(client, "emmy")
    client.post(f"/proyectos/{proyecto}/participantes", headers=HX, data={"ref": f"i:{gente['sofia']}"})
    assert proyectos.rol_de(proyecto, gente["sofia"]) == "co_investigador"
    part = next(x for x in proyectos.participantes(proyecto) if x.get("id") == gente["sofia"] and x["interno"])
    client.post(f"/proyectos/{proyecto}/participantes/{part['participante_id']}/rol", headers=HX,
                data={"rol": "responsable"})
    assert proyectos.rol_de(proyecto, gente["sofia"]) == "co_investigador"
    client.post(f"/proyectos/{proyecto}/participantes/{part['participante_id']}/rol", headers=HX,
                data={"rol": "co_responsable"})
    assert proyectos.rol_de(proyecto, gente["sofia"]) == "co_responsable"


def test_participante_no_gestiona(client, gente, proyecto):
    entrar(client, "alan")
    r = client.post(f"/proyectos/{proyecto}/participantes", headers=HX, data={"ref": f"i:{gente['sofia']}"})
    assert r.status_code == 403 and proyectos.rol_de(proyecto, gente["sofia"]) is None


def test_siempre_queda_un_responsable(gente, proyecto):
    resp = proyectos.responsables(proyecto)[0]
    assert "al menos un responsable" in proyectos.cambiar_rol(proyecto, resp["participante_id"],
                                                              "co_investigador", True)
    assert "al menos un responsable" in proyectos.dar_de_baja(proyecto, resp["participante_id"], True)


def test_externos_no_pueden_ser_responsables(gente, proyecto):
    weyl = personas.crear_externo("Hermann", "Weyl", "IAS", None, gente["emmy"])
    assert "cuenta" in proyectos.agregar_participante(proyecto, f"e:{weyl['id']}", "co_responsable", True)
    assert proyectos.agregar_participante(proyecto, f"e:{weyl['id']}", "colaborador", False) is None
    assert "ya participa" in proyectos.agregar_participante(proyecto, f"e:{weyl['id']}", "tesista", False)


def test_alta_de_externo_desde_el_proyecto(client, proyecto):
    entrar(client, "emmy")
    client.post(f"/proyectos/{proyecto}/participantes/externo", headers=HX,
                data=dict(ext_nombres="Hermann", ext_apellidos="Weyl", ext_institucion="IAS"))
    assert any(x["apellidos"] == "Weyl" and x["rol"] == "colaborador" for x in proyectos.participantes(proyecto))


# --- Flujo de propuestas ------------------------------------------------------------------------------

def test_participante_propone_y_queda_pendiente(client, gente, proyecto):
    entrar(client, "alan")
    r = client.post("/productos", headers=HX, data=_producto(gente["alan"], proyecto=[str(proyecto)]))
    assert "pendientes-cambiados" in r.headers["hx-trigger"]
    pid = _pid_producto("Invariantes")
    assert proyectos.vinculo("producto", pid, proyecto)["estado"] == "pendiente"
    assert proyectos.registros(proyecto, "producto") == []  # aún no forma parte del proyecto
    assert proyectos.n_pendientes_para({"id": gente["emmy"]}) == 1
    entrar(client, "emmy")
    r = client.get("/proyectos/pendientes/contador", headers=HX)
    assert ">1<" in r.text and "load" not in r.text  # el reemplazo no vuelve a dispararse solo


def test_responsable_vincula_directo(client, gente, proyecto):
    entrar(client, "emmy")
    client.post("/productos", headers=HX, data=_producto(gente["emmy"], proyecto=[str(proyecto)]))
    assert proyectos.vinculo("producto", _pid_producto("Invariantes"), proyecto)["estado"] == "aprobado"


def test_ajeno_no_puede_proponer(client, gente, proyecto):
    entrar(client, "sofia")
    client.post("/productos", headers=HX, data=_producto(gente["sofia"], proyecto=[str(proyecto)]))
    assert proyectos.vinculos_de("producto", _pid_producto("Invariantes")) == []


def test_aprobar(client, gente, proyecto):
    entrar(client, "alan")
    client.post("/productos", headers=HX, data=_producto(gente["alan"], proyecto=[str(proyecto)]))
    pid = _pid_producto("Invariantes")
    assert client.post(f"/proyectos/{proyecto}/pendientes/producto/{pid}/aprobar", headers=HX).status_code == 403
    entrar(client, "emmy")
    r = client.post(f"/proyectos/{proyecto}/pendientes/producto/{pid}/aprobar", headers=HX)
    assert "No hay propuestas pendientes" in r.text
    assert 'id="contador-pestana-pendientes"' in r.text and r.headers["hx-trigger"] == "pendientes-cambiados"
    assert [x["registro_id"] for x in proyectos.registros(proyecto, "producto")] == [pid]


def test_rechazar_exige_motivo_y_se_puede_volver_a_proponer(client, gente, proyecto):
    entrar(client, "alan")
    client.post("/productos", headers=HX, data=_producto(gente["alan"], proyecto=[str(proyecto)]))
    pid = _pid_producto("Invariantes")
    entrar(client, "emmy")
    client.post(f"/proyectos/{proyecto}/pendientes/producto/{pid}/rechazar", headers=HX, data={"comentario": " "})
    assert proyectos.vinculo("producto", pid, proyecto)["estado"] == "pendiente"
    client.post(f"/proyectos/{proyecto}/pendientes/producto/{pid}/rechazar", headers=HX,
                data={"comentario": "Falta el agradecimiento al proyecto."})
    v = proyectos.vinculo("producto", pid, proyecto)
    assert v["estado"] == "rechazado" and v["comentario"] == "Falta el agradecimiento al proyecto."
    # Quien propuso lo ve con el motivo…
    entrar(client, "alan")
    assert "Falta el agradecimiento" in client.get("/proyectos").text
    # …y al guardar con la casilla marcada, vuelve a quedar pendiente.
    client.put(f"/productos/{pid}", headers=HX, data=_producto(gente["alan"], proyecto=[str(proyecto)]))
    v = proyectos.vinculo("producto", pid, proyecto)
    assert v["estado"] == "pendiente" and v["comentario"] is None


def test_retirar_propuesta_pendiente_pero_no_la_aprobada(client, gente, proyecto):
    entrar(client, "alan")
    client.post("/productos", headers=HX, data=_producto(gente["alan"], proyecto=[str(proyecto)]))
    pid = _pid_producto("Invariantes")
    client.put(f"/productos/{pid}", headers=HX, data=_producto(gente["alan"]))  # desmarcada
    assert proyectos.vinculo("producto", pid, proyecto) is None
    client.put(f"/productos/{pid}", headers=HX, data=_producto(gente["alan"], proyecto=[str(proyecto)]))
    proyectos.aprobar("producto", pid, proyecto, gente["emmy"])
    client.put(f"/productos/{pid}", headers=HX, data=_producto(gente["alan"]))  # desmarcada otra vez
    assert proyectos.vinculo("producto", pid, proyecto)["estado"] == "aprobado"


def test_actividad_aprobada_con_responsable_del_proyecto(client, gente, proyecto):
    entrar(client, "alan")
    tipo = get_db().q("SELECT id FROM tipo_actividad WHERE nombre = 'Seminario'")[0]["id"]
    client.post("/actividades", headers=HX, data=dict(
        tipo_id=str(tipo), titulo="Seminario del proyecto", fecha_inicio="2026-04-01",
        modalidad="presencial", ambito="local", participante=[f"i:{gente['alan']}"], rol=["expositor"],
        proyecto=[str(proyecto)]))
    aid = actividades.de_investigador(gente["alan"])[0]["id"]
    part_alan = next(x["participante_id"] for x in proyectos.participantes(proyecto)
                     if x["interno"] and x["id"] == gente["alan"])
    entrar(client, "emmy")
    # Un participante de otro proyecto no puede ser responsable de la actividad.
    otro = proyectos.crear(dict(nombre="Otro", estado="vigente"), gente["sofia"], gente["admin"])
    ajeno = proyectos.participantes(otro)[0]["participante_id"]
    assert "participante del proyecto" in proyectos.aprobar("actividad", aid, proyecto, gente["emmy"], ajeno)
    client.post(f"/proyectos/{proyecto}/pendientes/actividad/{aid}/aprobar", headers=HX,
                data={"responsable": str(part_alan)})
    v = proyectos.vinculo("actividad", aid, proyecto)
    assert v["estado"] == "aprobado" and v["responsable_participante_id"] == part_alan
    assert "Seminario del proyecto" in client.get(f"/proyectos/{proyecto}/tab/actividades", headers=HX).text


def test_baja_conserva_lo_aprobado_e_impide_nuevas_propuestas(client, gente, proyecto):
    entrar(client, "alan")
    client.post("/productos", headers=HX, data=_producto(gente["alan"], proyecto=[str(proyecto)]))
    pid = _pid_producto("Invariantes")
    proyectos.aprobar("producto", pid, proyecto, gente["emmy"])
    part_alan = next(x["participante_id"] for x in proyectos.participantes(proyecto)
                     if x["interno"] and x["id"] == gente["alan"])
    get_db().execute("UPDATE proyecto_participante SET fecha_hasta = date('now', 'localtime', '-1 day') WHERE id = ?",
                     [part_alan])
    assert proyectos.registros(proyecto, "producto")[0]["registro_id"] == pid
    client.post("/productos", headers=HX, data=_producto(gente["alan"], titulo="Otro", proyecto=[str(proyecto)]))
    assert proyectos.vinculos_de("producto", _pid_producto("Otro")) == []
    assert proyectos.para_proponer(gente["alan"]) == []
    assert "Vincular a proyectos" not in client.get("/productos/nuevo", headers=HX).text


def test_editado_despues_de_aprobado(client, gente, proyecto):
    entrar(client, "alan")
    client.post("/productos", headers=HX, data=_producto(gente["alan"], proyecto=[str(proyecto)]))
    pid = _pid_producto("Invariantes")
    proyectos.aprobar("producto", pid, proyecto, gente["emmy"])
    get_db().execute("UPDATE producto_proyecto SET revisado_en = datetime('now', '-1 hour')")
    client.put(f"/productos/{pid}", headers=HX, data=_producto(gente["alan"], titulo="Invariantes (v2)",
                                                                proyecto=[str(proyecto)]))
    assert proyectos.registros(proyecto, "producto")[0]["editado_despues"]
    entrar(client, "emmy")
    assert "Editados después de aprobados" in client.get(f"/proyectos/{proyecto}").text


def test_desvincular_solo_responsable(client, gente, proyecto):
    entrar(client, "emmy")
    client.post("/productos", headers=HX, data=_producto(gente["emmy"], proyecto=[str(proyecto)]))
    pid = _pid_producto("Invariantes")
    entrar(client, "alan")
    assert client.post(f"/proyectos/{proyecto}/producto/{pid}/desvincular", headers=HX).status_code == 403
    entrar(client, "emmy")
    client.post(f"/proyectos/{proyecto}/producto/{pid}/desvincular", headers=HX)
    assert proyectos.vinculo("producto", pid, proyecto) is None
    assert productos.obtener(pid) is not None  # el producto sigue existiendo


def test_casillas_en_el_formulario(client, gente, proyecto):
    entrar(client, "alan")
    r = client.get(f"/productos/nuevo?proyecto={proyecto}", headers=HX)
    assert "Vincular a proyectos" in r.text and "quedará pendiente" in r.text
    casilla = re.search(r'<input[^>]*name="proyecto"[^>]*>', r.text).group(0)
    assert f'value="{proyecto}"' in casilla and "checked" in casilla  # preseleccionado
    entrar(client, "emmy")
    assert "se vincula directamente" in client.get("/productos/nuevo", headers=HX).text
    entrar(client, "sofia")
    assert "Vincular a proyectos" not in client.get("/productos/nuevo", headers=HX).text


def test_fuera_de_periodo():
    p = {"fecha_inicio": "2026-03-01", "fecha_fin": "2029-02-28"}
    assert proyectos.fuera_de_periodo(p, "actividad", {"fecha_inicio": "2025-10-01", "fecha_fin": "2025-12-15"})
    assert not proyectos.fuera_de_periodo(p, "actividad", {"fecha_inicio": "2026-02-20", "fecha_fin": "2026-03-05"})
    assert proyectos.fuera_de_periodo(p, "producto", {"anio": 2025})
    assert not proyectos.fuera_de_periodo(p, "producto", {"anio": 2026})
    assert not proyectos.fuera_de_periodo({"fecha_inicio": None, "fecha_fin": None}, "producto", {"anio": 1990})
