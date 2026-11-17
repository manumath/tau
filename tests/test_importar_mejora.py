"""Carga del plan de mejora desde CSV (PLAN §72, etapa 4), con el archivo versionado del plan de la Carrera."""
import base64

from app.calidad import actividades_mejora as am
from app.calidad import importar_mejora as im
from app.calidad import marco, mejora
from app.comun import permisos, unidades, usuarios
from app.comun.db import get_db
from tests.conftest import HX


def _mid():
    return marco.de_unidad(unidades.id_de("CMAT"))["id"]


def test_el_plan_de_la_carrera_se_lee_completo(app):
    d = usuarios.por_email("admin@test.cl")
    permisos.asignar(d["id"], "direccion_carrera", unidades.id_de("CMAT"))
    acciones, errores = im.leer(im.plan_de_la_carrera(), _mid(), d["id"])
    assert not errores
    assert len(acciones) == 15 and sum(len(a["actividades"]) for a in acciones) == 57
    assert all(a["estado"] == "nueva" and not a["mensajes"] for a in acciones), [a["mensajes"] for a in acciones]
    assert all(not t["errores"] for a in acciones for t in a["actividades"])
    a4 = next(a for a in acciones if a["codigo"] == "A4")
    assert a4["prioridad"] == "alta" and a4["datos"]["plazo"] == "2028-12-31"
    t = next(t for t in a4["actividades"] if t["codigo"] == "4.2")
    assert t["datos"]["presupuesto"] == 2000 and t["datos"]["fuente"] == "Recursos Propios"
    assert t["datos"]["inicio"] == "2027-03-01" and t["datos"]["linea_base"].startswith("21,7 %")
    assert t["indicador"]["nombre"] == "Retención al primer año"
    titulacion = next(t for t in a4["actividades"] if t["codigo"] == "4.3")
    assert titulacion["indicador"]["nombre"] == "Titulación oportuna"
    # Responsable propuesto: quien hoy ocupa la Dirección de Carrera.
    a2 = next(a for a in acciones if a["codigo"] == "A2")
    assert a2["responsable"]["id"] == d["id"]
    # Ninguna mención a agencias ni a sus instrumentos en el archivo versionado (PLAN §57).
    texto = im.plan_de_la_carrera().decode("utf-8").lower()
    assert not any(x in texto for x in ("cinda", "ceub", "guía de antecedentes"))


def test_cargar_por_pantalla_y_no_duplicar(carrera):
    contenido = base64.b64encode(im.plan_de_la_carrera()).decode()
    r = carrera.post("/calidad/mejora/importar/revisar", headers=HX,
                     files={"archivo": ("plan.csv", im.plan_de_la_carrera(), "text/csv")})
    assert r.status_code == 200 and "15 acción(es) nueva(s) con 57 actividad(es)" in r.text
    carrera.post("/calidad/mejora/importar/confirmar", headers=HX, data={"contenido": contenido, "ligar": ["A4|4.3"]})
    assert get_db().q("SELECT COUNT(*) n FROM accion_mejora")[0]["n"] == 15
    assert get_db().q("SELECT COUNT(*) n FROM actividad_mejora")[0]["n"] == 57
    ligadas = get_db().q("SELECT codigo FROM actividad_mejora WHERE indicador_id IS NOT NULL")
    assert [x["codigo"] for x in ligadas] == ["4.3"]                 # solo las marcadas
    a4 = next(a for a in mejora.acciones(_mid()) if a["codigo"] == "A4")
    assert a4["plazo"] == "2028-12-31" and len(am.de_accion(a4["id"])) == 6
    # La segunda carga del mismo archivo no duplica nada.
    r = carrera.post("/calidad/mejora/importar/revisar", headers=HX,
                     files={"archivo": ("plan.csv", im.plan_de_la_carrera(), "text/csv")})
    assert "0 acción(es) nueva(s)" in r.text and "15 ya en el plan" in r.text
    assert carrera.get("/calidad/mejora/importar/plantilla").status_code == 200
    assert carrera.get("/calidad/mejora").status_code == 200


def test_errores_y_permisos(carrera, client):
    malo = ("accion,accion_titulo,actividad,descripcion,fin,responsable,prioridad\n"
            "A1,Una acción,1.1,,12/2027,DTIC,P1\n"
            "A1,Una acción,1.2,Bien,13/2027,DTIC,P1\n"
            "A2,Otra,2.1,Bien,06/2027,DTIC,P9\n").encode()
    acciones, errores = im.leer(malo, _mid(), usuarios.por_email("admin@test.cl")["id"])
    assert not errores
    a1, a2 = acciones
    assert a1["estado"] == "error" and "Ninguna actividad válida." in a1["mensajes"]
    assert a2["estado"] == "nueva" and any("P9" in m for m in a2["mensajes"])
    assert im.leer(b"x,y\n1,2\n", _mid(), 1)[1][0].startswith("Faltan columnas")
    carrera.post("/logout", headers=HX)
    otro = usuarios.crear("otro@test.cl", "Otro", "Docente", "Clave-otro-12345", debe_cambiar_pass=False)
    assert otro
    from tests.conftest import login
    login(carrera, "otro@test.cl", "Clave-otro-12345")
    assert carrera.get("/calidad/mejora/importar", headers=HX).status_code == 403
    assert carrera.post("/calidad/mejora/importar/confirmar", headers=HX, data={"contenido": ""}).status_code == 403
