"""Ficha estadística de la Carrera y exportación por correspondencia (PLAN §57, etapa 7)."""
import io
from datetime import date

from openpyxl import Workbook, load_workbook

from app.calidad import ficha, marco
from app.comun import unidades
from tests.conftest import HX

HOY = date.today().year


def _marco():
    return marco.de_unidad(unidades.id_de("CMAT"))


def _plantilla() -> bytes:
    libro = Workbook()
    h = libro.active
    h.title = "Antecedentes"
    h["A1"] = "Formulario externo"
    h["C3"] = "=B3*2"
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def test_ficha_y_claves(carrera):
    r = carrera.get("/calidad/ficha")
    assert r.status_code == 200 and "Cuerpo académico" in r.text and "Admisión por cohorte" in r.text
    d = ficha.datos(_marco(), HOY)
    v = ficha.valores(d)
    assert f"academicos.total.{HOY}" in v and f"admision.mujeres.I-{HOY}" in v
    assert any(k.startswith("indicador.D3.2.b.") for k in v)
    x = carrera.get(f"/calidad/ficha/xlsx?hasta={HOY}")
    libro = load_workbook(io.BytesIO(x.content))
    assert libro.sheetnames == ["Cuerpo académico", "Oferta", "Admisión", "Cohortes", "Indicadores", "Claves"]
    assert libro["Claves"].max_row - 1 == len(v)


def test_correspondencia():
    filas, err = ficha.leer_correspondencia("hoja;celda;clave\nAntecedentes;$B$3;academicos.total.2025\n".encode())
    assert not err and filas[0]["celda"] == "B3"
    _, err = ficha.leer_correspondencia(b"hoja,clave\nx,y\n")
    assert "columnas" in err[0]
    _, err = ficha.leer_correspondencia(b"hoja,celda,clave\nA,3B,academicos.total.2025\n")
    assert "Fila 2" in err[0]
    contenido, err, n = ficha.llenar(_plantilla(), [{"fila": 2, "hoja": "Antecedentes", "celda": "B3", "clave": "a.b"},
                                                   {"fila": 3, "hoja": "Antecedentes", "celda": "B4", "clave": "c.d"}],
                                     {"a.b": 7, "c.d": None})
    assert not err and n == 1
    h = load_workbook(io.BytesIO(contenido))["Antecedentes"]
    assert (h["A1"].value, h["B3"].value, h["C3"].value, h["B4"].value) == ("Formulario externo", 7, "=B3*2", None)
    _, err, _ = ficha.llenar(_plantilla(), [{"fila": 2, "hoja": "Otra", "celda": "B3", "clave": "a.b"}], {"a.b": 1})
    assert "no tiene la hoja" in err[0]
    _, err, _ = ficha.llenar(b"no es xlsx", [], {})
    assert "no es un archivo XLSX" in err[0]


def test_llenar_por_pantalla(carrera):
    csv = f"hoja,celda,clave\nAntecedentes,B3,academicos.total.{HOY}\n".encode()
    r = carrera.post("/calidad/ficha/plantilla", data={"hasta": str(HOY)},
                     files={"plantilla": ("form.xlsx", _plantilla()), "correspondencia": ("c.csv", csv)})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxml")
    assert "form-llena.xlsx" in r.headers["content-disposition"]
    assert load_workbook(io.BytesIO(r.content))["Antecedentes"]["B3"].value == 0
    malo = b"hoja,celda,clave\nAntecedentes,B3,academicos.nada.1999\n"
    r = carrera.post("/calidad/ficha/plantilla", headers=HX,
                     files={"plantilla": ("form.xlsx", _plantilla()), "correspondencia": ("c.csv", malo)})
    assert "clave desconocida" in r.text
