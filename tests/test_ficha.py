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


def test_listados_de_la_ficha(carrera):
    """PLAN §61: los listados (una fila por persona, asignatura…) se escriben hacia abajo desde la celda indicada."""
    from app.academico import gestiones
    from app.calidad import capacitacion
    from app.comun import academicos, usuarios, vinculos
    from app.comun.db import get_db
    emmy = usuarios.por_email("inv@test.cl")["id"]
    vinculos.agregar(emmy, "titular", f"{HOY - 3}-02-01", carga={
        "horas": 160, "actividades": {"docencia": 96, "investigacion": 64, "extension": 0, "gestion": 0, "otras": 0},
        "detalles": {}})
    academicos.agregar_grado(emmy, {"nivel": "doctorado", "titulo": "Doctorado en Matemática",
                                    "institucion": "Universidad Dos", "pais": "Chile"})
    academicos.agregar_grado(emmy, {"nivel": "licenciatura", "institucion": "Universidad Uno"})
    capacitacion.crear({"usuario_id": emmy, "titulo": "Taller", "institucion": None, "area": "otra", "horas": 8,
                        "fecha_inicio": f"{HOY - 1}-03-01", "fecha_fin": f"{HOY - 1}-03-02", "evidencia_id": None}, emmy)
    g = gestiones.por_codigo(f"I-{HOY - 1}") or next(x for x in gestiones.crear_anio(HOY - 1) if x["tipo"] == "I")
    asig = get_db().q("SELECT id FROM asignatura WHERE sigla = 'MAT-111'")[0]["id"]
    oid = get_db().t.oferta.insert(gestion_id=g["id"], asignatura_id=asig, paralelo="A", inscritos=42)["id"]
    get_db().t.oferta_docente.insert(oferta_id=oid, usuario_id=emmy, rol="titular")
    d = ficha.datos(_marco(), HOY)
    v = ficha.valores(d)
    assert v["listado.academicos.apellidos"] == ["Noether"]
    assert v["listado.academicos.grado_1"] == ["Licenciatura o título profesional"]
    assert v["listado.academicos.grado_2"] == ["Doctorado en Matemática"]
    assert v["listado.academicos.institucion_2"] == ["Universidad Dos (Chile)"]
    assert v["listado.academicos.horas_total"] == [160] and v["listado.academicos.horas_investigacion"] == [64]
    assert v["listado.academicos.cursos"] == [f"Algebra I (I-{HOY - 1})"] and v["listado.academicos.n_cursos"] == [1]
    assert v["listado.capacitacion.titulo"] == ["Taller"]
    plan = next(k for k in v if k.startswith("listado.asignaturas_licenciatura_en_matematica_") and k.endswith(".nombre"))
    base = plan.rsplit(".", 1)[0]
    i = v[f"{base}.sigla"].index("MAT-111")
    assert v[plan][i] == "Algebra I (MAT-111)" and v[f"{base}.veces_dictada"][i] == 1
    assert v[f"{base}.max_estudiantes"][i] == 42 and v[f"{base}.linea_formativa"][i] == "Álgebra"
    assert "fecha_nacimiento" not in " ".join(v) and "edad" not in " ".join(k for k in v if k.startswith("listado."))
    assert "Listado academicos: Apellidos" in ficha.nombre_de("listado.academicos.apellidos")
    corr = [{"fila": 2, "hoja": "Antecedentes", "celda": "B7", "clave": "listado.academicos.apellidos"},
            {"fila": 3, "hoja": "Antecedentes", "celda": "C7", "clave": f"{base}.nombre"}]
    contenido, err, n = ficha.llenar(_plantilla(), corr, v)
    assert not err
    h = load_workbook(io.BytesIO(contenido))["Antecedentes"]
    assert h["B7"].value == "Noether" and h["B8"].value is None and h["C7"].value == "Algebra I (MAT-111)"
    assert h["C8"].value == v[plan][1] and h["A1"].value == "Formulario externo"
