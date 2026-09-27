"""Ajustes, etapa C: propuestas de proyectos institucionales."""
from datetime import date

import pytest

from app.investigacion import institucionales as inst
from app.investigacion import perfiles, proyectos
from app.comun import usuarios
from app.comun.db import get_db
from tests.conftest import HX, PASS_ADMIN, PASS_TEMP, login

CLAVE = "Clave-colega-1"


@pytest.fixture
def fecha(monkeypatch):
    """fecha('2026-09-10') fija «hoy» para las reglas de periodos y plazos."""
    def fijar(iso):
        monkeypatch.setattr(inst, "hoy", lambda: date.fromisoformat(iso))
    fijar("2026-09-10")
    return fijar


@pytest.fixture
def gente(app, fecha):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    perfiles.cambiar_categoria(emmy, "titular")
    crear = lambda email, nombre, apellido, cat: usuarios.crear(  # noqa: E731
        email, nombre, apellido, CLAVE, debe_cambiar_pass=False, categoria=cat)["id"]
    return {"emmy": emmy, "alan": crear("alan@test.cl", "Alan", "Turing", "contratado"),
            "sofia": crear("sofia@test.cl", "Sofía", "Kovalévskaya", "interino"),
            "carl": crear("carl@test.cl", "Carl", "Gauss", "invitado"),
            "admin": usuarios.por_email("admin@test.cl")["id"]}


def entrar(client, quien):
    client.post("/logout")
    email = {"emmy": "inv@test.cl", "admin": "admin@test.cl"}.get(quien, f"{quien}@test.cl")
    clave = {"emmy": PASS_TEMP, "admin": PASS_ADMIN}.get(quien, CLAVE)
    assert login(client, email, clave).headers["hx-redirect"] == "/"
    return client


COMPLETA = dict(nombre="Anillos y autómatas", descripcion="Estudio de anillos asociados a autómatas.",
                objetivo_general="Caracterizar autómatas por sus anillos.",
                metodologia="Métodos de álgebra conmutativa: $R[x]$.", resultados_esperados="Dos artículos.",
                bibliografia="Noether, E. (1921). Idealtheorie in Ringbereichen.",
                objetivo=["Construir el anillo.", "Probar que es noetheriano."],
                act_desc=["Seminario de lanzamiento", "Visita a Gotinga"], act_mes=["2026-10", "2027-03"],
                linea=["2", "4"])


def _crear(client, nombre="Anillos y autómatas"):
    r = client.post("/propuestas", headers=HX, data={"nombre": nombre})
    return int(r.headers["hx-redirect"].rsplit("/", 1)[1])


def _enviada(client, fecha):
    """Emmy crea y envía una propuesta completa dentro del plazo. → id de la propuesta."""
    entrar(client, "emmy")
    prop = _crear(client)
    client.put(f"/propuestas/{prop}", headers=HX, data=COMPLETA)
    fecha("2026-09-10")
    r = client.post(f"/propuestas/{prop}/enviar", headers=HX, data=COMPLETA)
    assert r.headers.get("hx-redirect") == f"/propuestas/{prop}", r.text
    return prop


# --- Periodos y plazos ----------------------------------------------------------------------------

def test_periodos(app, fecha):
    assert inst.meses(2026)[0] == ("2026-10", "oct 2026") and inst.meses(2026)[-1] == ("2027-09", "sept 2027")
    assert (inst.inicio(2026), inst.fin(2026)) == ("2026-10-01", "2027-09-30")
    assert inst.plazo(2026) == {"abre": "2026-09-01", "cierra": "2026-09-30", "modificado": False}
    fecha("2026-09-15")
    assert inst.periodo_abierto() == 2026 and inst.periodo_objetivo() == 2026
    fecha("2026-10-05")
    assert inst.periodo_abierto() is None and inst.periodo_objetivo() == 2027
    fecha("2026-05-01")
    assert inst.periodo_objetivo() == 2026


def test_plazo_extraordinario(client, gente, fecha):
    entrar(client, "emmy")
    assert client.post("/admin/propuestas/2026/plazo", headers=HX,
                       data={"abre": "2026-09-01", "cierra": "2026-10-15"}).status_code == 403
    entrar(client, "admin")
    r = client.post("/admin/propuestas/2026/plazo", headers=HX, data={"abre": "2026-09-01", "cierra": "2026-08-01"})
    assert "no puede ser anterior" in r.text
    client.post("/admin/propuestas/2026/plazo", headers=HX, data={"abre": "2026-09-01", "cierra": "2026-10-15"})
    fecha("2026-10-10")
    assert inst.abierta(2026) and inst.periodo_abierto() == 2026
    client.post("/admin/propuestas/2026/plazo/restablecer", headers=HX)
    assert not inst.abierta(2026)


# --- Quién propone ----------------------------------------------------------------------------------

@pytest.mark.parametrize("quien,puede", [("emmy", True), ("alan", True), ("sofia", False), ("carl", False)])
def test_proponen_titulares_y_contratados(client, gente, quien, puede):
    entrar(client, quien)
    assert (client.get("/propuestas/nueva", headers=HX).status_code == 200) == puede
    assert ("Proponer proyecto institucional" in client.get("/proyectos").text) == puede
    r = client.post("/propuestas", headers=HX, data={"nombre": "X"})
    assert ("hx-redirect" in r.headers) == puede


def test_proponente_queda_responsable_de_un_proyecto_en_formulacion(client, gente):
    entrar(client, "alan")
    prop = inst.obtener(_crear(client))
    p = proyectos.obtener(prop["proyecto_id"])
    assert (p["tipo"], p["estado"]) == ("institucional", "formulacion")
    assert proyectos.rol_de(p["id"], gente["alan"]) == "responsable"
    assert (prop["estado"], prop["modalidad"], prop["periodo"]) == ("borrador", "nuevo", 2026)
    assert "Anillos y autómatas" in client.get("/proyectos").text  # en «Mis propuestas»


# --- Flujo completo ----------------------------------------------------------------------------------

def test_no_se_envia_incompleta_ni_fuera_de_plazo(client, gente, fecha):
    entrar(client, "emmy")
    prop = _crear(client)
    r = client.post(f"/propuestas/{prop}/enviar", headers=HX, data={"nombre": "Anillos"})
    assert "Antes de enviar, complete" in r.text and "metodología" in r.text
    fecha("2026-08-20")
    r = client.post(f"/propuestas/{prop}/enviar", headers=HX, data=COMPLETA)
    assert "recibe propuestas del 1 de septiembre de 2026 al 30 de septiembre de 2026" in r.text
    # Lo escrito quedó guardado aunque no se pudo enviar.
    guardada = inst.obtener(prop)
    assert guardada["estado"] == "borrador" and guardada["metodologia"].startswith("Métodos")
    assert [o["texto"] for o in guardada["objetivos"]] == COMPLETA["objetivo"]
    assert [(a["descripcion"], a["mes_previsto"]) for a in guardada["actividades"]] == [
        ("Seminario de lanzamiento", "2026-10"), ("Visita a Gotinga", "2027-03")]


def test_mes_fuera_del_periodo(client, gente):
    entrar(client, "emmy")
    prop = _crear(client)
    r = client.put(f"/propuestas/{prop}", headers=HX, data={**COMPLETA, "act_mes": ["2026-10", "2028-01"]})
    assert "fuera del periodo" in r.text and "Visita a Gotinga" in r.text  # conserva lo escrito


def test_flujo_condicional_y_aceptacion(client, gente, fecha, buzon):
    prop = _enviada(client, fecha)
    assert inst.obtener(prop)["estado"] == "enviada"
    assert any(m["To"] == "admin@test.cl" and "Nueva propuesta" in m["Subject"] for m in buzon)
    # Enviada: ya no se edita.
    assert client.put(f"/propuestas/{prop}", headers=HX, data=COMPLETA).status_code == 403

    entrar(client, "admin")
    assert "Anillos y autómatas" in client.get("/admin/propuestas?periodo=2026").text
    assert client.get("/admin/propuestas/contador").text.count(">1<") == 1
    r = client.post(f"/propuestas/{prop}/decidir", headers=HX, data={"decision": "condicional"})
    assert "Indique las condiciones" in r.text
    client.post(f"/propuestas/{prop}/decidir", headers=HX,
                data={"decision": "condicional", "comentario": "Agregue un objetivo de formación."})
    assert inst.obtener(prop)["estado"] == "condicional"
    pid = inst.obtener(prop)["proyecto_id"]
    assert proyectos.obtener(pid)["estado"] == "formulacion"  # en espera
    assert any(m["To"] == "inv@test.cl" and "condiciones" in m["Subject"] for m in buzon)

    # Emmy corrige y reenvía, ya fuera del plazo (los reenvíos no dependen de él).
    fecha("2026-10-05")
    entrar(client, "emmy")
    assert "Condiciones de la administración" in client.get(f"/propuestas/{prop}").text
    corregida = {**COMPLETA, "objetivo": COMPLETA["objetivo"] + ["Formar a un doctorando."]}
    r = client.post(f"/propuestas/{prop}/enviar", headers=HX, data=corregida)
    assert r.headers.get("hx-redirect") == f"/propuestas/{prop}"
    assert (inst.obtener(prop)["estado"], inst.obtener(prop)["envios"]) == ("enviada", 2)

    entrar(client, "admin")
    client.post(f"/propuestas/{prop}/decidir", headers=HX, data={"decision": "aceptada"})
    p = proyectos.obtener(pid)
    assert (p["estado"], p["fecha_inicio"], p["fecha_fin"]) == ("vigente", "2026-10-01", "2027-09-30")
    assert p["nombre"] == "Anillos y autómatas" and p["objetivo_general"].startswith("Caracterizar")
    assert [o["texto"] for o in proyectos.objetivos(pid)][-1] == "Formar a un doctorando."
    assert [e["accion"] for e in inst.eventos(prop)] == ["enviada", "condicional", "enviada", "aceptada"]


def test_rechazo_y_retiro(client, gente, fecha):
    prop = _enviada(client, fecha)
    entrar(client, "admin")
    r = client.post(f"/propuestas/{prop}/decidir", headers=HX, data={"decision": "rechazada"})
    assert "motivo" in r.text
    client.post(f"/propuestas/{prop}/decidir", headers=HX, data={"decision": "rechazada", "comentario": "Sin fondos."})
    assert inst.obtener(prop)["estado"] == "rechazada"
    assert proyectos.obtener(inst.obtener(prop)["proyecto_id"])["estado"] == "formulacion"
    # Una rechazada ya no se decide ni se retira.
    assert "Solo se deciden" in client.post(f"/propuestas/{prop}/decidir", headers=HX,
                                            data={"decision": "aceptada"}).text

    entrar(client, "alan")
    otra = _crear(client, "Otra")
    client.put(f"/propuestas/{otra}", headers=HX, data={**COMPLETA, "nombre": "Otra"})
    client.post(f"/propuestas/{otra}/enviar", headers=HX, data={**COMPLETA, "nombre": "Otra"})
    client.post(f"/propuestas/{otra}/retirar", headers=HX)
    assert inst.obtener(otra)["estado"] == "retirada"


def test_solo_admin_decide(client, gente, fecha):
    prop = _enviada(client, fecha)
    r = client.post(f"/propuestas/{prop}/decidir", headers=HX, data={"decision": "aceptada"})
    assert r.status_code == 403 and inst.obtener(prop)["estado"] == "enviada"


def test_eliminar_borrador_borra_el_proyecto_nuevo(client, gente):
    entrar(client, "emmy")
    prop = inst.obtener(_crear(client))
    client.delete(f"/propuestas/{prop['id']}", headers=HX)
    assert inst.obtener(prop["id"]) is None and proyectos.obtener(prop["proyecto_id"]) is None


def test_quien_ve_la_propuesta(client, gente):
    entrar(client, "emmy")
    prop = _crear(client)
    entrar(client, "sofia")
    assert "no tiene acceso" in client.get(f"/propuestas/{prop}").text
    entrar(client, "admin")
    r = client.get(f"/propuestas/{prop}")
    assert "Anillos y autómatas" in r.text and "Guardar borrador" not in r.text
    # Los borradores no aparecen en la bandeja de la administración.
    assert "Anillos y autómatas" not in client.get("/admin/propuestas?periodo=2026").text


# --- Vigencia y continuidad ------------------------------------------------------------------------------

def _aceptada(client, fecha):
    prop = _enviada(client, fecha)
    entrar(client, "admin")
    client.post(f"/propuestas/{prop}/decidir", headers=HX, data={"decision": "aceptada"})
    return inst.obtener(prop)


def test_sin_continuidad_concluye_en_septiembre(client, gente, fecha):
    pid = _aceptada(client, fecha)["proyecto_id"]
    fecha("2027-09-30")
    inst.refrescar_vigencias()
    assert proyectos.obtener(pid)["estado"] == "vigente"
    fecha("2027-10-01")
    inst.refrescar_vigencias()
    assert proyectos.obtener(pid)["estado"] == "finalizado"


def test_continuidad(client, gente, fecha, buzon):
    prop = _aceptada(client, fecha)
    pid = prop["proyecto_id"]
    proyectos.agregar_participante(pid, f"i:{gente['alan']}", "co_investigador", False)

    # Recordatorio en septiembre, una sola vez.
    fecha("2027-09-02")
    buzon.clear()
    inst.mantenimiento(forzar=True)
    inst.mantenimiento(forzar=True)
    assert [m["To"] for m in buzon if "Continuidad" in m["Subject"]] == ["inv@test.cl"]

    entrar(client, "emmy")
    assert "Si no envía la propuesta de continuidad" in client.get(f"/proyectos/{pid}").text
    entrar(client, "alan")  # participante, no responsable
    client.post(f"/proyectos/{pid}/continuidad", headers=HX)
    assert inst.de_proyecto_y_periodo(pid, 2027) is None

    entrar(client, "emmy")
    r = client.post(f"/proyectos/{pid}/continuidad", headers=HX)
    cont = inst.de_proyecto_y_periodo(pid, 2027)
    assert r.headers["hx-redirect"] == f"/propuestas/{cont['id']}"
    assert (cont["modalidad"], cont["estado"]) == ("continuidad", "borrador")
    # Precargada con la anterior; las actividades hay que ubicarlas en el nuevo calendario.
    assert cont["metodologia"] == COMPLETA["metodologia"]
    assert [o["texto"] for o in cont["objetivos"]] == COMPLETA["objetivo"]
    assert [a["mes_previsto"] for a in cont["actividades"]] == [None, None]
    assert "el mes previsto de cada actividad" in inst.faltantes(cont)

    datos = {**COMPLETA, "act_mes": ["2027-11", "2028-04"], "objetivo": COMPLETA["objetivo"] + ["Nuevo objetivo."]}
    client.post(f"/propuestas/{cont['id']}/enviar", headers=HX, data=datos)
    assert inst.obtener(cont["id"])["estado"] == "enviada"

    # Pasa el 30 de septiembre sin decisión: sigue vigente, en renovación.
    fecha("2027-10-03")
    inst.refrescar_vigencias()
    p = proyectos.obtener(pid)
    assert p["estado"] == "vigente" and inst.en_renovacion(p)
    assert "En renovación" in client.get(f"/proyectos/{pid}").text

    entrar(client, "admin")
    client.post(f"/propuestas/{cont['id']}/decidir", headers=HX, data={"decision": "aceptada"})
    p = proyectos.obtener(pid)
    assert (p["estado"], p["fecha_inicio"], p["fecha_fin"]) == ("vigente", "2026-10-01", "2028-09-30")
    assert not inst.en_renovacion(p)
    assert "Nuevo objetivo." in [o["texto"] for o in proyectos.objetivos(pid)]


def test_continuidad_rechazada_concluye(client, gente, fecha):
    pid = _aceptada(client, fecha)["proyecto_id"]
    fecha("2027-09-10")
    entrar(client, "emmy")
    client.post(f"/proyectos/{pid}/continuidad", headers=HX)
    cont = inst.de_proyecto_y_periodo(pid, 2027)
    client.post(f"/propuestas/{cont['id']}/enviar", headers=HX,
                data={**COMPLETA, "act_mes": ["2027-11", "2028-04"]})
    fecha("2027-10-10")
    entrar(client, "admin")
    client.post(f"/propuestas/{cont['id']}/decidir", headers=HX, data={"decision": "rechazada", "comentario": "No."})
    assert proyectos.obtener(pid)["estado"] == "finalizado"


def test_proyecto_institucional_limita_edicion(client, gente, fecha):
    pid = _aceptada(client, fecha)["proyecto_id"]
    entrar(client, "emmy")
    r = client.get(f"/proyectos/{pid}/datos/editar", headers=HX)
    assert "vienen de la propuesta aceptada" in r.text and 'name="nombre"' not in r.text
    client.put(f"/proyectos/{pid}/datos", headers=HX, data={"nombre": "Otro nombre", "codigo": "INST-1",
                                                            "estado": "finalizado"})
    p = proyectos.obtener(pid)
    assert (p["nombre"], p["codigo"], p["estado"]) == ("Anillos y autómatas", "INST-1", "vigente")
    assert client.post(f"/proyectos/{pid}/objetivos", headers=HX, data={"texto": "x"}).status_code == 403


# --- Categorías en proyectos institucionales ---------------------------------------------------------------

def test_categorias_en_proyectos_institucionales(client, gente, fecha):
    pid = _aceptada(client, fecha)["proyecto_id"]
    assert proyectos.agregar_participante(pid, f"i:{gente['sofia']}", "co_responsable", False) is None
    assert "co-responsables" in proyectos.agregar_participante(pid, f"i:{gente['carl']}", "co_responsable", False)
    assert proyectos.agregar_participante(pid, f"i:{gente['carl']}", "co_investigador", False) is None
    assert "titular o contratado" in proyectos.reasignar_responsable(pid, gente["sofia"], "co_investigador")
    assert proyectos.reasignar_responsable(pid, gente["alan"], "co_investigador") is None
    # En un proyecto individual no hay restricción por categoría.
    indiv = proyectos.crear(dict(nombre="Individual", estado="vigente"), gente["carl"], gente["carl"])
    assert proyectos.agregar_participante(indiv, f"i:{gente['sofia']}", "co_responsable", False) is None
    assert get_db().q("SELECT tipo FROM proyecto WHERE id = ?", [indiv])[0]["tipo"] == "individual"
