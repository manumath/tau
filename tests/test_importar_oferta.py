"""Fase 3, paso 3.3b: importar la oferta de gestiones pasadas desde CSV."""
import base64

import pytest

from app.academico import gestiones, importar_oferta, oferta
from app.comun import permisos, unidades, usuarios, vinculos
from app.comun.db import get_db
from tests.conftest import HX, PASS_TEMP, login

ARCHIVO = ("gestion;sigla;paralelo;inscritos;email;rol;horas\n"
           "I-2021;MAT-111;A;45;inv@test.cl;titular;6\n"
           "I-2021;MAT-111;A;45;alan@test.cl;auxiliar;2\n"
           "I-2021;MAT-112;;40;;;\n"                       # paralelo A sin docente
           "ver-2021;MAT-278;A;12;inv@test.cl;;\n")         # horas y rol por omisión


@pytest.fixture
def gente(app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    alan = usuarios.crear("alan@test.cl", "Alan", "Turing", None)["id"]  # registrado sin acceso
    return {"emmy": emmy, "alan": alan}


def test_leer_y_aplicar(gente):
    lista, errores = importar_oferta.leer(ARCHIVO.encode())
    assert errores == [] and [g["codigo"] for g in lista] == ["I-2021", "VER-2021"]
    i2021 = lista[0]
    assert not i2021["existe"] and not i2021["errores"]
    assert len(i2021["paralelos"]) == 2 and i2021["paralelos"][("MAT-112", "A")]["docentes"] == []
    ver = lista[1]["paralelos"][("MAT-278", "A")]["docentes"][0]
    assert (ver["rol"], ver["horas"]) == ("titular", 11)  # las horas del plan
    assert any("Sin vínculo con la Carrera" in a for a in i2021["avisos"])
    assert importar_oferta.aplicar(lista, gente["emmy"]) == 2
    g = gestiones.por_codigo("I-2021")
    assert [gestiones.codigo(x) for x in gestiones.crear_anio(2021)] == ["I-2021", "INV-2021", "II-2021", "VER-2021"]
    o = {(x["sigla"], x["paralelo"]): x for x in oferta.listar(g["id"])}
    assert o[("MAT-111", "A")]["inscritos"] == 45 and len(o[("MAT-111", "A")]["docentes"]) == 2
    assert oferta.horas_de_docencia(gente["alan"], g["id"]) == 2
    # Volver a importar el mismo archivo no duplica: reemplaza.
    lista, _ = importar_oferta.leer(ARCHIVO.encode())
    assert lista[0]["actuales"] == 2
    importar_oferta.aplicar(lista, gente["emmy"])
    assert len(oferta.listar(g["id"])) == 2
    assert get_db().q("SELECT COUNT(*) n FROM auditoria WHERE accion = 'importar_oferta'")[0]["n"] == 4


def test_errores_por_fila_y_todo_o_nada(gente):
    gestiones.crear_anio(2022)
    previa = gestiones.por_codigo("II-2022")
    oferta.agregar(previa["id"], "MAT-251", "A", "", gente["emmy"])  # oferta existente que no debe perderse
    contenido = ("gestion,sigla,paralelo,inscritos,email,rol,horas\n"
                 "II-2022,MAT-111,A,30,inv@test.cl,titular,6\n"
                 "II-2022,FIS-137,A,,,,\n"                            # la dicta otra unidad
                 "II-2022,MAT-111,A,31,,,\n"                          # otro número de inscritos
                 "II-2022,MAT-112,A,,nadie@test.cl,,\n"               # persona no registrada
                 "II-2022,MAT-113,A,,inv@test.cl,jefe,\n"             # rol no válido
                 "II-2022,MAT-111,A,,inv@test.cl,titular,4\n"         # docente repetido
                 "II-2022,MAT-412,A,,inv@test.cl,,\n"                 # maestría sin horas en el plan
                 "III-2022,MAT-111,A,,,,\n"                           # gestión no válida
                 "I-2022,MAT-999,A,,,,\n")                            # sigla desconocida
    lista, errores = importar_oferta.leer(contenido.encode())
    por = {g["codigo"]: g for g in lista}
    textos = " ".join(por["II-2022"]["errores"])
    for fragmento in ("FIS-137 la dicta otra unidad", "otro número de inscritos", "nadie@test.cl",
                      "rol no válido", "figura dos veces", "indique las horas"):
        assert fragmento in textos, fragmento
    assert "III-2022" in " ".join(por["?"]["errores"]) and "MAT-999" in por["I-2022"]["errores"][0]
    assert importar_oferta.aplicar(lista, gente["emmy"]) == 0
    assert [o["sigla"] for o in oferta.listar(previa["id"])] == ["MAT-251"]  # intacta


def test_encabezados_obligatorios(gente):
    assert "Faltan columnas: sigla" in importar_oferta.leer(b"gestion,paralelo\nI-2021,A\n")[1][0]


def test_pantallas(client, gente):
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/docencia/oferta/importar").status_code == 403
    permisos.asignar(gente["emmy"], "direccion_carrera", unidades.id_de("CMAT"))
    vinculos.agregar(gente["emmy"], "titular", "2010-01-01", unidad=unidades.id_de("CMAT"))
    assert "Descargar plantilla" in client.get("/docencia/oferta/importar").text
    assert client.get("/docencia/oferta/plantilla").text.startswith("﻿gestion,sigla")
    r = client.post("/docencia/oferta/importar/revisar", headers=HX,
                    files={"archivo": ("o.csv", ARCHIVO.encode(), "text/csv")})
    assert "Importar 2 gestión(es)" in r.text and "Gestión nueva" in r.text
    # Emmy ya tiene vínculo con la Carrera: el aviso solo nombra a Alan.
    assert "Sin vínculo con la Carrera en esa gestión: alan@test.cl." in r.text
    r = client.post("/docencia/oferta/importar/confirmar", headers=HX,
                    data={"contenido": base64.b64encode(ARCHIVO.encode()).decode()})
    g = gestiones.por_codigo("VER-2021")
    assert r.headers["hx-redirect"] == f"/docencia/oferta?gestion={g['id']}"
    assert "MAT-278" in client.get(r.headers["hx-redirect"]).text
