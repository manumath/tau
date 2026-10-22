"""Cohortes estudiantiles (PLAN §49, etapa 1): carga del CSV, indicadores, tablero y hojas 3 a 6 de la Guía."""
import base64
import io

from openpyxl import load_workbook

from app.acreditacion import guia_antecedentes as guia
from app.comun import personas
from app.comun.db import get_db
from app.estudiantil import cohortes, importar
from tests.conftest import HX

ENCABEZADO = ("ru,nombres,apellidos,email,sexo,fecha_nacimiento,cohorte,via,otra_ciudad,extranjero,colegio,plan,estado,"
              "ultimo_ciclo,fecha_egreso,fecha_titulacion,modalidad,motivo\n")
CSV = ENCABEZADO + (
    "1111111,Sofía,Mamani,sofia@correo.bo,mujer,12/05/2004,2022-I,ordinaria,no,no,público,,cursando,,,,,\n"
    "2222222,Luis,Choque,luis@correo.bo,hombre,03/09/2002,2020-II,especial,sí,no,privado,,titulado,,15/06/2025,20/11/2025,"
    "tesis,\n"
    "3333333,Ana,Condori,,mujer,21/01/2003,2021-I,,,,,,retirado,2022-II,,,,no académico\n"
    "4444444,Pedro,Quispe,,hombre,,2020-II,,,,,,egresado,,10/12/2024,,,\n"
    "5555555,Rosa,Flores,,mujer,,2021-II,,,,,,congelado,2022-I,,,,\n")


def _cargar(texto=CSV):
    filas, errores = importar.leer(texto.encode())
    assert errores == []
    assert [f["errores"] for f in filas if f["errores"]] == []
    return importar.aplicar(filas, None)


def test_la_carga_crea_estudiantes_con_su_estado(app):
    assert _cargar() == (5, 0)
    luis = get_db().q("SELECT * FROM estudiante WHERE registro_universitario = '2222222'")[0]
    assert (luis["estado"], luis["titulado"], luis["fecha_egreso"], luis["fecha_titulacion"]) == (
        "titulado", 1, "2025-06-15", "2025-11-20")
    assert (luis["cohorte_anio"], luis["cohorte_ciclo"], luis["ultimo_anio"], luis["ultimo_ciclo"], luis["hasta"]) == (
        2020, "II", 2025, "I", 2025)
    assert (luis["via_ingreso"], luis["otra_ciudad"], luis["extranjero"], luis["colegio"], luis["sexo"]) == (
        "especial", 1, 0, "privado", "hombre")
    assert luis["edad_ingreso"] == 17                       # nació el 3-sep-2002; ingresó en agosto de 2020
    ana = get_db().q("SELECT * FROM estudiante WHERE registro_universitario = '3333333'")[0]
    assert (ana["estado"], ana["motivo_retiro"], ana["ultimo_anio"], ana["ultimo_ciclo"], ana["hasta"]) == (
        "retirado", "no_academico", 2022, "II", 2022)
    assert get_db().q("SELECT COUNT(*) n FROM persona_externa")[0]["n"] == 5
    # Compatible con la investigación: sigue habiendo un periodo de licenciatura del programa propio.
    sofia = get_db().q("SELECT externo_id FROM estudiante WHERE registro_universitario = '1111111'")[0]["externo_id"]
    assert estudiantes_etiqueta(sofia) == "Estudiante de licenciatura"


def estudiantes_etiqueta(externo_id):
    from app.comun import estudiantes
    return estudiantes.etiqueta(externo_id, 2023)


def test_recargar_actualiza_por_ru_y_no_duplica(app):
    _cargar()
    nuevo = CSV.replace("1111111,Sofía,Mamani,sofia@correo.bo,mujer,12/05/2004,2022-I,ordinaria,no,no,público,,cursando,,,,,",
                        "1111111,Sofía,Mamani,sofia@correo.bo,mujer,12/05/2004,2022-I,ordinaria,no,no,público,,egresado,,"
                        "01/07/2026,,,")
    filas, _ = importar.leer(nuevo.encode())
    assert sum(f["accion"] == "actualiza" for f in filas) == 5
    assert importar.aplicar(filas, None) == (0, 5)
    assert get_db().q("SELECT COUNT(*) n FROM estudiante")[0]["n"] == 5
    assert get_db().q("SELECT estado FROM estudiante WHERE registro_universitario = '1111111'")[0]["estado"] == "egresado"


def test_vincula_con_la_ficha_que_ya_existia(app, tmp_path):
    """Una persona externa que ya era estudiante en la investigación (sin RU) recibe el RU, no una ficha nueva."""
    mid = personas.crear_externo("Sofía", "Mamani", "UMSA", "Bolivia", 1)["id"]
    get_db().execute("UPDATE persona_externa SET email = 'sofia@correo.bo' WHERE id = ?", [mid])
    get_db().t.estudiante.insert(externo_id=mid, nivel="licenciatura", desde=2022)
    filas, _ = importar.leer(CSV.encode())
    sofia = next(f for f in filas if f["ru"] == "1111111")
    assert sofia["accion"] == "actualiza" and sofia["persona"]["id"] == mid and "vincula" in sofia["aviso"]
    importar.aplicar(filas, None)
    assert get_db().q("SELECT COUNT(*) n FROM persona_externa WHERE nombres = 'Sofía'")[0]["n"] == 1
    assert get_db().q("SELECT registro_universitario FROM estudiante WHERE externo_id = ?", [mid]) == [
        {"registro_universitario": "1111111"}]


def test_errores_de_la_carga(app):
    assert "Faltan columnas" in importar.leer(b"ru,nombres\n1,Ana\n")[1][0]
    malas = ENCABEZADO + (
        "9000001,Ana,Uno,,,,2022-I,,,,,,retirado,,,,,\n"                         # sin último ciclo ni motivo
        "9000002,Ana,Dos,,,,2022-I,,,,,,titulado,,,,,\n"                         # sin fecha de titulación
        "9000003,Ana,Tres,,,,2099-I,,,,,,cursando,,,,,\n"                        # cohorte futura
        "9000004,Ana,Cuatro,,,,2022-I,,,,,Plan X,cursando,,,,,\n"                # plan inexistente
        "9000005,Ana,Cinco,,,,2022-I,,,,,,desconocido,,,,,\n"                    # estado
        "9000006,Ana,Seis,,,,2022-I,,,,,,egresado,,15/06/2020,,,\n"              # egreso anterior al ingreso
        "9000006,Ana,Siete,,,,2022-I,,,,,,cursando,,,,,\n")                      # RU repetido
    filas, errores = importar.leer(malas.encode())
    assert errores == []
    texto = [" ".join(f["errores"]) for f in filas]
    assert "último ciclo" in texto[0] and "motivo" in texto[0]
    assert "fecha de titulación" in texto[1]
    assert "cohorte fuera de rango" in texto[2]
    assert "plan «Plan X»" in texto[3]
    assert "estado no válido" in texto[4]
    assert "anterior al ingreso" in texto[5]
    assert "ya aparece en la fila 7" in texto[6]
    assert importar.aplicar(filas, None) == (0, 0)
    assert get_db().q("SELECT COUNT(*) n FROM estudiante")[0]["n"] == 0


def test_indicadores_por_cohorte(app):
    _cargar()
    ciclos = cohortes.cohortes_hasta((2026, "II"), 20)
    res = {c["texto"]: c for c in cohortes.resumen(ciclos)}
    c = res["2020-II"]
    assert c["n"] == 2 and c["estados"]["titulado"] == 1 and c["estados"]["egresado"] == 1
    assert c["matricula"][7] == 2 and c["matricula"][15] == 2 and c["matricula"][16] == 1 and c["matricula"][17] == 0
    assert c["egresados"][15] == 1 and c["egresados"][16] == 1 and c["titulados"][17] == 1
    assert res["2021-I"]["desertores"] == 1 and res["2021-I"]["desercion_no_academica"] == 1
    # Congelado que no volvió en los dos ciclos siguientes cuenta como desertor.
    assert res["2021-II"]["desertores"] == 1
    adm = cohortes.admision(ciclos[10])
    assert (adm["ordinaria"], adm["mujeres"], adm["publico"], adm["tramos"]) == (1, 1, 1, [1, 0, 0, 0])


def test_un_congelado_reciente_aun_no_es_desertor(app):
    actual = cohortes.ordinal(*cohortes.ciclo_actual())
    anio, ciclo = cohortes.desde_ordinal(actual - 1)
    texto = ENCABEZADO + f"7000001,Eva,Mita,,,,{anio - 2}-I,,,,,,congelado,{anio}-{ciclo},,,,\n"
    _cargar(texto)
    e = cohortes.alumnos()[0]
    assert cohortes.desertor(e, actual) is False


# --- Pantallas -------------------------------------------------------------------------------------------------

def test_tablero_y_carga_por_la_direccion_de_carrera(carrera):
    r = carrera.get("/docencia/cohortes")
    assert r.status_code == 200 and "Aún no hay estudiantes con cohorte" in r.text and "Cargar CSV" in r.text
    assert 'href="/docencia/cohortes"' in r.text                      # pestaña de Docencia
    r = carrera.get("/docencia/cohortes/plantilla")
    assert r.status_code == 200 and r.text.startswith("﻿ru,nombres") or "ru,nombres" in r.text
    r = carrera.post("/docencia/cohortes/revisar", headers=HX, files={"archivo": ("c.csv", CSV.encode(), "text/csv")})
    assert "5 estudiante(s) se guardarán (5 nuevos)" in r.text and "Choque" in r.text
    r = carrera.post("/docencia/cohortes/confirmar", headers=HX, data={"contenido": base64.b64encode(CSV.encode()).decode()})
    assert r.headers["hx-redirect"] == "/docencia/cohortes"
    r = carrera.get("/docencia/cohortes")
    assert "2020-II" in r.text and "2021-I" in r.text and "Años medios hasta la titulación" in r.text
    assert "Choque" not in r.text                                       # solo agregados, sin nombres
    # Quedó en la auditoría.
    assert get_db().q("SELECT detalle FROM auditoria WHERE accion = 'importar_cohortes'")[0]["detalle"] == (
        "5 nueva(s), 0 actualizada(s)")


def test_carga_rechaza_archivo_sin_filas_validas(carrera):
    r = carrera.post("/docencia/cohortes/revisar", headers=HX,
                     files={"archivo": ("c.csv", b"ru,nombres\n1,Ana\n", "text/csv")})
    assert "Faltan columnas" in r.text


# --- Guía de Antecedentes ----------------------------------------------------------------------------------

def test_hojas_3_a_6_de_la_guia(app):
    _cargar()
    libro = load_workbook(io.BytesIO(guia.generar(ultimo=(2026, "II"))))
    h4, h5, h6, h3 = (libro[guia.H[k]] for k in ("cohortes", "egresados", "titulados", "admision"))
    # Hoja 4: cohorte 2020-II (fila 15): 2 matriculados desde su ingreso; 1 cuando egresa Pedro (2024-II → ciclo 15).
    assert (h4["I15"].value, h4["Q15"].value, h4["R15"].value, h4["S15"].value) == (2, 2, 1, 0)
    assert (h4["V15"].value, h4["W15"].value, h4["X15"].value) == (0, 0, 0)
    assert (h4["V16"].value, h4["W16"].value, h4["X16"].value) == (0, 1, 1)           # 2021-I: Ana
    assert h4["X17"].value == 1                                                       # 2021-II: Rosa (congelada)
    assert h4["B8"].value is None                                                     # 2017-I: sin datos
    assert h4["Y15"].value == '=IFERROR((I15-K15)/I15,"")'
    # Hojas 5 y 6: egresados y titulados de la cohorte 2020-II en los ciclos de 2022-I a 2026-II.
    assert [h5[f"{c}14"].value for c in "BGHI"] == [0, 1, 1, 0]
    assert [h6[f"{c}16"].value for c in "BHIJ"] == [0, 0, 1, 0]
    # Hoja 3: la cohorte 2022-I (fila 9): ordinaria, mujer, colegio público, menor de 18 años.
    assert [h3[c + "9"].value for c in "CEHIJKLMNOPQ"] == [1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0]
    assert h3["C10"].value is None


def test_la_lista_de_investigacion_no_muestra_el_seguimiento_academico(app, client):
    """Un investigador no ve la situación académica de los estudiantes cargados solo desde Seguimiento Académico."""
    from app.comun import usuarios
    from tests.conftest import PASS_TEMP, login
    _cargar()
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/estudiantes")
    assert r.status_code == 200 and "Choque" not in r.text and "Mamani" not in r.text
    sofia = get_db().q("SELECT externo_id FROM estudiante WHERE registro_universitario = '1111111'")[0]["externo_id"]
    assert "Esa persona no existe" in client.get(f"/estudiantes/{sofia}").text
    # Si participa en la investigación (autora de una tesis), vuelve a verse.
    get_db().execute("INSERT INTO producto (tipo_id, titulo, anio, estado_publicacion, revision, creado_por) "
                     "SELECT id, 'Tesis de Sofía', 2026, 'publicado', 'sin_arbitraje', ? FROM tipo_producto "
                     "WHERE nombre = 'Tesis dirigida'", [uid])
    pid = get_db().q("SELECT id FROM producto")[0]["id"]
    get_db().execute("INSERT INTO producto_autor (producto_id, externo_id, orden) VALUES (?, ?, 1)", [pid, sofia])
    assert "Mamani" in client.get("/estudiantes").text
