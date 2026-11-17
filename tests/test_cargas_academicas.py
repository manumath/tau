"""Cargas de datos académicos por CSV (PLAN §61): grados y capacitación. Datos inventados."""
import base64

from app.comun import academicos, importar_grados, usuarios
from tests.conftest import HX, PASS_TEMP, login

GRADOS = ("Correo,Grado,Título,Institución,País,Año\n"
          "inv@test.cl,Licenciado,Licenciatura en Matemática,Universidad Uno,Bolivia,2004\n"
          "inv@test.cl,M.Sc.,Maestría en Matemática,Universidad Dos,Chile,2008\n"
          "inv@test.cl,Doctor,,Universidad Tres,,\n"
          "inv@test.cl,bachiller,,,,\n"
          "nadie@test.cl,doctor,,,,\n")


def test_leer_y_aplicar_grados(app):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    academicos.agregar_grado(emmy, {"nivel": "doctorado", "institucion": "Universidad Tres"})  # ya estaba
    personas, errores = importar_grados.leer(GRADOS.encode())
    assert not errores
    p = {x["email"]: x for x in personas}
    assert "No hay una persona registrada" in p["nadie@test.cl"]["errores"][0]
    assert any("Elija el nivel" in e for e in p["inv@test.cl"]["errores"])  # «bachiller» no es un nivel
    assert p["inv@test.cl"]["repetidos"] == 1 and [g["nivel"] for g in p["inv@test.cl"]["grados"]] == [
        "licenciatura", "maestria"]
    # Una persona con errores no se carga: se corrige el archivo y se vuelve a subir.
    assert importar_grados.aplicar(personas, emmy) == 0
    personas, _ = importar_grados.leer("\n".join(GRADOS.splitlines()[:4]).encode())
    assert importar_grados.aplicar(personas, emmy) == 2
    assert [g["nivel"] for g in academicos.grados(emmy)] == ["doctorado", "maestria", "licenciatura"]
    # Volver a subirlo no duplica.
    personas, _ = importar_grados.leer("\n".join(GRADOS.splitlines()[:4]).encode())
    assert importar_grados.aplicar(personas, emmy) == 0


def test_pantalla_de_grados_por_permiso(admin, client):
    contenido = "\n".join(GRADOS.splitlines()[:3]).encode()
    r = admin.post("/admin/usuarios/importar-grados/revisar", headers=HX,
                   files={"archivo": ("g.csv", contenido, "text/csv")})
    assert "Agregar 2 grado(s)" in r.text
    admin.post("/admin/usuarios/importar-grados/confirmar", headers=HX,
               data={"contenido": base64.b64encode(contenido).decode()})
    assert len(academicos.grados(usuarios.por_email("inv@test.cl")["id"])) == 2
    assert "Importar grados" in admin.get("/admin/usuarios").text
    # Un investigador sin rol no llega.
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/admin/usuarios/importar-grados", headers=HX).status_code == 403


# --- Capacitación ---------------------------------------------------------------------------------------------

def test_importar_capacitaciones(carrera):
    from datetime import date

    from app.calidad import capacitacion, importar_capacitacion
    from app.comun import vinculos
    emmy = usuarios.por_email("inv@test.cl")["id"]
    vinculos.agregar(emmy, "titular", "2015-01-01")
    csv_ = ("email,titulo,institucion,area,horas,fecha_inicio,fecha_fin,anio\n"
            "inv@test.cl,Taller de escritura,Instituto,Investigación,10,,,2023\n"
            "inv@test.cl,Curso de didáctica,,pedagógica,,2024-03-01,2024-03-10,\n"
            "inv@test.cl,Curso raro,,astrología,,,,2024\n"
            "admin@test.cl,Curso,,otra,,,,2024\n"
            "nadie@test.cl,Curso,,otra,,,,2024\n")
    filas, errores = importar_capacitacion.leer(csv_.encode())
    assert not errores
    assert [f["estado"] for f in filas] == ["nueva", "nueva", "error", "error", "error"]
    assert filas[0]["datos"]["fecha_fin"] == "2023-12-31" and filas[0]["datos"]["area"] == "investigacion"
    assert "Elija el área" in filas[2]["mensaje"] and "vínculo" in filas[3]["mensaje"]
    contenido = csv_.encode()
    r = carrera.post("/calidad/capacitacion/importar/revisar", headers=HX,
                     files={"archivo": ("c.csv", contenido, "text/csv")})
    assert "Registrar 2 capacitación(es)" in r.text
    carrera.post("/calidad/capacitacion/importar/confirmar", headers=HX,
                 data={"contenido": base64.b64encode(contenido).decode()})
    assert len(capacitacion.listar(usuario=emmy)) == 2
    # Volver a subirlo no duplica; el año en curso se registra con la fecha de hoy.
    hoy = date.today()
    otra = f"email,titulo,area,anio\ninv@test.cl,Taller de escritura,investigacion,2023\ninv@test.cl,Nuevo,otra,{hoy.year}\n"
    filas, _ = importar_capacitacion.leer(otra.encode())
    assert [f["estado"] for f in filas] == ["existe", "nueva"] and filas[1]["datos"]["fecha_fin"] == hoy.isoformat()


def test_importar_capacitaciones_solo_quien_registra(client):
    emmy = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(emmy, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    assert client.get("/calidad/capacitacion/importar", headers=HX).status_code == 403
    assert client.post("/calidad/capacitacion/importar/confirmar", headers=HX, data={"contenido": ""}).status_code == 403
